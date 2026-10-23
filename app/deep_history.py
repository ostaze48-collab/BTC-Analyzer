from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .config import settings
from .historical_analogs import _evaluate_path, _safe_float, _similarity, _signature
from .indicators import snapshot

MAX_BARS = 12000
MAX_PAGES = 12
ARCHIVE_TTL_SECONDS = 1800
COMPUTE_TTL_SECONDS = 300
HORIZON_BY_BRAIN = {"SCALP": 48, "INTRADAY": 64, "SWING": 90}


class DeepHistoryResearch:
    """Cached longer anchor-timeframe memory for research only."""

    def __init__(self):
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._last_key: tuple[Any, ...] | None = None
        self._last_compute = 0.0
        self._lock = asyncio.Lock()
        self.state: dict[str, Any] = {"status": "BOOTING", "weight_in_master": 0.0}

    async def _fetch(self, interval: str) -> list[dict[str, Any]]:
        cached = self._cache.get(interval)
        now = time.monotonic()
        if cached and now - cached[0] < ARCHIVE_TTL_SECONDS:
            return cached[1]
        rows: list[dict[str, Any]] = []
        end_ms = int(time.time() * 1000)
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            for _ in range(MAX_PAGES):
                payload = None
                last_error: Exception | None = None
                for base in settings.rest_bases:
                    try:
                        r = await client.get(
                            f"{base}/api/v3/klines",
                            params={"symbol": settings.symbol, "interval": interval, "endTime": end_ms, "limit": 1000},
                        )
                        r.raise_for_status(); payload = r.json(); break
                    except Exception as exc:
                        last_error = exc
                if payload is None:
                    raise RuntimeError(f"Deep history failed for {interval}: {last_error}")
                if not payload:
                    break
                batch = [{
                    "time": int(x[0] // 1000), "close_time": int(x[6] // 1000),
                    "open": float(x[1]), "high": float(x[2]), "low": float(x[3]),
                    "close": float(x[4]), "volume": float(x[5]), "closed": True,
                } for x in payload]
                rows = batch + rows
                end_ms = int(payload[0][0]) - 1
                if len(payload) < 1000 or len(rows) >= MAX_BARS:
                    break
        unique = {r["time"]: r for r in rows}
        ordered = [unique[k] for k in sorted(unique)][-MAX_BARS:]
        self._cache[interval] = (time.monotonic(), ordered)
        return ordered

    @staticmethod
    def _anchor_signature(s: dict[str, Any]) -> dict[str, float | str]:
        neutral_layers = {k: {"direction": "NEUTRAL", "bias": 0.0} for k in ("MICRO", "INTRADAY", "SWING", "MACRO")}
        return _signature(s, neutral_layers, {"regime": "TRANSITION"})

    async def refresh(self, proposal: dict[str, Any] | None, current_snapshot: dict[str, Any] | None, force: bool = False) -> dict[str, Any]:
        proposal = proposal or {}; current_snapshot = current_snapshot or {}
        direction = str(proposal.get("direction", "")); anchor = str(proposal.get("anchor", ""))
        if direction not in ("LONG", "SHORT") or not anchor or not current_snapshot:
            self.state = {"status": "NO_ACTIVE_CANDIDATE", "weight_in_master": 0.0}; return self.state
        if anchor not in settings.native_intervals:
            self.state = {"status": "UNSUPPORTED_SYNTHETIC_ANCHOR", "anchor": anchor, "weight_in_master": 0.0}; return self.state

        risk_pct = _safe_float(proposal.get("risk_pct"), 0.0)
        if risk_pct <= 0:
            entry = _safe_float(proposal.get("entry"), 0.0); stop = _safe_float(proposal.get("stop_loss"), 0.0)
            risk_pct = abs(entry - stop) / entry * 100.0 if entry else 0.0
        key = (proposal.get("brain"), direction, anchor, round(risk_pct, 2), current_snapshot.get("trend"), current_snapshot.get("structure"))
        now = time.monotonic()
        if not force and key == self._last_key and now - self._last_compute < COMPUTE_TTL_SECONDS:
            return self.state
        if self._lock.locked():
            return self.state

        async with self._lock:
            try:
                history = await self._fetch(anchor)
            except Exception as exc:
                self.state = {"status": "SOURCE_ERROR", "error": str(exc)[:180], "weight_in_master": 0.0}; return self.state
            horizon = HORIZON_BY_BRAIN.get(str(proposal.get("brain", "INTRADAY")), 64)
            if len(history) < 300 + horizon:
                self.state = {"status": "INSUFFICIENT_HISTORY", "bars": len(history), "weight_in_master": 0.0}; return self.state

            current_sig = self._anchor_signature(current_snapshot)
            last_usable = len(history) - horizon - 1
            stride = max(1, (last_usable - 240) // 360)
            matches: list[dict[str, Any]] = []
            for idx in range(240, last_usable, stride):
                past = snapshot(history[max(0, idx - 240): idx + 1])
                if not past: continue
                sim = _similarity(current_sig, self._anchor_signature(past))
                if sim < 0.55: continue
                entry = float(history[idx]["close"])
                outcome = _evaluate_path(history[idx + 1: idx + 1 + horizon], direction, entry, risk_pct)
                matches.append({"time": int(history[idx]["close_time"]), "similarity": round(sim, 4), "entry": round(entry, 2), **outcome})

            matches.sort(key=lambda x: (x["similarity"], x["time"]), reverse=True); top = matches[:30]
            if not top:
                self.state = {"status": "NO_CLOSE_ANALOGS", "bars_scanned": len(history), "anchor": anchor, "weight_in_master": 0.0}
            else:
                hit = {f"hit_{r}r_pct": round(sum(1 for x in top if x["max_r"] >= r) / len(top) * 100, 2) for r in range(1, 6)}
                self.state = {
                    "status": "READY", "mode": "DEEP_ANCHOR_MEMORY_SHADOW", "weight_in_master": 0.0,
                    "brain": proposal.get("brain"), "direction": direction, "anchor": anchor,
                    "bars_scanned": len(history), "matches": len(top), "risk_pct": round(risk_pct, 4),
                    "avg_similarity_pct": round(sum(x["similarity"] for x in top) / len(top) * 100, 2),
                    "stop_pct": round(sum(1 for x in top if x["stopped"]) / len(top) * 100, 2),
                    "avg_mfe_r": round(sum(x["mfe_r"] for x in top) / len(top), 3),
                    "avg_mae_r": round(sum(x["mae_r"] for x in top) / len(top), 3), **hit,
                    "examples": sorted(top, key=lambda x: x["time"], reverse=True)[:8],
                    "note": "Deep archive supplements full 1m→1Y current analysis; MASTER weight remains zero until OOS proof.",
                }
            self._last_key = key; self._last_compute = time.monotonic(); return self.state

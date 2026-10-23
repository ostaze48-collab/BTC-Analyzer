from __future__ import annotations

import asyncio
import math
import time
from statistics import fmean
from typing import Any

from .brains import layer_context
from .indicators import snapshot
from .regime import classify_market_regime


_LAYER_NAMES = ("MICRO", "INTRADAY", "SWING", "MACRO")
_HORIZON_BY_BRAIN = {"SCALP": 48, "INTRADAY": 64, "SWING": 90}
_MIN_HISTORY = 90
_SIGNATURE_TARGET = 720


def _dir_value(value: str | None) -> float:
    if value in ("BULLISH", "LONG"):
        return 1.0
    if value in ("BEARISH", "SHORT"):
        return -1.0
    return 0.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def _bars_until(history: list[dict[str, Any]], ts: int, limit: int = 240) -> list[dict[str, Any]]:
    rows = [c for c in history if int(c.get("close_time", c.get("time", 0))) <= ts and c.get("closed", True)]
    return rows[-limit:]


def _quick_context(history_by_tf: dict[str, list[dict[str, Any]]], ts: int) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    snaps: dict[str, dict[str, Any]] = {}
    for tf, rows in history_by_tf.items():
        subset = _bars_until(rows, ts)
        snaps[tf] = snapshot(subset) if len(subset) >= 30 else {}
    layers = layer_context(snaps, cycle=None)
    regime = classify_market_regime(snaps, layers)
    return snaps, layers, regime


def _signature(anchor: dict[str, Any], layers: dict[str, Any], regime: dict[str, Any]) -> dict[str, float | str]:
    close = max(_safe_float(anchor.get("close"), 1.0), 1e-9)
    ema20 = _safe_float(anchor.get("ema20"), close)
    ema50 = _safe_float(anchor.get("ema50"), close)
    vwap = _safe_float(anchor.get("vwap20"), close)
    out: dict[str, float | str] = {
        "trend": str(anchor.get("trend", "MIXED")),
        "structure": str(anchor.get("structure", "RANGE")),
        "regime": str(regime.get("regime", "TRANSITION")),
        "rsi": (_safe_float(anchor.get("rsi14"), 50.0) - 50.0) / 50.0,
        "ema20_dist": (close / ema20 - 1.0) if ema20 else 0.0,
        "ema50_dist": (close / ema50 - 1.0) if ema50 else 0.0,
        "vwap_dist": (close / vwap - 1.0) if vwap else 0.0,
        "volume": max(-1.0, min(2.0, _safe_float(anchor.get("volume_ratio"), 1.0) - 1.0)),
        "volatility": max(0.0, min(5.0, _safe_float(anchor.get("volatility_pct"), 0.0))),
    }
    for name in _LAYER_NAMES:
        layer = layers.get(name, {})
        out[f"layer_{name.lower()}"] = _safe_float(layer.get("bias"), _dir_value(layer.get("direction")))
    return out


def _similarity(current: dict[str, float | str], past: dict[str, float | str]) -> float:
    numeric_scales = {
        "rsi": 0.55, "ema20_dist": 0.025, "ema50_dist": 0.04,
        "vwap_dist": 0.025, "volume": 1.0, "volatility": 1.5,
        "layer_micro": 0.65, "layer_intraday": 0.65,
        "layer_swing": 0.65, "layer_macro": 0.65,
    }
    weighted_distance = 0.0
    weight = 0.0
    for key, scale in numeric_scales.items():
        a = _safe_float(current.get(key))
        b = _safe_float(past.get(key))
        d = min(2.0, abs(a - b) / max(scale, 1e-9))
        w = 1.35 if key.startswith("layer_") else 1.0
        weighted_distance += d * w
        weight += w
    distance = weighted_distance / weight if weight else 2.0
    score = math.exp(-0.72 * distance)
    if current.get("trend") == past.get("trend"):
        score += 0.07
    if current.get("structure") == past.get("structure"):
        score += 0.07
    if current.get("regime") == past.get("regime"):
        score += 0.10
    return max(0.0, min(1.0, score))


def _evaluate_path(future: list[dict[str, Any]], direction: str, entry: float, risk_pct: float) -> dict[str, Any]:
    if not future or entry <= 0 or risk_pct <= 0:
        return {"max_r": 0.0, "stopped": False, "expired": True, "mfe_r": 0.0, "mae_r": 0.0}
    risk_price = entry * risk_pct / 100.0
    sign = 1.0 if direction == "LONG" else -1.0
    stop = entry - sign * risk_price
    max_r = mfe_r = mae_r = 0.0
    for candle in future:
        high = _safe_float(candle.get("high"), entry)
        low = _safe_float(candle.get("low"), entry)
        favorable = (high - entry) / risk_price if direction == "LONG" else (entry - low) / risk_price
        adverse = (entry - low) / risk_price if direction == "LONG" else (high - entry) / risk_price
        mfe_r = max(mfe_r, favorable)
        mae_r = max(mae_r, adverse)
        stop_hit = low <= stop if direction == "LONG" else high >= stop
        reached = max(0.0, favorable)
        if stop_hit:
            return {"max_r": round(max_r, 3), "stopped": True, "expired": False,
                    "mfe_r": round(max(0.0, mfe_r), 3), "mae_r": round(max(0.0, mae_r), 3)}
        max_r = max(max_r, min(5.0, reached))
        if max_r >= 5.0:
            return {"max_r": 5.0, "stopped": False, "expired": False,
                    "mfe_r": round(max(0.0, mfe_r), 3), "mae_r": round(max(0.0, mae_r), 3)}
    return {"max_r": round(max_r, 3), "stopped": False, "expired": True,
            "mfe_r": round(max(0.0, mfe_r), 3), "mae_r": round(max(0.0, mae_r), 3)}


def _history_revision(history_by_tf: dict[str, list[dict[str, Any]]], brain: str, anchor_tf: str) -> tuple[Any, ...]:
    parts: list[Any] = [brain, anchor_tf]
    for tf in sorted(history_by_tf):
        rows = history_by_tf[tf]
        first = int(rows[0].get("time", 0)) if rows else 0
        last = int(rows[-1].get("time", 0)) if rows else 0
        parts.extend((tf, len(rows), first, last))
    return tuple(parts)


def build_signature_memory(
    history_by_tf: dict[str, list[dict[str, Any]]],
    brain: str,
    anchor_tf: str,
    max_candidates: int = _SIGNATURE_TARGET,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build compact prior-market signatures once per history revision."""
    started = time.monotonic()
    anchor_history = list(history_by_tf.get(anchor_tf, []))
    horizon = _HORIZON_BY_BRAIN.get(brain, 64)
    last_usable = len(anchor_history) - horizon - 1
    if last_usable <= _MIN_HISTORY:
        return [], {"candidates": 0, "build_seconds": 0.0, "stride": 0}

    candidate_count = max(1, last_usable - _MIN_HISTORY)
    stride = max(1, math.ceil(candidate_count / max(1, max_candidates)))
    memory: list[dict[str, Any]] = []
    for idx in range(_MIN_HISTORY, last_usable, stride):
        candle = anchor_history[idx]
        ts = int(candle.get("close_time", candle.get("time", 0)))
        snaps, layers, regime = _quick_context(history_by_tf, ts)
        past_anchor = snaps.get(anchor_tf, {})
        if not past_anchor:
            continue
        memory.append({
            "idx": idx, "time": ts, "entry": _safe_float(candle.get("close"), 0.0),
            "regime": regime.get("regime"), "trend": past_anchor.get("trend"),
            "structure": past_anchor.get("structure"),
            "signature": _signature(past_anchor, layers, regime),
        })
    return memory, {
        "candidates": len(memory), "build_seconds": round(time.monotonic() - started, 3),
        "stride": stride, "anchor_bars": len(anchor_history), "target_candidates": max_candidates,
    }


def analyze_historical_analogs(
    proposal: dict[str, Any] | None,
    current_snapshots: dict[str, dict[str, Any]],
    current_layers: dict[str, Any],
    current_regime: dict[str, Any],
    history_by_tf: dict[str, list[dict[str, Any]]],
    max_matches: int = 24,
    signature_memory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    proposal = proposal or {}
    direction = str(proposal.get("direction", ""))
    anchor_tf = str(proposal.get("anchor", ""))
    anchor_history = list(history_by_tf.get(anchor_tf, []))
    current_anchor = current_snapshots.get(anchor_tf, {})
    if direction not in ("LONG", "SHORT") or not anchor_tf or not current_anchor:
        return {"status": "NO_ACTIVE_CANDIDATE", "weight_in_master": 0.0, "matches": 0}
    if len(anchor_history) < _MIN_HISTORY + 20:
        return {"status": "INSUFFICIENT_HISTORY", "weight_in_master": 0.0,
                "matches": 0, "anchor": anchor_tf, "available_bars": len(anchor_history)}

    risk_pct = _safe_float(proposal.get("risk_pct"), 0.0)
    if risk_pct <= 0:
        entry = _safe_float(proposal.get("entry"), 0.0)
        stop = _safe_float(proposal.get("stop_loss"), 0.0)
        risk_pct = abs(entry - stop) / entry * 100.0 if entry else 0.0
    if risk_pct <= 0:
        return {"status": "INVALID_RISK", "weight_in_master": 0.0, "matches": 0}

    current_sig = _signature(current_anchor, current_layers, current_regime)
    brain = str(proposal.get("brain", "INTRADAY"))
    horizon = _HORIZON_BY_BRAIN.get(brain, 64)

    cache_used = signature_memory is not None
    if signature_memory is None:
        # Conservative fallback while the background signature cache is building.
        signature_memory, _ = build_signature_memory(history_by_tf, brain, anchor_tf, max_candidates=180)

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in signature_memory:
        sim = _similarity(current_sig, row.get("signature") or {})
        if sim >= 0.52:
            scored.append((sim, row))
    scored.sort(key=lambda x: (x[0], x[1].get("time", 0)), reverse=True)

    top_rows = scored[:max_matches]
    top: list[dict[str, Any]] = []
    for sim, row in top_rows:
        idx = int(row.get("idx", -1))
        if idx < 0 or idx + 1 >= len(anchor_history):
            continue
        entry = _safe_float(row.get("entry"), 0.0)
        result = _evaluate_path(anchor_history[idx + 1: idx + 1 + horizon], direction, entry, risk_pct)
        top.append({
            "time": int(row.get("time", 0)), "entry": round(entry, 2),
            "similarity": round(sim, 4), "regime": row.get("regime"),
            "trend": row.get("trend"), "structure": row.get("structure"), **result,
        })

    if not top:
        return {"status": "NO_CLOSE_ANALOGS", "weight_in_master": 0.0, "matches": 0,
                "anchor": anchor_tf, "direction": direction, "risk_pct": round(risk_pct, 4),
                "signature_cache_used": cache_used, "signature_candidates_scanned": len(signature_memory)}

    rates = {f"hit_{r}r_pct": round(sum(1 for m in top if m["max_r"] >= r) / len(top) * 100.0, 2) for r in range(1, 6)}
    stop_rate = sum(1 for m in top if m["stopped"]) / len(top) * 100.0
    avg_similarity = fmean(m["similarity"] for m in top)
    avg_mfe = fmean(m["mfe_r"] for m in top)
    avg_mae = fmean(m["mae_r"] for m in top)
    quality = "STRONG" if len(top) >= 18 and avg_similarity >= 0.70 else ("MODERATE" if len(top) >= 10 else "WEAK")

    return {
        "status": "READY", "mode": "HISTORICAL_ANALOG_SHADOW", "weight_in_master": 0.0,
        "brain": brain, "direction": direction, "anchor": anchor_tf,
        "risk_pct": round(risk_pct, 4), "horizon_bars": horizon,
        "history_bars_scanned": len(anchor_history),
        "signature_cache_used": cache_used,
        "signature_candidates_scanned": len(signature_memory),
        "matches": len(top), "quality": quality,
        "avg_similarity_pct": round(avg_similarity * 100.0, 2),
        "stop_before_1r_pct": round(stop_rate, 2),
        "avg_mfe_r": round(avg_mfe, 3), "avg_mae_r": round(avg_mae, 3),
        **rates,
        "recent_examples": sorted(top, key=lambda m: m["time"], reverse=True)[:8],
        "method": "Historical signatures are precomputed across the loaded multi-timeframe archive; only top-similarity states are path-evaluated with STOP_FIRST_CONSERVATIVE.",
        "warning": "Historical analogs are evidence, not a guarantee. MASTER weight remains zero until separate out-of-sample validation passes.",
    }


class HistoricalAnalogEngine:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._last_key: tuple[Any, ...] | None = None
        self._last_at = 0.0
        self.state: dict[str, Any] = {"status": "BOOTING", "weight_in_master": 0.0, "matches": 0}
        self._lock = asyncio.Lock()
        self._memory: list[dict[str, Any]] = []
        self._memory_key: tuple[Any, ...] | None = None
        self._memory_meta: dict[str, Any] = {"status": "EMPTY", "candidates": 0}
        self._memory_task: asyncio.Task | None = None
        self._pending_memory_key: tuple[Any, ...] | None = None

    async def stop(self) -> None:
        if self._memory_task and not self._memory_task.done():
            self._memory_task.cancel()
        if self._memory_task:
            try:
                await self._memory_task
            except (asyncio.CancelledError, Exception):
                pass

    def _consume_memory_task(self, current_key: tuple[Any, ...]) -> None:
        task = self._memory_task
        if not task or not task.done():
            return
        try:
            memory, meta = task.result()
            if self._pending_memory_key == current_key:
                self._memory = memory
                self._memory_key = current_key
                self._memory_meta = {"status": "READY", **meta}
        except Exception as exc:
            self._memory_meta = {"status": "ERROR", "candidates": len(self._memory), "error": str(exc)[:160]}
        finally:
            self._memory_task = None
            self._pending_memory_key = None

    def _schedule_memory(self, key: tuple[Any, ...], history_by_tf: dict[str, list[dict[str, Any]]], brain: str, anchor_tf: str) -> None:
        if self._memory_key == key:
            return
        if self._memory_task and not self._memory_task.done():
            return
        self._pending_memory_key = key
        self._memory_meta = {"status": "BUILDING", "candidates": len(self._memory), "target_candidates": _SIGNATURE_TARGET}
        self._memory_task = asyncio.create_task(
            asyncio.to_thread(build_signature_memory, history_by_tf, brain, anchor_tf, _SIGNATURE_TARGET),
            name=f"historical-signatures-{brain.lower()}",
        )

    async def refresh(
        self,
        proposal: dict[str, Any] | None,
        snapshots: dict[str, dict[str, Any]],
        layers: dict[str, Any],
        regime: dict[str, Any],
        history_by_tf: dict[str, list[dict[str, Any]]],
        force: bool = False,
    ) -> dict[str, Any]:
        proposal = proposal or {}
        brain = str(proposal.get("brain", ""))
        anchor_tf = str(proposal.get("anchor", ""))
        history_key = _history_revision(history_by_tf, brain, anchor_tf) if brain and anchor_tf else tuple()
        self._consume_memory_task(history_key)
        if brain and anchor_tf:
            self._schedule_memory(history_key, history_by_tf, brain, anchor_tf)

        key = (
            brain, proposal.get("direction"), anchor_tf,
            round(_safe_float(proposal.get("risk_pct")), 2), regime.get("regime"),
            (layers.get("MACRO") or {}).get("direction"),
            (snapshots.get(anchor_tf) or {}).get("trend"),
            self._memory_key == history_key,
            len(self._memory) if self._memory_key == history_key else 0,
        )
        now = time.monotonic()
        if not force and key == self._last_key and now - self._last_at < self.ttl_seconds:
            self.state["signature_cache"] = dict(self._memory_meta)
            return self.state
        if self._lock.locked():
            return self.state
        async with self._lock:
            usable_memory = self._memory if self._memory_key == history_key else None
            self.state = await asyncio.to_thread(
                analyze_historical_analogs,
                proposal, snapshots, layers, regime, history_by_tf, 24, usable_memory,
            )
            self.state["signature_cache"] = dict(self._memory_meta)
            self._last_key = key
            self._last_at = time.monotonic()
            return self.state

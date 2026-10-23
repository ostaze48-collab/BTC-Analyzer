from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .config import settings

DAY_MS = 86_400_000

# Deeper history is loaded only for the currently relevant brain. This keeps
# startup light while giving each strategy enough prior regimes to compare.
PROFILE_DAYS: dict[str, dict[str, int]] = {
    "SCALP": {"5m": 45, "15m": 90, "1h": 180, "4h": 365, "1d": 1460},
    "INTRADAY": {"15m": 180, "1h": 365, "4h": 1095, "1d": 1825, "1w": 2555},
    "SWING": {"4h": 1825, "1d": 3285, "1w": 4380, "1M": 4380},
}


def _parse(row: list[Any], now_ms: int) -> dict[str, Any]:
    close_ms = int(row[6])
    return {
        "time": int(row[0] // 1000),
        "close_time": int(close_ms // 1000),
        "open": float(row[1]), "high": float(row[2]), "low": float(row[3]),
        "close": float(row[4]), "volume": float(row[5]),
        "closed": close_ms < now_ms,
    }


class HistoricalArchive:
    """Lazy public-market archive for historical analog research.

    The archive never changes MASTER directly. It only enlarges the history used
    by the shadow HistoricalAnalogEngine. Cache is in memory; losing the cache on
    a Render restart affects speed/sample depth, not trading-state correctness.
    """

    def __init__(self, ttl_seconds: int = 21_600):
        self.ttl_seconds = ttl_seconds
        self._cache: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self._loaded_at: dict[str, float] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self.states: dict[str, dict[str, Any]] = {}

    def state(self, brain: str | None = None) -> dict[str, Any]:
        brain = str(brain or "")
        if not brain:
            return {"status": "IDLE", "mode": "LAZY_ARCHIVE", "weight_in_master": 0.0}
        return self.states.get(brain, {
            "status": "NOT_LOADED", "brain": brain, "mode": "LAZY_ARCHIVE",
            "weight_in_master": 0.0, "coverage": {},
        })

    def history(self, brain: str | None) -> dict[str, list[dict[str, Any]]]:
        return self._cache.get(str(brain or ""), {})

    def schedule(self, brain: str | None) -> dict[str, Any]:
        brain = str(brain or "")
        if brain not in PROFILE_DAYS:
            return self.state(brain)
        now = time.monotonic()
        if brain in self._cache and now - self._loaded_at.get(brain, 0.0) < self.ttl_seconds:
            return self.state(brain)
        task = self._tasks.get(brain)
        if task and not task.done():
            return self.state(brain)
        self.states[brain] = {
            "status": "LOADING", "brain": brain, "mode": "LAZY_ARCHIVE",
            "weight_in_master": 0.0, "coverage": self.state(brain).get("coverage", {}),
        }
        self._tasks[brain] = asyncio.create_task(self._load(brain), name=f"historical-archive-{brain.lower()}")
        return self.state(brain)

    async def stop(self) -> None:
        for task in self._tasks.values():
            if task and not task.done():
                task.cancel()
        for task in self._tasks.values():
            if task:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    async def _fetch_interval(
        self, client: httpx.AsyncClient, interval: str, days: int,
    ) -> list[dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        end_ms = now_ms
        cursor = max(0, end_ms - int(days * DAY_MS))
        rows: list[dict[str, Any]] = []
        while cursor < end_ms:
            payload = None
            last_error: Exception | None = None
            for base in settings.rest_bases:
                try:
                    r = await client.get(
                        f"{base}/api/v3/klines",
                        params={
                            "symbol": settings.symbol, "interval": interval,
                            "startTime": cursor, "endTime": end_ms, "limit": 1000,
                        },
                        timeout=20,
                    )
                    r.raise_for_status()
                    payload = r.json()
                    break
                except Exception as exc:
                    last_error = exc
            if payload is None:
                raise RuntimeError(f"archive {interval} failed: {last_error}")
            if not payload:
                break
            rows.extend(_parse(row, now_ms) for row in payload)
            nxt = int(payload[-1][6]) + 1
            if nxt <= cursor:
                break
            cursor = nxt
            if len(payload) < 1000:
                break
            await asyncio.sleep(0.03)
        unique = {int(r["time"]): r for r in rows if r.get("closed", True)}
        return [unique[k] for k in sorted(unique)]

    async def _load(self, brain: str) -> None:
        profile = PROFILE_DAYS[brain]
        coverage: dict[str, Any] = {}
        data: dict[str, list[dict[str, Any]]] = {}
        errors: list[str] = []
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                # Sequential timeframes avoid sudden request bursts on public endpoints.
                for interval, days in profile.items():
                    try:
                        rows = await self._fetch_interval(client, interval, days)
                        data[interval] = rows
                        coverage[interval] = {
                            "target_days": days,
                            "bars": len(rows),
                            "first_time": rows[0]["time"] if rows else None,
                            "last_time": rows[-1]["time"] if rows else None,
                        }
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        errors.append(str(exc)[:180])
                        coverage[interval] = {"target_days": days, "bars": 0, "error": str(exc)[:120]}
            if data:
                self._cache[brain] = data
                self._loaded_at[brain] = time.monotonic()
            self.states[brain] = {
                "status": "READY" if data and not errors else ("PARTIAL" if data else "ERROR"),
                "brain": brain, "mode": "LAZY_ARCHIVE", "weight_in_master": 0.0,
                "coverage": coverage, "errors": errors,
                "loaded_timeframes": len(data),
                "bars_loaded": sum(len(v) for v in data.values()),
                "load_seconds": round(time.monotonic() - started, 2),
                "ttl_seconds": self.ttl_seconds,
            }
        except asyncio.CancelledError:
            self.states[brain] = {
                "status": "CANCELLED", "brain": brain, "mode": "LAZY_ARCHIVE",
                "weight_in_master": 0.0, "coverage": coverage,
            }
            raise

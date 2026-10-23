from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from .config import settings

DAY_MS = 86_400_000

# Deeper history is loaded only for the currently relevant brain. This keeps
# startup light while giving each strategy enough prior regimes to compare.
# Every brain anchor timeframe is explicitly included (5m / 30m / 4h).
PROFILE_DAYS: dict[str, dict[str, int]] = {
    "SCALP": {"5m": 45, "15m": 90, "1h": 180, "4h": 365, "1d": 1460},
    "INTRADAY": {"15m": 180, "30m": 365, "1h": 365, "4h": 1095, "1d": 1825, "1w": 2555},
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
            "weight_in_master": 0.0, "coverage": {},
        }
        self._tasks[brain] = asyncio.create_task(self._load(brain), name=f"historical-archive-{brain.lower()}")
        return self.state(brain)

    async def _fetch_interval(self, client: httpx.AsyncClient, base: str, interval: str, days: int) -> list[dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        start_ms = max(0, now_ms - days * DAY_MS)
        cursor = start_ms
        rows: list[dict[str, Any]] = []
        while cursor < now_ms:
            response = await client.get(
                f"{base}/api/v3/klines",
                params={
                    "symbol": settings.symbol, "interval": interval,
                    "startTime": cursor, "endTime": now_ms, "limit": 1000,
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
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
        unique = {int(r["time"]): r for r in rows if r.get("closed")}
        return [unique[k] for k in sorted(unique)]

    async def _load(self, brain: str) -> None:
        profile = PROFILE_DAYS[brain]
        errors: list[str] = []
        result: dict[str, list[dict[str, Any]]] = {}
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for interval, days in profile.items():
                loaded = False
                for base in settings.rest_bases:
                    try:
                        result[interval] = await self._fetch_interval(client, base, interval, days)
                        loaded = True
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        errors.append(f"{interval}@{base}: {str(exc)[:100]}")
                if not loaded:
                    result[interval] = []
        self._cache[brain] = result
        self._loaded_at[brain] = time.monotonic()
        coverage = {
            tf: {
                "bars": len(rows),
                "from": rows[0]["time"] if rows else None,
                "to": rows[-1]["time"] if rows else None,
            }
            for tf, rows in result.items()
        }
        ready = sum(1 for rows in result.values() if rows) >= max(2, len(profile) // 2)
        self.states[brain] = {
            "status": "READY" if ready else "PARTIAL",
            "brain": brain, "mode": "LAZY_ARCHIVE", "weight_in_master": 0.0,
            "coverage": coverage, "errors": errors[-8:],
            "loaded_at_monotonic": round(self._loaded_at[brain], 3),
        }

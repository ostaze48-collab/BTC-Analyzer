from __future__ import annotations

import asyncio
import time
from statistics import fmean
from typing import Any

import httpx

from .config import settings
from .cycle_models import cycle_model_context

DAY_MS = 86_400_000


class CycleWalkForward:
    """Evaluate long-horizon cycle context without fitting on future data."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self.last_result: dict[str, Any] | None = None

    @property
    def running(self) -> bool:
        return self._lock.locked()

    async def run(self, years: int = 6) -> dict[str, Any]:
        years = max(3, min(int(years), 9))
        if self._lock.locked():
            raise RuntimeError("Cycle walk-forward is already running")
        async with self._lock:
            end_ms = int(time.time() * 1000)
            requested_start = end_ms - int(years * 365.25 * DAY_MS)
            # Long warm-up permits Mayer/Pi/4-year SMA to exist before holdout.
            fetch_start = max(0, requested_start - 1_650 * DAY_MS)
            rows = await self._fetch_daily(fetch_start, end_ms)
            result = await asyncio.to_thread(self._evaluate, rows, requested_start // 1000, years)
            self.last_result = result
            return result

    async def _fetch_daily(self, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = start_ms
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            while cursor < end_ms:
                payload = None
                last_error: Exception | None = None
                for base in settings.rest_bases:
                    try:
                        response = await client.get(
                            f"{base}/api/v3/klines",
                            params={
                                "symbol": settings.symbol,
                                "interval": "1d",
                                "startTime": cursor,
                                "endTime": end_ms,
                                "limit": 1000,
                            },
                        )
                        response.raise_for_status()
                        payload = response.json()
                        break
                    except Exception as exc:
                        last_error = exc
                if payload is None:
                    raise RuntimeError(f"Daily history failed: {last_error}")
                if not payload:
                    break
                for row in payload:
                    rows.append({
                        "time": int(row[0] // 1000),
                        "close_time": int(row[6] // 1000),
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                        "closed": True,
                    })
                nxt = int(payload[-1][6]) + 1
                if nxt <= cursor:
                    break
                cursor = nxt
                if len(payload) < 1000:
                    break
        unique = {r["time"]: r for r in rows}
        return [unique[k] for k in sorted(unique)]

    @staticmethod
    def _bucket_stats(samples: list[dict[str, Any]]) -> dict[str, Any]:
        if not samples:
            return {
                "samples": 0,
                "directional_accuracy_pct": 0.0,
                "mean_signed_return": 0.0,
                "mean_abs_future_return": 0.0,
                "mean_bias": 0.0,
            }
        correct = sum(1 for s in samples if s["signed_return"] > 0)
        return {
            "samples": len(samples),
            "directional_accuracy_pct": round(correct / len(samples) * 100, 2),
            "mean_signed_return": round(fmean(s["signed_return"] for s in samples), 6),
            "mean_abs_future_return": round(fmean(abs(s["future_return"]) for s in samples), 6),
            "mean_bias": round(fmean(s["bias"] for s in samples), 4),
        }

    def _evaluate(self, rows: list[dict[str, Any]], requested_start_s: int, years: int) -> dict[str, Any]:
        if len(rows) < 450:
            raise RuntimeError("Not enough daily history for cycle validation")

        # Holdout is the later 35% of the requested period, chronologically.
        requested_idx = next((i for i, r in enumerate(rows) if r["close_time"] >= requested_start_s), 0)
        requested_count = max(1, len(rows) - requested_idx)
        holdout_start_idx = requested_idx + int(requested_count * 0.65)
        holdout_start_idx = max(400, min(holdout_start_idx, len(rows) - 181))

        horizons = (30, 90, 180)
        by_horizon: dict[str, list[dict[str, Any]]] = {str(h): [] for h in horizons}
        model_buckets: dict[str, dict[str, list[dict[str, Any]]]] = {
            str(h): {} for h in horizons
        }

        # Weekly sampling reduces serial duplication while retaining many OOS observations.
        for i in range(holdout_start_idx, len(rows) - max(horizons), 7):
            history = rows[: i + 1]
            context = cycle_model_context(history)
            bias = float(context.get("bias", 0.0) or 0.0)
            price = float(rows[i]["close"])
            if not context.get("available") or price <= 0:
                continue

            for horizon in horizons:
                future = float(rows[i + horizon]["close"])
                future_return = future / price - 1.0
                signed_return = bias * future_return
                sample = {
                    "time": int(rows[i]["close_time"]),
                    "price": price,
                    "bias": bias,
                    "future_return": future_return,
                    "signed_return": signed_return,
                }
                by_horizon[str(horizon)].append(sample)

                for name, model in (context.get("models") or {}).items():
                    mbias = float(model.get("bias", 0.0) or 0.0)
                    model_buckets[str(horizon)].setdefault(name, []).append({
                        **sample,
                        "bias": mbias,
                        "signed_return": mbias * future_return,
                    })

        horizon_stats = {h: self._bucket_stats(samples) for h, samples in by_horizon.items()}
        model_stats: dict[str, Any] = {}
        for horizon, buckets in model_buckets.items():
            model_stats[horizon] = {name: self._bucket_stats(samples) for name, samples in buckets.items()}

        # Readiness uses 90-day context because it matches cycle/valuation intent better than short horizons.
        primary = horizon_stats.get("90", self._bucket_stats([]))
        return {
            "validation_type": "CHRONOLOGICAL_HOLDOUT_NO_REFIT",
            "years_requested": years,
            "holdout_start": int(rows[holdout_start_idx]["close_time"]),
            "holdout_end": int(rows[-1]["close_time"]),
            "sampling_days": 7,
            "horizons_days": list(horizons),
            "primary_horizon_days": 90,
            "primary": primary,
            "by_horizon": horizon_stats,
            "by_model": model_stats,
            "notes": [
                "Cycle models are evaluated as context bias, not standalone trades.",
                "Only information available at each historical timestamp is used.",
                "Overlapping forward horizons remain correlated; weekly sampling reduces but does not remove this dependence.",
            ],
        }

from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from datetime import datetime, timezone
from typing import Awaitable, Callable

import httpx
import websockets

from .config import settings

MarketCallback = Callable[[dict], Awaitable[None]]


def _calendar_group(ts: int, interval: str) -> tuple[int, int, int]:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    if interval == "3M":
        bucket = (dt.month - 1) // 3
        return dt.year, bucket, (bucket + 1) * 3
    if interval == "6M":
        bucket = (dt.month - 1) // 6
        return dt.year, bucket, (bucket + 1) * 6
    return dt.year, 0, 12


def aggregate_monthly(monthly: list[dict], interval: str) -> list[dict]:
    """Aggregate native 1M candles into 3M, 6M and 1y UTC calendar candles."""
    if interval not in ("3M", "6M", "1y"):
        raise ValueError(f"Unsupported synthetic interval: {interval}")
    groups: dict[tuple[int, int, int], list[dict]] = {}
    for candle in monthly:
        groups.setdefault(_calendar_group(int(candle["time"]), interval), []).append(candle)

    out: list[dict] = []
    for key in sorted(groups):
        rows = sorted(groups[key], key=lambda x: x["time"])
        year, _bucket, expected_last_month = key
        last_dt = datetime.fromtimestamp(int(rows[-1]["time"]), tz=timezone.utc)
        period_complete = last_dt.year == year and last_dt.month == expected_last_month and bool(rows[-1].get("closed"))
        out.append({
            "time": int(rows[0]["time"]),
            "close_time": int(rows[-1].get("close_time", rows[-1]["time"])),
            "open": float(rows[0]["open"]),
            "high": max(float(x["high"]) for x in rows),
            "low": min(float(x["low"]) for x in rows),
            "close": float(rows[-1]["close"]),
            "volume": sum(float(x["volume"]) for x in rows),
            "closed": period_complete,
        })
    return out


class MarketData:
    def __init__(self, callback: MarketCallback):
        self.callback = callback
        self.candles: dict[str, deque] = {
            interval: deque(maxlen=settings.history_limit) for interval in settings.intervals
        }
        self.last_price: float | None = None
        self.connected = False
        self._task: asyncio.Task | None = None
        self._history_task: asyncio.Task | None = None

    async def _load_interval(self, client: httpx.AsyncClient, base: str, interval: str) -> None:
        response = await client.get(
            f"{base}/api/v3/klines",
            params={"symbol": settings.symbol, "interval": interval, "limit": settings.history_limit},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        now_ms = int(time.time() * 1000)
        series = deque(maxlen=settings.history_limit)
        for row in data:
            close_time_ms = int(row[6])
            series.append({
                "time": int(row[0] // 1000), "close_time": int(close_time_ms // 1000),
                "open": float(row[1]), "high": float(row[2]), "low": float(row[3]),
                "close": float(row[4]), "volume": float(row[5]),
                "closed": close_time_ms < now_ms,
            })
        self.candles[interval] = series
        if data and interval == "1m":
            self.last_price = float(data[-1][4])

    def _rebuild_synthetic(self) -> None:
        monthly = list(self.candles.get("1M", []))
        if not monthly:
            return
        for interval in settings.synthetic_intervals:
            rows = aggregate_monthly(monthly, interval)
            self.candles[interval] = deque(rows[-settings.history_limit:], maxlen=settings.history_limit)

    async def load_history(self) -> str:
        last_error: Exception | None = None
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for base in settings.rest_bases:
                try:
                    await asyncio.gather(*(self._load_interval(client, base, i) for i in settings.native_intervals))
                    self._rebuild_synthetic()
                    return base
                except Exception as exc:
                    last_error = exc
        raise RuntimeError(f"All history endpoints failed: {last_error}")

    def _history_ready(self) -> bool:
        return all(
            sum(1 for c in self.candles[i] if c.get("closed")) >= settings.min_bars(i)
            for i in settings.intervals
        )

    async def _history_retry_loop(self) -> None:
        while not self._history_ready():
            try:
                base = await self.load_history()
                await self.callback({"type": "history_ready", "source": base})
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.callback({"type": "history_error", "error": str(exc)[:220]})
                await asyncio.sleep(20)

    def _upsert(self, interval: str, candle: dict) -> None:
        series = self.candles[interval]
        if series and series[-1]["time"] == candle["time"]:
            series[-1] = candle
        else:
            series.append(candle)

    async def start(self) -> None:
        try:
            base = await self.load_history()
            await self.callback({"type": "history_ready", "source": base})
        except Exception as exc:
            await self.callback({"type": "history_error", "error": str(exc)[:220]})
            self._history_task = asyncio.create_task(self._history_retry_loop(), name="market-history-retry")
        self._task = asyncio.create_task(self.run(), name="market-stream")

    async def stop(self) -> None:
        for task in (self._task, self._history_task):
            if task:
                task.cancel()
        for task in (self._task, self._history_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def run(self) -> None:
        streams = "/".join(f"{settings.symbol.lower()}@kline_{interval}" for interval in settings.native_intervals)
        endpoint_index = 0
        while True:
            base = settings.ws_bases[endpoint_index % len(settings.ws_bases)]
            endpoint_index += 1
            url = f"{base}/stream?streams={streams}"
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=20, close_timeout=5, max_size=5_000_000) as ws:
                    self.connected = True
                    await self.callback({"type": "connection", "connected": True, "source": base})
                    async for raw in ws:
                        msg = json.loads(raw)
                        payload = msg.get("data", msg)
                        k = payload.get("k")
                        if not k:
                            continue
                        candle = {
                            "time": int(k["t"] // 1000), "close_time": int(k["T"] // 1000),
                            "open": float(k["o"]), "high": float(k["h"]), "low": float(k["l"]),
                            "close": float(k["c"]), "volume": float(k["v"]), "closed": bool(k["x"]),
                        }
                        interval = k["i"]
                        if interval not in self.candles:
                            continue
                        self._upsert(interval, candle)
                        self.last_price = candle["close"]
                        await self.callback({"type": "market", "interval": interval, "candle": candle, "closed": candle["closed"]})

                        if interval == "1M":
                            self._rebuild_synthetic()
                            for synthetic in settings.synthetic_intervals:
                                if self.candles[synthetic]:
                                    sc = self.candles[synthetic][-1]
                                    await self.callback({"type": "market", "interval": synthetic, "candle": sc, "closed": sc["closed"], "synthetic": True})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                await self.callback({"type": "connection", "connected": False, "source": base, "error": str(exc)[:220]})
                await asyncio.sleep(3)

    def get(self, interval: str, limit: int = 500) -> list[dict]:
        if interval not in self.candles:
            return []
        return list(self.candles[interval])[-limit:]

    def get_closed(self, interval: str, limit: int = 500) -> list[dict]:
        if interval not in self.candles:
            return []
        closed = [c for c in self.candles[interval] if c.get("closed")]
        return closed[-limit:]

from __future__ import annotations

import asyncio
import json
from collections import deque
from typing import Awaitable, Callable

import httpx
import websockets

from .config import settings

MarketCallback = Callable[[dict], Awaitable[None]]


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
            params={
                "symbol": settings.symbol,
                "interval": interval,
                "limit": settings.history_limit,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        series = deque(maxlen=settings.history_limit)
        for row in data:
            series.append(
                {
                    "time": int(row[0] // 1000),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume": float(row[5]),
                    "closed": True,
                }
            )
        self.candles[interval] = series
        if data and interval == "1m":
            self.last_price = float(data[-1][4])

    async def load_history(self) -> str:
        last_error: Exception | None = None
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for base in settings.rest_bases:
                try:
                    await asyncio.gather(
                        *(self._load_interval(client, base, i) for i in settings.intervals)
                    )
                    return base
                except Exception as exc:
                    last_error = exc
        raise RuntimeError(f"All history endpoints failed: {last_error}")

    def _history_ready(self) -> bool:
        return all(len(self.candles[i]) >= 200 for i in settings.intervals)

    async def _history_retry_loop(self) -> None:
        while not self._history_ready():
            try:
                base = await self.load_history()
                await self.callback({"type": "history_ready", "source": base})
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self.callback(
                    {"type": "history_error", "error": str(exc)[:220]}
                )
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
            # The web app still starts; history is retried in the background.
            await self.callback({"type": "history_error", "error": str(exc)[:220]})
            self._history_task = asyncio.create_task(
                self._history_retry_loop(), name="market-history-retry"
            )

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
        streams = "/".join(
            f"{settings.symbol.lower()}@kline_{interval}" for interval in settings.intervals
        )
        endpoint_index = 0

        while True:
            base = settings.ws_bases[endpoint_index % len(settings.ws_bases)]
            endpoint_index += 1
            url = f"{base}/stream?streams={streams}"
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=20,
                    close_timeout=5,
                    max_size=2_000_000,
                ) as ws:
                    self.connected = True
                    await self.callback(
                        {"type": "connection", "connected": True, "source": base}
                    )
                    async for raw in ws:
                        msg = json.loads(raw)
                        payload = msg.get("data", msg)
                        k = payload.get("k")
                        if not k:
                            continue
                        candle = {
                            "time": int(k["t"] // 1000),
                            "open": float(k["o"]),
                            "high": float(k["h"]),
                            "low": float(k["l"]),
                            "close": float(k["c"]),
                            "volume": float(k["v"]),
                            "closed": bool(k["x"]),
                        }
                        interval = k["i"]
                        self._upsert(interval, candle)
                        self.last_price = candle["close"]
                        await self.callback(
                            {
                                "type": "market",
                                "interval": interval,
                                "candle": candle,
                                "closed": candle["closed"],
                            }
                        )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.connected = False
                await self.callback(
                    {
                        "type": "connection",
                        "connected": False,
                        "source": base,
                        "error": str(exc)[:220],
                    }
                )
                await asyncio.sleep(3)

    def get(self, interval: str, limit: int = 500) -> list[dict]:
        if interval not in self.candles:
            return []
        return list(self.candles[interval])[-limit:]

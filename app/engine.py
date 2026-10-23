from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .brains import analyze_brains, layer_context
from .db import Database
from .indicators import snapshot
from .market import MarketData
from .master import select_trade
from .trade_manager import TradeManager

Broadcaster = Callable[[dict], Awaitable[None]]


class TradingEngine:
    def __init__(self, db: Database, broadcast: Broadcaster):
        self.db = db
        self.broadcast = broadcast
        self.trade_manager = TradeManager(db)
        self.market = MarketData(self.on_market_event)
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.layers: dict[str, Any] = {}
        self.master: dict[str, Any] = {"action": "BOOTING", "winner": None, "proposals": [], "message": "Loading market history"}
        self.last_analysis_at: str | None = None
        self._analysis_lock = asyncio.Lock()

    async def start(self) -> None:
        await self.market.start()
        await self.analyze(force=True)

    async def stop(self) -> None:
        await self.market.stop()

    def _build_snapshots(self) -> dict[str, dict[str, Any]]:
        # Trading decisions use only confirmed/closed candles on every timeframe.
        # The UI still receives the current live candle separately for charting.
        return {interval: snapshot(self.market.get_closed(interval)) for interval in self.market.candles}

    async def analyze(self, force: bool = False) -> None:
        if self._analysis_lock.locked() and not force:
            return
        async with self._analysis_lock:
            self.snapshots = self._build_snapshots()
            self.layers = layer_context(self.snapshots)
            proposals = analyze_brains(self.snapshots)
            advisory = select_trade(proposals)
            advisory["timeframe_layers"] = self.layers

            active = self.trade_manager.active
            price = self.market.last_price
            if active and price:
                opposite = [
                    p for p in advisory["proposals"]
                    if p.get("direction") in ("LONG", "SHORT")
                    and p["direction"] != active["direction"]
                    and p.get("risk_gate") == "PASSED"
                ]
                strong_opposite = [p for p in opposite if p.get("final_score", 0) >= 84]
                if len(strong_opposite) >= 2:
                    self.trade_manager.early_exit(price, reason="EARLY_EXIT_OPPOSITE_CONSENSUS")
                    proposals = analyze_brains(self.snapshots)
                    advisory = select_trade(proposals)
                    advisory["timeframe_layers"] = self.layers
                    active = None

            if not active and advisory["action"] in ("LONG", "SHORT") and advisory["winner"]:
                self.trade_manager.open_from_proposal(advisory["winner"])

            self.master = advisory
            self.last_analysis_at = datetime.now(timezone.utc).isoformat()
            await self.broadcast({"type": "state", "state": self.state()})

    async def on_market_event(self, event: dict) -> None:
        if event["type"] == "market":
            candle = event["candle"]
            price = float(candle["close"])
            closed_trade = self.trade_manager.on_price(price)
            await self.broadcast({"type": "candle", "interval": event["interval"], "candle": candle, "price": price})

            # Re-evaluate once per confirmed 1m close. Higher timeframes are
            # automatically incorporated when their confirmed candle changes.
            if event["interval"] == "1m" and event["closed"]:
                await self.analyze()
            elif closed_trade:
                await self.analyze(force=True)
            else:
                await self.broadcast({"type": "state", "state": self.state()})
        elif event["type"] in ("connection", "history_ready", "history_error"):
            await self.broadcast({"type": event["type"], **event})

    def state(self) -> dict[str, Any]:
        price = self.market.last_price
        return {
            "symbol": "BTCUSDT", "price": price, "connected": self.market.connected,
            "last_analysis_at": self.last_analysis_at, "snapshots": self.snapshots,
            "timeframe_layers": self.layers, "master": self.master,
            "active_trade": self.trade_manager.state(price), "stats": self.db.stats(),
            "settings": {
                "risk_per_trade_pct": 0.75, "paper_fee_pct_each_side": 0.10,
                "one_trade_only": True, "paper_only": True,
                "analysis_uses_closed_candles": True,
                "intervals": list(self.market.candles.keys()),
            },
        }

    def reset(self) -> dict[str, Any]:
        if self.trade_manager.active:
            raise RuntimeError("Close the active paper trade before reset.")
        self.db.reset()
        self.trade_manager.reset()
        return self.state()

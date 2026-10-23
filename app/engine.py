from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .analysis import enriched_snapshot
from .brains import analyze_brains, layer_context
from .cycle_models import cycle_model_context
from .db import Database
from .derivatives_intelligence import DerivativesIntelligence
from .market import MarketData
from .master import select_trade
from .network_intelligence import NetworkIntelligence
from .regime import classify_market_regime, feature_vector
from .trade_manager import TradeManager

Broadcaster = Callable[[dict], Awaitable[None]]


class TradingEngine:
    def __init__(self, db: Database, broadcast: Broadcaster):
        self.db = db
        self.broadcast = broadcast
        self.trade_manager = TradeManager(db)
        self.market = MarketData(self.on_market_event)
        self.network_source = NetworkIntelligence(ttl_seconds=300)
        self.network: dict[str, Any] = self.network_source.state
        self.derivatives_source = DerivativesIntelligence(ttl_seconds=60)
        self.derivatives: dict[str, Any] = self.derivatives_source.state
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.layers: dict[str, Any] = {}
        self.cycle: dict[str, Any] = {"available": False, "models": {}, "bias": 0.0, "strength": 0.0}
        self.regime: dict[str, Any] = {"regime": "BOOTING", "direction": "NEUTRAL", "volatility": "NORMAL"}
        self.master: dict[str, Any] = {"action": "BOOTING", "winner": None, "proposals": [], "message": "Loading market history"}
        self.learning_cache: dict[str, Any] = self.db.learning_summary()
        self.last_analysis_at: str | None = None
        self._analysis_lock = asyncio.Lock()

    async def start(self) -> None:
        await self.market.start()
        await self.analyze(force=True)

    async def stop(self) -> None:
        await self.market.stop()

    def _build_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            interval: enriched_snapshot(self.market.get_closed(interval, limit=1800 if interval == "1d" else 500))
            for interval in self.market.candles
        }

    def _features(self, advisory: dict[str, Any] | None = None) -> dict[str, Any]:
        return feature_vector(
            self.snapshots, self.layers, advisory or self.master, self.regime,
            self.cycle, self.network, self.derivatives,
        )

    def _public_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            tf: {k: v for k, v in snap.items() if not k.startswith("_")}
            for tf, snap in self.snapshots.items()
        }

    def _record_exit(self, closed_trade: dict[str, Any], advisory: dict[str, Any] | None = None) -> None:
        if not closed_trade:
            return
        features = self._features(advisory)
        features["exit"] = {
            "reason": closed_trade.get("exit_reason"), "price": closed_trade.get("exit_price"),
            "pnl": closed_trade.get("realized_pnl"), "mfe_pct": closed_trade.get("mfe_pct"),
            "mae_pct": closed_trade.get("mae_pct"),
        }
        self.db.record_feature(int(closed_trade["id"]), "EXIT", features)
        self.learning_cache = self.db.learning_summary()

    async def analyze(self, force: bool = False) -> None:
        if self._analysis_lock.locked() and not force:
            return
        async with self._analysis_lock:
            self.snapshots = self._build_snapshots()
            self.cycle = cycle_model_context(self.market.get_closed("1d", limit=1800))
            self.network, self.derivatives = await asyncio.gather(
                self.network_source.refresh_if_due(force=False),
                self.derivatives_source.refresh_if_due(force=False),
            )
            self.layers = layer_context(self.snapshots, self.cycle)
            self.regime = classify_market_regime(self.snapshots, self.layers)

            # Network and derivatives intelligence deliberately have ZERO trading
            # weight. They are logged with outcomes first and can only be promoted
            # after separate out-of-sample incremental-edge validation.
            proposals = analyze_brains(self.snapshots, self.cycle)
            advisory = select_trade(proposals)
            advisory["timeframe_layers"] = self.layers
            advisory["market_regime"] = self.regime
            advisory["cycle_models"] = self.cycle
            advisory["network_intelligence"] = self.network
            advisory["derivatives_intelligence"] = self.derivatives

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
                    closed = self.trade_manager.early_exit(price, reason="EARLY_EXIT_OPPOSITE_CONSENSUS")
                    if closed:
                        self._record_exit(closed, advisory)
                    proposals = analyze_brains(self.snapshots, self.cycle)
                    advisory = select_trade(proposals)
                    advisory["timeframe_layers"] = self.layers
                    advisory["market_regime"] = self.regime
                    advisory["cycle_models"] = self.cycle
                    advisory["network_intelligence"] = self.network
                    advisory["derivatives_intelligence"] = self.derivatives
                    active = None

            if not active and advisory["action"] in ("LONG", "SHORT") and advisory["winner"]:
                context = {"regime": self.regime, "feature_vector": self._features(advisory)}
                self.trade_manager.open_from_proposal(advisory["winner"], context=context)

            self.master = advisory
            self.last_analysis_at = datetime.now(timezone.utc).isoformat()
            await self.broadcast({"type": "state", "state": self.state()})

    async def on_market_event(self, event: dict) -> None:
        if event["type"] == "market":
            candle = event["candle"]
            price = float(candle["close"])
            closed_trade = self.trade_manager.on_price(price)
            await self.broadcast({"type": "candle", "interval": event["interval"], "candle": candle, "price": price})

            if closed_trade:
                self._record_exit(closed_trade)
                await self.analyze(force=True)
            elif event["interval"] == "1m" and event["closed"]:
                await self.analyze()
            else:
                await self.broadcast({"type": "state", "state": self.state()})
        elif event["type"] in ("connection", "history_ready", "history_error"):
            await self.broadcast({"type": event["type"], **event})

    def state(self) -> dict[str, Any]:
        price = self.market.last_price
        total_features = sum(int((s.get("feature_summary") or {}).get("count", 0)) for s in self.snapshots.values())
        return {
            "symbol": "BTCUSDT", "price": price, "connected": self.market.connected,
            "last_analysis_at": self.last_analysis_at, "snapshots": self._public_snapshots(),
            "timeframe_layers": self.layers, "market_regime": self.regime,
            "cycle_models": self.cycle, "network_intelligence": self.network,
            "derivatives_intelligence": self.derivatives, "master": self.master,
            "active_trade": self.trade_manager.state(price), "stats": self.db.stats(),
            "learning": self.learning_cache,
            "feature_engine": {
                "total_background_features": total_features,
                "full_pool_server_side": True,
                "selection_policy": "bounded_family_vote_then_walk_forward_validation",
            },
            "settings": {
                "risk_per_trade_pct": 0.75, "paper_fee_pct_each_side": 0.10,
                "one_trade_only": True, "paper_only": True, "analysis_uses_closed_candles": True,
                "intervals": list(self.market.candles.keys()), "pattern_engine": True, "learning_journal": True,
                "cycle_models": True, "network_intelligence": "SHADOW_ONLY",
                "derivatives_intelligence": "SHADOW_ONLY", "analysis_horizon": "1m→1y",
            },
        }

    def reset(self) -> dict[str, Any]:
        if self.trade_manager.active:
            raise RuntimeError("Close the active paper trade before reset.")
        self.db.reset(); self.trade_manager.reset(); self.learning_cache = self.db.learning_summary()
        return self.state()

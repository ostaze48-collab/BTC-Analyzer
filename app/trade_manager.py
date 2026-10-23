from __future__ import annotations

from typing import Any

from .config import settings
from .db import Database


class TradeManager:
    def __init__(self, db: Database):
        self.db = db
        self.active = self.db.active_trade()

    def _round_trip_pnl(self, trade: dict[str, Any], qty: float, exit_price: float) -> float:
        sign = 1.0 if trade["direction"] == "LONG" else -1.0
        gross = (exit_price - trade["entry"]) * qty * sign
        fees = (trade["entry"] * qty + exit_price * qty) * settings.paper_fee_rate
        return gross - fees

    def open_from_proposal(self, p: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if self.active:
            return None
        capital = float(self.db.account()["capital"])
        risk_budget = capital * settings.risk_per_trade
        risk_per_btc = abs(float(p["entry"]) - float(p["stop_loss"]))
        if risk_per_btc <= 0:
            return None
        qty = min(risk_budget / risk_per_btc, capital / float(p["entry"]))
        if qty <= 0:
            return None

        context = context or {}
        regime = context.get("regime") or {}
        payload = {
            "brain": p["brain"], "direction": p["direction"], "entry": p["entry"],
            "stop_loss": p["stop_loss"], "tp1": p["tp1"], "tp2": p["tp2"], "tp3": p["tp3"],
            "quantity": qty, "confidence": p["confidence"], "safety_score": p["safety_score"],
            "profit_score": p["profit_score"], "final_score": p["final_score"],
            "market_regime": regime.get("regime"),
            "meta": {
                "risk_budget": risk_budget, "actual_risk": qty * risk_per_btc,
                "rr": p["rr"], "ev_pct": p["ev_pct"], "entry_zone": p.get("entry_zone"),
                "consensus": p.get("shared_context"), "macro_direction": p.get("macro_direction"),
                "pattern_bias": p.get("pattern_bias", 0.0), "regime": regime,
            },
        }
        self.active = self.db.create_trade(payload)
        self.active["mfe_pct"] = float(self.active.get("mfe_pct", 0.0) or 0.0)
        self.active["mae_pct"] = float(self.active.get("mae_pct", 0.0) or 0.0)
        features = context.get("feature_vector")
        if features:
            self.db.record_feature(int(self.active["id"]), "ENTRY", features)
        return self.active

    def _update_excursion(self, price: float) -> None:
        if not self.active:
            return
        entry = float(self.active["entry"])
        if entry <= 0:
            return
        if self.active["direction"] == "LONG":
            favorable = max(0.0, (price - entry) / entry * 100)
            adverse = max(0.0, (entry - price) / entry * 100)
        else:
            favorable = max(0.0, (entry - price) / entry * 100)
            adverse = max(0.0, (price - entry) / entry * 100)
        self.active["mfe_pct"] = max(float(self.active.get("mfe_pct", 0.0)), favorable)
        self.active["mae_pct"] = max(float(self.active.get("mae_pct", 0.0)), adverse)

    def _partial(self, fraction_of_original: float, price: float, flag: str) -> None:
        if not self.active:
            return
        original_qty = float(self.active["quantity"])
        remaining = float(self.active["remaining_qty"])
        qty = min(remaining, original_qty * fraction_of_original)
        if qty <= 0:
            return
        pnl = self._round_trip_pnl(self.active, qty, price)
        realized = float(self.active["realized_pnl"]) + pnl
        remaining -= qty
        updates = {
            "remaining_qty": remaining, "realized_pnl": realized, flag: 1,
            "mfe_pct": float(self.active.get("mfe_pct", 0.0)),
            "mae_pct": float(self.active.get("mae_pct", 0.0)),
        }
        if flag == "tp1_hit":
            updates["stop_loss"] = float(self.active["entry"])
        elif flag == "tp2_hit":
            updates["stop_loss"] = float(self.active["tp1"])
        self.active = self.db.update_trade(int(self.active["id"]), **updates)

    def _close_remaining(self, price: float, reason: str) -> dict[str, Any] | None:
        if not self.active:
            return None
        self._update_excursion(price)
        remaining = float(self.active["remaining_qty"])
        realized = float(self.active["realized_pnl"])
        if remaining > 0:
            realized += self._round_trip_pnl(self.active, remaining, price)
        trade_id = int(self.active["id"])
        closed = self.db.close_trade(
            trade_id, price, reason, realized,
            mfe_pct=float(self.active.get("mfe_pct", 0.0)),
            mae_pct=float(self.active.get("mae_pct", 0.0)),
        )
        self.db.update_capital(realized)
        self.active = None
        return closed

    def on_price(self, price: float) -> dict[str, Any] | None:
        if not self.active:
            return None
        self._update_excursion(price)
        t = self.active
        if t["direction"] == "LONG":
            if price <= float(t["stop_loss"]): return self._close_remaining(price, "STOP_LOSS")
            if not int(t["tp1_hit"]) and price >= float(t["tp1"]): self._partial(0.30, float(t["tp1"]), "tp1_hit"); t = self.active
            if t and not int(t["tp2_hit"]) and price >= float(t["tp2"]): self._partial(0.40, float(t["tp2"]), "tp2_hit"); t = self.active
            if t and price >= float(t["tp3"]): return self._close_remaining(float(t["tp3"]), "TP3")
        else:
            if price >= float(t["stop_loss"]): return self._close_remaining(price, "STOP_LOSS")
            if not int(t["tp1_hit"]) and price <= float(t["tp1"]): self._partial(0.30, float(t["tp1"]), "tp1_hit"); t = self.active
            if t and not int(t["tp2_hit"]) and price <= float(t["tp2"]): self._partial(0.40, float(t["tp2"]), "tp2_hit"); t = self.active
            if t and price <= float(t["tp3"]): return self._close_remaining(float(t["tp3"]), "TP3")
        return None

    def early_exit(self, price: float, reason: str = "EARLY_EXIT") -> dict[str, Any] | None:
        return self._close_remaining(price, reason)

    def state(self, current_price: float | None = None) -> dict[str, Any] | None:
        if not self.active:
            return None
        t = dict(self.active)
        if current_price:
            remaining = float(t["remaining_qty"])
            sign = 1 if t["direction"] == "LONG" else -1
            unrealized = (current_price - float(t["entry"])) * remaining * sign
            t["unrealized_pnl"] = round(unrealized, 4)
            t["total_live_pnl"] = round(float(t["realized_pnl"]) + unrealized, 4)
        t["mfe_pct"] = round(float(t.get("mfe_pct", 0.0)), 4)
        t["mae_pct"] = round(float(t.get("mae_pct", 0.0)), 4)
        return t

    def reset(self) -> None:
        self.active = None

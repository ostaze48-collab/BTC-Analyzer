from __future__ import annotations

from typing import Any

from .config import settings
from .db import Database
from .risk_engine import build_risk_plan, hard_floor_breached


class TradeManager:
    def __init__(self, db: Database):
        self.db = db
        self.active = self.db.active_trade()
        self.last_rejection: dict[str, Any] | None = None

    def _round_trip_pnl(self, trade: dict[str, Any], qty: float, exit_price: float) -> float:
        sign = 1.0 if trade["direction"] == "LONG" else -1.0
        gross = (exit_price - trade["entry"]) * qty * sign
        fees = (trade["entry"] * qty + exit_price * qty) * settings.paper_fee_rate
        return gross - fees

    def _live_trade_pnl(self, price: float) -> float:
        if not self.active:
            return 0.0
        remaining = float(self.active.get("remaining_qty", 0.0) or 0.0)
        realized = float(self.active.get("realized_pnl", 0.0) or 0.0)
        return realized + (self._round_trip_pnl(self.active, remaining, price) if remaining > 0 else 0.0)

    def open_from_proposal(self, p: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if self.active:
            self.last_rejection = {"reason": "ONE_TRADE_ONLY_LOCK"}
            return None

        context = context or {}
        regime = context.get("regime") or {}
        account = self.db.account()
        plan = build_risk_plan(p, account, regime)
        if not plan.get("allowed"):
            self.last_rejection = plan
            return None

        payload = {
            "brain": p["brain"],
            "direction": p["direction"],
            "entry": p["entry"],
            "stop_loss": p["stop_loss"],
            "tp1": plan["tp1"],
            "tp2": plan["tp2"],
            "tp3": plan["tp3"],
            "quantity": plan["quantity"],
            "confidence": p["confidence"],
            "safety_score": p["safety_score"],
            "profit_score": p["profit_score"],
            "final_score": p["final_score"],
            "market_regime": regime.get("regime"),
            "leverage": plan["leverage"],
            "notional": plan["notional"],
            "margin_used": plan["margin_used"],
            "risk_budget": plan["risk_budget"],
            "target_r": plan["target_r"],
            "meta": {
                "adaptive_risk_plan": plan,
                "rr": p.get("rr"),
                "ev_pct": p.get("ev_pct"),
                "entry_zone": p.get("entry_zone"),
                "consensus": p.get("shared_context"),
                "macro_direction": p.get("macro_direction"),
                "pattern_bias": p.get("pattern_bias", 0.0),
                "regime": regime,
            },
        }
        self.active = self.db.create_trade(payload)
        self.active["mfe_pct"] = float(self.active.get("mfe_pct", 0.0) or 0.0)
        self.active["mae_pct"] = float(self.active.get("mae_pct", 0.0) or 0.0)
        features = context.get("feature_vector")
        if features:
            features = dict(features)
            features["adaptive_risk_plan"] = plan
            self.db.record_feature(int(self.active["id"]), "ENTRY", features)
        self.last_rejection = None
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

        # Portfolio-level emergency brake. This is exact in the paper model at the
        # observed price, but real markets can gap/slip beyond a planned limit.
        account = self.db.account()
        if hard_floor_breached(account, self._live_trade_pnl(price)):
            return self._close_remaining(price, "MAX_25PCT_DRAWDOWN_KILL_SWITCH")

        t = self.active
        if t["direction"] == "LONG":
            if price <= float(t["stop_loss"]):
                return self._close_remaining(price, "STOP_LOSS")
            if not int(t["tp1_hit"]) and price >= float(t["tp1"]):
                self._partial(0.30, float(t["tp1"]), "tp1_hit"); t = self.active
            if t and not int(t["tp2_hit"]) and price >= float(t["tp2"]):
                self._partial(0.40, float(t["tp2"]), "tp2_hit"); t = self.active
            if t and price >= float(t["tp3"]):
                return self._close_remaining(float(t["tp3"]), "ADAPTIVE_TARGET_R")
        else:
            if price >= float(t["stop_loss"]):
                return self._close_remaining(price, "STOP_LOSS")
            if not int(t["tp1_hit"]) and price <= float(t["tp1"]):
                self._partial(0.30, float(t["tp1"]), "tp1_hit"); t = self.active
            if t and not int(t["tp2_hit"]) and price <= float(t["tp2"]):
                self._partial(0.40, float(t["tp2"]), "tp2_hit"); t = self.active
            if t and price <= float(t["tp3"]):
                return self._close_remaining(float(t["tp3"]), "ADAPTIVE_TARGET_R")
        return None

    def early_exit(self, price: float, reason: str = "EARLY_EXIT") -> dict[str, Any] | None:
        return self._close_remaining(price, reason)

    def state(self, current_price: float | None = None) -> dict[str, Any] | None:
        if not self.active:
            return None
        t = dict(self.active)
        if current_price:
            total_live = self._live_trade_pnl(current_price)
            remaining = float(t["remaining_qty"])
            sign = 1 if t["direction"] == "LONG" else -1
            unrealized_gross = (current_price - float(t["entry"])) * remaining * sign
            t["unrealized_pnl"] = round(unrealized_gross, 4)
            t["total_live_pnl"] = round(total_live, 4)
            account = self.db.account()
            t["live_equity"] = round(float(account["capital"]) + total_live, 4)
            t["hard_floor"] = round(float(account["starting_capital"]) * (1.0 - settings.max_total_drawdown), 2)
        t["mfe_pct"] = round(float(t.get("mfe_pct", 0.0)), 4)
        t["mae_pct"] = round(float(t.get("mae_pct", 0.0)), 4)
        return t

    def reset(self) -> None:
        self.active = None
        self.last_rejection = None

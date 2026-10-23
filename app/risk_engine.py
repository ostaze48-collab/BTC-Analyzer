from __future__ import annotations

import math
from typing import Any

from .config import settings


def drawdown_from_start(account: dict[str, Any]) -> float:
    start = float(account.get("starting_capital", 0.0) or 0.0)
    capital = float(account.get("capital", 0.0) or 0.0)
    if start <= 0:
        return 0.0
    return max(0.0, (start - capital) / start)


def _base_risk_fraction(p: dict[str, Any]) -> float:
    """Planned stop-loss risk, not position notional."""
    score = float(p.get("final_score", 0.0) or 0.0)
    safety = float(p.get("safety_score", 0.0) or 0.0)
    ev = float(p.get("ev_pct", 0.0) or 0.0)

    if score >= 92 and safety >= 88 and ev > 0.35:
        risk = 0.014
    elif score >= 88:
        risk = 0.0115
    elif score >= 82:
        risk = 0.009
    elif score >= 75:
        risk = 0.0065
    else:
        risk = 0.004

    if p.get("shared_context") == "CONFLICT":
        risk *= 0.65
    volatility = float(p.get("volatility_pct", 0.0) or 0.0)
    if volatility >= 2.0:
        risk *= 0.70
    elif volatility >= 1.2:
        risk *= 0.85
    return max(0.0025, min(settings.max_risk_per_trade, risk))


def _drawdown_multiplier(dd: float) -> float:
    if dd >= settings.soft_pause_drawdown:
        return 0.0
    if dd >= 0.20:
        return 0.25
    if dd >= 0.15:
        return 0.50
    if dd >= 0.10:
        return 0.75
    return 1.0


def _target_r(p: dict[str, Any], regime: dict[str, Any] | None = None) -> float:
    """Adaptive terminal profit target between 1R and 5R."""
    score = float(p.get("final_score", 0.0) or 0.0)
    if score >= 92:
        target = 5.0
    elif score >= 88:
        target = 4.0
    elif score >= 82:
        target = 3.0
    elif score >= 75:
        target = 2.0
    else:
        target = 1.0

    brain = str(p.get("brain", ""))
    if brain == "SCALP":
        target = min(target, 2.5)
    elif brain == "INTRADAY":
        target = min(target, 4.0)

    r = (regime or {}).get("regime")
    if r == "RANGE":
        target = min(target, 2.0)
    elif r in ("TRANSITION", None):
        target = min(target, 3.0)

    macro = p.get("macro_direction")
    if macro in ("BULLISH", "BEARISH") and p.get("direction") not in (None, macro.replace("BULLISH", "LONG").replace("BEARISH", "SHORT")):
        target = min(target, 2.0)

    return max(1.0, min(5.0, target))


def _adaptive_targets(entry: float, stop: float, direction: str, target_r: float) -> tuple[float, float, float]:
    risk = abs(entry - stop)
    sign = 1.0 if direction == "LONG" else -1.0
    r1 = min(1.0, target_r)
    r2 = min(target_r, max(r1, target_r * 0.60))
    r3 = target_r
    return (
        entry + sign * risk * r1,
        entry + sign * risk * r2,
        entry + sign * risk * r3,
    )


def build_risk_plan(
    p: dict[str, Any],
    account: dict[str, Any],
    regime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a paper-trading plan. Leverage only changes exposure/margin, not the stop-risk budget."""
    start = float(account.get("starting_capital", 0.0) or 0.0)
    capital = float(account.get("capital", 0.0) or 0.0)
    entry = float(p.get("entry", 0.0) or 0.0)
    stop = float(p.get("stop_loss", 0.0) or 0.0)
    dd = drawdown_from_start(account)
    hard_floor = start * (1.0 - settings.max_total_drawdown)
    remaining_loss_capacity = max(0.0, capital - hard_floor)

    if start <= 0 or capital <= 0 or entry <= 0 or stop <= 0:
        return {"allowed": False, "reason": "Invalid account or price inputs"}
    if dd >= settings.soft_pause_drawdown:
        return {
            "allowed": False,
            "reason": "CAPITAL_PRESERVATION_PAUSE",
            "drawdown_pct": round(dd * 100, 3),
            "hard_floor": round(hard_floor, 2),
        }

    risk_per_btc = abs(entry - stop)
    if risk_per_btc <= 0:
        return {"allowed": False, "reason": "Invalid stop distance"}

    risk_fraction = _base_risk_fraction(p) * _drawdown_multiplier(dd)
    desired_risk = capital * risk_fraction
    # Reserve a small buffer before the hard 25% floor.
    floor_buffer = max(start * 0.0025, 0.01)
    max_allowed_risk = max(0.0, remaining_loss_capacity - floor_buffer)
    risk_budget = min(desired_risk, max_allowed_risk)
    if risk_budget <= 0:
        return {"allowed": False, "reason": "NO_RISK_CAPACITY_BEFORE_HARD_FLOOR"}

    stop_fraction = risk_per_btc / entry
    desired_notional = risk_budget / stop_fraction
    max_notional = capital * settings.max_paper_leverage
    notional = min(desired_notional, max_notional)
    quantity = notional / entry
    actual_risk = quantity * risk_per_btc

    # Minimal whole-number leverage needed for the selected notional.
    leverage = int(max(1, min(settings.max_paper_leverage, math.ceil(notional / capital))))
    margin_used = notional / leverage
    margin_pct = margin_used / capital * 100.0

    target_r = _target_r(p, regime)
    tp1, tp2, tp3 = _adaptive_targets(entry, stop, str(p.get("direction")), target_r)

    return {
        "allowed": True,
        "direction": p.get("direction"),
        "risk_fraction": round(actual_risk / capital, 6),
        "risk_budget": round(actual_risk, 6),
        "requested_risk_budget": round(desired_risk, 6),
        "remaining_loss_capacity": round(remaining_loss_capacity, 6),
        "drawdown_pct": round(dd * 100, 4),
        "hard_drawdown_limit_pct": round(settings.max_total_drawdown * 100, 2),
        "hard_floor": round(hard_floor, 2),
        "soft_pause_pct": round(settings.soft_pause_drawdown * 100, 2),
        "leverage": leverage,
        "max_leverage": settings.max_paper_leverage,
        "quantity": quantity,
        "notional": round(notional, 4),
        "margin_used": round(margin_used, 4),
        "margin_pct": round(margin_pct, 3),
        "stop_distance_pct": round(stop_fraction * 100, 4),
        "target_r": target_r,
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        "mode": "PAPER_ADAPTIVE_RISK",
    }


def live_equity(capital: float, trade_live_pnl: float) -> float:
    return capital + trade_live_pnl


def hard_floor_breached(account: dict[str, Any], trade_live_pnl: float) -> bool:
    start = float(account.get("starting_capital", 0.0) or 0.0)
    capital = float(account.get("capital", 0.0) or 0.0)
    floor = start * (1.0 - settings.max_total_drawdown)
    return live_equity(capital, trade_live_pnl) <= floor

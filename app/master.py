from __future__ import annotations

from typing import Any

from .config import settings


def _scores(p: dict[str, Any]) -> dict[str, float]:
    confidence = float(p.get("confidence", 0))
    consensus = float(p.get("consensus_score", 0))
    volatility = float(p.get("volatility_pct", 0))
    rr = float(p.get("rr", 0))
    ev = float(p.get("ev_pct", -99))
    volume_ratio = float(p.get("volume_ratio", 1))
    macro_strength = float(p.get("macro_strength", 0))

    volatility_penalty = min(15.0, max(0.0, (volatility - 1.2) * 7))
    stop_quality = max(0.0, 10.0 - max(0.0, float(p.get("risk_pct", 0)) - 1.0) * 4)
    volume_bonus = min(8.0, max(-3.0, (volume_ratio - 1.0) * 6))
    consensus_bonus = consensus * 12.0
    macro_adjustment = (5.0 * macro_strength) if p.get("macro_aligned") else (-(14.0 * macro_strength) if p.get("macro_conflict") else 0.0)

    sweep = ((p.get("liquidity") or {}).get("sweep") or {})
    liquidity_adjustment = 0.0
    if sweep.get("direction"):
        aligned = (p.get("direction") == "LONG" and sweep.get("direction") == "BULLISH") or (p.get("direction") == "SHORT" and sweep.get("direction") == "BEARISH")
        liquidity_adjustment = 4.0 if aligned else -5.0

    safety = confidence * 0.72 + stop_quality + volume_bonus + consensus_bonus + macro_adjustment + liquidity_adjustment - volatility_penalty
    safety = max(0.0, min(100.0, safety))
    profit = rr * 18.0 + max(0.0, ev) * 22.0
    profit = max(0.0, min(100.0, profit))
    final = 0.58 * safety + 0.32 * profit + 0.10 * max(0.0, confidence)
    return {"safety_score": round(safety, 2), "profit_score": round(profit, 2), "final_score": round(min(100.0, final), 2)}


def risk_gate(p: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    if p.get("direction") not in ("LONG", "SHORT"):
        reasons.append("No directional setup")
    if float(p.get("confidence", 0)) < settings.min_confidence:
        reasons.append("Confidence below minimum")
    if float(p.get("rr", 0)) < settings.min_rr:
        reasons.append("R:R below minimum")
    if float(p.get("ev_pct", -99)) <= 0:
        reasons.append("Expected value is not positive")
    if float(p.get("risk_pct", 999)) > settings.max_stop_pct:
        reasons.append("Stop distance exceeds maximum")
    if float(p.get("safety_score", 0)) < settings.min_safety_score:
        reasons.append("Safety score below minimum")
    if p.get("macro_conflict") and float(p.get("macro_strength", 0)) >= 0.65 and float(p.get("safety_score", 0)) < 78:
        reasons.append("Strong macro conflict")
    return (len(reasons) == 0, reasons)


def select_trade(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = []
    for proposal in proposals:
        p = dict(proposal)
        if p.get("direction") in ("LONG", "SHORT"):
            p.update(_scores(p))
        else:
            p.update({"safety_score": 0.0, "profit_score": 0.0, "final_score": 0.0})
        passed, reasons = risk_gate(p)
        p["risk_gate"] = "PASSED" if passed else "REJECTED"
        p["risk_gate_reasons"] = reasons
        enriched.append(p)

    passed = [p for p in enriched if p["risk_gate"] == "PASSED"]
    if passed:
        winner = max(passed, key=lambda p: (p["final_score"], p["ev_pct"], p["safety_score"]))
        action = winner["direction"]
        message = f"{winner['brain']} selected as best risk-adjusted opportunity"
    else:
        directional = [p for p in enriched if p.get("direction") in ("LONG", "SHORT")]
        if directional:
            winner = max(directional, key=lambda p: p["final_score"])
            action = "WAIT"
            message = "A setup exists, but it did not pass the risk gate"
        else:
            winner = None
            action = "NO_TRADE"
            message = "No directional edge"
    return {"action": action, "winner": winner, "proposals": enriched, "message": message}

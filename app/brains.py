from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import settings
from .indicators import vote


@dataclass(frozen=True)
class BrainProfile:
    name: str
    weights: dict[str, float]
    anchor: str
    tp_r: tuple[float, float, float]
    macro_sensitivity: float


PROFILES = (
    BrainProfile("SCALP", {"1m": 0.30, "3m": 0.35, "5m": 0.25, "15m": 0.10}, "5m", (1.2, 1.8, 2.5), 0.70),
    BrainProfile("INTRADAY", {"15m": 0.25, "30m": 0.30, "1h": 0.30, "2h": 0.15}, "30m", (1.4, 2.2, 3.0), 0.90),
    BrainProfile("SWING", {"4h": 0.20, "6h": 0.15, "8h": 0.10, "12h": 0.20, "1d": 0.25, "3d": 0.07, "1w": 0.03}, "4h", (1.5, 2.5, 4.0), 1.00),
)


def _weighted_vote(snapshots: dict[str, dict[str, Any]], weights: dict[str, float]) -> tuple[float, dict[str, float]]:
    total = 0.0
    used = 0.0
    details: dict[str, float] = {}
    for interval, weight in weights.items():
        value = vote(snapshots.get(interval, {}))
        details[interval] = round(value, 3)
        if snapshots.get(interval):
            total += value * weight
            used += weight
    return (total / used if used else 0.0), details


def macro_context(snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    weights = {"1d": 0.45, "3d": 0.30, "1w": 0.25}
    bias, votes = _weighted_vote(snapshots, weights)
    if bias > 0.18:
        direction = "BULLISH"
    elif bias < -0.18:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    return {"direction": direction, "bias": round(bias, 4), "strength": round(abs(bias), 4), "votes": votes}


def layer_context(snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    layers = {
        "MICRO": {"1m": 0.35, "3m": 0.35, "5m": 0.30},
        "INTRADAY": {"15m": 0.25, "30m": 0.25, "1h": 0.30, "2h": 0.20},
        "SWING": {"4h": 0.18, "6h": 0.14, "8h": 0.10, "12h": 0.18, "1d": 0.25, "3d": 0.10, "1w": 0.05},
    }
    out: dict[str, Any] = {}
    for name, weights in layers.items():
        bias, votes = _weighted_vote(snapshots, weights)
        direction = "BULLISH" if bias > 0.14 else ("BEARISH" if bias < -0.14 else "NEUTRAL")
        out[name] = {"direction": direction, "bias": round(bias, 4), "votes": votes}
    out["MACRO"] = macro_context(snapshots)
    return out


def _proposal(profile: BrainProfile, snapshots: dict[str, dict[str, Any]], macro: dict[str, Any]) -> dict[str, Any]:
    bias, details = _weighted_vote(snapshots, profile.weights)
    anchor = snapshots.get(profile.anchor, {})
    if not anchor:
        return {"brain": profile.name, "direction": "WAIT", "confidence": 50.0, "bias": 0.0, "reason": "Not enough market history"}

    if bias > 0.13:
        direction = "LONG"
    elif bias < -0.13:
        direction = "SHORT"
    else:
        direction = "WAIT"

    confidence = min(92.0, 50.0 + abs(bias) * 44.0)
    macro_dir = macro["direction"]
    macro_strength = float(macro["strength"])
    macro_conflict = direction in ("LONG", "SHORT") and macro_dir in ("BULLISH", "BEARISH") and ((direction == "LONG") != (macro_dir == "BULLISH"))
    macro_aligned = direction in ("LONG", "SHORT") and macro_dir in ("BULLISH", "BEARISH") and not macro_conflict

    if macro_aligned:
        confidence += min(6.0, 6.0 * macro_strength * profile.macro_sensitivity)
    elif macro_conflict:
        confidence -= min(18.0, (8.0 + 10.0 * macro_strength) * profile.macro_sensitivity)
    confidence = max(45.0, min(95.0, confidence))

    common = {
        "brain": profile.name,
        "direction": direction,
        "confidence": round(confidence, 2),
        "bias": round(bias, 4),
        "anchor": profile.anchor,
        "votes": details,
        "macro_direction": macro_dir,
        "macro_bias": macro["bias"],
        "macro_strength": macro["strength"],
        "macro_conflict": macro_conflict,
        "macro_aligned": macro_aligned,
        "structure_event": anchor.get("structure_event"),
        "swing_high": anchor.get("swing_high"),
        "swing_low": anchor.get("swing_low"),
        "fvg_zones": anchor.get("fvg_zones", []),
        "order_block": anchor.get("order_block"),
        "liquidity": anchor.get("liquidity", {}),
        "trend_channel": anchor.get("trend_channel"),
    }
    if direction == "WAIT":
        common["reason"] = "No directional edge above threshold"
        return common

    live = snapshots.get("1m", {})
    price = float(live.get("close", anchor["close"]))
    a = max(float(anchor["atr14"]), price * 0.001)
    support = float(anchor["support"])
    resistance = float(anchor["resistance"])

    if direction == "LONG":
        entry_low, entry_high, entry = price - 0.18 * a, price + 0.06 * a, price
        raw_stop = min(entry - 1.20 * a, support - 0.10 * a)
        stop = max(raw_stop, entry - 2.50 * a)
        risk = max(entry - stop, 0.25 * a)
        tp1, tp2, tp3 = entry + profile.tp_r[0] * risk, entry + profile.tp_r[1] * risk, entry + profile.tp_r[2] * risk
    else:
        entry_low, entry_high, entry = price - 0.06 * a, price + 0.18 * a, price
        raw_stop = max(entry + 1.20 * a, resistance + 0.10 * a)
        stop = min(raw_stop, entry + 2.50 * a)
        risk = max(stop - entry, 0.25 * a)
        tp1, tp2, tp3 = entry - profile.tp_r[0] * risk, entry - profile.tp_r[1] * risk, entry - profile.tp_r[2] * risk

    risk_pct = risk / entry * 100
    rr = abs(tp2 - entry) / risk if risk else 0.0
    probability = min(0.90, max(0.52, confidence / 100))
    reward_pct = abs(tp2 - entry) / entry * 100
    fees_pct = settings.paper_fee_rate * 2 * 100
    ev_pct = probability * reward_pct - (1 - probability) * risk_pct - fees_pct

    common.update({
        "win_probability": round(probability * 100, 2),
        "entry_zone": [round(entry_low, 2), round(entry_high, 2)], "entry": round(entry, 2),
        "stop_loss": round(stop, 2), "tp1": round(tp1, 2), "tp2": round(tp2, 2), "tp3": round(tp3, 2),
        "risk_pct": round(risk_pct, 4), "rr": round(rr, 3), "ev_pct": round(ev_pct, 4),
        "volatility_pct": round(float(anchor["volatility_pct"]), 4), "volume_ratio": round(float(anchor["volume_ratio"]), 3),
        "structure": anchor["structure"], "trend": anchor["trend"],
        "support": round(support, 2), "resistance": round(resistance, 2),
    })
    return common


def analyze_brains(snapshots: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    macro = macro_context(snapshots)
    proposals = [_proposal(profile, snapshots, macro) for profile in PROFILES]
    directional = [p for p in proposals if p.get("direction") in ("LONG", "SHORT")]

    for p in proposals:
        if p.get("direction") not in ("LONG", "SHORT"):
            p["consensus_score"] = 0.0
            p["shared_context"] = "NEUTRAL"
            continue
        same = sum(1 for x in directional if x["direction"] == p["direction"]) - 1
        opposite = sum(1 for x in directional if x["direction"] != p["direction"])
        consensus = max(-1.0, min(1.0, (same - opposite) / 2))
        adjusted = float(p["confidence"]) + same * 4.0 - opposite * 7.0
        p["confidence"] = round(max(45.0, min(95.0, adjusted)), 2)
        p["win_probability"] = round(max(50.0, min(90.0, adjusted)), 2)
        p["consensus_score"] = round(consensus, 2)
        if same >= 2: p["shared_context"] = "FULL_CONSENSUS"
        elif same == 1 and opposite == 0: p["shared_context"] = "PARTIAL_CONSENSUS"
        elif opposite >= 1: p["shared_context"] = "CONFLICT"
        else: p["shared_context"] = "SOLO"

        prob = p["win_probability"] / 100
        reward_pct = abs(p["tp2"] - p["entry"]) / p["entry"] * 100
        fees_pct = settings.paper_fee_rate * 2 * 100
        p["ev_pct"] = round(prob * reward_pct - (1 - prob) * p["risk_pct"] - fees_pct, 4)
    return proposals

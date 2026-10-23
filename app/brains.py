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


PROFILES = (
    BrainProfile("SCALP", {"1m": 0.50, "5m": 0.35, "15m": 0.15}, "5m", (1.2, 1.8, 2.5)),
    BrainProfile("INTRADAY", {"5m": 0.20, "15m": 0.50, "1h": 0.30}, "15m", (1.4, 2.2, 3.0)),
    BrainProfile("SWING", {"1h": 0.35, "4h": 0.65}, "4h", (1.5, 2.5, 4.0)),
)


def _proposal(profile: BrainProfile, snapshots: dict[str, dict[str, Any]]) -> dict[str, Any]:
    weighted = 0.0
    used = 0.0
    details = {}
    for interval, w in profile.weights.items():
        v = vote(snapshots.get(interval, {}))
        details[interval] = round(v, 3)
        weighted += v * w
        used += w

    bias = weighted / used if used else 0.0
    anchor = snapshots.get(profile.anchor, {})
    if not anchor:
        return {
            "brain": profile.name,
            "direction": "WAIT",
            "confidence": 50.0,
            "bias": 0.0,
            "reason": "Not enough market history",
        }

    if bias > 0.13:
        direction = "LONG"
    elif bias < -0.13:
        direction = "SHORT"
    else:
        direction = "WAIT"

    confidence = min(92.0, 50.0 + abs(bias) * 44.0)
    live = snapshots.get("1m", {})
    price = float(live.get("close", anchor["close"]))
    a = max(float(anchor["atr14"]), price * 0.001)
    support = float(anchor["support"])
    resistance = float(anchor["resistance"])

    if direction == "WAIT":
        return {
            "brain": profile.name,
            "direction": "WAIT",
            "confidence": round(confidence, 2),
            "bias": round(bias, 4),
            "anchor": profile.anchor,
            "votes": details,
            "reason": "No directional edge above threshold",
        }

    if direction == "LONG":
        entry_low = price - 0.18 * a
        entry_high = price + 0.06 * a
        entry = price
        raw_stop = min(entry - 1.20 * a, support - 0.10 * a)
        stop = max(raw_stop, entry - 2.50 * a)
        risk = max(entry - stop, 0.25 * a)
        tp1 = entry + profile.tp_r[0] * risk
        tp2 = entry + profile.tp_r[1] * risk
        tp3 = entry + profile.tp_r[2] * risk
    else:
        entry_low = price - 0.06 * a
        entry_high = price + 0.18 * a
        entry = price
        raw_stop = max(entry + 1.20 * a, resistance + 0.10 * a)
        stop = min(raw_stop, entry + 2.50 * a)
        risk = max(stop - entry, 0.25 * a)
        tp1 = entry - profile.tp_r[0] * risk
        tp2 = entry - profile.tp_r[1] * risk
        tp3 = entry - profile.tp_r[2] * risk

    risk_pct = risk / entry * 100
    rr = abs(tp2 - entry) / risk if risk else 0.0
    probability = min(0.90, max(0.52, confidence / 100))
    reward_pct = abs(tp2 - entry) / entry * 100
    round_trip_cost_pct = settings.paper_fee_rate * 2 * 100
    ev_pct = probability * reward_pct - (1 - probability) * risk_pct - round_trip_cost_pct

    return {
        "brain": profile.name,
        "direction": direction,
        "anchor": profile.anchor,
        "bias": round(bias, 4),
        "confidence": round(confidence, 2),
        "win_probability": round(probability * 100, 2),
        "entry_zone": [round(entry_low, 2), round(entry_high, 2)],
        "entry": round(entry, 2),
        "stop_loss": round(stop, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        "risk_pct": round(risk_pct, 4),
        "rr": round(rr, 3),
        "ev_pct": round(ev_pct, 4),
        "volatility_pct": round(float(anchor["volatility_pct"]), 4),
        "volume_ratio": round(float(anchor["volume_ratio"]), 3),
        "structure": anchor["structure"],
        "trend": anchor["trend"],
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "votes": details,
    }


def analyze_brains(snapshots: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    proposals = [_proposal(profile, snapshots) for profile in PROFILES]

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
        p["confidence"] = round(max(50.0, min(95.0, adjusted)), 2)
        p["win_probability"] = round(max(52.0, min(90.0, adjusted)), 2)
        p["consensus_score"] = round(consensus, 2)

        if same >= 2:
            p["shared_context"] = "FULL_CONSENSUS"
        elif same == 1 and opposite == 0:
            p["shared_context"] = "PARTIAL_CONSENSUS"
        elif opposite >= 1:
            p["shared_context"] = "CONFLICT"
        else:
            p["shared_context"] = "SOLO"

        prob = p["win_probability"] / 100
        reward_pct = abs(p["tp2"] - p["entry"]) / p["entry"] * 100
        risk_pct = p["risk_pct"]
        fees = settings.paper_fee_rate * 2 * 100
        p["ev_pct"] = round(prob * reward_pct - (1 - prob) * risk_pct - fees, 4)

    return proposals

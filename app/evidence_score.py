from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _analog_component(a: dict[str, Any], deep: bool = False) -> dict[str, Any]:
    if not a or a.get("status") != "READY":
        return {"available": False, "score": None, "reason": a.get("status", "NO_DATA") if a else "NO_DATA"}
    hit2 = _num(a.get("hit_2r_pct")); hit3 = _num(a.get("hit_3r_pct"))
    stop = _num(a.get("stop_pct" if deep else "stop_before_1r_pct"))
    similarity = _num(a.get("avg_similarity_pct")); matches = _num(a.get("matches"))
    sample_factor = min(1.0, matches / (24.0 if deep else 18.0))
    raw = hit2 * 0.34 + hit3 * 0.26 + (100.0 - stop) * 0.22 + similarity * 0.18
    score = 50.0 + (raw - 50.0) * sample_factor
    return {
        "available": True, "score": round(max(0.0, min(100.0, score)), 2),
        "matches": int(matches), "hit_2r_pct": hit2, "hit_3r_pct": hit3,
        "stop_pct": stop, "similarity_pct": similarity,
    }


def _brain_regime_component(learning: dict[str, Any], proposal: dict[str, Any], regime: dict[str, Any]) -> dict[str, Any]:
    brain = proposal.get("brain"); regime_name = regime.get("regime")
    rows = learning.get("brain_regime") or []
    row = next((x for x in rows if x.get("brain") == brain and x.get("regime") == regime_name), None)
    if not row:
        return {"available": False, "score": None, "reason": "NO_MATCHING_BRAIN_REGIME_SAMPLE"}
    n = int(row.get("trades", 0) or 0)
    if n < 5:
        return {"available": False, "score": None, "reason": "SMALL_SAMPLE", "trades": n}
    win = _num(row.get("win_rate")); pf = min(3.0, _num(row.get("profit_factor")))
    sample_factor = min(1.0, n / 30.0)
    raw = win * 0.55 + min(100.0, pf / 2.0 * 100.0) * 0.45
    score = 50.0 + (raw - 50.0) * sample_factor
    return {
        "available": True, "score": round(max(0.0, min(100.0, score)), 2),
        "trades": n, "win_rate": win, "profit_factor": _num(row.get("profit_factor")),
        "avg_mfe_pct": _num(row.get("avg_mfe_pct")), "avg_mae_pct": _num(row.get("avg_mae_pct")),
    }


def build_candidate_evidence(
    proposal: dict[str, Any] | None,
    regime: dict[str, Any],
    historical: dict[str, Any],
    deep_history: dict[str, Any],
    learning: dict[str, Any],
    historical_validation: dict[str, Any] | None = None,
    incremental: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposal = proposal or {}
    if proposal.get("direction") not in ("LONG", "SHORT"):
        return {"status": "NO_CANDIDATE", "score": None, "master_weight": 0.0, "components": {}}

    local = _analog_component(historical, deep=False)
    deep = _analog_component(deep_history, deep=True)
    brain = _brain_regime_component(learning, proposal, regime)
    weighted: list[tuple[float, float]] = []
    if local["available"]: weighted.append((float(local["score"]), 0.40))
    if deep["available"]: weighted.append((float(deep["score"]), 0.35))
    if brain["available"]: weighted.append((float(brain["score"]), 0.25))

    if not weighted:
        return {
            "status": "COLLECTING", "score": None, "master_weight": 0.0,
            "brain": proposal.get("brain"), "direction": proposal.get("direction"),
            "components": {"recent_multitimeframe": local, "deep_anchor": deep, "brain_regime": brain},
        }

    score = sum(s * w for s, w in weighted) / sum(w for _, w in weighted)
    hv = historical_validation or {}
    reliability = "UNPROVEN"
    if hv.get("status") == "USEFUL_OOS_EVIDENCE": reliability = "OOS_SUPPORTED"
    elif hv.get("status") == "MIXED_EVIDENCE": reliability = "MIXED"

    inc = incremental or {}
    research = {
        "historical_validation": hv.get("status", "NOT_RUN"),
        "incremental_edge_status": inc.get("status", "NOT_RUN"),
        "incremental_eligible": int(inc.get("eligible_count", 0) or 0),
    }
    grade = "A" if score >= 78 else ("B" if score >= 66 else ("C" if score >= 54 else "D"))
    return {
        "status": "READY", "mode": "SHADOW_EVIDENCE_SCORE", "score": round(score, 2), "grade": grade,
        "reliability": reliability, "master_weight": 0.0,
        "brain": proposal.get("brain"), "direction": proposal.get("direction"), "regime": regime.get("regime"),
        "components": {"recent_multitimeframe": local, "deep_anchor": deep, "brain_regime": brain},
        "research_validation": research,
        "warning": "Evidence score is research context only. It does not change MASTER or guarantee profit until OOS and shadow gates pass.",
    }

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


MIN_SAMPLES = 150
MIN_BRAIN_TRADES = 20
MIN_REGIME_TRADES = 20
MIN_MATURE_CELL = 15
MIN_MATURE_CELLS = 4
MIN_ROBUST_CELL_RATE = 60.0
MAX_BRAIN_SHARE = 80.0
MAX_REGIME_SHARE = 85.0
MAX_POSITIVE_CELL_CONCENTRATION = 70.0
MIN_CELL_MEAN_R = -0.20


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _trade_r(row: dict[str, Any]) -> float | None:
    risk = _f(row.get("risk_budget"))
    if risk <= 0:
        return None
    # Guard corrupted/outlier records from dominating the diagnostic matrix.
    return max(-10.0, min(10.0, _f(row.get("realized_pnl")) / risk))


def _metrics(rs: list[float]) -> dict[str, Any]:
    if not rs:
        return {"trades": 0, "mean_r": 0.0, "net_r": 0.0, "profit_factor": 0.0, "win_rate_pct": 0.0}
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(rs),
        "mean_r": round(sum(rs) / len(rs), 4),
        "net_r": round(sum(rs), 4),
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else (999.0 if gross_win else 0.0),
        "win_rate_pct": round(len(wins) / len(rs) * 100.0, 2),
    }


def robustness_matrix_gate(
    samples: list[dict[str, Any]] | None,
    stability: dict[str, Any] | None = None,
    sample_limit: int = 200,
) -> dict[str, Any]:
    """Check whether PAPER edge is diversified across naturally observed contexts.

    This is not a mandate to trade every brain/regime. It only asks whether the
    evidence already collected is broad enough to rule out a single-cell edge.
    """
    stability = stability or {}
    rows = list(samples or [])[-max(MIN_SAMPLES, min(int(sample_limit), 1000)):]
    valid: list[dict[str, Any]] = []
    for row in rows:
        r = _trade_r(row)
        if r is None:
            continue
        valid.append({
            **row,
            "r": r,
            "brain": str(row.get("brain") or "UNKNOWN"),
            "regime": str(row.get("market_regime") or "UNKNOWN"),
        })

    brain_counts = Counter(r["brain"] for r in valid if r["brain"] != "UNKNOWN")
    regime_counts = Counter(r["regime"] for r in valid if r["regime"] != "UNKNOWN")
    total = len(valid)
    qualifying_brains = {k: v for k, v in brain_counts.items() if v >= MIN_BRAIN_TRADES}
    qualifying_regimes = {k: v for k, v in regime_counts.items() if v >= MIN_REGIME_TRADES}
    max_brain_share = max((v / total * 100.0 for v in brain_counts.values()), default=100.0)
    max_regime_share = max((v / total * 100.0 for v in regime_counts.values()), default=100.0)

    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in valid:
        if row["brain"] == "UNKNOWN" or row["regime"] == "UNKNOWN":
            continue
        grouped[(row["brain"], row["regime"])].append(row["r"])

    cells: list[dict[str, Any]] = []
    for (brain, regime), rs in sorted(grouped.items()):
        m = _metrics(rs)
        m.update({"brain": brain, "regime": regime, "mature": len(rs) >= MIN_MATURE_CELL})
        m["robust"] = bool(m["mature"] and m["mean_r"] > 0 and m["profit_factor"] >= 1.05)
        cells.append(m)

    mature = [c for c in cells if c["mature"]]
    robust = [c for c in mature if c["robust"]]
    robust_rate = len(robust) / len(mature) * 100.0 if mature else 0.0
    worst_mature_mean = min((c["mean_r"] for c in mature), default=-999.0)

    positive_cells = [c for c in mature if c["net_r"] > 0]
    total_positive_r = sum(c["net_r"] for c in positive_cells)
    largest_positive_r = max((c["net_r"] for c in positive_cells), default=0.0)
    concentration = largest_positive_r / total_positive_r * 100.0 if total_positive_r > 0 else 100.0

    ladder_passed = int(stability.get("highest_level", 0) or 0) >= 3 or stability.get("status") == "STABILITY_7D_CONFIRMED"
    gates = [
        {"id":"seven_day_stability","passed":ladder_passed,"value":stability.get("status"),"requirement":"V1.28 must reach sequential 7D PAPER stability before robustness promotion."},
        {"id":"valid_r_sample","passed":total >= MIN_SAMPLES,"value":total,"requirement":f">= {MIN_SAMPLES} closed PAPER trades with valid recorded risk_budget."},
        {"id":"brain_coverage","passed":len(qualifying_brains) >= 2,"value":qualifying_brains,"requirement":f">= 2 naturally observed brains with >= {MIN_BRAIN_TRADES} trades each."},
        {"id":"brain_concentration","passed":max_brain_share <= MAX_BRAIN_SHARE,"value":round(max_brain_share,2),"requirement":f"One brain must not exceed {MAX_BRAIN_SHARE:.0f}% of the diagnostic sample."},
        {"id":"regime_coverage","passed":len(qualifying_regimes) >= 2,"value":qualifying_regimes,"requirement":f">= 2 naturally observed non-UNKNOWN regimes with >= {MIN_REGIME_TRADES} trades each."},
        {"id":"regime_concentration","passed":max_regime_share <= MAX_REGIME_SHARE,"value":round(max_regime_share,2),"requirement":f"One regime must not exceed {MAX_REGIME_SHARE:.0f}% of the diagnostic sample."},
        {"id":"mature_cells","passed":len(mature) >= MIN_MATURE_CELLS,"value":len(mature),"requirement":f">= {MIN_MATURE_CELLS} Brain×Regime cells with >= {MIN_MATURE_CELL} trades each."},
        {"id":"robust_cell_rate","passed":len(mature) >= MIN_MATURE_CELLS and robust_rate >= MIN_ROBUST_CELL_RATE,"value":round(robust_rate,2),"requirement":f">= {MIN_ROBUST_CELL_RATE:.0f}% of mature cells must have Mean R > 0 and PF >= 1.05."},
        {"id":"no_severely_negative_mature_cell","passed":bool(mature) and worst_mature_mean >= MIN_CELL_MEAN_R,"value":round(worst_mature_mean,4),"requirement":f"Every mature cell must have Mean R >= {MIN_CELL_MEAN_R:.2f}."},
        {"id":"positive_edge_concentration","passed":len(positive_cells) >= 2 and concentration <= MAX_POSITIVE_CELL_CONCENTRATION,"value":round(concentration,2),"requirement":f"Largest positive mature cell must contribute <= {MAX_POSITIVE_CELL_CONCENTRATION:.0f}% of total positive mature-cell R."},
    ]
    all_passed = all(g["passed"] for g in gates)
    return {
        "status": "ROBUSTNESS_MATRIX_PASSED" if all_passed else "ROBUSTNESS_MATRIX_BLOCKED",
        "gates": gates,
        "failed_gates": [g["id"] for g in gates if not g["passed"]],
        "sample": {
            "requested_limit": sample_limit, "valid_r_trades": total,
            "qualifying_brains": qualifying_brains, "qualifying_regimes": qualifying_regimes,
            "max_brain_share_pct": round(max_brain_share,2), "max_regime_share_pct": round(max_regime_share,2),
        },
        "matrix": cells,
        "mature_cells": len(mature), "robust_cells": len(robust),
        "robust_cell_rate_pct": round(robust_rate,2),
        "positive_edge_concentration_pct": round(concentration,2),
        "next_stage": "EXTENDED_REGIME_DIVERSE_PAPER_OBSERVATION" if all_passed else "CONTINUE_NATURAL_PAPER_COLLECTION",
        "paper_only": True, "automatic_real_execution": False,
        "real_execution_eligibility": False, "live_execution_enabled": False,
        "target_auto_apply": False, "guarantee": "NONE",
        "policy": "This gate observes naturally occurring Brain×Regime diversity; it must never force trades in weak regimes merely to satisfy coverage. Passing remains PAPER-only evidence.",
    }

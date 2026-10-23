from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any


MIN_OBSERVATION_HOURS = 24.0
MIN_RECENT_SNAPSHOTS = 8
MIN_NEW_TRADES = 20
MIN_STRICT_PASS_RATE = 75.0
MIN_MANDATORY_PASS_RATE = 75.0
MIN_TOTAL_PAPER_TRADES = 120

_STAGE_RANK = {
    "DATA_BUILDING": 0,
    "EVIDENCE_BUILDING": 1,
    "SHADOW_VALIDATED": 2,
    "STRICT_PAPER_REVIEW_CANDIDATE": 3,
}


def _dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _full_mandatory_pass(row: dict[str, Any]) -> bool:
    total = _i(row.get("mandatory_total"))
    return total > 0 and _i(row.get("mandatory_passed")) >= total


def evidence_stability_gate(history_report: dict[str, Any] | None) -> dict[str, Any]:
    """Require evidence to stay healthy across real time *and* new PAPER trades.

    Repeated identical snapshots alone cannot satisfy this gate. The 24h window
    must also contain material new closed-paper trades. This remains a research
    gate only and never authorizes real-money execution.
    """
    history_report = history_report or {}
    rows = sorted(
        list(history_report.get("snapshots") or []),
        key=lambda r: (str(r.get("captured_at", "")), _i(r.get("id"))),
    )
    if not rows:
        return {
            "status": "STABILITY_WINDOW_BLOCKED", "gates": [],
            "failed_gates": ["history_available"], "window": {},
            "paper_only": True, "real_execution_eligibility": False,
            "live_execution_enabled": False, "automatic_real_execution": False,
            "message": "Research history is empty; stability cannot be evaluated.",
        }

    current = rows[-1]
    end = _dt(current.get("captured_at"))
    first_time = _dt(rows[0].get("captured_at"))
    total_span = (end - first_time).total_seconds() / 3600.0 if end and first_time else 0.0
    cutoff = end - timedelta(hours=MIN_OBSERVATION_HOURS) if end else None

    if cutoff:
        recent = [r for r in rows if (_dt(r.get("captured_at")) or end) >= cutoff]
        before = [r for r in rows if (_dt(r.get("captured_at")) or end) <= cutoff]
        baseline = before[-1] if before else rows[0]
    else:
        recent, baseline = rows, rows[0]

    strict_rate = (sum(1 for r in recent if r.get("strict_pass")) / len(recent) * 100.0) if recent else 0.0
    mandatory_rate = (sum(1 for r in recent if _full_mandatory_pass(r)) / len(recent) * 100.0) if recent else 0.0
    trade_growth = max(0, _i(current.get("paper_trades")) - _i(baseline.get("paper_trades")))

    regressions = 0
    for prev, row in zip(recent, recent[1:]):
        prev_rank = _STAGE_RANK.get(str(prev.get("status")), -1)
        row_rank = _STAGE_RANK.get(str(row.get("status")), -1)
        if row_rank < prev_rank or (bool(prev.get("strict_pass")) and not bool(row.get("strict_pass"))):
            regressions += 1

    real_interlock = all(not bool(r.get("real_execution_eligibility", False)) for r in recent)
    current_candidate = str(current.get("status")) == "STRICT_PAPER_REVIEW_CANDIDATE"
    current_strict = bool(current.get("strict_pass"))
    total_trades = _i(current.get("paper_trades"))

    gates = [
        {
            "id": "observation_span",
            "passed": total_span >= MIN_OBSERVATION_HOURS,
            "value": round(total_span, 2),
            "requirement": f"Research history must span at least {MIN_OBSERVATION_HOURS:.0f} real hours.",
        },
        {
            "id": "recent_snapshot_density",
            "passed": len(recent) >= MIN_RECENT_SNAPSHOTS,
            "value": len(recent),
            "requirement": f"At least {MIN_RECENT_SNAPSHOTS} evidence snapshots must exist in the latest 24h observation window.",
        },
        {
            "id": "new_paper_trades",
            "passed": trade_growth >= MIN_NEW_TRADES and total_trades >= MIN_TOTAL_PAPER_TRADES,
            "value": {"new_trades": trade_growth, "total_trades": total_trades},
            "requirement": f"The observation window must include >= {MIN_NEW_TRADES} new closed PAPER trades and total PAPER trades >= {MIN_TOTAL_PAPER_TRADES}.",
        },
        {
            "id": "unified_stage_now",
            "passed": current_candidate,
            "value": current.get("status"),
            "requirement": "Current Unified Research Readiness must remain STRICT_PAPER_REVIEW_CANDIDATE.",
        },
        {
            "id": "strict_paper_now",
            "passed": current_strict,
            "value": current.get("strict_status"),
            "requirement": "Current Strict Paper Review must be PASSED.",
        },
        {
            "id": "strict_paper_stability",
            "passed": strict_rate >= MIN_STRICT_PASS_RATE,
            "value": round(strict_rate, 2),
            "requirement": f"Strict Paper must pass in >= {MIN_STRICT_PASS_RATE:.0f}% of snapshots in the latest 24h window.",
        },
        {
            "id": "mandatory_gate_stability",
            "passed": mandatory_rate >= MIN_MANDATORY_PASS_RATE,
            "value": round(mandatory_rate, 2),
            "requirement": f"All Unified mandatory gates must be simultaneously passed in >= {MIN_MANDATORY_PASS_RATE:.0f}% of recent snapshots.",
        },
        {
            "id": "no_recent_regression",
            "passed": regressions == 0,
            "value": regressions,
            "requirement": "No Unified-stage downgrade or Strict-Paper PASS→BLOCKED transition may occur inside the observation window.",
        },
        {
            "id": "real_execution_interlock",
            "passed": real_interlock,
            "value": "LOCKED" if real_interlock else "UNSAFE_FLAG",
            "requirement": "Real-execution eligibility must remain false for every snapshot in the stability window.",
        },
    ]

    all_passed = all(g["passed"] for g in gates)
    return {
        "status": "STABILITY_WINDOW_PASSED" if all_passed else "STABILITY_WINDOW_BLOCKED",
        "gates": gates,
        "failed_gates": [g["id"] for g in gates if not g["passed"]],
        "window": {
            "hours_required": MIN_OBSERVATION_HOURS,
            "total_history_span_hours": round(total_span, 2),
            "recent_snapshots": len(recent),
            "baseline_at": baseline.get("captured_at"),
            "latest_at": current.get("captured_at"),
            "new_paper_trades": trade_growth,
            "total_paper_trades": total_trades,
            "strict_pass_rate_pct": round(strict_rate, 2),
            "mandatory_full_pass_rate_pct": round(mandatory_rate, 2),
            "regressions": regressions,
        },
        "next_stage": "EXTENDED_PAPER_STABILITY_OBSERVATION" if all_passed else "CONTINUE_PAPER_STABILITY_COLLECTION",
        "paper_only": True,
        "automatic_real_execution": False,
        "real_execution_eligibility": False,
        "live_execution_enabled": False,
        "target_auto_apply": False,
        "score_is_authorization": False,
        "guarantee": "NONE",
        "policy": "Passing V1.27 proves only short-horizon stability of research/PAPER evidence. It never authorizes real-money trading or automatic target changes.",
    }

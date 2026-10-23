from __future__ import annotations

from statistics import fmean
from typing import Any

MIN_CHECKPOINTS = 4
MIN_TRADE_SPAN = 60
RECENT_REQUIRED = 3


def _window30_mean(snapshot: dict[str, Any]) -> float:
    try:
        payload = snapshot.get("payload") or {}
        return float((((payload.get("windows") or {}).get("30") or {}).get("mean_r", 0.0)) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def extended_paper_observation(
    current_review: dict[str, Any] | None,
    snapshots: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Evaluate persistence of V1.25 PAPER review across later trade checkpoints.

    Checkpoints are separated by newly closed eligible trades, but their rolling
    30/60/100 windows still overlap. This is persistence evidence only, never
    independent OOS evidence and never permission for real-money execution.
    """
    current = current_review or {}
    history = sorted(
        list(snapshots or []),
        key=lambda x: (int(x.get("eligible_samples", 0) or 0), int(x.get("id", 0) or 0)),
    )
    counts = [int(x.get("eligible_samples", 0) or 0) for x in history]
    span = (counts[-1] - counts[0]) if len(counts) >= 2 else 0
    gaps = [b - a for a, b in zip(counts, counts[1:])]
    spacing_ok = bool(gaps) and all(g >= 20 for g in gaps)

    recent = history[-RECENT_REQUIRED:]
    recent_statuses = [str(x.get("status", "")) for x in recent]
    recent_passes = sum(s == "STRICT_PAPER_REVIEW_PASSED" for s in recent_statuses)
    last_three_pass = len(recent) == RECENT_REQUIRED and recent_passes == RECENT_REQUIRED
    current_pass = current.get("status") == "STRICT_PAPER_REVIEW_PASSED"

    last_four = history[-4:]
    last_four_pass_rate = (
        sum(str(x.get("status", "")) == "STRICT_PAPER_REVIEW_PASSED" for x in last_four) / len(last_four)
        if last_four else 0.0
    )

    mean30_series = [_window30_mean(x) for x in recent]
    mean30_positive = len(mean30_series) == RECENT_REQUIRED and all(x > 0 for x in mean30_series)
    mean30_average = fmean(mean30_series) if mean30_series else 0.0
    latest_mean30 = mean30_series[-1] if mean30_series else 0.0
    persistence_decay_ok = (
        len(mean30_series) == RECENT_REQUIRED
        and mean30_average > 0
        and latest_mean30 >= mean30_average * 0.50
    )

    paper_interlock = (
        bool(current.get("paper_only", True))
        and not bool(current.get("automatic_real_execution", False))
        and not bool(current.get("real_execution_eligibility", False))
        and not bool(current.get("live_execution_enabled", False))
        and not bool(current.get("target_auto_apply", False))
    )

    gates = [
        {
            "id": "checkpoint_count",
            "passed": len(history) >= MIN_CHECKPOINTS,
            "value": len(history),
            "requirement": f"At least {MIN_CHECKPOINTS} persisted review checkpoints are required.",
        },
        {
            "id": "trade_span",
            "passed": span >= MIN_TRADE_SPAN,
            "value": span,
            "requirement": f"Observation checkpoints must span at least {MIN_TRADE_SPAN} newly eligible trades.",
        },
        {
            "id": "checkpoint_spacing",
            "passed": len(history) >= MIN_CHECKPOINTS and spacing_ok,
            "value": gaps,
            "requirement": "Persisted checkpoints must be separated by at least 20 newly eligible trades.",
        },
        {
            "id": "recent_three_pass",
            "passed": last_three_pass,
            "value": recent_statuses,
            "requirement": "The latest 3 persisted Strict Paper checkpoints must all pass.",
        },
        {
            "id": "current_review_pass",
            "passed": current_pass,
            "value": current.get("status", "NOT_RUN"),
            "requirement": "The current V1.25 Strict Paper Review must still pass now.",
        },
        {
            "id": "persistent_recent_edge",
            "passed": mean30_positive and persistence_decay_ok,
            "value": {
                "recent_30_mean_r_series": [round(x, 4) for x in mean30_series],
                "recent_average": round(mean30_average, 4),
                "latest": round(latest_mean30, 4),
            },
            "requirement": "Recent 30-trade Mean R must remain positive across the latest 3 checkpoints without >50% decay versus their average.",
        },
        {
            "id": "paper_only_interlock",
            "passed": paper_interlock,
            "value": "LOCKED" if paper_interlock else "UNSAFE_FLAG",
            "requirement": "Paper-only interlock must remain locked; no live eligibility, auto execution, or target auto-apply is allowed.",
        },
    ]

    all_pass = all(g["passed"] for g in gates)
    if all_pass:
        status = "PERSISTENCE_CONFIRMED_PAPER_ONLY"
        next_stage = "CONTINUE_LONG_HORIZON_PAPER_MONITORING"
    elif current_pass and history:
        status = "PERSISTENCE_BUILDING"
        next_stage = "COLLECT_MORE_CHECKPOINTS"
    else:
        status = "PERSISTENCE_NOT_CONFIRMED"
        next_stage = "CONTINUE_PAPER_AND_REVALIDATE"

    timeline = [
        {
            "id": x.get("id"),
            "eligible_samples": int(x.get("eligible_samples", 0) or 0),
            "status": x.get("status"),
            "captured_at": x.get("captured_at"),
            "window30_mean_r": round(_window30_mean(x), 4),
        }
        for x in history[-12:]
    ]

    return {
        "status": status,
        "next_stage": next_stage,
        "checkpoint_count": len(history),
        "required_checkpoints": MIN_CHECKPOINTS,
        "trade_span": span,
        "required_trade_span": MIN_TRADE_SPAN,
        "checkpoint_gaps": gaps[-12:],
        "last_four_pass_rate_pct": round(last_four_pass_rate * 100.0, 1),
        "timeline": timeline,
        "gates": gates,
        "failed_gates": [g["id"] for g in gates if not g["passed"]],
        "evidence_type": "TEMPORAL_PERSISTENCE_DIAGNOSTIC",
        "independence_warning": "Checkpoint windows overlap. Persistence across later trade counts is useful stability evidence but is not independent OOS evidence.",
        "paper_only": True,
        "automatic_real_execution": False,
        "real_execution_eligibility": False,
        "live_execution_enabled": False,
        "target_auto_apply": False,
        "guarantee": "NONE",
        "policy": "V1.26 can only confirm PAPER persistence. Even a full pass keeps the system in long-horizon PAPER monitoring and does not authorize real-money execution.",
    }

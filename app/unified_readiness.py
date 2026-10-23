from __future__ import annotations

from typing import Any


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def unified_research_readiness(
    core_readiness: dict[str, Any] | None,
    target_gate: dict[str, Any] | None,
    edge_lab: dict[str, Any] | None = None,
    incremental_edge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate research evidence without granting execution authority.

    The aggregate score is informational only. Stage promotion is determined by
    mandatory gates, never by a weighted score. Feature research is supporting
    evidence rather than a forced gate so the system is not incentivized to
    manufacture/overfit a new feature merely to advance stages.
    """
    core = core_readiness or {}
    target = target_gate or {}
    edge = edge_lab or {}
    incremental = incremental_edge or {}

    core_status = str(core.get("status", "NOT_READY"))
    core_score = _as_float(core.get("score"))
    core_live_flag = bool(core.get("live_execution_enabled", False))
    target_live_flag = bool(target.get("real_execution_enabled", False))
    target_pass = bool(target.get("all_gates_passed", False))
    target_gates = list(target.get("gates") or [])
    target_failed = list(target.get("failed_gates") or [])

    feature_candidates = _as_int(edge.get("diversified_candidate_count"))
    feature_samples = _as_int(edge.get("samples"))
    incremental_candidates = _as_int(incremental.get("eligible_count"))
    incremental_samples = _as_int(incremental.get("samples"))
    feature_oos_evidence = (
        incremental.get("status") == "SHADOW_TRIAL_CANDIDATES"
        and incremental_candidates > 0
        and incremental_samples >= 90
    )

    core_gate_rows = list(core.get("hard_gates") or [])
    core_failed = [str(g.get("id")) for g in core_gate_rows if not g.get("passed")]

    mandatory_gates = [
        {
            "id": "core_execution_readiness",
            "passed": core_status == "LIVE_CANDIDATE",
            "value": {"status": core_status, "score": core_score, "failed": core_failed},
            "requirement": "Core paper/OOS/drawdown/regime/cycle readiness must pass every hard gate.",
        },
        {
            "id": "target_evidence_consensus",
            "passed": target_pass,
            "value": {"status": target.get("status", "NOT_RUN"), "failed": target_failed},
            "requirement": "Full historical target walk-forward and frozen-entry live shadow must agree under the V1.23 gate.",
        },
        {
            "id": "real_execution_interlock",
            "passed": not core_live_flag and not target_live_flag,
            "value": "LOCKED" if not core_live_flag and not target_live_flag else "UNSAFE_FLAG",
            "requirement": "Automatic real-money execution must remain disabled while research readiness is evaluated.",
        },
    ]

    supporting_evidence = [
        {
            "id": "feature_edge_lab",
            "passed": edge.get("status") == "OOS_CANDIDATES_AVAILABLE" and feature_candidates > 0,
            "value": {
                "status": edge.get("status", "NOT_RUN"),
                "samples": feature_samples,
                "diversified_candidates": feature_candidates,
            },
            "meaning": "Chronological feature audit found diversified OOS candidates. Informational; no auto-promotion.",
        },
        {
            "id": "incremental_feature_walkforward",
            "passed": feature_oos_evidence,
            "value": {
                "status": incremental.get("status", "NOT_RUN"),
                "samples": incremental_samples,
                "eligible": incremental_candidates,
            },
            "meaning": "At least one feature improved an expanding-window baseline in repeated forward folds. Still shadow-only.",
        },
    ]

    all_mandatory = all(g["passed"] for g in mandatory_gates)
    interlock_ok = mandatory_gates[2]["passed"]

    if all_mandatory:
        status = "PILOT_REVIEW_CANDIDATE"
        message = (
            "Mandatory research gates passed. This permits only a separate review of a tiny, hard-capped paper/live-pilot design; "
            "nothing is enabled automatically."
        )
    elif core_status in {"SHADOW_READY", "LIVE_CANDIDATE"} and target_pass and interlock_ok:
        status = "SHADOW_VALIDATED"
        message = "Target evidence is validated, but one or more core execution hard gates remain open. Continue paper/shadow validation."
    elif core_score >= 40.0 or target_pass or feature_oos_evidence:
        status = "EVIDENCE_BUILDING"
        message = "Some evidence layers are promising, but mandatory readiness gates are still open."
    else:
        status = "DATA_BUILDING"
        message = "Evidence is still immature. Continue collecting chronologically separated paper/OOS/regime-diverse samples."

    target_pass_count = sum(1 for g in target_gates if g.get("passed"))
    target_total = len(target_gates)
    target_score = (target_pass_count / target_total * 100.0) if target_total else (100.0 if target_pass else 0.0)
    feature_score = min(
        100.0,
        (25.0 if edge.get("status") == "OOS_CANDIDATES_AVAILABLE" else 0.0)
        + min(25.0, feature_candidates * 5.0)
        + (30.0 if feature_oos_evidence else 0.0)
        + min(20.0, incremental_candidates * 5.0),
    )
    research_score = round(core_score * 0.65 + target_score * 0.25 + feature_score * 0.10, 1)

    return {
        "status": status,
        "research_score": research_score,
        "score_is_authorization": False,
        "message": message,
        "mandatory_gates": mandatory_gates,
        "failed_mandatory_gates": [g["id"] for g in mandatory_gates if not g["passed"]],
        "supporting_evidence": supporting_evidence,
        "core_readiness": {
            "status": core_status,
            "score": core_score,
            "passed": core.get("passed"),
            "total": core.get("total"),
            "failed_hard_gates": core_failed,
            "hard_gates": core_gate_rows,
        },
        "target_evidence": {
            "status": target.get("status", "NOT_RUN"),
            "all_gates_passed": target_pass,
            "failed_gates": target_failed,
            "successful_full_walkforward_brains": target.get("successful_full_walkforward_brains", []),
        },
        "feature_research": {
            "edge_status": edge.get("status", "NOT_RUN"),
            "edge_samples": feature_samples,
            "diversified_candidates": feature_candidates,
            "incremental_status": incremental.get("status", "NOT_RUN"),
            "incremental_samples": incremental_samples,
            "incremental_candidates": incremental_candidates,
            "incremental_oos_evidence": feature_oos_evidence,
            "is_mandatory_for_stage": False,
        },
        "automatic_real_execution": False,
        "live_execution_enabled": False,
        "target_auto_apply": False,
        "guarantee": "NONE",
        "policy": "No score or stage starts real trading. PILOT_REVIEW_CANDIDATE only permits a separate explicit review of a tiny-capital, hard-capped pilot with kill-switches; real execution remains OFF in this build.",
    }

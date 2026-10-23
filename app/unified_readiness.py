from __future__ import annotations

from typing import Any


def unified_research_readiness(
    core_readiness: dict[str, Any] | None,
    target_gate: dict[str, Any] | None,
    edge_lab: dict[str, Any] | None = None,
    incremental_edge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine evidence layers without granting automatic execution authority."""
    core = core_readiness or {}
    target = target_gate or {}
    edge = edge_lab or {}
    incremental = incremental_edge or {}

    core_status = str(core.get("status", "NOT_READY"))
    core_score = float(core.get("score", 0.0) or 0.0)
    target_pass = bool(target.get("all_gates_passed", False))
    target_failed = list(target.get("failed_gates") or [])

    feature_candidates = int(edge.get("diversified_candidate_count", 0) or 0)
    incremental_candidates = int(incremental.get("eligible_count", 0) or 0)
    feature_oos_evidence = incremental.get("status") == "SHADOW_TRIAL_CANDIDATES" and incremental_candidates > 0

    gates = [
        {
            "id": "core_execution_readiness",
            "passed": core_status == "LIVE_CANDIDATE",
            "value": {"status": core_status, "score": core_score},
            "requirement": "Core readiness must pass paper sample, genuine execution OOS, drawdown, regime robustness and cycle holdout gates.",
        },
        {
            "id": "target_evidence_consensus",
            "passed": target_pass,
            "value": {"status": target.get("status"), "failed": target_failed},
            "requirement": "Full historical target walk-forward and frozen-entry live shadow must agree under the V1.23 evidence gate.",
        },
        {
            "id": "real_execution_interlock",
            "passed": not bool(core.get("live_execution_enabled", False)) and not bool(target.get("real_execution_enabled", False)),
            "value": "LOCKED",
            "requirement": "Automatic real-money execution must remain disabled during research readiness evaluation.",
        },
    ]

    core_pass = gates[0]["passed"]
    interlock = gates[2]["passed"]

    if core_pass and target_pass and interlock:
        status = "LIVE_PILOT_CANDIDATE"
        message = "All research evidence gates passed. This permits only a separately authorized tiny-capital pilot design; automatic real execution remains disabled."
    elif core_status in {"SHADOW_READY", "LIVE_CANDIDATE"} and target_pass and interlock:
        status = "SHADOW_VALIDATED"
        message = "Target evidence is validated, but core execution evidence is not yet sufficient for a live pilot. Continue paper/shadow testing."
    elif core_score >= 40 or target_pass or feature_oos_evidence:
        status = "EVIDENCE_BUILDING"
        message = "Some evidence layers are promising, but one or more hard readiness gates remain open."
    else:
        status = "DATA_BUILDING"
        message = "Evidence remains immature. Continue collecting paper, OOS and regime-diverse samples."

    # Informational score only; status above is determined by hard gates.
    target_score = 100.0 if target_pass else max(0.0, 100.0 - len(target_failed) * 14.0)
    feature_score = min(100.0, feature_candidates * 8.0 + incremental_candidates * 12.0)
    research_score = round(core_score * 0.65 + target_score * 0.25 + feature_score * 0.10, 1)

    return {
        "status": status,
        "research_score": research_score,
        "message": message,
        "hard_gates": gates,
        "core_readiness": {"status": core_status, "score": core_score, "passed": core.get("passed"), "total": core.get("total")},
        "target_evidence": {
            "status": target.get("status", "NOT_RUN"),
            "all_gates_passed": target_pass,
            "failed_gates": target_failed,
            "successful_full_walkforward_brains": target.get("successful_full_walkforward_brains", []),
        },
        "feature_research": {
            "edge_status": edge.get("status", "NOT_RUN"),
            "diversified_candidates": feature_candidates,
            "incremental_status": incremental.get("status", "NOT_RUN"),
            "incremental_candidates": incremental_candidates,
            "incremental_oos_evidence": feature_oos_evidence,
        },
        "automatic_real_execution": False,
        "live_execution_enabled": False,
        "guarantee": "NONE",
        "policy": "No status automatically starts real trading. LIVE_PILOT_CANDIDATE only permits a separate explicit decision about a tiny-capital, hard-capped pilot with immediate kill-switches.",
    }

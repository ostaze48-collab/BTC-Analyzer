from __future__ import annotations

from typing import Any

REQUIRED_FULL_BRAINS = 2
MIN_FULL_ROWS = 30
MIN_LIVE_RESOLVED = 30
MIN_LIVE_OVERRIDES = 12
MIN_LIVE_COVERAGE = 50.0


def _gate(name: str, passed: bool, value: Any, requirement: str) -> dict[str, Any]:
    return {"id": name, "passed": bool(passed), "value": value, "requirement": requirement}


def target_evidence_gate(
    full_results: dict[str, dict[str, Any]] | None,
    live_shadow: dict[str, Any] | None,
) -> dict[str, Any]:
    """Consensus gate for target-policy research promotion.

    This function can only authorize the *next research stage*. It never changes
    targets, position sizing, leverage, MASTER, or real execution.
    """
    full_results = full_results or {}
    live_shadow = live_shadow or {}

    successful_full = {
        brain: result for brain, result in full_results.items()
        if (result or {}).get("status") == "FULL_WALKFORWARD_OUTPERFORMS"
        and int((result or {}).get("validation_rows", 0) or 0) >= MIN_FULL_ROWS
        and float(((result or {}).get("holdout") or {}).get("delta_mean_r", 0.0) or 0.0) > 0
        and float(((result or {}).get("holdout") or {}).get("drawdown_ratio", 9.0) or 9.0) <= 1.10
    }

    live_ok = (
        live_shadow.get("status") == "LIVE_SHADOW_OUTPERFORMS"
        and int(live_shadow.get("resolved", 0) or 0) >= MIN_LIVE_RESOLVED
        and int(live_shadow.get("advisor_overrides", 0) or 0) >= MIN_LIVE_OVERRIDES
        and float(live_shadow.get("resolution_coverage_pct", 0.0) or 0.0) >= MIN_LIVE_COVERAGE
        and float((live_shadow.get("holdout") or {}).get("delta_mean_r", 0.0) or 0.0) > 0
        and float((live_shadow.get("holdout") or {}).get("drawdown_ratio", 9.0) or 9.0) <= 1.10
    )

    gates = [
        _gate(
            "full_walkforward_brains",
            len(successful_full) >= REQUIRED_FULL_BRAINS,
            sorted(successful_full),
            f"At least {REQUIRED_FULL_BRAINS} brains must pass full historical walk-forward with positive holdout and DD ratio <= 1.10.",
        ),
        _gate(
            "live_shadow_status",
            live_shadow.get("status") == "LIVE_SHADOW_OUTPERFORMS",
            live_shadow.get("status", "NOT_RUN"),
            "Frozen-entry live shadow must outperform baseline.",
        ),
        _gate(
            "live_shadow_resolved",
            int(live_shadow.get("resolved", 0) or 0) >= MIN_LIVE_RESOLVED,
            int(live_shadow.get("resolved", 0) or 0),
            f">= {MIN_LIVE_RESOLVED} resolved live-shadow comparisons.",
        ),
        _gate(
            "live_shadow_overrides",
            int(live_shadow.get("advisor_overrides", 0) or 0) >= MIN_LIVE_OVERRIDES,
            int(live_shadow.get("advisor_overrides", 0) or 0),
            f">= {MIN_LIVE_OVERRIDES} genuine target overrides.",
        ),
        _gate(
            "live_shadow_coverage",
            float(live_shadow.get("resolution_coverage_pct", 0.0) or 0.0) >= MIN_LIVE_COVERAGE,
            round(float(live_shadow.get("resolution_coverage_pct", 0.0) or 0.0), 2),
            f">= {MIN_LIVE_COVERAGE:.0f}% resolution coverage.",
        ),
        _gate(
            "live_holdout_risk_adjusted",
            live_ok,
            {
                "delta_mean_r": (live_shadow.get("holdout") or {}).get("delta_mean_r"),
                "drawdown_ratio": (live_shadow.get("holdout") or {}).get("drawdown_ratio"),
            },
            "Live final holdout must remain positive without >10% relative DD inflation.",
        ),
    ]

    passed = all(g["passed"] for g in gates)
    status = "BOUNDED_SHADOW_EXPERIMENT_CANDIDATE" if passed else "NOT_READY_FOR_TARGET_INFLUENCE"
    failed = [g["id"] for g in gates if not g["passed"]]

    return {
        "status": status,
        "all_gates_passed": passed,
        "gates": gates,
        "failed_gates": failed,
        "successful_full_walkforward_brains": sorted(successful_full),
        "live_shadow_status": live_shadow.get("status", "NOT_RUN"),
        "next_research_stage_allowed": passed,
        "auto_apply": False,
        "target_execution_weight": 0.0,
        "master_weight": 0.0,
        "real_execution_enabled": False,
        "policy": "Passing this gate permits only design/testing of a bounded paper-shadow experiment. It never authorizes automatic target changes or real-money trading.",
    }

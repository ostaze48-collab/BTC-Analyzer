from __future__ import annotations

from typing import Any


def _f(d: dict[str, Any] | None, key: str, default: float = 0.0) -> float:
    try:
        return float((d or {}).get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _i(d: dict[str, Any] | None, key: str, default: int = 0) -> int:
    try:
        return int((d or {}).get(key, default) or default)
    except (TypeError, ValueError):
        return default


def readiness_report(
    paper_stats: dict[str, Any] | None,
    learning: dict[str, Any] | None,
    execution_oos: dict[str, Any] | None,
    cycle_oos: dict[str, Any] | None,
) -> dict[str, Any]:
    """Conservative evidence gate for any future live-trading transition."""
    paper_stats = paper_stats or {}
    learning = learning or {}
    execution_oos = execution_oos or {}
    cycle_oos = cycle_oos or {}

    paper_trades = _i(paper_stats, "trades")
    paper_pf = _f(paper_stats, "profit_factor")
    paper_dd = _f(paper_stats, "max_drawdown_pct", 999.0)

    exec_type = str(execution_oos.get("validation_type", "NONE"))
    exec_is_oos = exec_type in {"WALK_FORWARD_OOS", "CHRONOLOGICAL_HOLDOUT_FROZEN_POLICY"}
    exec_trades = _i(execution_oos, "trades")
    exec_pf = _f(execution_oos, "profit_factor")
    exec_dd = _f(execution_oos, "max_drawdown_pct", 999.0)
    exec_avg_r = _f(execution_oos, "avg_r")
    exec_return = _f(execution_oos, "return_pct")

    cycle_samples = _i(cycle_oos, "samples")
    cycle_edge = _f(cycle_oos, "mean_signed_return")
    cycle_hit = _f(cycle_oos, "directional_accuracy_pct")

    matrix = list((learning or {}).get("brain_regime") or [])
    mature_regimes = [r for r in matrix if _i(r, "trades") >= 20]
    profitable_regimes = [r for r in mature_regimes if _f(r, "profit_factor") >= 1.05 and _f(r, "net_pnl") > 0]
    regime_coverage = len(profitable_regimes) / len(mature_regimes) if mature_regimes else 0.0

    hard_gates = [
        {"id":"paper_sample","label":"Paper sample ≥ 100 closed trades","passed":paper_trades >= 100,"value":paper_trades},
        {"id":"paper_risk","label":"Paper PF ≥ 1.20 and DD ≤ 12%","passed":paper_pf >= 1.20 and paper_dd <= 12.0,"value":{"pf":round(paper_pf,3),"dd":round(paper_dd,3)}},
        {"id":"oos_type","label":"Execution evidence is genuine chronological OOS / frozen-policy holdout","passed":exec_is_oos,"value":exec_type},
        {"id":"oos_sample","label":"Execution OOS ≥ 300 trades","passed":exec_is_oos and exec_trades >= 300,"value":exec_trades},
        {"id":"oos_edge","label":"Execution OOS PF ≥ 1.35, Avg R ≥ 0.10, Return > 0","passed":exec_is_oos and exec_pf >= 1.35 and exec_avg_r >= 0.10 and exec_return > 0,"value":{"pf":round(exec_pf,3),"avg_r":round(exec_avg_r,3),"return_pct":round(exec_return,3)}},
        {"id":"oos_drawdown","label":"Execution OOS max DD ≤ 10%","passed":exec_is_oos and exec_dd <= 10.0,"value":round(exec_dd,3)},
        {"id":"regime_robustness","label":"Profitable in ≥ 60% of mature Brain×Regime cells","passed":len(mature_regimes) >= 3 and regime_coverage >= 0.60,"value":{"mature":len(mature_regimes),"profitable":len(profitable_regimes),"coverage_pct":round(regime_coverage*100,2)}},
        {"id":"cycle_oos","label":"Cycle context has positive 90d holdout edge with ≥ 120 samples","passed":cycle_samples >= 120 and cycle_edge > 0 and cycle_hit >= 50.0,"value":{"samples":cycle_samples,"edge":round(cycle_edge,6),"accuracy_pct":round(cycle_hit,2)}},
    ]

    passed = sum(1 for g in hard_gates if g["passed"])
    score = round(passed / len(hard_gates) * 100, 1)

    if all(g["passed"] for g in hard_gates):
        status = "LIVE_CANDIDATE"
        message = "Evidence gates passed. Eligible for a separately controlled tiny-capital live pilot; profit is still not guaranteed."
    elif score >= 55 and paper_trades >= 50:
        status = "SHADOW_READY"
        message = "Promising, but continue paper/shadow testing. Live execution remains blocked."
    else:
        status = "NOT_READY"
        message = "Insufficient evidence for real-money execution. Continue research and paper/shadow testing."

    return {
        "status": status, "score": score, "hard_gates": hard_gates,
        "passed": passed, "total": len(hard_gates), "message": message,
        "live_execution_enabled": False, "guarantee": "NONE",
        "policy": "No automatic real-money transition. LIVE_CANDIDATE only permits a later separately authorized tiny-capital pilot.",
    }

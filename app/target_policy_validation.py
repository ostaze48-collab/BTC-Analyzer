from __future__ import annotations

from statistics import fmean
from typing import Any

from .target_advisor import build_historical_target_advisor_from_summary

MIN_RESOLVED = 30
MIN_HOLDOUT = 10
HOLDOUT_FRACTION = 0.30


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
        return x if x == x and abs(x) != float("inf") else default
    except (TypeError, ValueError):
        return default


def _partial_policy_r(target_r: float, mfe_r: float, stopped: bool) -> float | None:
    """Counterfactual R under the system's 30/40/30 partial-exit structure.

    If the observed paper path ended before a higher target can be resolved, None
    is returned. We never fabricate candles after the real paper trade closed.
    """
    target_r = max(1.0, min(5.0, float(target_r)))
    mfe_r = max(0.0, float(mfe_r))
    tp1 = min(1.0, target_r)
    tp2 = min(target_r, max(tp1, target_r * 0.60))

    if mfe_r >= target_r:
        return 0.30 * tp1 + 0.40 * tp2 + 0.30 * target_r
    if not stopped:
        return None
    if mfe_r < tp1:
        return -1.0
    if mfe_r < tp2:
        # TP1 was taken; remaining size would have been protected at entry.
        return 0.30 * tp1
    # TP1 + TP2 were taken; final 30% would have a stop at TP1.
    return 0.30 * tp1 + 0.40 * tp2 + 0.30 * tp1


def _metrics(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"trades": 0, "mean_r": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0}
    wins = sum(1 for x in values if x > 0)
    gross_win = sum(x for x in values if x > 0)
    gross_loss = abs(sum(x for x in values if x < 0))
    equity = peak = max_dd = 0.0
    for x in values:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": len(values),
        "mean_r": round(fmean(values), 4),
        "win_rate": round(wins / len(values) * 100.0, 2),
        "profit_factor": round(gross_win / gross_loss, 4) if gross_loss > 1e-12 else (10.0 if gross_win > 0 else 0.0),
        "max_drawdown_r": round(max_dd, 4),
    }


def validate_target_policy(edge_samples: list[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare current target policy with historical-advisor target on recorded paths.

    Evidence is chronological and conservative but incomplete: paper trades stop
    recording future candles after they close, so higher counterfactual targets may
    be unresolved. Full archive replay is intentionally a separate next stage.
    """
    trade_map = {int(t.get("id", 0)): t for t in trades}
    ordered = sorted(edge_samples, key=lambda s: (str(s.get("opened_at", "")), int(s.get("trade_id", 0))))
    rows: list[dict[str, Any]] = []
    eligible = 0

    for sample in ordered:
        trade = trade_map.get(int(sample.get("trade_id", 0)))
        if not trade:
            continue
        features = sample.get("features") or {}
        analog = features.get("historical_analogs") or {}
        advisor = build_historical_target_advisor_from_summary(analog)
        advisor_r = advisor.get("recommended_r")
        if advisor_r is None:
            continue
        plan = features.get("adaptive_risk_plan") or {}
        stop_pct = _finite(plan.get("stop_distance_pct"), 0.0)
        if stop_pct <= 0:
            continue
        eligible += 1
        mfe_pct = _finite(trade.get("mfe_pct"), 0.0)
        mfe_r = mfe_pct / stop_pct
        baseline_r_target = _finite(trade.get("target_r"), _finite(plan.get("target_r"), 0.0))
        if baseline_r_target <= 0:
            continue
        exit_reason = str(trade.get("exit_reason") or "")
        stopped = exit_reason == "STOP_LOSS"
        baseline_path_r = _partial_policy_r(baseline_r_target, mfe_r, stopped)
        advisor_path_r = _partial_policy_r(float(advisor_r), mfe_r, stopped)
        if baseline_path_r is None or advisor_path_r is None:
            continue
        rows.append({
            "trade_id": int(sample.get("trade_id", 0)),
            "opened_at": sample.get("opened_at"),
            "brain": sample.get("brain"),
            "regime": sample.get("market_regime"),
            "baseline_target_r": round(baseline_r_target, 3),
            "advisor_target_r": round(float(advisor_r), 3),
            "mfe_r": round(mfe_r, 3),
            "baseline_path_r": round(baseline_path_r, 4),
            "advisor_path_r": round(advisor_path_r, 4),
            "delta_r": round(advisor_path_r - baseline_path_r, 4),
            "exit_reason": exit_reason,
        })

    resolved = len(rows)
    coverage = resolved / eligible * 100.0 if eligible else 0.0
    baseline_values = [float(r["baseline_path_r"]) for r in rows]
    advisor_values = [float(r["advisor_path_r"]) for r in rows]
    baseline = _metrics(baseline_values)
    advisor = _metrics(advisor_values)

    holdout_n = max(MIN_HOLDOUT, int(resolved * HOLDOUT_FRACTION)) if resolved else 0
    holdout_n = min(holdout_n, resolved)
    holdout_rows = rows[-holdout_n:] if holdout_n else []
    holdout_baseline = _metrics([float(r["baseline_path_r"]) for r in holdout_rows])
    holdout_advisor = _metrics([float(r["advisor_path_r"]) for r in holdout_rows])

    delta_mean = float(advisor["mean_r"]) - float(baseline["mean_r"])
    holdout_delta = float(holdout_advisor["mean_r"]) - float(holdout_baseline["mean_r"])
    dd_ratio = (
        float(advisor["max_drawdown_r"]) / float(baseline["max_drawdown_r"])
        if float(baseline["max_drawdown_r"]) > 1e-12 else 0.0
    )
    holdout_dd_ratio = (
        float(holdout_advisor["max_drawdown_r"]) / float(holdout_baseline["max_drawdown_r"])
        if float(holdout_baseline["max_drawdown_r"]) > 1e-12 else 0.0
    )

    enough = resolved >= MIN_RESOLVED and len(holdout_rows) >= MIN_HOLDOUT and coverage >= 50.0
    improved = (
        enough
        and delta_mean >= 0.05
        and holdout_delta >= 0.05
        and float(advisor["profit_factor"]) >= float(baseline["profit_factor"])
        and float(holdout_advisor["profit_factor"]) >= float(holdout_baseline["profit_factor"])
        and dd_ratio <= 1.10
        and holdout_dd_ratio <= 1.10
    )
    status = "JOURNAL_SHADOW_OUTPERFORMS" if improved else ("NO_PROVEN_IMPROVEMENT" if enough else "INSUFFICIENT_RESOLVED_PATHS")

    return {
        "status": status,
        "mode": "JOURNAL_PATH_PARTIAL_VALIDATION",
        "auto_apply": False,
        "weight_in_risk_engine": 0.0,
        "eligible_with_advisor": eligible,
        "resolved_comparisons": resolved,
        "resolution_coverage_pct": round(coverage, 2),
        "minimum_resolved": MIN_RESOLVED,
        "baseline": baseline,
        "advisor": advisor,
        "delta_mean_r": round(delta_mean, 4),
        "drawdown_ratio": round(dd_ratio, 4),
        "holdout": {
            "trades": len(holdout_rows),
            "baseline": holdout_baseline,
            "advisor": holdout_advisor,
            "delta_mean_r": round(holdout_delta, 4),
            "drawdown_ratio": round(holdout_dd_ratio, 4),
        },
        "recent_resolved": rows[-20:],
        "limitations": [
            "Future candles after a paper trade closes are not available in the journal path.",
            "Counterfactual higher targets can therefore be unresolved and are excluded, not guessed.",
            "R-path comparison excludes fee/slippage differences because both policies share the same entry/stop path assumption.",
        ],
        "next_stage": "Full historical archive walk-forward must resolve every target path before any target policy can change execution.",
    }

from __future__ import annotations

from statistics import fmean
from typing import Any

from .target_advisor import build_historical_target_advisor_from_summary
from .target_policy_validation import _partial_policy_r

MIN_RESOLVED = 30
MIN_OVERRIDES = 12
MIN_HOLDOUT = 10


def _metrics(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"trades": 0, "mean_r": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0}
    wins = sum(1 for x in values if x > 0)
    gw = sum(x for x in values if x > 0)
    gl = abs(sum(x for x in values if x < 0))
    equity = peak = dd = 0.0
    for x in values:
        equity += x
        peak = max(peak, equity)
        dd = max(dd, peak - equity)
    return {
        "trades": len(values),
        "mean_r": round(fmean(values), 4),
        "win_rate": round(wins / len(values) * 100.0, 2),
        "profit_factor": round(gw / gl, 4) if gl > 1e-12 else (10.0 if gw > 0 else 0.0),
        "max_drawdown_r": round(dd, 4),
    }


def validate_live_shadow_target(edge_samples: list[dict[str, Any]], trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate target choices reconstructed strictly from frozen ENTRY evidence.

    Historical analogs and the baseline risk plan are already stored in each ENTRY
    feature snapshot. The advisor target is therefore reconstructed from what the
    system knew at entry, never from current/newer analog data. Execution remains
    unchanged; unresolved counterfactuals are excluded rather than guessed.
    """
    trade_map = {int(t.get("id", 0)): t for t in trades}
    samples = sorted(edge_samples, key=lambda s: (str(s.get("opened_at", "")), int(s.get("trade_id", 0))))
    eligible = overrides = 0
    rows: list[dict[str, Any]] = []

    for sample in samples:
        features = sample.get("features") or {}
        analog = features.get("historical_analogs") or {}
        plan = features.get("adaptive_risk_plan") or {}
        if analog.get("status") != "READY" or not plan:
            continue
        advisor = build_historical_target_advisor_from_summary(analog)
        advisor_target = advisor.get("recommended_r")
        if advisor_target is None:
            continue
        trade = trade_map.get(int(sample.get("trade_id", 0)))
        if not trade:
            continue
        stop_pct = float(plan.get("stop_distance_pct", 0.0) or 0.0)
        baseline_target = float(plan.get("target_r", trade.get("target_r", 0.0)) or 0.0)
        if stop_pct <= 0 or baseline_target <= 0:
            continue
        eligible += 1
        if abs(float(advisor_target) - baseline_target) > 1e-9:
            overrides += 1

        mfe_r = float(trade.get("mfe_pct", 0.0) or 0.0) / stop_pct
        stopped = str(trade.get("exit_reason") or "") == "STOP_LOSS"
        baseline_r = _partial_policy_r(baseline_target, mfe_r, stopped)
        shadow_r = _partial_policy_r(float(advisor_target), mfe_r, stopped)
        if baseline_r is None or shadow_r is None:
            continue
        rows.append({
            "trade_id": int(sample.get("trade_id", 0)),
            "opened_at": sample.get("opened_at"),
            "brain": sample.get("brain"),
            "regime": sample.get("market_regime"),
            "schema": features.get("schema"),
            "baseline_target_r": round(baseline_target, 3),
            "shadow_target_r": round(float(advisor_target), 3),
            "baseline_r": round(float(baseline_r), 4),
            "shadow_r": round(float(shadow_r), 4),
            "delta_r": round(float(shadow_r) - float(baseline_r), 4),
            "analog_matches_at_entry": int(analog.get("matches", 0) or 0),
            "analog_quality_at_entry": analog.get("quality"),
            "advisor_ev_at_entry": advisor.get("best_conservative_ev_r"),
        })

    resolved = len(rows)
    coverage = resolved / eligible * 100.0 if eligible else 0.0
    base = _metrics([float(r["baseline_r"]) for r in rows])
    shadow = _metrics([float(r["shadow_r"]) for r in rows])
    delta = float(shadow["mean_r"]) - float(base["mean_r"])
    dd_ratio = float(shadow["max_drawdown_r"]) / float(base["max_drawdown_r"]) if float(base["max_drawdown_r"]) > 1e-12 else 0.0

    holdout_n = max(MIN_HOLDOUT, int(resolved * 0.30)) if resolved else 0
    holdout_n = min(holdout_n, resolved)
    holdout = rows[-holdout_n:] if holdout_n else []
    hb = _metrics([float(r["baseline_r"]) for r in holdout])
    hs = _metrics([float(r["shadow_r"]) for r in holdout])
    hdelta = float(hs["mean_r"]) - float(hb["mean_r"])
    hdd_ratio = float(hs["max_drawdown_r"]) / float(hb["max_drawdown_r"]) if float(hb["max_drawdown_r"]) > 1e-12 else 0.0

    enough = resolved >= MIN_RESOLVED and overrides >= MIN_OVERRIDES and holdout_n >= MIN_HOLDOUT and coverage >= 50.0
    passes = (
        enough and delta >= 0.05 and hdelta >= 0.05
        and float(shadow["profit_factor"]) >= float(base["profit_factor"])
        and float(hs["profit_factor"]) >= float(hb["profit_factor"])
        and dd_ratio <= 1.10 and hdd_ratio <= 1.10
    )
    status = "LIVE_SHADOW_OUTPERFORMS" if passes else ("NO_LIVE_SHADOW_EDGE" if enough else "INSUFFICIENT_LIVE_SHADOW_DATA")

    by_brain: dict[str, Any] = {}
    for brain in sorted({str(r.get("brain")) for r in rows}):
        subset = [r for r in rows if str(r.get("brain")) == brain]
        if len(subset) < 5:
            continue
        bm = _metrics([float(r["baseline_r"]) for r in subset])
        sm = _metrics([float(r["shadow_r"]) for r in subset])
        by_brain[brain] = {
            "trades": len(subset), "baseline_mean_r": bm["mean_r"], "shadow_mean_r": sm["mean_r"],
            "delta_mean_r": round(float(sm["mean_r"]) - float(bm["mean_r"]), 4),
        }

    return {
        "status": status,
        "mode": "FROZEN_ENTRY_LIVE_SHADOW",
        "auto_apply": False,
        "weight_in_risk_engine": 0.0,
        "entry_evidence_frozen": True,
        "eligible": eligible,
        "advisor_overrides": overrides,
        "resolved": resolved,
        "resolution_coverage_pct": round(coverage, 2),
        "baseline": base,
        "shadow": shadow,
        "delta_mean_r": round(delta, 4),
        "drawdown_ratio": round(dd_ratio, 4),
        "holdout": {
            "trades": holdout_n, "baseline": hb, "shadow": hs,
            "delta_mean_r": round(hdelta, 4), "drawdown_ratio": round(hdd_ratio, 4),
        },
        "by_brain": by_brain,
        "recent_resolved": rows[-20:],
        "policy": "Advisor target is reconstructed only from the historical_analogs snapshot frozen at ENTRY. It never changes execution in V1.22.",
        "limitations": [
            "Paper journal stops observing future candles after the real trade closes; some higher shadow targets remain unresolved.",
            "Full Historical Walk-Forward V1.21 is the complete-candle complement to this live-shadow evidence.",
        ],
        "next_stage": "Only if V1.21 full walk-forward and V1.22 live shadow both remain positive across brains/regimes can a later bounded target blend be considered.",
    }

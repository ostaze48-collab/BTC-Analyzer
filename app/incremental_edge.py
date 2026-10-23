from __future__ import annotations

from statistics import fmean, median
from typing import Any

from .edge_lab import _family, _flatten_selected, _is_directional, _pearson, _source

MIN_TOTAL = 90
MIN_INITIAL_TRAIN = 45
TEST_BLOCK = 15
MIN_FEATURE_TRAIN = 30
MIN_FEATURE_TEST = 10


def _r_metrics(values: list[float]) -> dict[str, float]:
    if not values:
        return {"trades": 0, "mean_r": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0}
    wins = sum(1 for x in values if x > 0)
    gross_win = sum(x for x in values if x > 0)
    gross_loss = abs(sum(x for x in values if x < 0))
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for x in values:
        equity += x
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": len(values),
        "mean_r": fmean(values),
        "win_rate": wins / len(values) * 100.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 1e-12 else (10.0 if gross_win > 0 else 0.0),
        "max_drawdown_r": max_dd,
    }


def _prepare(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(samples, key=lambda s: (str(s.get("opened_at", "")), int(s.get("trade_id", 0))))
    out: list[dict[str, Any]] = []
    for sample in ordered:
        risk = float(sample.get("risk_budget", 0.0) or 0.0)
        if risk <= 0:
            continue
        pnl = float(sample.get("realized_pnl", 0.0) or 0.0)
        direction_sign = 1.0 if sample.get("direction") == "LONG" else -1.0
        raw = _flatten_selected(sample.get("features") or {})
        values = {
            name: (value * direction_sign if _is_directional(name) else value)
            for name, value in raw.items()
        }
        out.append({
            "r": pnl / risk,
            "values": values,
            "regime": sample.get("market_regime") or "UNKNOWN",
            "brain": sample.get("brain") or "UNKNOWN",
        })
    return out


def _folds(n: int) -> list[tuple[int, int]]:
    folds: list[tuple[int, int]] = []
    train_end = MIN_INITIAL_TRAIN
    while train_end + MIN_FEATURE_TEST <= n:
        test_end = min(n, train_end + TEST_BLOCK)
        if test_end - train_end >= MIN_FEATURE_TEST:
            folds.append((train_end, test_end))
        train_end += TEST_BLOCK
    return folds


def _evaluate_feature(rows: list[dict[str, Any]], feature: str) -> dict[str, Any] | None:
    fold_rows: list[dict[str, Any]] = []
    for train_end, test_end in _folds(len(rows)):
        train = [(r["values"][feature], r["r"]) for r in rows[:train_end] if feature in r["values"]]
        test = [(r["values"][feature], r["r"]) for r in rows[train_end:test_end] if feature in r["values"]]
        if len(train) < MIN_FEATURE_TRAIN or len(test) < MIN_FEATURE_TEST:
            continue
        tx, ty = [x for x, _ in train], [y for _, y in train]
        corr = _pearson(tx, ty)
        if abs(corr) < 0.02:
            continue
        orientation = 1.0 if corr >= 0 else -1.0
        threshold = median(tx)
        baseline_r = [y for _, y in test]
        if orientation > 0:
            filtered_r = [y for x, y in test if x >= threshold]
        else:
            filtered_r = [y for x, y in test if x <= threshold]
        if len(filtered_r) < max(4, int(len(test) * 0.25)):
            continue
        baseline = _r_metrics(baseline_r)
        filtered = _r_metrics(filtered_r)
        baseline_dd = baseline["max_drawdown_r"]
        filtered_dd = filtered["max_drawdown_r"]
        dd_ratio = filtered_dd / baseline_dd if baseline_dd > 1e-12 else (0.0 if filtered_dd <= 1e-12 else 9.99)
        delta_mean = filtered["mean_r"] - baseline["mean_r"]
        delta_pf = min(10.0, filtered["profit_factor"]) - min(10.0, baseline["profit_factor"])
        passed = (
            delta_mean > 0.05
            and filtered["mean_r"] > 0
            and delta_pf >= -0.05
            and dd_ratio <= 1.15
        )
        fold_rows.append({
            "train_end": train_end,
            "test_end": test_end,
            "train_corr": round(corr, 4),
            "orientation": "HIGHER_BETTER" if orientation > 0 else "LOWER_BETTER",
            "threshold": round(float(threshold), 8),
            "baseline": {k: round(v, 4) if isinstance(v, float) else v for k, v in baseline.items()},
            "filtered": {k: round(v, 4) if isinstance(v, float) else v for k, v in filtered.items()},
            "delta_mean_r": round(delta_mean, 4),
            "delta_profit_factor": round(delta_pf, 4),
            "drawdown_ratio": round(dd_ratio, 4),
            "retention_pct": round(len(filtered_r) / len(test) * 100.0, 2),
            "passed": passed,
        })

    if len(fold_rows) < 3:
        return None
    positive = sum(1 for f in fold_rows if f["passed"])
    positive_pct = positive / len(fold_rows) * 100.0
    mean_delta = fmean(float(f["delta_mean_r"]) for f in fold_rows)
    mean_pf_delta = fmean(float(f["delta_profit_factor"]) for f in fold_rows)
    mean_dd_ratio = fmean(float(f["drawdown_ratio"]) for f in fold_rows)
    mean_retention = fmean(float(f["retention_pct"]) for f in fold_rows)
    filtered_means = [float(f["filtered"]["mean_r"]) for f in fold_rows]
    baseline_means = [float(f["baseline"]["mean_r"]) for f in fold_rows]

    eligible = (
        positive_pct >= 67.0
        and mean_delta >= 0.08
        and fmean(filtered_means) > 0.10
        and mean_pf_delta > 0
        and mean_dd_ratio <= 1.10
        and mean_retention >= 25.0
    )
    score = min(100.0, max(0.0,
        positive_pct * 0.35
        + min(30.0, max(0.0, mean_delta) * 100.0)
        + min(20.0, max(0.0, mean_pf_delta) * 15.0)
        + max(0.0, 15.0 * (1.10 - min(1.10, mean_dd_ratio)) / 1.10)
    ))
    return {
        "feature": feature,
        "family": _family(feature),
        "source": _source(feature),
        "folds": len(fold_rows),
        "positive_folds": positive,
        "positive_fold_pct": round(positive_pct, 1),
        "mean_delta_r": round(mean_delta, 4),
        "mean_delta_profit_factor": round(mean_pf_delta, 4),
        "mean_drawdown_ratio": round(mean_dd_ratio, 4),
        "mean_retention_pct": round(mean_retention, 1),
        "baseline_mean_r": round(fmean(baseline_means), 4),
        "filtered_mean_r": round(fmean(filtered_means), 4),
        "walkforward_score": round(score, 2),
        "eligible_for_shadow_trial": eligible,
        "fold_details": fold_rows,
    }


def incremental_walkforward(samples: list[dict[str, Any]], max_features: int = 250) -> dict[str, Any]:
    """Expanding-window baseline-vs-feature filter test. Does not change MASTER weights."""
    rows = _prepare(samples)
    if len(rows) < MIN_TOTAL:
        return {
            "status": "INSUFFICIENT_DATA",
            "samples": len(rows),
            "minimum_samples": MIN_TOTAL,
            "features_evaluated": 0,
            "eligible_count": 0,
            "eligible": [],
            "diversified_top": [],
            "auto_apply": False,
            "mode": "RESEARCH_ONLY",
        }

    availability: dict[str, int] = {}
    for row in rows:
        for name in row["values"]:
            availability[name] = availability.get(name, 0) + 1
    candidates = [
        name for name, count in availability.items()
        if count >= int(len(rows) * 0.65)
    ]
    # Deterministic cap: highest-coverage features first, then name.
    candidates = sorted(candidates, key=lambda n: (-availability[n], n))[:max_features]

    evaluated: list[dict[str, Any]] = []
    for feature in candidates:
        result = _evaluate_feature(rows, feature)
        if result:
            result["availability_pct"] = round(availability[feature] / len(rows) * 100.0, 1)
            evaluated.append(result)

    ranked = sorted(evaluated, key=lambda r: (r["eligible_for_shadow_trial"], r["walkforward_score"]), reverse=True)
    eligible = [r for r in ranked if r["eligible_for_shadow_trial"]]
    best_by_family: dict[str, dict[str, Any]] = {}
    for row in eligible:
        family = row["family"]
        if family not in best_by_family or row["walkforward_score"] > best_by_family[family]["walkforward_score"]:
            best_by_family[family] = row
    diversified = sorted(best_by_family.values(), key=lambda r: r["walkforward_score"], reverse=True)[:20]

    source_summary: dict[str, dict[str, int]] = {}
    for row in evaluated:
        src = row["source"]
        source_summary.setdefault(src, {"evaluated": 0, "eligible": 0})
        source_summary[src]["evaluated"] += 1
        if row["eligible_for_shadow_trial"]:
            source_summary[src]["eligible"] += 1

    return {
        "status": "SHADOW_TRIAL_CANDIDATES" if diversified else "NO_STABLE_INCREMENTAL_EDGE_YET",
        "samples": len(rows),
        "fold_scheme": f"EXPANDING_TRAIN + {TEST_BLOCK}-TRADE FORWARD BLOCKS",
        "baseline": "all feature-available trades in each forward block",
        "variant": "same trades filtered by train-derived feature median/orientation",
        "features_evaluated": len(evaluated),
        "eligible_count": len(eligible),
        "source_summary": source_summary,
        "eligible": eligible[:50],
        "diversified_top": diversified,
        "auto_apply": False,
        "mode": "RESEARCH_ONLY",
        "next_stage": "Eligible features may enter a bounded SHADOW score only; MASTER weight remains unchanged until a full engine replay confirms improvement.",
    }

from __future__ import annotations

import math
from statistics import fmean, median
from typing import Any

from .edge_lab import _flatten_selected, _is_directional

MIN_TOTAL = 80
MIN_FOLD_TEST = 10
DEFAULT_FOLDS = 4


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _profit_factor(rs: list[float]) -> float:
    wins = sum(x for x in rs if x > 0)
    losses = abs(sum(x for x in rs if x < 0))
    if losses <= 1e-12:
        return 999.0 if wins > 0 else 0.0
    return wins / losses


def _max_drawdown_r(rs: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in rs:
        equity += r
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _prepare(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(samples, key=lambda s: (str(s.get("opened_at", "")), int(s.get("trade_id", 0))))
    out: list[dict[str, Any]] = []
    for sample in ordered:
        risk = _finite(sample.get("risk_budget")) or 0.0
        pnl = _finite(sample.get("realized_pnl")) or 0.0
        if risk <= 0:
            continue
        sign = 1.0 if sample.get("direction") == "LONG" else -1.0
        raw = _flatten_selected(sample.get("features") or {})
        aligned = {name: value * sign if _is_directional(name) else value for name, value in raw.items()}
        out.append({
            "r": pnl / risk,
            "values": aligned,
            "regime": sample.get("market_regime") or "UNKNOWN",
            "brain": sample.get("brain"),
        })
    return out


def _fold_boundaries(n: int, folds: int) -> list[tuple[int, int, int]]:
    if n < MIN_TOTAL:
        return []
    folds = max(2, min(folds, 6))
    first_train = max(40, int(n * 0.45))
    remaining = n - first_train
    test_size = max(MIN_FOLD_TEST, remaining // folds)
    boundaries: list[tuple[int, int, int]] = []
    train_end = first_train
    while train_end + MIN_FOLD_TEST <= n and len(boundaries) < folds:
        test_end = min(n, train_end + test_size)
        if test_end - train_end < MIN_FOLD_TEST:
            break
        boundaries.append((0, train_end, test_end))
        train_end = test_end
    return boundaries


def validate_feature_incremental(
    samples: list[dict[str, Any]],
    feature_names: list[str],
    folds: int = DEFAULT_FOLDS,
) -> dict[str, Any]:
    """Expanding-window baseline-vs-filter validation.

    The feature is not allowed to alter trade sizing or direction here. It is only
    tested as an additional selection filter on chronologically later trades.
    This isolates whether it adds incremental selection value over the baseline.
    """
    prepared = _prepare(samples)
    boundaries = _fold_boundaries(len(prepared), folds)
    if len(boundaries) < 2:
        return {
            "status": "INSUFFICIENT_DATA",
            "samples": len(prepared),
            "minimum_samples": MIN_TOTAL,
            "folds": 0,
            "auto_promotion_enabled": False,
            "features": [],
        }

    reports: list[dict[str, Any]] = []
    for feature in feature_names:
        fold_rows: list[dict[str, Any]] = []
        for _start, train_end, test_end in boundaries:
            train = [r for r in prepared[:train_end] if feature in r["values"]]
            test = [r for r in prepared[train_end:test_end] if feature in r["values"]]
            if len(train) < 30 or len(test) < MIN_FOLD_TEST:
                continue

            # Learn only from the train window. Orientation is the sign of the
            # difference between upper/lower halves of realized R.
            threshold = median(r["values"][feature] for r in train)
            high_train = [r["r"] for r in train if r["values"][feature] >= threshold]
            low_train = [r["r"] for r in train if r["values"][feature] < threshold]
            if not high_train or not low_train:
                continue
            orientation = 1.0 if fmean(high_train) >= fmean(low_train) else -1.0

            baseline_r = [r["r"] for r in test]
            selected = [
                r for r in test
                if (r["values"][feature] - threshold) * orientation >= 0
            ]
            selected_r = [r["r"] for r in selected]
            if len(selected_r) < max(3, int(len(test) * 0.20)):
                continue

            base_mean = fmean(baseline_r)
            sel_mean = fmean(selected_r)
            base_pf = _profit_factor(baseline_r)
            sel_pf = _profit_factor(selected_r)
            base_dd = _max_drawdown_r(baseline_r)
            sel_dd = _max_drawdown_r(selected_r)
            fold_rows.append({
                "train_end": train_end,
                "test_end": test_end,
                "test_trades": len(test),
                "selected_trades": len(selected),
                "retention_pct": round(len(selected) / len(test) * 100.0, 2),
                "threshold": round(float(threshold), 8),
                "orientation": "HIGHER_BETTER" if orientation > 0 else "LOWER_BETTER",
                "baseline_mean_r": round(base_mean, 4),
                "selected_mean_r": round(sel_mean, 4),
                "delta_mean_r": round(sel_mean - base_mean, 4),
                "baseline_pf": round(base_pf, 3),
                "selected_pf": round(sel_pf, 3),
                "delta_pf": round(sel_pf - base_pf, 3) if base_pf < 900 and sel_pf < 900 else None,
                "baseline_max_dd_r": round(base_dd, 3),
                "selected_max_dd_r": round(sel_dd, 3),
                "delta_max_dd_r": round(sel_dd - base_dd, 3),
            })

        if len(fold_rows) < 2:
            continue
        delta_rs = [row["delta_mean_r"] for row in fold_rows]
        dd_deltas = [row["delta_max_dd_r"] for row in fold_rows]
        positive_folds = sum(1 for x in delta_rs if x > 0)
        stable_pct = positive_folds / len(delta_rs) * 100.0
        avg_delta_r = fmean(delta_rs)
        avg_dd_delta = fmean(dd_deltas)
        avg_retention = fmean(row["retention_pct"] for row in fold_rows)
        pf_deltas = [row["delta_pf"] for row in fold_rows if row["delta_pf"] is not None]
        avg_pf_delta = fmean(pf_deltas) if pf_deltas else 0.0

        candidate = (
            len(fold_rows) >= 3
            and stable_pct >= 66.0
            and avg_delta_r >= 0.08
            and avg_retention >= 25.0
            and avg_dd_delta <= 0.35
        )
        status = "PROMOTION_CANDIDATE" if candidate else ("WATCH" if avg_delta_r > 0 and stable_pct >= 50 else "REJECT")
        score = max(0.0, min(100.0,
            max(0.0, avg_delta_r) / 0.30 * 45.0
            + stable_pct / 100.0 * 30.0
            + max(0.0, min(1.0, avg_retention / 50.0)) * 15.0
            + max(0.0, min(1.0, (0.35 - avg_dd_delta) / 0.35)) * 10.0
        ))
        reports.append({
            "feature": feature,
            "status": status,
            "folds": len(fold_rows),
            "positive_fold_pct": round(stable_pct, 1),
            "avg_delta_mean_r": round(avg_delta_r, 4),
            "avg_delta_pf": round(avg_pf_delta, 3),
            "avg_delta_max_dd_r": round(avg_dd_delta, 3),
            "avg_retention_pct": round(avg_retention, 2),
            "incremental_score": round(score, 2),
            "fold_results": fold_rows,
        })

    reports.sort(key=lambda r: (r["status"] == "PROMOTION_CANDIDATE", r["incremental_score"]), reverse=True)
    candidates = [r for r in reports if r["status"] == "PROMOTION_CANDIDATE"]
    return {
        "status": "READY" if reports else "INSUFFICIENT_FEATURE_COVERAGE",
        "samples": len(prepared),
        "folds_available": len(boundaries),
        "method": "EXPANDING_WINDOW_BASELINE_VS_FEATURE_FILTER",
        "features_tested": len(reports),
        "promotion_candidates": len(candidates),
        "features": reports[:30],
        "auto_promotion_enabled": False,
        "promotion_policy": "A promotion candidate still needs paper/shadow confirmation before any bounded MASTER weight is enabled.",
    }


def run_incremental_lab(samples: list[dict[str, Any]], edge_report: dict[str, Any], max_features: int = 12) -> dict[str, Any]:
    names = [str(row.get("feature")) for row in (edge_report.get("diversified_top") or []) if row.get("feature")]
    return validate_feature_incremental(samples, names[:max_features])

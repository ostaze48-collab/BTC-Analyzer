from __future__ import annotations

import math
from statistics import fmean
from typing import Any

MIN_TRAIN = 30
MIN_TEST = 15


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3 or len(xs) != len(ys):
        return 0.0
    mx, my = fmean(xs), fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denx = math.sqrt(sum(x * x for x in dx))
    deny = math.sqrt(sum(y * y for y in dy))
    if denx <= 1e-12 or deny <= 1e-12:
        return 0.0
    return sum(a * b for a, b in zip(dx, dy)) / (denx * deny)


def _spread(xs: list[float], ys: list[float], orientation: float) -> float:
    if len(xs) < 8:
        return 0.0
    rows = sorted(zip(xs, ys), key=lambda z: z[0])
    n = max(2, len(rows) // 4)
    low = fmean(y for _, y in rows[:n])
    high = fmean(y for _, y in rows[-n:])
    return (high - low) * orientation


def _metrics(analog: dict[str, Any]) -> dict[str, float]:
    fields = (
        "avg_similarity_pct", "stop_before_1r_pct",
        "hit_1r_pct", "hit_2r_pct", "hit_3r_pct", "hit_4r_pct", "hit_5r_pct",
        "avg_mfe_r", "avg_mae_r", "matches",
    )
    out: dict[str, float] = {}
    for key in fields:
        value = _finite(analog.get(key))
        if value is not None:
            out[key] = value
    return out


def validate_historical_analogs(samples: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(samples, key=lambda s: (str(s.get("opened_at", "")), int(s.get("trade_id", 0))))
    prepared: list[dict[str, Any]] = []
    for sample in ordered:
        risk = _finite(sample.get("risk_budget")) or 0.0
        if risk <= 0:
            continue
        features = sample.get("features") or {}
        analog = features.get("historical_analogs") or {}
        if analog.get("status") != "READY":
            continue
        vals = _metrics(analog)
        if not vals:
            continue
        pnl = _finite(sample.get("realized_pnl")) or 0.0
        prepared.append({"r": pnl / risk, "values": vals})

    total = len(prepared)
    if total < MIN_TRAIN + MIN_TEST:
        return {
            "status": "INSUFFICIENT_DATA",
            "samples": total,
            "minimum_samples": MIN_TRAIN + MIN_TEST,
            "useful": False,
            "weight_in_master": 0.0,
            "metrics": [],
            "message": "Need more closed paper trades that had READY historical analog evidence.",
        }

    cutoff = max(MIN_TRAIN, min(total - MIN_TEST, int(total * 0.70)))
    names = sorted({name for row in prepared for name in row["values"]})
    results: list[dict[str, Any]] = []
    naturally_negative = {"stop_before_1r_pct", "avg_mae_r"}

    for name in names:
        train = [(r["values"][name], r["r"]) for r in prepared[:cutoff] if name in r["values"]]
        test = [(r["values"][name], r["r"]) for r in prepared[cutoff:] if name in r["values"]]
        if len(train) < MIN_TRAIN or len(test) < MIN_TEST:
            continue
        tx, ty = [x for x, _ in train], [y for _, y in train]
        vx, vy = [x for x, _ in test], [y for _, y in test]
        train_corr = _pearson(tx, ty)
        test_corr = _pearson(vx, vy)
        expected_orientation = -1.0 if name in naturally_negative else 1.0
        oriented_test_corr = test_corr * expected_orientation
        spread = _spread(vx, vy, expected_orientation)
        consistent = train_corr * expected_orientation > 0 and oriented_test_corr > 0
        useful = consistent and oriented_test_corr >= 0.05 and spread >= 0.10
        score = max(0.0, min(100.0, max(0.0, oriented_test_corr) * 55.0 + min(1.0, max(0.0, spread) / 0.50) * 45.0))
        results.append({
            "metric": name,
            "train_corr": round(train_corr, 4),
            "test_corr": round(test_corr, 4),
            "oos_oriented_corr": round(oriented_test_corr, 4),
            "oos_quartile_spread_r": round(spread, 4),
            "useful": useful,
            "score": round(score, 2),
        })

    results.sort(key=lambda r: (r["useful"], r["score"]), reverse=True)
    useful_rows = [r for r in results if r["useful"]]
    if len(useful_rows) >= 2:
        status = "USEFUL_OOS_EVIDENCE"
    elif useful_rows:
        status = "MIXED_EVIDENCE"
    else:
        status = "NOT_PROVEN_USEFUL"

    return {
        "status": status,
        "samples": total,
        "train_samples": cutoff,
        "test_samples": total - cutoff,
        "useful": len(useful_rows) >= 2,
        "useful_metric_count": len(useful_rows),
        "metrics": results,
        "weight_in_master": 0.0,
        "auto_apply": False,
        "next_stage": "Only after stable OOS usefulness and full engine replay may historical evidence receive a small bounded MASTER weight.",
    }

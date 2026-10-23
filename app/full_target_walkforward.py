from __future__ import annotations

import math
from statistics import fmean
from typing import Any

from .brains import PROFILES, analyze_brains, layer_context
from .historical_analogs import (
    _HORIZON_BY_BRAIN,
    _quick_context,
    _signature,
    _similarity,
    _safe_float,
    _evaluate_path,
)
from .master import select_trade
from .risk_engine import _target_r
from .target_advisor import build_historical_target_advisor

MIN_PRIOR = 30
MAX_LOCAL_MATCHES = 24
MIN_VALIDATION = 30
HOLDOUT_FRACTION = 0.30

ANCHOR_BY_BRAIN = {p.name: p.anchor for p in PROFILES}


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


def simulate_partial_policy(
    future: list[dict[str, Any]],
    direction: str,
    entry: float,
    risk_pct: float,
    target_r: float,
) -> float:
    """Resolve a full future candle path using the system's 30/40/30 exits.

    Initial stop has precedence over targets within a candle. Stop upgrades caused
    by a target become effective from the next candle; this is deterministic and
    avoids inventing intrabar ordering after the initial STOP_FIRST rule.
    Any remaining size at horizon expiry is marked to the final close.
    """
    if not future or direction not in ("LONG", "SHORT") or entry <= 0 or risk_pct <= 0:
        return 0.0
    target_r = max(1.0, min(5.0, float(target_r)))
    risk_price = entry * risk_pct / 100.0
    sign = 1.0 if direction == "LONG" else -1.0
    tp1 = min(1.0, target_r)
    tp2 = min(target_r, max(tp1, target_r * 0.60))
    realized = 0.0
    remaining = 1.0
    hit1 = hit2 = False
    stop_r = -1.0

    for candle in future:
        high = _safe_float(candle.get("high"), entry)
        low = _safe_float(candle.get("low"), entry)
        stop_price = entry + sign * risk_price * stop_r
        stop_hit = low <= stop_price if direction == "LONG" else high >= stop_price
        if stop_hit:
            return round(realized + remaining * stop_r, 4)

        favorable_r = (high - entry) / risk_price if direction == "LONG" else (entry - low) / risk_price
        if not hit1 and favorable_r >= tp1:
            realized += 0.30 * tp1
            remaining -= 0.30
            hit1 = True
        if not hit2 and favorable_r >= tp2:
            # If target_r is exactly 1R, TP1/TP2/TP3 collapse to the same level;
            # process all partials and finish at target.
            realized += 0.40 * tp2
            remaining -= 0.40
            hit2 = True
        if favorable_r >= target_r:
            realized += remaining * target_r
            return round(realized, 4)

        if hit2:
            stop_r = tp1
        elif hit1:
            stop_r = 0.0

    last_close = _safe_float(future[-1].get("close"), entry)
    final_r = sign * (last_close - entry) / risk_price
    final_r = max(stop_r, min(target_r, final_r))
    return round(realized + remaining * final_r, 4)


def _quality(matches: list[tuple[float, dict[str, Any]]]) -> str:
    if not matches:
        return "WEAK"
    avg = fmean(x[0] for x in matches)
    if len(matches) >= 18 and avg >= 0.70:
        return "STRONG"
    if len(matches) >= 10 and avg >= 0.58:
        return "MODERATE"
    return "WEAK"


def _build_records(history_by_tf: dict[str, list[dict[str, Any]]], brain: str, max_points: int) -> list[dict[str, Any]]:
    anchor_tf = ANCHOR_BY_BRAIN[brain]
    anchor = [c for c in history_by_tf.get(anchor_tf, []) if c.get("closed", True)]
    horizon = _HORIZON_BY_BRAIN.get(brain, 64)
    start = 120
    last_usable = len(anchor) - horizon - 1
    if last_usable <= start:
        return []
    span = max(1, last_usable - start)
    stride = max(1, math.ceil(span / max(1, max_points)))
    records: list[dict[str, Any]] = []

    for idx in range(start, last_usable, stride):
        candle = anchor[idx]
        ts = int(candle.get("close_time", candle.get("time", 0)))
        snaps, layers, regime = _quick_context(history_by_tf, ts)
        proposals = analyze_brains(snaps, cycle=None)
        advisory = select_trade(proposals)
        winner = advisory.get("winner") or {}
        if advisory.get("action") not in ("LONG", "SHORT") or winner.get("brain") != brain:
            continue
        direction = str(winner.get("direction"))
        entry = _safe_float(winner.get("entry"), _safe_float(candle.get("close"), 0.0))
        risk_pct = _safe_float(winner.get("risk_pct"), 0.0)
        if entry <= 0 or risk_pct <= 0:
            continue
        future = anchor[idx + 1: idx + 1 + horizon]
        if len(future) < horizon:
            continue
        anchor_snap = snaps.get(anchor_tf, {})
        if not anchor_snap:
            continue
        outcome = _evaluate_path(future, direction, entry, risk_pct)
        baseline_target = float(_target_r(winner, regime))
        baseline_r = simulate_partial_policy(future, direction, entry, risk_pct, baseline_target)
        policy_by_int = {
            float(r): simulate_partial_policy(future, direction, entry, risk_pct, float(r))
            for r in range(1, 6)
        }
        records.append({
            "time": ts,
            "brain": brain,
            "direction": direction,
            "regime": regime.get("regime", "UNKNOWN"),
            "signature": _signature(anchor_snap, layers, regime),
            "outcome": outcome,
            "baseline_target_r": round(baseline_target, 3),
            "baseline_policy_r": baseline_r,
            "policy_by_int": policy_by_int,
            "final_score": round(_safe_float(winner.get("final_score")), 2),
            "safety_score": round(_safe_float(winner.get("safety_score")), 2),
        })
    return records


def run_full_target_walkforward(
    history_by_tf: dict[str, list[dict[str, Any]]],
    brain: str,
    max_points: int = 300,
) -> dict[str, Any]:
    """Expanding-window local-analog target validation on full candle paths.

    At each validation point the local target is selected using ONLY earlier
    engine-selected records. The current point's future path is consulted only
    after the target choice is frozen. This is target-policy OOS research, not a
    full execution backtest and never changes live/paper targets automatically.
    """
    brain = str(brain).upper()
    if brain not in ANCHOR_BY_BRAIN:
        raise ValueError("brain must be SCALP, INTRADAY or SWING")
    records = _build_records(history_by_tf, brain, max(80, min(int(max_points), 600)))
    if len(records) <= MIN_PRIOR:
        return {
            "status": "INSUFFICIENT_ENGINE_SELECTED_POINTS",
            "brain": brain,
            "records": len(records),
            "minimum_prior": MIN_PRIOR,
            "mode": "FULL_ARCHIVE_TARGET_WALKFORWARD",
            "auto_apply": False,
            "weight_in_risk_engine": 0.0,
        }

    rows: list[dict[str, Any]] = []
    overrides = 0
    for i in range(MIN_PRIOR, len(records)):
        current = records[i]
        prior = [r for r in records[:i] if r["direction"] == current["direction"]]
        if len(prior) < 12:
            continue
        ranked = sorted(
            ((_similarity(current["signature"], p["signature"]), p) for p in prior),
            key=lambda x: x[0], reverse=True,
        )[:MAX_LOCAL_MATCHES]
        local = [p for sim, p in ranked if sim >= 0.50]
        if len(local) < 8:
            local = [p for _sim, p in ranked[:12]]
        quality = _quality([(sim, p) for sim, p in ranked if p in local])
        advisor = build_historical_target_advisor([p["outcome"] for p in local], quality=quality)
        recommended = advisor.get("recommended_r")
        baseline_target = float(current["baseline_target_r"])
        advisor_target = float(recommended) if recommended is not None else baseline_target
        if abs(advisor_target - baseline_target) > 1e-9:
            overrides += 1
        if advisor_target in current["policy_by_int"]:
            advisor_r = float(current["policy_by_int"][advisor_target])
        else:
            # Current baseline can be fractional (e.g. 2.5R); local advisor emits integers.
            advisor_r = float(current["baseline_policy_r"])
        rows.append({
            "time": current["time"],
            "direction": current["direction"],
            "regime": current["regime"],
            "baseline_target_r": baseline_target,
            "advisor_target_r": advisor_target,
            "baseline_r": float(current["baseline_policy_r"]),
            "advisor_r": advisor_r,
            "delta_r": round(advisor_r - float(current["baseline_policy_r"]), 4),
            "local_matches": len(local),
            "local_quality": quality,
            "avg_similarity_pct": round(fmean(sim for sim, _p in ranked[:len(local)]) * 100.0, 2) if local else 0.0,
        })

    if not rows:
        return {
            "status": "INSUFFICIENT_VALIDATION_ROWS", "brain": brain, "records": len(records),
            "mode": "FULL_ARCHIVE_TARGET_WALKFORWARD", "auto_apply": False, "weight_in_risk_engine": 0.0,
        }

    baseline_values = [r["baseline_r"] for r in rows]
    advisor_values = [r["advisor_r"] for r in rows]
    baseline = _metrics(baseline_values)
    advisor = _metrics(advisor_values)
    holdout_n = max(10, int(len(rows) * HOLDOUT_FRACTION)) if rows else 0
    holdout_n = min(holdout_n, len(rows))
    holdout = rows[-holdout_n:] if holdout_n else []
    hb = _metrics([r["baseline_r"] for r in holdout])
    ha = _metrics([r["advisor_r"] for r in holdout])
    delta = float(advisor["mean_r"]) - float(baseline["mean_r"])
    hdelta = float(ha["mean_r"]) - float(hb["mean_r"])
    dd_ratio = float(advisor["max_drawdown_r"]) / float(baseline["max_drawdown_r"]) if float(baseline["max_drawdown_r"]) > 1e-12 else 0.0
    hdd_ratio = float(ha["max_drawdown_r"]) / float(hb["max_drawdown_r"]) if float(hb["max_drawdown_r"]) > 1e-12 else 0.0
    override_rate = overrides / len(rows) * 100.0

    enough = len(rows) >= MIN_VALIDATION and len(holdout) >= 10 and overrides >= 10
    passes = (
        enough and delta >= 0.05 and hdelta >= 0.05
        and float(advisor["profit_factor"]) >= float(baseline["profit_factor"])
        and float(ha["profit_factor"]) >= float(hb["profit_factor"])
        and dd_ratio <= 1.10 and hdd_ratio <= 1.10
    )
    status = "FULL_WALKFORWARD_OUTPERFORMS" if passes else ("NO_FULL_WALKFORWARD_EDGE" if enough else "INSUFFICIENT_POLICY_OVERRIDES")

    regimes: dict[str, dict[str, Any]] = {}
    for name in sorted({r["regime"] for r in rows}):
        subset = [r for r in rows if r["regime"] == name]
        if len(subset) < 5:
            continue
        b = _metrics([r["baseline_r"] for r in subset])
        a = _metrics([r["advisor_r"] for r in subset])
        regimes[name] = {
            "trades": len(subset), "baseline_mean_r": b["mean_r"], "advisor_mean_r": a["mean_r"],
            "delta_mean_r": round(float(a["mean_r"]) - float(b["mean_r"]), 4),
        }

    return {
        "status": status,
        "brain": brain,
        "anchor": ANCHOR_BY_BRAIN[brain],
        "mode": "FULL_ARCHIVE_TARGET_WALKFORWARD",
        "no_lookahead": True,
        "auto_apply": False,
        "weight_in_risk_engine": 0.0,
        "engine_selected_records": len(records),
        "validation_rows": len(rows),
        "advisor_overrides": overrides,
        "override_rate_pct": round(override_rate, 2),
        "baseline": baseline,
        "advisor": advisor,
        "delta_mean_r": round(delta, 4),
        "drawdown_ratio": round(dd_ratio, 4),
        "holdout": {
            "rows": len(holdout), "baseline": hb, "advisor": ha,
            "delta_mean_r": round(hdelta, 4), "drawdown_ratio": round(hdd_ratio, 4),
        },
        "by_regime": regimes,
        "recent_rows": rows[-20:],
        "policy": "Target choice at each point uses prior records only. Current future candles are evaluated only after the target is frozen.",
        "next_stage": "If stable across brains/regimes, record advisor targets in live Shadow mode before any bounded execution influence.",
    }

from __future__ import annotations

import math
from statistics import fmean
from typing import Any

MIN_TRAIN = 30
MIN_TEST = 15
TRAIN_FRACTION = 0.70

_DIRECTIONAL_PREFIXES = (
    "ret_", "momentum_", "sma_dist_", "ema_dist_", "rsi_", "zscore_",
    "donchian_pos_", "stoch_", "williams_r_", "cci_", "cmf_", "obv_slope_",
    "body_frac_", "close_location_",
)

_SKIP_NUMERIC_KEYS = {
    "weight_in_master", "refreshed_at_unix", "next_funding_time", "sample_count",
    "feature_count", "count", "time", "timestamp", "current_hashrate", "current_difficulty",
    "mark_price", "index_price", "current", "notional", "margin_used", "risk_budget",
}


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
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


def _quartile_spread(xs: list[float], ys: list[float], orientation: float = 1.0) -> float:
    if len(xs) < 8:
        return 0.0
    rows = sorted(zip(xs, ys), key=lambda z: z[0])
    n = max(2, len(rows) // 4)
    low = fmean(y for _, y in rows[:n])
    high = fmean(y for _, y in rows[-n:])
    return (high - low) * orientation


def _flatten_selected(payload: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}

    background = payload.get("background_features") or {}
    for tf, features in background.items():
        if not isinstance(features, dict):
            continue
        for name, value in features.items():
            x = _finite(value)
            if x is not None:
                out[f"tf.{tf}.{name}"] = x

    cycle = payload.get("cycle_models") or {}
    for key in ("bias", "strength"):
        x = _finite(cycle.get(key))
        if x is not None:
            out[f"cycle.{key}"] = x

    network = payload.get("network_intelligence") or {}
    nshadow = network.get("shadow") or {}
    x = _finite(nshadow.get("bias"))
    if x is not None:
        out["network.shadow_bias"] = x
    for name, value in (nshadow.get("components") or {}).items():
        x = _finite(value)
        if x is not None:
            out[f"network.{name}"] = x

    derivatives = payload.get("derivatives_intelligence") or {}
    dshadow = derivatives.get("shadow") or {}
    x = _finite(dshadow.get("bias"))
    if x is not None:
        out["derivatives.shadow_bias"] = x
    for name, value in (dshadow.get("components") or {}).items():
        x = _finite(value)
        if x is not None:
            out[f"derivatives.{name}"] = x

    fields = {
        "derivatives.funding": ((derivatives.get("premium") or {}).get("current_funding_rate")),
        "derivatives.avg_funding": ((derivatives.get("premium") or {}).get("avg_recent_funding_rate")),
        "derivatives.basis_bps": ((derivatives.get("premium") or {}).get("basis_bps")),
        "derivatives.oi_change_pct": ((derivatives.get("open_interest") or {}).get("history_change_pct")),
        "derivatives.global_ls": ((derivatives.get("positioning") or {}).get("global_long_short_ratio")),
        "derivatives.top_account_ls": ((derivatives.get("positioning") or {}).get("top_account_long_short_ratio")),
        "derivatives.top_position_ls": ((derivatives.get("positioning") or {}).get("top_position_long_short_ratio")),
        "derivatives.taker_ratio": ((derivatives.get("flow") or {}).get("taker_buy_sell_ratio")),
    }
    for name, value in fields.items():
        x = _finite(value)
        if x is not None:
            out[name] = x

    # Historical-analog evidence is already direction-specific because the path
    # is evaluated in the candidate LONG/SHORT direction. Keep it non-directional
    # here and validate whether stronger historical outcomes actually add OOS edge.
    analog = payload.get("historical_analogs") or {}
    analog_fields = {
        "avg_similarity_pct": analog.get("avg_similarity_pct"),
        "stop_before_1r_pct": analog.get("stop_before_1r_pct"),
        "avg_mfe_r": analog.get("avg_mfe_r"),
        "avg_mae_r": analog.get("avg_mae_r"),
        "hit_1r_pct": analog.get("hit_1r_pct"),
        "hit_2r_pct": analog.get("hit_2r_pct"),
        "hit_3r_pct": analog.get("hit_3r_pct"),
        "hit_4r_pct": analog.get("hit_4r_pct"),
        "hit_5r_pct": analog.get("hit_5r_pct"),
    }
    for name, value in analog_fields.items():
        x = _finite(value)
        if x is not None:
            out[f"analog.{name}"] = x

    return out


def _is_directional(path: str) -> bool:
    leaf = path.split(".")[-1]
    if path.startswith("analog."):
        return False
    if path.startswith(("network.", "derivatives.", "cycle.")):
        return path not in {"derivatives.oi_change_pct"}
    return leaf.startswith(_DIRECTIONAL_PREFIXES)


def _family(path: str) -> str:
    parts = path.split(".")
    if path.startswith("analog."):
        leaf = parts[-1]
        if leaf.startswith("hit_"):
            return "analog:target_reach"
        if leaf in ("avg_mfe_r", "avg_mae_r", "stop_before_1r_pct"):
            return "analog:path_risk"
        return "analog:similarity"
    if len(parts) >= 3 and parts[0] == "tf":
        leaf = parts[-1]
        family = leaf.split("_")[0]
        if leaf.startswith("sma_dist_"):
            family = "sma"
        elif leaf.startswith("ema_dist_"):
            family = "ema"
        elif leaf.startswith("donchian_pos_"):
            family = "donchian"
        elif leaf.startswith("realized_vol_"):
            family = "realized_vol"
        elif leaf.startswith("volume_ratio_"):
            family = "volume"
        elif leaf.startswith("obv_slope_"):
            family = "obv"
        elif leaf.startswith("body_frac_"):
            family = "body"
        elif leaf.startswith("close_location_"):
            family = "close_location"
        return f"{parts[1]}:{family}"
    return ":".join(parts[:2])


def _source(path: str) -> str:
    if path.startswith("analog."):
        return "ANALOG_SHADOW"
    if path.startswith("tf."):
        return "TECHNICAL"
    if path.startswith("network."):
        return "NETWORK_SHADOW"
    if path.startswith("derivatives."):
        return "DERIVATIVES_SHADOW"
    if path.startswith("cycle."):
        return "CYCLE"
    return "OTHER"


def analyze_feature_edge(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Chronological train/test feature audit. Never auto-promotes a feature."""
    ordered = sorted(samples, key=lambda s: (str(s.get("opened_at", "")), int(s.get("trade_id", 0))))
    total = len(ordered)
    if total < MIN_TRAIN + MIN_TEST:
        return {
            "status": "INSUFFICIENT_DATA",
            "samples": total,
            "minimum_samples": MIN_TRAIN + MIN_TEST,
            "auto_promotion_enabled": False,
            "candidates": [], "diversified_top": [], "features_tested": 0,
            "message": "Need more chronologically separated closed trades before judging feature edge.",
        }

    cutoff = max(MIN_TRAIN, min(total - MIN_TEST, int(total * TRAIN_FRACTION)))
    prepared: list[dict[str, Any]] = []
    feature_names: set[str] = set()
    for idx, sample in enumerate(ordered):
        risk = _finite(sample.get("risk_budget")) or 0.0
        pnl = _finite(sample.get("realized_pnl")) or 0.0
        if risk <= 0:
            continue
        direction_sign = 1.0 if sample.get("direction") == "LONG" else -1.0
        values = _flatten_selected(sample.get("features") or {})
        aligned: dict[str, float] = {}
        for name, value in values.items():
            aligned[name] = value * direction_sign if _is_directional(name) else value
        feature_names.update(aligned)
        prepared.append({
            "split": "TRAIN" if idx < cutoff else "TEST",
            "r": pnl / risk,
            "values": aligned,
            "brain": sample.get("brain"),
            "regime": sample.get("market_regime") or "UNKNOWN",
        })

    rows: list[dict[str, Any]] = []
    for name in sorted(feature_names):
        train = [(r["values"][name], r["r"]) for r in prepared if r["split"] == "TRAIN" and name in r["values"]]
        test = [(r["values"][name], r["r"]) for r in prepared if r["split"] == "TEST" and name in r["values"]]
        if len(train) < MIN_TRAIN or len(test) < MIN_TEST:
            continue
        train_x, train_y = [x for x, _ in train], [y for _, y in train]
        test_x, test_y = [x for x, _ in test], [y for _, y in test]
        train_corr = _pearson(train_x, train_y)
        test_corr = _pearson(test_x, test_y)
        orientation = 1.0 if train_corr >= 0 else -1.0
        test_spread = _quartile_spread(test_x, test_y, orientation)
        same_sign = train_corr == 0 or test_corr == 0 or (train_corr > 0) == (test_corr > 0)

        regime_edges: dict[str, float] = {}
        for regime in sorted({r["regime"] for r in prepared if r["split"] == "TEST"}):
            subset = [(r["values"][name], r["r"]) for r in prepared if r["split"] == "TEST" and r["regime"] == regime and name in r["values"]]
            if len(subset) >= 8:
                regime_edges[regime] = _quartile_spread([x for x, _ in subset], [y for _, y in subset], orientation)
        stable_regimes = sum(1 for v in regime_edges.values() if v > 0)
        regime_stability = stable_regimes / len(regime_edges) if regime_edges else 0.0

        candidate = (
            same_sign
            and abs(train_corr) >= 0.08
            and abs(test_corr) >= 0.04
            and test_spread >= 0.15
            and len(test) >= MIN_TEST
        )
        watch = same_sign and test_spread > 0 and abs(test_corr) > 0
        status = "CANDIDATE" if candidate else ("WATCH" if watch else "REJECT")
        edge_score = min(100.0, (
            abs(test_corr) * 45.0
            + min(1.0, max(0.0, test_spread) / 0.75) * 40.0
            + regime_stability * 15.0
        ))
        rows.append({
            "feature": name,
            "family": _family(name),
            "source": _source(name),
            "direction_aligned": _is_directional(name),
            "status": status,
            "train_samples": len(train), "test_samples": len(test),
            "train_corr": round(train_corr, 4), "test_corr": round(test_corr, 4),
            "oos_quartile_spread_r": round(test_spread, 4),
            "regime_stability_pct": round(regime_stability * 100, 1),
            "regime_edges": {k: round(v, 4) for k, v in regime_edges.items()},
            "edge_score": round(edge_score, 2),
        })

    ranked = sorted(rows, key=lambda r: (r["status"] == "CANDIDATE", r["edge_score"]), reverse=True)
    candidates = [r for r in ranked if r["status"] == "CANDIDATE"]

    best_by_family: dict[str, dict[str, Any]] = {}
    for row in candidates:
        fam = row["family"]
        if fam not in best_by_family or row["edge_score"] > best_by_family[fam]["edge_score"]:
            best_by_family[fam] = row
    diversified = sorted(best_by_family.values(), key=lambda r: r["edge_score"], reverse=True)[:20]

    source_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        src = row["source"]
        source_counts.setdefault(src, {"tested": 0, "candidates": 0, "watch": 0, "rejected": 0})
        source_counts[src]["tested"] += 1
        if row["status"] == "CANDIDATE":
            source_counts[src]["candidates"] += 1
        elif row["status"] == "WATCH":
            source_counts[src]["watch"] += 1
        else:
            source_counts[src]["rejected"] += 1

    promotion_evidence_ready = total >= 150 and len(diversified) >= 5
    return {
        "status": "EVIDENCE_BUILDING" if not promotion_evidence_ready else "OOS_CANDIDATES_AVAILABLE",
        "samples": total,
        "train_samples": cutoff,
        "test_samples": total - cutoff,
        "split": "CHRONOLOGICAL_70_30",
        "outcome": "realized_R_after_fees",
        "features_tested": len(rows),
        "candidate_count": len(candidates),
        "diversified_candidate_count": len(diversified),
        "source_counts": source_counts,
        "candidates": candidates[:50],
        "diversified_top": diversified,
        "promotion_evidence_ready": promotion_evidence_ready,
        "auto_promotion_enabled": False,
        "promotion_policy": "No feature receives MASTER weight until a separate walk-forward incremental baseline-vs-feature test passes.",
    }

from __future__ import annotations

import math
from statistics import fmean, pstdev
from typing import Any

from .indicators import atr, ema, rsi

PERIODS = (3, 5, 8, 10, 14, 20, 21, 30, 34, 50, 55, 89, 100, 144, 200)
FLOW_PERIODS = (10, 14, 20, 30, 50)


def _sma(values: list[float], period: int) -> float:
    subset = values[-period:]
    return fmean(subset) if subset else 0.0


def _returns(values: list[float], period: int) -> list[float]:
    subset = values[-(period + 1):]
    out: list[float] = []
    for a, b in zip(subset[:-1], subset[1:]):
        if a:
            out.append(b / a - 1.0)
    return out


def _zscore(values: list[float], period: int) -> float:
    subset = values[-period:]
    if len(subset) < 2:
        return 0.0
    sd = pstdev(subset)
    return (values[-1] - fmean(subset)) / sd if sd else 0.0


def _stochastic(candles: list[dict[str, float]], period: int) -> float:
    subset = candles[-period:]
    if not subset:
        return 50.0
    hh = max(float(c["high"]) for c in subset)
    ll = min(float(c["low"]) for c in subset)
    close = float(subset[-1]["close"])
    return 100.0 * (close - ll) / (hh - ll) if hh > ll else 50.0


def _cci(candles: list[dict[str, float]], period: int) -> float:
    subset = candles[-period:]
    if len(subset) < 3:
        return 0.0
    tps = [(float(c["high"]) + float(c["low"]) + float(c["close"])) / 3.0 for c in subset]
    mean = fmean(tps)
    md = fmean(abs(x - mean) for x in tps)
    return (tps[-1] - mean) / (0.015 * md) if md else 0.0


def _cmf(candles: list[dict[str, float]], period: int) -> float:
    subset = candles[-period:]
    mfv = 0.0
    volume = 0.0
    for c in subset:
        h, l, cl, v = map(float, (c["high"], c["low"], c["close"], c["volume"]))
        mult = ((cl - l) - (h - cl)) / (h - l) if h > l else 0.0
        mfv += mult * v
        volume += v
    return mfv / volume if volume else 0.0


def _obv_slope(candles: list[dict[str, float]], period: int) -> float:
    subset = candles[-(period + 1):]
    if len(subset) < 3:
        return 0.0
    obv = 0.0
    series = [0.0]
    for prev, cur in zip(subset[:-1], subset[1:]):
        pc, cc, v = float(prev["close"]), float(cur["close"]), float(cur["volume"])
        obv += v if cc > pc else (-v if cc < pc else 0.0)
        series.append(obv)
    scale = max(1.0, sum(float(c["volume"]) for c in subset[1:]))
    return (series[-1] - series[0]) / scale


def feature_pool(candles: list[dict[str, float]]) -> dict[str, float]:
    """Generate a broad numeric feature pool for research/ML.

    Hundreds of periodized features are generated on dense timeframes. They are
    candidate features, not independent votes. Sparse monthly/yearly frames only
    emit periods they truly contain, preventing duplicated pseudo-information.
    """
    if len(candles) < 8:
        return {}
    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    volumes = [float(c["volume"]) for c in candles]
    close = closes[-1]
    volume_now = volumes[-1]
    out: dict[str, float] = {}

    for p in PERIODS:
        if len(candles) < p:
            continue
        sma = _sma(closes, p)
        em = ema(closes, p)[-1]
        rets = _returns(closes, p)
        ret = close / closes[-p] - 1.0 if p > 1 and closes[-p] else 0.0
        vol = pstdev(rets) * math.sqrt(p) if len(rets) >= 2 else 0.0
        hh, ll = max(highs[-p:]), min(lows[-p:])
        donchian = (close - ll) / (hh - ll) if hh > ll else 0.5
        avg_vol = fmean(volumes[-p:]) if volumes[-p:] else 0.0
        a = atr(candles, p)

        out[f"ret_{p}"] = ret
        out[f"momentum_{p}"] = close - closes[-p]
        out[f"sma_dist_{p}"] = close / sma - 1.0 if sma else 0.0
        out[f"ema_dist_{p}"] = close / em - 1.0 if em else 0.0
        out[f"rsi_{p}"] = rsi(closes, max(2, min(p, len(closes) - 1))) / 100.0 - 0.5
        out[f"atr_pct_{p}"] = a / close if close else 0.0
        out[f"realized_vol_{p}"] = vol
        out[f"zscore_{p}"] = _zscore(closes, p)
        out[f"donchian_pos_{p}"] = donchian - 0.5
        out[f"range_pct_{p}"] = (hh - ll) / close if close else 0.0
        out[f"volume_ratio_{p}"] = volume_now / avg_vol - 1.0 if avg_vol else 0.0

    for p in FLOW_PERIODS:
        if len(candles) < p:
            continue
        stoch = _stochastic(candles, p)
        out[f"stoch_{p}"] = stoch / 100.0 - 0.5
        out[f"williams_r_{p}"] = stoch / 100.0 - 0.5
        out[f"cci_{p}"] = max(-4.0, min(4.0, _cci(candles, p) / 100.0))
        out[f"cmf_{p}"] = max(-1.0, min(1.0, _cmf(candles, p)))
        out[f"obv_slope_{p}"] = max(-1.0, min(1.0, _obv_slope(candles, p)))

    for lag in range(1, min(11, len(candles))):
        c = candles[-lag]
        o, h, l, cl = map(float, (c["open"], c["high"], c["low"], c["close"]))
        rng = max(h - l, 1e-12)
        out[f"body_frac_lag{lag}"] = (cl - o) / rng
        out[f"upper_wick_lag{lag}"] = (h - max(o, cl)) / rng
        out[f"lower_wick_lag{lag}"] = (min(o, cl) - l) / rng
        out[f"close_location_lag{lag}"] = (cl - l) / rng - 0.5

    return {k: round(float(v), 8) for k, v in out.items() if math.isfinite(float(v))}


def feature_summary(features: dict[str, float]) -> dict[str, Any]:
    if not features:
        return {"count": 0, "bias": 0.0, "strength": 0.0, "families": {}}

    families: dict[str, list[float]] = {}
    for key, value in features.items():
        family = key.split("_")[0]
        families.setdefault(family, []).append(float(value))

    family_scores: dict[str, float] = {}
    for family, values in families.items():
        bounded = [max(-1.0, min(1.0, v)) for v in values]
        family_scores[family] = fmean(bounded) if bounded else 0.0

    directional_families = [
        "ret", "momentum", "sma", "ema", "rsi", "zscore", "donchian",
        "stoch", "williams", "cci", "cmf", "obv", "body", "close",
    ]
    selected = [family_scores[k] for k in directional_families if k in family_scores]
    bias = fmean(selected) if selected else 0.0
    strength = min(1.0, abs(bias) * 2.5)
    ranked = sorted(family_scores.items(), key=lambda kv: abs(kv[1]), reverse=True)[:8]
    return {
        "count": len(features),
        "bias": round(max(-1.0, min(1.0, bias)), 4),
        "strength": round(strength, 4),
        "families": {k: round(v, 4) for k, v in ranked},
    }

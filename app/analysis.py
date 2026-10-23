from __future__ import annotations

from statistics import fmean
from typing import Any

from .feature_factory import feature_pool, feature_summary
from .indicators import atr, confirmed_pivots, ema, rolling_vwap, rsi, snapshot
from .patterns import candlestick_patterns, classical_patterns, pattern_bias


def _sparse_macro_snapshot(candles: list[dict[str, float]]) -> dict[str, Any]:
    """Fallback for 6M/1Y where BTC cannot have 30-200 historical bars yet."""
    if len(candles) < 8:
        return {}
    closes = [float(c["close"]) for c in candles]
    vols = [float(c["volume"]) for c in candles]
    close = closes[-1]
    p_fast = min(5, len(closes))
    p_mid = min(8, len(closes))
    p_slow = min(13, len(closes))
    e_fast = ema(closes, p_fast)[-1]
    e_mid = ema(closes, p_mid)[-1]
    e_slow = ema(closes, p_slow)[-1]
    a_period = max(2, min(8, len(candles)))
    a = atr(candles, a_period)
    recent = candles[-min(8, len(candles)):]
    support = min(float(c["low"]) for c in recent)
    resistance = max(float(c["high"]) for c in recent)
    prev_vols = vols[:-1][-min(6, max(1, len(vols)-1)):]
    vol_avg = fmean(prev_vols) if prev_vols else max(vols[-1], 1e-9)
    vol_ratio = vols[-1] / vol_avg if vol_avg else 1.0
    if close > e_fast > e_mid >= e_slow:
        trend = "BULLISH"
        structure = "BULLISH"
    elif close < e_fast < e_mid <= e_slow:
        trend = "BEARISH"
        structure = "BEARISH"
    else:
        trend = "MIXED"
        structure = "RANGE"
    return {
        "close": close,
        "ema20": e_fast,
        "ema50": e_mid,
        "ema200": e_slow,
        "rsi14": rsi(closes, max(2, min(7, len(closes)-1))),
        "macd": 0.0,
        "macd_signal": 0.0,
        "macd_hist": (e_fast - e_mid) / close if close else 0.0,
        "atr14": a,
        "vwap20": rolling_vwap(candles, min(8, len(candles))),
        "volume_ratio": vol_ratio,
        "support": support,
        "resistance": resistance,
        "structure": structure,
        "trend": trend,
        "volatility_pct": (a / close * 100) if close else 0.0,
        "swing_high": resistance,
        "swing_high_time": int(max(recent, key=lambda c: float(c["high"]))["time"]),
        "swing_low": support,
        "swing_low_time": int(min(recent, key=lambda c: float(c["low"]))["time"]),
        "structure_event": None,
        "fvg_zones": [],
        "order_block": None,
        "liquidity": {"equal_highs": [], "equal_lows": [], "sweep": None},
        "trend_channel": None,
        "sparse_macro": True,
        "sample_count": len(candles),
    }


def enriched_snapshot(candles: list[dict[str, float]]) -> dict[str, Any]:
    """Build technical snapshot + patterns + hidden broad feature pool."""
    base = snapshot(candles)
    if not base:
        base = _sparse_macro_snapshot(candles)
    if not base:
        return {}
    pivots = confirmed_pivots(candles)
    candle = candlestick_patterns(candles, float(base.get("atr14", 0.0))) if len(candles) >= 10 else []
    classical = classical_patterns(candles, pivots, float(base.get("atr14", 0.0))) if len(candles) >= 10 else []
    features = feature_pool(candles)
    base["candlestick_patterns"] = candle
    base["chart_patterns"] = classical
    base["pattern_bias"] = round(pattern_bias(candle, classical), 4)
    base["feature_summary"] = feature_summary(features)
    base["_feature_pool"] = features
    base["sample_count"] = len(candles)
    return base

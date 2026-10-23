from __future__ import annotations

from typing import Any

from .feature_factory import feature_pool, feature_summary
from .indicators import confirmed_pivots, snapshot
from .patterns import candlestick_patterns, classical_patterns, pattern_bias


def enriched_snapshot(candles: list[dict[str, float]]) -> dict[str, Any]:
    """Build technical snapshot + structure + patterns + hidden feature pool."""
    base = snapshot(candles)
    if not base:
        return {}
    pivots = confirmed_pivots(candles)
    candle = candlestick_patterns(candles, float(base.get("atr14", 0.0)))
    classical = classical_patterns(candles, pivots, float(base.get("atr14", 0.0)))
    features = feature_pool(candles)
    base["candlestick_patterns"] = candle
    base["chart_patterns"] = classical
    base["pattern_bias"] = round(pattern_bias(candle, classical), 4)
    base["feature_summary"] = feature_summary(features)
    # Internal-only: engine strips private keys before sending snapshots to UI.
    base["_feature_pool"] = features
    return base

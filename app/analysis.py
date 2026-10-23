from __future__ import annotations

from typing import Any

from .indicators import confirmed_pivots, snapshot
from .patterns import candlestick_patterns, classical_patterns, pattern_bias


def enriched_snapshot(candles: list[dict[str, float]]) -> dict[str, Any]:
    """Build the standard technical snapshot plus confirmed pattern context."""
    base = snapshot(candles)
    if not base:
        return {}
    pivots = confirmed_pivots(candles)
    candle = candlestick_patterns(candles, float(base.get("atr14", 0.0)))
    classical = classical_patterns(candles, pivots, float(base.get("atr14", 0.0)))
    base["candlestick_patterns"] = candle
    base["chart_patterns"] = classical
    base["pattern_bias"] = round(pattern_bias(candle, classical), 4)
    return base

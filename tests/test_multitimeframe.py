import unittest

from app.brains import macro_context
from app.config import settings
from app.indicators import liquidity_map, trend_channel
from app.master import _scores


def bullish_snapshot():
    return {
        "trend": "BULLISH", "close": 110.0, "ema20": 108.0, "ema50": 105.0,
        "ema200": 100.0, "vwap20": 107.0, "rsi14": 60.0, "macd_hist": 1.0,
        "structure": "BULLISH", "structure_event": {"kind": "BOS_UP"},
        "order_block": {}, "fvg_zones": [], "liquidity": {}, "trend_channel": None,
        "feature_summary": {"count": 220, "bias": 0.2, "strength": 0.5},
        "pattern_bias": 0.0,
    }


class MultiTimeframeTests(unittest.TestCase):
    def test_full_stack_runs_micro_to_yearly(self):
        self.assertEqual(settings.intervals[0], "1m")
        self.assertEqual(settings.intervals[-1], "1y")
        self.assertIn("30m", settings.intervals)
        self.assertIn("12h", settings.intervals)
        self.assertIn("3d", settings.intervals)
        self.assertIn("1M", settings.intervals)
        self.assertIn("3M", settings.intervals)
        self.assertIn("6M", settings.intervals)
        self.assertEqual(len(settings.intervals), 18)

    def test_macro_context_uses_large_timeframes(self):
        snaps = {
            "1d": bullish_snapshot(), "3d": bullish_snapshot(), "1w": bullish_snapshot(),
            "1M": bullish_snapshot(), "3M": bullish_snapshot(), "6M": bullish_snapshot(), "1y": bullish_snapshot(),
        }
        macro = macro_context(snaps)
        self.assertEqual(macro["direction"], "BULLISH")
        self.assertGreater(macro["strength"], 0.2)

    def test_macro_conflict_reduces_safety(self):
        base = {
            "confidence": 80, "consensus_score": 0.5, "volatility_pct": 0.8,
            "rr": 2.0, "ev_pct": 0.5, "volume_ratio": 1.2, "risk_pct": 0.6,
            "direction": "LONG", "liquidity": {}, "macro_strength": 0.8,
        }
        aligned = dict(base, macro_aligned=True, macro_conflict=False)
        conflict = dict(base, macro_aligned=False, macro_conflict=True)
        self.assertGreater(_scores(aligned)["safety_score"], _scores(conflict)["safety_score"])

    def test_equal_high_liquidity_sweep(self):
        candles = [
            {"time": 1, "close": 99.0, "high": 99.4, "low": 98.5},
            {"time": 2, "close": 99.5, "high": 100.0, "low": 99.0},
            {"time": 3, "close": 99.4, "high": 99.8, "low": 99.1},
            {"time": 4, "close": 99.6, "high": 100.1, "low": 99.2},
            {"time": 5, "close": 99.5, "high": 99.9, "low": 99.2},
            {"time": 6, "close": 99.4, "high": 100.7, "low": 99.1},
        ]
        pivots = [
            {"type": "HIGH", "price": 100.0, "time": 2, "index": 1},
            {"type": "HIGH", "price": 100.1, "time": 4, "index": 3},
        ]
        liq = liquidity_map(candles, pivots, atr_value=1.0)
        self.assertTrue(liq["equal_highs"])
        self.assertEqual(liq["sweep"]["kind"], "SWEEP_HIGH")
        self.assertEqual(liq["sweep"]["direction"], "BEARISH")

    def test_ascending_channel_from_confirmed_swings(self):
        candles = [{"time": 10, "close": 110, "high": 111, "low": 109}]
        pivots = [
            {"type": "LOW", "price": 90, "time": 1, "index": 0},
            {"type": "HIGH", "price": 100, "time": 2, "index": 1},
            {"type": "LOW", "price": 95, "time": 5, "index": 2},
            {"type": "HIGH", "price": 105, "time": 6, "index": 3},
        ]
        channel = trend_channel(candles, pivots)
        self.assertIsNotNone(channel)
        self.assertEqual(channel["kind"], "ASCENDING_CHANNEL")


if __name__ == "__main__":
    unittest.main()

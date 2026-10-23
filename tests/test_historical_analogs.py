import unittest

from app.historical_analogs import _evaluate_path, _similarity


class HistoricalAnalogTests(unittest.TestCase):
    def test_identical_signature_scores_higher_than_opposite_signature(self):
        current = {
            "trend": "BULLISH", "structure": "BULLISH", "regime": "TREND_UP",
            "rsi": 0.2, "ema20_dist": 0.01, "ema50_dist": 0.02, "vwap_dist": 0.005,
            "volume": 0.4, "volatility": 0.8,
            "layer_micro": 0.7, "layer_intraday": 0.8, "layer_swing": 0.9, "layer_macro": 0.9,
        }
        opposite = {
            "trend": "BEARISH", "structure": "BEARISH", "regime": "TREND_DOWN",
            "rsi": -0.4, "ema20_dist": -0.03, "ema50_dist": -0.05, "vwap_dist": -0.03,
            "volume": -0.5, "volatility": 2.0,
            "layer_micro": -0.8, "layer_intraday": -0.9, "layer_swing": -0.9, "layer_macro": -1.0,
        }
        self.assertGreater(_similarity(current, current), 0.95)
        self.assertGreater(_similarity(current, current), _similarity(current, opposite))

    def test_same_candle_stop_wins_over_large_target(self):
        future = [{"high": 106.0, "low": 98.0, "close": 104.0}]
        result = _evaluate_path(future, "LONG", entry=100.0, risk_pct=1.0)
        self.assertTrue(result["stopped"])
        self.assertEqual(result["max_r"], 0.0)

    def test_short_path_measures_favorable_r_correctly(self):
        future = [
            {"high": 100.2, "low": 98.0, "close": 98.5},
            {"high": 99.0, "low": 96.0, "close": 96.5},
        ]
        result = _evaluate_path(future, "SHORT", entry=100.0, risk_pct=1.0)
        self.assertFalse(result["stopped"])
        self.assertGreaterEqual(result["max_r"], 4.0)


if __name__ == "__main__":
    unittest.main()

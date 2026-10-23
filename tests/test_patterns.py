import unittest

from app.patterns import candlestick_patterns, classical_patterns, pattern_bias


def c(t, o, h, l, close):
    return {"time": t, "open": o, "high": h, "low": l, "close": close, "volume": 1.0}


class PatternTests(unittest.TestCase):
    def test_bullish_engulfing_detected_on_closed_sequence(self):
        candles = [
            c(1, 100, 101, 98, 99),
            c(2, 99.5, 100, 97.5, 98),
            c(3, 97.5, 101, 97, 100.5),
            c(4, 100.5, 101, 100, 100.8),
        ]
        pats = candlestick_patterns(candles, atr_value=2.0)
        names = {p["name"] for p in pats}
        self.assertIn("BULLISH_ENGULFING", names)

    def test_double_top_requires_neckline_break_for_confirmation(self):
        pivots = [
            {"type": "HIGH", "price": 110, "time": 2, "index": 1},
            {"type": "LOW", "price": 100, "time": 4, "index": 3},
            {"type": "HIGH", "price": 110.2, "time": 6, "index": 5},
            {"type": "LOW", "price": 102, "time": 7, "index": 6},
        ]
        # Classical patterns require enough confirmed history before they are
        # considered; use 11 completed bars so the test exercises the pattern,
        # not the minimum-history guard.
        forming = [c(i, 104, 106, 103, 104) for i in range(1, 12)]
        forming[-1]["close"] = 103
        p = [x for x in classical_patterns(forming, pivots, 1.0) if x["name"] == "DOUBLE_TOP"][0]
        self.assertFalse(p["confirmed"])
        self.assertLess(p["strength"], 0.6)

        broken = [dict(x) for x in forming]
        broken[-1]["close"] = 99
        p2 = [x for x in classical_patterns(broken, pivots, 1.0) if x["name"] == "DOUBLE_TOP"][0]
        self.assertTrue(p2["confirmed"])
        self.assertGreater(p2["strength"], p["strength"])

    def test_pattern_bias_is_bounded_and_secondary(self):
        candles = [{"name": "X", "direction": "BULLISH", "strength": 1.0, "time": i} for i in range(5)]
        charts = [{"name": "Y", "direction": "BULLISH", "strength": 1.0, "confirmed": True, "time": i} for i in range(4)]
        bias = pattern_bias(candles, charts)
        self.assertGreater(bias, 0)
        self.assertLessEqual(abs(bias), 0.65)

    def test_triangle_uses_confirmed_pivots(self):
        pivots = [
            {"type": "HIGH", "price": 110, "time": 1, "index": 0},
            {"type": "LOW", "price": 90, "time": 2, "index": 1},
            {"type": "HIGH", "price": 108, "time": 3, "index": 2},
            {"type": "LOW", "price": 92, "time": 4, "index": 3},
            {"type": "HIGH", "price": 106, "time": 5, "index": 4},
            {"type": "LOW", "price": 94, "time": 6, "index": 5},
        ]
        candles = [c(i, 100, 101, 99, 100) for i in range(1, 12)]
        names = {p["name"] for p in classical_patterns(candles, pivots, 2.0)}
        self.assertIn("SYMMETRICAL_TRIANGLE", names)


if __name__ == "__main__":
    unittest.main()

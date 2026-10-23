import unittest

from app.indicators import active_fvgs, confirmed_pivots, heuristic_order_block, market_structure


def c(t, o, h, l, close, v=100):
    return {"time": t, "open": o, "high": h, "low": l, "close": close, "volume": v, "closed": True}


class MarketStructureTests(unittest.TestCase):
    def setUp(self):
        # Confirmed swing high at index 2, swing low at index 4, then an
        # upside break. Candle 5 is bearish so it can become the heuristic OB.
        self.candles = [
            c(0, 10.0, 11.0, 9.4, 10.4),
            c(60, 10.4, 12.0, 9.8, 11.4),
            c(120, 11.4, 14.0, 10.2, 13.0),
            c(180, 13.0, 12.8, 9.7, 10.6),
            c(240, 10.6, 11.4, 8.5, 10.2),
            c(300, 10.8, 12.1, 9.2, 9.8),
            c(360, 9.8, 14.8, 10.0, 14.5),
            c(420, 14.5, 14.7, 11.0, 13.8),
            c(480, 13.8, 14.4, 11.5, 13.4),
        ]

    def test_pivot_requires_right_confirmation(self):
        pivots = confirmed_pivots(self.candles[:4], left=2, right=2)
        self.assertFalse(any(p["index"] == 2 for p in pivots))

        pivots = confirmed_pivots(self.candles[:5], left=2, right=2)
        self.assertTrue(any(p["type"] == "HIGH" and p["index"] == 2 for p in pivots))

    def test_detects_recent_upside_break(self):
        ms = market_structure(self.candles)
        self.assertIsNotNone(ms["event"])
        self.assertIn(ms["event"]["kind"], {"BOS_UP", "CHOCH_UP"})
        self.assertEqual(ms["event"]["direction"], "BULLISH")
        self.assertEqual(ms["event"]["level"], 14.0)

    def test_heuristic_order_block_is_last_opposite_candle(self):
        ms = market_structure(self.candles)
        ob = heuristic_order_block(self.candles, ms)
        self.assertIsNotNone(ob)
        self.assertEqual(ob["kind"], "BULLISH")
        self.assertTrue(ob["heuristic"])
        self.assertEqual(ob["time"], 300)

    def test_fvg_stays_only_while_not_fully_filled(self):
        data = [
            c(0, 9.5, 10.0, 9.0, 9.8),
            c(60, 9.8, 10.7, 9.6, 10.5),
            c(120, 11.2, 12.0, 11.1, 11.8),  # bullish FVG: 10.0 -> 11.1
            c(180, 11.8, 12.2, 10.6, 11.4),  # partial fill, not through 10.0
        ]
        zones = active_fvgs(data)
        self.assertTrue(any(z["kind"] == "BULLISH" and z["lower"] == 10.0 for z in zones))

        data.append(c(240, 11.4, 11.5, 9.9, 10.2))  # full fill through lower edge
        zones = active_fvgs(data)
        self.assertFalse(any(z["kind"] == "BULLISH" and z["lower"] == 10.0 for z in zones))


if __name__ == "__main__":
    unittest.main()

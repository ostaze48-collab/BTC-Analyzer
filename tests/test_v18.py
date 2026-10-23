import unittest
from datetime import datetime, timezone, timedelta

from app.cycle_models import cycle_model_context, halving_price_regression, power_law_fair_price
from app.feature_factory import feature_pool
from app.market import aggregate_monthly


def candle(ts, o, h, l, c, v=100.0):
    return {"time": ts, "close_time": ts + 10, "open": o, "high": h, "low": l, "close": c, "volume": v, "closed": True}


class V18Tests(unittest.TestCase):
    def test_monthly_aggregates_to_quarter_half_and_year(self):
        rows = []
        for month in range(1, 13):
            ts = int(datetime(2024, month, 1, tzinfo=timezone.utc).timestamp())
            rows.append(candle(ts, 100 + month, 110 + month, 90 + month, 105 + month, 10 + month))
        q = aggregate_monthly(rows, "3M")
        h = aggregate_monthly(rows, "6M")
        y = aggregate_monthly(rows, "1y")
        self.assertEqual(len(q), 4)
        self.assertEqual(len(h), 2)
        self.assertEqual(len(y), 1)
        self.assertTrue(all(x["closed"] for x in q + h + y))
        self.assertEqual(y[0]["open"], 101.0)
        self.assertEqual(y[0]["close"], 117.0)
        self.assertEqual(y[0]["high"], 122.0)
        self.assertEqual(y[0]["low"], 91.0)

    def test_public_cycle_formulas_are_positive(self):
        ts = int(datetime(2026, 10, 23, tzinfo=timezone.utc).timestamp())
        self.assertGreater(power_law_fair_price(ts), 0)
        self.assertGreater(halving_price_regression(ts), 0)

    def test_cycle_context_builds_mayer_and_pi_from_daily_history(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = []
        price = 40000.0
        for i in range(420):
            price *= 1.0008
            ts = int((start + timedelta(days=i)).timestamp())
            rows.append(candle(ts, price * .995, price * 1.01, price * .99, price, 1000 + i))
        ctx = cycle_model_context(rows)
        self.assertTrue(ctx["available"])
        self.assertIn("power_law", ctx["models"])
        self.assertIn("hpr_rainbow", ctx["models"])
        self.assertIn("mayer_multiple", ctx["models"])
        self.assertIn("pi_cycle_top", ctx["models"])

    def test_dense_frame_generates_hundreds_of_background_features(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = []
        price = 70000.0
        for i in range(230):
            price += ((i % 9) - 4) * 13 + 25
            ts = int((start + timedelta(minutes=i)).timestamp())
            rows.append(candle(ts, price - 20, price + 70, price - 80, price, 100 + (i % 11) * 7))
        features = feature_pool(rows)
        self.assertGreaterEqual(len(features), 200)
        self.assertIn("rsi_14", features)
        self.assertIn("cmf_20", features)
        self.assertIn("donchian_pos_50", features)

    def test_sparse_year_frame_does_not_fake_200_period_features(self):
        start = datetime(2018, 1, 1, tzinfo=timezone.utc)
        rows = [candle(int(datetime(2018+i, 1, 1, tzinfo=timezone.utc).timestamp()), 100+i, 120+i, 90+i, 110+i) for i in range(8)]
        features = feature_pool(rows)
        self.assertNotIn("ema_dist_200", features)
        self.assertIn("ema_dist_8", features)


if __name__ == "__main__":
    unittest.main()

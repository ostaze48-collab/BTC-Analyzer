import unittest
from datetime import datetime, timedelta, timezone

from app.cycle_walkforward import CycleWalkForward


def daily_rows(days=2600):
    start = datetime(2019, 1, 1, tzinfo=timezone.utc)
    rows = []
    price = 4000.0
    for i in range(days):
        # deterministic trend + recurring cycles, not meant to model BTC realism
        drift = 1.0009 if (i // 180) % 2 == 0 else 0.9997
        price *= drift
        price *= 1.0 + (((i % 31) - 15) / 100000.0)
        ts = int((start + timedelta(days=i)).timestamp())
        rows.append({
            "time": ts,
            "close_time": ts + 86399,
            "open": price * .997,
            "high": price * 1.012,
            "low": price * .988,
            "close": price,
            "volume": 1000 + (i % 17) * 20,
            "closed": True,
        })
    return rows


class CycleWalkForwardTests(unittest.TestCase):
    def test_bucket_stats(self):
        stats = CycleWalkForward._bucket_stats([
            {"signed_return": .1, "future_return": .2, "bias": .5},
            {"signed_return": -.02, "future_return": -.1, "bias": .2},
        ])
        self.assertEqual(stats["samples"], 2)
        self.assertEqual(stats["directional_accuracy_pct"], 50.0)

    def test_chronological_holdout_produces_only_late_samples(self):
        rows = daily_rows()
        requested_start = rows[500]["close_time"]
        result = CycleWalkForward()._evaluate(rows, requested_start, 6)
        self.assertEqual(result["validation_type"], "CHRONOLOGICAL_HOLDOUT_NO_REFIT")
        self.assertGreater(result["primary"]["samples"], 20)
        self.assertGreaterEqual(result["holdout_start"], requested_start)
        self.assertEqual(result["primary_horizon_days"], 90)
        self.assertIn("power_law", result["by_model"]["90"])


if __name__ == "__main__":
    unittest.main()

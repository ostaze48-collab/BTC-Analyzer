import unittest

from app.incremental_edge import incremental_walkforward


def make_sample(i: int) -> dict:
    # Feature alternates; HIGH values consistently outperform LOW values in all
    # forward blocks so the validator should detect stable incremental edge.
    high = (i % 2) == 0
    r = 0.55 if high else -0.18
    return {
        "trade_id": i,
        "opened_at": f"2026-01-{(i % 28) + 1:02d}T00:{i % 60:02d}:00Z",
        "brain": "INTRADAY",
        "direction": "LONG",
        "market_regime": "TREND_UP" if i % 3 else "RANGE",
        "risk_budget": 10.0,
        "realized_pnl": r * 10.0,
        "features": {
            "background_features": {
                "30m": {
                    "ret_14": 1.0 if high else -1.0,
                    "realized_vol_20": 0.25 + (i % 5) * 0.01,
                }
            }
        },
    }


class IncrementalEdgeTests(unittest.TestCase):
    def test_insufficient_data_never_auto_applies(self):
        result = incremental_walkforward([make_sample(i) for i in range(30)])
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertFalse(result["auto_apply"])

    def test_stable_filter_can_become_shadow_trial_candidate(self):
        result = incremental_walkforward([make_sample(i) for i in range(120)], max_features=20)
        self.assertFalse(result["auto_apply"])
        self.assertGreater(result["features_evaluated"], 0)
        features = {row["feature"]: row for row in result["eligible"]}
        self.assertIn("tf.30m.ret_14", features)
        self.assertTrue(features["tf.30m.ret_14"]["eligible_for_shadow_trial"])
        self.assertGreater(features["tf.30m.ret_14"]["mean_delta_r"], 0)


if __name__ == "__main__":
    unittest.main()

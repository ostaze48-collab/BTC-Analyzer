import unittest

from app.target_policy_validation import _partial_policy_r, validate_target_policy


class TargetPolicyValidationTests(unittest.TestCase):
    def test_partial_policy_matches_30_40_30_structure(self):
        # 3R terminal target => TP1=1R, TP2=1.8R, TP3=3R.
        self.assertAlmostEqual(_partial_policy_r(3.0, 3.2, False), 1.92, places=6)
        self.assertAlmostEqual(_partial_policy_r(3.0, 0.5, True), -1.0, places=6)
        self.assertAlmostEqual(_partial_policy_r(3.0, 1.2, True), 0.30, places=6)
        self.assertAlmostEqual(_partial_policy_r(3.0, 2.0, True), 1.32, places=6)

    def test_unresolved_higher_counterfactual_is_not_guessed(self):
        self.assertIsNone(_partial_policy_r(5.0, 2.0, False))

    def test_validator_never_auto_applies_with_small_sample(self):
        trades = []
        samples = []
        for i in range(1, 11):
            trades.append({
                "id": i, "mfe_pct": 2.0, "target_r": 2.0,
                "exit_reason": "ADAPTIVE_TARGET_R",
            })
            samples.append({
                "trade_id": i, "opened_at": f"2026-01-{i:02d}T00:00:00+00:00",
                "brain": "INTRADAY", "market_regime": "TREND_UP",
                "features": {
                    "adaptive_risk_plan": {"stop_distance_pct": 1.0, "target_r": 2.0},
                    "historical_analogs": {
                        "status": "READY", "matches": 20, "quality": "STRONG",
                        "hit_1r_pct": 85, "hit_2r_pct": 70, "hit_3r_pct": 45,
                        "hit_4r_pct": 25, "hit_5r_pct": 10,
                    },
                },
            })
        r = validate_target_policy(samples, trades)
        self.assertEqual(r["status"], "INSUFFICIENT_RESOLVED_PATHS")
        self.assertFalse(r["auto_apply"])
        self.assertEqual(r["weight_in_risk_engine"], 0.0)

    def test_unresolved_rows_reduce_coverage_not_fabricated(self):
        trade = {"id": 1, "mfe_pct": 1.2, "target_r": 1.0, "exit_reason": "EARLY_EXIT"}
        sample = {
            "trade_id": 1, "opened_at": "2026-01-01T00:00:00+00:00",
            "brain": "INTRADAY", "market_regime": "TREND_UP",
            "features": {
                "adaptive_risk_plan": {"stop_distance_pct": 1.0, "target_r": 1.0},
                "historical_analogs": {
                    "status": "READY", "matches": 20, "quality": "STRONG",
                    "hit_1r_pct": 90, "hit_2r_pct": 80, "hit_3r_pct": 70,
                    "hit_4r_pct": 60, "hit_5r_pct": 55,
                },
            },
        }
        r = validate_target_policy([sample], [trade])
        self.assertEqual(r["eligible_with_advisor"], 1)
        self.assertEqual(r["resolved_comparisons"], 0)
        self.assertEqual(r["resolution_coverage_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()

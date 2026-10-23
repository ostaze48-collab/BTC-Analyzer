import unittest

from app.target_advisor import build_historical_target_advisor


class HistoricalTargetAdvisorTests(unittest.TestCase):
    def test_requires_minimum_matches(self):
        r = build_historical_target_advisor([{"max_r": 2.0, "stopped": False, "mfe_r": 2.0, "mae_r": 0.2}] * 7)
        self.assertEqual(r["status"], "INSUFFICIENT_MATCHES")
        self.assertIsNone(r["recommended_r"])
        self.assertEqual(r["weight_in_risk_engine"], 0.0)

    def test_prefers_target_with_best_conservative_ev(self):
        matches = []
        for _ in range(12):
            matches.append({"max_r": 3.2, "stopped": False, "mfe_r": 3.2, "mae_r": 0.3})
        for _ in range(6):
            matches.append({"max_r": 1.2, "stopped": True, "mfe_r": 1.2, "mae_r": 1.1})
        for _ in range(6):
            matches.append({"max_r": 0.4, "stopped": True, "mfe_r": 0.4, "mae_r": 1.1})
        r = build_historical_target_advisor(matches, quality="STRONG")
        self.assertEqual(r["mode"], "SHADOW_ONLY")
        self.assertEqual(r["weight_in_risk_engine"], 0.0)
        self.assertIn(r["recommended_r"], (1.0, 2.0, 3.0, 4.0, 5.0))
        self.assertGreater(r["best_conservative_ev_r"], 0)
        self.assertEqual(len(r["targets"]), 5)

    def test_far_target_is_not_rewarded_when_most_paths_stop_first(self):
        matches = []
        for _ in range(4):
            matches.append({"max_r": 5.0, "stopped": False, "mfe_r": 5.0, "mae_r": 0.2})
        for _ in range(20):
            matches.append({"max_r": 0.5, "stopped": True, "mfe_r": 0.5, "mae_r": 1.1})
        r = build_historical_target_advisor(matches, quality="MODERATE")
        target5 = next(x for x in r["targets"] if x["target_r"] == 5.0)
        self.assertLess(target5["conservative_ev_r"], 1.0)


if __name__ == "__main__":
    unittest.main()

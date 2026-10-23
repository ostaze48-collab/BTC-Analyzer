import unittest

from app.readiness import readiness_report


class ReadinessTests(unittest.TestCase):
    def robust_learning(self):
        return {
            "brain_regime": [
                {"brain":"SCALP","regime":"RANGE","trades":30,"profit_factor":1.3,"net_pnl":20},
                {"brain":"INTRADAY","regime":"TREND_UP","trades":30,"profit_factor":1.5,"net_pnl":35},
                {"brain":"SWING","regime":"TREND_DOWN","trades":30,"profit_factor":1.4,"net_pnl":25},
                {"brain":"SCALP","regime":"BREAKOUT_UP","trades":30,"profit_factor":0.9,"net_pnl":-5},
            ]
        }

    def test_short_replay_can_never_satisfy_execution_oos_gate(self):
        report = readiness_report(
            {"trades":150,"profit_factor":1.5,"max_drawdown_pct":5},
            self.robust_learning(),
            {"validation_type":"SHORT_WINDOW_REPLAY","trades":1000,"profit_factor":2.0,"max_drawdown_pct":2,"avg_r":0.5,"return_pct":20},
            {"samples":150,"mean_signed_return":0.02,"directional_accuracy_pct":55},
        )
        self.assertNotEqual(report["status"], "LIVE_CANDIDATE")
        gate = next(g for g in report["hard_gates"] if g["id"] == "oos_type")
        self.assertFalse(gate["passed"])

    def test_all_hard_gates_can_produce_live_candidate_but_not_enable_execution(self):
        report = readiness_report(
            {"trades":150,"profit_factor":1.5,"max_drawdown_pct":5},
            self.robust_learning(),
            {"validation_type":"WALK_FORWARD_OOS","trades":400,"profit_factor":1.5,"max_drawdown_pct":7,"avg_r":0.2,"return_pct":12},
            {"samples":160,"mean_signed_return":0.015,"directional_accuracy_pct":54},
        )
        self.assertEqual(report["status"], "LIVE_CANDIDATE")
        self.assertFalse(report["live_execution_enabled"])
        self.assertEqual(report["guarantee"], "NONE")

    def test_empty_evidence_is_not_ready(self):
        report = readiness_report({}, {}, {}, {})
        self.assertEqual(report["status"], "NOT_READY")
        self.assertLess(report["score"], 50)


if __name__ == "__main__":
    unittest.main()

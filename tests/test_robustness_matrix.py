import unittest

from app.robustness_matrix import robustness_matrix_gate


def trade(i, brain, regime, r):
    return {
        "trade_id": i,
        "brain": brain,
        "market_regime": regime,
        "realized_pnl": r * 10.0,
        "risk_budget": 10.0,
    }


def healthy_samples():
    rows = []
    i = 0
    for brain in ("SCALP", "INTRADAY"):
        for regime in ("TREND_UP", "RANGE"):
            for j in range(40):
                i += 1
                r = 0.5 if j % 10 < 7 else -0.5
                rows.append(trade(i, brain, regime, r))
    return rows


class RobustnessMatrixTests(unittest.TestCase):
    def test_diversified_positive_matrix_can_pass_but_remains_paper_only(self):
        r = robustness_matrix_gate(healthy_samples(), {"status": "STABILITY_7D_CONFIRMED", "highest_level": 3})
        self.assertEqual(r["status"], "ROBUSTNESS_MATRIX_PASSED")
        self.assertEqual(r["failed_gates"], [])
        self.assertGreaterEqual(r["mature_cells"], 4)
        self.assertGreaterEqual(r["robust_cell_rate_pct"], 60)
        self.assertFalse(r["automatic_real_execution"])
        self.assertFalse(r["real_execution_eligibility"])
        self.assertFalse(r["target_auto_apply"])

    def test_seven_day_stability_is_required_first(self):
        r = robustness_matrix_gate(healthy_samples(), {"status": "STABILITY_72H_CONFIRMED", "highest_level": 2})
        self.assertIn("seven_day_stability", r["failed_gates"])
        self.assertEqual(r["status"], "ROBUSTNESS_MATRIX_BLOCKED")

    def test_single_brain_cannot_fake_robustness(self):
        rows = []
        for i in range(180):
            rows.append(trade(i, "SCALP", "TREND_UP" if i % 2 else "RANGE", 0.4 if i % 4 else -0.2))
        r = robustness_matrix_gate(rows, {"status": "STABILITY_7D_CONFIRMED", "highest_level": 3})
        self.assertIn("brain_coverage", r["failed_gates"])
        self.assertIn("brain_concentration", r["failed_gates"])

    def test_single_regime_cannot_fake_robustness(self):
        rows = []
        for i in range(180):
            rows.append(trade(i, "SCALP" if i % 2 else "INTRADAY", "TREND_UP", 0.4 if i % 4 else -0.2))
        r = robustness_matrix_gate(rows, {"status": "STABILITY_7D_CONFIRMED", "highest_level": 3})
        self.assertIn("regime_coverage", r["failed_gates"])
        self.assertIn("regime_concentration", r["failed_gates"])

    def test_one_profitable_cell_cannot_dominate_positive_edge(self):
        rows = healthy_samples()
        # Make three cells barely positive and one cell extremely positive while
        # keeping values bounded by the R clamp; concentration must block.
        for row in rows:
            if row["brain"] == "SCALP" and row["market_regime"] == "TREND_UP":
                row["realized_pnl"] = 20.0
            else:
                row["realized_pnl"] = 1.0 if row["trade_id"] % 2 else -0.5
        r = robustness_matrix_gate(rows, {"status": "STABILITY_7D_CONFIRMED", "highest_level": 3})
        self.assertIn("positive_edge_concentration", r["failed_gates"])

    def test_missing_risk_budget_is_not_counted_as_valid_r_evidence(self):
        rows = healthy_samples()
        for row in rows[:50]:
            row["risk_budget"] = 0
        r = robustness_matrix_gate(rows, {"status": "STABILITY_7D_CONFIRMED", "highest_level": 3})
        self.assertIn("valid_r_sample", r["failed_gates"])


if __name__ == "__main__":
    unittest.main()

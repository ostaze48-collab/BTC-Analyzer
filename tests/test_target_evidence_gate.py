import unittest

from app.target_evidence_gate import target_evidence_gate


def full_ok(brain):
    return {
        "brain": brain,
        "status": "FULL_WALKFORWARD_OUTPERFORMS",
        "validation_rows": 60,
        "holdout": {"delta_mean_r": 0.12, "drawdown_ratio": 0.95},
    }


def live_ok():
    return {
        "status": "LIVE_SHADOW_OUTPERFORMS",
        "resolved": 55,
        "advisor_overrides": 25,
        "resolution_coverage_pct": 72.0,
        "holdout": {"delta_mean_r": 0.10, "drawdown_ratio": 0.97},
    }


class TargetEvidenceGateTests(unittest.TestCase):
    def test_live_alone_never_passes(self):
        r = target_evidence_gate({}, live_ok())
        self.assertFalse(r["all_gates_passed"])
        self.assertEqual(r["status"], "NOT_READY_FOR_TARGET_INFLUENCE")

    def test_one_historical_brain_is_not_enough(self):
        r = target_evidence_gate({"SCALP": full_ok("SCALP")}, live_ok())
        self.assertFalse(r["all_gates_passed"])

    def test_two_full_brains_plus_live_can_pass_research_gate_only(self):
        r = target_evidence_gate({"SCALP": full_ok("SCALP"), "INTRADAY": full_ok("INTRADAY")}, live_ok())
        self.assertTrue(r["all_gates_passed"])
        self.assertEqual(r["status"], "BOUNDED_SHADOW_EXPERIMENT_CANDIDATE")
        self.assertTrue(r["next_research_stage_allowed"])
        self.assertFalse(r["auto_apply"])
        self.assertEqual(r["target_execution_weight"], 0.0)
        self.assertEqual(r["master_weight"], 0.0)
        self.assertFalse(r["real_execution_enabled"])

    def test_bad_live_holdout_blocks_even_with_all_brains(self):
        live = live_ok(); live["holdout"] = {"delta_mean_r": -0.1, "drawdown_ratio": 1.2}
        r = target_evidence_gate({b: full_ok(b) for b in ("SCALP", "INTRADAY", "SWING")}, live)
        self.assertFalse(r["all_gates_passed"])
        self.assertIn("live_holdout_risk_adjusted", r["failed_gates"])


if __name__ == "__main__":
    unittest.main()

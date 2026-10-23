import unittest

from app.unified_readiness import unified_research_readiness


class UnifiedReadinessTests(unittest.TestCase):
    def test_target_gate_alone_cannot_create_live_candidate(self):
        r = unified_research_readiness(
            {"status": "NOT_READY", "score": 25, "live_execution_enabled": False},
            {"all_gates_passed": True, "status": "BOUNDED_SHADOW_EXPERIMENT_CANDIDATE", "failed_gates": [], "real_execution_enabled": False},
            {}, {},
        )
        self.assertNotEqual(r["status"], "LIVE_PILOT_CANDIDATE")
        self.assertFalse(r["live_execution_enabled"])

    def test_full_core_and_target_evidence_only_create_candidate_not_execution(self):
        r = unified_research_readiness(
            {"status": "LIVE_CANDIDATE", "score": 100, "passed": 8, "total": 8, "live_execution_enabled": False},
            {"all_gates_passed": True, "status": "BOUNDED_SHADOW_EXPERIMENT_CANDIDATE", "failed_gates": [], "real_execution_enabled": False, "successful_full_walkforward_brains": ["SCALP", "INTRADAY"]},
            {"status": "OOS_CANDIDATES_AVAILABLE", "diversified_candidate_count": 5},
            {"status": "SHADOW_TRIAL_CANDIDATES", "eligible_count": 3},
        )
        self.assertEqual(r["status"], "LIVE_PILOT_CANDIDATE")
        self.assertFalse(r["automatic_real_execution"])
        self.assertFalse(r["live_execution_enabled"])
        self.assertEqual(r["guarantee"], "NONE")

    def test_execution_interlock_blocks_candidate(self):
        r = unified_research_readiness(
            {"status": "LIVE_CANDIDATE", "score": 100, "live_execution_enabled": True},
            {"all_gates_passed": True, "status": "BOUNDED_SHADOW_EXPERIMENT_CANDIDATE", "failed_gates": [], "real_execution_enabled": False},
            {}, {},
        )
        self.assertNotEqual(r["status"], "LIVE_PILOT_CANDIDATE")
        gate = next(g for g in r["hard_gates"] if g["id"] == "real_execution_interlock")
        self.assertFalse(gate["passed"])

    def test_research_score_does_not_override_hard_gates(self):
        r = unified_research_readiness(
            {"status": "SHADOW_READY", "score": 80, "live_execution_enabled": False},
            {"all_gates_passed": False, "status": "NOT_READY_FOR_TARGET_INFLUENCE", "failed_gates": ["live_shadow_status"], "real_execution_enabled": False},
            {"status": "OOS_CANDIDATES_AVAILABLE", "diversified_candidate_count": 20},
            {"status": "SHADOW_TRIAL_CANDIDATES", "eligible_count": 20},
        )
        self.assertGreater(r["research_score"], 50)
        self.assertNotEqual(r["status"], "LIVE_PILOT_CANDIDATE")


if __name__ == "__main__":
    unittest.main()

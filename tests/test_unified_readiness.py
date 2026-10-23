import unittest

from app.unified_readiness import unified_research_readiness


class UnifiedReadinessTests(unittest.TestCase):
    def _target_pass(self):
        return {
            "status": "BOUNDED_SHADOW_EXPERIMENT_CANDIDATE",
            "all_gates_passed": True,
            "gates": [
                {"id": "a", "passed": True},
                {"id": "b", "passed": True},
            ],
            "failed_gates": [],
            "successful_full_walkforward_brains": ["INTRADAY", "SWING"],
            "real_execution_enabled": False,
        }

    def _core(self, status="LIVE_CANDIDATE", score=100.0, live=False):
        return {
            "status": status,
            "score": score,
            "passed": 8 if status == "LIVE_CANDIDATE" else 4,
            "total": 8,
            "live_execution_enabled": live,
            "hard_gates": [
                {"id": "paper_sample", "passed": status == "LIVE_CANDIDATE"},
                {"id": "oos_edge", "passed": status == "LIVE_CANDIDATE"},
            ],
        }

    def _edge(self):
        return {
            "status": "OOS_CANDIDATES_AVAILABLE",
            "samples": 180,
            "diversified_candidate_count": 4,
        }

    def _incremental(self):
        return {
            "status": "SHADOW_TRIAL_CANDIDATES",
            "samples": 150,
            "eligible_count": 2,
        }

    def test_high_score_never_overrides_failed_mandatory_gate(self):
        r = unified_research_readiness(
            self._core(status="NOT_READY", score=95.0),
            self._target_pass(),
            self._edge(),
            self._incremental(),
        )
        self.assertNotEqual(r["status"], "PILOT_REVIEW_CANDIDATE")
        self.assertIn("core_execution_readiness", r["failed_mandatory_gates"])
        self.assertFalse(r["score_is_authorization"])
        self.assertFalse(r["live_execution_enabled"])

    def test_all_mandatory_gates_only_create_review_candidate(self):
        r = unified_research_readiness(
            self._core(), self._target_pass(), self._edge(), self._incremental()
        )
        self.assertEqual(r["status"], "PILOT_REVIEW_CANDIDATE")
        self.assertEqual(r["failed_mandatory_gates"], [])
        self.assertFalse(r["automatic_real_execution"])
        self.assertFalse(r["live_execution_enabled"])
        self.assertFalse(r["target_auto_apply"])
        self.assertEqual(r["guarantee"], "NONE")

    def test_execution_flag_breaks_interlock(self):
        r = unified_research_readiness(
            self._core(live=True), self._target_pass(), self._edge(), self._incremental()
        )
        self.assertIn("real_execution_interlock", r["failed_mandatory_gates"])
        self.assertNotEqual(r["status"], "PILOT_REVIEW_CANDIDATE")

    def test_feature_edge_is_supporting_not_forced_gate(self):
        r = unified_research_readiness(self._core(), self._target_pass(), {}, {})
        self.assertEqual(r["status"], "PILOT_REVIEW_CANDIDATE")
        self.assertFalse(r["feature_research"]["is_mandatory_for_stage"])
        self.assertEqual(len(r["supporting_evidence"]), 2)

    def test_research_score_is_informational_only(self):
        r = unified_research_readiness(
            self._core(status="SHADOW_READY", score=80.0),
            {"all_gates_passed": False, "status": "NOT_READY_FOR_TARGET_INFLUENCE", "failed_gates": ["live_shadow_status"], "real_execution_enabled": False},
            {"status": "OOS_CANDIDATES_AVAILABLE", "samples": 300, "diversified_candidate_count": 20},
            {"status": "SHADOW_TRIAL_CANDIDATES", "samples": 300, "eligible_count": 20},
        )
        self.assertGreater(r["research_score"], 50)
        self.assertFalse(r["score_is_authorization"])
        self.assertNotEqual(r["status"], "PILOT_REVIEW_CANDIDATE")


if __name__ == "__main__":
    unittest.main()

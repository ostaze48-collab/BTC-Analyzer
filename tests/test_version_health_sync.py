import unittest

from app.main import health
from app.version import APP_LABEL, APP_VERSION


class VersionHealthSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_matches_version_and_research_capabilities(self):
        data = await health()
        self.assertEqual(data["version"], APP_VERSION)
        self.assertEqual(data["version_label"], APP_LABEL)
        self.assertTrue(data["stable_experiment_ui"])
        self.assertTrue(data["experiment_archive"])
        self.assertIn(data["experiment_archive_backend"], ("sqlite", "postgres"))
        self.assertIsInstance(data["experiment_archive_persistent"], bool)
        self.assertTrue(data["historical_analogs"])
        self.assertTrue(data["long_historical_memory"])
        self.assertTrue(data["historical_signature_cache"])
        self.assertEqual(data["signature_target_candidates"], 720)
        self.assertTrue(data["target_evidence_gate"])
        self.assertTrue(data["unified_research_readiness"])
        self.assertEqual(data["unified_readiness_mode"], "HARD_GATE_AGGREGATION")
        self.assertTrue(data["strict_paper_review"])
        self.assertEqual(data["strict_paper_review_mode"], "OVERLAPPING_30_60_100_DIAGNOSTIC")
        self.assertTrue(data["research_evidence_history"])
        self.assertEqual(data["research_evidence_history_mode"], "PERSISTENT_MATERIAL_SNAPSHOTS_WITH_STRICT_PAPER")
        self.assertTrue(data["evidence_stability_window"])
        self.assertEqual(data["evidence_stability_window_mode"], "24H_TIME_AND_NEW_TRADE_GATE")
        self.assertFalse(data["target_policy_auto_apply"])
        self.assertFalse(data["real_execution_enabled"])
        self.assertTrue(data["paper_only"])


if __name__ == "__main__":
    unittest.main()

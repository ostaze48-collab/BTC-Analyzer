import unittest

from app.main import health
from app.version import APP_LABEL, APP_VERSION


class VersionHealthSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_matches_version_and_research_capabilities(self):
        data = await health()
        self.assertEqual(data["version"], APP_VERSION)
        self.assertEqual(data["version_label"], APP_LABEL)
        self.assertTrue(data["historical_analogs"])
        self.assertTrue(data["long_historical_memory"])
        self.assertTrue(data["historical_signature_cache"])
        self.assertEqual(data["signature_target_candidates"], 720)
        self.assertTrue(data["target_evidence_gate"])
        self.assertTrue(data["unified_research_readiness"])
        self.assertEqual(data["unified_readiness_mode"], "HARD_GATE_AGGREGATION")
        self.assertFalse(data["target_policy_auto_apply"])
        self.assertFalse(data["real_execution_enabled"])


if __name__ == "__main__":
    unittest.main()

import unittest

from app.main import health
from app.version import APP_LABEL, APP_VERSION


class VersionHealthSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_health_matches_version_and_analog_validation_capability(self):
        data = await health()
        self.assertEqual(data["version"], APP_VERSION)
        self.assertEqual(data["version_label"], APP_LABEL)
        self.assertTrue(data["historical_analogs"])
        self.assertTrue(data["analog_edge_validation"])
        self.assertFalse(data["real_execution_enabled"])


if __name__ == "__main__":
    unittest.main()

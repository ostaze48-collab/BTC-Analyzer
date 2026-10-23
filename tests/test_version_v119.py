import unittest

from app.target_advisor import build_historical_target_advisor_from_summary
from app.version import APP_LABEL, APP_VERSION


class VersionCapabilityTests(unittest.TestCase):
    def test_version(self):
        self.assertEqual(APP_VERSION, "1.25.0")
        self.assertEqual(APP_LABEL, "V1.25")

    def test_target_advisor_remains_shadow_only(self):
        r = build_historical_target_advisor_from_summary({
            "status": "READY", "matches": 20, "quality": "STRONG",
            "hit_1r_pct": 80, "hit_2r_pct": 65, "hit_3r_pct": 45,
            "hit_4r_pct": 30, "hit_5r_pct": 20,
        })
        self.assertEqual(r["mode"], "SHADOW_ONLY")
        self.assertEqual(r["weight_in_risk_engine"], 0.0)


if __name__ == "__main__":
    unittest.main()

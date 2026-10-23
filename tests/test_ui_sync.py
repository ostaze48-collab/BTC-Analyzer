import unittest
from pathlib import Path

from app.version import APP_LABEL, APP_VERSION


class UiSyncTests(unittest.TestCase):
    def test_index_loads_all_current_version_layers(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_LABEL, html)
        for script in ("v22.js", "v23.js", "v24.js", "v25.js", "v26.js", "v27.js", "v28.js", "v29.js"):
            self.assertIn(f'/static/{script}', html)

    def test_latest_ui_reads_target_advisor_source(self):
        v29 = Path("app/static/v29.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", v29)
        self.assertIn("/api/historical-target-advisor", v29)
        self.assertIn("Historical Target Advisor", v29)
        self.assertEqual(APP_VERSION, "1.19.0")
        self.assertEqual(APP_LABEL, "V1.19")


if __name__ == "__main__":
    unittest.main()

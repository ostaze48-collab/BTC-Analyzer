import unittest
from pathlib import Path

from app.version import APP_LABEL, APP_VERSION


class UiSyncTests(unittest.TestCase):
    def test_index_loads_all_current_version_layers(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_LABEL, html)
        for script in ("v22.js", "v23.js", "v24.js", "v25.js", "v26.js"):
            self.assertIn(f'/static/{script}', html)

    def test_latest_ui_reads_backend_version_and_validation_sources(self):
        v25 = Path("app/static/v25.js").read_text(encoding="utf-8")
        v26 = Path("app/static/v26.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", v25)
        self.assertIn("/api/historical-analogs", v25)
        self.assertIn("/api/version", v26)
        self.assertIn("/api/analog-validation", v26)
        self.assertEqual(APP_VERSION, "1.16.0")
        self.assertEqual(APP_LABEL, "V1.16")


if __name__ == "__main__":
    unittest.main()

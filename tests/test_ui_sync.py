import unittest
from pathlib import Path

from app.version import APP_LABEL, APP_VERSION


class UiSyncTests(unittest.TestCase):
    def test_index_loads_all_current_version_layers(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_LABEL, html)
        for script in ("v22.js", "v23.js", "v24.js", "v25.js", "v26.js", "v27.js", "v28.js"):
            self.assertIn(f'/static/{script}', html)

    def test_latest_ui_reads_signature_cache_source(self):
        v28 = Path("app/static/v28.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", v28)
        self.assertIn("/api/historical-analogs", v28)
        self.assertEqual(APP_VERSION, "1.18.0")
        self.assertEqual(APP_LABEL, "V1.18")


if __name__ == "__main__":
    unittest.main()

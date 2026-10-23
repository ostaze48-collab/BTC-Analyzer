import unittest
from pathlib import Path

from app.version import APP_LABEL, APP_VERSION


class UiSyncTests(unittest.TestCase):
    def test_index_loads_all_current_version_layers(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_LABEL, html)
        for script in ("v22.js", "v23.js", "v24.js", "v25.js", "v26.js", "v27.js", "v28.js", "v29.js", "v30.js", "v31.js", "v32.js", "v33.js", "v34.js", "v35.js"):
            self.assertIn(f'/static/{script}', html)

    def test_latest_ui_reads_strict_paper_review(self):
        v35 = Path("app/static/v35.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", v35)
        self.assertIn("/api/strict-paper-review", v35)
        self.assertIn("Strict Paper Review Protocol", v35)
        self.assertIn("ليس OOS مستقل", v35)
        self.assertEqual(APP_VERSION, "1.25.0")
        self.assertEqual(APP_LABEL, "V1.25")


if __name__ == "__main__":
    unittest.main()

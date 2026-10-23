import unittest
from pathlib import Path

from app.version import APP_LABEL, APP_VERSION


class UiSyncTests(unittest.TestCase):
    def test_index_loads_all_current_version_layers(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_LABEL, html)
        for script in ("v22.js", "v23.js", "v24.js", "v25.js", "v26.js", "v27.js", "v28.js", "v29.js", "v30.js", "v31.js", "v32.js", "v33.js", "v34.js", "v35.js", "v36.js"):
            self.assertIn(f'/static/{script}', html)

    def test_latest_ui_reads_extended_paper_observation(self):
        v36 = Path("app/static/v36.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", v36)
        self.assertIn("/api/extended-paper-observation", v36)
        self.assertIn("/api/extended-paper-observation/checkpoint", v36)
        self.assertIn("Extended Paper Observation", v36)
        self.assertIn("Persistence evidence", v36)
        self.assertEqual(APP_VERSION, "1.26.0")
        self.assertEqual(APP_LABEL, "V1.26")


if __name__ == "__main__":
    unittest.main()

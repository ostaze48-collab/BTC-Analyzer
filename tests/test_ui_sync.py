import unittest
from pathlib import Path

from app.system_manifest import UI_LAYERS
from app.version import APP_LABEL, APP_VERSION


class UiSyncTests(unittest.TestCase):
    def test_index_loads_all_current_version_layers(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_LABEL, html)
        for script in UI_LAYERS:
            self.assertIn(f'/static/{script}', html)

    def test_latest_ui_reads_candidate_and_archive_sources(self):
        v25 = Path("app/static/v25.js").read_text(encoding="utf-8")
        v27 = Path("app/static/v27.js").read_text(encoding="utf-8")
        v28 = Path("app/static/v28.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", v25)
        self.assertIn("/api/historical-analogs", v25)
        self.assertIn("/api/historical-archive", v27)
        self.assertIn("/api/candidate-evidence", v28)
        self.assertIn("/api/analog-validation", v28)
        self.assertEqual(APP_VERSION, f"{APP_LABEL.removeprefix('V')}.0")


if __name__ == "__main__":
    unittest.main()

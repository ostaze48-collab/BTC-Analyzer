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

    def test_latest_ui_reads_backend_version_and_research_sources(self):
        historical = Path("app/static/v25.js").read_text(encoding="utf-8")
        deep = Path("app/static/v26.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", historical)
        self.assertIn("/api/historical-analogs", historical)
        self.assertIn("/api/deep-history", deep)
        self.assertIn("/api/evidence-score", deep)
        self.assertEqual(APP_VERSION, f"{APP_LABEL.removeprefix('V')}.0")


if __name__ == "__main__":
    unittest.main()

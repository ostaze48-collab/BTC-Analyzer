import unittest
from pathlib import Path

from app.version import APP_LABEL, APP_VERSION


class UiSyncTests(unittest.TestCase):
    def test_index_loads_all_current_version_layers(self):
        html = Path("app/static/index.html").read_text(encoding="utf-8")
        self.assertIn(APP_LABEL, html)
        for script in (
            "v22.js", "v23.js", "v24.js", "v25.js", "v26.js", "v27.js", "v28.js",
            "v29.js", "v30.js", "v31.js", "v32.js", "v33.js", "v34.js", "v35.js", "v36.js", "v37.js", "v38.js",
        ):
            self.assertIn(f'/static/{script}', html)

    def test_v35_still_reads_strict_paper_review(self):
        v35 = Path("app/static/v35.js").read_text(encoding="utf-8")
        self.assertIn("/api/strict-paper-review", v35)
        self.assertIn("Strict Paper Review Protocol", v35)

    def test_v36_still_reads_research_evidence_history(self):
        v36 = Path("app/static/v36.js").read_text(encoding="utf-8")
        self.assertIn("/api/research-history", v36)
        self.assertIn("Research Evidence History", v36)

    def test_v37_still_reads_evidence_stability_window(self):
        v37 = Path("app/static/v37.js").read_text(encoding="utf-8")
        self.assertIn("/api/evidence-stability", v37)
        self.assertIn("Evidence Stability Window", v37)

    def test_latest_ui_reads_multiday_stability_ladder(self):
        v38 = Path("app/static/v38.js").read_text(encoding="utf-8")
        self.assertIn("/api/version", v38)
        self.assertIn("/api/research-history", v38)
        self.assertIn("Multi‑Day Stability Ladder", v38)
        self.assertIn("L3_168H", v38)
        self.assertIn("activeDays", v38)
        self.assertEqual(APP_VERSION, "1.28.0")
        self.assertEqual(APP_LABEL, "V1.28")


if __name__ == "__main__":
    unittest.main()

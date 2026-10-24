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
            "stable.js",
        ):
            self.assertIn(f'/static/{script}', html)
        self.assertIn('/static/stable.css', html)

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

    def test_v38_still_reads_multiday_stability_ladder(self):
        v38 = Path("app/static/v38.js").read_text(encoding="utf-8")
        self.assertIn("/api/research-history", v38)
        self.assertIn("Multi‑Day Stability Ladder", v38)

    def test_stable_ui_preserves_results_and_mobile_experiment_mode(self):
        stable = Path("app/static/stable.js").read_text(encoding="utf-8")
        css = Path("app/static/stable.css").read_text(encoding="utf-8")
        self.assertIn("btc_ai_trader_v2_stable_results", stable)
        self.assertIn("PRE_RESET", stable)
        self.assertIn("/api/trades?limit=200", stable)
        self.assertIn("application/json", stable)
        self.assertIn("stableResultsSection", stable)
        self.assertIn("@media(max-width:900px)", css)
        self.assertIn("stable-brain-results", css)
        self.assertEqual(APP_VERSION, "2.0.0")
        self.assertEqual(APP_LABEL, "V2.0 STABLE")


if __name__ == "__main__":
    unittest.main()

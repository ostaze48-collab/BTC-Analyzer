import unittest
from pathlib import Path

from app.config import settings
from app.version import APP_LABEL


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "app" / "static" / "index.html"
V22 = ROOT / "app" / "static" / "v22.js"


class InterfaceSyncTests(unittest.TestCase):
    def test_index_uses_current_version_and_all_intelligence_layers(self):
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn(f"BTC AI Trader {APP_LABEL}", html)
        self.assertIn(f"<span>{APP_LABEL}</span>", html)
        for script in ("v22.js", "v23.js", "v24.js", "v25.js", "v26.js"):
            self.assertEqual(html.count(f'/static/{script}'), 1, script)
        self.assertIn("Adaptive", html)
        self.assertIn("Historical", html)
        self.assertIn("Deep Evidence", html)

    def test_all_configured_timeframes_are_available_on_chart(self):
        html = INDEX.read_text(encoding="utf-8")
        for tf in settings.intervals:
            self.assertIn(f'data-tf="{tf}"', html, tf)

    def test_no_legacy_dynamic_ui_chain_remains(self):
        js = V22.read_text(encoding="utf-8")
        self.assertNotIn("/static/v23.js", js)
        self.assertNotIn("createElement('script')", js)
        self.assertNotIn('createElement("script")', js)


if __name__ == "__main__":
    unittest.main()

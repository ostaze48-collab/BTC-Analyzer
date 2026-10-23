import unittest

from app.brains import PROFILES
from app.engine import TradingEngine
from app.historical_archive import HistoricalArchive, PROFILE_DAYS, _parse


class HistoricalArchiveTests(unittest.TestCase):
    def test_profiles_match_strategy_horizons_and_anchors(self):
        self.assertGreaterEqual(PROFILE_DAYS["SCALP"]["5m"], 30)
        self.assertGreaterEqual(PROFILE_DAYS["INTRADAY"]["15m"], 90)
        self.assertGreaterEqual(PROFILE_DAYS["INTRADAY"]["30m"], 180)
        self.assertGreaterEqual(PROFILE_DAYS["SWING"]["4h"], 365 * 4)
        self.assertGreaterEqual(PROFILE_DAYS["SWING"]["1d"], 365 * 8)
        for profile in PROFILES:
            self.assertIn(profile.anchor, PROFILE_DAYS[profile.name], f"missing deep anchor for {profile.name}")

    def test_archive_is_shadow_and_empty_before_lazy_load(self):
        archive = HistoricalArchive()
        state = archive.state("SCALP")
        self.assertEqual(state["status"], "NOT_LOADED")
        self.assertEqual(state["weight_in_master"], 0.0)
        self.assertEqual(archive.history("SCALP"), {})

    def test_parse_marks_only_finished_candles_closed(self):
        row = [1000, "1", "2", "0.5", "1.5", "10", 1999]
        self.assertTrue(_parse(row, now_ms=2000)["closed"])
        self.assertFalse(_parse(row, now_ms=1500)["closed"])

    def test_merge_history_deduplicates_and_prefers_current(self):
        archive = [
            {"time": 1, "close": 10.0, "closed": True},
            {"time": 2, "close": 20.0, "closed": True},
        ]
        current = [
            {"time": 2, "close": 21.0, "closed": True},
            {"time": 3, "close": 30.0, "closed": True},
        ]
        merged = TradingEngine._merge_history(archive, current)
        self.assertEqual([x["time"] for x in merged], [1, 2, 3])
        self.assertEqual(merged[1]["close"], 21.0)


if __name__ == "__main__":
    unittest.main()

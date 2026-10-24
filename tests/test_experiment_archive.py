import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.experiment_archive import ExperimentArchive, build_experiment_snapshot


class FakeDb:
    def __init__(self):
        self._trades = [
            {
                "id": 1, "status": "CLOSED", "brain": "SCALP", "market_regime": "TRENDING_UP",
                "direction": "LONG", "opened_at": "2026-01-01T00:00:00+00:00", "closed_at": "2026-01-01T01:00:00+00:00",
                "realized_pnl": 12.0, "risk_budget": 8.0, "exit_reason": "TP",
            },
            {
                "id": 2, "status": "CLOSED", "brain": "INTRADAY", "market_regime": "RANGE",
                "direction": "SHORT", "opened_at": "2026-01-01T02:00:00+00:00", "closed_at": "2026-01-01T05:00:00+00:00",
                "realized_pnl": -4.0, "risk_budget": 8.0, "exit_reason": "SL",
            },
        ]

    def stats(self):
        return {
            "starting_capital": 1000.0, "capital": 1008.0, "net_pnl": 8.0,
            "trades": 2, "wins": 1, "losses": 1, "win_rate": 50.0,
            "profit_factor": 3.0, "max_drawdown_pct": 0.4,
        }

    def recent_trades(self, limit):
        return list(reversed(self._trades))[:limit]


class ExperimentArchiveTests(unittest.TestCase):
    def test_snapshot_contains_equity_r_and_breakdowns(self):
        snap = build_experiment_snapshot(FakeDb(), "2.0.0", "Trial A")
        self.assertEqual(snap["label"], "Trial A")
        self.assertEqual(snap["status"], "HAS_RESULTS")
        self.assertEqual(snap["metrics"]["trades"], 2)
        self.assertAlmostEqual(snap["metrics"]["avg_r"], 0.5)
        self.assertAlmostEqual(snap["metrics"]["net_r"], 1.0)
        self.assertEqual(snap["equity_curve"][-1]["equity"], 1008.0)
        self.assertEqual({row["name"] for row in snap["by_brain"]}, {"SCALP", "INTRADAY"})
        self.assertTrue(snap["paper_only"])

    def test_sqlite_fallback_saves_and_lists_archives(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=False):
            old = os.environ.pop("DATABASE_URL", None)
            try:
                path = str(Path(tmp) / "archive.db")
                archive = ExperimentArchive(path)
                archive.init()
                self.assertEqual(archive.backend, "sqlite")
                self.assertFalse(archive.persistent_across_redeploys)
                snap = build_experiment_snapshot(FakeDb(), "2.0.0", "Saved Test")
                saved = archive.save(snap)
                rows = archive.list(10)
                self.assertGreater(saved["id"], 0)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["label"], "Saved Test")
                self.assertEqual(rows[0]["metrics"]["net_pnl"], 8.0)
                self.assertTrue(rows[0]["paper_only"])
                archive.close()
            finally:
                if old is not None:
                    os.environ["DATABASE_URL"] = old


if __name__ == "__main__":
    unittest.main()

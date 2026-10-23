import os
import tempfile
import unittest

from app.research_history import ResearchHistoryStore, compact_snapshot, summarize_research_history


def report(status="EVIDENCE_BUILDING", score=45.0, passed=1, target=False, feature=False):
    mandatory = [
        {"id": "core_execution_readiness", "passed": passed >= 1},
        {"id": "target_evidence_consensus", "passed": passed >= 2},
        {"id": "real_execution_interlock", "passed": passed >= 3},
    ]
    failed = [g["id"] for g in mandatory if not g["passed"]]
    return {
        "status": status,
        "research_score": score,
        "mandatory_gates": mandatory,
        "failed_mandatory_gates": failed,
        "core_readiness": {"status": "SHADOW_READY", "score": score},
        "target_evidence": {"status": "PASS" if target else "OPEN", "all_gates_passed": target},
        "feature_research": {"incremental_oos_evidence": feature},
        "paper_only": True,
        "real_execution_eligibility": False,
    }


class ResearchHistoryPureTests(unittest.TestCase):
    def test_compact_snapshot_keeps_research_not_execution_state(self):
        row = compact_snapshot(report(), {"trades": 20, "profit_factor": 1.2, "max_drawdown_pct": 4.0}, "1.25.0")
        self.assertEqual(row["paper_trades"], 20)
        self.assertTrue(row["paper_only"])
        self.assertFalse(row["real_execution_eligibility"])

    def test_two_points_are_not_enough_for_trend_claim(self):
        rows = [
            {"id": 1, "captured_at": "2026-01-01T00:00:00+00:00", "status": "DATA_BUILDING", "research_score": 20, "mandatory_passed": 1, "mandatory_total": 3},
            {"id": 2, "captured_at": "2026-01-01T01:00:00+00:00", "status": "EVIDENCE_BUILDING", "research_score": 40, "mandatory_passed": 2, "mandatory_total": 3},
        ]
        summary = summarize_research_history(rows)
        self.assertEqual(summary["trend"], "INSUFFICIENT_HISTORY")
        self.assertFalse(summary["real_execution_eligibility"])

    def test_regression_has_precedence_on_latest_step(self):
        rows = [
            {"id": 1, "captured_at": "2026-01-01T00:00:00+00:00", "status": "DATA_BUILDING", "research_score": 20, "mandatory_passed": 1, "mandatory_total": 3},
            {"id": 2, "captured_at": "2026-01-01T01:00:00+00:00", "status": "SHADOW_VALIDATED", "research_score": 70, "mandatory_passed": 3, "mandatory_total": 3},
            {"id": 3, "captured_at": "2026-01-01T02:00:00+00:00", "status": "EVIDENCE_BUILDING", "research_score": 50, "mandatory_passed": 2, "mandatory_total": 3},
        ]
        summary = summarize_research_history(rows)
        self.assertEqual(summary["trend"], "REGRESSING")
        self.assertEqual(summary["stage_regressions"], 1)


class ResearchHistoryStoreTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.store = ResearchHistoryStore(self.path)
        self.store.init()

    def tearDown(self):
        self.store.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def test_same_material_state_is_throttled(self):
        first = self.store.record(report(), {"trades": 10}, "1.25.0", min_interval_seconds=3600)
        second = self.store.record(report(), {"trades": 10}, "1.25.0", min_interval_seconds=3600)
        self.assertTrue(first["recorded"])
        self.assertFalse(second["recorded"])
        self.assertEqual(len(self.store.history()), 1)

    def test_material_change_records_even_inside_interval(self):
        self.store.record(report(score=40), {"trades": 10}, "1.25.0", min_interval_seconds=3600)
        changed = self.store.record(
            report(status="SHADOW_VALIDATED", score=60, passed=2, target=True),
            {"trades": 11}, "1.25.0", min_interval_seconds=3600,
        )
        self.assertTrue(changed["recorded"])
        self.assertEqual(len(self.store.history()), 2)

    def test_clear_starts_new_research_epoch(self):
        self.store.record(report(), {"trades": 10}, "1.25.0", min_interval_seconds=0)
        self.store.clear()
        self.assertEqual(self.store.history(), [])


if __name__ == "__main__":
    unittest.main()

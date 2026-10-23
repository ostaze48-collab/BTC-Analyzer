import os
import tempfile
import unittest

from app.research_history import ResearchHistoryStore, compact_snapshot, summarize_research_history


def unified(status="EVIDENCE_BUILDING", score=45.0, passed=1, target=False, feature=False):
    mandatory = [
        {"id": "core_execution_readiness", "passed": passed >= 1},
        {"id": "target_evidence_consensus", "passed": passed >= 2},
        {"id": "real_execution_interlock", "passed": passed >= 3},
    ]
    failed = [g["id"] for g in mandatory if not g["passed"]]
    return {
        "status": status, "research_score": score,
        "mandatory_gates": mandatory, "failed_mandatory_gates": failed,
        "core_readiness": {"status": "SHADOW_READY", "score": score},
        "target_evidence": {"status": "PASS" if target else "OPEN", "all_gates_passed": target},
        "feature_research": {"incremental_oos_evidence": feature},
        "paper_only": True, "real_execution_eligibility": False,
    }


def strict(passed=False, gates_passed=2):
    gates = [{"id": f"g{i}", "passed": i < gates_passed} for i in range(6)]
    return {
        "status": "STRICT_PAPER_REVIEW_PASSED" if passed else "STRICT_PAPER_REVIEW_BLOCKED",
        "gates": gates, "paper_only": True, "real_execution_eligibility": False,
    }


class ResearchHistoryPureTests(unittest.TestCase):
    def test_compact_snapshot_keeps_strict_paper_context_without_execution_permission(self):
        row = compact_snapshot(
            unified(), strict(True, 6),
            {"trades": 100, "profit_factor": 1.2, "max_drawdown_pct": 4.0}, "1.26.0",
        )
        self.assertEqual(row["paper_trades"], 100)
        self.assertTrue(row["strict_pass"])
        self.assertEqual(row["strict_gates_passed"], 6)
        self.assertTrue(row["paper_only"])
        self.assertFalse(row["real_execution_eligibility"])

    def test_two_points_are_not_enough_for_trend_claim(self):
        rows = [
            {"id":1,"captured_at":"2026-01-01T00:00:00+00:00","status":"DATA_BUILDING","research_score":20,"mandatory_passed":1,"mandatory_total":3,"strict_pass":False},
            {"id":2,"captured_at":"2026-01-01T01:00:00+00:00","status":"EVIDENCE_BUILDING","research_score":40,"mandatory_passed":2,"mandatory_total":3,"strict_pass":False},
        ]
        s = summarize_research_history(rows)
        self.assertEqual(s["trend"], "INSUFFICIENT_HISTORY")
        self.assertFalse(s["real_execution_eligibility"])

    def test_strict_paper_pass_to_blocked_is_regression(self):
        rows = [
            {"id":1,"captured_at":"2026-01-01T00:00:00+00:00","status":"STRICT_PAPER_REVIEW_CANDIDATE","research_score":80,"mandatory_passed":3,"mandatory_total":3,"strict_pass":False},
            {"id":2,"captured_at":"2026-01-01T01:00:00+00:00","status":"STRICT_PAPER_REVIEW_CANDIDATE","research_score":82,"mandatory_passed":3,"mandatory_total":3,"strict_pass":True,"strict_status":"STRICT_PAPER_REVIEW_PASSED"},
            {"id":3,"captured_at":"2026-01-01T02:00:00+00:00","status":"STRICT_PAPER_REVIEW_CANDIDATE","research_score":82,"mandatory_passed":3,"mandatory_total":3,"strict_pass":False,"strict_status":"STRICT_PAPER_REVIEW_BLOCKED"},
        ]
        s = summarize_research_history(rows)
        self.assertEqual(s["trend"], "REGRESSING")
        self.assertGreaterEqual(s["stage_regressions"], 1)


class ResearchHistoryStoreTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3"); os.close(fd)
        self.store = ResearchHistoryStore(self.path); self.store.init()

    def tearDown(self):
        try: self.store.close()
        except Exception: pass
        try: os.remove(self.path)
        except OSError: pass

    def test_same_material_state_is_throttled(self):
        a = self.store.record(unified(), strict(), {"trades":10}, "1.26.0", 3600)
        b = self.store.record(unified(), strict(), {"trades":10}, "1.26.0", 3600)
        self.assertTrue(a["recorded"]); self.assertFalse(b["recorded"])
        self.assertEqual(len(self.store.history()), 1)

    def test_strict_status_change_records_inside_throttle(self):
        self.store.record(unified(), strict(False), {"trades":100}, "1.26.0", 3600)
        b = self.store.record(unified(), strict(True, 6), {"trades":100}, "1.26.0", 3600)
        self.assertTrue(b["recorded"])
        self.assertEqual(len(self.store.history()), 2)

    def test_clear_starts_new_research_epoch(self):
        self.store.record(unified(), strict(), {"trades":10}, "1.26.0", 0)
        self.store.clear(); self.assertEqual(self.store.history(), [])

    def test_store_can_reopen_after_close(self):
        self.store.record(unified(), strict(), {"trades":10}, "1.26.0", 0)
        self.store.close(); self.store.init()
        self.assertEqual(len(self.store.history()), 1)


if __name__ == "__main__":
    unittest.main()

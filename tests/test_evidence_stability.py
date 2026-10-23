import unittest
from datetime import datetime, timedelta, timezone

from app.evidence_stability import evidence_stability_gate


def row(i, start, trades, strict=True, stage="STRICT_PAPER_REVIEW_CANDIDATE", mandatory=3, total=3, real=False):
    return {
        "id": i,
        "captured_at": (start + timedelta(hours=i * 4)).isoformat(),
        "status": stage,
        "research_score": 80.0,
        "mandatory_passed": mandatory,
        "mandatory_total": total,
        "strict_pass": strict,
        "strict_status": "STRICT_PAPER_REVIEW_PASSED" if strict else "STRICT_PAPER_REVIEW_BLOCKED",
        "paper_trades": trades,
        "real_execution_eligibility": real,
    }


class EvidenceStabilityTests(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_empty_history_is_blocked(self):
        r = evidence_stability_gate({"snapshots": []})
        self.assertEqual(r["status"], "STABILITY_WINDOW_BLOCKED")
        self.assertFalse(r["real_execution_eligibility"])

    def test_time_without_new_trades_cannot_fake_stability(self):
        rows = [row(i, self.start, 120, strict=True) for i in range(8)]
        r = evidence_stability_gate({"snapshots": rows})
        self.assertEqual(r["status"], "STABILITY_WINDOW_BLOCKED")
        self.assertIn("new_paper_trades", r["failed_gates"])

    def test_full_time_and_trade_window_can_pass_but_remains_paper_only(self):
        rows = [row(i, self.start, 100 + i * 5, strict=True) for i in range(8)]
        r = evidence_stability_gate({"snapshots": rows})
        self.assertEqual(r["status"], "STABILITY_WINDOW_PASSED")
        self.assertEqual(r["failed_gates"], [])
        self.assertGreaterEqual(r["window"]["new_paper_trades"], 20)
        self.assertTrue(r["paper_only"])
        self.assertFalse(r["automatic_real_execution"])
        self.assertFalse(r["real_execution_eligibility"])
        self.assertFalse(r["live_execution_enabled"])
        self.assertFalse(r["target_auto_apply"])

    def test_pass_to_blocked_inside_window_breaks_stability(self):
        rows = [row(i, self.start, 100 + i * 5, strict=True) for i in range(8)]
        rows[5]["strict_pass"] = False
        rows[5]["strict_status"] = "STRICT_PAPER_REVIEW_BLOCKED"
        r = evidence_stability_gate({"snapshots": rows})
        self.assertEqual(r["status"], "STABILITY_WINDOW_BLOCKED")
        self.assertIn("no_recent_regression", r["failed_gates"])

    def test_real_execution_flag_breaks_interlock(self):
        rows = [row(i, self.start, 100 + i * 5, strict=True) for i in range(8)]
        rows[-2]["real_execution_eligibility"] = True
        r = evidence_stability_gate({"snapshots": rows})
        self.assertIn("real_execution_interlock", r["failed_gates"])
        self.assertFalse(r["real_execution_eligibility"])


if __name__ == "__main__":
    unittest.main()

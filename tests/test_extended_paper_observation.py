import unittest

from app.db import Database
from app.extended_paper_observation import extended_paper_observation


def review_payload(n: int, passed: bool = True, mean30: float = 0.20):
    return {
        "status": "STRICT_PAPER_REVIEW_PASSED" if passed else "STRICT_PAPER_REVIEW_BLOCKED",
        "eligible_samples": n,
        "windows": {
            "30": {"mean_r": mean30},
            "60": {"mean_r": 0.18},
            "100": {"mean_r": 0.16},
        },
        "paper_only": True,
        "automatic_real_execution": False,
        "real_execution_eligibility": False,
        "live_execution_enabled": False,
        "target_auto_apply": False,
    }


class ReviewSnapshotDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.db.init()

    def tearDown(self):
        self.db.conn.close()

    def test_first_checkpoint_needs_100_eligible_samples(self):
        r = self.db.record_review_snapshot(review_payload(99), min_trade_gap=20)
        self.assertFalse(r["recorded"])
        self.assertEqual(r["reason"], "NEED_100_ELIGIBLE")
        self.assertEqual(self.db.review_snapshots(), [])

    def test_polling_same_sample_count_cannot_manufacture_persistence(self):
        first = self.db.record_review_snapshot(review_payload(100), min_trade_gap=20)
        again = self.db.record_review_snapshot(review_payload(100), min_trade_gap=20)
        self.assertTrue(first["recorded"])
        self.assertFalse(again["recorded"])
        self.assertEqual(again["reason"], "NO_NEW_ELIGIBLE_TRADES")
        self.assertEqual(len(self.db.review_snapshots()), 1)

    def test_checkpoint_requires_twenty_new_trades(self):
        self.assertTrue(self.db.record_review_snapshot(review_payload(100))["recorded"])
        too_soon = self.db.record_review_snapshot(review_payload(119))
        enough = self.db.record_review_snapshot(review_payload(120))
        self.assertFalse(too_soon["recorded"])
        self.assertEqual(too_soon["reason"], "CHECKPOINT_GAP_NOT_REACHED")
        self.assertTrue(enough["recorded"])
        self.assertEqual([x["eligible_samples"] for x in self.db.review_snapshots()], [100, 120])

    def test_reset_clears_persistence_snapshots(self):
        self.db.record_review_snapshot(review_payload(100))
        self.db.reset()
        self.assertEqual(self.db.review_snapshots(), [])


class ExtendedPaperObservationTests(unittest.TestCase):
    @staticmethod
    def history(statuses=(True, True, True, True), means=(0.20, 0.18, 0.17, 0.16)):
        rows = []
        for i, (passed, mean) in enumerate(zip(statuses, means)):
            n = 100 + i * 20
            payload = review_payload(n, passed=passed, mean30=mean)
            rows.append({
                "id": i + 1,
                "eligible_samples": n,
                "status": payload["status"],
                "captured_at": f"2026-10-{20+i:02d}T00:00:00+00:00",
                "payload": payload,
            })
        return rows

    def test_four_spaced_passes_confirm_paper_persistence_only(self):
        current = review_payload(160, passed=True, mean30=0.16)
        r = extended_paper_observation(current, self.history())
        self.assertEqual(r["status"], "PERSISTENCE_CONFIRMED_PAPER_ONLY")
        self.assertEqual(r["trade_span"], 60)
        self.assertEqual(r["failed_gates"], [])
        self.assertEqual(r["next_stage"], "CONTINUE_LONG_HORIZON_PAPER_MONITORING")
        self.assertFalse(r["real_execution_eligibility"])
        self.assertFalse(r["live_execution_enabled"])
        self.assertFalse(r["target_auto_apply"])

    def test_one_snapshot_can_never_confirm_persistence(self):
        h = self.history()[:1]
        r = extended_paper_observation(review_payload(100), h)
        self.assertNotEqual(r["status"], "PERSISTENCE_CONFIRMED_PAPER_ONLY")
        self.assertIn("checkpoint_count", r["failed_gates"])
        self.assertIn("trade_span", r["failed_gates"])

    def test_recent_failed_checkpoint_breaks_confirmation(self):
        h = self.history(statuses=(True, True, False, True))
        r = extended_paper_observation(review_payload(160), h)
        self.assertIn("recent_three_pass", r["failed_gates"])
        self.assertNotEqual(r["status"], "PERSISTENCE_CONFIRMED_PAPER_ONLY")

    def test_persistent_recent_edge_decay_breaks_confirmation(self):
        h = self.history(means=(0.20, 0.20, 0.20, 0.02))
        r = extended_paper_observation(review_payload(160, mean30=0.02), h)
        self.assertIn("persistent_recent_edge", r["failed_gates"])

    def test_current_strict_review_must_still_pass(self):
        r = extended_paper_observation(review_payload(160, passed=False), self.history())
        self.assertIn("current_review_pass", r["failed_gates"])

    def test_warning_says_persistence_is_not_independent_oos(self):
        r = extended_paper_observation(review_payload(160), self.history())
        self.assertIn("not independent OOS evidence", r["independence_warning"])
        self.assertEqual(r["evidence_type"], "TEMPORAL_PERSISTENCE_DIAGNOSTIC")


if __name__ == "__main__":
    unittest.main()

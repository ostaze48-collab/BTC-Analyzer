import unittest
from datetime import datetime, timedelta, timezone

from app.stability_ladder import stability_ladder


def snapshots(hours=168, step_hours=3, trades_per_step=2, strict=True):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = []
    count = 110
    steps = int(hours / step_hours) + 1
    for i in range(steps):
        count += trades_per_step
        rows.append({
            "id": i + 1,
            "captured_at": (start + timedelta(hours=i * step_hours)).isoformat(),
            "status": "STRICT_PAPER_REVIEW_CANDIDATE",
            "mandatory_passed": 3,
            "mandatory_total": 3,
            "strict_pass": strict,
            "strict_status": "STRICT_PAPER_REVIEW_PASSED" if strict else "STRICT_PAPER_REVIEW_BLOCKED",
            "paper_trades": count,
            "real_execution_eligibility": False,
        })
    return rows


class StabilityLadderTests(unittest.TestCase):
    def test_no_history_is_blocked(self):
        r = stability_ladder({"snapshots": []})
        self.assertEqual(r["highest_level"], 0)
        self.assertEqual(r["status"], "MULTIDAY_STABILITY_BLOCKED")
        self.assertFalse(r["real_execution_eligibility"])

    def test_24h_only_does_not_jump_to_longer_levels(self):
        rows = snapshots(hours=24, step_hours=3, trades_per_step=4)
        r = stability_ladder({"snapshots": rows})
        self.assertEqual(r["highest_level"], 1)
        self.assertTrue(r["levels"][0]["passed"])
        self.assertFalse(r["levels"][1]["passed"])

    def test_seven_day_distributed_activity_can_reach_level3(self):
        rows = snapshots(hours=168, step_hours=3, trades_per_step=2)
        r = stability_ladder({"snapshots": rows})
        self.assertEqual(r["highest_level"], 3)
        self.assertEqual(r["status"], "STABILITY_7D_CONFIRMED")
        self.assertGreaterEqual(r["levels"][2]["metrics"]["active_trade_days"], 6)
        self.assertFalse(r["automatic_real_execution"])
        self.assertFalse(r["real_execution_eligibility"])
        self.assertFalse(r["target_auto_apply"])

    def test_one_day_burst_cannot_fake_seven_day_activity(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = []
        trades = 110
        for day in range(8):
            for point in range(5):
                if day == 7:
                    trades += 8
                rows.append({
                    "id": len(rows) + 1,
                    "captured_at": (start + timedelta(days=day, hours=point * 3)).isoformat(),
                    "status": "STRICT_PAPER_REVIEW_CANDIDATE",
                    "mandatory_passed": 3, "mandatory_total": 3,
                    "strict_pass": True, "strict_status": "STRICT_PAPER_REVIEW_PASSED",
                    "paper_trades": trades, "real_execution_eligibility": False,
                })
        r = stability_ladder({"snapshots": rows})
        self.assertLess(r["highest_level"], 3)
        self.assertIn("active_trade_days", r["levels"][2]["failed_gates"])

    def test_levels_are_sequential(self):
        rows = snapshots(hours=168, step_hours=3, trades_per_step=2)
        # Break the last 24h strict evidence so L1 fails; longer historical data must not skip it.
        for row in rows[-9:]:
            row["strict_pass"] = False
            row["strict_status"] = "STRICT_PAPER_REVIEW_BLOCKED"
        r = stability_ladder({"snapshots": rows})
        self.assertEqual(r["highest_level"], 0)


if __name__ == "__main__":
    unittest.main()

import unittest

from app.historical_validation import validate_historical_analogs


def sample(i: int, good: bool) -> dict:
    hit = 82.0 if good else 28.0
    stop = 18.0 if good else 72.0
    pnl = 8.0 if good else -6.0
    return {
        "trade_id": i,
        "opened_at": f"2026-01-{(i % 28) + 1:02d}T00:00:{i % 60:02d}Z",
        "direction": "LONG",
        "risk_budget": 10.0,
        "realized_pnl": pnl,
        "features": {
            "historical_analogs": {
                "status": "READY",
                "avg_similarity_pct": 78.0 if good else 55.0,
                "stop_before_1r_pct": stop,
                "hit_1r_pct": hit,
                "hit_2r_pct": hit - 8,
                "hit_3r_pct": hit - 18,
                "hit_4r_pct": hit - 28,
                "hit_5r_pct": hit - 38,
                "avg_mfe_r": 3.2 if good else 0.7,
                "avg_mae_r": 0.4 if good else 1.4,
                "matches": 20,
            }
        },
    }


class HistoricalValidationTests(unittest.TestCase):
    def test_insufficient_samples_never_claim_useful(self):
        result = validate_historical_analogs([sample(i, i % 2 == 0) for i in range(20)])
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertFalse(result["useful"])
        self.assertEqual(result["weight_in_master"], 0.0)

    def test_oos_relationship_can_be_detected_without_auto_apply(self):
        rows = [sample(i, i % 4 != 0) for i in range(80)]
        result = validate_historical_analogs(rows)
        self.assertIn(result["status"], {"USEFUL_OOS_EVIDENCE", "MIXED_EVIDENCE"})
        self.assertGreaterEqual(result["useful_metric_count"], 1)
        self.assertEqual(result["weight_in_master"], 0.0)
        self.assertFalse(result["auto_apply"])


if __name__ == "__main__":
    unittest.main()

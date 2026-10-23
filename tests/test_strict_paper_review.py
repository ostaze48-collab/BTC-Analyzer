import unittest

from app.strict_paper_review import strict_paper_review


class StrictPaperReviewTests(unittest.TestCase):
    def _unified(self, allowed=True, unsafe=False):
        return {
            "status": "STRICT_PAPER_REVIEW_CANDIDATE" if allowed else "EVIDENCE_BUILDING",
            "strict_paper_review_allowed": allowed,
            "paper_only": not unsafe,
            "live_execution_enabled": unsafe,
            "real_execution_eligibility": unsafe,
            "automatic_real_execution": unsafe,
        }

    def _samples(self, n=100, degrading=False):
        rows = []
        for i in range(n):
            if degrading and i >= max(0, n - 30):
                r = -0.15 if i % 2 else 0.05
            else:
                r = 0.6 if i % 3 != 2 else -0.3
            rows.append({
                "trade_id": i + 1,
                "opened_at": f"{i:05d}",
                "brain": ("SCALP", "INTRADAY", "SWING")[i % 3],
                "market_regime": ("TREND_UP", "RANGE", "TREND_DOWN")[i % 3],
                "risk_budget": 100.0,
                "realized_pnl": r * 100.0,
            })
        return rows

    def test_stable_100_trade_sample_passes_strict_paper_review(self):
        r = strict_paper_review(self._unified(), self._samples())
        self.assertEqual(r["status"], "STRICT_PAPER_REVIEW_PASSED")
        self.assertEqual(r["failed_gates"], [])
        self.assertEqual(r["next_stage"], "EXTENDED_PAPER_OBSERVATION")
        self.assertTrue(r["paper_only"])
        self.assertFalse(r["real_execution_eligibility"])
        self.assertFalse(r["live_execution_enabled"])
        self.assertFalse(r["target_auto_apply"])

    def test_recent_degradation_blocks_even_if_long_history_was_good(self):
        r = strict_paper_review(self._unified(), self._samples(degrading=True))
        self.assertEqual(r["status"], "STRICT_PAPER_REVIEW_BLOCKED")
        self.assertIn("window_30", r["failed_gates"])
        self.assertIn("recent_decay", r["failed_gates"])

    def test_insufficient_sample_cannot_pass(self):
        r = strict_paper_review(self._unified(), self._samples(60))
        self.assertEqual(r["status"], "STRICT_PAPER_REVIEW_BLOCKED")
        self.assertIn("window_100", r["failed_gates"])
        self.assertLess(r["eligible_samples"], r["minimum_samples"])

    def test_unified_gate_must_explicitly_allow_strict_review(self):
        r = strict_paper_review(self._unified(allowed=False), self._samples())
        self.assertIn("unified_readiness", r["failed_gates"])
        self.assertEqual(r["next_stage"], "CONTINUE_PAPER_COLLECTION")

    def test_any_real_execution_flag_breaks_paper_interlock(self):
        r = strict_paper_review(self._unified(allowed=True, unsafe=True), self._samples())
        self.assertIn("paper_only_interlock", r["failed_gates"])
        self.assertFalse(r["real_execution_eligibility"])
        self.assertFalse(r["live_execution_enabled"])

    def test_windows_are_explicitly_not_independent_oos_evidence(self):
        r = strict_paper_review(self._unified(), self._samples())
        self.assertIn("not independent OOS evidence", r["independence_warning"])
        self.assertEqual(r["window_scheme"], "OVERLAPPING_RECENT_30_60_100_DIAGNOSTIC")


if __name__ == "__main__":
    unittest.main()

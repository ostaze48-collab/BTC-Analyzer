import unittest

from app.candidate_evidence import build_candidate_row


class CandidateEvidenceTests(unittest.TestCase):
    def proposal(self, brain="INTRADAY"):
        return {
            "brain": brain, "direction": "LONG", "anchor": "15m",
            "risk_gate": "PASSED", "confidence": 82, "safety_score": 79,
            "profit_score": 72, "final_score": 80, "rr": 2.2, "ev_pct": 0.6,
            "entry": 100.0, "stop_loss": 98.0, "tp1": 102.0, "tp2": 104.0, "tp3": 106.0,
        }

    def analog(self):
        return {
            "status": "READY", "matches": 20, "quality": "STRONG",
            "hit_1r_pct": 76, "hit_2r_pct": 64, "hit_3r_pct": 51,
            "hit_4r_pct": 38, "hit_5r_pct": 27,
            "stop_before_1r_pct": 29, "avg_similarity_pct": 74,
        }

    def test_candidate_row_combines_analog_and_brain_regime_history_without_master_weight(self):
        learning = {"brain_regime": [{
            "brain": "INTRADAY", "regime": "TREND_UP", "trades": 22,
            "win_rate": 61, "profit_factor": 1.65, "net_pnl": 40,
            "avg_mfe_pct": 2.2, "avg_mae_pct": 0.8,
        }]}
        row = build_candidate_row(
            self.proposal(), self.analog(), learning, {"regime": "TREND_UP"},
            {"status": "READY", "bars_loaded": 5000},
        )
        self.assertEqual(row["brain"], "INTRADAY")
        self.assertEqual(row["analog"]["matches"], 20)
        self.assertGreater(row["evidence_score"], 60)
        self.assertEqual(row["master_weight"], 0.0)
        self.assertEqual(row["brain_regime_history"]["status"], "READY")

    def test_small_or_missing_history_does_not_fake_large_evidence(self):
        row = build_candidate_row(
            self.proposal("SCALP"), {"status": "NO_CLOSE_ANALOGS", "matches": 0},
            {"brain_regime": []}, {"regime": "RANGE"}, {"status": "NOT_LOADED"},
        )
        self.assertEqual(row["brain_regime_history"]["status"], "NO_SAMPLE")
        self.assertEqual(row["master_weight"], 0.0)
        self.assertLess(row["evidence_score"], 80)

    def test_wait_brain_is_visible_but_gets_no_current_evidence_score(self):
        p = self.proposal("SWING")
        p.update({"direction": "WAIT", "risk_gate": "REJECTED", "confidence": 58, "safety_score": 0})
        row = build_candidate_row(
            p, self.analog(),
            {"brain_regime": [{"brain": "SWING", "regime": "RANGE", "trades": 20, "win_rate": 70, "profit_factor": 2.0}]},
            {"regime": "RANGE"}, {"status": "READY", "bars_loaded": 9000},
        )
        self.assertEqual(row["direction"], "WAIT")
        self.assertEqual(row["evidence_score"], 0.0)
        self.assertEqual(row["evidence_grade"], "WAIT")
        self.assertEqual(row["master_weight"], 0.0)


if __name__ == "__main__":
    unittest.main()

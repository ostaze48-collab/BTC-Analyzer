import unittest

from app.evidence_score import build_candidate_evidence


class EvidenceScoreTests(unittest.TestCase):
    def setUp(self):
        self.proposal = {"brain": "INTRADAY", "direction": "LONG"}
        self.regime = {"regime": "TREND_UP"}
        self.local = {
            "status": "READY", "matches": 20, "hit_2r_pct": 72, "hit_3r_pct": 58,
            "stop_before_1r_pct": 24, "avg_similarity_pct": 76,
        }
        self.deep = {
            "status": "READY", "matches": 28, "hit_2r_pct": 68, "hit_3r_pct": 53,
            "stop_pct": 29, "avg_similarity_pct": 70,
        }
        self.learning = {"brain_regime": [{
            "brain": "INTRADAY", "regime": "TREND_UP", "trades": 30,
            "win_rate": 63, "profit_factor": 1.7, "avg_mfe_pct": 2.1, "avg_mae_pct": 0.8,
        }]}

    def test_score_is_shadow_only_even_with_strong_evidence(self):
        result = build_candidate_evidence(
            self.proposal, self.regime, self.local, self.deep, self.learning,
            {"status": "USEFUL_OOS_EVIDENCE"}, {"status": "READY", "eligible_count": 3},
        )
        self.assertEqual(result["status"], "READY")
        self.assertGreater(result["score"], 60)
        self.assertEqual(result["master_weight"], 0.0)
        self.assertEqual(result["reliability"], "OOS_SUPPORTED")

    def test_missing_evidence_collects_without_claiming_edge(self):
        result = build_candidate_evidence(self.proposal, self.regime, {}, {}, {"brain_regime": []})
        self.assertEqual(result["status"], "COLLECTING")
        self.assertIsNone(result["score"])
        self.assertEqual(result["master_weight"], 0.0)


if __name__ == "__main__":
    unittest.main()

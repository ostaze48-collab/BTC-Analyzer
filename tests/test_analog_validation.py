import unittest

from app.analog_validation import summarize_analog_validation
from app.edge_lab import _flatten_selected, _is_directional, _source


class AnalogValidationTests(unittest.TestCase):
    def test_analog_features_are_extracted_as_shadow_nondirectional(self):
        payload = {
            "historical_analogs": {
                "avg_similarity_pct": 72.5,
                "stop_before_1r_pct": 31.0,
                "avg_mfe_r": 2.4,
                "avg_mae_r": 0.7,
                "hit_1r_pct": 69.0,
                "hit_2r_pct": 54.0,
                "hit_3r_pct": 39.0,
                "hit_4r_pct": 25.0,
                "hit_5r_pct": 14.0,
                "matches": 24,
            }
        }
        flat = _flatten_selected(payload)
        self.assertEqual(flat["analog.hit_2r_pct"], 54.0)
        self.assertEqual(flat["analog.avg_mfe_r"], 2.4)
        self.assertNotIn("analog.matches", flat)
        self.assertFalse(_is_directional("analog.hit_2r_pct"))
        self.assertEqual(_source("analog.hit_2r_pct"), "ANALOG_SHADOW")

    def test_insufficient_sample_never_promotes(self):
        report = summarize_analog_validation({"samples": 20}, {"samples": 20})
        self.assertEqual(report["status"], "INSUFFICIENT_DATA")
        self.assertFalse(report["useful_for_master"])
        self.assertEqual(report["master_weight"], 0.0)

    def test_correlation_alone_is_not_incremental_edge(self):
        edge = {
            "samples": 80,
            "candidates": [{"feature": "analog.hit_2r_pct", "source": "ANALOG_SHADOW"}],
        }
        report = summarize_analog_validation(edge, {"samples": 80, "eligible": []})
        self.assertEqual(report["status"], "CORRELATION_ONLY")
        self.assertFalse(report["useful_for_master"])
        self.assertEqual(report["master_weight"], 0.0)

    def test_incremental_candidate_is_detected_but_master_weight_stays_zero(self):
        edge = {"samples": 140, "candidates": []}
        inc = {
            "samples": 140,
            "eligible": [{
                "feature": "analog.hit_3r_pct",
                "source": "ANALOG_SHADOW",
                "mean_delta_r": 0.18,
                "positive_fold_pct": 80.0,
            }],
        }
        report = summarize_analog_validation(edge, inc)
        self.assertEqual(report["status"], "INCREMENTAL_EDGE_DETECTED")
        self.assertTrue(report["useful_for_master"])
        self.assertEqual(report["master_weight"], 0.0)


if __name__ == "__main__":
    unittest.main()

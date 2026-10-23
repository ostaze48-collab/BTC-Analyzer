import unittest

from app.derivatives_intelligence import DerivativesIntelligence, summarize_derivatives
from app.market import _capacity
from app.regime import feature_vector


class DerivativesIntelligenceTests(unittest.TestCase):
    def test_summary_extracts_derivatives_but_keeps_zero_master_weight(self):
        raw = {
            "premium": {
                "markPrice": "101.0", "indexPrice": "100.0",
                "lastFundingRate": "0.0005", "nextFundingTime": 123,
            },
            "funding": [{"fundingRate": "0.0002"}, {"fundingRate": "0.0004"}],
            "open_interest": {"openInterest": "10000"},
            "open_interest_hist": [
                {"sumOpenInterestValue": "100"},
                {"sumOpenInterestValue": "110"},
            ],
            "global_ls": [{"longShortRatio": "1.20"}],
            "top_accounts": [{"longShortRatio": "1.10"}],
            "top_positions": [{"longShortRatio": "1.30"}],
            "taker": [{"buyVol": "120", "sellVol": "100"}],
        }
        out = summarize_derivatives(raw)
        self.assertTrue(out["available"])
        self.assertAlmostEqual(out["premium"]["basis_bps"], 100.0)
        self.assertAlmostEqual(out["open_interest"]["history_change_pct"], 10.0)
        self.assertAlmostEqual(out["flow"]["taker_buy_sell_ratio"], 1.2)
        self.assertEqual(out["shadow"]["weight_in_master"], 0.0)
        self.assertEqual(out["shadow"]["mode"], "SHADOW_ONLY")

    def test_default_state_is_shadow_only(self):
        d = DerivativesIntelligence()
        self.assertEqual(d.state["shadow"]["weight_in_master"], 0.0)
        self.assertEqual(d.state["shadow"]["mode"], "SHADOW_ONLY")

    def test_learning_vector_records_derivatives_context(self):
        derivatives = {"shadow": {"weight_in_master": 0.0, "bias": 0.25}}
        vector = feature_vector({}, {}, {}, {}, {}, {}, derivatives)
        self.assertEqual(vector["schema"], "learning_vector_v4")
        self.assertEqual(vector["derivatives_intelligence"]["shadow"]["bias"], 0.25)
        self.assertEqual(vector["derivatives_intelligence"]["shadow"]["weight_in_master"], 0.0)

    def test_daily_capacity_supports_four_year_cycle_measures(self):
        self.assertGreaterEqual(_capacity("1d"), 1458)


if __name__ == "__main__":
    unittest.main()

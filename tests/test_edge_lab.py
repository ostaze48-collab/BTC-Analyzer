import unittest

from app.edge_lab import analyze_feature_edge


def sample(i: int, total: int = 100):
    aligned = (((i * 7) % 23) - 11) / 11.0
    direction = "LONG" if i % 2 == 0 else "SHORT"
    sign = 1.0 if direction == "LONG" else -1.0
    raw_directional = aligned * sign
    # Strong synthetic relationship after direction alignment; deterministic small noise.
    outcome_r = aligned * 1.6 + (((i * 5) % 7) - 3) * 0.015
    regime = ("TREND_UP", "TREND_DOWN", "RANGE")[i % 3]
    return {
        "trade_id": i + 1,
        "opened_at": f"2026-01-{1 + (i // 24):02d}T{(i % 24):02d}:00:00+00:00",
        "brain": ("SCALP", "INTRADAY", "SWING")[i % 3],
        "direction": direction,
        "market_regime": regime,
        "risk_budget": 10.0,
        "realized_pnl": outcome_r * 10.0,
        "features": {
            "background_features": {
                "5m": {
                    "ret_14": raw_directional,
                    "ret_20": raw_directional * 0.97,
                    "atr_pct_14": ((i * 13) % 17) / 100.0,
                }
            },
            "cycle_models": {"bias": raw_directional * 0.3, "strength": abs(raw_directional)},
            "network_intelligence": {
                "shadow": {"bias": raw_directional * 0.2, "components": {"hashrate_trend": raw_directional * 0.2}, "weight_in_master": 0.0}
            },
            "derivatives_intelligence": {
                "shadow": {"bias": raw_directional * 0.4, "components": {"taker_pressure": raw_directional * 0.4}, "weight_in_master": 0.0},
                "flow": {"taker_buy_sell_ratio": 1.0 + raw_directional * 0.15},
            },
        },
    }


class EdgeLabTests(unittest.TestCase):
    def test_small_sample_is_insufficient(self):
        report = analyze_feature_edge([sample(i, 20) for i in range(20)])
        self.assertEqual(report["status"], "INSUFFICIENT_DATA")
        self.assertFalse(report["auto_promotion_enabled"])

    def test_direction_alignment_finds_oos_edge(self):
        report = analyze_feature_edge([sample(i) for i in range(100)])
        self.assertGreater(report["features_tested"], 0)
        names = {r["feature"] for r in report["candidates"]}
        self.assertIn("tf.5m.ret_14", names)
        row = next(r for r in report["candidates"] if r["feature"] == "tf.5m.ret_14")
        self.assertTrue(row["direction_aligned"])
        self.assertGreater(row["test_corr"], 0.5)
        self.assertGreater(row["oos_quartile_spread_r"], 0.15)

    def test_correlated_period_variants_do_not_count_as_independent_families(self):
        report = analyze_feature_edge([sample(i) for i in range(100)])
        ret_rows = [r for r in report["diversified_top"] if r["family"] == "5m:ret"]
        self.assertEqual(len(ret_rows), 1)

    def test_shadow_sources_can_be_measured_but_never_auto_promoted(self):
        report = analyze_feature_edge([sample(i, 200) for i in range(200)])
        sources = {r["source"] for r in report["candidates"]}
        self.assertIn("DERIVATIVES_SHADOW", sources)
        self.assertFalse(report["auto_promotion_enabled"])
        self.assertIn("walk-forward", report["promotion_policy"].lower())


if __name__ == "__main__":
    unittest.main()

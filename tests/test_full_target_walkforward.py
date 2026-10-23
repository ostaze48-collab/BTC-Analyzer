import unittest
from unittest.mock import patch

from app.full_target_walkforward import run_full_target_walkforward, simulate_partial_policy


def _record(i: int, outcome_max: float, stopped: bool, baseline_r: float = 0.3):
    policy = {1.0: 0.3, 2.0: 0.86, 3.0: 1.32, 4.0: 1.72, 5.0: 2.12}
    if stopped and outcome_max < 1.0:
        policy = {k: -1.0 for k in policy}
    return {
        "time": i,
        "brain": "INTRADAY",
        "direction": "LONG",
        "regime": "TREND_UP",
        "signature": {
            "trend": "BULLISH", "structure": "BULLISH", "regime": "TREND_UP",
            "rsi": 0.2, "ema20_dist": 0.01, "ema50_dist": 0.02, "vwap_dist": 0.01,
            "volume": 0.2, "volatility": 0.8,
            "layer_micro": 0.2, "layer_intraday": 0.5, "layer_swing": 0.6, "layer_macro": 0.7,
        },
        "outcome": {"max_r": outcome_max, "stopped": stopped, "expired": False, "mfe_r": outcome_max, "mae_r": 1.0 if stopped else 0.3},
        "baseline_target_r": 2.0,
        "baseline_policy_r": baseline_r if not (stopped and outcome_max < 1.0) else -1.0,
        "policy_by_int": policy,
        "final_score": 80.0,
        "safety_score": 80.0,
    }


class FullTargetWalkForwardTests(unittest.TestCase):
    def test_full_path_stop_has_precedence(self):
        future = [{"high": 104.0, "low": 98.0, "close": 103.0}]
        # Entry 100, risk 1% => stop=99 and 3R=103 touched in same candle.
        self.assertEqual(simulate_partial_policy(future, "LONG", 100.0, 1.0, 3.0), -1.0)

    def test_target_path_uses_partial_exit_structure(self):
        future = [
            {"high": 101.2, "low": 99.5, "close": 101.0},
            {"high": 102.0, "low": 100.5, "close": 101.8},
            {"high": 103.2, "low": 101.2, "close": 103.0},
        ]
        # 3R policy: 30%*1 + 40%*1.8 + 30%*3 = 1.92R
        self.assertAlmostEqual(simulate_partial_policy(future, "LONG", 100.0, 1.0, 3.0), 1.92, places=4)

    def test_future_records_do_not_change_first_walkforward_decision(self):
        base = [_record(i, 3.0 if i % 3 else 0.4, i % 3 == 0) for i in range(45)]
        later = [_record(100 + i, 0.2, True) for i in range(8)]
        with patch("app.full_target_walkforward._build_records", return_value=base):
            a = run_full_target_walkforward({}, "INTRADAY", 100)
        with patch("app.full_target_walkforward._build_records", return_value=base + later):
            b = run_full_target_walkforward({}, "INTRADAY", 100)
        self.assertGreater(len(a.get("recent_rows", [])), 0)
        first_a = a["recent_rows"][0]
        # With 45 records there are 15 validation rows; with +8 there are 23 and
        # only last 20 are returned. Compare a row by its timestamp when present.
        match = next((x for x in b["recent_rows"] if x["time"] == first_a["time"]), None)
        if match is None:
            # Compare the earliest common timestamp instead.
            common = sorted(set(x["time"] for x in a["recent_rows"]) & set(x["time"] for x in b["recent_rows"]))
            self.assertTrue(common)
            t = common[0]
            first_a = next(x for x in a["recent_rows"] if x["time"] == t)
            match = next(x for x in b["recent_rows"] if x["time"] == t)
        self.assertEqual(first_a["advisor_target_r"], match["advisor_target_r"])
        self.assertEqual(first_a["delta_r"], match["delta_r"])


if __name__ == "__main__":
    unittest.main()

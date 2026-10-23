import unittest

from app.master import select_trade


class MasterTests(unittest.TestCase):
    def base(self, brain, direction, confidence, rr, ev, risk=0.5, consensus=0.5):
        return {
            "brain": brain,
            "direction": direction,
            "confidence": confidence,
            "rr": rr,
            "ev_pct": ev,
            "risk_pct": risk,
            "consensus_score": consensus,
            "volatility_pct": 0.8,
            "volume_ratio": 1.4,
            "entry": 100,
            "stop_loss": 99.5 if direction == "LONG" else 100.5,
            "tp1": 101,
            "tp2": 102,
            "tp3": 103,
        }

    def test_master_selects_one(self):
        proposals = [
            self.base("SCALP", "LONG", 75, 1.8, 0.25),
            self.base("INTRADAY", "LONG", 84, 2.2, 0.80),
            self.base("SWING", "LONG", 78, 2.5, 0.55),
        ]
        result = select_trade(proposals)
        self.assertEqual(result["action"], "LONG")
        self.assertIsNotNone(result["winner"])
        passed = [x for x in result["proposals"] if x["risk_gate"] == "PASSED"]
        self.assertGreaterEqual(len(passed), 1)

    def test_negative_ev_is_rejected(self):
        proposals = [self.base("SCALP", "LONG", 90, 2.0, -0.1)]
        result = select_trade(proposals)
        self.assertNotEqual(result["action"], "LONG")


if __name__ == "__main__":
    unittest.main()

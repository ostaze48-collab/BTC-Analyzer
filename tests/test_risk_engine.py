import unittest

from app.config import settings
from app.risk_engine import build_risk_plan, hard_floor_breached


class RiskEngineTests(unittest.TestCase):
    def proposal(self, score=85, safety=86, brain="INTRADAY", direction="LONG", entry=100.0, stop=99.0):
        return {
            "brain": brain,
            "direction": direction,
            "entry": entry,
            "stop_loss": stop,
            "final_score": score,
            "safety_score": safety,
            "ev_pct": 0.8,
            "volatility_pct": 0.8,
            "shared_context": "FULL_CONSENSUS",
            "macro_direction": "BULLISH" if direction == "LONG" else "BEARISH",
        }

    def test_plan_selects_bounded_leverage_and_fee_aware_risk(self):
        account = {"starting_capital": 1000.0, "capital": 1000.0}
        plan = build_risk_plan(self.proposal(score=90, stop=99.5), account, {"regime": "TREND_UP"})
        self.assertTrue(plan["allowed"])
        self.assertGreaterEqual(plan["leverage"], 1)
        self.assertLessEqual(plan["leverage"], settings.max_paper_leverage)
        self.assertLessEqual(plan["risk_fraction"], settings.max_risk_per_trade + 1e-6)
        self.assertGreater(plan["fee_risk_pct_of_notional"], 0)
        self.assertGreater(plan["notional"], 0)

    def test_profit_target_expands_with_edge_but_never_above_5r(self):
        account = {"starting_capital": 1000.0, "capital": 1000.0}
        low = build_risk_plan(self.proposal(score=72), account, {"regime": "TREND_UP"})
        high = build_risk_plan(self.proposal(score=95, safety=94, brain="SWING"), account, {"regime": "TREND_UP"})
        self.assertEqual(low["target_r"], 1.0)
        self.assertEqual(high["target_r"], 5.0)
        self.assertGreater(high["tp3"], high["tp2"])
        self.assertGreater(high["tp2"], high["tp1"])

    def test_short_targets_move_downward(self):
        account = {"starting_capital": 1000.0, "capital": 1000.0}
        p = self.proposal(score=88, direction="SHORT", entry=100.0, stop=101.0)
        plan = build_risk_plan(p, account, {"regime": "TREND_DOWN"})
        self.assertTrue(plan["allowed"])
        self.assertLess(plan["tp1"], 100.0)
        self.assertLess(plan["tp2"], plan["tp1"])
        self.assertLess(plan["tp3"], plan["tp2"])

    def test_drawdown_reduces_risk_before_pause(self):
        p = self.proposal(score=90, stop=99.5)
        fresh = build_risk_plan(p, {"starting_capital": 1000.0, "capital": 1000.0}, {"regime": "TREND_UP"})
        dd15 = build_risk_plan(p, {"starting_capital": 1000.0, "capital": 850.0}, {"regime": "TREND_UP"})
        self.assertTrue(fresh["allowed"])
        self.assertTrue(dd15["allowed"])
        self.assertLess(dd15["risk_budget"], fresh["risk_budget"])

    def test_soft_pause_stops_new_entries_before_25pct_floor(self):
        p = self.proposal(score=95, safety=95, brain="SWING")
        account = {"starting_capital": 1000.0, "capital": 770.0}
        plan = build_risk_plan(p, account, {"regime": "TREND_UP"})
        self.assertFalse(plan["allowed"])
        self.assertEqual(plan["reason"], "CAPITAL_PRESERVATION_PAUSE")

    def test_hard_floor_kill_switch(self):
        account = {"starting_capital": 1000.0, "capital": 800.0}
        self.assertFalse(hard_floor_breached(account, -49.0))
        self.assertTrue(hard_floor_breached(account, -50.0))
        self.assertTrue(hard_floor_breached(account, -60.0))


if __name__ == "__main__":
    unittest.main()

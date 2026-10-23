import unittest

from app.backtest import BacktestEngine


class BacktestMechanicsTests(unittest.TestCase):
    def test_stop_first_when_same_candle_hits_stop_and_target(self):
        bt = BacktestEngine()
        trade = {
            "brain": "SCALP", "direction": "LONG", "entry": 100.0,
            "stop_loss": 99.0, "tp1": 101.0, "tp2": 102.0, "tp3": 103.0,
            "quantity": 1.0, "remaining_qty": 1.0, "realized_pnl": 0.0,
            "tp1_hit": False, "tp2_hit": False, "initial_risk_price": 1.0,
            "mfe_pct": 0.0, "mae_pct": 0.0,
        }
        candle = {"high": 103.5, "low": 98.5, "close_time": 1}
        closed = bt._manage(trade, candle)
        self.assertEqual(closed["exit_reason"], "STOP_LOSS")

    def test_summary_groups_basic_performance_without_changing_trade_data(self):
        trades = [
            {"realized_pnl": 10.0, "r_multiple": 1.0, "mfe_pct": 1.5, "mae_pct": 0.3},
            {"realized_pnl": -5.0, "r_multiple": -0.5, "mfe_pct": 0.4, "mae_pct": 0.8},
        ]
        summary = BacktestEngine.summarize_trades(trades)
        self.assertEqual(summary["trades"], 2)
        self.assertEqual(summary["wins"], 1)
        self.assertEqual(summary["losses"], 1)
        self.assertEqual(summary["win_rate"], 50.0)
        self.assertEqual(summary["net_pnl"], 5.0)
        self.assertEqual(summary["profit_factor"], 2.0)
        self.assertAlmostEqual(summary["avg_r"], 0.25)

    def test_open_trade_carries_historical_regime_and_cycle_bias(self):
        p = {
            "brain": "SWING", "direction": "LONG", "entry": 100.0, "stop_loss": 98.0,
            "tp1": 102.0, "tp2": 104.0, "tp3": 108.0,
            "macro_direction": "BULLISH", "macro_conflict": False, "pattern_bias": 0.2,
            "feature_bias": 0.1,
        }
        trade = BacktestEngine._open(
            p, 1000.0, 10,
            {"regime": "TREND_UP", "volatility": "NORMAL"},
            {"bias": 0.25},
        )
        self.assertIsNotNone(trade)
        self.assertEqual(trade["market_regime"], "TREND_UP")
        self.assertEqual(trade["regime_volatility"], "NORMAL")
        self.assertEqual(trade["cycle_bias"], 0.25)
        self.assertEqual(trade["feature_bias"], 0.1)


if __name__ == "__main__":
    unittest.main()

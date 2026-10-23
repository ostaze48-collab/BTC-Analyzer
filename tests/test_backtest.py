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


if __name__ == "__main__":
    unittest.main()

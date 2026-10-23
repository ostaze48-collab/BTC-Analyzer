import os
import tempfile
import unittest

from app.db import Database
from app.regime import classify_market_regime, feature_vector
from app.trade_manager import TradeManager


def snap(trend="BULLISH", structure="BULLISH", event=None, volume=1.0, vol=0.5):
    return {
        "trend": trend, "structure": structure, "structure_event": {"kind": event} if event else None,
        "volume_ratio": volume, "volatility_pct": vol, "rsi14": 55.0, "macd_hist": 0.2,
        "pattern_bias": 0.1, "liquidity": {}, "trend_channel": None,
    }


class RegimeTests(unittest.TestCase):
    def test_pullback_inside_uptrend(self):
        layers = {
            "MICRO": {"direction": "BEARISH"}, "INTRADAY": {"direction": "BEARISH"},
            "SWING": {"direction": "BULLISH"}, "MACRO": {"direction": "BULLISH"},
        }
        snaps = {"1h": snap(trend="BEARISH", structure="BEARISH"), "4h": snap(), "1d": snap()}
        regime = classify_market_regime(snaps, layers)
        self.assertEqual(regime["regime"], "PULLBACK_UPTREND")
        self.assertEqual(regime["direction"], "BULLISH")

    def test_breakout_up_needs_volume_and_not_opposite_macro(self):
        layers = {
            "MICRO": {"direction": "BULLISH"}, "INTRADAY": {"direction": "BULLISH"},
            "SWING": {"direction": "BULLISH"}, "MACRO": {"direction": "BULLISH"},
        }
        snaps = {"1h": snap(event="BOS_UP", volume=1.4), "4h": snap(), "1d": snap()}
        regime = classify_market_regime(snaps, layers)
        self.assertEqual(regime["regime"], "BREAKOUT_UP")

    def test_feature_vector_keeps_timeframe_features(self):
        snaps = {"1m": snap(), "1d": snap(event="BOS_UP")}
        layers = {"MICRO": {"direction": "BULLISH"}, "MACRO": {"direction": "BULLISH"}}
        master = {"winner": {"brain": "SCALP", "direction": "LONG", "confidence": 80, "safety_score": 82, "profit_score": 75, "final_score": 80, "rr": 2.0, "ev_pct": 0.3}}
        regime = {"regime": "TREND_UP", "direction": "BULLISH"}
        fv = feature_vector(snaps, layers, master, regime)
        self.assertIn("1m", fv["timeframes"])
        self.assertIn("1d", fv["timeframes"])
        self.assertEqual(fv["winner"]["brain"], "SCALP")


class LearningDatabaseTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.db = Database(self.path)
        self.db.init()

    def tearDown(self):
        self.db.conn.close()
        try:
            os.remove(self.path)
        except OSError:
            pass

    def proposal(self):
        return {
            "brain": "INTRADAY", "direction": "LONG", "entry": 100.0, "stop_loss": 98.0,
            "tp1": 102.0, "tp2": 104.0, "tp3": 106.0,
            "confidence": 80.0, "safety_score": 82.0, "profit_score": 77.0, "final_score": 80.0,
            "rr": 2.0, "ev_pct": 0.5, "entry_zone": [99.8, 100.2], "shared_context": "PARTIAL_CONSENSUS",
            "macro_direction": "BULLISH", "pattern_bias": 0.2,
        }

    def test_trade_manager_records_entry_features_and_excursions(self):
        manager = TradeManager(self.db)
        trade = manager.open_from_proposal(self.proposal(), context={"regime": {"regime": "TREND_UP"}, "feature_vector": {"x": 1}})
        self.assertIsNotNone(trade)
        self.assertEqual(trade["market_regime"], "TREND_UP")
        manager.on_price(101.0)
        state = manager.state(101.0)
        self.assertGreater(state["mfe_pct"], 0)
        manager.on_price(99.0)
        state = manager.state(99.0)
        self.assertGreater(state["mae_pct"], 0)
        closed = manager.early_exit(100.5, "TEST_EXIT")
        self.db.record_feature(int(closed["id"]), "EXIT", {"y": 2})
        summary = self.db.learning_summary()
        self.assertEqual(summary["closed_trades"], 1)
        self.assertEqual(summary["feature_snapshots"], 2)
        self.assertEqual(summary["brain_regime"][0]["regime"], "TREND_UP")
        self.assertGreaterEqual(summary["brain_regime"][0]["avg_mfe_pct"], 0)


if __name__ == "__main__":
    unittest.main()

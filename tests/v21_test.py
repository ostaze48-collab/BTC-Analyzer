from pathlib import Path
import sys, tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from btc_analyzer.paper import PaperLedger
from btc_analyzer.regime import MarketRegimeEngine

cfg={
 "paper_start_balance":100,"paper_risk_per_trade_pct":1,
 "paper_fee_bps_per_side":0,"paper_slippage_bps":0,
 "paper_max_notional_multiple":100,"report_timezone_offset_hours":3,
 "lane_cooldowns_seconds":{"SCALP":0},"lane_expiry_seconds":{"SCALP":999999},
 "paper_daily_loss_limit_pct":3,"paper_max_consecutive_losses":4,"paper_max_open_trades":3
}
with tempfile.TemporaryDirectory() as td:
    l=PaperLedger(Path(td)/"p.db",cfg)
    l.maybe_open({"SCALP":{"action":"LONG","setup_grade":"A","setup_score":80,
                 "plan":{"entry":100,"sl":99,"tp1":101.3,"tp2":101.8}}})
    op=l.open_positions(100.5)
    assert len(op)==1 and op[0]["trade_state"]=="OPEN"
    assert l.risk_guard()["allow_new_trades"] is True

reg=MarketRegimeEngine().evaluate({
 "timeframes":{"1H":{"adx":35,"atr_pct":0.6,"volatility":"NORMAL","wave_state":"EXPANDING"},
               "15m":{"wave_state":"EXPANDING"}},
 "hierarchy":{"swing":0.6,"intraday":0.5,"entry":0.4},
 "families":{"trend":0.7,"momentum":0.5,"structure":0.6}
})
assert reg["regime"]=="TREND"
print("V2.1 tests: OK")

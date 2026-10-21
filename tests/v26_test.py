from pathlib import Path
import sys, tempfile
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from btc_analyzer.price_action import PriceActionEngine
from btc_analyzer.decision import DecisionEngine
from btc_analyzer.paper import PaperLedger

def frame_from_close(close):
    close=np.asarray(close,dtype=float)
    idx=pd.date_range("2026-01-01",periods=len(close),freq="h",tz="UTC")
    op=np.r_[close[0],close[:-1]]
    high=np.maximum(op,close)+.5
    low=np.minimum(op,close)-.5
    vol=np.full(len(close),100.0)
    return pd.DataFrame({
      "open":op,"high":high,"low":low,"close":close,
      "volume":vol,"quote_volume":vol*close,
      "taker_base":vol*.52,"taker_quote":vol*close*.52
    },index=idx)

# 1) Candlestick detection: bullish engulfing.
pa=PriceActionEngine()
df=frame_from_close(np.linspace(100,102,48).tolist()+[99,101.5])
df.iloc[-2,df.columns.get_loc("open")]=101.0
df.iloc[-2,df.columns.get_loc("close")]=99.0
df.iloc[-2,df.columns.get_loc("high")]=101.4
df.iloc[-2,df.columns.get_loc("low")]=98.7
df.iloc[-1,df.columns.get_loc("open")]=98.5
df.iloc[-1,df.columns.get_loc("close")]=101.5
df.iloc[-1,df.columns.get_loc("high")]=102.0
df.iloc[-1,df.columns.get_loc("low")]=98.2
candles=pa.candles(df)
assert any(x["name"]=="BULLISH_ENGULFING" for x in candles["patterns"])

# 2) Repeated oscillations produce meaningful S/R zones.
x=np.arange(100)
close=105+5*np.sin(x*np.pi/6)
df2=frame_from_close(close)
zones=pa.zones(df2)
assert zones["nearest_support"] is not None
assert zones["nearest_resistance"] is not None
assert zones["nearest_support"]["touches"]>=2
assert zones["nearest_resistance"]["touches"]>=2

# 3) Rising oscillatory market produces an ascending support trendline.
close=100+.18*x+3*np.sin(x*np.pi/6)
df3=frame_from_close(close)
lines=pa.trendlines(df3)
assert lines["support_line"] is not None
assert lines["support_line"]["slope"]>0
assert lines["support_line"]["r2"]>.5

def a(trend=1,mom=1,structure="BULLISH",wave="UP",state="EXPANDING",
      support=95,resistance=None,atr=.2,over=False):
    return {
      "trend_score":trend,"momentum_score":mom,"structure":structure,
      "wave_direction":wave,"wave_state":state,"support":support,
      "resistance":resistance,"atr_pct":atr,"overextended":over
    }

# 4) Price Action cannot create a trade by itself.
neutral_analysis={
 "bias":"NEUTRAL",
 "hierarchy":{"intraday":0,"swing":0},
 "timeframes":{},
 "price_action":{"timeframes":{
   "5m":{"directional_score":1,"bullish_evidence":["SUPPORT_ZONE","BULLISH_ENGULFING"],"bearish_evidence":[]}
 }}
}
dec=DecisionEngine().evaluate(neutral_analysis,{"score":0},100)
assert dec["lanes"]["SCALP"]["action"]=="WAIT"

# 5) Strong opposition from >=2 PA families vetoes an otherwise valid long scalp.
T={
 "4H":a(),"1H":a(),"30m":a(),"15m":a(),
 "5m":a(),"3m":a(),"1m":a(),"1D":a(),"3D":a(),"1W":a()
}
bear_pa={}
for tf in ("15m","5m","3m","1m"):
    bear_pa[tf]={
      "state":"BEARISH","directional_score":-.8,
      "bullish_evidence":[],
      "bearish_evidence":["RESISTANCE_ZONE","BEARISH_ENGULFING"],
      "zones":{"nearest_support":None,"nearest_resistance":None}
    }
analysis={
 "bias":"BULLISH","bias_score":.7,
 "hierarchy":{"macro":.5,"longterm":.6,"swing":.8,"intraday":.8,"entry":.7},
 "families":{"trend":.8,"momentum":.7,"structure":.7,"wave":.7,"volume":.2},
 "timeframes":T,
 "price_action":{"timeframes":bear_pa}
}
dec=DecisionEngine().evaluate(analysis,{"score":0},100)
scalp=dec["lanes"]["SCALP"]
assert scalp["triggered"] is True
assert scalp["price_action"]["strong_opposition"] is True
assert scalp["action"]=="WAIT"

# 6) Paper DB stores PA state and produces PA calibration.
CFG={
 "paper_start_balance":100,"paper_risk_per_trade_pct":1,
 "paper_fee_bps_per_side":0,"paper_slippage_bps":0,
 "paper_max_notional_multiple":100,"report_timezone_offset_hours":3,
 "lane_cooldowns_seconds":{"SCALP":0,"INTRADAY":0,"SWING":0},
 "lane_expiry_seconds":{"SCALP":999999,"INTRADAY":999999,"SWING":999999},
 "paper_daily_loss_limit_pct":100,"paper_max_consecutive_losses":20,
 "paper_max_open_trades":1,
}
with tempfile.TemporaryDirectory() as td:
    ledger=PaperLedger(Path(td)/"paper.db",CFG)
    lane={
      "action":"LONG","setup_grade":"A","setup_score":80,
      "opportunity":{"opportunity_id":"PA-TEST"},
      "diagnostics":{
        "entry_timing":"OPTIMAL","chasing_risk":"LOW",
        "available_rr":1.8,"structural_obstacle":None
      },
      "price_action":{
        "state":"ALIGNED","score":.45,
        "aligned_evidence":["5m:SUPPORT_ZONE","5m:BULLISH_ENGULFING"],
        "opposed_evidence":[],
        "aligned_families":["ZONE","CANDLE"],
        "opposed_families":[]
      },
      "plan":{"entry":100,"sl":99,"tp1":101.3,"tp2":101.8}
    }
    ledger.maybe_open({"SCALP":lane},market_regime="TREND")
    row=ledger.recent(1)[0]
    assert row["price_action_state"]=="ALIGNED"
    assert abs(float(row["price_action_score"])-.45)<1e-9

    ledger.process_closed_bar({"ts":1,"open":100,"high":101.4,"low":100.2,"close":101.2})
    ledger.process_closed_bar({"ts":2,"open":101.2,"high":101.9,"low":101.0,"close":101.8})
    stats=ledger.price_action_stats()
    aligned=[x for x in stats if x["label"]=="ALIGNED"]
    assert len(aligned)==1
    assert aligned[0]["trades"]==1
    assert aligned[0]["wins"]==1

print("V2.6 tests: OK")

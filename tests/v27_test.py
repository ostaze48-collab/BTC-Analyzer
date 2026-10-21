from pathlib import Path
import sys, tempfile
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from btc_analyzer.price_action import PriceActionEngine
from btc_analyzer.decision import DecisionEngine
from btc_analyzer.paper import PaperLedger

# -------------------------
# Pattern validation lifecycle
# -------------------------
idx=pd.date_range("2026-01-01",periods=20,freq="h",tz="UTC")
base=pd.DataFrame({
  "open":[100.0]*20,"high":[101.0]*20,"low":[99.0]*20,"close":[100.0]*20,
  "volume":[100.0]*20,"quote_volume":[10000.0]*20,
  "taker_base":[52.0]*20,"taker_quote":[5200.0]*20,
},index=idx)

pa=PriceActionEngine()

# Double bottom: below neckline => candidate.
p={"name":"DOUBLE_BOTTOM","direction":"BULLISH","strength":72,
   "details":{"bottoms":[95,95.2],"neckline":100}}
candidate=pa._pattern_validation(dict(p),base,0.2,[],[])
assert candidate["validation"]["status"]=="CANDIDATE"

# Close above neckline => confirmed.
confirmed_df=base.copy()
confirmed_df.iloc[-1,confirmed_df.columns.get_loc("close")]=100.5
confirmed_df.iloc[-1,confirmed_df.columns.get_loc("high")]=100.7
p2={"name":"DOUBLE_BOTTOM","direction":"BULLISH","strength":72,
    "details":{"bottoms":[95,95.2],"neckline":100}}
confirmed=pa._pattern_validation(p2,confirmed_df,0.2,[],[])
assert confirmed["validation"]["status"]=="CONFIRMED"
assert confirmed["validation"]["target"]>100.5

# Break below invalidation => failed.
failed_df=base.copy()
failed_df.iloc[-1,failed_df.columns.get_loc("close")]=94.5
failed_df.iloc[-1,failed_df.columns.get_loc("low")]=94.3
p3={"name":"DOUBLE_BOTTOM","direction":"BULLISH","strength":72,
    "details":{"bottoms":[95,95.2],"neckline":100}}
failed=pa._pattern_validation(p3,failed_df,0.2,[],[])
assert failed["validation"]["status"]=="FAILED"

# -------------------------
# Structure-aware plan
# -------------------------
de=DecisionEngine()
a={
 "atr_pct":.20,"support":99.72,"resistance":100.72,
 "wave_state":"EXPANDING","overextended":False
}
pa_tf={
 "zones":{
   "zones":[
     {"center":99.75,"low":99.70,"high":99.80,"strength":82},
     {"center":100.75,"low":100.70,"high":100.80,"strength":78},
   ],
   "nearest_support":{"center":99.75,"low":99.70,"high":99.80,"strength":82},
   "nearest_resistance":{"center":100.75,"low":100.70,"high":100.80,"strength":78},
 },
 "trendlines":{"support_line":None,"resistance_line":None},
 "chart_patterns":{"patterns":[]}
}
plan=de._plan(100,a,1,"SCALP",pa_tf)
assert plan["mode"]=="STRUCTURE_AWARE"
assert plan["stop_source"] in ("SUPPORT_ZONE","SWING_SUPPORT")
assert plan["sl"]<100
assert plan["tp1"]>100
assert plan["tp2"]>plan["tp1"]

# No structural evidence => ATR fallback.
fallback=de._plan(
    100,
    {"atr_pct":.20,"support":None,"resistance":None,
     "wave_state":"EXPANDING","overextended":False},
    1,"SCALP",
    {"zones":{"zones":[]},"trendlines":{},"chart_patterns":{"patterns":[]}}
)
assert fallback["mode"]=="ATR_FALLBACK"
assert fallback["stop_source"]=="ATR"

# Confirmed chart-pattern target can be used.
pa_pattern={
 "zones":{"zones":[{"center":99.75,"low":99.70,"high":99.80,"strength":82}]},
 "trendlines":{},
 "chart_patterns":{"patterns":[{
   "name":"DOUBLE_BOTTOM","direction":"BULLISH","strength":80,
   "validation":{"status":"CONFIRMED","target":101.5}
 }]}
}
pattern_a={
 "atr_pct":.20,"support":99.72,"resistance":None,
 "wave_state":"EXPANDING","overextended":False
}
pp=de._plan(100,pattern_a,1,"SCALP",pa_pattern)
assert pp["mode"]=="STRUCTURE_AWARE"
assert pp["pattern_target"]==101.5
assert ("DOUBLE_BOTTOM" in pp["tp1_source"] or "DOUBLE_BOTTOM" in pp["tp2_source"])
assert (abs(pp["tp1"]-101.5)<1e-9 or abs(pp["tp2"]-101.5)<1e-9)

# -------------------------
# DB migration + plan calibration
# -------------------------
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
      "opportunity":{"opportunity_id":"V27-PLAN"},
      "diagnostics":{
        "entry_timing":"OPTIMAL","chasing_risk":"LOW",
        "available_rr":2.0,"structural_obstacle":None
      },
      "price_action":{
        "state":"ALIGNED","score":.3,
        "aligned_evidence":["5m:SUPPORT_ZONE"],
        "opposed_evidence":[],
        "aligned_families":["ZONE"],"opposed_families":[]
      },
      "plan":{
        "entry":100,"sl":99,"tp1":101.3,"tp2":101.8,
        "mode":"STRUCTURE_AWARE",
        "stop_source":"SUPPORT_ZONE",
        "tp1_source":"RESISTANCE_ZONE",
        "tp2_source":"DOUBLE_BOTTOM[CONFIRMED]"
      }
    }
    ledger.maybe_open({"SCALP":lane},market_regime="TREND")
    row=ledger.recent(1)[0]
    assert row["plan_mode"]=="STRUCTURE_AWARE"
    assert row["stop_source"]=="SUPPORT_ZONE"

    ledger.process_closed_bar({"ts":1,"open":100,"high":101.4,"low":100.2,"close":101.2})
    ledger.process_closed_bar({"ts":2,"open":101.2,"high":101.9,"low":101.0,"close":101.8})

    stats=ledger.execution_plan_stats()
    x=[r for r in stats if r["label"]=="STRUCTURE_AWARE"]
    assert len(x)==1 and x[0]["trades"]==1 and x[0]["wins"]==1

print("V2.7 tests: OK")

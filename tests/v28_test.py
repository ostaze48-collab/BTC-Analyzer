from pathlib import Path
import sys, tempfile, sqlite3
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from btc_analyzer.paper import PaperLedger
from btc_analyzer.opportunity import OpportunityTracker
from btc_analyzer.decision import DecisionEngine
from btc_analyzer.lane_lab import LaneComparisonLab

CFG={
 "paper_start_balance":1000,
 "paper_fixed_start_balance":1000,
 "paper_risk_per_trade_pct":0.5,
 "paper_fee_bps_per_side":0,
 "paper_slippage_bps":0,
 "paper_max_notional_multiple":3,
 "report_timezone_offset_hours":3,
 "lane_cooldowns_seconds":{"FAST_SCALP":0,"SCALP":0,"INTRADAY":0,"SWING":0},
 "lane_expiry_seconds":{"FAST_SCALP":900,"SCALP":7200,"INTRADAY":43200,"SWING":259200},
 "paper_daily_loss_limit_pct":3,
 "paper_max_consecutive_losses":4,
 "paper_max_open_trades":1,
}

def a(trend=1,mom=1,structure="BULLISH",wave="UP",state="EXPANDING",volume=.25):
    return {
      "trend_score":trend,"momentum_score":mom,"structure":structure,
      "wave_direction":wave,"wave_state":state,"support":99.7,
      "resistance":101.0,"atr_pct":.18,"overextended":False,
      "volume_score":volume
    }

# 1) Fixed capital: old active $100 experiment is archived on startup and $1000 is created.
with tempfile.TemporaryDirectory() as td:
    db=Path(td)/"paper.db"
    old_cfg={**CFG,"paper_start_balance":100}
    old_cfg.pop("paper_fixed_start_balance")
    old=PaperLedger(db,old_cfg)
    old_id=old.get_experiment_id()
    assert old.get_start_balance()==100

    fixed=PaperLedger(db,CFG)
    assert fixed.get_start_balance()==1000
    assert fixed.get_experiment_id()!=old_id
    hist=fixed.experiment_history()
    assert hist[0]["status"]=="ACTIVE" and hist[0]["start_balance"]==1000
    assert any(x["experiment_id"]==old_id and x["status"]=="ARCHIVED" for x in hist)

    try:
        fixed.set_start_balance(500,reset_results=True)
        raise AssertionError("capital change should have been rejected")
    except ValueError:
        pass

# 2) FAST_SCALP can trigger from 3m + 1m with 5m/15m only as guards.
T={
 "1m":a(trend=.65,mom=.7),"3m":a(trend=.75,mom=.7),
 "5m":a(trend=.25,mom=.2),"15m":a(trend=.10,mom=.1),
 "30m":a(trend=.10,mom=.1),"1H":a(trend=.10,mom=.1),
 "4H":a(trend=.10,mom=.1),"1D":a(trend=.10,mom=.1),
 "3D":a(trend=.10,mom=.1),"1W":a(trend=.10,mom=.1),
}
pa_tfs={}
for tf in ("1m","3m","5m","15m"):
    pa_tfs[tf]={
      "directional_score":.12,"state":"NEUTRAL",
      "bullish_evidence":["SUPPORT_ZONE"],"bearish_evidence":[],
      "zones":{"zones":[],"nearest_support":None,"nearest_resistance":None},
      "trendlines":{},"chart_patterns":{"patterns":[]}
    }
analysis={
 "bias":"NEUTRAL","bias_score":0,
 "hierarchy":{"macro":0,"longterm":0,"swing":.1,"intraday":.1,"entry":.7},
 "families":{"trend":.2,"momentum":.2,"structure":.2,"wave":.2,"volume":.2},
 "timeframes":T,"price_action":{"timeframes":pa_tfs}
}
dec=DecisionEngine().evaluate(analysis,{"score":0},100)
fast=dec["lanes"]["FAST_SCALP"]
assert fast["triggered"] is True
assert fast["action"]=="LONG"
assert fast["setup_score"]>=64
assert fast["plan"]["risk_pct"] < 1.0
assert "FAST_SCALP" in dec["lanes"]

# 3) Fast opportunity is stable inside same closed 1m bar and rotates on next bar.
with tempfile.TemporaryDirectory() as td:
    tr=OpportunityTracker(Path(td)/"opp.db")
    lanes={
      "FAST_SCALP":fast,
      "SCALP":{"side_bias":"NEUTRAL","setup_score":0,"action":"WAIT"},
      "INTRADAY":{"side_bias":"NEUTRAL","setup_score":0,"action":"WAIT"},
      "SWING":{"side_bias":"NEUTRAL","setup_score":0,"action":"WAIT"},
    }
    x1=tr.observe(lanes,fast_bar_ts=1000)["FAST_SCALP"]["opportunity_id"]
    x2=tr.observe(lanes,fast_bar_ts=1000)["FAST_SCALP"]["opportunity_id"]
    x3=tr.observe(lanes,fast_bar_ts=1060)["FAST_SCALP"]["opportunity_id"]
    assert x1==x2
    assert x3!=x1

# 4) Lane Lab has 4 independent accounts, all fixed at $1000.
with tempfile.TemporaryDirectory() as td:
    lab=LaneComparisonLab(Path(td),CFG,1000)
    assert set(lab.ledgers)=={"FAST_SCALP","SCALP","INTRADAY","SWING"}
    assert all(x.get_start_balance()==1000 for x in lab.ledgers.values())

# 5) Main account remains globally one open trade even with FAST_SCALP present.
with tempfile.TemporaryDirectory() as td:
    ledger=PaperLedger(Path(td)/"paper.db",CFG)
    fast_signal={**fast,"opportunity":{"opportunity_id":"FAST-1"}}
    scalp_signal={
      "action":"LONG","setup_grade":"A+","setup_score":99,
      "opportunity":{"opportunity_id":"SCALP-1"},
      "diagnostics":{"entry_timing":"OPTIMAL","chasing_risk":"LOW","available_rr":1.8,"structural_obstacle":None},
      "price_action":{"state":"NEUTRAL","score":0,"aligned_evidence":[],"opposed_evidence":[],"aligned_families":[],"opposed_families":[]},
      "plan":{"entry":100,"sl":99,"tp1":101.3,"tp2":101.8,"mode":"ATR_FALLBACK","stop_source":"ATR","tp1_source":"ATR_R1","tp2_source":"ATR_R2"}
    }
    ledger.maybe_open({"FAST_SCALP":fast_signal,"SCALP":scalp_signal},market_regime="TREND")
    rows=ledger.recent(10)
    assert len(rows)==1
    assert rows[0]["lane"]=="SCALP"  # stronger Setup Score wins main account

print("V2.8 tests: OK")

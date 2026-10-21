from pathlib import Path
import sys, tempfile, sqlite3

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from btc_analyzer.paper import PaperLedger
from btc_analyzer.opportunity import OpportunityTracker
from btc_analyzer.decision import DecisionEngine
from btc_analyzer.research import ResearchJournal

CFG={
 "paper_start_balance":100,
 "paper_risk_per_trade_pct":1,
 "paper_fee_bps_per_side":0,
 "paper_slippage_bps":0,
 "paper_max_notional_multiple":100,
 "report_timezone_offset_hours":3,
 "lane_cooldowns_seconds":{"SCALP":0,"INTRADAY":0,"SWING":0},
 "lane_expiry_seconds":{"SCALP":999999,"INTRADAY":999999,"SWING":999999},
 "paper_daily_loss_limit_pct":3,
 "paper_max_consecutive_losses":4,
 "paper_max_open_trades":3,
}

def a(trend=1,mom=1,structure="BULLISH",wave="UP",state="EXPANDING",
      over=False,support=95,resistance=None,atr=.20,adx=35):
    return {
      "trend_score":trend,
      "momentum_score":mom,
      "structure":structure,
      "wave_direction":wave,
      "wave_state":state,
      "overextended":over,
      "support":support,
      "resistance":resistance,
      "atr_pct":atr,
      "adx":adx,
      "volatility":"NORMAL",
      "volume_score":.2
    }

# Opportunity ID stability
with tempfile.TemporaryDirectory() as td:
    tracker=OpportunityTracker(Path(td)/"opp.db")
    lanes={
      "SCALP":{"side_bias":"LONG","setup_score":65,"action":"WAIT"},
      "INTRADAY":{"side_bias":"NEUTRAL","setup_score":20,"action":"WAIT"},
      "SWING":{"side_bias":"NEUTRAL","setup_score":20,"action":"WAIT"},
    }
    first=tracker.observe(lanes)["SCALP"]["opportunity_id"]
    second=tracker.observe(lanes)["SCALP"]["opportunity_id"]
    assert first==second
    lanes["SCALP"]["setup_score"]=75
    current=tracker.observe(lanes)["SCALP"]
    assert current["state"]=="READY"
    assert current["opportunity_id"]==first

# A+ territory but missing 15m confirmation caps grade to A
T={
 "4H":a(),
 "1H":a(),
 "30m":a(),
 "15m":a(trend=.05,mom=1,structure="BULLISH",wave="UP",state="MATURE"),
 "5m":a(),
 "3m":a(),
 "1m":a(),
 "1D":a(),
 "3D":a(),
 "1W":a()
}
analysis={
 "bias":"BULLISH",
 "bias_score":.6,
 "hierarchy":{"macro":.4,"longterm":.5,"swing":.7,"intraday":.8,"entry":.5},
 "families":{"trend":.7,"momentum":.5,"structure":.5,"wave":.6,"volume":.2},
 "timeframes":T
}
scalp=DecisionEngine().evaluate(analysis,{"score":0},100)["lanes"]["SCALP"]
assert scalp["setup_score"]>=85
assert scalp["setup_grade"]=="A"
assert scalp["action"]=="LONG"
assert scalp["diagnostics"]["rr_gate_pass"] is True

# Non-destructive Paper DB migration + MFE/MAE + efficiency
with tempfile.TemporaryDirectory() as td:
    db=Path(td)/"paper.db"
    c=sqlite3.connect(db)
    c.execute('''CREATE TABLE trades(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      engine_version TEXT NOT NULL,
      lane TEXT NOT NULL,
      side TEXT NOT NULL,
      open_ts REAL NOT NULL,
      entry REAL NOT NULL,
      sl REAL NOT NULL,
      tp1 REAL NOT NULL,
      tp2 REAL NOT NULL,
      quantity REAL NOT NULL,
      risk_usd REAL NOT NULL,
      notional_usd REAL NOT NULL,
      setup_grade TEXT,
      setup_score REAL,
      status TEXT DEFAULT 'OPEN',
      tp1_hit INTEGER DEFAULT 0,
      tp1_ts REAL,
      partial_gross REAL DEFAULT 0,
      fees REAL DEFAULT 0,
      close_ts REAL,
      exit_price REAL,
      gross_pnl REAL DEFAULT 0,
      net_pnl REAL DEFAULT 0,
      realized_r REAL DEFAULT 0,
      last_bar_ts REAL DEFAULT 0,
      reason TEXT
    )''')
    c.commit()
    c.close()

    ledger=PaperLedger(db,CFG)
    cc=ledger.con()
    cols={r["name"] for r in cc.execute("PRAGMA table_info(trades)").fetchall()}
    cc.close()
    assert {"opportunity_id","mfe_r","mae_r","capture_efficiency_pct","market_regime"} <= cols

    lane={
      "action":"LONG",
      "setup_grade":"A",
      "setup_score":80,
      "opportunity":{"opportunity_id":"SCALP-TEST"},
      "diagnostics":{
        "entry_timing":"OPTIMAL",
        "chasing_risk":"LOW",
        "available_rr":1.8,
        "structural_obstacle":None
      },
      "plan":{"entry":100,"sl":99,"tp1":101.3,"tp2":101.8}
    }

    ledger.maybe_open({"SCALP":lane},market_regime="TREND")
    ledger.process_closed_bar({"ts":1,"open":100,"high":100.8,"low":99.6,"close":100.5})
    op=ledger.open_positions(100.5)[0]
    assert .79<=op["mfe_r"]<=.81
    assert -.41<=op["mae_r"]<=-.39

    ledger.process_closed_bar({"ts":2,"open":100.5,"high":101.4,"low":100.3,"close":101.2})
    ledger.process_closed_bar({"ts":3,"open":101.2,"high":101.9,"low":101.0,"close":101.8})
    row=ledger.recent(1)[0]
    assert row["status"]=="WIN"
    assert row["mfe_r"]>=1.79
    assert row["capture_efficiency_pct"]>0

# Research DB migration
with tempfile.TemporaryDirectory() as td:
    db=Path(td)/"research.db"
    c=sqlite3.connect(db)
    c.execute('''CREATE TABLE snapshots(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      bucket_ts INTEGER UNIQUE,
      ts REAL,
      price REAL,
      bias TEXT,
      bias_score REAL,
      best_lane TEXT,
      best_action TEXT,
      best_grade TEXT,
      best_score REAL,
      context_regime TEXT,
      context_score REAL,
      analysis_json TEXT,
      lanes_json TEXT,
      r1h_pct REAL,
      r4h_pct REAL
    )''')
    c.commit()
    c.close()

    journal=ResearchJournal(db,300)
    cc=journal.con()
    cols={r["name"] for r in cc.execute("PRAGMA table_info(snapshots)").fetchall()}
    cc.close()
    assert {"market_regime","opportunity_id","entry_timing","chasing_risk","available_rr"} <= cols

print("V2.2 tests: OK")

from pathlib import Path
import sys, tempfile, sqlite3

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from btc_analyzer.paper import PaperLedger

CFG={
 "paper_start_balance":100,
 "paper_risk_per_trade_pct":1,
 "paper_fee_bps_per_side":0,
 "paper_slippage_bps":0,
 "paper_max_notional_multiple":100,
 "report_timezone_offset_hours":3,
 "lane_cooldowns_seconds":{"SCALP":0,"INTRADAY":0,"SWING":0},
 "lane_expiry_seconds":{"SCALP":999999,"INTRADAY":999999,"SWING":999999},
 "paper_daily_loss_limit_pct":50,
 "paper_max_consecutive_losses":20,
 "paper_max_open_trades":1,
}

def lane(action="LONG",score=80,rr=1.8,opp="O1"):
    return {
      "action":action,
      "setup_grade":"A",
      "setup_score":score,
      "opportunity":{"opportunity_id":opp},
      "diagnostics":{
        "entry_timing":"OPTIMAL",
        "chasing_risk":"LOW",
        "available_rr":rr,
        "structural_obstacle":None
      },
      "plan":{"entry":100,"sl":99,"tp1":101.3,"tp2":101.8}
    }

# 1. V2.3-style DB migration keeps old trades.
with tempfile.TemporaryDirectory() as td:
    db=Path(td)/"paper.db"
    c=sqlite3.connect(db)
    c.execute("""CREATE TABLE trades(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      engine_version TEXT NOT NULL,lane TEXT NOT NULL,side TEXT NOT NULL,
      open_ts REAL NOT NULL,entry REAL NOT NULL,sl REAL NOT NULL,
      tp1 REAL NOT NULL,tp2 REAL NOT NULL,quantity REAL NOT NULL,
      risk_usd REAL NOT NULL,notional_usd REAL NOT NULL,setup_grade TEXT,
      setup_score REAL,status TEXT DEFAULT 'OPEN',tp1_hit INTEGER DEFAULT 0,
      tp1_ts REAL,partial_gross REAL DEFAULT 0,fees REAL DEFAULT 0,
      close_ts REAL,exit_price REAL,gross_pnl REAL DEFAULT 0,
      net_pnl REAL DEFAULT 0,realized_r REAL DEFAULT 0,
      last_bar_ts REAL DEFAULT 0,reason TEXT,opportunity_id TEXT,
      market_regime TEXT,entry_timing TEXT,chasing_risk TEXT,
      available_rr REAL,structural_obstacle REAL,mfe_price REAL,mae_price REAL,
      mfe_r REAL DEFAULT 0,mae_r REAL DEFAULT 0,capture_efficiency_pct REAL
    )""")
    c.execute("""CREATE TABLE paper_settings(
      key TEXT PRIMARY KEY,value TEXT NOT NULL
    )""")
    c.execute("INSERT INTO paper_settings(key,value) VALUES('start_balance','100')")
    c.execute("""INSERT INTO trades(
      engine_version,lane,side,open_ts,entry,sl,tp1,tp2,quantity,risk_usd,
      notional_usd,status,close_ts,exit_price,gross_pnl,net_pnl,realized_r
    ) VALUES('V2.3','SCALP','LONG',1,100,99,101.3,101.8,1,1,100,
             'WIN',2,101.8,1.8,1.8,1.8)""")
    c.commit();c.close()

    ledger=PaperLedger(db,CFG)
    assert ledger.pnl_dashboard()["total"]["trades"]==1
    cc=ledger.con()
    row=cc.execute("SELECT experiment_id FROM trades LIMIT 1").fetchone()
    cc.close()
    assert row["experiment_id"]==ledger.get_experiment_id()

# 2. New capital archives old experiment instead of deleting it.
with tempfile.TemporaryDirectory() as td:
    ledger=PaperLedger(Path(td)/"paper.db",CFG)
    first_exp=ledger.get_experiment_id()

    ledger.maybe_open({"SCALP":lane(opp="WIN1")},market_regime="TREND")
    ledger.process_closed_bar({"ts":1,"open":100,"high":101.4,"low":100.2,"close":101.2})
    ledger.process_closed_bar({"ts":2,"open":101.2,"high":101.9,"low":101.0,"close":101.8})
    assert ledger.pnl_dashboard()["total"]["wins"]==1

    result=ledger.set_start_balance(1000,reset_results=True)
    second_exp=result["experiment_id"]
    assert second_exp!=first_exp
    assert ledger.pnl_dashboard()["total"]["trades"]==0
    assert ledger.pnl_dashboard()["balance"]==1000

    history=ledger.experiment_history()
    assert len(history)==2
    old=[x for x in history if x["experiment_id"]==first_exp][0]
    new=[x for x in history if x["experiment_id"]==second_exp][0]
    assert old["status"]=="ARCHIVED"
    assert old["trades"]==1
    assert old["net_pnl"]>0
    assert new["status"]=="ACTIVE"
    assert new["trades"]==0

    cc=ledger.con()
    assert cc.execute("SELECT COUNT(*) n FROM trades").fetchone()["n"]==1
    cc.close()

# 3. One main trade remains enforced.
with tempfile.TemporaryDirectory() as td:
    ledger=PaperLedger(Path(td)/"paper.db",CFG)
    ledger.maybe_open({
      "SCALP":lane(score=80,opp="S1"),
      "INTRADAY":lane(score=90,opp="I1")
    },market_regime="TREND")
    rows=ledger.recent()
    assert len(rows)==1
    assert rows[0]["lane"]=="INTRADAY"

    ledger.maybe_open({"SCALP":lane(score=99,opp="S2")},market_regime="TREND")
    assert len(ledger.recent())==1

# 4. Analytics: a win followed by a loss produces drawdown and expectancy.
with tempfile.TemporaryDirectory() as td:
    ledger=PaperLedger(Path(td)/"paper.db",CFG)

    # Win
    ledger.maybe_open({"SCALP":lane(opp="W")},market_regime="TREND")
    ledger.process_closed_bar({"ts":1,"open":100,"high":101.4,"low":100.2,"close":101.2})
    ledger.process_closed_bar({"ts":2,"open":101.2,"high":101.9,"low":101.0,"close":101.8})

    # Loss
    short_lane=lane(action="LONG",score=80,rr=1.8,opp="L")
    ledger.maybe_open({"SCALP":short_lane},market_regime="TREND")
    ledger.process_closed_bar({"ts":3,"open":100,"high":100.2,"low":98.9,"close":99})

    a=ledger.analytics()
    assert a["trades"]==2
    assert a["max_drawdown_usd"]>0
    assert a["max_drawdown_pct"]>0
    assert len(a["equity_curve"])==3
    assert a["max_win_streak"]>=1
    assert a["max_loss_streak"]>=1

    tp=ledger.time_performance()
    assert "hour" in tp and "weekday" in tp

print("V2.4 tests: OK")

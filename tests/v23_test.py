from pathlib import Path
import sys, tempfile

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
 "paper_daily_loss_limit_pct":3,
 "paper_max_consecutive_losses":4,
 "paper_max_open_trades":1,
}

def lane(action,score,rr,opp):
    return {
      "action":action,
      "setup_grade":"A+",
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

with tempfile.TemporaryDirectory() as td:
    db=Path(td)/"paper.db"
    ledger=PaperLedger(db,CFG)

    # Capital persists in DB and reset is clean.
    assert ledger.get_start_balance()==100
    ledger.set_start_balance(1000,reset_results=True)
    assert ledger.get_start_balance()==1000
    assert ledger.pnl_dashboard()["balance"]==1000

    # Two actionable lanes in same cycle -> only strongest opens.
    ledger.maybe_open({
      "SCALP":lane("LONG",80,1.8,"S1"),
      "INTRADAY":lane("LONG",90,1.5,"I1"),
      "SWING":{"action":"WAIT","setup_score":95}
    },market_regime="TREND")

    rows=ledger.recent(10)
    assert len(rows)==1
    assert rows[0]["lane"]=="INTRADAY"
    assert rows[0]["opportunity_id"]=="I1"

    # A second call while one trade is open must not open anything else.
    ledger.maybe_open({
      "SCALP":lane("LONG",99,2.0,"S2")
    },market_regime="TREND")
    assert len(ledger.recent(10))==1
    assert ledger.risk_guard()["open_trades"]==1

    # Reset capital deletes current main trade and changes baseline.
    ledger.set_start_balance(2500,reset_results=True)
    assert ledger.get_start_balance()==2500
    assert len(ledger.recent(10))==0
    assert ledger.pnl_dashboard()["balance"]==2500
    assert ledger.pnl_dashboard()["total"]["net_pnl"]==0
    assert ledger.pnl_dashboard()["total"]["return_pct"]==0

    # Persistence across a new PaperLedger object.
    ledger2=PaperLedger(db,CFG)
    assert ledger2.get_start_balance()==2500

print("V2.3 tests: OK")

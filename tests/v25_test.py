from pathlib import Path
import sys, tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from btc_analyzer.lane_lab import LaneComparisonLab
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

def sig(lane,opp,score=80):
    return {
      "lane":lane,
      "side_bias":"LONG",
      "action":"LONG",
      "setup_grade":"A",
      "setup_score":score,
      "opportunity":{"opportunity_id":opp},
      "diagnostics":{
        "entry_timing":"OPTIMAL",
        "chasing_risk":"LOW",
        "available_rr":1.8,
        "structural_obstacle":None
      },
      "plan":{"entry":100,"sl":99,"tp1":101.3,"tp2":101.8}
    }

# 1) All three lanes can be tested independently at the same time.
with tempfile.TemporaryDirectory() as td:
    lab=LaneComparisonLab(Path(td),CFG,100)
    lab.observe({
      "SCALP":sig("SCALP","S-1"),
      "INTRADAY":sig("INTRADAY","I-1"),
      "SWING":sig("SWING","W-1"),
    },market_regime="TREND")

    summary=lab.summary(100)
    assert summary["lanes"]["SCALP"]["open_trades"]==1
    assert summary["lanes"]["INTRADAY"]["open_trades"]==1
    assert summary["lanes"]["SWING"]["open_trades"]==1

# 2) Same Opportunity ID cannot be replayed after it has already traded.
with tempfile.TemporaryDirectory() as td:
    ledger=PaperLedger(Path(td)/"p.db",{
      **CFG,
      "paper_daily_loss_limit_pct":1000000,
      "paper_max_consecutive_losses":1000000,
    })
    s=sig("SCALP","SAME-OPP")
    ledger.maybe_open({"SCALP":s},market_regime="TREND")
    ledger.process_closed_bar({"ts":1,"open":100,"high":101.4,"low":100.2,"close":101.2})
    ledger.process_closed_bar({"ts":2,"open":101.2,"high":101.9,"low":101.0,"close":101.8})
    assert len(ledger.recent())==1

    ledger.maybe_open({"SCALP":s},market_regime="TREND")
    assert len(ledger.recent())==1

# 3) Ranking waits for sample size and then identifies stronger observed lane.
with tempfile.TemporaryDirectory() as td:
    lab=LaneComparisonLab(Path(td),CFG,100)

    # Nine SCALP winners are still insufficient for a provisional leader.
    for i in range(9):
        led=lab.ledgers["SCALP"]
        led.maybe_open({"SCALP":sig("SCALP",f"S-{i}")},market_regime="TREND")
        led.process_closed_bar({"ts":i*10+1,"open":100,"high":101.4,"low":100.2,"close":101.2})
        led.process_closed_bar({"ts":i*10+2,"open":101.2,"high":101.9,"low":101.0,"close":101.8})
    assert lab.summary(100)["best_observed_lane"] is None

    # 10th winner allows a provisional observed leader.
    led=lab.ledgers["SCALP"]
    led.maybe_open({"SCALP":sig("SCALP","S-9")},market_regime="TREND")
    led.process_closed_bar({"ts":91,"open":100,"high":101.4,"low":100.2,"close":101.2})
    led.process_closed_bar({"ts":92,"open":101.2,"high":101.9,"low":101.0,"close":101.8})

    # Ten INTRADAY losses for contrast.
    for i in range(10):
        led=lab.ledgers["INTRADAY"]
        led.maybe_open({"INTRADAY":sig("INTRADAY",f"I-{i}")},market_regime="TREND")
        led.process_closed_bar({"ts":200+i,"open":100,"high":100.2,"low":98.8,"close":99})

    result=lab.summary(100)
    assert result["best_observed_lane"]=="SCALP"
    assert result["lanes"]["SCALP"]["quality_score"] > result["lanes"]["INTRADAY"]["quality_score"]
    assert result["lanes"]["SCALP"]["evidence"]=="MEDIUM"

# 4) Capital reset starts fresh lab experiments while history is retained.
with tempfile.TemporaryDirectory() as td:
    lab=LaneComparisonLab(Path(td),CFG,100)
    old={lane:ledger.get_experiment_id() for lane,ledger in lab.ledgers.items()}
    lab.reset_capital(1000)

    for lane,ledger in lab.ledgers.items():
        assert ledger.get_start_balance()==1000
        assert ledger.get_experiment_id()!=old[lane]
        assert len(ledger.experiment_history())==2

print("V2.5 tests: OK")

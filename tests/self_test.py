from pathlib import Path
import tempfile, sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from btc_analyzer.analysis import MarketAnalyzer
from btc_analyzer.context import BitcoinContextEngine
from btc_analyzer.decision import DecisionEngine
from btc_analyzer.paper import PaperLedger

idx=pd.date_range("2025-01-01",periods=500,freq="D",tz="UTC")
close=np.linspace(50000,85000,500)
base=pd.DataFrame({
    "open":close*.999,"high":close*1.01,"low":close*.99,"close":close,
    "volume":np.linspace(100,150,500),"quote_volume":close*np.linspace(100,150,500),
    "taker_base":np.linspace(52,80,500),"taker_quote":close*np.linspace(52,80,500),
},index=idx)

frames={tf:base.tail(300).copy() for tf in MarketAnalyzer.ORDER}
analysis=MarketAnalyzer().analyze(frames,{
    "funding":0.0,"open_interest":1,"mark_price":85000,"status":"OK","error":None
})

ctx=BitcoinContextEngine()
ctx.api_key=""
context=ctx.evaluate({"1D":base,"1W":base},85000)
decision=DecisionEngine().evaluate(analysis,context,85000)
assert "SCALP" in decision["lanes"]

with tempfile.TemporaryDirectory() as td:
    cfg={
        "paper_start_balance":100,
        "paper_risk_per_trade_pct":1,
        "paper_fee_bps_per_side":0,
        "paper_slippage_bps":0,
        "paper_max_notional_multiple":100,
        "report_timezone_offset_hours":3,
        "lane_cooldowns_seconds":{"SCALP":0},
        "lane_expiry_seconds":{"SCALP":999999},
    }
    ledger=PaperLedger(Path(td)/"paper.db",cfg)
    ledger.maybe_open({
        "SCALP":{
            "action":"LONG","setup_grade":"A","setup_score":80,
            "plan":{"entry":100,"sl":99,"tp1":101.3,"tp2":101.8}
        }
    })
    ledger.process_closed_bar({"ts":1,"open":100,"high":101.4,"low":100.1,"close":101.2})
    ledger.process_closed_bar({"ts":2,"open":101.2,"high":102,"low":100.8,"close":101.9})
    assert ledger.pnl_dashboard()["total"]["net_pnl"]>0

print("BTC Analyzer V2.0 self-test: OK")

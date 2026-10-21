from __future__ import annotations
import json, os, threading, time
from copy import deepcopy
from pathlib import Path

from btc_analyzer.core import json_native
from btc_analyzer.data import MarketDataClient
from btc_analyzer.analysis import MarketAnalyzer
from btc_analyzer.context import BitcoinContextEngine
from btc_analyzer.decision import DecisionEngine
from btc_analyzer.paper import PaperLedger
from btc_analyzer.research import ResearchJournal, ShadowLab
from btc_analyzer.regime import MarketRegimeEngine

class Engine:
    VERSION="V2.1"

    def __init__(self,root:Path,cfg:dict):
        self.root=root
        self.cfg=cfg
        self.data_dir=Path(os.environ.get("DATA_DIR") or (root/"data"))
        self.data_dir.mkdir(parents=True,exist_ok=True)

        self.data=MarketDataClient(cfg.get("symbol","BTCUSDT"))
        self.analyzer=MarketAnalyzer()
        self.context=BitcoinContextEngine(
            session=self.data.s,
            refresh_seconds=cfg.get("bitbo_refresh_seconds",900)
        )
        self.decision=DecisionEngine()
        self.regime=MarketRegimeEngine()
        self.paper=PaperLedger(self.data_dir/"paper_v2.db",cfg)
        self.research=ResearchJournal(
            self.data_dir/"research_v2.db",
            cfg.get("research_snapshot_seconds",300)
        )
        self.shadow=ShadowLab(self.data_dir/"shadow_v2.db")

        self.state={"status":"STARTING","engine_version":self.VERSION}
        self.last_good=None
        self.last_success_ts=None
        self.last_error=None
        self.last_error_ts=None
        self.lock=threading.RLock()
        self.stop=threading.Event()

    def _neutral_context(self,error):
        return {
            "score":0.0,"regime":"NEUTRAL","components":{},
            "local":{"mayer_multiple":None,"sma200d":None,"ma200w":None,"distance_200w_pct":None},
            "bitbo":{"enabled":False,"status":"ERROR","error":str(error)}
        }

    def cycle(self):
        started=time.time()

        frames=self.data.closed_frames()
        live_price=self.data.live_price()
        closed_bar=self.data.latest_closed_1m_bar()
        futures=self.data.futures()

        # Existing virtual trades are evaluated only against a CLOSED 1m bar.
        # This avoids using the still-forming candle for historical outcomes.
        self.paper.process_closed_bar(closed_bar)
        self.shadow.process_bar(closed_bar)

        analysis=self.analyzer.analyze(frames,futures)
        market_regime=self.regime.evaluate(analysis)

        try:
            btc_context=self.context.evaluate(frames,live_price)
        except Exception as e:
            btc_context=self._neutral_context(e)

        decision=self.decision.evaluate(analysis,btc_context,live_price)

        # New virtual trades are opened AFTER processing the last closed bar,
        # so that bar can never hit a trade that did not yet exist.
        self.paper.maybe_open(decision["lanes"])
        self.shadow.observe(decision["shadow"])

        self.research.update_outcomes(live_price)
        self.research.snapshot(live_price,analysis,decision,btc_context)

        paper_pnl=self.paper.pnl_dashboard()
        open_positions=self.paper.open_positions(live_price)
        unrealized=self.paper.unrealized_summary(live_price)
        risk_guard=self.paper.risk_guard()
        lane_stats=self.paper.lane_stats()
        recent_trades=self.paper.recent()
        research_stats=self.research.stats()
        shadow_stats=self.shadow.stats()

        now=time.time()
        health={
            "engine_version":self.VERSION,
            "cycle_seconds":now-started,
            "last_success_ts":now,
            "last_success_age_sec":0,
            "last_error":self.last_error,
            "last_error_ts":self.last_error_ts,
            "spot_provider":self.data.spot_provider,
            "spot_error":self.data.last_spot_error,
            "futures_status":futures.get("status"),
            "futures_error":futures.get("error"),
            "bitbo_status":(btc_context.get("bitbo") or {}).get("status"),
            "data_freshness_sec":self.data.freshness(),
            "persistent_storage":bool(os.environ.get("DATA_DIR")),
            "data_dir":str(self.data_dir),
            "closed_candle_analysis":True,
            "live_price_separate":True,
            "custom_bars_closed_only":True,
            "regime_research_only":True,
        }

        st={
            "status":"OK",
            "engine_version":self.VERSION,
            "ts":now,
            "price":live_price,
            "analysis":analysis,
            "market_regime":market_regime,
            "bitcoin_context":btc_context,
            "decision":decision,
            "pnl":paper_pnl,
            "open_positions":open_positions,
            "unrealized":unrealized,
            "risk_guard":risk_guard,
            "lane_stats":lane_stats,
            "recent_trades":recent_trades,
            "research":research_stats,
            "shadow_compare":shadow_stats,
            "health":health,
        }

        with self.lock:
            self.state=st
            self.last_good=deepcopy(st)
            self.last_success_ts=now
            self.last_error=None

    def run(self):
        interval=max(10,int(self.cfg.get("engine_cycle_seconds",30)))
        while not self.stop.is_set():
            try:
                self.cycle()
            except Exception as e:
                now=time.time()
                self.last_error=str(e)
                self.last_error_ts=now
                with self.lock:
                    if self.last_good:
                        degraded=deepcopy(self.last_good)
                        degraded["status"]="DEGRADED"
                        degraded["health"]["last_error"]=str(e)
                        degraded["health"]["last_error_ts"]=now
                        degraded["health"]["last_success_age_sec"]=(
                            now-self.last_success_ts if self.last_success_ts else None
                        )
                        self.state=degraded
                    else:
                        self.state={
                            "status":"ERROR",
                            "engine_version":self.VERSION,
                            "error":str(e),
                            "ts":now,
                            "health":{
                                "last_error":str(e),
                                "last_error_ts":now,
                                "persistent_storage":bool(os.environ.get("DATA_DIR")),
                                "data_dir":str(self.data_dir)
                            }
                        }
            self.stop.wait(interval)

    def snapshot(self):
        with self.lock:
            st=deepcopy(self.state)
        if st.get("health") and self.last_success_ts:
            st["health"]["last_success_age_sec"]=max(0,time.time()-self.last_success_ts)
        return json.loads(json.dumps(st,default=json_native))

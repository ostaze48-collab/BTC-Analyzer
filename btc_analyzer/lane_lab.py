from __future__ import annotations
from copy import deepcopy
from pathlib import Path

from .paper import PaperLedger

class LaneComparisonLab:
    """
    Independent paper accounts for SCALP / INTRADAY / SWING.

    Purpose:
    measure each lane without the main account's "one trade globally" rule
    censoring the other lanes.

    Research-only: these lab accounts never affect main-account P&L or decisions.
    """

    LANES=("SCALP","INTRADAY","SWING")

    def __init__(self,data_dir:Path,cfg:dict,start_balance:float):
        self.data_dir=Path(data_dir)
        self.data_dir.mkdir(parents=True,exist_ok=True)

        lab_cfg=deepcopy(cfg)
        lab_cfg["paper_start_balance"]=float(start_balance)

        # Do not censor strategy research after a loss streak/day loss.
        # Each lane should keep taking every qualified setup so performance
        # can be measured rather than stopped by account-governance rules.
        lab_cfg["paper_daily_loss_limit_pct"]=1_000_000.0
        lab_cfg["paper_max_consecutive_losses"]=1_000_000
        lab_cfg["paper_max_open_trades"]=1

        self.ledgers={
            lane:PaperLedger(
                self.data_dir/f"lane_lab_{lane.lower()}_v2.db",
                lab_cfg
            )
            for lane in self.LANES
        }

        # On first creation, align a fresh lab with the main starting capital.
        for ledger in self.ledgers.values():
            history=ledger.experiment_history()
            current=history[0] if history else None
            if (
                current and
                current["trades"]==0 and
                abs(float(current["start_balance"])-float(start_balance))>1e-9
            ):
                ledger.set_start_balance(float(start_balance),reset_results=False)

    def process_closed_bar(self,bar):
        for ledger in self.ledgers.values():
            ledger.process_closed_bar(bar)

    def observe(self,lanes,market_regime=None):
        """
        Each lane gets its own independent account, therefore SCALP,
        INTRADAY and SWING may all have an open LAB trade at the same time.
        """
        for lane in self.LANES:
            signal=lanes.get(lane)
            if not signal:
                continue
            self.ledgers[lane].maybe_open(
                {lane:signal},
                market_regime=market_regime
            )

    def reset_capital(self,amount):
        return {
            lane:ledger.set_start_balance(float(amount),reset_results=True)
            for lane,ledger in self.ledgers.items()
        }

    @staticmethod
    def _clamp(x,lo,hi):
        return max(lo,min(hi,float(x)))

    def _quality_score(self,analytics,stats):
        """
        Provisional evidence-weighted score.
        It intentionally shrinks toward 50 when sample size is small.

        Inputs are mostly scale-free:
        expectancy in R, PF, drawdown %, WR.
        Dollar P&L is displayed but not used to rank strategy quality.
        """
        n=int(analytics.get("trades") or 0)
        exp_r=float(analytics.get("expectancy_r") or 0)
        pf=float(analytics.get("profit_factor") or 0)
        dd=float(analytics.get("max_drawdown_pct") or 0)
        wr=float(stats.get("win_rate") or 0)

        pf_capped=min(pf,3.0)
        raw=50.0
        raw += self._clamp(exp_r,-1.0,1.0)*25.0
        raw += self._clamp(pf_capped-1.0,-1.0,2.0)*10.0
        raw += self._clamp((wr-50.0)/50.0,-1.0,1.0)*8.0
        raw -= min(dd,20.0)*1.2
        raw=self._clamp(raw,0,100)

        reliability=min(1.0,n/30.0)
        score=50.0+(raw-50.0)*reliability

        if n<10:
            evidence="LOW"
        elif n<30:
            evidence="MEDIUM"
        else:
            evidence="HIGH"

        return round(score,1),evidence,round(reliability*100,1)

    def summary(self,live_price=None):
        lanes={}
        for lane,ledger in self.ledgers.items():
            analytics=ledger.analytics()
            lane_stats=ledger.lane_stats().get(lane,{})
            pnl=ledger.pnl_dashboard()
            opens=ledger.open_positions(live_price)
            score,evidence,reliability=self._quality_score(
                analytics,lane_stats
            )

            lanes[lane]={
                "lane":lane,
                "starting_capital":pnl.get("starting_capital"),
                "balance":pnl.get("balance"),
                "closed_trades":analytics.get("trades",0),
                "open_trades":len(opens),
                "wins":lane_stats.get("wins",0),
                "losses":lane_stats.get("losses",0),
                "win_rate":lane_stats.get("win_rate",0),
                "net_pnl":analytics.get("net_pnl",0),
                "return_pct":analytics.get("return_pct",0),
                "expectancy_r":analytics.get("expectancy_r",0),
                "expectancy_usd":analytics.get("expectancy_usd",0),
                "profit_factor":analytics.get("profit_factor",0),
                "max_drawdown_pct":analytics.get("max_drawdown_pct",0),
                "max_drawdown_usd":analytics.get("max_drawdown_usd",0),
                "payoff_ratio":analytics.get("payoff_ratio",0),
                "recovery_factor":analytics.get("recovery_factor",0),
                "quality_score":score,
                "evidence":evidence,
                "reliability_pct":reliability,
                "avg_mfe_r":lane_stats.get("avg_mfe_r",0),
                "avg_mae_r":lane_stats.get("avg_mae_r",0),
                "capture_efficiency":lane_stats.get("avg_capture_efficiency",0),
                "experiment_id":analytics.get("experiment_id"),
            }

        ranked=sorted(
            lanes.values(),
            key=lambda x:(
                x["quality_score"],
                x["closed_trades"],
                x["expectancy_r"]
            ),
            reverse=True
        )

        enough=[x for x in ranked if x["closed_trades"]>=10]
        leader=enough[0] if enough else None

        return {
            "research_only":True,
            "ranking_method":"Evidence-weighted: Expectancy R + PF + WR - Drawdown; shrunk toward neutral until 30 closed trades.",
            "minimum_for_provisional_leader":10,
            "target_for_high_evidence":30,
            "best_observed_lane":leader["lane"] if leader else None,
            "best_observed_score":leader["quality_score"] if leader else None,
            "status":"PROVISIONAL" if leader else "WAITING_FOR_DATA",
            "lanes":lanes,
            "ranking":[x["lane"] for x in ranked],
        }

    def regime_comparison(self):
        out=[]
        for lane,ledger in self.ledgers.items():
            for row in ledger.regime_stats():
                row=dict(row)
                row["lane"]=lane
                out.append(row)
        return sorted(out,key=lambda x:(x.get("regime") or "",x["lane"]))

    def price_action_comparison(self):
        out=[]
        for lane,ledger in self.ledgers.items():
            for row in ledger.price_action_stats():
                x=dict(row)
                x["lane"]=lane
                out.append(x)
        return sorted(out,key=lambda x:(x.get("label") or "",x["lane"]))

    def execution_plan_comparison(self):
        out=[]
        for lane,ledger in self.ledgers.items():
            for row in ledger.execution_plan_stats():
                x=dict(row)
                x["lane"]=lane
                out.append(x)
        return sorted(out,key=lambda x:(x.get("label") or "",x["lane"]))

    def histories(self):
        return {
            lane:ledger.experiment_history()
            for lane,ledger in self.ledgers.items()
        }

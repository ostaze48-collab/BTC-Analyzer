from __future__ import annotations
import sqlite3, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core import safe

class PaperLedger:
    """
    Main virtual account only: SCALP + INTRADAY + SWING.
    Shadow strategies are intentionally excluded from account P&L totals.
    """

    def __init__(self, db_path, cfg):
        self.db_path=str(db_path)
        self.start_balance=float(cfg.get("paper_start_balance",100.0))
        self.risk_pct=float(cfg.get("paper_risk_per_trade_pct",0.5))
        self.fee_bps=float(cfg.get("paper_fee_bps_per_side",0.0))
        self.slippage_bps=float(cfg.get("paper_slippage_bps",0.0))
        self.max_notional_multiple=float(cfg.get("paper_max_notional_multiple",3.0))
        self.tz_offset=int(cfg.get("report_timezone_offset_hours",3))
        self.cooldowns=cfg.get("lane_cooldowns_seconds",{})
        self.expiries=cfg.get("lane_expiry_seconds",{})
        self._init()

    def con(self):
        c=sqlite3.connect(self.db_path,timeout=10)
        c.row_factory=sqlite3.Row
        return c

    def _init(self):
        c=self.con()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS trades(
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
        );
        CREATE INDEX IF NOT EXISTS idx_trades_close ON trades(close_ts);
        CREATE INDEX IF NOT EXISTS idx_trades_lane ON trades(lane,status);
        """)
        c.commit(); c.close()

    def _fee(self, notional):
        return abs(float(notional))*self.fee_bps/10000.0

    def balance(self):
        c=self.con()
        row=c.execute("SELECT COALESCE(SUM(net_pnl),0) pnl FROM trades WHERE status!='OPEN'").fetchone()
        c.close()
        return self.start_balance + float(row["pnl"] or 0)

    def maybe_open(self,lanes,now=None):
        now=now or time.time()
        c=self.con()
        bal=max(.01,self.balance())
        for lane,s in lanes.items():
            if s.get("action") not in ("LONG","SHORT"):
                continue
            p=s.get("plan") or {}
            if any(p.get(k) is None for k in ("entry","sl","tp1","tp2")):
                continue

            if c.execute("SELECT 1 FROM trades WHERE lane=? AND status='OPEN' LIMIT 1",(lane,)).fetchone():
                continue
            last=c.execute("SELECT open_ts FROM trades WHERE lane=? ORDER BY id DESC LIMIT 1",(lane,)).fetchone()
            cooldown=float(self.cooldowns.get(lane,600))
            if last and now-float(last["open_ts"])<cooldown:
                continue

            side=s["action"]
            entry=float(p["entry"])
            slip=self.slippage_bps/10000.0
            entry=entry*(1+slip if side=="LONG" else 1-slip)
            sl=float(p["sl"]); tp1=float(p["tp1"]); tp2=float(p["tp2"])
            stop_dist=abs(entry-sl)
            if stop_dist<=0:
                continue

            target_risk=bal*self.risk_pct/100.0
            qty_by_risk=target_risk/stop_dist
            max_notional=bal*self.max_notional_multiple
            qty_cap=max_notional/max(entry,1e-9)
            qty=max(0,min(qty_by_risk,qty_cap))
            if qty<=0:
                continue

            risk_usd=qty*stop_dist
            notional=qty*entry
            entry_fee=self._fee(notional)

            c.execute("""
              INSERT INTO trades(
                engine_version,lane,side,open_ts,entry,sl,tp1,tp2,
                quantity,risk_usd,notional_usd,setup_grade,setup_score,
                fees,reason
              ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,(
                "V2.0",lane,side,now,entry,sl,tp1,tp2,
                qty,risk_usd,notional,s.get("setup_grade"),safe(s.get("setup_score")),
                entry_fee,"MAIN_LANE_SIGNAL"
            ))
        c.commit(); c.close()

    @staticmethod
    def _signed_move(side,entry,exit_price):
        return (exit_price-entry) if side=="LONG" else (entry-exit_price)

    def _finish(self,c,r,exit_price,status,close_ts):
        qty=float(r["quantity"])
        partial=float(r["partial_gross"] or 0)
        remaining=qty*(.5 if int(r["tp1_hit"] or 0) else 1.0)
        gross=partial + self._signed_move(r["side"],float(r["entry"]),exit_price)*remaining
        fees=float(r["fees"] or 0) + self._fee(exit_price*remaining)
        net=gross-fees
        realized_r=net/max(float(r["risk_usd"]),1e-9)
        final_status=status
        if status not in ("EXPIRED","CANCELLED"):
            final_status="WIN" if net>0 else "LOSS" if net<0 else "BE"
        c.execute("""
          UPDATE trades
          SET status=?,close_ts=?,exit_price=?,gross_pnl=?,fees=?,net_pnl=?,realized_r=?
          WHERE id=?
        """,(final_status,close_ts,exit_price,gross,fees,net,realized_r,r["id"]))

    def process_closed_bar(self,bar):
        if not bar:
            return
        bar_ts=float(bar["ts"])
        hi=float(bar["high"]); lo=float(bar["low"]); close=float(bar["close"])
        now=time.time()
        c=self.con()
        rows=c.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()

        for r in rows:
            if float(r["last_bar_ts"] or 0)>=bar_ts:
                continue
            side=r["side"]
            sl=float(r["sl"]); tp1=float(r["tp1"]); tp2=float(r["tp2"])

            if side=="LONG":
                sl_hit=lo<=sl
                tp1_hit_bar=hi>=tp1
                tp2_hit_bar=hi>=tp2
            else:
                sl_hit=hi>=sl
                tp1_hit_bar=lo<=tp1
                tp2_hit_bar=lo<=tp2

            already_tp1=bool(r["tp1_hit"])

            if not already_tp1:
                # Conservative same-bar rule: if stop and target are both touched,
                # assume the stop happened first.
                if sl_hit:
                    self._finish(c,r,sl,"LOSS",now)
                    continue
                if tp1_hit_bar:
                    qty=float(r["quantity"])*.5
                    partial=self._signed_move(side,float(r["entry"]),tp1)*qty
                    fees=float(r["fees"] or 0)+self._fee(tp1*qty)
                    c.execute("""
                      UPDATE trades
                      SET tp1_hit=1,tp1_ts=?,partial_gross=?,fees=?,last_bar_ts=?
                      WHERE id=?
                    """,(now,partial,fees,bar_ts,r["id"]))
                    # If TP2 also occurred in this same bar, do not assume TP2
                    # after TP1. We wait for a subsequent closed bar.
                    continue
            else:
                # After TP1, remaining 50% stays active. Same-bar ambiguity is
                # again resolved conservatively in favor of the stop.
                if sl_hit:
                    self._finish(c,r,sl,"LOSS",now)
                    continue
                if tp2_hit_bar:
                    self._finish(c,r,tp2,"WIN",now)
                    continue

            expiry=float(self.expiries.get(r["lane"],86400))
            if now-float(r["open_ts"])>=expiry:
                self._finish(c,r,close,"EXPIRED",now)
                continue

            c.execute("UPDATE trades SET last_bar_ts=? WHERE id=?",(bar_ts,r["id"]))

        c.commit(); c.close()

    def _period_start(self,period):
        tz=timezone(timedelta(hours=self.tz_offset))
        now=datetime.now(tz)
        if period=="day":
            start=now.replace(hour=0,minute=0,second=0,microsecond=0)
        elif period=="week":
            start=(now-timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
        elif period=="month":
            start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        else:
            return None
        return start.timestamp()

    def _summary(self,start_ts=None):
        c=self.con()
        q="SELECT * FROM trades WHERE status!='OPEN'"
        args=[]
        if start_ts is not None:
            q+=" AND close_ts>=?"
            args.append(start_ts)
        rows=c.execute(q,args).fetchall()
        c.close()

        net=[float(r["net_pnl"] or 0) for r in rows]
        gross=[float(r["gross_pnl"] or 0) for r in rows]
        wins=sum(1 for x in net if x>0)
        losses=sum(1 for x in net if x<0)
        bes=sum(1 for x in net if x==0)
        gp=sum(x for x in gross if x>0)
        gl=abs(sum(x for x in gross if x<0))
        fees=sum(float(r["fees"] or 0) for r in rows)
        total_r=sum(float(r["realized_r"] or 0) for r in rows)
        return {
            "trades":len(rows),"wins":wins,"losses":losses,"be":bes,
            "win_rate":wins/max(1,wins+losses)*100,
            "gross_profit":gp,"gross_loss":gl,"fees":fees,
            "net_pnl":sum(net),"total_r":total_r,
            "profit_factor":gp/gl if gl>0 else (999 if gp>0 else 0)
        }

    def pnl_dashboard(self):
        return {
            "day":self._summary(self._period_start("day")),
            "week":self._summary(self._period_start("week")),
            "month":self._summary(self._period_start("month")),
            "total":self._summary(None),
            "balance":self.balance(),
            "timezone":f"UTC{self.tz_offset:+d}"
        }

    def lane_stats(self):
        c=self.con()
        out={}
        for lane in ("SCALP","INTRADAY","SWING"):
            rows=c.execute("SELECT * FROM trades WHERE lane=? ORDER BY id DESC",(lane,)).fetchall()
            closed=[r for r in rows if r["status"]!="OPEN"]
            wins=[r for r in closed if float(r["net_pnl"] or 0)>0]
            losses=[r for r in closed if float(r["net_pnl"] or 0)<0]
            gp=sum(max(0,float(r["gross_pnl"] or 0)) for r in closed)
            gl=abs(sum(min(0,float(r["gross_pnl"] or 0)) for r in closed))
            out[lane]={
                "trades":len(rows),
                "open":sum(1 for r in rows if r["status"]=="OPEN"),
                "wins":len(wins),"losses":len(losses),
                "win_rate":len(wins)/max(1,len(wins)+len(losses))*100,
                "net_pnl":sum(float(r["net_pnl"] or 0) for r in closed),
                "avg_r":sum(float(r["realized_r"] or 0) for r in closed)/max(1,len(closed)),
                "profit_factor":gp/gl if gl>0 else (999 if gp>0 else 0),
            }
        c.close()
        return out

    def recent(self,limit=30):
        c=self.con()
        rows=[dict(r) for r in c.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?",(int(limit),)
        ).fetchall()]
        c.close()
        return rows

from __future__ import annotations
import sqlite3, time
from datetime import datetime, timedelta, timezone

class PaperLedger:
    """
    Primary virtual account only: SCALP + INTRADAY + SWING.
    V2.2 adds non-destructive schema migration, Opportunity IDs,
    market-regime tagging, MFE/MAE and capture efficiency.
    """

    EXTRA_COLUMNS={
        "opportunity_id":"TEXT",
        "market_regime":"TEXT",
        "entry_timing":"TEXT",
        "chasing_risk":"TEXT",
        "available_rr":"REAL",
        "structural_obstacle":"REAL",
        "mfe_price":"REAL",
        "mae_price":"REAL",
        "mfe_r":"REAL DEFAULT 0",
        "mae_r":"REAL DEFAULT 0",
        "capture_efficiency_pct":"REAL",
    }

    def __init__(self,db_path,cfg):
        self.db_path=str(db_path)
        self.start_balance=float(cfg.get("paper_start_balance",100.0))
        self.risk_pct=float(cfg.get("paper_risk_per_trade_pct",0.5))
        self.fee_bps=float(cfg.get("paper_fee_bps_per_side",0.0))
        self.slippage_bps=float(cfg.get("paper_slippage_bps",0.0))
        self.max_notional_multiple=float(cfg.get("paper_max_notional_multiple",3.0))
        self.tz_offset=int(cfg.get("report_timezone_offset_hours",3))
        self.cooldowns=cfg.get("lane_cooldowns_seconds",{})
        self.expiries=cfg.get("lane_expiry_seconds",{})
        self.daily_loss_limit_pct=float(cfg.get("paper_daily_loss_limit_pct",3.0))
        self.max_consecutive_losses=int(cfg.get("paper_max_consecutive_losses",4))
        self.max_open_trades=int(cfg.get("paper_max_open_trades",3))
        self._init()

    def con(self):
        c=sqlite3.connect(self.db_path,timeout=10)
        c.row_factory=sqlite3.Row
        return c

    def _migrate(self,c):
        existing={r["name"] for r in c.execute("PRAGMA table_info(trades)").fetchall()}
        for name,ddl in self.EXTRA_COLUMNS.items():
            if name not in existing:
                c.execute(f"ALTER TABLE trades ADD COLUMN {name} {ddl}")
        c.execute("CREATE INDEX IF NOT EXISTS idx_trades_opp ON trades(opportunity_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_trades_regime ON trades(market_regime,status)")

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
          reason TEXT,
          opportunity_id TEXT,
          market_regime TEXT,
          entry_timing TEXT,
          chasing_risk TEXT,
          available_rr REAL,
          structural_obstacle REAL,
          mfe_price REAL,
          mae_price REAL,
          mfe_r REAL DEFAULT 0,
          mae_r REAL DEFAULT 0,
          capture_efficiency_pct REAL
        );
        CREATE INDEX IF NOT EXISTS idx_trades_close ON trades(close_ts);
        CREATE INDEX IF NOT EXISTS idx_trades_lane ON trades(lane,status);
        """)
        self._migrate(c)
        c.commit(); c.close()

    def _fee(self,notional):
        return abs(float(notional))*self.fee_bps/10000.0

    def balance(self):
        c=self.con()
        row=c.execute("SELECT COALESCE(SUM(net_pnl),0) pnl FROM trades WHERE status!='OPEN'").fetchone()
        c.close()
        return self.start_balance+float(row["pnl"] or 0)

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

    def risk_guard(self):
        day=self._summary(self._period_start("day"))
        c=self.con()
        open_count=int(c.execute("SELECT COUNT(*) n FROM trades WHERE status='OPEN'").fetchone()["n"] or 0)
        recent=c.execute("""
          SELECT net_pnl FROM trades
          WHERE status!='OPEN'
          ORDER BY close_ts DESC LIMIT ?
        """,(self.max_consecutive_losses,)).fetchall()
        c.close()

        consecutive_losses=0
        for r in recent:
            if float(r["net_pnl"] or 0)<0:
                consecutive_losses+=1
            else:
                break

        daily_limit_usd=self.start_balance*self.daily_loss_limit_pct/100.0
        reasons=[]
        if day["net_pnl"]<=-daily_limit_usd:
            reasons.append("DAILY_LOSS_LIMIT")
        if consecutive_losses>=self.max_consecutive_losses:
            reasons.append("CONSECUTIVE_LOSS_LIMIT")
        if open_count>=self.max_open_trades:
            reasons.append("MAX_OPEN_TRADES")

        return {
            "allow_new_trades":not reasons,
            "reasons":reasons,
            "daily_loss_limit_usd":daily_limit_usd,
            "daily_net_pnl":day["net_pnl"],
            "consecutive_losses":consecutive_losses,
            "max_consecutive_losses":self.max_consecutive_losses,
            "open_trades":open_count,
            "max_open_trades":self.max_open_trades,
        }

    def maybe_open(self,lanes,market_regime=None,now=None):
        now=now or time.time()
        if not self.risk_guard()["allow_new_trades"]:
            return
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
            diag=s.get("diagnostics") or {}
            opp=s.get("opportunity") or {}

            c.execute("""
              INSERT INTO trades(
                engine_version,lane,side,open_ts,entry,sl,tp1,tp2,
                quantity,risk_usd,notional_usd,setup_grade,setup_score,
                fees,reason,opportunity_id,market_regime,
                entry_timing,chasing_risk,available_rr,structural_obstacle,
                mfe_price,mae_price,mfe_r,mae_r
              ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,(
                "V2.2",lane,side,now,entry,sl,tp1,tp2,
                qty,risk_usd,notional,s.get("setup_grade"),float(s.get("setup_score") or 0),
                entry_fee,"MAIN_LANE_SIGNAL",
                opp.get("opportunity_id"),market_regime,
                diag.get("entry_timing"),diag.get("chasing_risk"),
                float(diag.get("available_rr") or 0),
                diag.get("structural_obstacle"),
                entry,entry,0.0,0.0
            ))
        c.commit(); c.close()

    @staticmethod
    def _signed_move(side,entry,exit_price):
        return (exit_price-entry) if side=="LONG" else (entry-exit_price)

    def _update_excursion(self,c,r,favorable=None,adverse=None):
        entry=float(r["entry"])
        stop_dist=max(abs(entry-float(r["sl"])),1e-9)
        mfe=float(r["mfe_price"]) if r["mfe_price"] is not None else entry
        mae=float(r["mae_price"]) if r["mae_price"] is not None else entry

        if r["side"]=="LONG":
            if favorable is not None: mfe=max(mfe,float(favorable))
            if adverse is not None: mae=min(mae,float(adverse))
            mfe_r=(mfe-entry)/stop_dist
            mae_r=(mae-entry)/stop_dist
        else:
            if favorable is not None: mfe=min(mfe,float(favorable))
            if adverse is not None: mae=max(mae,float(adverse))
            mfe_r=(entry-mfe)/stop_dist
            mae_r=(entry-mae)/stop_dist

        c.execute("""
          UPDATE trades
          SET mfe_price=?,mae_price=?,mfe_r=?,mae_r=?
          WHERE id=?
        """,(mfe,mae,mfe_r,mae_r,r["id"]))

    def _fresh(self,c,trade_id):
        return c.execute("SELECT * FROM trades WHERE id=?",(trade_id,)).fetchone()

    def _finish(self,c,r,exit_price,status,close_ts):
        r=self._fresh(c,r["id"])
        qty=float(r["quantity"])
        partial=float(r["partial_gross"] or 0)
        remaining=qty*(.5 if int(r["tp1_hit"] or 0) else 1.0)
        gross=partial+self._signed_move(r["side"],float(r["entry"]),exit_price)*remaining
        fees=float(r["fees"] or 0)+self._fee(exit_price*remaining)
        net=gross-fees
        realized_r=net/max(float(r["risk_usd"]),1e-9)
        mfe_r=max(0,float(r["mfe_r"] or 0))
        efficiency=(max(0,realized_r)/mfe_r*100) if mfe_r>1e-9 else 0.0
        efficiency=max(0,min(100,efficiency))

        final_status=status
        if status not in ("EXPIRED","CANCELLED"):
            final_status="WIN" if net>0 else "LOSS" if net<0 else "BE"

        c.execute("""
          UPDATE trades
          SET status=?,close_ts=?,exit_price=?,gross_pnl=?,fees=?,
              net_pnl=?,realized_r=?,capture_efficiency_pct=?
          WHERE id=?
        """,(final_status,close_ts,exit_price,gross,fees,net,realized_r,efficiency,r["id"]))

    def process_closed_bar(self,bar):
        if not bar:
            return
        bar_ts=float(bar["ts"])
        hi=float(bar["high"]); lo=float(bar["low"]); close=float(bar["close"])
        now=time.time()
        c=self.con()
        rows=c.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()

        for original in rows:
            if float(original["last_bar_ts"] or 0)>=bar_ts:
                continue
            r=self._fresh(c,original["id"])
            side=r["side"]
            sl=float(r["sl"]); tp1=float(r["tp1"]); tp2=float(r["tp2"])
            if side=="LONG":
                sl_hit=lo<=sl; tp1_hit_bar=hi>=tp1; tp2_hit_bar=hi>=tp2
                favorable_bar=hi; adverse_bar=lo
            else:
                sl_hit=hi>=sl; tp1_hit_bar=lo<=tp1; tp2_hit_bar=lo<=tp2
                favorable_bar=lo; adverse_bar=hi

            already_tp1=bool(r["tp1_hit"])

            if not already_tp1:
                if sl_hit:
                    # Conservative sequencing: stop first; do not credit favorable
                    # excursion from an ambiguous stop bar.
                    self._update_excursion(c,r,adverse=sl)
                    self._finish(c,r,sl,"LOSS",now)
                    continue

                if tp1_hit_bar:
                    self._update_excursion(c,r,favorable=tp1,adverse=adverse_bar)
                    r=self._fresh(c,r["id"])
                    qty=float(r["quantity"])*.5
                    partial=self._signed_move(side,float(r["entry"]),tp1)*qty
                    fees=float(r["fees"] or 0)+self._fee(tp1*qty)
                    c.execute("""
                      UPDATE trades
                      SET tp1_hit=1,tp1_ts=?,partial_gross=?,fees=?,last_bar_ts=?
                      WHERE id=?
                    """,(now,partial,fees,bar_ts,r["id"]))
                    continue

                self._update_excursion(c,r,favorable=favorable_bar,adverse=adverse_bar)

            else:
                if sl_hit:
                    self._update_excursion(c,r,adverse=sl)
                    self._finish(c,r,sl,"LOSS",now)
                    continue

                if tp2_hit_bar:
                    self._update_excursion(c,r,favorable=tp2,adverse=adverse_bar)
                    self._finish(c,r,tp2,"WIN",now)
                    continue

                self._update_excursion(c,r,favorable=favorable_bar,adverse=adverse_bar)

            r=self._fresh(c,r["id"])
            expiry=float(self.expiries.get(r["lane"],86400))
            if now-float(r["open_ts"])>=expiry:
                self._finish(c,r,close,"EXPIRED",now)
                continue

            c.execute("UPDATE trades SET last_bar_ts=? WHERE id=?",(bar_ts,r["id"]))

        c.commit(); c.close()

    def open_positions(self,live_price):
        c=self.con()
        rows=c.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY open_ts ASC").fetchall()
        c.close()
        out=[]
        now=time.time()
        live=float(live_price) if live_price is not None else 0.0

        for r in rows:
            entry=float(r["entry"]); qty=float(r["quantity"])
            tp1_hit=bool(r["tp1_hit"])
            remaining=qty*(.5 if tp1_hit else 1.0)
            partial=float(r["partial_gross"] or 0)
            move=(live-entry) if r["side"]=="LONG" else (entry-live)
            unrealized=partial+move*remaining
            current_r=unrealized/max(float(r["risk_usd"]),1e-9)

            def dist(level):
                level=float(level)
                if r["side"]=="LONG":
                    return (level-live)/max(live,1e-9)*100
                return (live-level)/max(live,1e-9)*100

            out.append({
                "id":r["id"],"lane":r["lane"],"side":r["side"],
                "opportunity_id":r["opportunity_id"],
                "market_regime":r["market_regime"],
                "setup_grade":r["setup_grade"],"setup_score":r["setup_score"],
                "entry_timing":r["entry_timing"],"chasing_risk":r["chasing_risk"],
                "available_rr":r["available_rr"],
                "trade_state":"TP1_HIT" if tp1_hit else "OPEN",
                "entry":entry,"live_price":live,
                "sl":float(r["sl"]),"tp1":float(r["tp1"]),"tp2":float(r["tp2"]),
                "unrealized_pnl":unrealized,"current_r":current_r,
                "mfe_r":float(r["mfe_r"] or 0),"mae_r":float(r["mae_r"] or 0),
                "age_sec":max(0,now-float(r["open_ts"])),
                "distance_to_sl_pct":dist(r["sl"]),
                "distance_to_tp1_pct":dist(r["tp1"]),
                "distance_to_tp2_pct":dist(r["tp2"]),
                "tp1_hit":tp1_hit,
            })
        return out

    def unrealized_summary(self,live_price):
        rows=self.open_positions(live_price)
        return {
            "open_trades":len(rows),
            "unrealized_pnl":sum(float(x["unrealized_pnl"]) for x in rows),
            "current_r":sum(float(x["current_r"]) for x in rows),
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
                "trades":len(rows),"open":sum(1 for r in rows if r["status"]=="OPEN"),
                "wins":len(wins),"losses":len(losses),
                "win_rate":len(wins)/max(1,len(wins)+len(losses))*100,
                "net_pnl":sum(float(r["net_pnl"] or 0) for r in closed),
                "avg_r":sum(float(r["realized_r"] or 0) for r in closed)/max(1,len(closed)),
                "avg_mfe_r":sum(float(r["mfe_r"] or 0) for r in closed)/max(1,len(closed)),
                "avg_mae_r":sum(float(r["mae_r"] or 0) for r in closed)/max(1,len(closed)),
                "avg_capture_efficiency":sum(float(r["capture_efficiency_pct"] or 0) for r in closed)/max(1,len(closed)),
                "profit_factor":gp/gl if gl>0 else (999 if gp>0 else 0),
            }
        c.close()
        return out

    def regime_stats(self):
        c=self.con()
        rows=c.execute("""
          SELECT lane,COALESCE(market_regime,'UNKNOWN') regime,
                 COUNT(*) trades,
                 SUM(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END) wins,
                 SUM(CASE WHEN net_pnl<0 THEN 1 ELSE 0 END) losses,
                 AVG(realized_r) avg_r,
                 AVG(mfe_r) avg_mfe_r,
                 AVG(mae_r) avg_mae_r,
                 AVG(capture_efficiency_pct) efficiency,
                 SUM(net_pnl) net_pnl
          FROM trades
          WHERE status!='OPEN'
          GROUP BY lane,COALESCE(market_regime,'UNKNOWN')
          ORDER BY lane,regime
        """).fetchall()
        c.close()
        out=[]
        for r in rows:
            wins=int(r["wins"] or 0); losses=int(r["losses"] or 0)
            out.append({
                "lane":r["lane"],"regime":r["regime"],"trades":int(r["trades"] or 0),
                "wins":wins,"losses":losses,
                "win_rate":wins/max(1,wins+losses)*100,
                "avg_r":float(r["avg_r"] or 0),
                "avg_mfe_r":float(r["avg_mfe_r"] or 0),
                "avg_mae_r":float(r["avg_mae_r"] or 0),
                "capture_efficiency":float(r["efficiency"] or 0),
                "net_pnl":float(r["net_pnl"] or 0),
            })
        return out

    def calibration_stats(self):
        c=self.con()
        result={"entry_timing":[],"chasing_risk":[]}
        for field in ("entry_timing","chasing_risk"):
            rows=c.execute(f"""
              SELECT COALESCE({field},'UNKNOWN') label,
                     COUNT(*) trades,
                     SUM(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END) wins,
                     SUM(CASE WHEN net_pnl<0 THEN 1 ELSE 0 END) losses,
                     AVG(realized_r) avg_r,
                     AVG(capture_efficiency_pct) efficiency
              FROM trades
              WHERE status!='OPEN'
              GROUP BY COALESCE({field},'UNKNOWN')
              ORDER BY trades DESC
            """).fetchall()
            result[field]=[{
                "label":r["label"],"trades":int(r["trades"] or 0),
                "wins":int(r["wins"] or 0),"losses":int(r["losses"] or 0),
                "win_rate":int(r["wins"] or 0)/max(1,int(r["wins"] or 0)+int(r["losses"] or 0))*100,
                "avg_r":float(r["avg_r"] or 0),
                "capture_efficiency":float(r["efficiency"] or 0),
            } for r in rows]
        c.close()
        return result

    def recent(self,limit=30):
        c=self.con()
        rows=[dict(r) for r in c.execute(
            "SELECT * FROM trades ORDER BY id DESC LIMIT ?",(int(limit),)
        ).fetchall()]
        c.close()
        return rows

from __future__ import annotations
import json, sqlite3, time, uuid
from datetime import datetime, timedelta, timezone

class PaperLedger:
    """
    Primary virtual account only: SCALP + INTRADAY + SWING.

    V2.4 adds experiment history and performance analytics while preserving:
    - one main trade at a time,
    - closed-bar outcome processing,
    - Opportunity IDs,
    - MFE/MAE,
    - capture efficiency,
    - non-destructive schema migration.
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
        "experiment_id":"TEXT",
        "price_action_state":"TEXT",
        "price_action_score":"REAL",
        "price_action_evidence":"TEXT",
    }

    VALID_CLOSED_STATUSES=("WIN","LOSS","BE","EXPIRED")

    def __init__(self,db_path,cfg):
        self.db_path=str(db_path)
        self.default_start_balance=float(cfg.get("paper_start_balance",100.0))
        self.start_balance=self.default_start_balance
        self.risk_pct=float(cfg.get("paper_risk_per_trade_pct",0.5))
        self.fee_bps=float(cfg.get("paper_fee_bps_per_side",0.0))
        self.slippage_bps=float(cfg.get("paper_slippage_bps",0.0))
        self.max_notional_multiple=float(cfg.get("paper_max_notional_multiple",3.0))
        self.tz_offset=int(cfg.get("report_timezone_offset_hours",3))
        self.cooldowns=cfg.get("lane_cooldowns_seconds",{})
        self.expiries=cfg.get("lane_expiry_seconds",{})
        self.daily_loss_limit_pct=float(cfg.get("paper_daily_loss_limit_pct",3.0))
        self.max_consecutive_losses=int(cfg.get("paper_max_consecutive_losses",4))
        # V2.3+ policy: only one main trade globally.
        self.max_open_trades=1
        self.current_experiment_id=None
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
        c.execute("CREATE INDEX IF NOT EXISTS idx_trades_experiment ON trades(experiment_id,status)")

    def _setting(self,c,key,default=None):
        row=c.execute("SELECT value FROM paper_settings WHERE key=?",(key,)).fetchone()
        return row["value"] if row else default

    def _set_setting(self,c,key,value):
        c.execute("""
          INSERT INTO paper_settings(key,value)
          VALUES(?,?)
          ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,(key,str(value)))

    def _new_experiment_id(self):
        stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
        return f"EXP-{stamp}-{uuid.uuid4().hex[:6].upper()}"

    def _create_experiment(self,c,amount,note=""):
        eid=self._new_experiment_id()
        now=time.time()
        c.execute("""
          INSERT INTO paper_experiments(
            experiment_id,start_ts,start_balance,status,note
          ) VALUES(?,?,?,'ACTIVE',?)
        """,(eid,now,float(amount),note))
        self._set_setting(c,"current_experiment_id",eid)
        self._set_setting(c,"start_balance",float(amount))
        return eid

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
          capture_efficiency_pct REAL,
          experiment_id TEXT,
          price_action_state TEXT,
          price_action_score REAL,
          price_action_evidence TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_trades_close ON trades(close_ts);
        CREATE INDEX IF NOT EXISTS idx_trades_lane ON trades(lane,status);

        CREATE TABLE IF NOT EXISTS paper_settings(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS paper_experiments(
          experiment_id TEXT PRIMARY KEY,
          start_ts REAL NOT NULL,
          end_ts REAL,
          start_balance REAL NOT NULL,
          status TEXT NOT NULL,
          note TEXT
        );
        """)
        self._migrate(c)

        raw_balance=self._setting(c,"start_balance",self.default_start_balance)
        try:
            self.start_balance=max(1.0,float(raw_balance))
        except Exception:
            self.start_balance=self.default_start_balance

        eid=self._setting(c,"current_experiment_id")
        active=None
        if eid:
            active=c.execute("""
              SELECT * FROM paper_experiments
              WHERE experiment_id=? AND status='ACTIVE'
            """,(eid,)).fetchone()

        # Migration path from V2.0-V2.3: create one experiment and attach
        # all existing untagged trades to it.
        if active is None:
            eid=self._create_experiment(c,self.start_balance,"Migrated/current experiment")
            c.execute("""
              UPDATE trades
              SET experiment_id=?
              WHERE experiment_id IS NULL OR experiment_id=''
            """,(eid,))
            active=c.execute(
                "SELECT * FROM paper_experiments WHERE experiment_id=?",(eid,)
            ).fetchone()

        self.current_experiment_id=active["experiment_id"]
        self.start_balance=float(active["start_balance"])
        self._set_setting(c,"start_balance",self.start_balance)
        self._set_setting(c,"current_experiment_id",self.current_experiment_id)

        c.commit()
        c.close()

    def _fee(self,notional):
        return abs(float(notional))*self.fee_bps/10000.0

    def get_start_balance(self):
        return float(self.start_balance)

    def get_experiment_id(self):
        return self.current_experiment_id

    def set_start_balance(self,amount,reset_results=True):
        """
        Starts a NEW paper experiment when reset_results=True.
        Previous trades remain stored and queryable under the archived experiment.
        """
        amount=float(amount)
        if amount<1:
            raise ValueError("Capital must be at least 1")
        if amount>100000000:
            raise ValueError("Capital is too large")

        c=self.con()
        now=time.time()

        if reset_results:
            # Manual experiment reset: do not pretend an unfinished trade was
            # a market win/loss. Preserve it as RESET in the old experiment.
            c.execute("""
              UPDATE trades
              SET status='RESET', close_ts=?, exit_price=entry,
                  gross_pnl=0, net_pnl=0, realized_r=0,
                  capture_efficiency_pct=0
              WHERE experiment_id=? AND status='OPEN'
            """,(now,self.current_experiment_id))

            c.execute("""
              UPDATE paper_experiments
              SET status='ARCHIVED',end_ts=?
              WHERE experiment_id=? AND status='ACTIVE'
            """,(now,self.current_experiment_id))

            new_id=self._create_experiment(
                c,amount,f"Started with ${amount:.2f}"
            )
            self.current_experiment_id=new_id
            self.start_balance=amount
        else:
            c.execute("""
              UPDATE paper_experiments
              SET start_balance=?
              WHERE experiment_id=?
            """,(amount,self.current_experiment_id))
            self._set_setting(c,"start_balance",amount)
            self.start_balance=amount

        c.commit()
        c.close()
        return {
            "start_balance":self.start_balance,
            "experiment_id":self.current_experiment_id,
            "new_experiment":bool(reset_results),
        }

    def _valid_closed_clause(self):
        return "status IN ('WIN','LOSS','BE','EXPIRED')"

    def _current_args(self):
        return (self.current_experiment_id,)

    def balance(self):
        c=self.con()
        row=c.execute(f"""
          SELECT COALESCE(SUM(net_pnl),0) pnl
          FROM trades
          WHERE experiment_id=? AND {self._valid_closed_clause()}
        """,self._current_args()).fetchone()
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

    def _summary_rows(self,rows,start_balance=None):
        start_balance=float(self.start_balance if start_balance is None else start_balance)
        net=[float(r["net_pnl"] or 0) for r in rows]
        gross=[float(r["gross_pnl"] or 0) for r in rows]
        wins=sum(1 for x in net if x>0)
        losses=sum(1 for x in net if x<0)
        bes=sum(1 for x in net if x==0)
        gp=sum(x for x in gross if x>0)
        gl=abs(sum(x for x in gross if x<0))
        fees=sum(float(r["fees"] or 0) for r in rows)
        total_r=sum(float(r["realized_r"] or 0) for r in rows)
        net_total=sum(net)
        return {
            "trades":len(rows),"wins":wins,"losses":losses,"be":bes,
            "win_rate":wins/max(1,wins+losses)*100,
            "gross_profit":gp,"gross_loss":gl,"fees":fees,
            "net_pnl":net_total,"total_r":total_r,
            "return_pct":net_total/max(start_balance,1e-9)*100,
            "profit_factor":gp/gl if gl>0 else (999 if gp>0 else 0)
        }

    def _summary(self,start_ts=None):
        c=self.con()
        q=f"""
          SELECT * FROM trades
          WHERE experiment_id=? AND {self._valid_closed_clause()}
        """
        args=[self.current_experiment_id]
        if start_ts is not None:
            q+=" AND close_ts>=?"
            args.append(start_ts)
        rows=c.execute(q,args).fetchall()
        c.close()
        return self._summary_rows(rows)

    def pnl_dashboard(self):
        return {
            "day":self._summary(self._period_start("day")),
            "week":self._summary(self._period_start("week")),
            "month":self._summary(self._period_start("month")),
            "total":self._summary(None),
            "experiment_id":self.current_experiment_id,
            "starting_capital":self.get_start_balance(),
            "balance":self.balance(),
            "timezone":f"UTC{self.tz_offset:+d}"
        }

    def risk_guard(self):
        day=self._summary(self._period_start("day"))
        c=self.con()
        open_count=int(c.execute("""
          SELECT COUNT(*) n FROM trades
          WHERE experiment_id=? AND status='OPEN'
        """,self._current_args()).fetchone()["n"] or 0)

        recent=c.execute(f"""
          SELECT net_pnl FROM trades
          WHERE experiment_id=? AND {self._valid_closed_clause()}
          ORDER BY close_ts DESC LIMIT ?
        """,(self.current_experiment_id,self.max_consecutive_losses)).fetchall()
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
        if open_count>=1:
            reasons.append("ONE_MAIN_TRADE_ALREADY_OPEN")

        return {
            "allow_new_trades":not reasons,
            "reasons":reasons,
            "daily_loss_limit_usd":daily_limit_usd,
            "daily_net_pnl":day["net_pnl"],
            "consecutive_losses":consecutive_losses,
            "max_consecutive_losses":self.max_consecutive_losses,
            "open_trades":open_count,
            "max_open_trades":1,
        }

    def maybe_open(self,lanes,market_regime=None,now=None):
        """
        Only ONE primary paper trade may be open globally.
        If several lanes are actionable, choose highest Setup Score,
        then Available R:R as tie-breaker.
        """
        now=now or time.time()
        if not self.risk_guard()["allow_new_trades"]:
            return

        c=self.con()
        if c.execute("""
          SELECT 1 FROM trades
          WHERE experiment_id=? AND status='OPEN'
          LIMIT 1
        """,self._current_args()).fetchone():
            c.close()
            return

        candidates=[]
        for lane_name,s in lanes.items():
            if s.get("action") not in ("LONG","SHORT"):
                continue
            plan=s.get("plan") or {}
            if any(plan.get(k) is None for k in ("entry","sl","tp1","tp2")):
                continue

            opp_id=(s.get("opportunity") or {}).get("opportunity_id")
            if opp_id and c.execute("""
              SELECT 1 FROM trades
              WHERE experiment_id=? AND opportunity_id=?
              LIMIT 1
            """,(self.current_experiment_id,opp_id)).fetchone():
                # One independent opportunity may create at most one trade
                # in this account/experiment.
                continue

            last=c.execute("""
              SELECT open_ts FROM trades
              WHERE experiment_id=? AND lane=?
              ORDER BY id DESC LIMIT 1
            """,(self.current_experiment_id,lane_name)).fetchone()
            cooldown=float(self.cooldowns.get(lane_name,600))
            if last and now-float(last["open_ts"])<cooldown:
                continue
            candidates.append((lane_name,s))

        if not candidates:
            c.close()
            return

        lane,s=max(
            candidates,
            key=lambda item:(
                float(item[1].get("setup_score") or 0),
                float((item[1].get("diagnostics") or {}).get("available_rr") or 0)
            )
        )

        bal=max(.01,self.balance())
        plan=s.get("plan") or {}
        side=s["action"]
        entry=float(plan["entry"])
        slip=self.slippage_bps/10000.0
        entry=entry*(1+slip if side=="LONG" else 1-slip)
        sl=float(plan["sl"]); tp1=float(plan["tp1"]); tp2=float(plan["tp2"])
        stop_dist=abs(entry-sl)
        if stop_dist<=0:
            c.close()
            return

        target_risk=bal*self.risk_pct/100.0
        qty_by_risk=target_risk/stop_dist
        max_notional=bal*self.max_notional_multiple
        qty_cap=max_notional/max(entry,1e-9)
        qty=max(0,min(qty_by_risk,qty_cap))
        if qty<=0:
            c.close()
            return

        risk_usd=qty*stop_dist
        notional=qty*entry
        entry_fee=self._fee(notional)
        diag=s.get("diagnostics") or {}
        opp=s.get("opportunity") or {}
        pa=s.get("price_action") or {}
        pa_evidence={
            "aligned":pa.get("aligned_evidence",[]),
            "opposed":pa.get("opposed_evidence",[]),
            "aligned_families":pa.get("aligned_families",[]),
            "opposed_families":pa.get("opposed_families",[]),
        }

        c.execute("""
          INSERT INTO trades(
            engine_version,lane,side,open_ts,entry,sl,tp1,tp2,
            quantity,risk_usd,notional_usd,setup_grade,setup_score,
            fees,reason,opportunity_id,market_regime,
            entry_timing,chasing_risk,available_rr,structural_obstacle,
            mfe_price,mae_price,mfe_r,mae_r,experiment_id,
            price_action_state,price_action_score,price_action_evidence
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,(
            "V2.6",lane,side,now,entry,sl,tp1,tp2,
            qty,risk_usd,notional,s.get("setup_grade"),float(s.get("setup_score") or 0),
            entry_fee,"BEST_MAIN_LANE_ONLY",
            opp.get("opportunity_id"),market_regime,
            diag.get("entry_timing"),diag.get("chasing_risk"),
            float(diag.get("available_rr") or 0),
            diag.get("structural_obstacle"),
            entry,entry,0.0,0.0,self.current_experiment_id,
            pa.get("state","NEUTRAL"),float(pa.get("score") or 0),
            json.dumps(pa_evidence,ensure_ascii=False)
        ))
        c.commit()
        c.close()

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
        if status not in ("EXPIRED","CANCELLED","RESET"):
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
        rows=c.execute("""
          SELECT * FROM trades
          WHERE experiment_id=? AND status='OPEN'
        """,self._current_args()).fetchall()

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

        c.commit()
        c.close()

    def open_positions(self,live_price):
        c=self.con()
        rows=c.execute("""
          SELECT * FROM trades
          WHERE experiment_id=? AND status='OPEN'
          ORDER BY open_ts ASC
        """,self._current_args()).fetchall()
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
                "experiment_id":r["experiment_id"],
                "opportunity_id":r["opportunity_id"],
                "market_regime":r["market_regime"],
                "setup_grade":r["setup_grade"],"setup_score":r["setup_score"],
                "entry_timing":r["entry_timing"],"chasing_risk":r["chasing_risk"],
                "available_rr":r["available_rr"],
                "price_action_state":r["price_action_state"],
                "price_action_score":float(r["price_action_score"] or 0),
                "price_action_evidence":r["price_action_evidence"],
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

    def _current_rows(self,include_open=True):
        c=self.con()
        q="SELECT * FROM trades WHERE experiment_id=?"
        args=[self.current_experiment_id]
        if not include_open:
            q+=f" AND {self._valid_closed_clause()}"
        rows=c.execute(q,args).fetchall()
        c.close()
        return rows

    def lane_stats(self):
        c=self.con()
        out={}
        for lane in ("SCALP","INTRADAY","SWING"):
            rows=c.execute("""
              SELECT * FROM trades
              WHERE experiment_id=? AND lane=?
              ORDER BY id DESC
            """,(self.current_experiment_id,lane)).fetchall()
            closed=[r for r in rows if r["status"] in self.VALID_CLOSED_STATUSES]
            wins=[r for r in closed if float(r["net_pnl"] or 0)>0]
            losses=[r for r in closed if float(r["net_pnl"] or 0)<0]
            gp=sum(max(0,float(r["gross_pnl"] or 0)) for r in closed)
            gl=abs(sum(min(0,float(r["gross_pnl"] or 0)) for r in closed))
            out[lane]={
                "trades":len([r for r in rows if r["status"]!="RESET"]),
                "open":sum(1 for r in rows if r["status"]=="OPEN"),
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
        rows=c.execute(f"""
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
          WHERE experiment_id=? AND {self._valid_closed_clause()}
          GROUP BY lane,COALESCE(market_regime,'UNKNOWN')
          ORDER BY lane,regime
        """,self._current_args()).fetchall()
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
              WHERE experiment_id=? AND {self._valid_closed_clause()}
              GROUP BY COALESCE({field},'UNKNOWN')
              ORDER BY trades DESC
            """,self._current_args()).fetchall()
            result[field]=[{
                "label":r["label"],"trades":int(r["trades"] or 0),
                "wins":int(r["wins"] or 0),"losses":int(r["losses"] or 0),
                "win_rate":int(r["wins"] or 0)/max(1,int(r["wins"] or 0)+int(r["losses"] or 0))*100,
                "avg_r":float(r["avg_r"] or 0),
                "capture_efficiency":float(r["efficiency"] or 0),
            } for r in rows]
        c.close()
        return result

    def price_action_stats(self):
        c=self.con()
        rows=c.execute(f"""
          SELECT COALESCE(price_action_state,'UNKNOWN') label,
                 COUNT(*) trades,
                 SUM(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END) wins,
                 SUM(CASE WHEN net_pnl<0 THEN 1 ELSE 0 END) losses,
                 AVG(realized_r) avg_r,
                 AVG(mfe_r) avg_mfe_r,
                 AVG(mae_r) avg_mae_r,
                 AVG(capture_efficiency_pct) efficiency,
                 SUM(net_pnl) net_pnl
          FROM trades
          WHERE experiment_id=? AND {self._valid_closed_clause()}
          GROUP BY COALESCE(price_action_state,'UNKNOWN')
          ORDER BY trades DESC
        """,self._current_args()).fetchall()
        c.close()

        out=[]
        for r in rows:
            wins=int(r["wins"] or 0)
            losses=int(r["losses"] or 0)
            out.append({
                "label":r["label"],
                "trades":int(r["trades"] or 0),
                "wins":wins,
                "losses":losses,
                "win_rate":wins/max(1,wins+losses)*100,
                "avg_r":float(r["avg_r"] or 0),
                "avg_mfe_r":float(r["avg_mfe_r"] or 0),
                "avg_mae_r":float(r["avg_mae_r"] or 0),
                "capture_efficiency":float(r["efficiency"] or 0),
                "net_pnl":float(r["net_pnl"] or 0),
            })
        return out

    def _streaks(self,rows):
        max_w=max_l=cur_w=cur_l=0
        for r in rows:
            pnl=float(r["net_pnl"] or 0)
            if pnl>0:
                cur_w+=1; cur_l=0
                max_w=max(max_w,cur_w)
            elif pnl<0:
                cur_l+=1; cur_w=0
                max_l=max(max_l,cur_l)
            else:
                cur_w=cur_l=0

        current_type="NONE"; current_count=0
        for r in reversed(rows):
            pnl=float(r["net_pnl"] or 0)
            typ="WIN" if pnl>0 else "LOSS" if pnl<0 else "BE"
            if current_type=="NONE":
                current_type=typ; current_count=1
            elif typ==current_type:
                current_count+=1
            else:
                break
        return {
            "max_win_streak":max_w,
            "max_loss_streak":max_l,
            "current_streak_type":current_type,
            "current_streak_count":current_count,
        }

    def analytics(self):
        c=self.con()
        rows=c.execute(f"""
          SELECT * FROM trades
          WHERE experiment_id=? AND {self._valid_closed_clause()}
          ORDER BY close_ts ASC,id ASC
        """,self._current_args()).fetchall()
        exp=c.execute("""
          SELECT * FROM paper_experiments WHERE experiment_id=?
        """,self._current_args()).fetchone()
        c.close()

        start=float(exp["start_balance"] if exp else self.start_balance)
        equity=start
        peak=start
        max_dd_abs=0.0
        max_dd_pct=0.0
        curve=[{
            "ts":float(exp["start_ts"] if exp else time.time()),
            "equity":start,
            "drawdown_pct":0.0,
            "trade_id":None
        }]

        wins=[]; losses=[]
        for r in rows:
            pnl=float(r["net_pnl"] or 0)
            equity+=pnl
            peak=max(peak,equity)
            dd_abs=max(0.0,peak-equity)
            dd_pct=dd_abs/max(peak,1e-9)*100
            max_dd_abs=max(max_dd_abs,dd_abs)
            max_dd_pct=max(max_dd_pct,dd_pct)
            curve.append({
                "ts":float(r["close_ts"] or r["open_ts"]),
                "equity":equity,
                "drawdown_pct":dd_pct,
                "trade_id":r["id"],
            })
            if pnl>0: wins.append(pnl)
            elif pnl<0: losses.append(pnl)

        n=len(rows)
        total_net=sum(float(r["net_pnl"] or 0) for r in rows)
        total_r=sum(float(r["realized_r"] or 0) for r in rows)
        expectancy_usd=total_net/max(1,n)
        expectancy_r=total_r/max(1,n)
        avg_win=sum(wins)/max(1,len(wins))
        avg_loss=sum(losses)/max(1,len(losses))
        best=max((float(r["net_pnl"] or 0) for r in rows),default=0.0)
        worst=min((float(r["net_pnl"] or 0) for r in rows),default=0.0)

        gp=sum(max(0,float(r["net_pnl"] or 0)) for r in rows)
        gl=abs(sum(min(0,float(r["net_pnl"] or 0)) for r in rows))
        pf=gp/gl if gl>0 else (999 if gp>0 else 0)
        payoff=avg_win/abs(avg_loss) if avg_loss<0 else (999 if avg_win>0 else 0)
        recovery=total_net/max_dd_abs if max_dd_abs>0 else (999 if total_net>0 else 0)

        streaks=self._streaks(rows)

        return {
            "experiment_id":self.current_experiment_id,
            "start_ts":float(exp["start_ts"] if exp else 0),
            "starting_capital":start,
            "current_equity":equity,
            "trades":n,
            "net_pnl":total_net,
            "return_pct":total_net/max(start,1e-9)*100,
            "max_drawdown_usd":max_dd_abs,
            "max_drawdown_pct":max_dd_pct,
            "expectancy_usd":expectancy_usd,
            "expectancy_r":expectancy_r,
            "avg_win_usd":avg_win,
            "avg_loss_usd":avg_loss,
            "payoff_ratio":payoff,
            "profit_factor":pf,
            "recovery_factor":recovery,
            "best_trade_usd":best,
            "worst_trade_usd":worst,
            **streaks,
            "equity_curve":curve,
        }

    def _bucket_performance(self,kind):
        tz=timezone(timedelta(hours=self.tz_offset))
        rows=self._current_rows(include_open=False)
        buckets={}
        day_names=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

        for r in rows:
            dt=datetime.fromtimestamp(float(r["open_ts"]),tz)
            if kind=="hour":
                key=f"{dt.hour:02d}:00"
                order=dt.hour
            else:
                key=day_names[dt.weekday()]
                order=dt.weekday()

            b=buckets.setdefault(key,{
                "label":key,"order":order,"trades":0,"wins":0,"losses":0,
                "net_pnl":0.0,"total_r":0.0
            })
            b["trades"]+=1
            pnl=float(r["net_pnl"] or 0)
            if pnl>0: b["wins"]+=1
            elif pnl<0: b["losses"]+=1
            b["net_pnl"]+=pnl
            b["total_r"]+=float(r["realized_r"] or 0)

        out=[]
        for b in buckets.values():
            b["win_rate"]=b["wins"]/max(1,b["wins"]+b["losses"])*100
            b["avg_r"]=b["total_r"]/max(1,b["trades"])
            out.append(b)
        return sorted(out,key=lambda x:x["order"])

    def time_performance(self):
        return {
            "hour":self._bucket_performance("hour"),
            "weekday":self._bucket_performance("weekday"),
            "timezone":f"UTC{self.tz_offset:+d}",
        }

    def experiment_history(self,limit=30):
        c=self.con()
        exps=c.execute("""
          SELECT * FROM paper_experiments
          ORDER BY start_ts DESC LIMIT ?
        """,(int(limit),)).fetchall()

        out=[]
        for e in exps:
            rows=c.execute(f"""
              SELECT * FROM trades
              WHERE experiment_id=? AND {self._valid_closed_clause()}
              ORDER BY close_ts ASC
            """,(e["experiment_id"],)).fetchall()
            summary=self._summary_rows(rows,float(e["start_balance"]))

            # Drawdown for each experiment.
            equity=float(e["start_balance"])
            peak=equity
            max_dd=0.0
            max_dd_pct=0.0
            total_r=0.0
            for r in rows:
                equity+=float(r["net_pnl"] or 0)
                peak=max(peak,equity)
                dd=max(0.0,peak-equity)
                max_dd=max(max_dd,dd)
                max_dd_pct=max(max_dd_pct,dd/max(peak,1e-9)*100)
                total_r+=float(r["realized_r"] or 0)

            out.append({
                "experiment_id":e["experiment_id"],
                "status":e["status"],
                "start_ts":float(e["start_ts"]),
                "end_ts":float(e["end_ts"]) if e["end_ts"] is not None else None,
                "start_balance":float(e["start_balance"]),
                "ending_balance":float(e["start_balance"])+summary["net_pnl"],
                "trades":summary["trades"],
                "wins":summary["wins"],
                "losses":summary["losses"],
                "win_rate":summary["win_rate"],
                "net_pnl":summary["net_pnl"],
                "return_pct":summary["return_pct"],
                "profit_factor":summary["profit_factor"],
                "total_r":total_r,
                "max_drawdown_usd":max_dd,
                "max_drawdown_pct":max_dd_pct,
                "note":e["note"],
            })
        c.close()
        return out

    def recent(self,limit=30):
        c=self.con()
        rows=[dict(r) for r in c.execute("""
          SELECT * FROM trades
          WHERE experiment_id=?
          ORDER BY id DESC LIMIT ?
        """,(self.current_experiment_id,int(limit))).fetchall()]
        c.close()
        return rows

    def export_rows(self,limit=10000):
        c=self.con()
        rows=[dict(r) for r in c.execute("""
          SELECT * FROM trades
          WHERE experiment_id=?
          ORDER BY id ASC LIMIT ?
        """,(self.current_experiment_id,int(limit))).fetchall()]
        c.close()
        return rows

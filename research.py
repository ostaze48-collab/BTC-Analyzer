from __future__ import annotations
import sqlite3, time, uuid
from .core import safe, json_dumps

class ResearchJournal:
    def __init__(self,db_path,snapshot_interval=300):
        self.db_path=str(db_path)
        self.interval=int(snapshot_interval)
        self._init()

    def con(self):
        c=sqlite3.connect(self.db_path,timeout=10)
        c.row_factory=sqlite3.Row
        return c

    def _init(self):
        c=self.con()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots(
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
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
        """)
        c.commit(); c.close()

    def snapshot(self,price,analysis,decision,context):
        if price is None:
            return
        now=time.time()
        bucket=int(now//self.interval)*self.interval
        best=decision.get("best_setup",{})
        c=self.con()
        c.execute("""
          INSERT OR IGNORE INTO snapshots(
            bucket_ts,ts,price,bias,bias_score,best_lane,best_action,
            best_grade,best_score,context_regime,context_score,
            analysis_json,lanes_json
          ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,(
            bucket,now,float(price),analysis.get("bias"),safe(analysis.get("bias_score")),
            best.get("lane"),best.get("action"),best.get("setup_grade"),
            safe(best.get("setup_score")),context.get("regime"),safe(context.get("score")),
            json_dumps(analysis),json_dumps(decision.get("lanes",{}))
        ))
        c.commit(); c.close()

    def update_outcomes(self,price):
        if price is None:
            return
        now=time.time(); p=float(price)
        c=self.con()
        for col,sec in (("r1h_pct",3600),("r4h_pct",14400)):
            rows=c.execute(
                f"SELECT id,price FROM snapshots WHERE {col} IS NULL AND ts<=? LIMIT 500",
                (now-sec,)
            ).fetchall()
            for r in rows:
                ret=(p/float(r["price"])-1)*100
                c.execute(f"UPDATE snapshots SET {col}=? WHERE id=?",(ret,r["id"]))
        c.commit(); c.close()

    def stats(self):
        c=self.con()
        total=c.execute("SELECT COUNT(*) n FROM snapshots").fetchone()["n"]
        rows=[]
        for grade in ("A+","A","B","C"):
            r=c.execute("""
              SELECT COUNT(*) n,
                AVG(CASE WHEN bias='BULLISH' THEN r1h_pct WHEN bias='BEARISH' THEN -r1h_pct END) a1,
                AVG(CASE WHEN bias='BULLISH' THEN r4h_pct WHEN bias='BEARISH' THEN -r4h_pct END) a4
              FROM snapshots WHERE best_grade=?
            """,(grade,)).fetchone()
            rows.append({
                "grade":grade,"n":int(r["n"] or 0),
                "aligned_1h_avg_pct":safe(r["a1"],None),
                "aligned_4h_avg_pct":safe(r["a4"],None)
            })
        recent=[dict(r) for r in c.execute("""
          SELECT ts,price,bias,best_lane,best_action,best_grade,best_score,
                 context_regime,r1h_pct,r4h_pct
          FROM snapshots ORDER BY id DESC LIMIT 25
        """).fetchall()]
        c.close()
        return {"snapshots":int(total),"by_grade":rows,"recent":recent}


class ShadowLab:
    STRATEGIES=("A_BASE_5M","B_5M_3M","C_FULL_SYNC","D_5M_1M")

    def __init__(self,db_path):
        self.db_path=str(db_path)
        self.active=None
        self._init()

    def con(self):
        c=sqlite3.connect(self.db_path,timeout=10)
        c.row_factory=sqlite3.Row
        return c

    def _init(self):
        c=self.con()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS setups(
          setup_id TEXT PRIMARY KEY,
          start_ts REAL,
          end_ts REAL,
          side TEXT,
          base_result_r REAL,
          finalized INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS variant_trades(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          setup_id TEXT,
          strategy TEXT,
          ts REAL,
          side TEXT,
          entry REAL,
          sl REAL,
          tp REAL,
          entry_delay_sec REAL,
          confirmation_cost_pct REAL,
          status TEXT DEFAULT 'OPEN',
          exit_ts REAL,
          exit_price REAL,
          result_r REAL DEFAULT 0,
          last_bar_ts REAL DEFAULT 0,
          UNIQUE(setup_id,strategy)
        );
        CREATE TABLE IF NOT EXISTS classifications(
          setup_id TEXT,
          strategy TEXT,
          classification TEXT,
          PRIMARY KEY(setup_id,strategy)
        );
        """)
        c.commit(); c.close()

    def _new_setup(self,side):
        sid=f"{int(time.time())}-{side}-{uuid.uuid4().hex[:6]}"
        c=self.con()
        c.execute("INSERT INTO setups(setup_id,start_ts,side) VALUES(?,?,?)",(sid,time.time(),side))
        c.commit(); c.close()
        self.active={"id":sid,"side":side,"start":time.time(),"triggered":set(),"base_entry":None}

    def _finalize_active(self):
        if not self.active:
            return
        c=self.con()
        c.execute("UPDATE setups SET end_ts=?,finalized=1 WHERE setup_id=?",(time.time(),self.active["id"]))
        c.commit(); c.close()
        self.active=None
        self._classify_ready()

    def observe(self,shadow):
        common=bool(shadow.get("common_ready"))
        side=shadow.get("side")
        if not common or side not in ("LONG","SHORT"):
            self._finalize_active()
            return

        if self.active is None or self.active["side"]!=side:
            self._finalize_active()
            self._new_setup(side)

        plan=shadow.get("plan",{})
        if any(plan.get(k) is None for k in ("entry","sl","tp2")):
            return
        variants=shadow.get("variants",{})
        c=self.con()
        now=time.time()

        for st in self.STRATEGIES:
            if not variants.get(st) or st in self.active["triggered"]:
                continue
            entry=float(plan["entry"]); sl=float(plan["sl"]); tp=float(plan["tp2"])
            delay=now-self.active["start"]
            cost=None
            if st=="A_BASE_5M":
                self.active["base_entry"]=entry
                cost=0.0
            elif self.active.get("base_entry"):
                base=self.active["base_entry"]
                signed=(entry/base-1)*100
                cost=signed if side=="LONG" else -signed

            c.execute("""
              INSERT OR IGNORE INTO variant_trades(
                setup_id,strategy,ts,side,entry,sl,tp,entry_delay_sec,confirmation_cost_pct
              ) VALUES(?,?,?,?,?,?,?,?,?)
            """,(self.active["id"],st,now,side,entry,sl,tp,delay,cost))
            self.active["triggered"].add(st)
        c.commit(); c.close()

    def process_bar(self,bar):
        if not bar:
            return
        bar_ts=float(bar["ts"]); hi=float(bar["high"]); lo=float(bar["low"])
        now=time.time()
        c=self.con()
        rows=c.execute("SELECT * FROM variant_trades WHERE status='OPEN'").fetchall()
        for r in rows:
            if float(r["last_bar_ts"] or 0)>=bar_ts:
                continue
            if r["side"]=="LONG":
                sl_hit=lo<=float(r["sl"]); tp_hit=hi>=float(r["tp"])
            else:
                sl_hit=hi>=float(r["sl"]); tp_hit=lo<=float(r["tp"])

            status=None; rr=0; ex=None
            if sl_hit:
                status="LOSS"; rr=-1.0; ex=float(r["sl"])
            elif tp_hit:
                stop=abs(float(r["entry"])-float(r["sl"]))
                reward=abs(float(r["tp"])-float(r["entry"]))
                status="WIN"; rr=reward/max(stop,1e-9); ex=float(r["tp"])
            elif now-float(r["ts"])>=7200:
                status="EXPIRED"; rr=0; ex=float(bar["close"])

            if status:
                c.execute("""
                  UPDATE variant_trades
                  SET status=?,exit_ts=?,exit_price=?,result_r=?,last_bar_ts=?
                  WHERE id=?
                """,(status,now,ex,rr,bar_ts,r["id"]))
                if r["strategy"]=="A_BASE_5M":
                    c.execute("UPDATE setups SET base_result_r=? WHERE setup_id=?",(rr,r["setup_id"]))
            else:
                c.execute("UPDATE variant_trades SET last_bar_ts=? WHERE id=?",(bar_ts,r["id"]))
        c.commit(); c.close()
        self._classify_ready()

    def _classify_ready(self):
        c=self.con()
        setups=c.execute("""
          SELECT * FROM setups
          WHERE finalized=1 AND base_result_r IS NOT NULL
        """).fetchall()

        for s in setups:
            triggered={r["strategy"] for r in c.execute(
                "SELECT strategy FROM variant_trades WHERE setup_id=?",(s["setup_id"],)
            ).fetchall()}
            base=float(s["base_result_r"])
            for st in self.STRATEGIES:
                if st in triggered:
                    continue
                if c.execute("SELECT 1 FROM classifications WHERE setup_id=? AND strategy=?",(s["setup_id"],st)).fetchone():
                    continue
                cls="MISSED_WINNER" if base>0 else "AVOIDED_LOSER" if base<0 else "NEUTRAL"
                c.execute("INSERT INTO classifications(setup_id,strategy,classification) VALUES(?,?,?)",
                          (s["setup_id"],st,cls))
        c.commit(); c.close()

    def stats(self):
        c=self.con()
        out=[]
        for st in self.STRATEGIES:
            rows=c.execute("SELECT * FROM variant_trades WHERE strategy=?",(st,)).fetchall()
            closed=[r for r in rows if r["status"]!="OPEN"]
            wins=[r for r in closed if r["status"]=="WIN"]
            losses=[r for r in closed if r["status"]=="LOSS"]
            gw=sum(max(0,float(r["result_r"])) for r in closed)
            gl=abs(sum(min(0,float(r["result_r"])) for r in closed))
            delays=[safe(r["entry_delay_sec"]) for r in rows]
            costs=[safe(r["confirmation_cost_pct"],None) for r in rows if r["confirmation_cost_pct"] is not None]
            classes=[r["classification"] for r in c.execute(
                "SELECT classification FROM classifications WHERE strategy=?",(st,)
            ).fetchall()]
            out.append({
                "strategy":st,
                "trades":len(rows),"wins":len(wins),"losses":len(losses),
                "win_rate":len(wins)/max(1,len(wins)+len(losses))*100,
                "profit_factor":gw/gl if gl>0 else (999 if gw>0 else 0),
                "avg_r":sum(float(r["result_r"]) for r in closed)/max(1,len(closed)),
                "avg_delay_sec":sum(delays)/max(1,len(delays)),
                "avg_confirmation_cost_pct":sum(costs)/max(1,len(costs)) if costs else None,
                "missed_winners":classes.count("MISSED_WINNER"),
                "avoided_losers":classes.count("AVOIDED_LOSER"),
                "neutral_misses":classes.count("NEUTRAL"),
            })
        recent=[dict(r) for r in c.execute(
            "SELECT * FROM variant_trades ORDER BY id DESC LIMIT 20"
        ).fetchall()]
        c.close()
        return {"strategies":out,"recent":recent,"active_setup":self.active["id"] if self.active else None}

from __future__ import annotations
import sqlite3, time, uuid

class OpportunityTracker:
    """
    Gives each evolving setup one stable ID so repeated 30-second engine
    cycles are not mistaken for independent opportunities.
    """
    LANES=("FAST_SCALP","SCALP","INTRADAY","SWING")

    def __init__(self,db_path):
        self.db_path=str(db_path)
        self.active={}
        self._init()
        self._restore()

    def con(self):
        c=sqlite3.connect(self.db_path,timeout=10)
        c.row_factory=sqlite3.Row
        return c

    def _init(self):
        c=self.con()
        c.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities(
          opportunity_id TEXT PRIMARY KEY,
          lane TEXT NOT NULL,
          side TEXT NOT NULL,
          start_ts REAL NOT NULL,
          last_ts REAL NOT NULL,
          end_ts REAL,
          status TEXT NOT NULL,
          start_score REAL,
          max_score REAL,
          last_score REAL,
          close_reason TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_opportunities_active
        ON opportunities(lane,end_ts);

        CREATE TABLE IF NOT EXISTS opportunity_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          opportunity_id TEXT NOT NULL,
          ts REAL NOT NULL,
          state TEXT NOT NULL,
          score REAL,
          action TEXT,
          note TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_opportunity_events
        ON opportunity_events(opportunity_id,ts);
        """)
        c.commit(); c.close()

    def _restore(self):
        c=self.con()
        rows=c.execute("""
          SELECT * FROM opportunities
          WHERE end_ts IS NULL
          ORDER BY start_ts ASC
        """).fetchall()
        c.close()
        for r in rows:
            self.active[r["lane"]]={
                "id":r["opportunity_id"],"lane":r["lane"],"side":r["side"],
                "start_ts":float(r["start_ts"]),"state":r["status"],
                "start_score":float(r["start_score"] or 0),
                "max_score":float(r["max_score"] or 0),
                "last_score":float(r["last_score"] or 0),
            }

    def _new_id(self,lane):
        stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
        return f"{lane}-{stamp}-{uuid.uuid4().hex[:5].upper()}"

    @staticmethod
    def _state(lane):
        score=float(lane.get("setup_score") or 0)
        action=lane.get("action")
        if action in ("LONG","SHORT"):
            return "TRIGGERED"
        if score>=72:
            return "READY"
        return "FORMING"

    def _event(self,c,oid,state,score,action,note=None):
        c.execute("""
          INSERT INTO opportunity_events(
            opportunity_id,ts,state,score,action,note
          ) VALUES(?,?,?,?,?,?)
        """,(oid,time.time(),state,float(score or 0),action,note))

    def _close(self,c,lane_name,reason):
        cur=self.active.get(lane_name)
        if not cur:
            return
        now=time.time()
        c.execute("""
          UPDATE opportunities
          SET end_ts=?,last_ts=?,status='CLOSED',close_reason=?
          WHERE opportunity_id=?
        """,(now,now,reason,cur["id"]))
        self._event(c,cur["id"],"CLOSED",cur.get("last_score"),"WAIT",reason)
        self.active.pop(lane_name,None)

    def observe(self,lanes,fast_bar_ts=None):
        """
        Hysteresis:
        - create when score >= 50 and side is directional
        - keep alive while score >= 45
        - close on side flip or score collapse
        """
        now=time.time()
        c=self.con()
        out={}

        for lane_name in self.LANES:
            lane=lanes.get(lane_name) or {}
            side=lane.get("side_bias")
            score=float(lane.get("setup_score") or 0)
            directional=side in ("LONG","SHORT")
            cur=self.active.get(lane_name)

            # FAST_SCALP is tied to a CLOSED 1m bar. Same bar => same ID;
            # next closed bar => fresh opportunity. This allows consecutive
            # fast trades without duplicate entries inside the same minute.
            if lane_name=="FAST_SCALP":
                action=lane.get("action")
                if action not in ("LONG","SHORT") or fast_bar_ts is None:
                    if cur:
                        self._close(c,lane_name,"TRIGGER_OFF")
                    continue

                bar_key=int(float(fast_bar_ts))
                oid=f"FAST_SCALP-{bar_key}-{action}"
                if cur and cur["id"]!=oid:
                    self._close(c,lane_name,"NEXT_1M_BAR")
                    cur=None

                if not cur:
                    row=c.execute(
                        "SELECT * FROM opportunities WHERE opportunity_id=?",(oid,)
                    ).fetchone()
                    if row:
                        cur={
                            "id":row["opportunity_id"],"lane":lane_name,
                            "side":row["side"],"start_ts":float(row["start_ts"]),
                            "state":row["status"],
                            "start_score":float(row["start_score"] or 0),
                            "max_score":float(row["max_score"] or 0),
                            "last_score":float(row["last_score"] or 0),
                        }
                        self.active[lane_name]=cur
                    else:
                        cur={
                            "id":oid,"lane":lane_name,"side":action,
                            "start_ts":now,"state":"TRIGGERED",
                            "start_score":score,"max_score":score,"last_score":score
                        }
                        self.active[lane_name]=cur
                        c.execute("""
                          INSERT INTO opportunities(
                            opportunity_id,lane,side,start_ts,last_ts,status,
                            start_score,max_score,last_score
                          ) VALUES(?,?,?,?,?,?,?,?,?)
                        """,(oid,lane_name,action,now,now,"TRIGGERED",score,score,score))
                        self._event(c,oid,"TRIGGERED",score,action,"FAST_1M_TRIGGER")
                else:
                    cur["max_score"]=max(cur["max_score"],score)
                    cur["last_score"]=score
                    c.execute("""
                      UPDATE opportunities SET last_ts=?,max_score=?,last_score=?
                      WHERE opportunity_id=?
                    """,(now,cur["max_score"],score,cur["id"]))

                out[lane_name]={
                    "opportunity_id":cur["id"],"state":"TRIGGERED",
                    "side":action,"age_sec":max(0,now-cur["start_ts"]),
                    "start_score":cur["start_score"],
                    "max_score":cur["max_score"],
                }
                continue

            if cur and (not directional or side!=cur["side"] or score<45):
                self._close(c,lane_name,"SIDE_FLIP" if directional and side!=cur["side"] else "SETUP_FADED")
                cur=None

            if not cur and directional and score>=50:
                oid=self._new_id(lane_name)
                state=self._state(lane)
                cur={
                    "id":oid,"lane":lane_name,"side":side,"start_ts":now,
                    "state":state,"start_score":score,"max_score":score,"last_score":score
                }
                self.active[lane_name]=cur
                c.execute("""
                  INSERT INTO opportunities(
                    opportunity_id,lane,side,start_ts,last_ts,status,
                    start_score,max_score,last_score
                  ) VALUES(?,?,?,?,?,?,?,?,?)
                """,(oid,lane_name,side,now,now,state,score,score,score))
                self._event(c,oid,state,score,lane.get("action"),"CREATED")

            elif cur:
                new_state=self._state(lane)
                state_changed=new_state!=cur["state"]
                cur["max_score"]=max(cur["max_score"],score)
                cur["last_score"]=score
                cur["state"]=new_state
                c.execute("""
                  UPDATE opportunities
                  SET last_ts=?,status=?,max_score=?,last_score=?
                  WHERE opportunity_id=?
                """,(now,new_state,cur["max_score"],score,cur["id"]))
                if state_changed:
                    self._event(c,cur["id"],new_state,score,lane.get("action"),"STATE_CHANGE")

            cur=self.active.get(lane_name)
            if cur:
                out[lane_name]={
                    "opportunity_id":cur["id"],
                    "state":cur["state"],
                    "side":cur["side"],
                    "age_sec":max(0,now-cur["start_ts"]),
                    "start_score":cur["start_score"],
                    "max_score":cur["max_score"],
                }

        c.commit(); c.close()
        return out

    def recent(self,limit=20):
        c=self.con()
        rows=[dict(r) for r in c.execute("""
          SELECT * FROM opportunities
          ORDER BY start_ts DESC LIMIT ?
        """,(int(limit),)).fetchall()]
        c.close()
        return rows

    def recent_events(self,limit=40):
        c=self.con()
        rows=[dict(r) for r in c.execute("""
          SELECT e.*,o.lane,o.side
          FROM opportunity_events e
          JOIN opportunities o ON o.opportunity_id=e.opportunity_id
          ORDER BY e.id DESC LIMIT ?
        """,(int(limit),)).fetchall()]
        c.close()
        return rows

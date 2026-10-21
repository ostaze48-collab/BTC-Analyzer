from __future__ import annotations
import json, math, time, sqlite3, threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional
import requests
import numpy as np
import pandas as pd

BINANCE_SPOT_BASES=["https://data-api.binance.vision","https://api.binance.com"]
BINANCE_FAPI="https://fapi.binance.com"

NATIVE={
 "1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m",
 "1H":"1h","2H":"2h","4H":"4h","6H":"6h","8H":"8h","12H":"12h",
 "1D":"1d","3D":"3d","1W":"1w","1M":"1M"
}
CUSTOM_DAILY={"12D":"12D","2W":"14D"}
CONTEXT_WINDOWS={"3M":90,"6M":180,"1Y":365}

def clamp(x,lo=-1.0,hi=1.0): return max(lo,min(hi,float(x)))
def safe(v,d=0.0):
    try:
        if v is None or (isinstance(v,float) and math.isnan(v)): return d
        return float(v)
    except Exception:return d
def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(c,n=14):
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    rs=up/dn.replace(0,np.nan)
    return (100-100/(1+rs)).fillna(50)
def atr(df,n=14):
    pc=df.close.shift(1)
    tr=pd.concat([(df.high-df.low).abs(),(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)
    return tr.ewm(alpha=1/n,adjust=False).mean()
def adx(df,n=14):
    up=df.high.diff(); dn=-df.low.diff()
    plus=pd.Series(np.where((up>dn)&(up>0),up,0.0),index=df.index)
    minus=pd.Series(np.where((dn>up)&(dn>0),dn,0.0),index=df.index)
    tr=atr(df,n).replace(0,np.nan)
    pdi=100*plus.ewm(alpha=1/n,adjust=False).mean()/tr
    mdi=100*minus.ewm(alpha=1/n,adjust=False).mean()/tr
    dx=(100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)).fillna(0)
    return dx.ewm(alpha=1/n,adjust=False).mean().fillna(0)
def macd_hist(c):
    m=ema(c,12)-ema(c,26); return m-ema(m,9)

class BinanceData:
    def __init__(self,symbol="BTCUSDT"):
        self.symbol=symbol; self.s=requests.Session()
        self.s.headers.update({"User-Agent":"BTC-Analyzer-V1.3/1.0"})
        self.spot_provider=None
        self.last_spot_error=None
    def get(self,url,params=None):
        r=self.s.get(url,params=params,timeout=15); r.raise_for_status(); return r.json()
    def get_spot(self,path,params=None):
        errors=[]
        for base in BINANCE_SPOT_BASES:
            try:
                r=self.s.get(base+path,params=params,timeout=15)
                r.raise_for_status()
                self.spot_provider=base
                self.last_spot_error=None
                return r.json()
            except Exception as e:
                errors.append(f"{base}: {e}")
        self.last_spot_error=" | ".join(errors)
        raise RuntimeError("All Binance spot market-data endpoints failed: "+self.last_spot_error)
    def klines(self,iv,limit=500):
        raw=self.get_spot("/api/v3/klines",{"symbol":self.symbol,"interval":iv,"limit":limit})
        cols=["open_time","open","high","low","close","volume","close_time","quote_volume","trades","taker_base","taker_quote","ignore"]
        df=pd.DataFrame(raw,columns=cols)
        for c in ["open","high","low","close","volume","quote_volume","taker_base","taker_quote"]:
            df[c]=pd.to_numeric(df[c],errors="coerce")
        df["open_time"]=pd.to_datetime(df.open_time,unit="ms",utc=True)
        return df.set_index("open_time")[["open","high","low","close","volume","quote_volume","taker_base","taker_quote"]].dropna()
    def resample(self,df,rule):
        return pd.DataFrame({
            "open":df.open.resample(rule).first(),
            "high":df.high.resample(rule).max(),
            "low":df.low.resample(rule).min(),
            "close":df.close.resample(rule).last(),
            "volume":df.volume.resample(rule).sum(),
            "quote_volume":df.quote_volume.resample(rule).sum(),
            "taker_base":df.taker_base.resample(rule).sum(),
            "taker_quote":df.taker_quote.resample(rule).sum(),
        }).dropna()
    def all_frames(self):
        out={}
        for tf,iv in NATIVE.items():
            try: out[tf]=self.klines(iv,500)
            except Exception: pass

        daily=out.get("1D")
        if daily is None or len(daily)<365:
            daily=self.klines("1d",500)
            out["1D"]=daily

        monthly=out.get("1M")
        if monthly is None:
            try:
                monthly=self.klines("1M",500)
                out["1M"]=monthly
            except Exception:
                monthly=None

        # Custom candle intervals.
        for tf,rule in CUSTOM_DAILY.items():
            try:
                out[tf]=self.resample(daily,rule)
            except Exception:
                pass

        # Macro context horizons.
        # These are NOT one giant yearly candle. They analyze the complete
        # last 90/180/365 daily candles, which gives indicators enough history.
        for tf,days in CONTEXT_WINDOWS.items():
            try:
                if len(daily)>=60:
                    out[tf]=daily.tail(min(days,len(daily))).copy()
            except Exception:
                pass
        return out
    def futures(self):
        x={"funding":None,"open_interest":None,"mark_price":None,"status":"UNAVAILABLE","error":None}
        errs=[]
        try:
            p=self.get(BINANCE_FAPI+"/fapi/v1/premiumIndex",{"symbol":self.symbol})
            x["funding"]=safe(p.get("lastFundingRate"),None); x["mark_price"]=safe(p.get("markPrice"),None)
            x["status"]="PARTIAL"
        except Exception as e:
            errs.append("premiumIndex: "+str(e))
        try:
            o=self.get(BINANCE_FAPI+"/fapi/v1/openInterest",{"symbol":self.symbol})
            x["open_interest"]=safe(o.get("openInterest"),None)
            x["status"]="OK" if x["mark_price"] is not None else "PARTIAL"
        except Exception as e:
            errs.append("openInterest: "+str(e))
        if errs: x["error"]=" | ".join(errs)
        return x

@dataclass
class TFAnalysis:
    tf:str; price:float; structure:str; trend:str; trend_score:float
    momentum_score:float; volume_score:float; volatility:str; atr_pct:float
    rsi:float; adx:float; wave_direction:str; wave_type:str; wave_state:str
    wave_change_pct:float; bos:str; support:Optional[float]; resistance:Optional[float]
    overextended:bool

class Analyzer:
    ORDER=["1Y","6M","3M","1M","2W","12D","1W","3D","1D","12H","8H","6H","4H","2H","1H","30m","15m","5m","3m","1m"]
    def pivots(self,df,w=3):
        if len(df)<15:return [],[]
        ph=df.high==df.high.rolling(2*w+1,center=True).max()
        pl=df.low==df.low.rolling(2*w+1,center=True).min()
        hs=[(i,float(df.high.loc[i])) for i in df.index[ph.fillna(False)]]
        ls=[(i,float(df.low.loc[i])) for i in df.index[pl.fillna(False)]]
        return hs[-8:],ls[-8:]
    def structure(self,df):
        hs,ls=self.pivots(df); struct="NEUTRAL";bos="NONE";sup=res=None
        if len(hs)>=2 and len(ls)>=2:
            h1,h2=hs[-2][1],hs[-1][1]; l1,l2=ls[-2][1],ls[-1][1]
            struct="BULLISH" if h2>h1 and l2>l1 else "BEARISH" if h2<h1 and l2<l1 else "RANGE/MIXED"
            p=float(df.close.iloc[-1]); sup=l2;res=h2
            if p>h2:bos="BOS_UP"
            elif p<l2:bos="BOS_DOWN"
        return struct,bos,sup,res
    def wave(self,df):
        if len(df)<30:return "NEUTRAL","UNKNOWN","FORMING",0.0
        threshold=max(safe(atr(df).iloc[-1])*1.2,safe(df.close.iloc[-1])*0.003)
        c=df.close.values; piv=[(0,c[0])]; direction=0; ext=c[0];ei=0
        for i,p in enumerate(c[1:],1):
            if direction>=0:
                if p>ext:ext=p;ei=i
                if ext-p>=threshold:piv.append((ei,ext));direction=-1;ext=p;ei=i
            if direction<=0:
                if p<ext:ext=p;ei=i
                if p-ext>=threshold:piv.append((ei,ext));direction=1;ext=p;ei=i
        if piv[-1][0]!=len(c)-1:piv.append((len(c)-1,c[-1]))
        if len(piv)<2:return "NEUTRAL","UNKNOWN","FORMING",0.0
        i0,p0=piv[-2];i1,p1=piv[-1];ch=(p1/p0-1)*100 if p0 else 0
        wd="UP" if ch>0 else "DOWN"
        prev=abs((piv[-2][1]/piv[-3][1]-1)*100) if len(piv)>=3 else 0
        wt="IMPULSE" if abs(ch)>=max(prev*.65,.5) else "CORRECTION"
        rm=safe(df.close.pct_change(3).iloc[-1])*100
        ws="MATURE" if abs(rm)<.05 else "EXHAUSTING" if (wd=="UP" and rm<0) or (wd=="DOWN" and rm>0) else "EXPANDING"
        return wd,wt,ws,ch
    def analyze_tf(self,tf,df):
        df=df.dropna().copy(); c=df.close;p=float(c.iloc[-1])
        e20=ema(c,20);e50=ema(c,50);e200=ema(c,min(200,max(50,len(c)//2)))
        ax=adx(df);rr=rsi(c);mh=macd_hist(c);at=atr(df)
        ap=safe(at.iloc[-1]/p*100); slope=safe(e20.pct_change(5).iloc[-1])*100
        ts=(.35 if p>e20.iloc[-1] else -.35)+(.30 if e20.iloc[-1]>e50.iloc[-1] else -.30)+(.20 if e50.iloc[-1]>e200.iloc[-1] else -.20)+clamp(slope)*.15
        ts=clamp(ts); trend="BULLISH" if ts>.25 else "BEARISH" if ts<-.25 else "NEUTRAL"
        ms=clamp(clamp((rr.iloc[-1]-50)/25)*.45+clamp(safe(mh.iloc[-1])/(p*.001))*.35+clamp(safe(c.pct_change(5).iloc[-1])*100)*.20)
        rv=safe(df.volume.iloc[-1]/df.volume.rolling(20).mean().iloc[-1],1)
        tr=safe(df.taker_base.iloc[-1]/max(df.volume.iloc[-1],1e-9),.5)
        vs=clamp((rv-1)*.5+(tr-.5)*2)
        st,bos,sup,res=self.structure(df);wd,wt,ws,wc=self.wave(df)
        bbw=safe((c.rolling(20).std()*4/c.rolling(20).mean()).iloc[-1])
        vol="HIGH" if ap>2 or bbw>.08 else "LOW" if ap<.35 else "NORMAL"
        over=abs(p-e20.iloc[-1])/max(safe(at.iloc[-1]),1e-9)>2.5
        return TFAnalysis(tf,p,st,trend,ts,ms,vs,vol,ap,float(rr.iloc[-1]),float(ax.iloc[-1]),wd,wt,ws,wc,bos,sup,res,over)
    def group(self,A,tfs):
        vals=[]
        for tf in tfs:
            a=A.get(tf)
            if not a:continue
            s=a.trend_score*.45+a.momentum_score*.25+(0.15 if a.structure=="BULLISH" else -0.15 if a.structure=="BEARISH" else 0)+(0.10 if a.wave_direction=="UP" else -0.10 if a.wave_direction=="DOWN" else 0)+a.volume_score*.05
            vals.append(s)
        return clamp(np.mean(vals)) if vals else 0
    def state(self,frames,fut):
        A={}
        for tf in self.ORDER:
            df=frames.get(tf)
            if df is not None and len(df)>=25:
                try:
                    A[tf]=self.analyze_tf(tf,df)
                except Exception:
                    pass

        H={
          "macro":self.group(A,["1Y","6M","3M","1M"]),
          "longterm":self.group(A,["2W","12D","1W","3D","1D"]),
          "swing":self.group(A,["12H","8H","6H","4H"]),
          "intraday":self.group(A,["2H","1H","30m"]),
          "entry":self.group(A,["15m","5m","3m","1m"])
        }

        # Independent evidence families. Indicators from the same family
        # do not get separate full votes.
        vals={"structure":[],"wave":[],"trend":[],"momentum":[],"volume":[]}
        for tf,a in A.items():
            w=3 if tf in ("1D","4H","1H","15m") else 1
            vals["structure"] += [1 if a.structure=="BULLISH" else -1 if a.structure=="BEARISH" else 0]*w
            vals["wave"] += [1 if a.wave_direction=="UP" else -1 if a.wave_direction=="DOWN" else 0]*w
            vals["trend"] += [a.trend_score]*w
            vals["momentum"] += [a.momentum_score]*w
            vals["volume"] += [a.volume_score]*w

        fam={k:clamp(np.mean(v) if v else 0) for k,v in vals.items()}

        funding=fut.get("funding")
        fam["derivatives"]=clamp(-funding/.001)*.25 if funding is not None else 0

        bias_score=clamp(
            H["macro"]*.15 +
            H["longterm"]*.25 +
            H["swing"]*.35 +
            H["intraday"]*.25
        )
        bias="BULLISH" if bias_score>.18 else "BEARISH" if bias_score<-.18 else "NEUTRAL"
        d=1 if bias=="BULLISH" else -1 if bias=="BEARISH" else 0

        # Confirmation status: a negative family is not automatically a hard veto.
        conf={}
        confirms=0
        strong_family_opposition=0
        for k,v in fam.items():
            aligned=(v*d)>.15 if d else False
            opposed=(v*d)<-.25 if d else False
            hard_opposed=(v*d)<-.55 if d else False
            if aligned:
                conf[k]="CONFIRM"
                confirms+=1
            elif hard_opposed and k in ("structure","wave","trend","momentum"):
                conf[k]="STRONG_VETO"
                strong_family_opposition+=1
            elif opposed:
                conf[k]="WARN"
            else:
                conf[k]="NEUTRAL"

        a15=A.get("15m")
        a5=A.get("5m")
        a3=A.get("3m")
        a1m=A.get("1m")
        a1h=A.get("1H")

        strong_veto=[]
        warnings=[]

        # Hard blockers.
        if d and H["entry"]*d<-.35:
            strong_veto.append("ENTRY_TIMEFRAME_STRONGLY_OPPOSED")
        if d and H["intraday"]*d<-.35:
            strong_veto.append("INTRADAY_STRONGLY_OPPOSED")
        if strong_family_opposition>=2:
            strong_veto.append("MULTIPLE_CORE_FAMILIES_OPPOSED")
        if a15 and a15.overextended:
            strong_veto.append("ENTRY_OVEREXTENDED")

        # Soft warnings: visible, but one warning alone does not cancel a setup.
        if d:
            if H["macro"]*d<.10:
                warnings.append("MACRO_WEAK")
            if H["longterm"]*d<.10:
                warnings.append("LONGTERM_WEAK")
            if H["entry"]*d<.45:
                warnings.append("ENTRY_ALIGNMENT_WEAK")
            if fam.get("volume",0)*d<-.20:
                warnings.append("VOLUME_OPPOSES")
            if fam.get("derivatives",0)*d<-.20:
                warnings.append("DERIVATIVES_OPPOSE")
            if fam.get("momentum",0)*d<-.20:
                warnings.append("MOMENTUM_OPPOSES")
        if a1h and a1h.volatility=="HIGH":
            warnings.append("HIGH_VOLATILITY")
        if a15 and a15.wave_state=="EXHAUSTING":
            warnings.append("15M_WAVE_EXHAUSTING")

        # Lower timeframe agreement is useful for timing, not for macro bias.
        lower_checks=[]
        for a in (a5,a3,a1m):
            if not a or not d:
                continue
            aligned=(a.trend_score*d>.15) and (
                (d>0 and a.wave_direction=="UP") or
                (d<0 and a.wave_direction=="DOWN")
            )
            lower_checks.append(aligned)
        lower_confirm_ratio=(sum(lower_checks)/len(lower_checks)) if lower_checks else 0.0
        if d and lower_checks and lower_confirm_ratio<.67:
            warnings.append("LOWER_TF_NOT_SYNCHRONIZED")

        # Setup state is separate from trigger state.
        if not d:
            setup_state="NO_BIAS"
        elif strong_veto:
            setup_state="BLOCKED"
        else:
            setup_core=(
                H["swing"]*d>=.20 and
                H["intraday"]*d>=.25 and
                sum(1 for k in ("structure","wave","trend","momentum") if conf.get(k)=="CONFIRM")>=2
            )
            setup_state="READY" if setup_core else "FORMING"

        trigger_conditions=[]
        if d:
            trigger_conditions.append(H["entry"]*d>=.45)
            trigger_conditions.append(lower_confirm_ratio>=.67 if lower_checks else False)

            # 15m or 5m must show directionally aligned trend/wave.
            entry_tf_ok=False
            for a in (a15,a5):
                if not a:
                    continue
                wave_ok=(d>0 and a.wave_direction=="UP") or (d<0 and a.wave_direction=="DOWN")
                if a.trend_score*d>.20 and wave_ok and not a.overextended:
                    entry_tf_ok=True
                    break
            trigger_conditions.append(entry_tf_ok)

        trigger_score=(sum(trigger_conditions)/len(trigger_conditions)*100) if trigger_conditions else 0.0
        if setup_state=="BLOCKED":
            trigger_state="BLOCKED"
        elif setup_state!="READY":
            trigger_state="NOT_READY"
        elif trigger_score>=99:
            trigger_state="TRIGGERED"
        elif trigger_score>=66:
            trigger_state="READY"
        else:
            trigger_state="NOT_READY"

        # Quality score: evidence + hierarchy, with transparent penalties.
        qs=0.0
        if d:
            qs=(
                max(0,bias_score*d)*30 +
                max(0,H["swing"]*d)*18 +
                max(0,H["intraday"]*d)*17 +
                max(0,H["entry"]*d)*15 +
                confirms/max(1,len(fam))*20
            )
        qs -= min(15, len(warnings)*2.5)
        qs -= len(strong_veto)*25
        qs=max(0,min(100,qs))
        q="A+" if qs>=85 else "A" if qs>=72 else "B" if qs>=58 else "C"

        action="WAIT"
        if d and setup_state=="READY" and trigger_state=="TRIGGERED" and not strong_veto and q in ("A","A+"):
            action="LONG" if d>0 else "SHORT"

        # Explain WAIT explicitly.
        why_wait=[]
        waiting_for=[]
        if action=="WAIT":
            if not d:
                why_wait.append("NO_CLEAR_DIRECTION")
                waiting_for.append("CLEAR_MULTI_TIMEFRAME_BIAS")
            else:
                if strong_veto:
                    why_wait.extend(strong_veto)
                    waiting_for.append("REMOVE_STRONG_VETO")
                if setup_state=="FORMING":
                    why_wait.append("SETUP_STILL_FORMING")
                if q not in ("A","A+"):
                    why_wait.append("QUALITY_BELOW_A")
                    waiting_for.append("QUALITY_A_OR_BETTER")
                if H["entry"]*d<.45:
                    why_wait.append("ENTRY_NOT_ALIGNED")
                    waiting_for.append("ENTRY_SCORE_ABOVE_45")
                if lower_checks and lower_confirm_ratio<.67:
                    why_wait.append("LOWER_TIMEFRAMES_NOT_CONFIRMED")
                    waiting_for.append("LOWER_TF_SYNCHRONIZATION")
                if trigger_state!="TRIGGERED":
                    why_wait.append("TRIGGER_NOT_CONFIRMED")
                    waiting_for.append("15M_5M_TRIGGER")
                if "VOLUME_OPPOSES" in warnings:
                    why_wait.append("VOLUME_AGAINST_BIAS")
                    waiting_for.append("VOLUME_IMPROVEMENT")

        # Remove duplicates while preserving order.
        why_wait=list(dict.fromkeys(why_wait))
        waiting_for=list(dict.fromkeys(waiting_for))
        warnings=list(dict.fromkeys(warnings))
        strong_veto=list(dict.fromkeys(strong_veto))

        veto_level="BLOCKED" if strong_veto else "SOFT_WARNING" if warnings else "CLEAR"

        price=A.get("1m",A.get("5m",A.get("15m",next(iter(A.values())) if A else None)))
        price=price.price if price else None
        t=A.get("15m") or A.get("1H")
        sl=tp1=tp2=None
        if t and price and d:
            dist=max(price*t.atr_pct/100*1.2,price*.0035)
            if d>0:
                sl=price-dist;tp1=price+1.5*dist;tp2=price+2.5*dist
            else:
                sl=price+dist;tp1=price-1.5*dist;tp2=price-2.5*dist

        return {
            "ts":time.time(),
            "price":price,
            "bias":bias,
            "bias_score":bias_score,
            "action":action,
            "quality":q,
            "quality_score":qs,
            "setup_state":setup_state,
            "trigger_state":trigger_state,
            "trigger_score":trigger_score,
            "hierarchy":H,
            "families":fam,
            "confirmations":conf,
            "veto":strong_veto,
            "strong_veto":strong_veto,
            "warnings":warnings,
            "veto_level":veto_level,
            "why_wait":why_wait,
            "waiting_for":waiting_for,
            "lower_tf_confirm_ratio":lower_confirm_ratio,
            "plan":{"entry":price,"sl":sl,"tp1":tp1,"tp2":tp2},
            "futures":fut,
            "timeframes":{k:asdict(v) for k,v in A.items()},
            "context_note":"1Y/6M/3M are rolling daily-chart analysis horizons, not single annual/semiannual candles."
        }

class PaperTracker:
    def __init__(self,path,start=100,risk=.5,cooldown=30):
        self.path=str(path);self.start=start;self.risk=risk;self.cooldown=cooldown*60;self.init()
    def con(self):
        c=sqlite3.connect(self.path,timeout=5);c.row_factory=sqlite3.Row;return c
    def init(self):
        c=self.con();c.execute("""CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY AUTOINCREMENT,ts REAL,side TEXT,quality TEXT,quality_score REAL,entry REAL,sl REAL,tp1 REAL,tp2 REAL,status TEXT DEFAULT 'OPEN',exit_ts REAL,exit_price REAL,result_r REAL DEFAULT 0,reason TEXT)""");c.commit();c.close()
    def add(self,s):
        if s.get("action") not in ("LONG","SHORT"):return
        p=s["plan"]
        if any(p.get(k) is None for k in ("entry","sl","tp1","tp2")):return
        c=self.con();last=c.execute("SELECT ts FROM signals ORDER BY id DESC LIMIT 1").fetchone()
        if last and time.time()-last["ts"]<self.cooldown:c.close();return
        c.execute("INSERT INTO signals(ts,side,quality,quality_score,entry,sl,tp1,tp2,reason) VALUES(?,?,?,?,?,?,?,?,?)",(time.time(),s["action"],s["quality"],s["quality_score"],p["entry"],p["sl"],p["tp1"],p["tp2"],json.dumps({"bias":s["bias"],"confirmations":s["confirmations"]})));c.commit();c.close()
    def update(self,price):
        if price is None:return
        c=self.con();rows=c.execute("SELECT * FROM signals WHERE status='OPEN'").fetchall();now=time.time()
        for r in rows:
            st=None;rr=0;ex=None
            if r["side"]=="LONG":
                if price<=r["sl"]:st="LOSS";rr=-1;ex=r["sl"]
                elif price>=r["tp2"]:st="WIN_TP2";rr=2.5;ex=r["tp2"]
                elif price>=r["tp1"]:st="WIN_TP1";rr=1.5;ex=r["tp1"]
            else:
                if price>=r["sl"]:st="LOSS";rr=-1;ex=r["sl"]
                elif price<=r["tp2"]:st="WIN_TP2";rr=2.5;ex=r["tp2"]
                elif price<=r["tp1"]:st="WIN_TP1";rr=1.5;ex=r["tp1"]
            if not st and now-r["ts"]>86400:st="EXPIRED";ex=price
            if st:c.execute("UPDATE signals SET status=?,exit_ts=?,exit_price=?,result_r=? WHERE id=?",(st,now,ex,rr,r["id"]))
        c.commit();c.close()
    def stats(self):
        c=self.con();rows=c.execute("SELECT * FROM signals ORDER BY id DESC").fetchall();c.close()
        closed=[r for r in rows if r["status"]!="OPEN"];wins=[r for r in closed if str(r["status"]).startswith("WIN")];loss=[r for r in closed if r["status"]=="LOSS"]
        bal=self.start
        for r in reversed(closed):bal+=bal*(self.risk/100)*float(r["result_r"])
        return {"total":len(rows),"open":sum(r["status"]=="OPEN" for r in rows),"closed":len(closed),"wins":len(wins),"losses":len(loss),"win_rate":len(wins)/max(1,len(wins)+len(loss))*100,"virtual_balance":bal,"recent":[dict(r) for r in rows[:30]]}

class Engine:
    def __init__(self,root,cfg):
        self.cfg=cfg;self.data=BinanceData(cfg["symbol"]);self.an=Analyzer()
        self.paper=PaperTracker(root/"paper.db",cfg["paper_start_balance"],cfg["paper_risk_per_trade_pct"],cfg["signal_cooldown_minutes"])
        self.state={"status":"STARTING"};self.lock=threading.RLock();self.stop=threading.Event()
    def cycle(self):
        s=self.an.state(self.data.all_frames(),self.data.futures());s["data_provider"]=self.data.spot_provider;s["spot_error"]=self.data.last_spot_error;self.paper.update(s.get("price"));self.paper.add(s);s["paper"]=self.paper.stats();s["status"]="OK"
        with self.lock:self.state=s
    def run(self):
        while not self.stop.is_set():
            try:self.cycle()
            except Exception as e:
                with self.lock:self.state={"status":"ERROR","error":str(e),"ts":time.time()}
            self.stop.wait(self.cfg.get("refresh_seconds",60))
    def snapshot(self):
        with self.lock:return json.loads(json.dumps(self.state,default=str))

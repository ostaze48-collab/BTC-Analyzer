from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
import numpy as np

from .core import clamp, safe, ema, rsi, atr, adx, macd_hist

@dataclass
class TFAnalysis:
    tf:str
    price:float
    structure:str
    trend:str
    trend_score:float
    momentum_score:float
    volume_score:float
    volatility:str
    atr_pct:float
    rsi:float
    adx:float
    wave_direction:str
    wave_type:str
    wave_state:str
    wave_change_pct:float
    bos:str
    support:Optional[float]
    resistance:Optional[float]
    overextended:bool

class MarketAnalyzer:
    ORDER=[
        "1Y","6M","3M","1M","2W","12D","1W","3D","1D",
        "12H","8H","6H","4H","2H","1H","30m","15m","5m","3m","1m"
    ]

    def pivots(self,df,w=3):
        if len(df)<15:
            return [],[]
        ph=df["high"]==df["high"].rolling(2*w+1,center=True).max()
        pl=df["low"]==df["low"].rolling(2*w+1,center=True).min()
        hs=[(i,float(df["high"].loc[i])) for i in df.index[ph.fillna(False)]]
        ls=[(i,float(df["low"].loc[i])) for i in df.index[pl.fillna(False)]]
        return hs[-10:],ls[-10:]

    def structure(self,df):
        hs,ls=self.pivots(df)
        struct="NEUTRAL"; bos="NONE"; sup=res=None
        if len(hs)>=2 and len(ls)>=2:
            h1,h2=hs[-2][1],hs[-1][1]
            l1,l2=ls[-2][1],ls[-1][1]
            if h2>h1 and l2>l1:
                struct="BULLISH"
            elif h2<h1 and l2<l1:
                struct="BEARISH"
            else:
                struct="RANGE/MIXED"
            p=float(df["close"].iloc[-1])
            sup=l2; res=h2
            if p>h2:
                bos="BOS_UP"
            elif p<l2:
                bos="BOS_DOWN"
        return struct,bos,sup,res

    def wave(self,df):
        if len(df)<30:
            return "NEUTRAL","UNKNOWN","FORMING",0.0
        threshold=max(
            safe(atr(df).iloc[-1])*1.2,
            safe(df["close"].iloc[-1])*0.003
        )
        c=df["close"].values
        piv=[(0,c[0])]
        direction=0
        ext=c[0]
        ei=0

        for i,p in enumerate(c[1:],1):
            if direction>=0:
                if p>ext:
                    ext=p; ei=i
                if ext-p>=threshold:
                    piv.append((ei,ext)); direction=-1; ext=p; ei=i
            if direction<=0:
                if p<ext:
                    ext=p; ei=i
                if p-ext>=threshold:
                    piv.append((ei,ext)); direction=1; ext=p; ei=i

        if piv[-1][0] != len(c)-1:
            piv.append((len(c)-1,c[-1]))
        if len(piv)<2:
            return "NEUTRAL","UNKNOWN","FORMING",0.0

        _,p0=piv[-2]
        _,p1=piv[-1]
        ch=(p1/p0-1)*100 if p0 else 0.0
        wd="UP" if ch>0 else "DOWN"

        prev=abs((piv[-2][1]/piv[-3][1]-1)*100) if len(piv)>=3 else 0
        wt="IMPULSE" if abs(ch)>=max(prev*.65,.5) else "CORRECTION"

        rm=safe(df["close"].pct_change(3).iloc[-1])*100
        if abs(rm)<.05:
            ws="MATURE"
        elif (wd=="UP" and rm<0) or (wd=="DOWN" and rm>0):
            ws="EXHAUSTING"
        else:
            ws="EXPANDING"
        return wd,wt,ws,ch

    def analyze_tf(self,tf,df):
        df=df.dropna().copy()
        c=df["close"]
        p=float(c.iloc[-1])

        e20=ema(c,20)
        e50=ema(c,50)
        e200=ema(c,min(200,max(50,len(c)//2)))

        ax=adx(df)
        rr=rsi(c)
        mh=macd_hist(c)
        at=atr(df)

        atr_pct=safe(at.iloc[-1]/p*100)
        slope=safe(e20.pct_change(5).iloc[-1])*100

        trend_score=(
            (.35 if p>e20.iloc[-1] else -.35) +
            (.30 if e20.iloc[-1]>e50.iloc[-1] else -.30) +
            (.20 if e50.iloc[-1]>e200.iloc[-1] else -.20) +
            clamp(slope)*.15
        )
        trend_score=clamp(trend_score)
        trend="BULLISH" if trend_score>.25 else "BEARISH" if trend_score<-.25 else "NEUTRAL"

        momentum_score=clamp(
            clamp((rr.iloc[-1]-50)/25)*.45 +
            clamp(safe(mh.iloc[-1])/(p*.001))*.35 +
            clamp(safe(c.pct_change(5).iloc[-1])*100)*.20
        )

        rel_vol=safe(df["volume"].iloc[-1]/df["volume"].rolling(20).mean().iloc[-1],1)
        taker_ratio=safe(df["taker_base"].iloc[-1]/max(df["volume"].iloc[-1],1e-9),.5)
        volume_score=clamp((rel_vol-1)*.5+(taker_ratio-.5)*2)

        struct,bos,sup,res=self.structure(df)
        wd,wt,ws,wc=self.wave(df)

        bbw=safe((c.rolling(20).std()*4/c.rolling(20).mean()).iloc[-1])
        volatility="HIGH" if atr_pct>2 or bbw>.08 else "LOW" if atr_pct<.35 else "NORMAL"

        overextended=bool(abs(p-e20.iloc[-1])/max(safe(at.iloc[-1]),1e-9)>2.5)

        return TFAnalysis(
            tf,p,struct,trend,trend_score,momentum_score,volume_score,
            volatility,atr_pct,float(rr.iloc[-1]),float(ax.iloc[-1]),
            wd,wt,ws,wc,bos,sup,res,overextended
        )

    def _group(self, A, tfs):
        vals=[]
        for tf in tfs:
            a=A.get(tf)
            if not a:
                continue
            s=(
                a.trend_score*.45 +
                a.momentum_score*.25 +
                (0.15 if a.structure=="BULLISH" else -0.15 if a.structure=="BEARISH" else 0) +
                (0.10 if a.wave_direction=="UP" else -0.10 if a.wave_direction=="DOWN" else 0) +
                a.volume_score*.05
            )
            vals.append(s)
        return clamp(float(np.mean(vals))) if vals else 0.0

    def analyze(self,frames,futures):
        A={}
        for tf in self.ORDER:
            df=frames.get(tf)
            if df is None or len(df)<25:
                continue
            try:
                A[tf]=self.analyze_tf(tf,df)
            except Exception:
                continue

        # Macro horizons are correlated because they are derived from daily data.
        # We use their median as one macro-context vote instead of triple-counting.
        macro_context_vals=[
            A[tf].trend_score*.55 + A[tf].momentum_score*.25 +
            (0.10 if A[tf].structure=="BULLISH" else -0.10 if A[tf].structure=="BEARISH" else 0) +
            (0.10 if A[tf].wave_direction=="UP" else -0.10 if A[tf].wave_direction=="DOWN" else 0)
            for tf in ("1Y","6M","3M") if tf in A
        ]
        macro_context=float(np.median(macro_context_vals)) if macro_context_vals else 0.0
        monthly=A.get("1M")
        monthly_score=(
            monthly.trend_score*.55 + monthly.momentum_score*.25 +
            (0.10 if monthly.structure=="BULLISH" else -0.10 if monthly.structure=="BEARISH" else 0) +
            (0.10 if monthly.wave_direction=="UP" else -0.10 if monthly.wave_direction=="DOWN" else 0)
        ) if monthly else 0.0

        hierarchy={
            "macro":clamp(macro_context*.60 + monthly_score*.40),
            "longterm":self._group(A,["2W","12D","1W","3D","1D"]),
            "swing":self._group(A,["12H","8H","6H","4H"]),
            "intraday":self._group(A,["2H","1H","30m"]),
            "entry":self._group(A,["15m","5m","3m","1m"]),
        }

        vals={"structure":[],"wave":[],"trend":[],"momentum":[],"volume":[]}
        for tf,a in A.items():
            weight=3 if tf in ("1D","4H","1H","15m") else 1
            vals["structure"] += [1 if a.structure=="BULLISH" else -1 if a.structure=="BEARISH" else 0]*weight
            vals["wave"] += [1 if a.wave_direction=="UP" else -1 if a.wave_direction=="DOWN" else 0]*weight
            vals["trend"] += [a.trend_score]*weight
            vals["momentum"] += [a.momentum_score]*weight
            vals["volume"] += [a.volume_score]*weight

        families={k:clamp(float(np.mean(v)) if v else 0.0) for k,v in vals.items()}
        funding=futures.get("funding")
        families["derivatives"]=clamp(-funding/.001)*.25 if funding is not None else 0.0

        general_score=clamp(
            hierarchy["macro"]*.15 +
            hierarchy["longterm"]*.25 +
            hierarchy["swing"]*.35 +
            hierarchy["intraday"]*.25
        )
        bias="BULLISH" if general_score>.18 else "BEARISH" if general_score<-.18 else "NEUTRAL"

        return {
            "bias":bias,
            "bias_score":general_score,
            "hierarchy":hierarchy,
            "families":families,
            "timeframes":{k:asdict(v) for k,v in A.items()},
            "futures":futures,
            "macro_context_note":"1Y/6M/3M are correlated rolling daily horizons and are median-combined, not triple-counted."
        }

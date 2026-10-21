from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np

from .core import atr, clamp, safe


class PriceActionEngine:
    """
    Pure price-action geometry on CLOSED candles.

    Families:
    1) Support / Resistance Zones
    2) Trendlines / Channels
    3) Candlestick patterns
    4) Classical chart-pattern candidates

    The engine does not create trades. It produces evidence for DecisionEngine.
    """

    IMPORTANT_TFS=("1W","3D","1D","12H","8H","6H","4H","2H","1H","30m","15m","5m","3m","1m")

    def _pivots(self,df,w=3,limit=16):
        if df is None or len(df)<2*w+8:
            return [],[]
        h=df["high"]
        l=df["low"]
        ph=(h==h.rolling(2*w+1,center=True).max()).fillna(False)
        pl=(l==l.rolling(2*w+1,center=True).min()).fillna(False)

        highs=[]
        lows=[]
        for pos,(idx,row) in enumerate(df.iterrows()):
            if bool(ph.iloc[pos]):
                highs.append({"pos":pos,"ts":str(idx),"price":float(row["high"])})
            if bool(pl.iloc[pos]):
                lows.append({"pos":pos,"ts":str(idx),"price":float(row["low"])})
        return highs[-limit:],lows[-limit:]

    def _cluster_levels(self,points,price,tol):
        if not points:
            return []
        groups=[]
        for p in sorted(points,key=lambda x:x["price"]):
            placed=False
            for g in groups:
                center=float(np.mean([x["price"] for x in g]))
                if abs(p["price"]-center)<=tol:
                    g.append(p); placed=True; break
            if not placed:
                groups.append([p])

        out=[]
        for g in groups:
            center=float(np.mean([x["price"] for x in g]))
            last=max(x["pos"] for x in g)
            touches=len(g)
            side="SUPPORT" if center<price else "RESISTANCE" if center>price else "AT_PRICE"
            dist=abs(center-price)/max(price,1e-9)*100
            out.append({
                "center":center,
                "low":min(x["price"] for x in g)-tol*.35,
                "high":max(x["price"] for x in g)+tol*.35,
                "touches":touches,
                "last_touch_pos":last,
                "side":side,
                "distance_pct":dist,
            })
        return out

    def zones(self,df):
        if df is None or len(df)<30:
            return {"zones":[],"nearest_support":None,"nearest_resistance":None}
        price=float(df["close"].iloc[-1])
        at=safe(atr(df).iloc[-1],price*.003)
        tol=max(at*.40,price*.0012)
        highs,lows=self._pivots(df,w=3,limit=20)

        # Cluster highs and lows together to detect role-flip zones.
        pts=[{**x,"origin":"HIGH"} for x in highs]+[{**x,"origin":"LOW"} for x in lows]
        clusters=self._cluster_levels(pts,price,tol)

        recent_close=df["close"].tail(8).astype(float).tolist()
        n=len(df)
        enriched=[]
        for z in clusters:
            members=[
                p for p in pts
                if abs(p["price"]-z["center"])<=tol*1.15
            ]
            high_origins=sum(1 for x in members if x["origin"]=="HIGH")
            low_origins=sum(1 for x in members if x["origin"]=="LOW")
            role_flip=high_origins>0 and low_origins>0

            age=max(0,n-1-int(z["last_touch_pos"]))
            if z["touches"]<=1:
                freshness="FRESH"
            elif z["touches"]<=3:
                freshness="TESTED"
            else:
                freshness="WEAKENED"

            strength=min(100,
                38 + min(4,z["touches"])*12 +
                (12 if role_flip else 0) +
                max(0,18-min(age,18))
            )

            # Recent close-through and retest approximation.
            above=[c>z["high"] for c in recent_close]
            below=[c<z["low"] for c in recent_close]
            breakout="NONE"
            retest=False
            if any(above[:-1]) and recent_close[-1]>z["high"]:
                breakout="BREAK_UP"
                retest=any(z["low"]<=c<=z["high"] for c in recent_close[-3:])
            elif any(below[:-1]) and recent_close[-1]<z["low"]:
                breakout="BREAK_DOWN"
                retest=any(z["low"]<=c<=z["high"] for c in recent_close[-3:])

            enriched.append({
                **z,
                "role_flip":role_flip,
                "freshness":freshness,
                "strength":round(strength,1),
                "breakout":breakout,
                "retest":bool(retest),
            })

        supports=sorted(
            [z for z in enriched if z["center"]<price],
            key=lambda z:abs(price-z["center"])
        )
        resistances=sorted(
            [z for z in enriched if z["center"]>price],
            key=lambda z:abs(price-z["center"])
        )
        return {
            "zones":sorted(enriched,key=lambda z:z["distance_pct"])[:10],
            "nearest_support":supports[0] if supports else None,
            "nearest_resistance":resistances[0] if resistances else None,
            "tolerance":tol,
        }

    @staticmethod
    def _line_from_points(points):
        if len(points)<2:
            return None
        xs=np.array([p["pos"] for p in points],dtype=float)
        ys=np.array([p["price"] for p in points],dtype=float)
        if np.ptp(xs)<=0:
            return None
        slope,intercept=np.polyfit(xs,ys,1)
        fitted=slope*xs+intercept
        ss_res=float(np.sum((ys-fitted)**2))
        ss_tot=float(np.sum((ys-np.mean(ys))**2))
        r2=1.0-ss_res/ss_tot if ss_tot>1e-12 else 1.0
        return slope,intercept,max(0,min(1,r2))

    def trendlines(self,df):
        if df is None or len(df)<35:
            return {
                "support_line":None,"resistance_line":None,
                "channel":"NONE","breakout":"NONE","retest":False
            }
        price=float(df["close"].iloc[-1])
        at=safe(atr(df).iloc[-1],price*.003)
        tol=max(at*.45,price*.0015)
        highs,lows=self._pivots(df,w=3,limit=10)
        n=len(df)
        last_x=n-1

        def build(points,kind):
            if len(points)<2:
                return None
            pts=points[-4:]
            line=self._line_from_points(pts)
            if not line:
                return None
            slope,intercept,r2=line
            projected=slope*last_x+intercept
            residuals=[abs(p["price"]-(slope*p["pos"]+intercept)) for p in points[-6:]]
            touches=sum(1 for r in residuals if r<=tol)
            slope_pct_bar=slope/max(price,1e-9)*100

            valid_direction=(
                (kind=="SUPPORT" and slope>0) or
                (kind=="RESISTANCE" and slope<0)
            )
            return {
                "kind":kind,
                "slope":float(slope),
                "slope_pct_per_bar":float(slope_pct_bar),
                "intercept":float(intercept),
                "projected":float(projected),
                "r2":float(r2),
                "touches":int(touches),
                "valid_direction":bool(valid_direction),
                "distance_pct":abs(price-projected)/max(price,1e-9)*100,
                "points":pts,
            }

        support=build(lows,"SUPPORT")
        resistance=build(highs,"RESISTANCE")

        recent=df.tail(5)
        breakout="NONE"; retest=False
        if support and support["valid_direction"] and support["r2"]>=.55:
            vals=[
                support["slope"]*(n-len(recent)+i)+support["intercept"]
                for i in range(len(recent))
            ]
            closes=recent["close"].astype(float).tolist()
            if any(c<v-tol for c,v in zip(closes[:-1],vals[:-1])) and closes[-1]<vals[-1]-tol:
                breakout="TRENDLINE_BREAK_DOWN"
                retest=abs(closes[-1]-vals[-1])<=tol*1.4

        if resistance and resistance["valid_direction"] and resistance["r2"]>=.55:
            vals=[
                resistance["slope"]*(n-len(recent)+i)+resistance["intercept"]
                for i in range(len(recent))
            ]
            closes=recent["close"].astype(float).tolist()
            if any(c>v+tol for c,v in zip(closes[:-1],vals[:-1])) and closes[-1]>vals[-1]+tol:
                breakout="TRENDLINE_BREAK_UP"
                retest=abs(closes[-1]-vals[-1])<=tol*1.4

        channel="NONE"
        if support and resistance and support["r2"]>=.50 and resistance["r2"]>=.50:
            s1=support["slope_pct_per_bar"]
            s2=resistance["slope_pct_per_bar"]
            if abs(s1-s2)<=max(.01,abs(s1)*.40,abs(s2)*.40):
                if s1>0 and s2>0:
                    channel="ASCENDING_CHANNEL"
                elif s1<0 and s2<0:
                    channel="DESCENDING_CHANNEL"
                else:
                    channel="HORIZONTAL_CHANNEL"

        return {
            "support_line":support,
            "resistance_line":resistance,
            "channel":channel,
            "breakout":breakout,
            "retest":bool(retest),
        }

    @staticmethod
    def _bar(row):
        o=float(row["open"]); h=float(row["high"])
        l=float(row["low"]); c=float(row["close"])
        body=abs(c-o)
        rng=max(h-l,1e-9)
        upper=h-max(o,c)
        lower=min(o,c)-l
        return {
            "open":o,"high":h,"low":l,"close":c,
            "body":body,"range":rng,"upper":upper,"lower":lower,
            "bull":c>o,"bear":c<o,
            "body_ratio":body/rng,
        }

    def candles(self,df):
        if df is None or len(df)<4:
            return {"patterns":[],"directional_score":0.0}
        b0=self._bar(df.iloc[-1])
        b1=self._bar(df.iloc[-2])
        b2=self._bar(df.iloc[-3])
        pats=[]

        def add(name,direction,strength):
            pats.append({
                "name":name,
                "direction":direction,
                "strength":round(float(strength),1)
            })

        if b0["body_ratio"]<=.12:
            add("DOJI","NEUTRAL",45)

        if b0["lower"]>=max(b0["body"]*2.0,b0["range"]*.45) and b0["upper"]<=b0["range"]*.18:
            add("HAMMER","BULLISH",68 if b0["bull"] else 60)

        if b0["upper"]>=max(b0["body"]*2.0,b0["range"]*.45) and b0["lower"]<=b0["range"]*.18:
            add("SHOOTING_STAR","BEARISH",68 if b0["bear"] else 60)

        if (
            b1["bear"] and b0["bull"] and
            b0["open"]<=b1["close"] and b0["close"]>=b1["open"] and
            b0["body"]>=b1["body"]*.9
        ):
            add("BULLISH_ENGULFING","BULLISH",78)

        if (
            b1["bull"] and b0["bear"] and
            b0["open"]>=b1["close"] and b0["close"]<=b1["open"] and
            b0["body"]>=b1["body"]*.9
        ):
            add("BEARISH_ENGULFING","BEARISH",78)

        if b0["high"]<b1["high"] and b0["low"]>b1["low"]:
            add("INSIDE_BAR","NEUTRAL",55)

        # Morning / Evening Star approximations.
        if (
            b2["bear"] and b2["body_ratio"]>.45 and
            b1["body_ratio"]<.28 and
            b0["bull"] and b0["close"]>(b2["open"]+b2["close"])/2
        ):
            add("MORNING_STAR","BULLISH",82)

        if (
            b2["bull"] and b2["body_ratio"]>.45 and
            b1["body_ratio"]<.28 and
            b0["bear"] and b0["close"]<(b2["open"]+b2["close"])/2
        ):
            add("EVENING_STAR","BEARISH",82)

        # Outside bar.
        if b0["high"]>b1["high"] and b0["low"]<b1["low"]:
            add(
                "BULLISH_OUTSIDE_BAR" if b0["bull"] else "BEARISH_OUTSIDE_BAR",
                "BULLISH" if b0["bull"] else "BEARISH",
                66
            )

        score=0.0
        for p in pats:
            sign=1 if p["direction"]=="BULLISH" else -1 if p["direction"]=="BEARISH" else 0
            score+=sign*(p["strength"]/100)
        score=clamp(score/2.0)

        return {
            "patterns":pats,
            "directional_score":score,
            "primary":max(pats,key=lambda x:x["strength"]) if pats else None,
        }

    def _pattern_validation(self,p,df,tol,highs,lows):
        """
        Validate a detected geometric pattern against CLOSED candles.

        Status:
        - CANDIDATE: geometry exists but breakout is not confirmed.
        - CONFIRMED: close is beyond the validation level.
        - RETESTED: breakout happened and price retested the validation level.
        - FAILED: invalidation level was breached.
        - ACTIVE: channel-type structure without a directional breakout requirement.
        """
        name=p.get("name")
        direction=p.get("direction","NEUTRAL")
        d=p.setdefault("details",{})
        close=float(df["close"].iloc[-1])
        high=float(df["high"].iloc[-1])
        low=float(df["low"].iloc[-1])
        closes=df["close"].astype(float)
        recent=closes.tail(6).tolist()

        status="CANDIDATE"
        breakout_level=None
        invalidation=None
        target=None
        retest=False

        if name=="DOUBLE_TOP":
            tops=d.get("tops") or []
            neckline=safe(d.get("neckline"))
            if len(tops)>=2 and neckline:
                peak=float(np.mean(tops))
                breakout_level=neckline
                invalidation=max(tops)+tol
                target=neckline-max(peak-neckline,0)
                if close>invalidation:
                    status="FAILED"
                elif close<neckline-tol*.15:
                    status="CONFIRMED"
                    if any(x<neckline-tol*.15 for x in recent[:-1]) and high>=neckline-tol:
                        status="RETESTED"; retest=True

        elif name=="DOUBLE_BOTTOM":
            bottoms=d.get("bottoms") or []
            neckline=safe(d.get("neckline"))
            if len(bottoms)>=2 and neckline:
                trough=float(np.mean(bottoms))
                breakout_level=neckline
                invalidation=min(bottoms)-tol
                target=neckline+max(neckline-trough,0)
                if close<invalidation:
                    status="FAILED"
                elif close>neckline+tol*.15:
                    status="CONFIRMED"
                    if any(x>neckline+tol*.15 for x in recent[:-1]) and low<=neckline+tol:
                        status="RETESTED"; retest=True

        elif name=="HEAD_AND_SHOULDERS" and len(highs)>=3:
            a,b,c=highs[-3],highs[-2],highs[-1]
            left_low=float(df["low"].iloc[a["pos"]:b["pos"]+1].min())
            right_low=float(df["low"].iloc[b["pos"]:c["pos"]+1].min())
            neckline=(left_low+right_low)/2
            d["neckline"]=neckline
            breakout_level=neckline
            invalidation=float(b["price"])+tol
            target=neckline-max(float(b["price"])-neckline,0)
            if close>invalidation:
                status="FAILED"
            elif close<neckline-tol*.15:
                status="CONFIRMED"
                if any(x<neckline-tol*.15 for x in recent[:-1]) and high>=neckline-tol:
                    status="RETESTED"; retest=True

        elif name=="INVERSE_HEAD_AND_SHOULDERS" and len(lows)>=3:
            a,b,c=lows[-3],lows[-2],lows[-1]
            left_high=float(df["high"].iloc[a["pos"]:b["pos"]+1].max())
            right_high=float(df["high"].iloc[b["pos"]:c["pos"]+1].max())
            neckline=(left_high+right_high)/2
            d["neckline"]=neckline
            breakout_level=neckline
            invalidation=float(b["price"])-tol
            target=neckline+max(neckline-float(b["price"]),0)
            if close<invalidation:
                status="FAILED"
            elif close>neckline+tol*.15:
                status="CONFIRMED"
                if any(x>neckline+tol*.15 for x in recent[:-1]) and low<=neckline+tol:
                    status="RETESTED"; retest=True

        elif name in {
            "SYMMETRICAL_TRIANGLE","ASCENDING_TRIANGLE","DESCENDING_TRIANGLE",
            "RISING_WEDGE","FALLING_WEDGE","CHANNEL"
        } and len(highs)>=3 and len(lows)>=3:
            hp=highs[-4:] if len(highs)>=4 else highs[-3:]
            lp=lows[-4:] if len(lows)>=4 else lows[-3:]
            xh=np.array([x["pos"] for x in hp],dtype=float)
            yh=np.array([x["price"] for x in hp],dtype=float)
            xl=np.array([x["pos"] for x in lp],dtype=float)
            yl=np.array([x["price"] for x in lp],dtype=float)

            sh,ih=np.polyfit(xh,yh,1)
            sl,il=np.polyfit(xl,yl,1)
            pos=len(df)-1
            upper=float(sh*pos+ih)
            lower=float(sl*pos+il)
            if lower>upper:
                lower,upper=upper,lower
            d["upper_boundary"]=upper
            d["lower_boundary"]=lower

            width=max(upper-lower,tol)
            if name=="CHANNEL":
                status="ACTIVE"
                target=upper if direction=="BULLISH" else lower if direction=="BEARISH" else None
            else:
                bullish_pattern=name in ("ASCENDING_TRIANGLE","FALLING_WEDGE")
                bearish_pattern=name in ("DESCENDING_TRIANGLE","RISING_WEDGE")
                neutral_pattern=name=="SYMMETRICAL_TRIANGLE"

                if bullish_pattern:
                    invalidation=lower-tol
                    if close<lower-tol*.15:
                        status="FAILED"
                    elif close>upper+tol*.15:
                        status="CONFIRMED"
                        direction="BULLISH"
                        breakout_level=upper
                        target=close+width
                        if any(x>upper+tol*.15 for x in recent[:-1]) and low<=upper+tol:
                            status="RETESTED"; retest=True

                elif bearish_pattern:
                    invalidation=upper+tol
                    if close>upper+tol*.15:
                        status="FAILED"
                    elif close<lower-tol*.15:
                        status="CONFIRMED"
                        direction="BEARISH"
                        breakout_level=lower
                        target=close-width
                        if any(x<lower-tol*.15 for x in recent[:-1]) and high>=lower-tol:
                            status="RETESTED"; retest=True

                elif neutral_pattern:
                    if close>upper+tol*.15:
                        status="CONFIRMED"
                        direction="BULLISH"
                        breakout_level=upper
                        invalidation=lower-tol
                        target=close+width
                        if any(x>upper+tol*.15 for x in recent[:-1]) and low<=upper+tol:
                            status="RETESTED"; retest=True
                    elif close<lower-tol*.15:
                        status="CONFIRMED"
                        direction="BEARISH"
                        breakout_level=lower
                        invalidation=upper+tol
                        target=close-width
                        if any(x<lower-tol*.15 for x in recent[:-1]) and high>=lower-tol:
                            status="RETESTED"; retest=True

        elif name in ("BULL_FLAG","BEAR_FLAG"):
            look=df.tail(12)
            prior=look.iloc[:-1]
            if len(prior)>=5:
                upper=float(prior["high"].max())
                lower=float(prior["low"].min())
                width=max(upper-lower,tol)
                if name=="BULL_FLAG":
                    breakout_level=upper
                    invalidation=lower-tol
                    if close<invalidation:
                        status="FAILED"
                    elif close>upper+tol*.10:
                        status="CONFIRMED"
                        target=close+width
                        if low<=upper+tol:
                            status="RETESTED"; retest=True
                else:
                    breakout_level=lower
                    invalidation=upper+tol
                    if close>invalidation:
                        status="FAILED"
                    elif close<lower-tol*.10:
                        status="CONFIRMED"
                        target=close-width
                        if high>=lower-tol:
                            status="RETESTED"; retest=True

        p["direction"]=direction
        p["validation"]={
            "status":status,
            "breakout_level":breakout_level,
            "invalidation":invalidation,
            "target":target,
            "retest":bool(retest),
        }
        return p

    @staticmethod
    def _pattern_weight_multiplier(status):
        return {
            "CANDIDATE":0.35,
            "ACTIVE":0.45,
            "CONFIRMED":1.0,
            "RETESTED":1.15,
            "FAILED":0.0,
        }.get(status,0.35)

    def chart_patterns(self,df):
        if df is None or len(df)<45:
            return {"patterns":[],"directional_score":0.0}
        price=float(df["close"].iloc[-1])
        at=safe(atr(df).iloc[-1],price*.003)
        tol=max(at*.65,price*.0025)
        highs,lows=self._pivots(df,w=3,limit=10)
        pats=[]

        def add(name,direction,strength,details=None):
            pats.append({
                "name":name,
                "direction":direction,
                "strength":round(float(strength),1),
                "details":details or {}
            })

        # Double top / bottom
        if len(highs)>=2:
            a,b=highs[-2],highs[-1]
            sep=b["pos"]-a["pos"]
            if 4<=sep<=45 and abs(a["price"]-b["price"])<=tol:
                neckline=min(
                    float(df["low"].iloc[a["pos"]:b["pos"]+1].min()),
                    min(a["price"],b["price"])
                )
                add("DOUBLE_TOP","BEARISH",72,{
                    "tops":[a["price"],b["price"]],
                    "neckline":neckline
                })

        if len(lows)>=2:
            a,b=lows[-2],lows[-1]
            sep=b["pos"]-a["pos"]
            if 4<=sep<=45 and abs(a["price"]-b["price"])<=tol:
                neckline=max(
                    float(df["high"].iloc[a["pos"]:b["pos"]+1].max()),
                    max(a["price"],b["price"])
                )
                add("DOUBLE_BOTTOM","BULLISH",72,{
                    "bottoms":[a["price"],b["price"]],
                    "neckline":neckline
                })

        # Head & shoulders candidates
        if len(highs)>=3:
            a,b,c=highs[-3],highs[-2],highs[-1]
            shoulders_close=abs(a["price"]-c["price"])<=tol*1.5
            if b["price"]>a["price"]+tol*.5 and b["price"]>c["price"]+tol*.5 and shoulders_close:
                add("HEAD_AND_SHOULDERS","BEARISH",76,{
                    "left":a["price"],"head":b["price"],"right":c["price"]
                })

        if len(lows)>=3:
            a,b,c=lows[-3],lows[-2],lows[-1]
            shoulders_close=abs(a["price"]-c["price"])<=tol*1.5
            if b["price"]<a["price"]-tol*.5 and b["price"]<c["price"]-tol*.5 and shoulders_close:
                add("INVERSE_HEAD_AND_SHOULDERS","BULLISH",76,{
                    "left":a["price"],"head":b["price"],"right":c["price"]
                })

        # Triangle / wedge / channel from regression of recent pivots.
        def fit(points):
            if len(points)<3:
                return None
            pts=points[-4:]
            xs=np.array([x["pos"] for x in pts],dtype=float)
            ys=np.array([x["price"] for x in pts],dtype=float)
            if np.ptp(xs)<=0:
                return None
            slope,intercept=np.polyfit(xs,ys,1)
            return float(slope),float(intercept),pts

        fh=fit(highs); fl=fit(lows)
        if fh and fl:
            sh,ih,hp=fh
            sl,il,lp=fl
            shp=sh/max(price,1e-9)*100
            slp=sl/max(price,1e-9)*100

            # Converging boundaries.
            converging=(sh<sl)
            if converging:
                if sh<0 and sl>0:
                    add("SYMMETRICAL_TRIANGLE","NEUTRAL",66,{
                        "upper_slope_pct":shp,"lower_slope_pct":slp
                    })
                elif abs(sl)<=abs(sh)*.35 and sh<0:
                    add("DESCENDING_TRIANGLE","BEARISH",68,{
                        "upper_slope_pct":shp,"lower_slope_pct":slp
                    })
                elif abs(sh)<=abs(sl)*.35 and sl>0:
                    add("ASCENDING_TRIANGLE","BULLISH",68,{
                        "upper_slope_pct":shp,"lower_slope_pct":slp
                    })
                elif sh>0 and sl>0:
                    add("RISING_WEDGE","BEARISH",64,{
                        "upper_slope_pct":shp,"lower_slope_pct":slp
                    })
                elif sh<0 and sl<0:
                    add("FALLING_WEDGE","BULLISH",64,{
                        "upper_slope_pct":shp,"lower_slope_pct":slp
                    })

            # Parallel boundaries => channel.
            if abs(shp-slp)<=max(.01,abs(shp)*.35,abs(slp)*.35):
                direction="BULLISH" if (shp+slp)/2>0 else "BEARISH" if (shp+slp)/2<0 else "NEUTRAL"
                add("CHANNEL",direction,60,{
                    "upper_slope_pct":shp,"lower_slope_pct":slp
                })

        # Flag candidate: strong prior move followed by compact counter/sideways pullback.
        if len(df)>=30:
            c=df["close"].astype(float)
            impulse=(c.iloc[-10]/c.iloc[-30]-1)*100
            recent=(c.iloc[-1]/c.iloc[-10]-1)*100
            recent_range=(df["high"].iloc[-10:].max()-df["low"].iloc[-10:].min())/price*100
            if impulse>2.0 and recent_range<abs(impulse)*.65 and recent<=1.0:
                add("BULL_FLAG","BULLISH",62,{
                    "impulse_pct":float(impulse),"flag_range_pct":float(recent_range)
                })
            elif impulse<-2.0 and recent_range<abs(impulse)*.65 and recent>=-1.0:
                add("BEAR_FLAG","BEARISH",62,{
                    "impulse_pct":float(impulse),"flag_range_pct":float(recent_range)
                })

        pats=[
            self._pattern_validation(p,df,tol,highs,lows)
            for p in pats
        ]

        score=0.0
        for p in pats:
            sign=1 if p["direction"]=="BULLISH" else -1 if p["direction"]=="BEARISH" else 0
            status=(p.get("validation") or {}).get("status","CANDIDATE")
            mult=self._pattern_weight_multiplier(status)
            score+=sign*(p["strength"]/100)*mult
        score=clamp(score/2.2)

        ranked=sorted(
            pats,
            key=lambda x:(
                self._pattern_weight_multiplier((x.get("validation") or {}).get("status","CANDIDATE")),
                x["strength"]
            ),
            reverse=True
        )[:6]

        return {
            "patterns":ranked,
            "directional_score":score,
            "primary":ranked[0] if ranked else None,
        }

    def _timeframe_confluence(self,tf,df):
        price=float(df["close"].iloc[-1])
        zones=self.zones(df)
        lines=self.trendlines(df)
        candles=self.candles(df)
        patterns=self.chart_patterns(df)

        bull=[]; bear=[]

        ns=zones.get("nearest_support")
        nr=zones.get("nearest_resistance")
        if ns and ns["distance_pct"]<=1.0:
            weight=min(1.0,.35+ns["strength"]/140)
            bull.append(("SUPPORT_ZONE",weight,ns))
        if nr and nr["distance_pct"]<=1.0:
            weight=min(1.0,.35+nr["strength"]/140)
            bear.append(("RESISTANCE_ZONE",weight,nr))

        if ns and ns.get("breakout")=="BREAK_DOWN":
            bear.append(("SUPPORT_BREAK",.75,ns))
        if nr and nr.get("breakout")=="BREAK_UP":
            bull.append(("RESISTANCE_BREAK",.75,nr))

        sl=lines.get("support_line")
        rl=lines.get("resistance_line")
        if sl and sl.get("valid_direction") and sl.get("r2",0)>=.55 and sl.get("distance_pct",99)<=1.0:
            bull.append(("UP_TRENDLINE",min(.75,.35+sl["r2"]*.4),sl))
        if rl and rl.get("valid_direction") and rl.get("r2",0)>=.55 and rl.get("distance_pct",99)<=1.0:
            bear.append(("DOWN_TRENDLINE",min(.75,.35+rl["r2"]*.4),rl))

        if lines.get("breakout")=="TRENDLINE_BREAK_UP":
            bull.append(("TRENDLINE_BREAK_UP",.72,lines))
        elif lines.get("breakout")=="TRENDLINE_BREAK_DOWN":
            bear.append(("TRENDLINE_BREAK_DOWN",.72,lines))

        for p in candles.get("patterns",[]):
            w=p["strength"]/100*.65
            if p["direction"]=="BULLISH":
                bull.append((p["name"],w,p))
            elif p["direction"]=="BEARISH":
                bear.append((p["name"],w,p))

        for p in patterns.get("patterns",[]):
            status=(p.get("validation") or {}).get("status","CANDIDATE")
            mult=self._pattern_weight_multiplier(status)
            w=p["strength"]/100*.70*mult
            label=f"{p['name']}[{status}]"
            if w<=0:
                continue
            if p["direction"]=="BULLISH":
                bull.append((label,w,p))
            elif p["direction"]=="BEARISH":
                bear.append((label,w,p))

        # Saturating family score; this is evidence strength, not probability.
        bull_score=min(1.0,sum(x[1] for x in bull)/2.2)
        bear_score=min(1.0,sum(x[1] for x in bear)/2.2)
        directional=clamp(bull_score-bear_score)

        if directional>.22:
            state="BULLISH"
        elif directional<-.22:
            state="BEARISH"
        else:
            state="NEUTRAL"

        return {
            "tf":tf,
            "price":price,
            "zones":zones,
            "trendlines":lines,
            "candles":candles,
            "chart_patterns":patterns,
            "bullish_evidence":[x[0] for x in bull],
            "bearish_evidence":[x[0] for x in bear],
            "bullish_score":bull_score,
            "bearish_score":bear_score,
            "directional_score":directional,
            "state":state,
        }

    def analyze(self,frames):
        out={}
        for tf in self.IMPORTANT_TFS:
            df=frames.get(tf)
            if df is None or len(df)<25:
                continue
            try:
                out[tf]=self._timeframe_confluence(tf,df)
            except Exception as e:
                out[tf]={
                    "tf":tf,"state":"ERROR","directional_score":0.0,
                    "error":str(e)
                }

        # High-level summary only; DecisionEngine performs lane-specific matching.
        vals=[
            x.get("directional_score",0.0)
            for tf,x in out.items()
            if tf in ("1D","4H","1H","30m","15m","5m")
        ]
        score=float(np.mean(vals)) if vals else 0.0
        return {
            "summary_score":clamp(score),
            "summary_state":"BULLISH" if score>.18 else "BEARISH" if score<-.18 else "NEUTRAL",
            "timeframes":out,
            "closed_candles_only":True,
            "note":"Price-action patterns are confluence evidence, never standalone trade triggers."
        }

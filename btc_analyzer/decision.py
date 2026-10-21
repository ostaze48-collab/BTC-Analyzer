from __future__ import annotations
from .core import clamp, safe


class DecisionEngine:
    MIN_RR={"SCALP":1.20,"INTRADAY":1.40,"SWING":1.60}

    CANDLE_NAMES={
        "DOJI","HAMMER","SHOOTING_STAR","BULLISH_ENGULFING",
        "BEARISH_ENGULFING","INSIDE_BAR","MORNING_STAR","EVENING_STAR",
        "BULLISH_OUTSIDE_BAR","BEARISH_OUTSIDE_BAR"
    }

    def _dir_value(self,a):
        if not a:
            return 0.0
        struct=1 if a.get("structure")=="BULLISH" else -1 if a.get("structure")=="BEARISH" else 0
        wave=1 if a.get("wave_direction")=="UP" else -1 if a.get("wave_direction")=="DOWN" else 0
        return clamp(
            safe(a.get("trend_score"))*.45 +
            safe(a.get("momentum_score"))*.20 +
            struct*.20 + wave*.15
        )

    def _context(self,T,names,weights):
        vals=[]; ws=[]
        for tf,w in zip(names,weights):
            a=T.get(tf)
            if a:
                vals.append(self._dir_value(a)*w); ws.append(w)
        return clamp(sum(vals)/sum(ws)) if ws else 0.0

    @staticmethod
    def _aligned(a,d,min_trend=.12,require_wave=True):
        if not a or not d:
            return False
        trend_ok=safe(a.get("trend_score"))*d>=min_trend
        if not require_wave:
            return bool(trend_ok)
        wave_ok=(d>0 and a.get("wave_direction")=="UP") or (d<0 and a.get("wave_direction")=="DOWN")
        return bool(trend_ok and wave_ok)

    @staticmethod
    def _not_strongly_opposed(a,d):
        if not a or not d:
            return True
        struct=a.get("structure")
        struct_opposed=(d>0 and struct=="BEARISH") or (d<0 and struct=="BULLISH")
        trend_opposed=safe(a.get("trend_score"))*d<-.35
        return not (struct_opposed and trend_opposed)

    @staticmethod
    def _grade(score):
        return "A+" if score>=85 else "A" if score>=72 else "B" if score>=58 else "C"

    @staticmethod
    def _cap_grade(grade,cap):
        order={"C":0,"B":1,"A":2,"A+":3}
        return grade if order[grade]<=order[cap] else cap

    @staticmethod
    def _atr_plan(price,a,d,lane):
        if not price or not a or not d:
            return {
                "entry":price,"sl":None,"tp1":None,"tp2":None,
                "risk_pct":None,"mode":"NONE",
                "stop_source":"NONE","tp1_source":"NONE","tp2_source":"NONE"
            }
        atr_pct=max(.01,safe(a.get("atr_pct"),.2))/100
        if lane=="SCALP":
            dist=max(price*atr_pct*1.15,price*.0015); r1,r2=1.3,1.8
        elif lane=="INTRADAY":
            dist=max(price*atr_pct*1.25,price*.0035); r1,r2=1.5,2.2
        else:
            dist=max(price*atr_pct*1.35,price*.008); r1,r2=1.8,2.8
        if d>0:
            sl=price-dist; tp1=price+dist*r1; tp2=price+dist*r2
        else:
            sl=price+dist; tp1=price-dist*r1; tp2=price-dist*r2
        return {
            "entry":price,"sl":sl,"tp1":tp1,"tp2":tp2,
            "risk_pct":dist/price*100,
            "mode":"ATR_FALLBACK",
            "stop_source":"ATR","tp1_source":"ATR_R1","tp2_source":"ATR_R2",
            "invalidation_level":sl,
            "pattern_target":None,
        }

    @staticmethod
    def _confirmed_pattern_target(pa_tf,d,entry):
        if not pa_tf:
            return None,None
        patterns=((pa_tf.get("chart_patterns") or {}).get("patterns") or [])
        best=None
        for p in patterns:
            if (d>0 and p.get("direction")!="BULLISH") or (d<0 and p.get("direction")!="BEARISH"):
                continue
            v=p.get("validation") or {}
            if v.get("status") not in ("CONFIRMED","RETESTED"):
                continue
            target=safe(v.get("target"),None)
            if target is None:
                continue
            if d>0 and target<=entry:
                continue
            if d<0 and target>=entry:
                continue
            strength=safe(p.get("strength"))
            status_bonus=12 if v.get("status")=="RETESTED" else 0
            score=strength+status_bonus
            if best is None or score>best[0]:
                best=(score,float(target),f"{p.get('name')}[{v.get('status')}]")
        return (best[1],best[2]) if best else (None,None)

    @staticmethod
    def _structure_candidates(price,a,d,pa_tf,buffer_abs):
        stops=[]
        targets=[]
        if not pa_tf:
            pa_tf={}

        zones=(pa_tf.get("zones") or {}).get("zones") or []
        for z in zones:
            center=safe(z.get("center"),None)
            if center is None or safe(z.get("strength"))<55:
                continue
            low=safe(z.get("low"),center)
            high=safe(z.get("high"),center)
            if d>0:
                if high<price:
                    stops.append((max(0,low-buffer_abs),"SUPPORT_ZONE"))
                elif center>price:
                    targets.append((center,"RESISTANCE_ZONE"))
            else:
                if low>price:
                    stops.append((high+buffer_abs,"RESISTANCE_ZONE"))
                elif center<price:
                    targets.append((center,"SUPPORT_ZONE"))

        tl=pa_tf.get("trendlines") or {}
        if d>0:
            line=tl.get("support_line")
            if (
                line and line.get("valid_direction") and
                safe(line.get("r2"))>=.55 and
                safe(line.get("projected"))<price
            ):
                stops.append((safe(line.get("projected"))-buffer_abs,"UP_TRENDLINE"))
            opp=tl.get("resistance_line")
            if opp and safe(opp.get("r2"))>=.55 and safe(opp.get("projected"))>price:
                targets.append((safe(opp.get("projected")),"RESISTANCE_TRENDLINE"))
        else:
            line=tl.get("resistance_line")
            if (
                line and line.get("valid_direction") and
                safe(line.get("r2"))>=.55 and
                safe(line.get("projected"))>price
            ):
                stops.append((safe(line.get("projected"))+buffer_abs,"DOWN_TRENDLINE"))
            opp=tl.get("support_line")
            if opp and safe(opp.get("r2"))>=.55 and 0<safe(opp.get("projected"))<price:
                targets.append((safe(opp.get("projected")),"SUPPORT_TRENDLINE"))

        # Existing market-structure swing remains useful as a fallback
        # structural invalidation candidate.
        if d>0:
            sup=safe(a.get("support"),None)
            if sup is not None and 0<sup<price:
                stops.append((sup-buffer_abs,"SWING_SUPPORT"))
            res=safe(a.get("resistance"),None)
            if res is not None and res>price:
                targets.append((res,"SWING_RESISTANCE"))
        else:
            res=safe(a.get("resistance"),None)
            if res is not None and res>price:
                stops.append((res+buffer_abs,"SWING_RESISTANCE"))
            sup=safe(a.get("support"),None)
            if sup is not None and 0<sup<price:
                targets.append((sup,"SWING_SUPPORT"))

        return stops,targets

    def _plan(self,price,a,d,lane,pa_tf=None):
        fallback=self._atr_plan(price,a,d,lane)
        if not price or not a or not d:
            return fallback

        price=float(price)
        atr_abs=price*max(.01,safe(a.get("atr_pct"),.2))/100
        buffer_abs=max(atr_abs*.25,price*.00035)

        if lane=="SCALP":
            min_stop=max(price*.0010,atr_abs*.55)
            max_stop=price*.0080
            default_r1,default_r2=1.3,1.8
        elif lane=="INTRADAY":
            min_stop=max(price*.0020,atr_abs*.60)
            max_stop=price*.0250
            default_r1,default_r2=1.5,2.2
        else:
            min_stop=max(price*.0040,atr_abs*.70)
            max_stop=price*.0600
            default_r1,default_r2=1.8,2.8

        stops,targets=self._structure_candidates(
            price,a,d,pa_tf,buffer_abs
        )

        valid_stops=[]
        for level,source in stops:
            if level is None or level<=0:
                continue
            if d>0 and level>=price:
                continue
            if d<0 and level<=price:
                continue
            dist=abs(price-level)
            if min_stop<=dist<=max_stop:
                valid_stops.append((dist,float(level),source))

        if not valid_stops:
            return fallback

        # Closest trustworthy structural invalidation that is not too tight.
        _,sl,stop_source=min(valid_stops,key=lambda x:x[0])
        risk=abs(price-sl)

        pattern_target,pattern_source=self._confirmed_pattern_target(
            pa_tf,d,price
        )
        if pattern_target is not None:
            targets.append((pattern_target,pattern_source))

        valid_targets=[]
        for level,source in targets:
            if level is None:
                continue
            level=float(level)
            if d>0 and level<=price:
                continue
            if d<0 and level>=price:
                continue
            rr=abs(level-price)/max(risk,1e-9)
            if rr>=.60:
                valid_targets.append((rr,level,source))

        valid_targets.sort(key=lambda x:x[0])

        # TP1: first meaningful obstacle at >=0.8R, otherwise normal R1.
        tp1_candidate=next((x for x in valid_targets if x[0]>=.80),None)
        if tp1_candidate:
            _,tp1,tp1_source=tp1_candidate
        else:
            tp1=price+risk*default_r1*d
            tp1_source="R_MULTIPLE"

        # TP2: strongest farther structural/pattern target at >= lane minimum RR.
        min_rr=self.MIN_RR[lane]
        farther=[x for x in valid_targets if x[0]>=max(min_rr,1.20)]
        if farther:
            # Use farthest target up to 4R to avoid unrealistic distant projections.
            bounded=[x for x in farther if x[0]<=4.0] or farther[:1]
            _,tp2,tp2_source=max(bounded,key=lambda x:x[0])
        else:
            tp2=price+risk*default_r2*d
            tp2_source="R_MULTIPLE"

        # Keep TP ordering sane.
        if d>0 and tp2<=tp1:
            tp2=price+risk*max(default_r2,abs(tp1-price)/risk+.4)
            tp2_source="R_MULTIPLE_AFTER_TP1"
        elif d<0 and tp2>=tp1:
            tp2=price-risk*max(default_r2,abs(tp1-price)/risk+.4)
            tp2_source="R_MULTIPLE_AFTER_TP1"

        return {
            "entry":price,
            "sl":sl,
            "tp1":tp1,
            "tp2":tp2,
            "risk_pct":risk/price*100,
            "mode":"STRUCTURE_AWARE",
            "stop_source":stop_source,
            "tp1_source":tp1_source,
            "tp2_source":tp2_source,
            "invalidation_level":sl,
            "pattern_target":pattern_target,
            "structure_rr_to_tp2":abs(tp2-price)/max(risk,1e-9),
        }

    @staticmethod
    def _pa_family(name):
        if "ZONE" in name or "SUPPORT" in name or "RESISTANCE" in name:
            return "ZONE"
        if "TRENDLINE" in name:
            return "TRENDLINE"
        if name in DecisionEngine.CANDLE_NAMES:
            return "CANDLE"
        return "CHART_PATTERN"

    def _pa_match(self,analysis,tfs,weights,d):
        pa=(analysis.get("price_action") or {}).get("timeframes",{})
        if not d:
            return {
                "score":0.0,"state":"NEUTRAL","aligned_evidence":[],
                "opposed_evidence":[],"aligned_families":[],
                "opposed_families":[],"strong_opposition":False,
                "frames_used":[]
            }

        vals=[]; ws=[]
        aligned=[]; opposed=[]
        aligned_families=set(); opposed_families=set()
        frames_used=[]

        for tf,w in zip(tfs,weights):
            x=pa.get(tf)
            if not x or x.get("state")=="ERROR":
                continue
            frames_used.append(tf)
            ds=safe(x.get("directional_score"))*d
            vals.append(ds*w); ws.append(w)

            good=x.get("bullish_evidence",[]) if d>0 else x.get("bearish_evidence",[])
            bad=x.get("bearish_evidence",[]) if d>0 else x.get("bullish_evidence",[])

            for name in good[:4]:
                label=f"{tf}:{name}"
                if label not in aligned:
                    aligned.append(label)
                aligned_families.add(self._pa_family(name))
            for name in bad[:4]:
                label=f"{tf}:{name}"
                if label not in opposed:
                    opposed.append(label)
                opposed_families.add(self._pa_family(name))

        score=clamp(sum(vals)/sum(ws)) if ws else 0.0
        state="ALIGNED" if score>=.18 else "OPPOSED" if score<=-.18 else "NEUTRAL"

        # A hard veto needs both substantial directional opposition and
        # at least two independent price-action families. A single candle
        # pattern cannot block a trade by itself.
        strong_opposition=bool(
            score<=-.45 and len(opposed_families)>=2 and len(opposed)>=2
        )

        return {
            "score":score,
            "state":state,
            "aligned_evidence":aligned[:8],
            "opposed_evidence":opposed[:8],
            "aligned_families":sorted(aligned_families),
            "opposed_families":sorted(opposed_families),
            "strong_opposition":strong_opposition,
            "frames_used":frames_used,
        }

    @staticmethod
    def _nearest_zone_obstacle(pa_tf,d,entry):
        if not pa_tf or not entry:
            return None
        z=pa_tf.get("zones") or {}
        if d>0:
            r=z.get("nearest_resistance")
            if (
                r and safe(r.get("center"))>entry and
                safe(r.get("strength"))>=55
            ):
                return safe(r.get("center"))
        else:
            s=z.get("nearest_support")
            if (
                s and 0<safe(s.get("center"))<entry and
                safe(s.get("strength"))>=55
            ):
                return safe(s.get("center"))
        return None

    def _diagnostics(self,plan,a,d,lane,triggered,pa_tf=None,pa_match=None):
        entry=plan.get("entry"); sl=plan.get("sl"); tp2=plan.get("tp2")
        if any(x is None for x in (entry,sl,tp2)) or not a or not d:
            return {
                "entry_timing":"UNKNOWN","chasing_risk":"UNKNOWN",
                "available_rr":0.0,"rr_gate_pass":False,
                "structural_obstacle":None,"price_action_state":"NEUTRAL",
                "price_action_score":0.0
            }

        entry=float(entry); sl=float(sl); tp2=float(tp2)
        stop_dist=abs(entry-sl)
        planned_reward=abs(tp2-entry)

        obstacle=None
        if d>0:
            r=a.get("resistance")
            if r is not None and float(r)>entry:
                obstacle=float(r)
        else:
            s=a.get("support")
            if s is not None and float(s)<entry:
                obstacle=float(s)

        # V2.6: use the richer S/R zone as an additional structural obstacle.
        pa_obstacle=self._nearest_zone_obstacle(pa_tf,d,entry)
        if pa_obstacle is not None:
            if obstacle is None or abs(pa_obstacle-entry)<abs(obstacle-entry):
                obstacle=pa_obstacle

        available_reward=planned_reward
        if obstacle is not None:
            available_reward=min(available_reward,abs(obstacle-entry))

        rr=available_reward/max(stop_dist,1e-9)

        if bool(a.get("overextended")) or a.get("wave_state")=="EXHAUSTING":
            chasing="HIGH"
        elif a.get("wave_state")=="MATURE":
            chasing="MEDIUM"
        else:
            chasing="LOW"

        if chasing=="HIGH":
            timing="LATE"
        elif triggered and a.get("wave_state")=="EXPANDING":
            timing="OPTIMAL"
        elif not triggered:
            timing="EARLY"
        else:
            timing="ACCEPTABLE"

        pa_match=pa_match or {}
        return {
            "entry_timing":timing,
            "chasing_risk":chasing,
            "available_rr":rr,
            "rr_gate_pass":bool(rr>=self.MIN_RR[lane]),
            "structural_obstacle":obstacle,
            "price_action_state":pa_match.get("state","NEUTRAL"),
            "price_action_score":safe(pa_match.get("score")),
        }

    def evaluate(self,analysis,context,live_price):
        T=analysis.get("timeframes",{})
        PA=(analysis.get("price_action") or {}).get("timeframes",{})
        global_d=1 if analysis.get("bias")=="BULLISH" else -1 if analysis.get("bias")=="BEARISH" else 0

        scalp_ctx=self._context(T,["4H","1H","30m","15m"],[.30,.30,.20,.20])
        intra_ctx=self._context(T,["1D","4H","1H","30m"],[.25,.35,.25,.15])
        swing_ctx=self._context(T,["1W","3D","1D","4H"],[.20,.20,.35,.25])

        def d_from(s,t=.18):
            return 1 if s>=t else -1 if s<=-t else 0
        ds=d_from(scalp_ctx,.18); di=d_from(intra_ctx,.20); dw=d_from(swing_ctx,.20)

        context_score=safe((context or {}).get("score"),0.0)
        context_alignment=context_score*ds if ds else 0.0

        t1,t3,t5=T.get("1m"),T.get("3m"),T.get("5m")
        t15,t30,t1h,t4h,t1d=T.get("15m"),T.get("30m"),T.get("1H"),T.get("4H"),T.get("1D")

        # Price Action matching. It can reinforce or veto; it never creates
        # a trigger if the original trend/structure/wave trigger is absent.
        pa_scalp=self._pa_match(
            analysis,["15m","5m","3m","1m"],[.20,.40,.25,.15],ds
        )
        pa_intra=self._pa_match(
            analysis,["1H","30m","15m"],[.25,.40,.35],di
        )
        pa_swing=self._pa_match(
            analysis,["1D","4H"],[.45,.55],dw
        )

        a1=self._aligned(t1,ds,.08) if ds else False
        a3=self._aligned(t3,ds,.10) if ds else False
        a5=self._aligned(t5,ds,.12) if ds else False
        a15=self._aligned(t15,ds,.10) if ds else False

        scalp_permission=bool(
            ds and
            (global_d==ds or (global_d==0 and abs(scalp_ctx)>=.45)) and
            safe(analysis.get("hierarchy",{}).get("intraday"))*ds>0 and
            context_alignment>-.25
        )
        common_scalp=bool(
            scalp_permission and
            self._not_strongly_opposed(t15,ds) and
            self._not_strongly_opposed(t30,ds) and
            abs(scalp_ctx)>=.22
        )
        variants={
            "A_BASE_5M":bool(common_scalp and a5),
            "B_5M_3M":bool(common_scalp and a5 and a3),
            "C_FULL_SYNC":bool(common_scalp and a5 and a3 and a1),
            "D_5M_1M":bool(common_scalp and a5 and a1),
        }
        scalp_trigger=variants["D_5M_1M"]
        scalp_score=max(0,min(100,
            abs(scalp_ctx)*55+(18 if a5 else 0)+(12 if a1 else 0)+(8 if a3 else 0)+(7 if a15 else 0)
            + pa_scalp["score"]*8
        ))
        scalp_grade=self._grade(scalp_score)
        if not a15 or not a3 or pa_scalp["state"]=="OPPOSED":
            scalp_grade=self._cap_grade(scalp_grade,"A")
        scalp_plan=self._plan(live_price,t5,ds,"SCALP",PA.get("5m"))
        scalp_diag=self._diagnostics(
            scalp_plan,t5,ds,"SCALP",scalp_trigger,
            PA.get("5m"),pa_scalp
        )
        scalp_action=("LONG" if ds>0 else "SHORT") if (
            scalp_trigger and scalp_grade in ("A","A+") and
            scalp_diag["rr_gate_pass"] and scalp_diag["chasing_risk"]!="HIGH" and
            not pa_scalp["strong_opposition"]
        ) else "WAIT"

        ia15=self._aligned(t15,di,.12) if di else False
        ia30=self._aligned(t30,di,.12) if di else False
        ia1h=self._aligned(t1h,di,.10) if di else False
        intra_permission=bool(di and abs(intra_ctx)>=.25 and self._not_strongly_opposed(t4h,di))
        intra_trigger=bool(intra_permission and ia30 and ia15)
        intra_score=max(0,min(100,
            abs(intra_ctx)*60+(15 if ia1h else 0)+(15 if ia30 else 0)+(10 if ia15 else 0)
            + pa_intra["score"]*8
        ))
        intra_grade=self._grade(intra_score)
        if not ia1h or pa_intra["state"]=="OPPOSED":
            intra_grade=self._cap_grade(intra_grade,"A")
        intra_plan=self._plan(live_price,t15,di,"INTRADAY",PA.get("15m"))
        intra_diag=self._diagnostics(
            intra_plan,t15,di,"INTRADAY",intra_trigger,
            PA.get("15m"),pa_intra
        )
        intra_action=("LONG" if di>0 else "SHORT") if (
            intra_trigger and intra_grade in ("A","A+") and
            intra_diag["rr_gate_pass"] and intra_diag["chasing_risk"]!="HIGH" and
            not pa_intra["strong_opposition"]
        ) else "WAIT"

        wa1d=self._aligned(t1d,dw,.10) if dw else False
        wa4h=self._aligned(t4h,dw,.12) if dw else False
        swing_permission=bool(dw and abs(swing_ctx)>=.25)
        swing_trigger=bool(swing_permission and wa1d and wa4h)
        swing_score=max(0,min(100,
            abs(swing_ctx)*68+(17 if wa1d else 0)+(15 if wa4h else 0)
            + pa_swing["score"]*8
        ))
        swing_grade=self._grade(swing_score)
        if pa_swing["state"]=="OPPOSED":
            swing_grade=self._cap_grade(swing_grade,"A")
        swing_plan=self._plan(live_price,t4h,dw,"SWING",PA.get("4H"))
        swing_diag=self._diagnostics(
            swing_plan,t4h,dw,"SWING",swing_trigger,
            PA.get("4H"),pa_swing
        )
        swing_action=("LONG" if dw>0 else "SHORT") if (
            swing_trigger and swing_grade in ("A","A+") and
            swing_diag["rr_gate_pass"] and swing_diag["chasing_risk"]!="HIGH" and
            not pa_swing["strong_opposition"]
        ) else "WAIT"

        def lane(name,d,ctx,action,grade,score,trigger,plan,diag,why,pa):
            tilt=context_score*15
            long_score=max(0,min(100,50+ctx*50+tilt))
            short_score=max(0,min(100,50-ctx*50-tilt))
            why=dict(why)
            why["rr_gate"]=bool(diag["rr_gate_pass"])
            why["not_chasing"]=diag["chasing_risk"]!="HIGH"
            why["price_action_veto_clear"]=not pa.get("strong_opposition",False)
            return {
                "lane":name,
                "side_bias":"LONG" if d>0 else "SHORT" if d<0 else "NEUTRAL",
                "context_score":ctx,
                "long_direction_score":long_score,
                "short_direction_score":short_score,
                "long_permission":long_score,
                "short_permission":short_score,
                "triggered":bool(trigger),
                "action":action,
                "setup_grade":grade,
                "setup_score":score,
                "why":why,
                "plan":plan,
                "diagnostics":diag,
                "price_action":pa,
            }

        lanes={
            "SCALP":lane(
                "SCALP",ds,scalp_ctx,scalp_action,scalp_grade,scalp_score,
                scalp_trigger,scalp_plan,scalp_diag,{
                    "higher_tf_permission":scalp_permission,
                    "15m_support":a15,"5m_setup":a5,
                    "3m_confirm":a3,"1m_execution":a1
                },pa_scalp
            ),
            "INTRADAY":lane(
                "INTRADAY",di,intra_ctx,intra_action,intra_grade,intra_score,
                intra_trigger,intra_plan,intra_diag,{
                    "1h_support":ia1h,"30m_setup":ia30,"15m_trigger":ia15
                },pa_intra
            ),
            "SWING":lane(
                "SWING",dw,swing_ctx,swing_action,swing_grade,swing_score,
                swing_trigger,swing_plan,swing_diag,{
                    "1d_support":wa1d,"4h_trigger":wa4h
                },pa_swing
            ),
        }

        actionable=[x for x in lanes.values() if x["action"] in ("LONG","SHORT")]
        best=max(actionable or list(lanes.values()),key=lambda x:x["setup_score"])

        return {
            "lanes":lanes,
            "best_setup":best,
            "shadow":{
                "common_ready":common_scalp,
                "side":"LONG" if ds>0 else "SHORT" if ds<0 else "NEUTRAL",
                "direction":ds,
                "context_score":scalp_ctx,
                "variants":variants,
                "plan":scalp_plan
            }
        }

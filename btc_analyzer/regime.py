from __future__ import annotations
from .core import safe

class MarketRegimeEngine:
    """Research/display-only regime classifier using existing V2.0 features."""
    def evaluate(self, analysis):
        T=analysis.get("timeframes",{})
        H=analysis.get("hierarchy",{})
        F=analysis.get("families",{})

        a1h=T.get("1H") or {}
        a15=T.get("15m") or {}

        adx_1h=safe(a1h.get("adx"))
        atr_1h=safe(a1h.get("atr_pct"))
        trend=safe(F.get("trend"))
        momentum=safe(F.get("momentum"))
        structure=safe(F.get("structure"))
        swing=safe(H.get("swing"))
        intraday=safe(H.get("intraday"))
        entry=safe(H.get("entry"))

        if a1h.get("volatility")=="HIGH" or atr_1h>=2.0:
            regime="HIGH_VOL"; confidence=min(100,55+atr_1h*10)
        elif adx_1h>=28 and abs(trend)>=.35 and abs(swing)>=.30:
            regime="TREND"; confidence=min(100,55+adx_1h*.8+abs(trend)*20)
        elif abs(swing)>=.35 and abs(intraday)>=.25 and swing*entry<0:
            regime="PULLBACK"; confidence=min(100,60+abs(swing-entry)*20)
        elif a1h.get("volatility")=="LOW" and adx_1h<20:
            regime="COMPRESSION"; confidence=70
        elif abs(trend)<.20 and abs(structure)<.25 and adx_1h<23:
            regime="RANGE"; confidence=68
        elif (
            abs(swing)>=.35 and
            (a15.get("wave_state")=="EXHAUSTING" or a1h.get("wave_state")=="EXHAUSTING") and
            abs(momentum)<.20
        ):
            regime="EXHAUSTION"; confidence=65
        elif swing*intraday<0 and abs(intraday)>=.25:
            regime="REVERSAL_CANDIDATE"; confidence=62
        else:
            regime="MIXED"; confidence=50

        return {
            "regime":regime,
            "confidence":round(float(confidence),1),
            "research_only":True,
            "drivers":{
                "adx_1h":adx_1h,"atr_1h_pct":atr_1h,
                "trend_family":trend,"momentum_family":momentum,
                "structure_family":structure,"swing":swing,
                "intraday":intraday,"entry":entry,
            }
        }

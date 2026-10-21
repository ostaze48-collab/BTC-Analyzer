from __future__ import annotations
import os, time, requests
from .core import clamp, safe

class BitcoinContextEngine:
    BASE="https://charts.bitbo.io/api/v1"
    ENDPOINTS={
        "realized_price":"realized-price",
        "mvrv":"mvrv",
        "nupl":"nupl-ratio",
        "sopr":"sopr",
        "etf":"etf-flows-new-btc",
    }

    def __init__(self, session=None, refresh_seconds=900):
        self.s=session or requests.Session()
        self.api_key=os.environ.get("BITBO_API_KEY","").strip()
        self.refresh_seconds=max(900,int(refresh_seconds))
        self.last_fetch=0.0
        self.remote={}
        self.remote_status="NO_API_KEY" if not self.api_key else "STARTING"
        self.remote_error=None

    def _latest(self, endpoint):
        r=self.s.get(
            f"{self.BASE}/{endpoint}/",
            params={"latest":"true","api_key":self.api_key},
            timeout=15
        )
        r.raise_for_status()
        rows=(r.json().get("data") or [])
        return rows[-1] if rows else None

    def refresh_remote(self):
        if not self.api_key:
            self.remote_status="NO_API_KEY"
            return
        now=time.time()
        if now-self.last_fetch < self.refresh_seconds:
            return
        out={}
        errors=[]
        for key,endpoint in self.ENDPOINTS.items():
            try:
                out[key]=self._latest(endpoint)
            except Exception as e:
                errors.append(f"{key}: {e}")
        self.last_fetch=now
        if out:
            self.remote=out
        self.remote_error=" | ".join(errors) if errors else None
        self.remote_status="OK" if out and not errors else "PARTIAL" if out else "ERROR"

    @staticmethod
    def _value(row,index,default=None):
        try:
            return float(row[index]) if row is not None else default
        except Exception:
            return default

    def local_metrics(self,frames,spot):
        out={"mayer_multiple":None,"sma200d":None,"ma200w":None,"distance_200w_pct":None}
        if spot is None:
            return out
        try:
            d=frames.get("1D")
            if d is not None and len(d)>=200:
                sma=float(d["close"].tail(200).mean())
                out["sma200d"]=sma
                out["mayer_multiple"]=float(spot)/sma if sma else None
        except Exception:
            pass
        try:
            w=frames.get("1W")
            if w is not None and len(w)>=200:
                ma=float(w["close"].tail(200).mean())
                out["ma200w"]=ma
                out["distance_200w_pct"]=(float(spot)/ma-1)*100 if ma else None
        except Exception:
            pass
        return out

    def evaluate(self,frames,spot):
        self.refresh_remote()
        local=self.local_metrics(frames,spot)

        realized=self._value(self.remote.get("realized_price"),1)
        mvrv=self._value(self.remote.get("mvrv"),1)
        nupl=self._value(self.remote.get("nupl"),1)
        sopr=self._value(self.remote.get("sopr"),1)
        etf_row=self.remote.get("etf")
        etf_7d=self._value(etf_row,3)
        supply_7d=self._value(etf_row,4)
        etf_minus_supply=self._value(etf_row,5)

        components={}
        mm=local.get("mayer_multiple")
        if mm is not None:
            if mm<.85: components["mayer"]=.08
            elif mm<1.0: components["mayer"]=.03
            elif mm<=1.6: components["mayer"]=.10
            elif mm<=2.2: components["mayer"]=.01
            else: components["mayer"]=-.10

        d200=local.get("distance_200w_pct")
        if d200 is not None:
            components["ma200w"]=.08 if d200>0 else -.08

        if realized and spot:
            ratio=float(spot)/realized
            if ratio<.95: components["realized_price"]=.06
            elif ratio<2.0: components["realized_price"]=.08
            elif ratio<3.0: components["realized_price"]=.01
            else: components["realized_price"]=-.08

        if mvrv is not None:
            if mvrv<1.0: components["mvrv"]=.06
            elif mvrv<2.0: components["mvrv"]=.08
            elif mvrv<3.0: components["mvrv"]=.01
            else: components["mvrv"]=-.08

        if nupl is not None:
            if nupl<0: components["nupl"]=.04
            elif nupl<.55: components["nupl"]=.06
            elif nupl<.75: components["nupl"]=.01
            else: components["nupl"]=-.07

        if sopr is not None:
            if sopr<.98: components["sopr"]=-.04
            elif sopr<=1.05: components["sopr"]=.02
            else: components["sopr"]=-.02

        if etf_minus_supply is not None:
            components["etf_vs_supply"]=.08 if etf_minus_supply>0 else -.08

        score=clamp(sum(components.values()),-.35,.35)
        regime="SUPPORTIVE" if score>=.12 else "HEADWIND" if score<=-.12 else "NEUTRAL"
        return {
            "score":score,
            "regime":regime,
            "components":components,
            "local":local,
            "bitbo":{
                "enabled":bool(self.api_key),
                "status":self.remote_status,
                "error":self.remote_error,
                "realized_price":realized,
                "mvrv":mvrv,
                "nupl":nupl,
                "sopr":sopr,
                "etf_7d_avg_btc":etf_7d,
                "new_supply_7d_avg_btc":supply_7d,
                "etf_minus_supply_btc":etf_minus_supply,
                "last_fetch_ts":self.last_fetch or None,
            }
        }

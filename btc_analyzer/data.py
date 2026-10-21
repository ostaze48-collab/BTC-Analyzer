from __future__ import annotations
import time
from dataclasses import dataclass
import requests
import pandas as pd

from .core import safe

SPOT_BASES = ["https://data-api.binance.vision", "https://api.binance.com"]
FAPI_BASE = "https://fapi.binance.com"

NATIVE = {
    "1m":"1m","3m":"3m","5m":"5m","15m":"15m","30m":"30m",
    "1H":"1h","2H":"2h","4H":"4h","6H":"6h","8H":"8h","12H":"12h",
    "1D":"1d","3D":"3d","1W":"1w","1M":"1M"
}
CUSTOM_DAILY = {"12D":"12D","2W":"14D"}
CONTEXT_WINDOWS = {"3M":90,"6M":180,"1Y":365}

TTL = {
    "1m":25,"3m":60,"5m":90,"15m":180,"30m":300,
    "1H":600,"2H":900,"4H":1800,"6H":2400,"8H":3000,"12H":3600,
    "1D":14400,"3D":21600,"1W":43200,"1M":86400
}

@dataclass
class CacheItem:
    fetched_at: float
    df: pd.DataFrame

class MarketDataClient:
    def __init__(self, symbol="BTCUSDT"):
        self.symbol = symbol
        self.s = requests.Session()
        self.s.headers.update({"User-Agent":"BTC-Analyzer-V2.0/1.0"})
        self.spot_provider = None
        self.last_spot_error = None
        self.cache: dict[str, CacheItem] = {}
        self.futures_cache = None
        self.futures_cache_ts = 0.0

    def _spot_get(self, path, params=None):
        errors=[]
        for base in SPOT_BASES:
            try:
                r=self.s.get(base+path, params=params, timeout=15)
                r.raise_for_status()
                self.spot_provider=base
                self.last_spot_error=None
                return r.json()
            except Exception as e:
                errors.append(f"{base}: {e}")
        self.last_spot_error=" | ".join(errors)
        raise RuntimeError("All Binance spot endpoints failed: "+self.last_spot_error)

    def _get(self, url, params=None):
        r=self.s.get(url, params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def live_price(self):
        try:
            p=self._spot_get("/api/v3/ticker/price", {"symbol":self.symbol})
            return float(p["price"])
        except Exception:
            item=self.cache.get("1m")
            if item is not None and len(item.df):
                return float(item.df["close"].iloc[-1])
            raise

    def _fetch_klines(self, interval, limit=500):
        raw=self._spot_get("/api/v3/klines", {
            "symbol":self.symbol, "interval":interval, "limit":limit
        })
        cols=[
            "open_time","open","high","low","close","volume","close_time",
            "quote_volume","trades","taker_base","taker_quote","ignore"
        ]
        df=pd.DataFrame(raw, columns=cols)
        for c in ["open","high","low","close","volume","quote_volume","taker_base","taker_quote"]:
            df[c]=pd.to_numeric(df[c], errors="coerce")
        df["open_time"]=pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"]=pd.to_datetime(df["close_time"], unit="ms", utc=True)
        return df.set_index("open_time")[[
            "open","high","low","close","volume","quote_volume",
            "taker_base","taker_quote","close_time"
        ]].dropna()

    def _cached_native(self, tf, force=False):
        now=time.time()
        item=self.cache.get(tf)
        ttl=TTL.get(tf,300)
        if not force and item and now-item.fetched_at < ttl:
            return item.df
        iv=NATIVE[tf]
        df=self._fetch_klines(iv,500)
        self.cache[tf]=CacheItem(now,df)
        return df

    @staticmethod
    def closed_only(df):
        now=pd.Timestamp.now(tz="UTC")
        return df[df["close_time"] <= now].copy()

    @staticmethod
    def resample(df, rule):
        base=df.drop(columns=["close_time"], errors="ignore")
        grouped=base.resample(rule)
        out=pd.DataFrame({
            "open":grouped["open"].first(),
            "high":grouped["high"].max(),
            "low":grouped["low"].min(),
            "close":grouped["close"].last(),
            "volume":grouped["volume"].sum(),
            "quote_volume":grouped["quote_volume"].sum(),
            "taker_base":grouped["taker_base"].sum(),
            "taker_quote":grouped["taker_quote"].sum(),
        }).dropna()
        # 12D/14D custom candles are used only when the whole bucket is closed.
        # This prevents a partially formed custom candle from repainting analysis.
        try:
            if rule.endswith("D"):
                expected=int(rule[:-1])
                counts=grouped["close"].count()
                out=out[counts.reindex(out.index).fillna(0)>=expected]
        except Exception:
            pass
        return out

    def closed_frames(self):
        out={}
        for tf in NATIVE:
            try:
                out[tf]=self.closed_only(self._cached_native(tf))
            except Exception:
                pass

        daily=out.get("1D")
        if daily is None or len(daily)<365:
            raw=self._fetch_klines("1d",500)
            daily=self.closed_only(raw)
            out["1D"]=daily
            self.cache["1D"]=CacheItem(time.time(),raw)

        for tf,rule in CUSTOM_DAILY.items():
            try:
                out[tf]=self.resample(daily,rule)
            except Exception:
                pass

        for tf,days in CONTEXT_WINDOWS.items():
            if daily is not None and len(daily)>=60:
                out[tf]=daily.tail(min(days,len(daily))).drop(columns=["close_time"],errors="ignore").copy()

        # Strip close_time from analytical frames so indicator code stays clean.
        for tf,df in list(out.items()):
            out[tf]=df.drop(columns=["close_time"], errors="ignore")
        return out

    def latest_closed_1m_bar(self):
        df=self.closed_only(self._cached_native("1m", force=True))
        if df.empty:
            return None
        row=df.iloc[-1]
        return {
            "ts": df.index[-1].timestamp(),
            "open":float(row["open"]),
            "high":float(row["high"]),
            "low":float(row["low"]),
            "close":float(row["close"]),
        }

    def freshness(self):
        now=time.time()
        out={}
        for tf,item in self.cache.items():
            out[tf]=max(0.0,now-item.fetched_at)
        return out

    def futures(self):
        now=time.time()
        if self.futures_cache is not None and now-self.futures_cache_ts < 300:
            return self.futures_cache
        x={"funding":None,"open_interest":None,"mark_price":None,"status":"UNAVAILABLE","error":None}
        errs=[]
        try:
            p=self._get(FAPI_BASE+"/fapi/v1/premiumIndex",{"symbol":self.symbol})
            x["funding"]=safe(p.get("lastFundingRate"),None)
            x["mark_price"]=safe(p.get("markPrice"),None)
            x["status"]="PARTIAL"
        except Exception as e:
            errs.append("premiumIndex: "+str(e))
        try:
            o=self._get(FAPI_BASE+"/fapi/v1/openInterest",{"symbol":self.symbol})
            x["open_interest"]=safe(o.get("openInterest"),None)
            x["status"]="OK" if x["mark_price"] is not None else "PARTIAL"
        except Exception as e:
            errs.append("openInterest: "+str(e))
        if errs:
            x["error"]=" | ".join(errs)
        self.futures_cache=x
        self.futures_cache_ts=now
        return x

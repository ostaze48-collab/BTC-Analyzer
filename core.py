from __future__ import annotations
import json, math
import numpy as np
import pandas as pd

def clamp(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, float(x)))

def safe(v, default=0.0):
    try:
        if v is None:
            return default
        if isinstance(v, (float, np.floating)) and math.isnan(float(v)):
            return default
        return float(v)
    except Exception:
        return default

def json_native(obj):
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    return str(obj)

def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, default=json_native)

def ema(s, span):
    return s.ewm(span=span, adjust=False).mean()

def rsi(close, period=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)

def atr(df, period=14):
    pc = df["close"].shift(1)
    tr = pd.concat([
        (df["high"]-df["low"]).abs(),
        (df["high"]-pc).abs(),
        (df["low"]-pc).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False).mean()

def adx(df, period=14):
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus = pd.Series(np.where((up>dn)&(up>0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn>up)&(dn>0), dn, 0.0), index=df.index)
    tr = atr(df, period).replace(0, np.nan)
    pdi = 100 * plus.ewm(alpha=1/period, adjust=False).mean() / tr
    mdi = 100 * minus.ewm(alpha=1/period, adjust=False).mean() / tr
    dx = (100 * (pdi-mdi).abs() / (pdi+mdi).replace(0,np.nan)).fillna(0)
    return dx.ewm(alpha=1/period, adjust=False).mean().fillna(0)

def macd_hist(close):
    m = ema(close,12) - ema(close,26)
    return m - ema(m,9)

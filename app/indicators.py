from __future__ import annotations

from statistics import fmean
from typing import Any


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    out = [values[0]]
    for value in values[1:]:
        out.append(alpha * value + (1 - alpha) * out[-1])
    return out


def rsi(values: list[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    gains = []
    losses = []
    for a, b in zip(values[-(period + 1):-1], values[-period:]):
        d = b - a
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_gain = fmean(gains) if gains else 0.0
    avg_loss = fmean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0 if avg_gain else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def true_ranges(candles: list[dict[str, float]]) -> list[float]:
    out: list[float] = []
    for i, c in enumerate(candles):
        if i == 0:
            out.append(c["high"] - c["low"])
        else:
            prev = candles[i - 1]["close"]
            out.append(max(c["high"] - c["low"], abs(c["high"] - prev), abs(c["low"] - prev)))
    return out


def atr(candles: list[dict[str, float]], period: int = 14) -> float:
    trs = true_ranges(candles)
    if not trs:
        return 0.0
    chunk = trs[-period:]
    return fmean(chunk)


def macd(values: list[float]) -> tuple[float, float, float]:
    if len(values) < 35:
        return 0.0, 0.0, 0.0
    e12 = ema(values, 12)
    e26 = ema(values, 26)
    macd_line = [a - b for a, b in zip(e12, e26)]
    sig = ema(macd_line, 9)
    return macd_line[-1], sig[-1], macd_line[-1] - sig[-1]


def rolling_vwap(candles: list[dict[str, float]], period: int = 20) -> float:
    subset = candles[-period:]
    den = sum(c["volume"] for c in subset)
    if den <= 0:
        return subset[-1]["close"] if subset else 0.0
    num = sum(((c["high"] + c["low"] + c["close"]) / 3) * c["volume"] for c in subset)
    return num / den


def structure(candles: list[dict[str, float]]) -> str:
    if len(candles) < 40:
        return "NEUTRAL"
    older = candles[-40:-20]
    recent = candles[-20:]
    oh, ol = max(c["high"] for c in older), min(c["low"] for c in older)
    rh, rl = max(c["high"] for c in recent), min(c["low"] for c in recent)
    if rh > oh and rl > ol:
        return "BULLISH"
    if rh < oh and rl < ol:
        return "BEARISH"
    return "RANGE"


def snapshot(candles: list[dict[str, float]]) -> dict[str, Any]:
    if len(candles) < 30:
        return {}
    closes = [c["close"] for c in candles]
    vols = [c["volume"] for c in candles]
    e20 = ema(closes, 20)[-1]
    e50 = ema(closes, 50)[-1]
    e200 = ema(closes, 200)[-1] if len(closes) >= 200 else ema(closes, min(100, len(closes)))[-1]
    m, ms, mh = macd(closes)
    a = atr(candles, 14)
    close = closes[-1]
    prev_vols = vols[-21:-1]
    vol_avg = fmean(prev_vols) if prev_vols else max(vols[-1], 1e-9)
    vol_ratio = vols[-1] / vol_avg if vol_avg else 1.0

    recent = candles[-30:]
    support = min(c["low"] for c in recent)
    resistance = max(c["high"] for c in recent)
    st = structure(candles)

    if close > e20 > e50 and e50 >= e200 * 0.995:
        trend = "BULLISH"
    elif close < e20 < e50 and e50 <= e200 * 1.005:
        trend = "BEARISH"
    else:
        trend = "MIXED"

    return {
        "close": close,
        "ema20": e20,
        "ema50": e50,
        "ema200": e200,
        "rsi14": rsi(closes, 14),
        "macd": m,
        "macd_signal": ms,
        "macd_hist": mh,
        "atr14": a,
        "vwap20": rolling_vwap(candles, 20),
        "volume_ratio": vol_ratio,
        "support": support,
        "resistance": resistance,
        "structure": st,
        "trend": trend,
        "volatility_pct": (a / close * 100) if close else 0.0,
    }


def vote(s: dict[str, Any]) -> float:
    if not s:
        return 0.0
    score = 0.0
    if s["trend"] == "BULLISH":
        score += 2.0
    elif s["trend"] == "BEARISH":
        score -= 2.0

    score += 0.9 if s["close"] > s["ema20"] else -0.9
    score += 0.7 if s["ema20"] > s["ema50"] else -0.7
    score += 0.5 if s["close"] > s["vwap20"] else -0.5

    r = s["rsi14"]
    if 52 <= r <= 70:
        score += 0.6
    elif 30 <= r <= 48:
        score -= 0.6
    elif r > 78:
        score -= 0.25
    elif r < 22:
        score += 0.25

    if s["macd_hist"] > 0:
        score += 0.8
    elif s["macd_hist"] < 0:
        score -= 0.8

    if s["structure"] == "BULLISH":
        score += 1.0
    elif s["structure"] == "BEARISH":
        score -= 1.0

    # Maximum magnitude is roughly 6.5.
    return max(-1.0, min(1.0, score / 6.5))

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
    gains: list[float] = []
    losses: list[float] = []
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
    return fmean(trs[-period:])


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


def confirmed_pivots(
    candles: list[dict[str, float]],
    left: int = 2,
    right: int = 2,
    lookback: int = 180,
) -> list[dict[str, Any]]:
    """Return confirmed swing pivots only.

    A pivot is not available until `right` candles exist after it. This keeps the
    live/backtest feature deterministic and avoids using an unconfirmed last bar.
    """
    n = len(candles)
    if n < left + right + 3:
        return []
    start = max(left, n - lookback)
    end = n - right
    pivots: list[dict[str, Any]] = []
    for i in range(start, end):
        c = candles[i]
        left_slice = candles[i - left:i]
        right_slice = candles[i + 1:i + right + 1]
        if c["high"] > max(x["high"] for x in left_slice) and c["high"] >= max(x["high"] for x in right_slice):
            pivots.append({"type": "HIGH", "price": float(c["high"]), "time": int(c["time"]), "index": i})
        if c["low"] < min(x["low"] for x in left_slice) and c["low"] <= min(x["low"] for x in right_slice):
            pivots.append({"type": "LOW", "price": float(c["low"]), "time": int(c["time"]), "index": i})
    return sorted(pivots, key=lambda x: (x["index"], x["type"]))


def _pivot_state(pivots: list[dict[str, Any]]) -> str:
    highs = [p for p in pivots if p["type"] == "HIGH"]
    lows = [p for p in pivots if p["type"] == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    higher_high = highs[-1]["price"] > highs[-2]["price"]
    higher_low = lows[-1]["price"] > lows[-2]["price"]
    lower_high = highs[-1]["price"] < highs[-2]["price"]
    lower_low = lows[-1]["price"] < lows[-2]["price"]
    if higher_high and higher_low:
        return "BULLISH"
    if lower_high and lower_low:
        return "BEARISH"
    return "RANGE"


def market_structure(candles: list[dict[str, float]]) -> dict[str, Any]:
    pivots = confirmed_pivots(candles)
    highs = [p for p in pivots if p["type"] == "HIGH"]
    lows = [p for p in pivots if p["type"] == "LOW"]
    state = _pivot_state(pivots)
    latest_high = highs[-1] if highs else None
    latest_low = lows[-1] if lows else None

    events: list[dict[str, Any]] = []
    # Search only recent confirmed pivots; a break event is valid only when the
    # pivot had already been confirmable before the crossing candle.
    for p in pivots[-14:]:
        first_j = max(1, p["index"] + 3)
        for j in range(first_j, len(candles)):
            prev_close = float(candles[j - 1]["close"])
            close = float(candles[j]["close"])
            crossed_up = p["type"] == "HIGH" and prev_close <= p["price"] < close
            crossed_down = p["type"] == "LOW" and prev_close >= p["price"] > close
            if not (crossed_up or crossed_down):
                continue
            known_before = [q for q in pivots if q["index"] + 2 < j]
            pre_state = _pivot_state(known_before)
            if crossed_up:
                kind = "CHOCH_UP" if pre_state == "BEARISH" else "BOS_UP"
                direction = "BULLISH"
            else:
                kind = "CHOCH_DOWN" if pre_state == "BULLISH" else "BOS_DOWN"
                direction = "BEARISH"
            events.append({
                "kind": kind,
                "direction": direction,
                "level": round(float(p["price"]), 2),
                "time": int(candles[j]["time"]),
                "bar_index": j,
                "age_bars": len(candles) - 1 - j,
            })
            break

    recent_event = max(events, key=lambda x: x["bar_index"]) if events else None
    if recent_event and recent_event["age_bars"] > 24:
        recent_event = None

    return {
        "state": state,
        "swing_high": round(float(latest_high["price"]), 2) if latest_high else None,
        "swing_high_time": int(latest_high["time"]) if latest_high else None,
        "swing_low": round(float(latest_low["price"]), 2) if latest_low else None,
        "swing_low_time": int(latest_low["time"]) if latest_low else None,
        "event": recent_event,
        "pivot_count": len(pivots),
    }


def active_fvgs(candles: list[dict[str, float]], lookback: int = 120, limit: int = 4) -> list[dict[str, Any]]:
    """Detect simple 3-candle fair-value gaps and return unfilled zones."""
    if len(candles) < 3:
        return []
    start = max(2, len(candles) - lookback)
    zones: list[dict[str, Any]] = []
    for i in range(start, len(candles)):
        left = candles[i - 2]
        right = candles[i]
        zone = None
        if float(right["low"]) > float(left["high"]):
            zone = {
                "kind": "BULLISH",
                "lower": float(left["high"]),
                "upper": float(right["low"]),
                "time": int(right["time"]),
                "index": i,
            }
            # Bullish FVG is considered fully filled once price trades through
            # its lower boundary after formation.
            zone["filled"] = any(float(c["low"]) <= zone["lower"] for c in candles[i + 1:])
        elif float(right["high"]) < float(left["low"]):
            zone = {
                "kind": "BEARISH",
                "lower": float(right["high"]),
                "upper": float(left["low"]),
                "time": int(right["time"]),
                "index": i,
            }
            zone["filled"] = any(float(c["high"]) >= zone["upper"] for c in candles[i + 1:])
        if zone and not zone["filled"]:
            close = float(candles[-1]["close"])
            mid = (zone["lower"] + zone["upper"]) / 2
            zone["lower"] = round(zone["lower"], 2)
            zone["upper"] = round(zone["upper"], 2)
            zone["distance_pct"] = round(abs(close - mid) / close * 100, 3) if close else 0.0
            zones.append(zone)
    zones.sort(key=lambda z: (z["distance_pct"], -z["index"]))
    return zones[:limit]


def heuristic_order_block(candles: list[dict[str, float]], ms: dict[str, Any]) -> dict[str, Any] | None:
    """Return the last opposite candle before the latest BOS/CHoCH.

    This is deliberately labelled heuristic. It is a deterministic research
    feature, not a claim that every returned zone is an institutional order block.
    """
    event = ms.get("event")
    if not event:
        return None
    event_time = int(event["time"])
    event_index = next((i for i, c in enumerate(candles) if int(c["time"]) == event_time), None)
    if event_index is None:
        return None
    start = max(0, event_index - 12)
    direction = event["direction"]
    for i in range(event_index - 1, start - 1, -1):
        c = candles[i]
        bearish_candle = float(c["close"]) < float(c["open"])
        bullish_candle = float(c["close"]) > float(c["open"])
        if (direction == "BULLISH" and bearish_candle) or (direction == "BEARISH" and bullish_candle):
            return {
                "kind": direction,
                "lower": round(float(c["low"]), 2),
                "upper": round(float(c["high"]), 2),
                "time": int(c["time"]),
                "source_event": event["kind"],
                "heuristic": True,
            }
    return None


def structure(candles: list[dict[str, float]]) -> str:
    # Prefer confirmed swing structure. Fall back to the older rolling-range
    # method when not enough confirmed pivots exist yet.
    ms = market_structure(candles)
    if ms["state"] != "NEUTRAL":
        return ms["state"]
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
    m, msig, mh = macd(closes)
    a = atr(candles, 14)
    close = closes[-1]
    prev_vols = vols[-21:-1]
    vol_avg = fmean(prev_vols) if prev_vols else max(vols[-1], 1e-9)
    vol_ratio = vols[-1] / vol_avg if vol_avg else 1.0

    recent = candles[-30:]
    support = min(c["low"] for c in recent)
    resistance = max(c["high"] for c in recent)
    market = market_structure(candles)
    st = market["state"] if market["state"] != "NEUTRAL" else structure(candles)
    fvgs = active_fvgs(candles)
    ob = heuristic_order_block(candles, market)

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
        "macd_signal": msig,
        "macd_hist": mh,
        "atr14": a,
        "vwap20": rolling_vwap(candles, 20),
        "volume_ratio": vol_ratio,
        "support": support,
        "resistance": resistance,
        "structure": st,
        "trend": trend,
        "volatility_pct": (a / close * 100) if close else 0.0,
        "swing_high": market["swing_high"],
        "swing_high_time": market["swing_high_time"],
        "swing_low": market["swing_low"],
        "swing_low_time": market["swing_low_time"],
        "structure_event": market["event"],
        "fvg_zones": fvgs,
        "order_block": ob,
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

    event = s.get("structure_event") or {}
    kind = event.get("kind")
    if kind == "BOS_UP":
        score += 0.9
    elif kind == "CHOCH_UP":
        score += 0.65
    elif kind == "BOS_DOWN":
        score -= 0.9
    elif kind == "CHOCH_DOWN":
        score -= 0.65

    ob = s.get("order_block") or {}
    if ob.get("kind") == "BULLISH":
        score += 0.25
    elif ob.get("kind") == "BEARISH":
        score -= 0.25

    # Only a small contribution from nearby, still-active FVGs. This keeps
    # market-structure features contextual rather than letting one zone dominate.
    for zone in (s.get("fvg_zones") or [])[:2]:
        if float(zone.get("distance_pct", 99)) > 1.5:
            continue
        score += 0.15 if zone.get("kind") == "BULLISH" else -0.15

    return max(-1.0, min(1.0, score / 8.0))

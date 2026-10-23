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
            out.append(float(c["high"]) - float(c["low"]))
        else:
            prev = float(candles[i - 1]["close"])
            out.append(max(float(c["high"]) - float(c["low"]), abs(float(c["high"]) - prev), abs(float(c["low"]) - prev)))
    return out


def atr(candles: list[dict[str, float]], period: int = 14) -> float:
    trs = true_ranges(candles)
    return fmean(trs[-period:]) if trs else 0.0


def macd(values: list[float]) -> tuple[float, float, float]:
    if len(values) < 35:
        return 0.0, 0.0, 0.0
    e12 = ema(values, 12)
    e26 = ema(values, 26)
    line = [a - b for a, b in zip(e12, e26)]
    sig = ema(line, 9)
    return line[-1], sig[-1], line[-1] - sig[-1]


def rolling_vwap(candles: list[dict[str, float]], period: int = 20) -> float:
    subset = candles[-period:]
    den = sum(float(c["volume"]) for c in subset)
    if den <= 0:
        return float(subset[-1]["close"]) if subset else 0.0
    num = sum(((float(c["high"]) + float(c["low"]) + float(c["close"])) / 3) * float(c["volume"]) for c in subset)
    return num / den


def confirmed_pivots(candles: list[dict[str, float]], left: int = 2, right: int = 2, lookback: int = 200) -> list[dict[str, Any]]:
    """Confirmed pivots only; the right-side candles must already exist."""
    n = len(candles)
    if n < left + right + 1:
        return []
    start = max(left, n - lookback)
    end = n - right
    pivots: list[dict[str, Any]] = []
    for i in range(start, end):
        c = candles[i]
        ls = candles[i - left:i]
        rs = candles[i + 1:i + right + 1]
        high = float(c["high"])
        low = float(c["low"])
        if high > max(float(x["high"]) for x in ls) and high >= max(float(x["high"]) for x in rs):
            pivots.append({"type": "HIGH", "price": high, "time": int(c["time"]), "index": i})
        if low < min(float(x["low"]) for x in ls) and low <= min(float(x["low"]) for x in rs):
            pivots.append({"type": "LOW", "price": low, "time": int(c["time"]), "index": i})
    return sorted(pivots, key=lambda x: (x["index"], x["type"]))


def _pivot_state(pivots: list[dict[str, Any]]) -> str:
    highs = [p for p in pivots if p["type"] == "HIGH"]
    lows = [p for p in pivots if p["type"] == "LOW"]
    if len(highs) < 2 or len(lows) < 2:
        return "NEUTRAL"
    hh = highs[-1]["price"] > highs[-2]["price"]
    hl = lows[-1]["price"] > lows[-2]["price"]
    lh = highs[-1]["price"] < highs[-2]["price"]
    ll = lows[-1]["price"] < lows[-2]["price"]
    if hh and hl:
        return "BULLISH"
    if lh and ll:
        return "BEARISH"
    return "RANGE"


def _rolling_structure(candles: list[dict[str, float]]) -> str:
    if len(candles) < 40:
        return "NEUTRAL"
    older = candles[-40:-20]
    recent = candles[-20:]
    oh, ol = max(float(c["high"]) for c in older), min(float(c["low"]) for c in older)
    rh, rl = max(float(c["high"]) for c in recent), min(float(c["low"]) for c in recent)
    if rh > oh and rl > ol:
        return "BULLISH"
    if rh < oh and rl < ol:
        return "BEARISH"
    return "RANGE"


def market_structure(candles: list[dict[str, float]], pivots: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    pivots = pivots if pivots is not None else confirmed_pivots(candles)
    highs = [p for p in pivots if p["type"] == "HIGH"]
    lows = [p for p in pivots if p["type"] == "LOW"]
    state = _pivot_state(pivots)
    latest_high = highs[-1] if highs else None
    latest_low = lows[-1] if lows else None

    candidates = sorted(highs[-3:] + lows[-3:], key=lambda x: x["index"])
    events: list[dict[str, Any]] = []
    for p in candidates:
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
                kind, direction = ("CHOCH_UP" if pre_state == "BEARISH" else "BOS_UP"), "BULLISH"
            else:
                kind, direction = ("CHOCH_DOWN" if pre_state == "BULLISH" else "BOS_DOWN"), "BEARISH"
            events.append({
                "kind": kind, "direction": direction, "level": round(float(p["price"]), 2),
                "time": int(candles[j]["time"]), "bar_index": j,
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
    n = len(candles)
    if n < 3:
        return []
    start = max(2, n - lookback)
    suffix_min_low = [float("inf")] * (n + 1)
    suffix_max_high = [float("-inf")] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix_min_low[i] = min(float(candles[i]["low"]), suffix_min_low[i + 1])
        suffix_max_high[i] = max(float(candles[i]["high"]), suffix_max_high[i + 1])

    close = float(candles[-1]["close"])
    zones: list[dict[str, Any]] = []
    for i in range(start, n):
        left, right = candles[i - 2], candles[i]
        zone: dict[str, Any] | None = None
        if float(right["low"]) > float(left["high"]):
            lower, upper = float(left["high"]), float(right["low"])
            if suffix_min_low[i + 1] > lower:
                zone = {"kind": "BULLISH", "lower": lower, "upper": upper, "time": int(right["time"]), "index": i}
        elif float(right["high"]) < float(left["low"]):
            lower, upper = float(right["high"]), float(left["low"])
            if suffix_max_high[i + 1] < upper:
                zone = {"kind": "BEARISH", "lower": lower, "upper": upper, "time": int(right["time"]), "index": i}
        if zone:
            mid = (zone["lower"] + zone["upper"]) / 2
            zone["lower"] = round(zone["lower"], 2)
            zone["upper"] = round(zone["upper"], 2)
            zone["distance_pct"] = round(abs(close - mid) / close * 100, 3) if close else 0.0
            zones.append(zone)
    zones.sort(key=lambda z: (z["distance_pct"], -z["index"]))
    return zones[:limit]


def heuristic_order_block(candles: list[dict[str, float]], ms: dict[str, Any]) -> dict[str, Any] | None:
    event = ms.get("event")
    if not event:
        return None
    event_index = next((i for i, c in enumerate(candles) if int(c["time"]) == int(event["time"])), None)
    if event_index is None:
        return None
    direction = event["direction"]
    for i in range(event_index - 1, max(-1, event_index - 13), -1):
        c = candles[i]
        bearish = float(c["close"]) < float(c["open"])
        bullish = float(c["close"]) > float(c["open"])
        if (direction == "BULLISH" and bearish) or (direction == "BEARISH" and bullish):
            return {
                "kind": direction, "lower": round(float(c["low"]), 2), "upper": round(float(c["high"]), 2),
                "time": int(c["time"]), "source_event": event["kind"], "heuristic": True,
            }
    return None


def _cluster_pivots(items: list[dict[str, Any]], tolerance: float) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for p in items:
        best = None
        best_dist = float("inf")
        for c in clusters:
            dist = abs(float(p["price"]) - float(c["level"]))
            if dist <= tolerance and dist < best_dist:
                best, best_dist = c, dist
        if best is None:
            clusters.append({"prices": [float(p["price"])], "times": [int(p["time"])], "level": float(p["price"])})
        else:
            best["prices"].append(float(p["price"]))
            best["times"].append(int(p["time"]))
            best["level"] = fmean(best["prices"])
    return clusters


def liquidity_map(candles: list[dict[str, float]], pivots: list[dict[str, Any]], atr_value: float) -> dict[str, Any]:
    if not candles:
        return {"equal_highs": [], "equal_lows": [], "sweep": None}
    close = float(candles[-1]["close"])
    tolerance = max(atr_value * 0.22, close * 0.0010)
    highs = _cluster_pivots([p for p in pivots[-30:] if p["type"] == "HIGH"], tolerance)
    lows = _cluster_pivots([p for p in pivots[-30:] if p["type"] == "LOW"], tolerance)

    def pack(groups: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
        out = []
        for g in groups:
            if len(g["prices"]) < 2:
                continue
            level = float(g["level"])
            out.append({
                "kind": kind, "level": round(level, 2), "touches": len(g["prices"]),
                "lower": round(level - tolerance * 0.35, 2), "upper": round(level + tolerance * 0.35, 2),
                "last_time": max(g["times"]), "distance_pct": round(abs(close - level) / close * 100, 3) if close else 0.0,
            })
        out.sort(key=lambda x: (x["distance_pct"], -x["touches"]))
        return out[:3]

    equal_highs = pack(highs, "EQUAL_HIGH")
    equal_lows = pack(lows, "EQUAL_LOW")
    sweep = None
    # Sweep must occur after the liquidity level already existed; checking only
    # recent bars keeps the event actionable and avoids stale historical sweeps.
    for c in candles[-5:]:
        for z in equal_highs:
            if int(c["time"]) <= int(z["last_time"]):
                continue
            if float(c["high"]) > float(z["upper"]) and float(c["close"]) < float(z["level"]):
                sweep = {"kind": "SWEEP_HIGH", "direction": "BEARISH", "level": z["level"], "time": int(c["time"])}
        for z in equal_lows:
            if int(c["time"]) <= int(z["last_time"]):
                continue
            if float(c["low"]) < float(z["lower"]) and float(c["close"]) > float(z["level"]):
                sweep = {"kind": "SWEEP_LOW", "direction": "BULLISH", "level": z["level"], "time": int(c["time"])}
    return {"equal_highs": equal_highs, "equal_lows": equal_lows, "sweep": sweep, "tolerance": round(tolerance, 2)}


def trend_channel(candles: list[dict[str, float]], pivots: list[dict[str, Any]]) -> dict[str, Any] | None:
    highs = [p for p in pivots if p["type"] == "HIGH"][-2:]
    lows = [p for p in pivots if p["type"] == "LOW"][-2:]
    if len(highs) < 2 or len(lows) < 2 or not candles:
        return None
    now = int(candles[-1]["time"])

    def projected(pair: list[dict[str, Any]]) -> dict[str, Any]:
        a, b = pair
        dt = max(1, int(b["time"]) - int(a["time"]))
        slope = (float(b["price"]) - float(a["price"])) / dt
        end_price = float(b["price"]) + slope * max(0, now - int(b["time"]))
        return {
            "start_time": int(a["time"]), "start_price": round(float(a["price"]), 2),
            "pivot_time": int(b["time"]), "pivot_price": round(float(b["price"]), 2),
            "end_time": now, "end_price": round(end_price, 2), "slope": slope,
        }

    upper, lower = projected(highs), projected(lows)
    us, ls = float(upper["slope"]), float(lower["slope"])
    scale = max(abs(us), abs(ls), 1e-12)
    parallel = abs(us - ls) / scale < 0.65
    if us > 0 and ls > 0:
        kind = "ASCENDING_CHANNEL" if parallel else "BULLISH_EXPANSION"
    elif us < 0 and ls < 0:
        kind = "DESCENDING_CHANNEL" if parallel else "BEARISH_EXPANSION"
    elif us < 0 < ls:
        kind = "CONVERGING"
    elif ls < 0 < us:
        kind = "DIVERGING"
    else:
        kind = "MIXED"
    return {"kind": kind, "upper": upper, "lower": lower, "parallel": parallel}


def structure(candles: list[dict[str, float]]) -> str:
    pivots = confirmed_pivots(candles)
    ms = market_structure(candles, pivots)
    return ms["state"] if ms["state"] != "NEUTRAL" else _rolling_structure(candles)


def snapshot(candles: list[dict[str, float]]) -> dict[str, Any]:
    if len(candles) < 30:
        return {}
    closes = [float(c["close"]) for c in candles]
    vols = [float(c["volume"]) for c in candles]
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
    support = min(float(c["low"]) for c in recent)
    resistance = max(float(c["high"]) for c in recent)

    pivots = confirmed_pivots(candles)
    market = market_structure(candles, pivots)
    st = market["state"] if market["state"] != "NEUTRAL" else _rolling_structure(candles)
    fvgs = active_fvgs(candles)
    ob = heuristic_order_block(candles, market)
    liquidity = liquidity_map(candles, pivots, a)
    channel = trend_channel(candles, pivots)

    if close > e20 > e50 and e50 >= e200 * 0.995:
        trend = "BULLISH"
    elif close < e20 < e50 and e50 <= e200 * 1.005:
        trend = "BEARISH"
    else:
        trend = "MIXED"

    return {
        "close": close, "ema20": e20, "ema50": e50, "ema200": e200,
        "rsi14": rsi(closes, 14), "macd": m, "macd_signal": msig, "macd_hist": mh,
        "atr14": a, "vwap20": rolling_vwap(candles, 20), "volume_ratio": vol_ratio,
        "support": support, "resistance": resistance, "structure": st, "trend": trend,
        "volatility_pct": (a / close * 100) if close else 0.0,
        "swing_high": market["swing_high"], "swing_high_time": market["swing_high_time"],
        "swing_low": market["swing_low"], "swing_low_time": market["swing_low_time"],
        "structure_event": market["event"], "fvg_zones": fvgs, "order_block": ob,
        "liquidity": liquidity, "trend_channel": channel,
    }


def vote(s: dict[str, Any]) -> float:
    if not s:
        return 0.0
    score = 0.0
    if s["trend"] == "BULLISH": score += 2.0
    elif s["trend"] == "BEARISH": score -= 2.0
    score += 0.9 if s["close"] > s["ema20"] else -0.9
    score += 0.7 if s["ema20"] > s["ema50"] else -0.7
    score += 0.5 if s["close"] > s["vwap20"] else -0.5

    r = s["rsi14"]
    if 52 <= r <= 70: score += 0.6
    elif 30 <= r <= 48: score -= 0.6
    elif r > 78: score -= 0.25
    elif r < 22: score += 0.25
    score += 0.8 if s["macd_hist"] > 0 else (-0.8 if s["macd_hist"] < 0 else 0.0)
    if s["structure"] == "BULLISH": score += 1.0
    elif s["structure"] == "BEARISH": score -= 1.0

    kind = (s.get("structure_event") or {}).get("kind")
    if kind == "BOS_UP": score += 0.9
    elif kind == "CHOCH_UP": score += 0.65
    elif kind == "BOS_DOWN": score -= 0.9
    elif kind == "CHOCH_DOWN": score -= 0.65

    ob = s.get("order_block") or {}
    if ob.get("kind") == "BULLISH": score += 0.25
    elif ob.get("kind") == "BEARISH": score -= 0.25
    for zone in (s.get("fvg_zones") or [])[:2]:
        if float(zone.get("distance_pct", 99)) <= 1.5:
            score += 0.15 if zone.get("kind") == "BULLISH" else -0.15

    sweep = ((s.get("liquidity") or {}).get("sweep") or {})
    if sweep.get("direction") == "BULLISH": score += 0.75
    elif sweep.get("direction") == "BEARISH": score -= 0.75

    channel_kind = (s.get("trend_channel") or {}).get("kind")
    if channel_kind in ("ASCENDING_CHANNEL", "BULLISH_EXPANSION"): score += 0.30
    elif channel_kind in ("DESCENDING_CHANNEL", "BEARISH_EXPANSION"): score -= 0.30

    return max(-1.0, min(1.0, score / 9.0))

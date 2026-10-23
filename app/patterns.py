from __future__ import annotations

from typing import Any


def _body(c: dict[str, float]) -> float:
    return abs(float(c["close"]) - float(c["open"]))


def _range(c: dict[str, float]) -> float:
    return max(1e-12, float(c["high"]) - float(c["low"]))


def _bullish(c: dict[str, float]) -> bool:
    return float(c["close"]) > float(c["open"])


def _bearish(c: dict[str, float]) -> bool:
    return float(c["close"]) < float(c["open"])


def candlestick_patterns(candles: list[dict[str, float]], atr_value: float) -> list[dict[str, Any]]:
    """Detect recent confirmed candle patterns only.

    The function consumes closed candles. Returned patterns are context features,
    not standalone trade signals. We scan only the last three completed bars so
    old candle shapes do not keep influencing the live decision indefinitely.
    """
    if len(candles) < 4:
        return []
    out: list[dict[str, Any]] = []
    eps = max(float(atr_value) * 0.06, float(candles[-1]["close"]) * 0.0002)

    for idx in range(max(1, len(candles) - 3), len(candles)):
        c = candles[idx]
        p = candles[idx - 1]
        body = _body(c)
        rng = _range(c)
        upper = float(c["high"]) - max(float(c["open"]), float(c["close"]))
        lower = min(float(c["open"]), float(c["close"])) - float(c["low"])
        body_ratio = body / rng

        if body_ratio <= 0.10:
            out.append({"name": "DOJI", "direction": "NEUTRAL", "strength": 0.25, "time": int(c["time"]), "price": float(c["close"])})

        if lower >= max(body * 2.2, eps) and upper <= max(body * 0.7, eps * 0.45) and body_ratio <= 0.45:
            out.append({"name": "HAMMER", "direction": "BULLISH", "strength": 0.55, "time": int(c["time"]), "price": float(c["close"])})
        if upper >= max(body * 2.2, eps) and lower <= max(body * 0.7, eps * 0.45) and body_ratio <= 0.45:
            out.append({"name": "SHOOTING_STAR", "direction": "BEARISH", "strength": 0.55, "time": int(c["time"]), "price": float(c["close"])})

        if _bearish(p) and _bullish(c) and float(c["open"]) <= float(p["close"]) and float(c["close"]) >= float(p["open"]) and body > _body(p) * 1.05:
            out.append({"name": "BULLISH_ENGULFING", "direction": "BULLISH", "strength": 0.72, "time": int(c["time"]), "price": float(c["close"])})
        if _bullish(p) and _bearish(c) and float(c["open"]) >= float(p["close"]) and float(c["close"]) <= float(p["open"]) and body > _body(p) * 1.05:
            out.append({"name": "BEARISH_ENGULFING", "direction": "BEARISH", "strength": 0.72, "time": int(c["time"]), "price": float(c["close"])})

        if float(c["high"]) < float(p["high"]) and float(c["low"]) > float(p["low"]):
            direction = "BULLISH" if _bullish(c) else ("BEARISH" if _bearish(c) else "NEUTRAL")
            out.append({"name": "INSIDE_BAR", "direction": direction, "strength": 0.35, "time": int(c["time"]), "price": float(c["close"])})

    # Three-candle reversal patterns require all three bars to be complete.
    a, b, c = candles[-3], candles[-2], candles[-1]
    big_a = _body(a) >= max(atr_value * 0.45, _range(a) * 0.55)
    small_b = _body(b) <= max(atr_value * 0.25, _range(b) * 0.35)
    midpoint_a = (float(a["open"]) + float(a["close"])) / 2
    if _bearish(a) and big_a and small_b and _bullish(c) and float(c["close"]) > midpoint_a:
        out.append({"name": "MORNING_STAR", "direction": "BULLISH", "strength": 0.78, "time": int(c["time"]), "price": float(c["close"])})
    if _bullish(a) and big_a and small_b and _bearish(c) and float(c["close"]) < midpoint_a:
        out.append({"name": "EVENING_STAR", "direction": "BEARISH", "strength": 0.78, "time": int(c["time"]), "price": float(c["close"])})

    # Prefer stronger and newer patterns, remove duplicates from overlapping rules.
    dedup: dict[tuple[str, int], dict[str, Any]] = {}
    for p in out:
        dedup[(p["name"], p["time"])] = p
    result = list(dedup.values())
    result.sort(key=lambda x: (x["time"], x["strength"]), reverse=True)
    return result[:6]


def classical_patterns(candles: list[dict[str, float]], pivots: list[dict[str, Any]], atr_value: float) -> list[dict[str, Any]]:
    """Detect simple pivot-confirmed classical patterns without lookahead."""
    if len(candles) < 10 or len(pivots) < 4:
        return []
    close = float(candles[-1]["close"])
    tolerance = max(float(atr_value) * 0.35, close * 0.002)
    highs = [p for p in pivots if p["type"] == "HIGH"]
    lows = [p for p in pivots if p["type"] == "LOW"]
    out: list[dict[str, Any]] = []

    # Double top/bottom: two confirmed pivots near the same level with an
    # intervening opposite swing. We do not call it a breakout until price
    # actually closes through the neckline.
    if len(highs) >= 2:
        h1, h2 = highs[-2], highs[-1]
        between_lows = [p for p in lows if h1["index"] < p["index"] < h2["index"]]
        if between_lows and abs(float(h2["price"]) - float(h1["price"])) <= tolerance:
            neckline = min(float(p["price"]) for p in between_lows)
            confirmed = close < neckline
            out.append({
                "name": "DOUBLE_TOP", "direction": "BEARISH", "strength": 0.78 if confirmed else 0.48,
                "confirmed": confirmed, "level": round((float(h1["price"]) + float(h2["price"])) / 2, 2),
                "neckline": round(neckline, 2), "time": int(h2["time"]),
            })
    if len(lows) >= 2:
        l1, l2 = lows[-2], lows[-1]
        between_highs = [p for p in highs if l1["index"] < p["index"] < l2["index"]]
        if between_highs and abs(float(l2["price"]) - float(l1["price"])) <= tolerance:
            neckline = max(float(p["price"]) for p in between_highs)
            confirmed = close > neckline
            out.append({
                "name": "DOUBLE_BOTTOM", "direction": "BULLISH", "strength": 0.78 if confirmed else 0.48,
                "confirmed": confirmed, "level": round((float(l1["price"]) + float(l2["price"])) / 2, 2),
                "neckline": round(neckline, 2), "time": int(l2["time"]),
            })

    # Triangle classification from the latest three highs/lows. Slopes are
    # estimated in price-per-second; only already-confirmed pivots are used.
    if len(highs) >= 3 and len(lows) >= 3:
        hs, ls = highs[-3:], lows[-3:]

        def slope(points: list[dict[str, Any]]) -> float:
            dt = max(1, int(points[-1]["time"]) - int(points[0]["time"]))
            return (float(points[-1]["price"]) - float(points[0]["price"])) / dt

        sh, sl = slope(hs), slope(ls)
        flat_eps = max(tolerance / max(1, int(hs[-1]["time"]) - int(hs[0]["time"])), 1e-12)
        if sh < -flat_eps and sl > flat_eps:
            name, direction, strength = "SYMMETRICAL_TRIANGLE", "NEUTRAL", 0.52
        elif abs(sh) <= flat_eps and sl > flat_eps:
            name, direction, strength = "ASCENDING_TRIANGLE", "BULLISH", 0.62
        elif sh < -flat_eps and abs(sl) <= flat_eps:
            name, direction, strength = "DESCENDING_TRIANGLE", "BEARISH", 0.62
        else:
            name = None
        if name:
            out.append({
                "name": name, "direction": direction, "strength": strength, "confirmed": False,
                "upper_level": round(float(hs[-1]["price"]), 2), "lower_level": round(float(ls[-1]["price"]), 2),
                "time": max(int(hs[-1]["time"]), int(ls[-1]["time"])),
            })

    out.sort(key=lambda x: (x.get("confirmed", False), x["strength"], x["time"]), reverse=True)
    return out[:4]


def pattern_bias(candle_patterns: list[dict[str, Any]], chart_patterns: list[dict[str, Any]]) -> float:
    """Small bounded directional contribution; patterns cannot dominate trend."""
    score = 0.0
    for p in candle_patterns[:3]:
        direction = p.get("direction")
        strength = float(p.get("strength", 0))
        if direction == "BULLISH": score += strength * 0.22
        elif direction == "BEARISH": score -= strength * 0.22
    for p in chart_patterns[:2]:
        direction = p.get("direction")
        strength = float(p.get("strength", 0))
        factor = 0.42 if p.get("confirmed") else 0.24
        if direction == "BULLISH": score += strength * factor
        elif direction == "BEARISH": score -= strength * factor
    return max(-0.65, min(0.65, score))

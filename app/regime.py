from __future__ import annotations

from typing import Any


def _dir(layer: dict[str, Any]) -> str:
    return str(layer.get("direction", "NEUTRAL"))


def classify_market_regime(snapshots: dict[str, dict[str, Any]], layers: dict[str, Any]) -> dict[str, Any]:
    """Classify market state from confirmed multi-timeframe context."""
    micro = _dir(layers.get("MICRO", {}))
    intraday = _dir(layers.get("INTRADAY", {}))
    swing = _dir(layers.get("SWING", {}))
    macro = _dir(layers.get("MACRO", {}))

    s1h = snapshots.get("1h", {})
    s4h = snapshots.get("4h", {})
    s1d = snapshots.get("1d", {})
    event1h = (s1h.get("structure_event") or {}).get("kind")
    event4h = (s4h.get("structure_event") or {}).get("kind")
    volume1h = float(s1h.get("volume_ratio", 1.0) or 1.0)

    breakout_up = (event1h in ("BOS_UP", "CHOCH_UP") or event4h == "BOS_UP") and volume1h >= 1.15 and macro != "BEARISH"
    breakout_down = (event1h in ("BOS_DOWN", "CHOCH_DOWN") or event4h == "BOS_DOWN") and volume1h >= 1.15 and macro != "BULLISH"

    if breakout_up:
        regime = "BREAKOUT_UP"
    elif breakout_down:
        regime = "BREAKOUT_DOWN"
    elif macro == "BULLISH" and swing == "BULLISH" and intraday == "BEARISH":
        regime = "PULLBACK_UPTREND"
    elif macro == "BEARISH" and swing == "BEARISH" and intraday == "BULLISH":
        regime = "PULLBACK_DOWNTREND"
    elif macro == "BULLISH" and swing == "BULLISH":
        regime = "TREND_UP"
    elif macro == "BEARISH" and swing == "BEARISH":
        regime = "TREND_DOWN"
    else:
        range_votes = sum(1 for tf in ("30m", "1h", "4h") if snapshots.get(tf, {}).get("structure") == "RANGE")
        regime = "RANGE" if range_votes >= 2 or (macro == "NEUTRAL" and swing == "NEUTRAL") else "TRANSITION"

    vol1h = float(s1h.get("volatility_pct", 0.0) or 0.0)
    vol4h = float(s4h.get("volatility_pct", 0.0) or 0.0)
    if vol1h >= 1.1 or vol4h >= 2.2:
        volatility = "HIGH"
    elif vol1h <= 0.35 and vol4h <= 0.9:
        volatility = "LOW"
    else:
        volatility = "NORMAL"

    direction = "BULLISH" if regime in ("BREAKOUT_UP", "PULLBACK_UPTREND", "TREND_UP") else ("BEARISH" if regime in ("BREAKOUT_DOWN", "PULLBACK_DOWNTREND", "TREND_DOWN") else "NEUTRAL")
    return {
        "regime": regime,
        "direction": direction,
        "volatility": volatility,
        "layers": {"micro": micro, "intraday": intraday, "swing": swing, "macro": macro},
        "evidence": {
            "event_1h": event1h, "event_4h": event4h,
            "volume_ratio_1h": round(volume1h, 3),
            "volatility_1h": round(vol1h, 3), "volatility_4h": round(vol4h, 3),
            "daily_structure": s1d.get("structure"),
        },
    }


def feature_vector(
    snapshots: dict[str, dict[str, Any]],
    layers: dict[str, Any],
    master: dict[str, Any],
    regime: dict[str, Any],
    cycle: dict[str, Any] | None = None,
    network: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Auditable learning vector containing summaries + hidden background pool."""
    timeframes: dict[str, Any] = {}
    background: dict[str, dict[str, float]] = {}
    total_features = 0
    for tf, s in snapshots.items():
        if not s:
            continue
        summary = s.get("feature_summary") or {}
        timeframes[tf] = {
            "trend": s.get("trend"), "structure": s.get("structure"),
            "rsi": round(float(s.get("rsi14", 0.0)), 3),
            "macd_hist": round(float(s.get("macd_hist", 0.0)), 6),
            "volatility_pct": round(float(s.get("volatility_pct", 0.0)), 4),
            "volume_ratio": round(float(s.get("volume_ratio", 0.0)), 4),
            "pattern_bias": round(float(s.get("pattern_bias", 0.0)), 4),
            "feature_bias": round(float(summary.get("bias", 0.0)), 4),
            "feature_count": int(summary.get("count", 0)),
            "structure_event": (s.get("structure_event") or {}).get("kind"),
            "liquidity_sweep": ((s.get("liquidity") or {}).get("sweep") or {}).get("direction"),
            "channel": (s.get("trend_channel") or {}).get("kind"),
            "sample_count": int(s.get("sample_count", 0) or 0),
        }
        pool = s.get("_feature_pool") or {}
        if pool:
            background[tf] = pool
            total_features += len(pool)

    winner = master.get("winner") or {}
    return {
        "schema": "learning_vector_v3",
        "regime": regime,
        "layers": layers,
        "cycle_models": cycle or {},
        "network_intelligence": network or {},
        "winner": {
            "brain": winner.get("brain"), "direction": winner.get("direction"),
            "confidence": winner.get("confidence"), "safety": winner.get("safety_score"),
            "profit": winner.get("profit_score"), "final": winner.get("final_score"),
            "rr": winner.get("rr"), "ev_pct": winner.get("ev_pct"),
            "macro_direction": winner.get("macro_direction"), "pattern_bias": winner.get("pattern_bias"),
            "feature_bias": winner.get("feature_bias"), "feature_count": winner.get("feature_count"),
        },
        "timeframes": timeframes,
        "background_features": background,
        "background_feature_count": total_features,
    }

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import fmean
from typing import Any

GENESIS_BLOCK_TS = int(datetime(2009, 1, 3, tzinfo=timezone.utc).timestamp())
HPR_GENESIS_TS = int(datetime(2009, 1, 9, tzinfo=timezone.utc).timestamp())


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return fmean(values[-period:])


def _days_since(ts: int, origin: int) -> float:
    return max(1.0, (ts - origin) / 86400.0)


def power_law_fair_price(ts: int) -> float:
    """Bitbo-published long-term power-law regression fair-price formula."""
    days = _days_since(ts, GENESIS_BLOCK_TS)
    return (10 ** -17.016) * (days ** 5.845)


def halving_price_regression(ts: int) -> float:
    """Bitbo-published HPR/Rainbow regression center line."""
    days = _days_since(ts, HPR_GENESIS_TS)
    log10_price = 2.6521 * math.log(days) - 18.163
    return 10 ** log10_price


def cycle_model_context(daily_candles: list[dict[str, Any]]) -> dict[str, Any]:
    """Price-derived long-horizon cycle context.

    These models are context features, not standalone trading signals. On-chain
    models such as MVRV/Puell/Reserve Risk require real on-chain data and are
    intentionally not approximated here.
    """
    if not daily_candles:
        return {"available": False, "models": {}, "bias": 0.0, "strength": 0.0}

    closes = [float(c["close"]) for c in daily_candles]
    price = closes[-1]
    ts = int(daily_candles[-1].get("close_time") or daily_candles[-1]["time"])
    models: dict[str, Any] = {}
    votes: list[float] = []

    fair = power_law_fair_price(ts)
    power_dev = price / fair - 1.0 if fair > 0 else 0.0
    # Undervaluation produces positive long-horizon value bias; overvaluation negative.
    power_vote = max(-1.0, min(1.0, -power_dev / 1.25))
    models["power_law"] = {
        "fair_price": round(fair, 2),
        "deviation_pct": round(power_dev * 100, 2),
        "bias": round(power_vote, 4),
        "source": "public_formula",
    }
    votes.append(power_vote * 0.30)

    hpr = halving_price_regression(ts)
    hpr_dev = price / hpr - 1.0 if hpr > 0 else 0.0
    hpr_vote = max(-1.0, min(1.0, -hpr_dev / 1.10))
    models["hpr_rainbow"] = {
        "fair_price": round(hpr, 2),
        "deviation_pct": round(hpr_dev * 100, 2),
        "bias": round(hpr_vote, 4),
        "source": "public_formula",
    }
    votes.append(hpr_vote * 0.22)

    ma200 = _sma(closes, 200)
    if ma200:
        mayer = price / ma200
        # Around 1 is neutral. Extreme values are contextual, not direct entries.
        mayer_vote = max(-1.0, min(1.0, (1.35 - mayer) / 1.10))
        models["mayer_multiple"] = {
            "value": round(mayer, 4),
            "ma200": round(ma200, 2),
            "bias": round(mayer_vote, 4),
            "source": "price_200dma",
        }
        votes.append(mayer_vote * 0.18)

    ma111 = _sma(closes, 111)
    ma350 = _sma(closes, 350)
    if ma111 and ma350:
        top_line = 2.0 * ma350
        ratio = ma111 / top_line if top_line else 0.0
        # Near/above the cross is a cycle-overextension warning, not a short trigger.
        pi_vote = max(-1.0, min(0.2, (0.82 - ratio) / 0.28))
        models["pi_cycle_top"] = {
            "ma111": round(ma111, 2),
            "ma350_x2": round(top_line, 2),
            "ratio": round(ratio, 4),
            "crossed": bool(ma111 >= top_line),
            "bias": round(pi_vote, 4),
            "source": "111dma_vs_2x350dma",
        }
        votes.append(pi_vote * 0.16)

    ma1458 = _sma(closes, 1458)
    if ma1458:
        multiple = price / ma1458
        four_year_vote = max(-1.0, min(1.0, (2.2 - multiple) / 2.2))
        models["four_year_sma"] = {
            "ma1458": round(ma1458, 2),
            "multiple": round(multiple, 4),
            "bias": round(four_year_vote, 4),
            "source": "1458_day_sma",
        }
        votes.append(four_year_vote * 0.14)

    total_weight = 0.30 + 0.22
    if "mayer_multiple" in models:
        total_weight += 0.18
    if "pi_cycle_top" in models:
        total_weight += 0.16
    if "four_year_sma" in models:
        total_weight += 0.14
    bias = sum(votes) / total_weight if total_weight else 0.0
    strength = min(1.0, abs(bias) * 1.8)

    return {
        "available": True,
        "price": round(price, 2),
        "timestamp": ts,
        "bias": round(max(-1.0, min(1.0, bias)), 4),
        "strength": round(strength, 4),
        "models": models,
        "role": "cycle_valuation_context_only",
        "onchain_pending": ["mvrv", "realized_price", "puell_multiple", "reserve_risk", "sopr", "nupl"],
    }

from __future__ import annotations

import asyncio
import time
from statistics import fmean
from typing import Any

import httpx

FAPI = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
PERIOD = "5m"


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _change_pct(new: float | None, old: float | None) -> float | None:
    if new is None or old in (None, 0):
        return None
    return (new / old - 1.0) * 100.0


def _series_latest(rows: Any, key: str) -> float | None:
    if not isinstance(rows, list) or not rows:
        return None
    return _num(rows[-1].get(key))


def summarize_derivatives(raw: dict[str, Any]) -> dict[str, Any]:
    premium = raw.get("premium") or {}
    funding_rows = raw.get("funding") or []
    oi_now = raw.get("open_interest") or {}
    oi_hist = raw.get("open_interest_hist") or []
    global_ls = raw.get("global_ls") or []
    top_accounts = raw.get("top_accounts") or []
    top_positions = raw.get("top_positions") or []
    taker = raw.get("taker") or []

    mark = _num(premium.get("markPrice"))
    index = _num(premium.get("indexPrice"))
    basis_bps = ((mark / index - 1.0) * 10_000.0) if mark and index else None
    current_funding = _num(premium.get("lastFundingRate"))
    funding_vals = [_num(x.get("fundingRate")) for x in funding_rows if _num(x.get("fundingRate")) is not None]
    avg_funding = fmean(funding_vals) if funding_vals else None

    current_oi = _num(oi_now.get("openInterest"))
    hist_values = []
    for row in oi_hist if isinstance(oi_hist, list) else []:
        value = _num(row.get("sumOpenInterestValue"))
        if value is None:
            value = _num(row.get("sumOpenInterest"))
        if value is not None:
            hist_values.append(value)
    oi_change = _change_pct(hist_values[-1], hist_values[0]) if len(hist_values) >= 2 else None

    global_ratio = _series_latest(global_ls, "longShortRatio")
    top_account_ratio = _series_latest(top_accounts, "longShortRatio")
    top_position_ratio = _series_latest(top_positions, "longShortRatio")

    taker_buy = _series_latest(taker, "buyVol")
    taker_sell = _series_latest(taker, "sellVol")
    if taker_buy is None:
        taker_buy = _series_latest(taker, "takerBuyVol")
    if taker_sell is None:
        taker_sell = _series_latest(taker, "takerSellVol")
    taker_ratio = (taker_buy / taker_sell) if taker_buy is not None and taker_sell not in (None, 0) else _series_latest(taker, "buySellRatio")

    components: dict[str, float] = {}
    # These are descriptive/contrarian research features only; no decision weight yet.
    if current_funding is not None:
        components["funding_crowding"] = max(-1.0, min(1.0, -current_funding / 0.0010))
    if basis_bps is not None:
        components["basis_crowding"] = max(-1.0, min(1.0, -basis_bps / 80.0))
    if global_ratio is not None and global_ratio > 0:
        components["global_ls_contrarian"] = max(-1.0, min(1.0, -(global_ratio - 1.0) / 1.5))
    if top_position_ratio is not None and top_position_ratio > 0:
        components["top_position_contrarian"] = max(-1.0, min(1.0, -(top_position_ratio - 1.0) / 1.5))
    if taker_ratio is not None and taker_ratio > 0:
        components["taker_pressure"] = max(-1.0, min(1.0, (taker_ratio - 1.0) / 0.75))

    shadow_bias = fmean(components.values()) if components else 0.0
    return {
        "available": any(v is not None for v in (mark, current_funding, current_oi, global_ratio, top_position_ratio, taker_ratio)),
        "symbol": SYMBOL,
        "premium": {
            "mark_price": mark,
            "index_price": index,
            "basis_bps": round(basis_bps, 4) if basis_bps is not None else None,
            "current_funding_rate": current_funding,
            "avg_recent_funding_rate": round(avg_funding, 8) if avg_funding is not None else None,
            "next_funding_time": premium.get("nextFundingTime"),
        },
        "open_interest": {
            "current": current_oi,
            "history_change_pct": round(oi_change, 4) if oi_change is not None else None,
        },
        "positioning": {
            "global_long_short_ratio": global_ratio,
            "top_account_long_short_ratio": top_account_ratio,
            "top_position_long_short_ratio": top_position_ratio,
        },
        "flow": {
            "taker_buy_sell_ratio": round(taker_ratio, 5) if taker_ratio is not None else None,
            "taker_buy_volume": taker_buy,
            "taker_sell_volume": taker_sell,
        },
        "shadow": {
            "bias": round(max(-1.0, min(1.0, shadow_bias)), 4),
            "components": {k: round(v, 4) for k, v in components.items()},
            "weight_in_master": 0.0,
            "mode": "SHADOW_ONLY",
            "reason": "Derivatives features must prove incremental OOS value before receiving trading weight.",
        },
    }


class DerivativesIntelligence:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = ttl_seconds
        self.last_refresh_monotonic = 0.0
        self._lock = asyncio.Lock()
        self.state: dict[str, Any] = {
            "available": False, "symbol": SYMBOL,
            "shadow": {"bias": 0.0, "components": {}, "weight_in_master": 0.0, "mode": "SHADOW_ONLY"},
            "errors": [],
        }

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
        response = await client.get(f"{FAPI}{path}", params=params, timeout=10)
        response.raise_for_status()
        return response.json()

    async def refresh_if_due(self, force: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        if not force and now - self.last_refresh_monotonic < self.ttl_seconds:
            return self.state
        if self._lock.locked():
            return self.state
        async with self._lock:
            errors: list[str] = []
            async with httpx.AsyncClient(follow_redirects=True) as client:
                async def safe(name: str, path: str, params: dict[str, Any]):
                    try:
                        return await self._get(client, path, params)
                    except Exception as exc:
                        errors.append(f"{name}: {str(exc)[:120]}")
                        return {} if name in {"premium", "open_interest"} else []

                premium, funding, oi_now, oi_hist, global_ls, top_accounts, top_positions, taker = await asyncio.gather(
                    safe("premium", "/fapi/v1/premiumIndex", {"symbol": SYMBOL}),
                    safe("funding", "/fapi/v1/fundingRate", {"symbol": SYMBOL, "limit": 30}),
                    safe("open_interest", "/fapi/v1/openInterest", {"symbol": SYMBOL}),
                    safe("open_interest_hist", "/futures/data/openInterestHist", {"symbol": SYMBOL, "period": PERIOD, "limit": 30}),
                    safe("global_ls", "/futures/data/globalLongShortAccountRatio", {"symbol": SYMBOL, "period": PERIOD, "limit": 30}),
                    safe("top_accounts", "/futures/data/topLongShortAccountRatio", {"symbol": SYMBOL, "period": PERIOD, "limit": 30}),
                    safe("top_positions", "/futures/data/topLongShortPositionRatio", {"symbol": SYMBOL, "period": PERIOD, "limit": 30}),
                    safe("taker", "/futures/data/takerlongshortRatio", {"symbol": SYMBOL, "period": PERIOD, "limit": 30}),
                )

            raw = {
                "premium": premium, "funding": funding, "open_interest": oi_now,
                "open_interest_hist": oi_hist, "global_ls": global_ls,
                "top_accounts": top_accounts, "top_positions": top_positions, "taker": taker,
            }
            summary = summarize_derivatives(raw)
            summary["errors"] = errors
            summary["refreshed_at_unix"] = int(time.time())
            self.state = summary
            self.last_refresh_monotonic = time.monotonic()
            return self.state

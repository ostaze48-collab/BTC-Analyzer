from __future__ import annotations

import asyncio
import time
from statistics import fmean
from typing import Any

import httpx

MEMPOOL_BASE = "https://mempool.space/api"
COINMETRICS_BASE = "https://community-api.coinmetrics.io/v4"
COMMUNITY_METRICS = ("AdrActCnt", "TxCnt", "IssTotNtv", "HashRate", "CapMrktCurUSD")


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_change(new: float | None, old: float | None) -> float | None:
    if new is None or old in (None, 0):
        return None
    return (new / old - 1.0) * 100.0


def summarize_coinmetrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"available": False, "metrics": {}}
    ordered = sorted(rows, key=lambda r: str(r.get("time", "")))
    latest = ordered[-1]
    metrics: dict[str, Any] = {}
    for metric in COMMUNITY_METRICS:
        vals = [(str(r.get("time", "")), _num(r.get(metric))) for r in ordered]
        vals = [(t, v) for t, v in vals if v is not None]
        if not vals:
            continue
        current = vals[-1][1]
        seven = vals[-8][1] if len(vals) >= 8 else vals[0][1]
        thirty = vals[-31][1] if len(vals) >= 31 else vals[0][1]
        metrics[metric] = {
            "value": current,
            "change_7d_pct": _pct_change(current, seven),
            "change_30d_pct": _pct_change(current, thirty),
        }
    return {
        "available": bool(metrics),
        "time": latest.get("time"),
        "metrics": metrics,
    }


def summarize_mempool(
    mempool: dict[str, Any] | None,
    hashrate: dict[str, Any] | None,
    difficulty: dict[str, Any] | None,
    fees: dict[str, Any] | None,
) -> dict[str, Any]:
    mempool = mempool or {}
    hashrate = hashrate or {}
    difficulty = difficulty or {}
    fees = fees or {}

    hseries = [float(x.get("avgHashrate", 0) or 0) for x in (hashrate.get("hashrates") or []) if _num(x.get("avgHashrate"))]
    current_hash = _num(hashrate.get("currentHashrate"))
    mean_hash = fmean(hseries[-30:]) if hseries else None
    hash_change = _pct_change(current_hash, mean_hash)

    count = int(mempool.get("count", 0) or 0)
    vsize = _num(mempool.get("vsize")) or 0.0
    total_fee = _num(mempool.get("total_fee")) or 0.0
    vmb = vsize / 1_000_000.0

    fee_fields = {k: _num(fees.get(k)) for k in ("fastestFee", "halfHourFee", "hourFee", "economyFee", "minimumFee")}
    fee_fields = {k: v for k, v in fee_fields.items() if v is not None}

    # Research-only descriptive pressure score. It has zero trading weight until validated.
    congestion = max(0.0, min(1.0, vmb / 300.0))
    return {
        "available": bool(mempool or hashrate or difficulty or fees),
        "mempool": {
            "tx_count": count,
            "vsize_mb": round(vmb, 4),
            "total_fee_btc": round(total_fee / 100_000_000.0, 8),
            "congestion_score": round(congestion, 4),
        },
        "mining": {
            "current_hashrate": current_hash,
            "current_difficulty": _num(hashrate.get("currentDifficulty")),
            "hashrate_vs_30d_mean_pct": round(hash_change, 4) if hash_change is not None else None,
            "difficulty_adjustment": difficulty,
        },
        "fees": fee_fields,
    }


def network_shadow_summary(mempool_ctx: dict[str, Any], coinmetrics_ctx: dict[str, Any]) -> dict[str, Any]:
    """Create an audit-friendly research score that is NOT used for trading yet."""
    components: dict[str, float] = {}
    mining = mempool_ctx.get("mining") or {}
    hash_delta = _num(mining.get("hashrate_vs_30d_mean_pct"))
    if hash_delta is not None:
        components["hashrate_trend"] = max(-1.0, min(1.0, hash_delta / 15.0))

    metrics = coinmetrics_ctx.get("metrics") or {}
    for metric, scale in (("AdrActCnt", 20.0), ("TxCnt", 20.0), ("HashRate", 15.0), ("CapMrktCurUSD", 35.0)):
        row = metrics.get(metric) or {}
        ch = _num(row.get("change_30d_pct"))
        if ch is not None:
            components[metric] = max(-1.0, min(1.0, ch / scale))

    values = list(components.values())
    bias = fmean(values) if values else 0.0
    return {
        "bias": round(max(-1.0, min(1.0, bias)), 4),
        "components": {k: round(v, 4) for k, v in components.items()},
        "weight_in_master": 0.0,
        "mode": "SHADOW_ONLY",
        "reason": "Network features are collected for validation before receiving decision weight.",
    }


class NetworkIntelligence:
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.last_refresh_monotonic = 0.0
        self.state: dict[str, Any] = {
            "available": False,
            "mode": "SHADOW_ONLY",
            "weight_in_master": 0.0,
            "mempool": {},
            "coinmetrics": {},
            "shadow": {"bias": 0.0, "components": {}, "weight_in_master": 0.0, "mode": "SHADOW_ONLY"},
            "errors": [],
        }
        self._lock = asyncio.Lock()

    async def _get_json(self, client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> Any:
        response = await client.get(url, params=params, timeout=12)
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
                async def safe(name: str, url: str, params: dict[str, Any] | None = None):
                    try:
                        return await self._get_json(client, url, params)
                    except Exception as exc:
                        errors.append(f"{name}: {str(exc)[:120]}")
                        return {}

                mempool, hashrate, difficulty, fees, cm = await asyncio.gather(
                    safe("mempool", f"{MEMPOOL_BASE}/mempool"),
                    safe("hashrate", f"{MEMPOOL_BASE}/v1/mining/hashrate/1m"),
                    safe("difficulty", f"{MEMPOOL_BASE}/v1/difficulty-adjustment"),
                    safe("fees", f"{MEMPOOL_BASE}/v1/fees/recommended"),
                    safe(
                        "coinmetrics",
                        f"{COINMETRICS_BASE}/timeseries/asset-metrics",
                        {
                            "assets": "btc",
                            "metrics": ",".join(COMMUNITY_METRICS),
                            "frequency": "1d",
                            "page_size": 45,
                            "paging_from": "end",
                        },
                    ),
                )

            mp = summarize_mempool(mempool, hashrate, difficulty, fees)
            cm_rows = cm.get("data", []) if isinstance(cm, dict) else []
            cm_summary = summarize_coinmetrics(cm_rows)
            shadow = network_shadow_summary(mp, cm_summary)
            self.state = {
                "available": bool(mp.get("available") or cm_summary.get("available")),
                "mode": "SHADOW_ONLY",
                "weight_in_master": 0.0,
                "refreshed_at_unix": int(time.time()),
                "mempool": mp,
                "coinmetrics": cm_summary,
                "shadow": shadow,
                "errors": errors,
            }
            self.last_refresh_monotonic = time.monotonic()
            return self.state

from __future__ import annotations

import asyncio
import time
from collections import deque
from statistics import fmean
from typing import Any

import httpx

from .brains import analyze_brains
from .config import settings
from .indicators import snapshot
from .master import select_trade

INTERVAL_MS = {
    "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000, "30m": 1_800_000,
    "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000, "6h": 21_600_000,
    "8h": 28_800_000, "12h": 43_200_000, "1d": 86_400_000,
    "3d": 259_200_000, "1w": 604_800_000,
}


class BacktestEngine:
    def __init__(self):
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._lock.locked()

    async def run(self, days: int = 3) -> dict[str, Any]:
        days = max(1, min(int(days), 14))
        if self._lock.locked():
            raise RuntimeError("A backtest is already running")
        async with self._lock:
            end_ms = int(time.time() * 1000)
            start_ms = end_ms - days * 86_400_000
            data = await self._load_all(start_ms, end_ms)
            return await asyncio.to_thread(self._simulate, data, start_ms, end_ms, days)

    async def _load_all(self, start_ms: int, end_ms: int) -> dict[str, list[dict[str, Any]]]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
            results = await asyncio.gather(*[self._fetch_interval(client, tf, start_ms, end_ms) for tf in settings.intervals])
        return dict(zip(settings.intervals, results))

    async def _fetch_interval(self, client: httpx.AsyncClient, interval: str, start_ms: int, end_ms: int):
        cursor = max(0, start_ms - INTERVAL_MS[interval] * 220)
        rows: list[dict[str, Any]] = []
        while cursor < end_ms:
            payload = None
            last_error: Exception | None = None
            for base in settings.rest_bases:
                try:
                    r = await client.get(
                        f"{base}/api/v3/klines",
                        params={"symbol": settings.symbol, "interval": interval, "startTime": cursor, "endTime": end_ms, "limit": 1000},
                    )
                    r.raise_for_status()
                    payload = r.json()
                    break
                except Exception as exc:
                    last_error = exc
            if payload is None:
                raise RuntimeError(f"Historical data failed for {interval}: {last_error}")
            if not payload:
                break
            for row in payload:
                rows.append({
                    "time": int(row[0] // 1000), "close_time": int(row[6] // 1000),
                    "open": float(row[1]), "high": float(row[2]), "low": float(row[3]),
                    "close": float(row[4]), "volume": float(row[5]), "closed": True,
                })
            nxt = int(payload[-1][6]) + 1
            if nxt <= cursor:
                break
            cursor = nxt
            if len(payload) < 1000:
                break
        unique = {x["time"]: x for x in rows}
        return [unique[k] for k in sorted(unique)]

    @staticmethod
    def _pnl(t: dict[str, Any], qty: float, exit_price: float) -> float:
        sign = 1.0 if t["direction"] == "LONG" else -1.0
        gross = (exit_price - t["entry"]) * qty * sign
        fees = (t["entry"] * qty + exit_price * qty) * settings.paper_fee_rate
        return gross - fees

    @staticmethod
    def _open(p: dict[str, Any], capital: float, ts: int) -> dict[str, Any] | None:
        risk = abs(float(p["entry"]) - float(p["stop_loss"]))
        if risk <= 0:
            return None
        qty = min(capital * settings.risk_per_trade / risk, capital / float(p["entry"]))
        if qty <= 0:
            return None
        return {
            "brain": p["brain"], "direction": p["direction"], "entry": float(p["entry"]),
            "stop_loss": float(p["stop_loss"]), "tp1": float(p["tp1"]), "tp2": float(p["tp2"]), "tp3": float(p["tp3"]),
            "quantity": qty, "remaining_qty": qty, "realized_pnl": 0.0,
            "tp1_hit": False, "tp2_hit": False, "opened_at": ts,
            "initial_risk_price": risk, "mfe_pct": 0.0, "mae_pct": 0.0,
            "macro_direction": p.get("macro_direction"), "macro_conflict": p.get("macro_conflict", False),
        }

    def _partial(self, t: dict[str, Any], fraction: float, price: float, flag: str):
        qty = min(t["remaining_qty"], t["quantity"] * fraction)
        if qty <= 0:
            return
        t["realized_pnl"] += self._pnl(t, qty, price)
        t["remaining_qty"] -= qty
        t[flag] = True
        if flag == "tp1_hit":
            t["stop_loss"] = t["entry"]
        elif flag == "tp2_hit":
            t["stop_loss"] = t["tp1"]

    def _close(self, t: dict[str, Any], price: float, reason: str, ts: int):
        if t["remaining_qty"] > 0:
            t["realized_pnl"] += self._pnl(t, t["remaining_qty"], price)
        t["remaining_qty"] = 0.0
        t["exit_price"], t["exit_reason"], t["closed_at"] = price, reason, ts
        denom = t["quantity"] * t["initial_risk_price"]
        t["r_multiple"] = t["realized_pnl"] / denom if denom > 0 else 0.0
        return t

    def _manage(self, t: dict[str, Any], c: dict[str, Any]):
        e = t["entry"]
        if t["direction"] == "LONG":
            t["mfe_pct"] = max(t["mfe_pct"], (c["high"] - e) / e * 100)
            t["mae_pct"] = max(t["mae_pct"], (e - c["low"]) / e * 100)
            # Conservative ambiguity policy: stop is processed before targets.
            if c["low"] <= t["stop_loss"]:
                return self._close(t, t["stop_loss"], "STOP_LOSS", c["close_time"])
            if not t["tp1_hit"] and c["high"] >= t["tp1"]:
                self._partial(t, .30, t["tp1"], "tp1_hit")
            if not t["tp2_hit"] and c["high"] >= t["tp2"]:
                self._partial(t, .40, t["tp2"], "tp2_hit")
            if c["high"] >= t["tp3"]:
                return self._close(t, t["tp3"], "TP3", c["close_time"])
        else:
            t["mfe_pct"] = max(t["mfe_pct"], (e - c["low"]) / e * 100)
            t["mae_pct"] = max(t["mae_pct"], (c["high"] - e) / e * 100)
            if c["high"] >= t["stop_loss"]:
                return self._close(t, t["stop_loss"], "STOP_LOSS", c["close_time"])
            if not t["tp1_hit"] and c["low"] <= t["tp1"]:
                self._partial(t, .30, t["tp1"], "tp1_hit")
            if not t["tp2_hit"] and c["low"] <= t["tp2"]:
                self._partial(t, .40, t["tp2"], "tp2_hit")
            if c["low"] <= t["tp3"]:
                return self._close(t, t["tp3"], "TP3", c["close_time"])
        return None

    def _simulate(self, data, start_ms: int, end_ms: int, days: int):
        start_s, end_s = start_ms // 1000, end_ms // 1000
        timeline = [c for c in data["1m"] if start_s <= c["close_time"] <= end_s]
        if not timeline:
            raise RuntimeError("No historical 1m candles were returned")

        histories = {tf: deque(maxlen=settings.history_limit) for tf in settings.intervals}
        pointers = {tf: 0 for tf in settings.intervals}
        cached_snapshots: dict[str, dict[str, Any]] = {tf: {} for tf in settings.intervals}
        capital = float(settings.paper_start_capital)
        peak, max_dd = capital, 0.0
        active = None
        trades: list[dict[str, Any]] = []
        selected = {"SCALP": 0, "INTRADAY": 0, "SWING": 0}

        for minute in timeline:
            now = minute["close_time"]
            changed: set[str] = set()
            for tf in settings.intervals:
                rows, i = data[tf], pointers[tf]
                while i < len(rows) and rows[i]["close_time"] <= now:
                    histories[tf].append(rows[i])
                    i += 1
                    changed.add(tf)
                pointers[tf] = i

            if active:
                closed = self._manage(active, minute)
                if closed:
                    capital += closed["realized_pnl"]
                    trades.append(closed)
                    active = None
                    peak = max(peak, capital)
                    max_dd = max(max_dd, (peak - capital) / peak * 100 if peak else 0)

            for tf in settings.intervals:
                if tf in changed or not cached_snapshots[tf]:
                    cached_snapshots[tf] = snapshot(list(histories[tf]))
            snaps = cached_snapshots
            if any(not snaps[tf] for tf in settings.intervals):
                continue

            advisory = select_trade(analyze_brains(snaps))
            if active:
                opp = [
                    p for p in advisory["proposals"]
                    if p.get("direction") in ("LONG", "SHORT")
                    and p["direction"] != active["direction"]
                    and p.get("risk_gate") == "PASSED"
                    and p.get("final_score", 0) >= 84
                ]
                if len(opp) >= 2:
                    closed = self._close(active, minute["close"], "EARLY_EXIT_OPPOSITE_CONSENSUS", now)
                    capital += closed["realized_pnl"]
                    trades.append(closed)
                    active = None
                    peak = max(peak, capital)
                    max_dd = max(max_dd, (peak - capital) / peak * 100 if peak else 0)

            if not active and advisory["action"] in ("LONG", "SHORT") and advisory["winner"]:
                active = self._open(advisory["winner"], capital, now)
                if active:
                    selected[active["brain"]] += 1

        if active:
            last = timeline[-1]
            closed = self._close(active, last["close"], "END_OF_TEST", last["close_time"])
            capital += closed["realized_pnl"]
            trades.append(closed)
            peak = max(peak, capital)
            max_dd = max(max_dd, (peak - capital) / peak * 100 if peak else 0)

        pnls = [t["realized_pnl"] for t in trades]
        wins = sum(p > 0 for p in pnls)
        gw, gl = sum(p for p in pnls if p > 0), abs(sum(p for p in pnls if p < 0))
        by_brain = {}
        for brain in selected:
            sub = [t for t in trades if t["brain"] == brain]
            sp = [t["realized_pnl"] for t in sub]
            sw = sum(p > 0 for p in sp)
            by_brain[brain] = {
                "trades": len(sub), "wins": sw, "losses": len(sub)-sw,
                "win_rate": round(sw / len(sub) * 100, 2) if sub else 0.0,
                "net_pnl": round(sum(sp), 2),
                "avg_r": round(fmean([t["r_multiple"] for t in sub]), 3) if sub else 0.0,
                "avg_mfe_pct": round(fmean([t["mfe_pct"] for t in sub]), 3) if sub else 0.0,
                "avg_mae_pct": round(fmean([t["mae_pct"] for t in sub]), 3) if sub else 0.0,
                "selected": selected[brain],
            }

        return {
            "symbol": settings.symbol, "days": days,
            "assumptions": {
                "paper_only": True, "one_trade_only": True,
                "same_candle_rule": "STOP_FIRST_CONSERVATIVE",
                "confirmed_candles_only": True, "intervals": list(settings.intervals),
            },
            "metrics": {
                "starting_capital": round(settings.paper_start_capital, 2), "ending_capital": round(capital, 2),
                "net_pnl": round(capital-settings.paper_start_capital, 2), "return_pct": round((capital/settings.paper_start_capital-1)*100, 2),
                "trades": len(trades), "wins": wins, "losses": len(trades)-wins,
                "win_rate": round(wins/len(trades)*100, 2) if trades else 0.0,
                "profit_factor": round(gw/gl, 3) if gl else (999.0 if gw else 0.0),
                "avg_r": round(fmean([t["r_multiple"] for t in trades]), 3) if trades else 0.0,
                "max_drawdown_pct": round(max_dd, 3),
            },
            "by_brain": by_brain,
            "recent_trades": [
                {"brain": t["brain"], "direction": t["direction"], "entry": round(t["entry"],2), "exit": round(t["exit_price"],2),
                 "pnl": round(t["realized_pnl"],2), "r": round(t["r_multiple"],3), "reason": t["exit_reason"],
                 "mfe_pct": round(t["mfe_pct"],3), "mae_pct": round(t["mae_pct"],3),
                 "macro_direction": t.get("macro_direction"), "macro_conflict": t.get("macro_conflict", False)}
                for t in trades[-100:]
            ],
        }

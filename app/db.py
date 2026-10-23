from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str | None = None):
        self.path = path or settings.db_path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS account (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    starting_capital REAL NOT NULL,
                    capital REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    brain TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    entry REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    tp1 REAL NOT NULL,
                    tp2 REAL NOT NULL,
                    tp3 REAL NOT NULL,
                    quantity REAL NOT NULL,
                    remaining_qty REAL NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL,
                    safety_score REAL NOT NULL,
                    profit_score REAL NOT NULL,
                    final_score REAL NOT NULL,
                    tp1_hit INTEGER NOT NULL DEFAULT 0,
                    tp2_hit INTEGER NOT NULL DEFAULT 0,
                    exit_price REAL,
                    exit_reason TEXT,
                    meta_json TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            row = self.conn.execute("SELECT id FROM account WHERE id=1").fetchone()
            if not row:
                self.conn.execute(
                    "INSERT INTO account(id, starting_capital, capital, updated_at) VALUES(1, ?, ?, ?)",
                    (settings.paper_start_capital, settings.paper_start_capital, utc_now()),
                )
            self.conn.commit()

    def account(self) -> dict[str, Any]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM account WHERE id=1").fetchone()
            return dict(row)

    def update_capital(self, delta: float) -> float:
        with self._lock:
            self.conn.execute(
                "UPDATE account SET capital = capital + ?, updated_at=? WHERE id=1",
                (delta, utc_now()),
            )
            self.conn.commit()
            return float(self.account()["capital"])

    def create_trade(self, trade: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            cur = self.conn.execute(
                """
                INSERT INTO trades(
                    brain, direction, status, opened_at,
                    entry, stop_loss, tp1, tp2, tp3,
                    quantity, remaining_qty, realized_pnl,
                    confidence, safety_score, profit_score, final_score,
                    meta_json
                ) VALUES (?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
                """,
                (
                    trade["brain"], trade["direction"], utc_now(),
                    trade["entry"], trade["stop_loss"], trade["tp1"], trade["tp2"], trade["tp3"],
                    trade["quantity"], trade["quantity"],
                    trade["confidence"], trade["safety_score"], trade["profit_score"], trade["final_score"],
                    json.dumps(trade.get("meta", {}), ensure_ascii=False),
                ),
            )
            self.conn.commit()
            return self.get_trade(cur.lastrowid)

    def get_trade(self, trade_id: int) -> dict[str, Any]:
        with self._lock:
            row = self.conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
            return dict(row) if row else {}

    def active_trade(self) -> dict[str, Any] | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM trades WHERE status='OPEN' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def update_trade(self, trade_id: int, **fields: Any) -> dict[str, Any]:
        if not fields:
            return self.get_trade(trade_id)
        with self._lock:
            keys = list(fields)
            sql = ", ".join(f"{k}=?" for k in keys)
            values = [fields[k] for k in keys] + [trade_id]
            self.conn.execute(f"UPDATE trades SET {sql} WHERE id=?", values)
            self.conn.commit()
            return self.get_trade(trade_id)

    def close_trade(self, trade_id: int, exit_price: float, reason: str, realized_pnl: float) -> dict[str, Any]:
        with self._lock:
            self.conn.execute(
                """
                UPDATE trades
                SET status='CLOSED', closed_at=?, exit_price=?, exit_reason=?,
                    remaining_qty=0, realized_pnl=?
                WHERE id=?
                """,
                (utc_now(), exit_price, reason, realized_pnl, trade_id),
            )
            self.conn.commit()
            return self.get_trade(trade_id)

    def recent_trades(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            account = self.account()
            rows = self.conn.execute(
                "SELECT realized_pnl FROM trades WHERE status='CLOSED'"
            ).fetchall()
            pnls = [float(r["realized_pnl"]) for r in rows]
            wins = sum(1 for x in pnls if x > 0)
            gross_win = sum(x for x in pnls if x > 0)
            gross_loss = abs(sum(x for x in pnls if x < 0))
            peak = account["starting_capital"]
            equity = account["starting_capital"]
            max_dd = 0.0
            for pnl in pnls[::-1]:
                equity += pnl
                peak = max(peak, equity)
                if peak > 0:
                    max_dd = max(max_dd, (peak - equity) / peak * 100)
            return {
                "starting_capital": round(float(account["starting_capital"]), 2),
                "capital": round(float(account["capital"]), 2),
                "net_pnl": round(float(account["capital"]) - float(account["starting_capital"]), 2),
                "trades": len(pnls),
                "wins": wins,
                "losses": len(pnls) - wins,
                "win_rate": round((wins / len(pnls) * 100) if pnls else 0.0, 2),
                "profit_factor": round((gross_win / gross_loss) if gross_loss else (999.0 if gross_win else 0.0), 2),
                "max_drawdown_pct": round(max_dd, 2),
            }

    def reset(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM trades")
            self.conn.execute(
                "UPDATE account SET starting_capital=?, capital=?, updated_at=? WHERE id=1",
                (settings.paper_start_capital, settings.paper_start_capital, utc_now()),
            )
            self.conn.commit()

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
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

    def _ensure_column(self, table: str, name: str, definition: str) -> None:
        cols = {row["name"] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if name not in cols:
            self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

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

                CREATE TABLE IF NOT EXISTS trade_features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER NOT NULL,
                    phase TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    feature_json TEXT NOT NULL,
                    FOREIGN KEY(trade_id) REFERENCES trades(id)
                );
                CREATE INDEX IF NOT EXISTS idx_trade_features_trade ON trade_features(trade_id);
                """
            )
            self._ensure_column("trades", "market_regime", "TEXT")
            self._ensure_column("trades", "mfe_pct", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("trades", "mae_pct", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("trades", "leverage", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column("trades", "notional", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("trades", "margin_used", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("trades", "risk_budget", "REAL NOT NULL DEFAULT 0")
            self._ensure_column("trades", "target_r", "REAL NOT NULL DEFAULT 0")

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
            self.conn.execute("UPDATE account SET capital = capital + ?, updated_at=? WHERE id=1", (delta, utc_now()))
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
                    market_regime, mfe_pct, mae_pct,
                    leverage, notional, margin_used, risk_budget, target_r,
                    meta_json
                ) VALUES (?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade["brain"], trade["direction"], utc_now(),
                    trade["entry"], trade["stop_loss"], trade["tp1"], trade["tp2"], trade["tp3"],
                    trade["quantity"], trade["quantity"], trade["confidence"], trade["safety_score"],
                    trade["profit_score"], trade["final_score"], trade.get("market_regime"),
                    int(trade.get("leverage", 1)), float(trade.get("notional", 0.0)),
                    float(trade.get("margin_used", 0.0)), float(trade.get("risk_budget", 0.0)),
                    float(trade.get("target_r", 0.0)),
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
            row = self.conn.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY id DESC LIMIT 1").fetchone()
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

    def record_feature(self, trade_id: int, phase: str, features: dict[str, Any]) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO trade_features(trade_id, phase, captured_at, feature_json) VALUES(?, ?, ?, ?)",
                (trade_id, phase, utc_now(), json.dumps(features, ensure_ascii=False, separators=(",", ":"))),
            )
            self.conn.commit()

    def close_trade(self, trade_id: int, exit_price: float, reason: str, realized_pnl: float, mfe_pct: float = 0.0, mae_pct: float = 0.0) -> dict[str, Any]:
        with self._lock:
            self.conn.execute(
                """
                UPDATE trades
                SET status='CLOSED', closed_at=?, exit_price=?, exit_reason=?,
                    remaining_qty=0, realized_pnl=?, mfe_pct=?, mae_pct=?
                WHERE id=?
                """,
                (utc_now(), exit_price, reason, realized_pnl, mfe_pct, mae_pct, trade_id),
            )
            self.conn.commit()
            return self.get_trade(trade_id)

    def recent_trades(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._lock:
            account = self.account()
            rows = self.conn.execute("SELECT realized_pnl FROM trades WHERE status='CLOSED' ORDER BY id ASC").fetchall()
            pnls = [float(r["realized_pnl"]) for r in rows]
            wins = sum(1 for x in pnls if x > 0)
            gross_win = sum(x for x in pnls if x > 0)
            gross_loss = abs(sum(x for x in pnls if x < 0))
            peak = float(account["starting_capital"])
            equity = peak
            max_dd = 0.0
            for pnl in pnls:
                equity += pnl
                peak = max(peak, equity)
                if peak > 0:
                    max_dd = max(max_dd, (peak - equity) / peak * 100)
            start = float(account["starting_capital"])
            capital = float(account["capital"])
            start_dd = max(0.0, (start - capital) / start * 100) if start > 0 else 0.0
            return {
                "starting_capital": round(start, 2),
                "capital": round(capital, 2),
                "net_pnl": round(capital - start, 2),
                "trades": len(pnls), "wins": wins, "losses": len(pnls) - wins,
                "win_rate": round((wins / len(pnls) * 100) if pnls else 0.0, 2),
                "profit_factor": round((gross_win / gross_loss) if gross_loss else (999.0 if gross_win else 0.0), 2),
                "max_drawdown_pct": round(max_dd, 2),
                "drawdown_from_start_pct": round(start_dd, 2),
                "hard_drawdown_limit_pct": round(settings.max_total_drawdown * 100, 2),
                "soft_pause_drawdown_pct": round(settings.soft_pause_drawdown * 100, 2),
            }

    def learning_summary(self) -> dict[str, Any]:
        with self._lock:
            rows = self.conn.execute(
                """
                SELECT brain, COALESCE(market_regime, 'UNKNOWN') AS regime,
                       realized_pnl, mfe_pct, mae_pct
                FROM trades WHERE status='CLOSED' ORDER BY id ASC
                """
            ).fetchall()
            groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
            for row in rows:
                groups.setdefault((row["brain"], row["regime"]), []).append(row)
            matrix = []
            for (brain, regime), subset in sorted(groups.items()):
                pnls = [float(x["realized_pnl"]) for x in subset]
                wins = sum(1 for x in pnls if x > 0)
                gw = sum(x for x in pnls if x > 0)
                gl = abs(sum(x for x in pnls if x < 0))
                matrix.append({
                    "brain": brain, "regime": regime, "trades": len(subset),
                    "win_rate": round(wins / len(subset) * 100, 2) if subset else 0.0,
                    "net_pnl": round(sum(pnls), 2),
                    "profit_factor": round(gw / gl, 3) if gl else (999.0 if gw else 0.0),
                    "avg_mfe_pct": round(sum(float(x["mfe_pct"]) for x in subset) / len(subset), 3),
                    "avg_mae_pct": round(sum(float(x["mae_pct"]) for x in subset) / len(subset), 3),
                })
            feature_count = int(self.conn.execute("SELECT COUNT(*) AS n FROM trade_features").fetchone()["n"])
            return {"closed_trades": len(rows), "feature_snapshots": feature_count, "brain_regime": matrix}

    def reset(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM trade_features")
            self.conn.execute("DELETE FROM trades")
            self.conn.execute("UPDATE account SET starting_capital=?, capital=?, updated_at=? WHERE id=1", (settings.paper_start_capital, settings.paper_start_capital, utc_now()))
            self.conn.commit()

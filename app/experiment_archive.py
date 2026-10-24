from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover - sqlite fallback remains available
    psycopg = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _group_performance(trades: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for trade in trades:
        name = str(trade.get(key) or "UNKNOWN")
        groups.setdefault(name, []).append(trade)

    out: list[dict[str, Any]] = []
    for name, rows in sorted(groups.items()):
        pnls = [_as_float(row.get("realized_pnl")) for row in rows]
        wins = [value for value in pnls if value > 0]
        losses = [value for value in pnls if value < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        r_values = [
            _as_float(row.get("realized_pnl")) / _as_float(row.get("risk_budget"))
            for row in rows
            if _as_float(row.get("risk_budget")) > 0
        ]
        out.append(
            {
                "name": name,
                "trades": len(rows),
                "wins": len(wins),
                "win_rate": round(len(wins) / len(rows) * 100.0, 2) if rows else 0.0,
                "net_pnl": round(sum(pnls), 2),
                "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else (999.0 if gross_win else 0.0),
                "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
            }
        )
    return out


def _downsample(points: list[dict[str, Any]], limit: int = 420) -> list[dict[str, Any]]:
    if len(points) <= limit:
        return points
    step = max(1, len(points) // limit)
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled[: limit + 1]


def build_experiment_snapshot(db: Any, app_version: str, label: str | None = None) -> dict[str, Any]:
    stats = dict(db.stats() or {})
    trades = list(db.recent_trades(5000) or [])
    closed = sorted(
        [trade for trade in trades if str(trade.get("status")) == "CLOSED"],
        key=lambda trade: (_as_int(trade.get("id")), str(trade.get("closed_at") or "")),
    )

    start_capital = _as_float(stats.get("starting_capital"), 1000.0)
    equity = start_capital
    curve: list[dict[str, Any]] = [{"trade": 0, "equity": round(equity, 2), "time": None}]
    r_values: list[float] = []
    for index, trade in enumerate(closed, start=1):
        equity += _as_float(trade.get("realized_pnl"))
        risk = _as_float(trade.get("risk_budget"))
        if risk > 0:
            r_values.append(_as_float(trade.get("realized_pnl")) / risk)
        curve.append(
            {
                "trade": index,
                "trade_id": _as_int(trade.get("id")),
                "equity": round(equity, 2),
                "time": trade.get("closed_at") or trade.get("opened_at"),
            }
        )

    started = _dt(closed[0].get("opened_at")) if closed else None
    ended = _dt(closed[-1].get("closed_at") or closed[-1].get("opened_at")) if closed else None
    duration_hours = max(0.0, (ended - started).total_seconds() / 3600.0) if started and ended else 0.0
    pnls = [_as_float(trade.get("realized_pnl")) for trade in closed]

    recent = []
    for trade in closed[-100:]:
        risk = _as_float(trade.get("risk_budget"))
        recent.append(
            {
                "id": _as_int(trade.get("id")),
                "brain": trade.get("brain"),
                "regime": trade.get("market_regime") or "UNKNOWN",
                "direction": trade.get("direction"),
                "opened_at": trade.get("opened_at"),
                "closed_at": trade.get("closed_at"),
                "realized_pnl": round(_as_float(trade.get("realized_pnl")), 4),
                "r": round(_as_float(trade.get("realized_pnl")) / risk, 4) if risk > 0 else None,
                "exit_reason": trade.get("exit_reason"),
            }
        )

    return {
        "label": (label or "Paper Experiment").strip()[:120] or "Paper Experiment",
        "app_version": app_version,
        "captured_at": _utc_now(),
        "paper_only": True,
        "status": "HAS_RESULTS" if closed else "EMPTY",
        "started_at": started.isoformat() if started else None,
        "ended_at": ended.isoformat() if ended else None,
        "duration_hours": round(duration_hours, 2),
        "metrics": {
            **stats,
            "expectancy_usd": round(sum(pnls) / len(pnls), 4) if pnls else 0.0,
            "avg_r": round(sum(r_values) / len(r_values), 4) if r_values else 0.0,
            "net_r": round(sum(r_values), 4) if r_values else 0.0,
            "largest_win": round(max(pnls), 2) if pnls else 0.0,
            "largest_loss": round(min(pnls), 2) if pnls else 0.0,
        },
        "by_brain": _group_performance(closed, "brain"),
        "by_regime": _group_performance(closed, "market_regime"),
        "equity_curve": _downsample(curve),
        "recent_trades": recent,
    }


class ExperimentArchive:
    """Persistent experiment result archive.

    On Render, DATABASE_URL points this archive at Postgres so archived experiment
    results survive container rebuilds. In local/CI environments it falls back to
    SQLite without changing the trading database contract.
    """

    def __init__(self, sqlite_path: str):
        self.sqlite_path = str(sqlite_path)
        self.database_url = (os.getenv("DATABASE_URL") or "").strip()
        self._lock = threading.RLock()
        self._sqlite: sqlite3.Connection | None = None

    @property
    def backend(self) -> str:
        return "postgres" if self.database_url else "sqlite"

    @property
    def persistent_across_redeploys(self) -> bool:
        return bool(self.database_url)

    def init(self) -> None:
        if self.database_url:
            if psycopg is None:
                raise RuntimeError("DATABASE_URL is configured but psycopg is not installed")
            with psycopg.connect(self.database_url) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS experiment_runs (
                        id BIGSERIAL PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        label TEXT NOT NULL,
                        app_version TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    )
                    """
                )
            return

        Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if self._sqlite is None:
                self._sqlite = sqlite3.connect(self.sqlite_path, check_same_thread=False)
                self._sqlite.row_factory = sqlite3.Row
            self._sqlite.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    label TEXT NOT NULL,
                    app_version TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            self._sqlite.commit()

    def close(self) -> None:
        with self._lock:
            if self._sqlite is not None:
                self._sqlite.close()
                self._sqlite = None

    def save(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        created_at = str(snapshot.get("captured_at") or _utc_now())
        label = str(snapshot.get("label") or "Paper Experiment")[:120]
        app_version = str(snapshot.get("app_version") or "")[:32]
        payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))

        if self.database_url:
            with psycopg.connect(self.database_url) as conn:
                row = conn.execute(
                    "INSERT INTO experiment_runs(created_at,label,app_version,payload_json) VALUES(%s,%s,%s,%s) RETURNING id",
                    (created_at, label, app_version, payload),
                ).fetchone()
                run_id = int(row[0])
        else:
            with self._lock:
                if self._sqlite is None:
                    self.init()
                cur = self._sqlite.execute(
                    "INSERT INTO experiment_runs(created_at,label,app_version,payload_json) VALUES(?,?,?,?)",
                    (created_at, label, app_version, payload),
                )
                self._sqlite.commit()
                run_id = int(cur.lastrowid)

        return {"id": run_id, "created_at": created_at, "label": label, "app_version": app_version, "snapshot": snapshot}

    def list(self, limit: int = 30) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 100))
        if self.database_url:
            with psycopg.connect(self.database_url) as conn:
                rows = conn.execute(
                    "SELECT id,created_at,label,app_version,payload_json FROM experiment_runs ORDER BY id DESC LIMIT %s",
                    (safe_limit,),
                ).fetchall()
                raw = [dict(zip(("id", "created_at", "label", "app_version", "payload_json"), row)) for row in rows]
        else:
            with self._lock:
                if self._sqlite is None:
                    self.init()
                raw = [dict(row) for row in self._sqlite.execute(
                    "SELECT id,created_at,label,app_version,payload_json FROM experiment_runs ORDER BY id DESC LIMIT ?",
                    (safe_limit,),
                ).fetchall()]

        out: list[dict[str, Any]] = []
        for row in raw:
            try:
                snapshot = json.loads(row.pop("payload_json") or "{}")
            except (TypeError, json.JSONDecodeError):
                snapshot = {}
            metrics = snapshot.get("metrics") or {}
            out.append(
                {
                    **row,
                    "status": snapshot.get("status", "UNKNOWN"),
                    "duration_hours": snapshot.get("duration_hours", 0.0),
                    "metrics": metrics,
                    "by_brain": snapshot.get("by_brain") or [],
                    "by_regime": snapshot.get("by_regime") or [],
                    "equity_curve": snapshot.get("equity_curve") or [],
                    "recent_trades": snapshot.get("recent_trades") or [],
                    "paper_only": True,
                }
            )
        return out

    def info(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "persistent_across_redeploys": self.persistent_across_redeploys,
            "paper_only": True,
        }

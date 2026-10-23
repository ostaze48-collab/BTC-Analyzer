from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from statistics import fmean
from typing import Any


_STAGE_RANK = {
    "DATA_BUILDING": 0,
    "EVIDENCE_BUILDING": 1,
    "SHADOW_VALIDATED": 2,
    "STRICT_PAPER_REVIEW_CANDIDATE": 3,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


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


def compact_snapshot(report: dict[str, Any], paper_stats: dict[str, Any] | None = None, app_version: str = "") -> dict[str, Any]:
    paper_stats = paper_stats or {}
    mandatory = list(report.get("mandatory_gates") or [])
    failed = list(report.get("failed_mandatory_gates") or [])
    feature = report.get("feature_research") or {}
    target = report.get("target_evidence") or {}
    core = report.get("core_readiness") or {}
    return {
        "app_version": app_version,
        "status": str(report.get("status", "DATA_BUILDING")),
        "research_score": round(_as_float(report.get("research_score")), 2),
        "mandatory_passed": sum(1 for g in mandatory if g.get("passed")),
        "mandatory_total": len(mandatory),
        "failed_mandatory_count": len(failed),
        "failed_mandatory_gates": failed,
        "core_status": str(core.get("status", "NOT_READY")),
        "core_score": round(_as_float(core.get("score")), 2),
        "target_status": str(target.get("status", "NOT_RUN")),
        "target_pass": bool(target.get("all_gates_passed", False)),
        "feature_incremental_oos": bool(feature.get("incremental_oos_evidence", False)),
        "paper_trades": _as_int(paper_stats.get("trades")),
        "paper_profit_factor": round(_as_float(paper_stats.get("profit_factor")), 4),
        "paper_drawdown_pct": round(_as_float(paper_stats.get("max_drawdown_pct")), 4),
        "paper_only": bool(report.get("paper_only", True)),
        "real_execution_eligibility": bool(report.get("real_execution_eligibility", False)),
    }


def summarize_research_history(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "status": "NO_HISTORY",
            "trend": "INSUFFICIENT_HISTORY",
            "snapshots": 0,
            "message": "No research-readiness snapshots recorded yet.",
        }

    ordered = sorted(rows, key=lambda r: (str(r.get("captured_at", "")), _as_int(r.get("id"))))
    first = ordered[0]
    current = ordered[-1]
    previous = ordered[-2] if len(ordered) >= 2 else first
    first_rank = _STAGE_RANK.get(str(first.get("status")), -1)
    current_rank = _STAGE_RANK.get(str(current.get("status")), -1)
    previous_rank = _STAGE_RANK.get(str(previous.get("status")), -1)

    score_delta_first = _as_float(current.get("research_score")) - _as_float(first.get("research_score"))
    score_delta_previous = _as_float(current.get("research_score")) - _as_float(previous.get("research_score"))
    gate_delta_first = _as_int(current.get("mandatory_passed")) - _as_int(first.get("mandatory_passed"))
    gate_delta_previous = _as_int(current.get("mandatory_passed")) - _as_int(previous.get("mandatory_passed"))

    if len(ordered) < 3:
        trend = "INSUFFICIENT_HISTORY"
    elif current_rank < previous_rank or gate_delta_previous < 0 or score_delta_previous <= -5.0:
        trend = "REGRESSING"
    elif current_rank > first_rank or gate_delta_first > 0 or score_delta_first >= 5.0:
        trend = "IMPROVING"
    else:
        trend = "STABLE"

    transitions = 0
    regressions = 0
    best_rank = -1
    best_stage = None
    for prev, row in zip(ordered, ordered[1:]):
        a = _STAGE_RANK.get(str(prev.get("status")), -1)
        b = _STAGE_RANK.get(str(row.get("status")), -1)
        if a != b:
            transitions += 1
        if b < a:
            regressions += 1
        if b > best_rank:
            best_rank = b
            best_stage = row.get("status")
    if first_rank > best_rank:
        best_rank = first_rank
        best_stage = first.get("status")

    target_pass_rate = fmean(1.0 if r.get("target_pass") else 0.0 for r in ordered) * 100.0
    feature_support_rate = fmean(1.0 if r.get("feature_incremental_oos") else 0.0 for r in ordered) * 100.0
    scores = [_as_float(r.get("research_score")) for r in ordered]
    started = _dt(str(first.get("captured_at", "")))
    ended = _dt(str(current.get("captured_at", "")))
    span_hours = (ended - started).total_seconds() / 3600.0 if started and ended else 0.0

    return {
        "status": "READY",
        "trend": trend,
        "snapshots": len(ordered),
        "current_stage": current.get("status"),
        "best_stage": best_stage,
        "stage_transitions": transitions,
        "stage_regressions": regressions,
        "research_score_current": round(_as_float(current.get("research_score")), 2),
        "research_score_first": round(_as_float(first.get("research_score")), 2),
        "research_score_delta_from_first": round(score_delta_first, 2),
        "research_score_delta_from_previous": round(score_delta_previous, 2),
        "mandatory_passed_current": _as_int(current.get("mandatory_passed")),
        "mandatory_total_current": _as_int(current.get("mandatory_total")),
        "mandatory_passed_delta_from_first": gate_delta_first,
        "target_pass_rate_pct": round(target_pass_rate, 2),
        "feature_incremental_support_rate_pct": round(feature_support_rate, 2),
        "average_research_score": round(fmean(scores), 2),
        "best_research_score": round(max(scores), 2),
        "worst_research_score": round(min(scores), 2),
        "paper_trades_current": _as_int(current.get("paper_trades")),
        "span_hours": round(max(0.0, span_hours), 2),
        "started_at": first.get("captured_at"),
        "latest_at": current.get("captured_at"),
        "score_is_authorization": False,
        "real_execution_eligibility": False,
        "message": "Trend describes research evidence only; it is not a trading signal or execution authorization.",
    }


class ResearchHistoryStore:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    captured_at TEXT NOT NULL,
                    app_version TEXT NOT NULL,
                    status TEXT NOT NULL,
                    research_score REAL NOT NULL,
                    mandatory_passed INTEGER NOT NULL,
                    mandatory_total INTEGER NOT NULL,
                    failed_mandatory_count INTEGER NOT NULL,
                    core_status TEXT NOT NULL,
                    core_score REAL NOT NULL,
                    target_status TEXT NOT NULL,
                    target_pass INTEGER NOT NULL,
                    feature_incremental_oos INTEGER NOT NULL,
                    paper_trades INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_research_snapshots_time ON research_snapshots(captured_at);
                """
            )
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def clear(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM research_snapshots")
            self.conn.commit()

    @staticmethod
    def _signature(snapshot: dict[str, Any]) -> tuple[Any, ...]:
        return (
            snapshot.get("status"),
            round(_as_float(snapshot.get("research_score")), 1),
            _as_int(snapshot.get("mandatory_passed")),
            _as_int(snapshot.get("failed_mandatory_count")),
            bool(snapshot.get("target_pass")),
            bool(snapshot.get("feature_incremental_oos")),
            _as_int(snapshot.get("paper_trades")),
        )

    def record(
        self,
        report: dict[str, Any],
        paper_stats: dict[str, Any] | None = None,
        app_version: str = "",
        min_interval_seconds: int = 900,
    ) -> dict[str, Any]:
        snapshot = compact_snapshot(report, paper_stats, app_version)
        now = datetime.now(timezone.utc)
        captured_at = now.isoformat()
        with self._lock:
            latest = self.conn.execute("SELECT * FROM research_snapshots ORDER BY id DESC LIMIT 1").fetchone()
            if latest:
                latest_payload = json.loads(latest["payload_json"] or "{}")
                last_time = _dt(latest["captured_at"])
                elapsed = (now - last_time).total_seconds() if last_time else float("inf")
                if elapsed < max(0, int(min_interval_seconds)) and self._signature(latest_payload) == self._signature(snapshot):
                    row = dict(latest)
                    row["payload"] = latest_payload
                    row["recorded"] = False
                    return row

            cur = self.conn.execute(
                """
                INSERT INTO research_snapshots(
                    captured_at, app_version, status, research_score,
                    mandatory_passed, mandatory_total, failed_mandatory_count,
                    core_status, core_score, target_status, target_pass,
                    feature_incremental_oos, paper_trades, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    captured_at, app_version, snapshot["status"], snapshot["research_score"],
                    snapshot["mandatory_passed"], snapshot["mandatory_total"], snapshot["failed_mandatory_count"],
                    snapshot["core_status"], snapshot["core_score"], snapshot["target_status"], int(snapshot["target_pass"]),
                    int(snapshot["feature_incremental_oos"]), snapshot["paper_trades"],
                    json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            # Keep history bounded even on very long-running research deployments.
            self.conn.execute(
                "DELETE FROM research_snapshots WHERE id NOT IN (SELECT id FROM research_snapshots ORDER BY id DESC LIMIT 5000)"
            )
            self.conn.commit()
            row = dict(self.conn.execute("SELECT * FROM research_snapshots WHERE id=?", (cur.lastrowid,)).fetchone())
            row["payload"] = snapshot
            row["recorded"] = True
            return row

    def history(self, limit: int = 240) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM research_snapshots ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()
            out: list[dict[str, Any]] = []
            for row in reversed(rows):
                item = dict(row)
                try:
                    payload = json.loads(item.pop("payload_json") or "{}")
                except (TypeError, json.JSONDecodeError):
                    payload = {}
                item.update(payload)
                item["target_pass"] = bool(item.get("target_pass"))
                item["feature_incremental_oos"] = bool(item.get("feature_incremental_oos"))
                out.append(item)
            return out

    def report(self, limit: int = 240) -> dict[str, Any]:
        rows = self.history(limit)
        return {
            "summary": summarize_research_history(rows),
            "snapshots": rows,
            "mode": "RESEARCH_EVIDENCE_HISTORY",
            "paper_only": True,
            "real_execution_eligibility": False,
        }

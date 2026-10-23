from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .evidence_stability import evidence_stability_gate


_STAGE_RANK = {
    "DATA_BUILDING": 0,
    "EVIDENCE_BUILDING": 1,
    "SHADOW_VALIDATED": 2,
    "STRICT_PAPER_REVIEW_CANDIDATE": 3,
}

_LEVELS = (
    {
        "id": "L1_24H",
        "hours": 24,
        "min_snapshots": 8,
        "min_new_trades": 20,
        "min_total_trades": 120,
        "min_active_days": 1,
        "strict_rate": 75.0,
        "mandatory_rate": 75.0,
    },
    {
        "id": "L2_72H",
        "hours": 72,
        "min_snapshots": 18,
        "min_new_trades": 45,
        "min_total_trades": 150,
        "min_active_days": 3,
        "strict_rate": 80.0,
        "mandatory_rate": 80.0,
    },
    {
        "id": "L3_168H",
        "hours": 168,
        "min_snapshots": 35,
        "min_new_trades": 90,
        "min_total_trades": 200,
        "min_active_days": 6,
        "strict_rate": 85.0,
        "mandatory_rate": 85.0,
    },
)


def _dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _full_mandatory(row: dict[str, Any]) -> bool:
    total = _i(row.get("mandatory_total"))
    return total > 0 and _i(row.get("mandatory_passed")) >= total


def _regressions(rows: list[dict[str, Any]]) -> int:
    count = 0
    for prev, row in zip(rows, rows[1:]):
        if _STAGE_RANK.get(str(row.get("status")), -1) < _STAGE_RANK.get(str(prev.get("status")), -1):
            count += 1
        elif bool(prev.get("strict_pass")) and not bool(row.get("strict_pass")):
            count += 1
    return count


def _active_trade_days(rows: list[dict[str, Any]], baseline_trades: int) -> tuple[int, dict[str, int]]:
    """Count UTC calendar days where cumulative closed PAPER trades increased."""
    if not rows:
        return 0, {}
    per_day_last: dict[str, int] = {}
    for row in rows:
        ts = _dt(row.get("captured_at"))
        if not ts:
            continue
        per_day_last[ts.date().isoformat()] = max(per_day_last.get(ts.date().isoformat(), 0), _i(row.get("paper_trades")))
    active = 0
    prev = baseline_trades
    deltas: dict[str, int] = {}
    for day in sorted(per_day_last):
        last = per_day_last[day]
        delta = max(0, last - prev)
        deltas[day] = delta
        if delta > 0:
            active += 1
        prev = max(prev, last)
    return active, deltas


def _evaluate_level(rows: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        return {"id": config["id"], "passed": False, "failed_gates": ["history_available"], "gates": [], "metrics": {}}

    current = rows[-1]
    end = _dt(current.get("captured_at"))
    first = _dt(rows[0].get("captured_at"))
    span = (end - first).total_seconds() / 3600.0 if end and first else 0.0
    cutoff = end - timedelta(hours=config["hours"]) if end else None
    if cutoff:
        window = [r for r in rows if (_dt(r.get("captured_at")) or end) >= cutoff]
        earlier = [r for r in rows if (_dt(r.get("captured_at")) or end) <= cutoff]
        baseline = earlier[-1] if earlier else rows[0]
    else:
        window, baseline = rows, rows[0]

    total_trades = _i(current.get("paper_trades"))
    baseline_trades = _i(baseline.get("paper_trades"))
    new_trades = max(0, total_trades - baseline_trades)
    strict_rate = sum(1 for r in window if r.get("strict_pass")) / len(window) * 100.0 if window else 0.0
    mandatory_rate = sum(1 for r in window if _full_mandatory(r)) / len(window) * 100.0 if window else 0.0
    regressions = _regressions(window)
    active_days, daily_trade_deltas = _active_trade_days(window, baseline_trades)
    interlock = all(not bool(r.get("real_execution_eligibility", False)) for r in window)
    current_candidate = str(current.get("status")) == "STRICT_PAPER_REVIEW_CANDIDATE"
    current_strict = bool(current.get("strict_pass"))

    gates = [
        {"id":"span","passed":span >= config["hours"],"value":round(span,2),"requirement":f">= {config['hours']}h total evidence history"},
        {"id":"snapshot_density","passed":len(window) >= config["min_snapshots"],"value":len(window),"requirement":f">= {config['min_snapshots']} snapshots in the level window"},
        {"id":"new_trades","passed":new_trades >= config["min_new_trades"] and total_trades >= config["min_total_trades"],"value":{"new":new_trades,"total":total_trades},"requirement":f">= {config['min_new_trades']} new PAPER trades and >= {config['min_total_trades']} total"},
        {"id":"active_trade_days","passed":active_days >= config["min_active_days"],"value":{"active_days":active_days,"daily_deltas":daily_trade_deltas},"requirement":f"PAPER activity spread across >= {config['min_active_days']} UTC day buckets"},
        {"id":"current_unified","passed":current_candidate,"value":current.get("status"),"requirement":"Current Unified stage remains STRICT_PAPER_REVIEW_CANDIDATE"},
        {"id":"current_strict","passed":current_strict,"value":current.get("strict_status"),"requirement":"Current Strict Paper Review remains PASSED"},
        {"id":"strict_rate","passed":strict_rate >= config["strict_rate"],"value":round(strict_rate,2),"requirement":f"Strict Paper pass rate >= {config['strict_rate']:.0f}%"},
        {"id":"mandatory_rate","passed":mandatory_rate >= config["mandatory_rate"],"value":round(mandatory_rate,2),"requirement":f"Full Unified mandatory-gate pass rate >= {config['mandatory_rate']:.0f}%"},
        {"id":"no_regressions","passed":regressions == 0,"value":regressions,"requirement":"Zero Unified-stage or Strict PASS→BLOCKED regressions inside the level window"},
        {"id":"real_execution_interlock","passed":interlock,"value":"LOCKED" if interlock else "UNSAFE_FLAG","requirement":"Real execution eligibility stays false for the entire level window"},
    ]
    passed = all(g["passed"] for g in gates)
    return {
        "id": config["id"], "hours": config["hours"], "passed": passed,
        "gates": gates, "failed_gates": [g["id"] for g in gates if not g["passed"]],
        "metrics": {
            "span_hours": round(span,2), "snapshots": len(window), "new_paper_trades": new_trades,
            "total_paper_trades": total_trades, "active_trade_days": active_days,
            "strict_pass_rate_pct": round(strict_rate,2), "mandatory_pass_rate_pct": round(mandatory_rate,2),
            "regressions": regressions, "daily_trade_deltas": daily_trade_deltas,
        },
    }


def stability_ladder(history_report: dict[str, Any] | None) -> dict[str, Any]:
    history_report = history_report or {}
    rows = sorted(list(history_report.get("snapshots") or []), key=lambda r: (str(r.get("captured_at", "")), _i(r.get("id"))))
    short_gate = evidence_stability_gate(history_report)
    levels = [_evaluate_level(rows, cfg) for cfg in _LEVELS]
    # V1.27 remains the canonical L1 gate. Force L1 to fail if the canonical gate fails.
    if levels:
        levels[0]["canonical_v127_status"] = short_gate.get("status")
        if short_gate.get("status") != "STABILITY_WINDOW_PASSED":
            levels[0]["passed"] = False
            if "canonical_v127" not in levels[0]["failed_gates"]:
                levels[0]["failed_gates"].append("canonical_v127")

    highest = 0
    for idx, level in enumerate(levels, start=1):
        if level["passed"] and idx == highest + 1:
            highest = idx
        else:
            break

    statuses = {
        0: "MULTIDAY_STABILITY_BLOCKED",
        1: "STABILITY_24H_CONFIRMED",
        2: "STABILITY_72H_CONFIRMED",
        3: "STABILITY_7D_CONFIRMED",
    }
    next_stage = {
        0: "BUILD_24H_STABILITY",
        1: "BUILD_72H_STABILITY",
        2: "BUILD_7D_STABILITY",
        3: "EXTENDED_MULTI_WEEK_PAPER_OBSERVATION",
    }
    return {
        "status": statuses[highest], "highest_level": highest, "levels": levels,
        "next_stage": next_stage[highest],
        "paper_only": True, "automatic_real_execution": False,
        "real_execution_eligibility": False, "live_execution_enabled": False,
        "target_auto_apply": False, "score_is_authorization": False, "guarantee":"NONE",
        "policy": "The ladder measures persistence of PAPER/research evidence across 24h, 72h and 7d. Even L3 never authorizes real-money trading or automatic target changes.",
    }

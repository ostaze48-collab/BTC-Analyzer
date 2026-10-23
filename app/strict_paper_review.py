from __future__ import annotations

from collections import Counter
from statistics import fmean
from typing import Any

WINDOWS = (30, 60, 100)
MIN_ELIGIBLE = 100


def _metrics(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {
            "trades": 0, "mean_r": 0.0, "net_r": 0.0,
            "win_rate_pct": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0,
        }
    wins = [x for x in values if x > 0]
    losses = [x for x in values if x < 0]
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_win / gross_loss if gross_loss > 1e-12 else (10.0 if gross_win > 0 else 0.0)
    return {
        "trades": len(values),
        "mean_r": round(fmean(values), 4),
        "net_r": round(sum(values), 4),
        "win_rate_pct": round(len(wins) / len(values) * 100.0, 2),
        "profit_factor": round(min(10.0, pf), 4),
        "max_drawdown_r": round(max_dd, 4),
    }


def _eligible_rows(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    ordered = sorted(samples, key=lambda s: (str(s.get("opened_at", "")), int(s.get("trade_id", 0) or 0)))
    for sample in ordered:
        try:
            risk = float(sample.get("risk_budget", 0.0) or 0.0)
            pnl = float(sample.get("realized_pnl", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if risk <= 0:
            continue
        rows.append({
            "trade_id": int(sample.get("trade_id", 0) or 0),
            "r": pnl / risk,
            "brain": str(sample.get("brain") or "UNKNOWN"),
            "regime": str(sample.get("market_regime") or "UNKNOWN"),
            "opened_at": sample.get("opened_at"),
        })
    return rows


def _window_pass(size: int, metrics: dict[str, Any]) -> tuple[bool, str]:
    thresholds = {
        30: {"mean_r": 0.05, "pf": 1.10, "dd": 5.0},
        60: {"mean_r": 0.07, "pf": 1.15, "dd": 7.0},
        100: {"mean_r": 0.08, "pf": 1.20, "dd": 10.0},
    }[size]
    passed = (
        float(metrics.get("mean_r", 0.0)) >= thresholds["mean_r"]
        and float(metrics.get("profit_factor", 0.0)) >= thresholds["pf"]
        and float(metrics.get("max_drawdown_r", 999.0)) <= thresholds["dd"]
        and float(metrics.get("net_r", 0.0)) > 0
    )
    requirement = (
        f"Last {size} trades: Mean R >= {thresholds['mean_r']:.2f}, "
        f"PF >= {thresholds['pf']:.2f}, Max DD <= {thresholds['dd']:.1f}R, Net R > 0."
    )
    return passed, requirement


def strict_paper_review(
    unified_readiness: dict[str, Any] | None,
    samples: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Stress-test recent PAPER stability after V1.24 research readiness.

    The 30/60/100 windows overlap and therefore are *not* treated as independent
    OOS evidence. They are a degradation/stability diagnostic only. Passing this
    protocol never enables real-money execution or target auto-apply.
    """
    unified = unified_readiness or {}
    rows = _eligible_rows(samples or [])
    available = len(rows)

    windows: dict[str, dict[str, Any]] = {}
    gates: list[dict[str, Any]] = []
    for size in WINDOWS:
        subset = rows[-size:] if available >= size else rows[:]
        metrics = _metrics([float(r["r"]) for r in subset])
        enough = available >= size
        passed, requirement = _window_pass(size, metrics) if enough else (False, f"Need at least {size} eligible closed PAPER trades.")
        windows[str(size)] = {**metrics, "available": enough, "passed": passed, "requirement": requirement}
        gates.append({
            "id": f"window_{size}",
            "passed": passed,
            "value": metrics,
            "requirement": requirement,
        })

    long_mean = float((windows.get("100") or {}).get("mean_r", 0.0) or 0.0)
    recent_mean = float((windows.get("30") or {}).get("mean_r", 0.0) or 0.0)
    recent_decay_ok = available >= 100 and recent_mean > 0 and long_mean > 0 and recent_mean >= long_mean * 0.50
    gates.append({
        "id": "recent_decay",
        "passed": recent_decay_ok,
        "value": {"recent_30_mean_r": round(recent_mean, 4), "long_100_mean_r": round(long_mean, 4)},
        "requirement": "Recent 30-trade Mean R must stay positive and at least 50% of the 100-trade Mean R.",
    })

    unified_ok = unified.get("status") == "STRICT_PAPER_REVIEW_CANDIDATE" and bool(unified.get("strict_paper_review_allowed", False))
    gates.insert(0, {
        "id": "unified_readiness",
        "passed": unified_ok,
        "value": unified.get("status", "NOT_RUN"),
        "requirement": "V1.24 Unified Research Readiness must explicitly allow strict PAPER review.",
    })

    interlock_ok = (
        bool(unified.get("paper_only", True))
        and not bool(unified.get("live_execution_enabled", False))
        and not bool(unified.get("real_execution_eligibility", False))
        and not bool(unified.get("automatic_real_execution", False))
    )
    gates.append({
        "id": "paper_only_interlock",
        "passed": interlock_ok,
        "value": "LOCKED" if interlock_ok else "UNSAFE_FLAG",
        "requirement": "PAPER-only interlock must remain locked; real execution and eligibility must both be false.",
    })

    recent = rows[-100:]
    brain_counts = Counter(r["brain"] for r in recent)
    regime_counts = Counter(r["regime"] for r in recent)
    total_recent = max(1, len(recent))
    concentration = {
        "brain_share_pct": {k: round(v / total_recent * 100.0, 1) for k, v in sorted(brain_counts.items())},
        "regime_share_pct": {k: round(v / total_recent * 100.0, 1) for k, v in sorted(regime_counts.items())},
    }

    all_passed = all(g["passed"] for g in gates)
    status = "STRICT_PAPER_REVIEW_PASSED" if all_passed else "STRICT_PAPER_REVIEW_BLOCKED"

    return {
        "status": status,
        "eligible_samples": available,
        "minimum_samples": MIN_ELIGIBLE,
        "window_scheme": "OVERLAPPING_RECENT_30_60_100_DIAGNOSTIC",
        "independence_warning": "Overlapping windows are diagnostic only and are not independent OOS evidence.",
        "windows": windows,
        "gates": gates,
        "failed_gates": [g["id"] for g in gates if not g["passed"]],
        "concentration": concentration,
        "next_stage": "EXTENDED_PAPER_OBSERVATION" if all_passed else "CONTINUE_PAPER_COLLECTION",
        "paper_only": True,
        "strict_paper_protocol": True,
        "automatic_real_execution": False,
        "real_execution_eligibility": False,
        "live_execution_enabled": False,
        "target_auto_apply": False,
        "guarantee": "NONE",
        "policy": "Passing V1.25 only permits extended PAPER observation. It never authorizes real-money trading, live execution, or automatic target changes.",
    }

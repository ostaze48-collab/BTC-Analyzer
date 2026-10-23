from __future__ import annotations

from typing import Any


def summarize_analog_validation(edge_report: dict[str, Any], incremental_report: dict[str, Any]) -> dict[str, Any]:
    edge_rows = [
        r for r in (edge_report.get("candidates") or edge_report.get("diversified_top") or [])
        if str(r.get("source", "")).startswith("ANALOG") or str(r.get("feature", "")).startswith("analog.")
    ]
    incremental_rows = [
        r for r in (incremental_report.get("eligible") or [])
        if str(r.get("source", "")).startswith("ANALOG") or str(r.get("feature", "")).startswith("analog.")
    ]

    samples = max(int(edge_report.get("samples", 0) or 0), int(incremental_report.get("samples", 0) or 0))
    if samples < 45:
        status = "INSUFFICIENT_DATA"
        useful = False
    elif incremental_rows:
        status = "INCREMENTAL_EDGE_DETECTED"
        useful = True
    elif edge_rows:
        status = "CORRELATION_ONLY"
        useful = False
    else:
        status = "NO_PROVEN_EDGE"
        useful = False

    return {
        "status": status,
        "samples": samples,
        "useful_for_master": useful,
        "master_weight": 0.0,
        "edge_candidates": edge_rows[:10],
        "incremental_candidates": incremental_rows[:10],
        "policy": "Historical analog evidence remains shadow-only until it improves forward blocks versus baseline without unacceptable drawdown.",
    }

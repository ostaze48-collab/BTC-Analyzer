from __future__ import annotations

from statistics import fmean
from typing import Any


def build_historical_target_advisor(matches: list[dict[str, Any]], quality: str = "WEAK") -> dict[str, Any]:
    """Rank terminal targets 1R..5R from matched historical paths.

    This is a SHADOW research layer. A target is considered a historical win when
    the matched path reached that R before its eventual stop. Unresolved/expired
    paths receive a small conservative penalty rather than being counted as wins.
    Laplace smoothing reduces overconfidence in small samples.
    """
    n = len(matches)
    if n < 8:
        return {
            "status": "INSUFFICIENT_MATCHES",
            "mode": "SHADOW_ONLY",
            "weight_in_risk_engine": 0.0,
            "matches": n,
            "recommended_r": None,
            "targets": [],
        }

    rows: list[dict[str, Any]] = []
    for target_r in range(1, 6):
        hits = sum(1 for m in matches if float(m.get("max_r", 0.0) or 0.0) >= target_r)
        losses = sum(
            1 for m in matches
            if float(m.get("max_r", 0.0) or 0.0) < target_r and bool(m.get("stopped"))
        )
        unresolved = max(0, n - hits - losses)

        # Smoothed probabilities; unresolved paths are explicitly visible and
        # penalized slightly so distant targets are not rewarded by censoring.
        p_hit = (hits + 1.0) / (n + 2.0)
        p_loss = (losses + 1.0) / (n + 2.0)
        unresolved_rate = unresolved / n
        raw_ev = p_hit * target_r - p_loss
        conservative_ev = raw_ev - unresolved_rate * 0.08 * target_r

        rows.append({
            "target_r": float(target_r),
            "hits": hits,
            "losses": losses,
            "unresolved": unresolved,
            "hit_pct": round(hits / n * 100.0, 2),
            "loss_pct": round(losses / n * 100.0, 2),
            "unresolved_pct": round(unresolved_rate * 100.0, 2),
            "smoothed_hit_pct": round(p_hit * 100.0, 2),
            "conservative_ev_r": round(conservative_ev, 4),
        })

    best = max(rows, key=lambda r: (r["conservative_ev_r"], -r["target_r"]))
    avg_mfe = fmean(float(m.get("mfe_r", 0.0) or 0.0) for m in matches)
    avg_mae = fmean(float(m.get("mae_r", 0.0) or 0.0) for m in matches)

    evidence_strength = "STRONG" if n >= 18 and quality == "STRONG" else ("MODERATE" if n >= 12 else "WEAK")
    status = "POSITIVE_SHADOW_EDGE" if float(best["conservative_ev_r"]) > 0.10 else "NO_POSITIVE_SHADOW_EDGE"

    return {
        "status": status,
        "mode": "SHADOW_ONLY",
        "weight_in_risk_engine": 0.0,
        "matches": n,
        "quality": quality,
        "evidence_strength": evidence_strength,
        "recommended_r": best["target_r"] if status == "POSITIVE_SHADOW_EDGE" else None,
        "best_conservative_ev_r": best["conservative_ev_r"],
        "recommended_hit_pct": best["hit_pct"],
        "avg_mfe_r": round(avg_mfe, 3),
        "avg_mae_r": round(avg_mae, 3),
        "targets": rows,
        "policy": "Research only: target recommendation does not alter live/paper execution until incremental OOS replay proves improvement.",
    }

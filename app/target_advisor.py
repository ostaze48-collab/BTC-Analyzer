from __future__ import annotations

from statistics import fmean
from typing import Any


def _empty(status: str, matches: int = 0) -> dict[str, Any]:
    return {
        "status": status,
        "mode": "SHADOW_ONLY",
        "weight_in_risk_engine": 0.0,
        "matches": matches,
        "recommended_r": None,
        "targets": [],
    }


def _finish(rows: list[dict[str, Any]], matches: int, quality: str, avg_mfe_r: float, avg_mae_r: float) -> dict[str, Any]:
    if not rows:
        return _empty("INSUFFICIENT_MATCHES", matches)
    best = max(rows, key=lambda r: (float(r["conservative_ev_r"]), -float(r["target_r"])))
    evidence_strength = "STRONG" if matches >= 18 and quality == "STRONG" else ("MODERATE" if matches >= 12 else "WEAK")
    status = "POSITIVE_SHADOW_EDGE" if float(best["conservative_ev_r"]) > 0.10 else "NO_POSITIVE_SHADOW_EDGE"
    return {
        "status": status,
        "mode": "SHADOW_ONLY",
        "weight_in_risk_engine": 0.0,
        "matches": matches,
        "quality": quality,
        "evidence_strength": evidence_strength,
        "recommended_r": best["target_r"] if status == "POSITIVE_SHADOW_EDGE" else None,
        "best_conservative_ev_r": best["conservative_ev_r"],
        "recommended_hit_pct": best["hit_pct"],
        "avg_mfe_r": round(avg_mfe_r, 3),
        "avg_mae_r": round(avg_mae_r, 3),
        "targets": rows,
        "policy": "Research only: target recommendation does not alter paper/live execution until a full incremental OOS replay proves improvement.",
    }


def build_historical_target_advisor(matches: list[dict[str, Any]], quality: str = "WEAK") -> dict[str, Any]:
    """Rank 1R..5R from raw matched historical paths.

    This helper is used in tests/research when raw paths are available. Expired
    paths are penalized rather than silently treated as wins.
    """
    n = len(matches)
    if n < 8:
        return _empty("INSUFFICIENT_MATCHES", n)

    rows: list[dict[str, Any]] = []
    for target_r in range(1, 6):
        hits = sum(1 for m in matches if float(m.get("max_r", 0.0) or 0.0) >= target_r)
        losses = sum(1 for m in matches if float(m.get("max_r", 0.0) or 0.0) < target_r and bool(m.get("stopped")))
        unresolved = max(0, n - hits - losses)
        p_hit = (hits + 1.0) / (n + 2.0)
        p_loss = (losses + 1.0) / (n + 2.0)
        unresolved_rate = unresolved / n
        conservative_ev = p_hit * target_r - p_loss - unresolved_rate * 0.08 * target_r
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

    avg_mfe = fmean(float(m.get("mfe_r", 0.0) or 0.0) for m in matches)
    avg_mae = fmean(float(m.get("mae_r", 0.0) or 0.0) for m in matches)
    return _finish(rows, n, quality, avg_mfe, avg_mae)


def build_historical_target_advisor_from_summary(analog: dict[str, Any] | None) -> dict[str, Any]:
    """Rank 1R..5R from the full Historical Analog summary.

    The analog engine exposes hit rates calculated from all selected matches.
    To avoid optimistic assumptions when exact path ordering is not exported,
    every non-hit is treated as a full -1R loss. This deliberately understates
    distant targets and makes 4R/5R hard to recommend without strong evidence.
    """
    analog = analog or {}
    n = int(analog.get("matches", 0) or 0)
    if analog.get("status") != "READY" or n < 8:
        return _empty("INSUFFICIENT_MATCHES", n)

    quality = str(analog.get("quality", "WEAK"))
    rows: list[dict[str, Any]] = []
    for target_r in range(1, 6):
        hit_pct = float(analog.get(f"hit_{target_r}r_pct", 0.0) or 0.0)
        hit_pct = max(0.0, min(100.0, hit_pct))
        estimated_hits = hit_pct / 100.0 * n
        # Laplace-smoothed hit probability. All non-hits are counted as losses.
        p_hit = (estimated_hits + 1.0) / (n + 2.0)
        p_loss = 1.0 - p_hit
        conservative_ev = p_hit * target_r - p_loss
        rows.append({
            "target_r": float(target_r),
            "hit_pct": round(hit_pct, 2),
            "loss_pct": round(100.0 - hit_pct, 2),
            "unresolved_pct": 0.0,
            "smoothed_hit_pct": round(p_hit * 100.0, 2),
            "conservative_ev_r": round(conservative_ev, 4),
            "assumption": "ALL_NON_HITS_ARE_-1R",
        })

    return _finish(
        rows,
        n,
        quality,
        float(analog.get("avg_mfe_r", 0.0) or 0.0),
        float(analog.get("avg_mae_r", 0.0) or 0.0),
    )

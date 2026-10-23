from __future__ import annotations

import asyncio
import time
from typing import Any

from .historical_analogs import analyze_historical_analogs

BRAINS = ("SCALP", "INTRADAY", "SWING")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _brain_regime_history(learning: dict[str, Any], brain: str, regime: str) -> dict[str, Any]:
    row = next((x for x in (learning.get("brain_regime") or []) if str(x.get("brain")) == brain and str(x.get("regime")) == regime), None)
    if not row:
        return {"status": "NO_SAMPLE", "trades": 0}
    trades = int(row.get("trades", 0) or 0)
    return {
        "status": "READY" if trades >= 5 else "SMALL_SAMPLE", "trades": trades,
        "win_rate": _num(row.get("win_rate")), "profit_factor": _num(row.get("profit_factor")),
        "net_pnl": _num(row.get("net_pnl")), "avg_mfe_pct": _num(row.get("avg_mfe_pct")),
        "avg_mae_pct": _num(row.get("avg_mae_pct")),
    }


def _shadow_score(proposal: dict[str, Any], analog: dict[str, Any], history: dict[str, Any]) -> dict[str, Any]:
    if proposal.get("direction") not in ("LONG", "SHORT"):
        return {"score": 0.0, "grade": "WAIT", "master_weight": 0.0}
    components: list[tuple[float, float]] = []
    if analog.get("status") == "READY":
        matches = max(0, int(analog.get("matches", 0) or 0)); sample = min(1.0, matches / 18.0)
        hit2 = _num(analog.get("hit_2r_pct")); hit3 = _num(analog.get("hit_3r_pct"))
        stop = _num(analog.get("stop_before_1r_pct")); similarity = _num(analog.get("avg_similarity_pct"))
        raw = hit2 * 0.35 + hit3 * 0.25 + (100.0 - stop) * 0.25 + similarity * 0.15
        components.append((max(0.0, min(100.0, 50.0 + (raw - 50.0) * sample)), 0.55))
    if history.get("status") in ("READY", "SMALL_SAMPLE") and history.get("trades", 0):
        trades = int(history.get("trades", 0)); sample = min(1.0, trades / 30.0); pf = min(3.0, _num(history.get("profit_factor")))
        raw = _num(history.get("win_rate")) * 0.60 + min(100.0, pf / 2.0 * 100.0) * 0.40
        components.append((max(0.0, min(100.0, 50.0 + (raw - 50.0) * sample)), 0.20))
    safety = _num(proposal.get("safety_score")); confidence = _num(proposal.get("confidence"))
    components.append((max(0.0, min(100.0, safety * 0.65 + confidence * 0.35)), 0.25))
    score = sum(v * w for v, w in components) / sum(w for _, w in components) if components else 0.0
    grade = "A" if score >= 78 else ("B" if score >= 66 else ("C" if score >= 54 else "D"))
    return {"score": round(score, 2), "grade": grade, "master_weight": 0.0}


def build_candidate_row(proposal: dict[str, Any], analog: dict[str, Any], learning: dict[str, Any], regime: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    brain = str(proposal.get("brain", "")); hist = _brain_regime_history(learning, brain, str(regime.get("regime", "UNKNOWN"))); shadow = _shadow_score(proposal, analog, hist)
    return {
        "brain": brain, "direction": proposal.get("direction"), "anchor": proposal.get("anchor"),
        "risk_gate": proposal.get("risk_gate"), "confidence": proposal.get("confidence"),
        "safety_score": proposal.get("safety_score"), "profit_score": proposal.get("profit_score"),
        "final_score": proposal.get("final_score"), "rr": proposal.get("rr"), "ev_pct": proposal.get("ev_pct"),
        "entry": proposal.get("entry"), "stop_loss": proposal.get("stop_loss"),
        "tp1": proposal.get("tp1"), "tp2": proposal.get("tp2"), "tp3": proposal.get("tp3"),
        "analog": analog, "brain_regime_history": hist, "archive": archive,
        "evidence_score": shadow["score"], "evidence_grade": shadow["grade"], "master_weight": 0.0,
    }


class CandidateEvidenceMatrix:
    """Background historical evidence for all three brains; shadow-only."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds; self._last_at = 0.0; self._last_key: tuple[Any, ...] | None = None; self._task: asyncio.Task | None = None
        self.state: dict[str, Any] = {"status": "BOOTING", "mode": "ALL_BRAINS_SHADOW", "master_weight": 0.0, "brains": {}}

    def _key(self, proposals: list[dict[str, Any]], regime: dict[str, Any], archives: dict[str, dict[str, Any]]) -> tuple[Any, ...]:
        proposal_key = tuple((p.get("brain"), p.get("direction"), p.get("anchor"), round(_num(p.get("risk_pct")), 2), round(_num(p.get("final_score")), 1)) for p in proposals)
        archive_key = tuple((b, (archives.get(b) or {}).get("status"), int((archives.get(b) or {}).get("bars_loaded", 0) or 0)) for b in BRAINS)
        return (str(regime.get("regime", "")), proposal_key, archive_key)

    def should_refresh(self, proposals: list[dict[str, Any]], regime: dict[str, Any], archives: dict[str, dict[str, Any]], force: bool = False) -> bool:
        if self._task and not self._task.done():
            return False
        key = self._key(proposals, regime, archives)
        if force:
            return True
        return not (key == self._last_key and time.monotonic() - self._last_at < self.ttl_seconds)

    def schedule(
        self, proposals: list[dict[str, Any]], snapshots: dict[str, dict[str, Any]], layers: dict[str, Any],
        regime: dict[str, Any], histories: dict[str, dict[str, list[dict[str, Any]]]], archives: dict[str, dict[str, Any]],
        learning: dict[str, Any], broadcaster=None, force: bool = False,
    ) -> dict[str, Any]:
        key = self._key(proposals, regime, archives); now = time.monotonic()
        if not force and key == self._last_key and now - self._last_at < self.ttl_seconds: return self.state
        if self._task and not self._task.done(): return self.state
        if not proposals:
            self.state = {"status": "NO_BRAIN_PROPOSALS", "mode": "ALL_BRAINS_SHADOW", "master_weight": 0.0, "brains": {}}; self._last_key, self._last_at = key, now; return self.state

        async def runner():
            rows: dict[str, Any] = {}
            for p in proposals:
                brain = str(p.get("brain"))
                if p.get("direction") in ("LONG", "SHORT"):
                    try:
                        analog = await asyncio.to_thread(analyze_historical_analogs, p, snapshots, layers, regime, histories.get(brain, {}))
                    except Exception as exc:
                        analog = {"status": "ERROR", "error": str(exc)[:160], "matches": 0, "weight_in_master": 0.0}
                else:
                    analog = {"status": "NO_DIRECTIONAL_SETUP", "matches": 0, "weight_in_master": 0.0}
                rows[brain] = build_candidate_row(p, analog, learning, regime, archives.get(brain, {}))
            for brain in BRAINS:
                rows.setdefault(brain, build_candidate_row({"brain": brain, "direction": "WAIT", "risk_gate": "REJECTED"}, {"status": "NO_PROPOSAL", "matches": 0}, learning, regime, archives.get(brain, {})))
            eligible = [r for r in rows.values() if r.get("direction") in ("LONG", "SHORT")]
            ordered = sorted(eligible, key=lambda r: (r.get("evidence_score", 0), r.get("final_score", 0)), reverse=True)
            self.state = {
                "status": "READY", "mode": "ALL_BRAINS_SHADOW", "master_weight": 0.0, "regime": regime.get("regime"),
                "brains": rows, "evidence_ranking": [r["brain"] for r in ordered],
                "best_historical_candidate": ordered[0]["brain"] if ordered else None,
                "warning": "Research ranking only. It does not override MASTER until full OOS incremental validation passes.",
            }
            self._last_key, self._last_at = key, time.monotonic()
            if broadcaster:
                try: await broadcaster({"type": "candidate_evidence", "candidate_evidence": self.state})
                except Exception: pass

        self.state = {"status": "LOADING", "mode": "ALL_BRAINS_SHADOW", "master_weight": 0.0, "brains": self.state.get("brains", {})}
        self._task = asyncio.create_task(runner(), name="candidate-evidence-matrix"); return self.state

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try: await self._task
            except asyncio.CancelledError: pass

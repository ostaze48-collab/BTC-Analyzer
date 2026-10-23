from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .analog_validation import summarize_analog_validation
from .backtest import BacktestEngine
from .config import settings
from .cycle_walkforward import CycleWalkForward
from .db import Database
from .edge_lab import analyze_feature_edge
from .engine import TradingEngine
from .extended_paper_observation import extended_paper_observation
from .full_target_walkforward import run_full_target_walkforward
from .incremental_edge import incremental_walkforward
from .live_shadow_target import validate_live_shadow_target
from .readiness import readiness_report
from .strict_paper_review import strict_paper_review
from .target_advisor import build_historical_target_advisor_from_summary
from .target_evidence_gate import target_evidence_gate
from .target_policy_validation import validate_target_policy
from .unified_readiness import unified_research_readiness
from .version import APP_LABEL, APP_NAME, APP_VERSION


class Hub:
    def __init__(self):
        self.clients: set[WebSocket] = set()
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            self.clients.discard(ws)

    async def broadcast(self, payload: dict):
        dead = []
        async with self.lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self.lock:
                for ws in dead:
                    self.clients.discard(ws)


db = Database()
hub = Hub()
engine: TradingEngine | None = None
backtester = BacktestEngine()
cycle_validator = CycleWalkForward()
last_execution_replay: dict[str, Any] | None = None
full_target_results: dict[str, dict[str, Any]] = {}
full_target_running: set[str] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    db.init()
    engine = TradingEngine(db, hub.broadcast)
    await engine.start()
    yield
    await engine.stop()


app = FastAPI(title=f"{APP_NAME} {APP_LABEL}", version=APP_VERSION, lifespan=lifespan)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def home():
    return FileResponse(static_dir / "index.html")


@app.get("/health")
async def health():
    return {
        "ok": True,
        "service": f"{APP_NAME} {APP_LABEL}",
        "version": APP_VERSION,
        "version_label": APP_LABEL,
        "market_connected": bool(engine and engine.market.connected),
        "backtest_running": backtester.running,
        "cycle_validation_running": cycle_validator.running,
        "paper_only": True,
        "real_execution_enabled": False,
        "timeframes": list(settings.intervals),
        "analysis_horizon": "1m→1y",
        "learning_journal": True,
        "feature_factory": True,
        "feature_edge_lab": True,
        "incremental_walkforward": True,
        "historical_analogs": True,
        "historical_analogs_mode": "SHADOW_ONLY",
        "analog_edge_validation": True,
        "historical_target_advisor": True,
        "historical_target_advisor_mode": "SHADOW_ONLY",
        "historical_target_range_r": [1, 5],
        "target_policy_validation": True,
        "target_policy_validation_mode": "JOURNAL_PATH_PARTIAL_VALIDATION",
        "full_target_walkforward": True,
        "full_target_walkforward_mode": "FULL_ARCHIVE_TARGET_WALKFORWARD",
        "live_shadow_target": True,
        "live_shadow_target_mode": "FROZEN_ENTRY_LIVE_SHADOW",
        "target_evidence_gate": True,
        "target_evidence_gate_mode": "RESEARCH_PROMOTION_ONLY",
        "unified_research_readiness": True,
        "unified_readiness_mode": "HARD_GATE_AGGREGATION",
        "strict_paper_review": True,
        "strict_paper_review_mode": "OVERLAPPING_30_60_100_DIAGNOSTIC",
        "extended_paper_observation": True,
        "extended_paper_observation_mode": "PERSISTED_20_TRADE_CHECKPOINTS",
        "target_policy_auto_apply": False,
        "long_historical_memory": True,
        "historical_archive_mode": "LAZY_SHADOW_ONLY",
        "historical_signature_cache": True,
        "signature_target_candidates": 720,
        "signature_cache_mode": "BACKGROUND_SHADOW_ONLY",
        "feature_auto_promotion": False,
        "cycle_models": True,
        "readiness_gate": True,
        "network_intelligence": "SHADOW_ONLY",
        "derivatives_intelligence": "SHADOW_ONLY",
        "long_daily_history": True,
        "adaptive_risk": True,
        "max_paper_leverage": settings.max_paper_leverage,
        "max_total_drawdown_pct": settings.max_total_drawdown * 100,
        "soft_pause_drawdown_pct": settings.soft_pause_drawdown * 100,
        "profit_target_range_r": [1, 5],
    }


@app.get("/api/version")
async def api_version():
    return {"name": APP_NAME, "version": APP_VERSION, "label": APP_LABEL}


@app.get("/api/state")
async def api_state():
    state = engine.state()
    state["readiness"] = _readiness()
    state["historical_target_advisor"] = build_historical_target_advisor_from_summary(engine.historical_analogs)
    state["app_version"] = APP_VERSION
    state["app_version_label"] = APP_LABEL
    return state


def _readiness() -> dict[str, Any]:
    cycle_primary = (cycle_validator.last_result or {}).get("primary") or {}
    exec_evidence: dict[str, Any] = {}
    if last_execution_replay:
        metrics = dict(last_execution_replay.get("metrics") or {})
        exec_evidence = {**metrics, "validation_type": "SHORT_WINDOW_REPLAY"}
    return readiness_report(db.stats(), db.learning_summary(), exec_evidence, cycle_primary)


def _unified_snapshot(limit: int = 5000) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    safe_limit = max(1, min(int(limit), 20000))
    samples = db.edge_samples(safe_limit)
    trades = db.recent_trades(safe_limit)
    edge = analyze_feature_edge(samples)
    incremental = incremental_walkforward(samples, max_features=500)
    live = validate_live_shadow_target(samples, trades)
    target_gate = target_evidence_gate(full_target_results, live)
    unified = unified_research_readiness(_readiness(), target_gate, edge, incremental)
    return unified, samples


def _strict_snapshot(limit: int = 5000) -> dict[str, Any]:
    unified, samples = _unified_snapshot(limit)
    return strict_paper_review(unified, samples)


@app.get("/api/readiness")
async def api_readiness():
    report = _readiness()
    report["cycle_validation"] = cycle_validator.last_result
    report["latest_execution_replay"] = last_execution_replay
    report["full_target_walkforward"] = full_target_results
    return report


@app.get("/api/edge-lab")
async def api_edge_lab(limit: int = 5000):
    samples = db.edge_samples(max(1, min(limit, 20000)))
    return analyze_feature_edge(samples)


@app.get("/api/incremental-edge")
async def api_incremental_edge(limit: int = 5000, max_features: int = 250):
    samples = db.edge_samples(max(1, min(limit, 20000)))
    return incremental_walkforward(samples, max_features=max(10, min(max_features, 1000)))


@app.get("/api/analog-validation")
async def api_analog_validation(limit: int = 5000):
    samples = db.edge_samples(max(1, min(limit, 20000)))
    edge = analyze_feature_edge(samples)
    incremental = incremental_walkforward(samples, max_features=500)
    return summarize_analog_validation(edge, incremental)


@app.get("/api/historical-analogs")
async def api_historical_analogs():
    return engine.historical_analogs


@app.get("/api/historical-target-advisor")
async def api_historical_target_advisor():
    return build_historical_target_advisor_from_summary(engine.historical_analogs)


@app.get("/api/target-policy-validation")
async def api_target_policy_validation(limit: int = 5000):
    safe_limit = max(1, min(limit, 20000))
    samples = db.edge_samples(safe_limit)
    trades = db.recent_trades(safe_limit)
    return validate_target_policy(samples, trades)


@app.get("/api/live-shadow-target")
async def api_live_shadow_target(limit: int = 5000):
    safe_limit = max(1, min(limit, 20000))
    samples = db.edge_samples(safe_limit)
    trades = db.recent_trades(safe_limit)
    return validate_live_shadow_target(samples, trades)


@app.get("/api/target-evidence-gate")
async def api_target_evidence_gate(limit: int = 5000):
    safe_limit = max(1, min(limit, 20000))
    samples = db.edge_samples(safe_limit)
    trades = db.recent_trades(safe_limit)
    live = validate_live_shadow_target(samples, trades)
    return target_evidence_gate(full_target_results, live)


@app.get("/api/unified-readiness")
async def api_unified_readiness(limit: int = 5000):
    unified, _ = _unified_snapshot(limit)
    return unified


@app.get("/api/strict-paper-review")
async def api_strict_paper_review(limit: int = 5000):
    return _strict_snapshot(limit)


@app.get("/api/extended-paper-observation")
async def api_extended_paper_observation(limit: int = 5000):
    current = _strict_snapshot(limit)
    history = db.review_snapshots(100)
    return extended_paper_observation(current, history)


@app.post("/api/extended-paper-observation/checkpoint")
async def api_record_extended_paper_checkpoint(limit: int = 5000):
    current = _strict_snapshot(limit)
    checkpoint = db.record_review_snapshot(current, min_trade_gap=20)
    history = db.review_snapshots(100)
    return {
        "checkpoint": checkpoint,
        "observation": extended_paper_observation(current, history),
    }


def _normalize_brain(brain: str) -> str:
    value = str(brain or "").upper()
    if value not in ("SCALP", "INTRADAY", "SWING"):
        raise HTTPException(400, "brain must be SCALP, INTRADAY or SWING")
    return value


@app.get("/api/full-target-walkforward")
async def api_full_target_walkforward(brain: str = "INTRADAY"):
    brain = _normalize_brain(brain)
    if brain in full_target_running:
        return {"status": "RUNNING", "brain": brain, "cached": full_target_results.get(brain)}
    result = full_target_results.get(brain)
    if result:
        return result
    archive = engine.historical_archive.state(brain)
    return {
        "status": "NOT_RUN", "brain": brain, "archive": archive,
        "mode": "FULL_ARCHIVE_TARGET_WALKFORWARD", "auto_apply": False,
        "weight_in_risk_engine": 0.0,
    }


@app.post("/api/full-target-walkforward")
async def api_run_full_target_walkforward(brain: str = "INTRADAY", max_points: int = 300):
    brain = _normalize_brain(brain)
    max_points = max(80, min(int(max_points), 600))
    if brain in full_target_running:
        return {"status": "RUNNING", "brain": brain, "cached": full_target_results.get(brain)}

    archive = engine.historical_archive.schedule(brain)
    if archive.get("status") not in ("READY", "PARTIAL"):
        return {
            "status": "ARCHIVE_LOADING", "brain": brain, "archive": archive,
            "message": "Deep history is loading in the background. Run again after archive status becomes READY/PARTIAL.",
            "auto_apply": False, "weight_in_risk_engine": 0.0,
        }

    full_target_running.add(brain)
    try:
        history = engine._history_for_analogs(brain)
        result = await asyncio.to_thread(run_full_target_walkforward, history, brain, max_points)
        result["archive"] = engine.historical_archive.state(brain)
        full_target_results[brain] = result
        return result
    finally:
        full_target_running.discard(brain)


@app.get("/api/historical-archive")
async def api_historical_archive(brain: str | None = None):
    if brain:
        return engine.historical_archive.state(brain.upper())
    return {
        "current": engine.archive_state,
        "brains": {
            name: engine.historical_archive.state(name)
            for name in ("SCALP", "INTRADAY", "SWING")
        },
        "mode": "LAZY_SHADOW_ONLY",
        "weight_in_master": 0.0,
    }


@app.get("/api/network")
async def api_network(refresh: bool = False):
    if refresh:
        return await engine.network_source.refresh_if_due(force=True)
    return engine.network


@app.get("/api/derivatives")
async def api_derivatives(refresh: bool = False):
    if refresh:
        return await engine.derivatives_source.refresh_if_due(force=True)
    return engine.derivatives


@app.get("/api/learning")
async def api_learning():
    return db.learning_summary()


@app.get("/api/candles/{interval}")
async def api_candles(interval: str, limit: int = 500):
    if interval not in settings.intervals:
        raise HTTPException(400, f"Unsupported interval: {interval}")
    return engine.market.get(interval, max(8, min(limit, 500)))


@app.get("/api/trades")
async def api_trades(limit: int = 50):
    return db.recent_trades(max(1, min(limit, 200)))


@app.post("/api/backtest")
async def api_backtest(days: int = 3):
    global last_execution_replay
    if days not in (1, 3, 7, 14):
        raise HTTPException(400, "days must be one of: 1, 3, 7, 14")
    try:
        result = await backtester.run(days)
        result["validation_type"] = "SHORT_WINDOW_REPLAY"
        last_execution_replay = result
        return result
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/cycle-validation")
async def api_cycle_validation(years: int = 6):
    if years not in (3, 4, 5, 6, 7, 8, 9):
        raise HTTPException(400, "years must be between 3 and 9")
    try:
        return await cycle_validator.run(years)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.post("/api/reset")
async def api_reset():
    try:
        return engine.reset()
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        await ws.send_json({"type": "state", "state": engine.state()})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)
    except Exception:
        await hub.disconnect(ws)

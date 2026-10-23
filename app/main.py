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
from .incremental_edge import incremental_walkforward
from .readiness import readiness_report
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


@app.get("/api/readiness")
async def api_readiness():
    report = _readiness()
    report["cycle_validation"] = cycle_validator.last_result
    report["latest_execution_replay"] = last_execution_replay
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

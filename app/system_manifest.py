from __future__ import annotations

from .version import APP_LABEL, APP_VERSION

UI_LAYERS = (
    "app.js", "structure.js", "patterns.js", "learning.js", "backtest.js",
    "v18.js", "v19.js", "v20.js", "v21.js", "v22.js", "v23.js", "v24.js",
    "v25.js", "v26.js", "v27.js", "v28.js",
)

INTELLIGENCE_LAYERS = (
    "MULTI_TIMEFRAME_1M_TO_1Y",
    "THREE_BRAINS_MASTER",
    "MARKET_STRUCTURE",
    "PATTERN_ENGINE",
    "FEATURE_FACTORY",
    "CYCLE_VALUATION",
    "NETWORK_SHADOW",
    "DERIVATIVES_SHADOW",
    "ADAPTIVE_RISK_LEVERAGE",
    "FEATURE_EDGE_LAB",
    "INCREMENTAL_WALKFORWARD",
    "HISTORICAL_SETUP_MEMORY",
    "ANALOG_EDGE_VALIDATION",
    "LONG_HISTORICAL_ARCHIVE",
    "ALL_BRAINS_CANDIDATE_EVIDENCE",
)


def manifest() -> dict:
    return {
        "version": APP_VERSION,
        "label": APP_LABEL,
        "ui_layers": list(UI_LAYERS),
        "intelligence_layers": list(INTELLIGENCE_LAYERS),
        "paper_only": True,
        "real_execution_enabled": False,
        "sync_policy": "LOGIC_REPLAY_JOURNAL_API_UI_TESTS_VERSION_TOGETHER",
    }

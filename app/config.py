import os
from dataclasses import dataclass


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    symbol: str = os.getenv("BTC_SYMBOL", "BTCUSDT").upper()

    native_intervals: tuple[str, ...] = (
        "1m", "3m", "5m", "15m", "30m",
        "1h", "2h", "4h", "6h", "8h", "12h",
        "1d", "3d", "1w", "1M",
    )
    synthetic_intervals: tuple[str, ...] = ("3M", "6M", "1y")
    intervals: tuple[str, ...] = native_intervals + synthetic_intervals

    micro_intervals: tuple[str, ...] = ("1m", "3m", "5m")
    intraday_intervals: tuple[str, ...] = ("15m", "30m", "1h", "2h")
    swing_intervals: tuple[str, ...] = ("4h", "6h", "8h", "12h", "1d", "3d")
    macro_intervals: tuple[str, ...] = ("1w", "1M", "3M", "6M", "1y")
    history_limit: int = 500
    history_min_bars: dict[str, int] | None = None

    paper_start_capital: float = _f("PAPER_START_CAPITAL", 1000.0)
    # Legacy baseline retained for compatibility; V1.12 uses adaptive risk engine.
    risk_per_trade: float = _f("RISK_PER_TRADE", 0.0075)
    max_risk_per_trade: float = _f("MAX_RISK_PER_TRADE", 0.014)
    paper_fee_rate: float = _f("PAPER_FEE_RATE", 0.001)
    max_paper_leverage: int = max(1, min(5, _i("MAX_PAPER_LEVERAGE", 5)))

    # Portfolio protection: hard loss limit 25% from starting capital.
    # New entries stop earlier at 23% to preserve a buffer before the hard floor.
    max_total_drawdown: float = min(0.25, max(0.05, _f("MAX_TOTAL_DRAWDOWN", 0.25)))
    soft_pause_drawdown: float = min(max_total_drawdown - 0.005, max(0.05, _f("SOFT_PAUSE_DRAWDOWN", 0.23)))

    min_confidence: float = _f("MIN_CONFIDENCE", 65.0)
    min_safety_score: float = _f("MIN_SAFETY_SCORE", 68.0)
    min_rr: float = _f("MIN_RR", 1.5)
    max_stop_pct: float = _f("MAX_STOP_PCT", 2.5)

    rest_bases: tuple[str, ...] = (
        "https://data-api.binance.vision",
        "https://api.binance.com",
        "https://api1.binance.com",
    )
    ws_bases: tuple[str, ...] = (
        "wss://data-stream.binance.vision",
        "wss://stream.binance.com:9443",
    )

    db_path: str = os.getenv("BTC_AI_DB", "btc_ai_v1.sqlite3")

    def min_bars(self, interval: str) -> int:
        defaults = {
            "1m": 200, "3m": 200, "5m": 200, "15m": 200, "30m": 200,
            "1h": 200, "2h": 200, "4h": 200, "6h": 200, "8h": 200, "12h": 200,
            "1d": 200, "3d": 120, "1w": 80, "1M": 36, "3M": 20, "6M": 12, "1y": 8,
        }
        return defaults.get(interval, 30)


settings = Settings()

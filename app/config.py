import os
from dataclasses import dataclass


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    symbol: str = os.getenv("BTC_SYMBOL", "BTCUSDT").upper()
    intervals: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h")
    history_limit: int = 500

    paper_start_capital: float = _f("PAPER_START_CAPITAL", 1000.0)
    risk_per_trade: float = _f("RISK_PER_TRADE", 0.0075)
    paper_fee_rate: float = _f("PAPER_FEE_RATE", 0.001)

    min_confidence: float = _f("MIN_CONFIDENCE", 65.0)
    min_safety_score: float = _f("MIN_SAFETY_SCORE", 68.0)
    min_rr: float = _f("MIN_RR", 1.5)
    max_stop_pct: float = _f("MAX_STOP_PCT", 2.5)

    # Official Binance public market-data endpoints. No API key is used.
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


settings = Settings()

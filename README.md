# BTC Analyzer V1.2

Fixes:
- Spot market data now uses Binance's public market-data-only endpoint:
  https://data-api.binance.vision
- api.binance.com kept only as fallback.
- Futures data is optional: a Futures HTTP 451 no longer stops the analyzer.
- /diag exposes data_provider and futures status.
- Dashboard remains embedded in app.py.

Render:
- Environment: Docker
- Root Directory: blank
- Health path: /health

No real trading. Research/Paper only.

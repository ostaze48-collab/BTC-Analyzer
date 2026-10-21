# BTC Analyzer V1.3

## New in V1.3
- 1Y / 6M / 3M are rolling macro-context analyses built from the last 365 / 180 / 90 daily candles.
- Soft Warnings are separated from Strong Veto.
- New SETUP state: NO_BIAS / FORMING / READY / BLOCKED.
- New TRIGGER state: NOT_READY / READY / TRIGGERED / BLOCKED.
- Dashboard explains WHY WAIT and WHAT WE ARE WAITING FOR.
- Paper signals are still generated only for actual LONG/SHORT actions.
- Binance public market-data endpoint remains the primary Spot source.
- Futures remains optional and cannot stop the entire analyzer.

## Important
V1.3 is a research/paper-trading system. It does not place real trades.

## Render
Environment: Docker
Root Directory: blank
Health path: /health
After upload use: Manual Deploy -> Clear build cache & deploy

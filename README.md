# BTC Analyzer V1.6 — Bitcoin Context Engine

## Always available without another API
- Mayer Multiple from Binance daily SMA200.
- 200-week moving average and distance from it.

## Optional Bitbo API
Set the Render environment variable:

BITBO_API_KEY=your_key_here

The key must stay in Render Environment and must not be committed to GitHub.

V1.6 requests only five Bitbo endpoints:
- realized-price
- mvrv
- nupl-ratio
- sopr
- etf-flows-new-btc

Refresh interval: 15 minutes.

## Decision role
Bitcoin Context is deliberately a small directional-permission tilt.
It cannot create a trade by itself and is not a hard veto.

## Research
`context_compare.db` stores SUPPORTIVE / NEUTRAL / HEADWIND context cases
and later measures aligned 1H and 4H outcomes. This is how we will decide
whether adding on-chain context actually improves the technical system.

All V1.5.1 functionality remains:
SCALP / INTRADAY / SWING, A/B/C/D confirmation comparison,
paper trading, research memory and persistent storage.

Research/Paper only. No live orders.

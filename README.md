# BTC Analyzer V1.5.1

Hotfix for V1.5.

## Fixed
- Converts NumPy boolean/float/integer scalar values to native Python values before JSON serialization.
- `overextended` is now a native Python bool.
- Research snapshot JSON uses a robust serializer.
- Engine snapshot JSON uses the same robust serializer.

This specifically fixes:
`Object of type bool is not JSON serializable`

All V1.5 functionality remains:
- SCALP / INTRADAY / SWING
- Higher-timeframe direction permission
- A/B/C/D scalp shadow comparison
- Confirmation cost / delay / missed setups
- Research memory and persistent storage support

Paper/Research only. No live trades.

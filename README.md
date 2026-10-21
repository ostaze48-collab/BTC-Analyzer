# BTC Analyzer V1.5

## New
- Three independent paper-analysis lanes:
  - SCALP: 5m setup + 1m execution, only when higher-timeframe direction permits it.
  - INTRADAY: 30m setup + 15m trigger with 1H/4H/1D context.
  - SWING: 1D/4H execution with 1W/3D/1D context.
- Direction Permission scores for LONG and SHORT.
- Parallel scalp shadow comparison:
  - A_BASE_5M
  - B_5M_3M
  - C_FULL_SYNC
  - D_5M_1M
- Tracks per-strategy:
  trades, win rate, profit factor, avg R, average trigger delay,
  confirmation cost, and missed setups.
- Separate paper performance for SCALP / INTRADAY / SWING.
- Persistent storage still supported with DATA_DIR=/var/data.

## Important
Research / paper only. No live orders.

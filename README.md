# BTC Analyzer V2.7 — Structure-Aware Execution & Pattern Validation

V2.7 builds on the V2.6 Price Action Engine. No new technical indicator is added.

## 1. Structure-Aware SL / TP

ATR is now a fallback, not the preferred execution geometry.

For each lane the decision engine first looks for trustworthy structural levels.

Possible stop sources:
- SUPPORT_ZONE
- RESISTANCE_ZONE
- UP_TRENDLINE
- DOWN_TRENDLINE
- SWING_SUPPORT
- SWING_RESISTANCE

A structural stop is accepted only when:
- it is on the correct side of the entry,
- the source has sufficient quality,
- the stop is not unrealistically tight,
- the stop is not excessively far for that lane.

If no valid structure exists, the system automatically uses:

`ATR_FALLBACK`

No artificial structural level is invented.

## 2. Structure-aware targets

Possible target sources:
- nearby opposing S/R zone
- opposing trendline
- swing support/resistance
- validated chart-pattern target
- R-multiple fallback

The Dashboard shows exactly where:
- SL
- TP1
- TP2

came from.

## 3. Pattern Validation Lifecycle

Classical pattern detection is no longer just a name.

Each chart-pattern candidate now receives a lifecycle state:

- CANDIDATE
- CONFIRMED
- RETESTED
- FAILED
- ACTIVE (for channel-type structures)

Examples:

Double Bottom:
- geometry first -> CANDIDATE
- close above neckline -> CONFIRMED
- breakout + later neckline test -> RETESTED
- break below pattern invalidation -> FAILED

The same concept is applied to:
- Double Top / Bottom
- H&S / Inverse H&S
- triangles
- wedges
- flags
- channels

## 4. Pattern targets

When a pattern is CONFIRMED or RETESTED, the engine can calculate a projected
target from its geometry.

A validated target may be used as a TP candidate only when:
- its direction matches the intended trade,
- it is beyond the entry in the correct direction,
- it is structurally meaningful.

CANDIDATE patterns are not allowed to supply a trade target.

## 5. Pattern weights are lifecycle-aware

Pattern evidence is weighted approximately as:

- FAILED: 0
- CANDIDATE: small weight
- ACTIVE: reduced weight
- CONFIRMED: full weight
- RETESTED: strongest validated weight

A pattern still cannot create a trade by itself.

## 6. Price Action veto remains conservative

One candle or one chart pattern cannot hard-veto a setup.

A strong PA veto still requires meaningful opposition from at least two
independent Price Action families.

## 7. Execution-plan research

Every main and Lane-Lab Paper trade now stores:

- plan_mode
- stop_source
- tp1_source
- tp2_source

The system compares actual closed-trade outcomes for:

- STRUCTURE_AWARE
- ATR_FALLBACK

Metrics:
- trades
- W/L
- Win Rate
- Net P&L
- Avg R
- Avg MFE
- Avg MAE
- Capture Efficiency

This allows later versions to determine from data whether structure-aware
execution actually improves results.

## 8. Existing principles retained

- one MAIN paper trade globally
- independent SCALP / INTRADAY / SWING Lane Lab
- Opportunity IDs
- closed-candle analysis
- MFE / MAE
- Experiment History
- Equity Curve / Drawdown / Expectancy
- Price Action is confluence, never a standalone trigger
- Market Regime remains research-only

## Persistent storage

Keep:

`DATA_DIR=/var/data`

with a Render Persistent Disk mounted at `/var/data`.

## Paper / Research only

No real orders are sent. Pattern recognition and projected targets are heuristic
technical-analysis tools, not guaranteed forecasts.

# BTC Analyzer V2.8 — FAST SCALP + Fixed $1,000 Capital

V2.8 adds a fourth trading lane while preserving the existing research methodology.
No new technical indicator is added.

## Permanent Paper Capital

The MAIN Paper account and all independent Lane-Lab accounts are fixed at:

`$1,000.00`

The Dashboard no longer provides a capital-change control.
The capital API also rejects manual changes.

When V2.8 starts on a persistent database whose ACTIVE experiment used another
starting balance, that experiment is archived once and a fresh $1,000 experiment
is created. Historical experiments are preserved.

If an old experiment had an open trade when the fixed-capital migration occurred,
that trade is stored as RESET with zero P&L rather than being misclassified as a
market win/loss.

Keep Render persistence enabled:

`DATA_DIR=/var/data`

## Four Trading Lanes

V2.8 measures:

1. FAST_SCALP
2. SCALP
3. INTRADAY
4. SWING

The MAIN account still allows only ONE open trade globally. If several lanes are
actionable at once, the strongest Setup Score wins, with Available R:R as the
tie-breaker.

The Lane Comparison Lab tests all four lanes independently so the MAIN account's
one-trade rule does not bias the comparison.

## FAST SCALP

FAST_SCALP is intentionally simpler and faster than normal SCALP.

Primary logic:
- 3m = micro-direction
- 1m = execution
- 5m = short-term countertrend guard
- 15m = secondary countertrend guard only
- 1m / 3m volume must not be strongly adverse
- lightweight Price Action confluence / veto

It does NOT require the full higher-timeframe synchronization demanded by normal
SCALP. This makes it capable of generating more frequent opportunities.

### FAST_SCALP risk geometry

Default fallback geometry is deliberately compact:
- shorter stop than normal SCALP
- TP1 approximately 0.85R
- TP2 approximately 1.25R
- minimum Available R:R gate = 1.00R
- expiry = 15 minutes

When a trustworthy 1m structural support/resistance/trendline exists, the existing
Structure-Aware engine may use it. Otherwise FAST_SCALP uses ATR_FALLBACK.

### Consecutive opportunities

A FAST_SCALP opportunity is tied to the latest CLOSED 1m candle.

Example:
- closed 1m bar 18:31 -> FAST_SCALP opportunity A
- repeated 30-second engine cycle on the same bar -> still opportunity A
- closed 1m bar 18:32 -> opportunity B

This prevents duplicate entries within one minute while allowing a new fast setup
on the next closed candle after the previous trade has finished.

## FAST_SCALP is not assumed to be profitable

It is measured independently using the same $1,000 starting capital and the same
configured risk-per-trade percentage. The system compares it against SCALP,
INTRADAY and SWING using:

- closed trades
- W/L and Win Rate
- Net P&L
- Return %
- Expectancy R
- Profit Factor
- Max Drawdown
- MFE / MAE
- Capture Efficiency
- Quality Score
- Evidence / Reliability
- performance by Market Regime
- Price Action alignment
- Structure-Aware vs ATR execution plan

A provisional best lane still requires at least 10 closed trades. Thirty or more
closed trades are treated as higher research evidence.

## Existing V2.7 features retained

- Support / Resistance Zones 2.0
- Trendlines and Channels
- Candlestick pattern candidates
- classical chart-pattern candidates
- Pattern lifecycle: CANDIDATE / CONFIRMED / RETESTED / FAILED / ACTIVE
- Structure-Aware SL / TP with ATR fallback
- Price Action confluence and conservative multi-family veto
- Opportunity IDs
- MFE / MAE and Capture Efficiency
- Equity Curve, Drawdown and Expectancy
- Experiment history
- SCALP A/B/C/D shadow research
- closed-candle analysis
- one MAIN trade globally

## Important

V2.8 is Paper / Research only. It sends no real orders and no observed Paper result
guarantees future profitability.

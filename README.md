# BTC Analyzer V2.6 — Performance Analytics & Experiment History

V2.6 keeps the Quality-First methodology. No new market indicator is added.

This release focuses on understanding whether the existing system is actually
performing well and on making capital experiments comparable.

## One main trade only

The main paper account still allows only ONE open trade at a time across:
- SCALP
- INTRADAY
- SWING

If several lanes are actionable in the same cycle:
1. highest Setup Score wins,
2. Available R:R breaks a tie.

Shadow A/B/C/D remains research-only and does not enter main-account P&L.

## Capital changes now create experiments

Changing Simulation Capital no longer destroys previous results.

Example:
- Experiment 1: $100
- Experiment 2: $1,000
- Experiment 3: $5,000

Each experiment has its own:
- starting capital
- trades
- W/L
- realized net P&L
- Return %
- Profit Factor
- Total R
- Max Drawdown

When a new capital value is applied:
- current experiment becomes ARCHIVED,
- a new ACTIVE experiment is created,
- old trades remain stored,
- current P&L starts from zero for the new experiment,
- Research and Shadow data remain untouched.

If a main trade is still open during a manual experiment change, it is stored as
RESET with zero P&L rather than being incorrectly classified as a market win/loss.

## Performance tab

V2.4 introduced the dedicated Performance tab; V2.6 retains it and adds a separate Price Action tab.

### Equity Curve
Built only from realized main-account trades.

Unrealized P&L is never inserted into the equity curve.

### Main analytics
- Return %
- Net P&L
- Max Drawdown $ and %
- Expectancy $
- Expectancy R
- Average Win
- Average Loss
- Payoff Ratio
- Profit Factor
- Recovery Factor
- Best Trade
- Worst Trade
- Maximum Win Streak
- Maximum Loss Streak
- Current Streak

### Time analysis
Closed trades are grouped by:
- entry hour
- weekday

using the configured report timezone.

This is research information only. V2.4 does not automatically block a particular
hour or weekday based on small samples.

## Experiment History

All experiments are displayed separately so different starting-capital tests are
not mixed.

This is especially important when comparing $100 versus $1,000 tests: absolute
profit changes with position size, while Return %, R and Drawdown are more useful
for judging the decision logic.

## CSV export

The current experiment's main trades can be exported from:

`/api/paper/trades.csv`

or from the Dashboard button.

## Database migration

V2.4 continues using:

`paper_v2.db`

and automatically adds:
- `experiment_id` to existing trades,
- `paper_experiments` table,
- current experiment settings.

Existing V2.0–V2.3 trades are attached to one migrated experiment instead of being
deleted.

## Persistent Render storage

Keep a Render Persistent Disk mounted at:

`/var/data`

with:

`DATA_DIR=/var/data`

Without persistent storage, experiment history cannot survive instance replacement.

## Important

Paper / Research only.
No real order is sent.
No metric guarantees future profit.


# V2.5 — Lane Comparison Lab

V2.5 adds a fair research comparison between:

- SCALP
- INTRADAY
- SWING

## Why the old main-account statistics were not enough

The main account intentionally permits only one open trade globally.

That means if SCALP and INTRADAY are both valid at the same time, the main account
opens only the stronger setup. The rejected lane then has no trade outcome, so its
main-account history is censored and cannot be used for a fair strategy comparison.

## Independent lane accounts

V2.5 therefore creates three research-only Paper accounts:

- lane_lab_scalp_v2.db
- lane_lab_intraday_v2.db
- lane_lab_swing_v2.db

They all use:
- the same starting capital,
- the same risk-per-trade setting,
- the same fees/slippage settings,
- the same market data,
- the same decision rules.

Each account may hold one trade for its own lane. Therefore SCALP, INTRADAY and
SWING can be tested in parallel without affecting the MAIN account.

Changing Simulation Capital starts a new experiment in all three lane labs as well.

## No duplicate opportunity replay

A single Opportunity ID can open at most one trade per account/experiment.

This prevents a persistent signal from being counted repeatedly as several
independent trades.

## Lane ranking

The Lane Comparison Lab reports:

- closed trades
- open trades
- W/L
- Win Rate
- Net P&L
- Return %
- Expectancy R
- Profit Factor
- Max Drawdown
- Quality Score
- Evidence level
- Reliability %

The Quality Score does NOT rank lanes by dollar profit alone.

It uses mostly scale-free evidence:
- Expectancy in R
- Profit Factor
- Win Rate
- Drawdown penalty

and is shrunk toward a neutral score of 50 when the sample is small.

Evidence levels:
- LOW: fewer than 10 closed trades
- MEDIUM: 10–29 closed trades
- HIGH: 30+ closed trades

A provisional "Best Observed Lane" is not shown until at least one lane has
10 closed trades.

This label describes observed Paper performance only. It is not a prediction or
guarantee of future profit.

## Performance by Market Regime

The lab also separates each lane by market regime.

This can later answer questions such as:
- Is SCALP strongest during TREND?
- Does INTRADAY perform better during PULLBACK?
- Is SWING damaged by RANGE conditions?

V2.5 does not automatically route the MAIN account to the observed winner.
That should only be considered after enough out-of-sample evidence.


# V2.6 — Price Action Engine

V2.6 adds price-action analysis without adding a new technical indicator.

## Support / Resistance Zones 2.0

Closed-candle pivots are clustered into zones instead of treating every pivot as
a perfect single-price line.

Each zone records:
- center / upper / lower bound
- distance from current price
- touch count
- strength score
- freshness: FRESH / TESTED / WEAKENED
- role flip when both pivot-high and pivot-low evidence exist
- recent break/retest approximation

Only sufficiently strong nearby zones are allowed to constrain the trade's
Available R:R.

## Trendlines & Channels

Swing lows and highs are fitted geometrically.

The engine records:
- projected line price
- slope and slope % per bar
- R² fit quality
- touches
- distance from price
- trendline break
- retest approximation
- channel candidate

This is computed from closed candles only.

## Candlestick patterns

V2.6 detects candidates including:
- Doji
- Hammer
- Shooting Star
- Bullish / Bearish Engulfing
- Inside Bar
- Morning / Evening Star
- Bullish / Bearish Outside Bar

A candlestick pattern NEVER creates a trade by itself.

## Classical chart-pattern candidates

The engine detects geometric candidates for:
- Double Top / Double Bottom
- Head & Shoulders / Inverse H&S
- Symmetrical / Ascending / Descending Triangle
- Rising / Falling Wedge
- Channel
- Bull / Bear Flag

They are deliberately labeled candidates. Pattern recognition from market data is
uncertain and must not be treated as a guaranteed formation.

## Price Action Confluence

For each lane, Price Action is matched to the intended direction.

SCALP:
- 15m
- 5m
- 3m
- 1m

INTRADAY:
- 1H
- 30m
- 15m

SWING:
- 1D
- 4H

States:
- ALIGNED
- NEUTRAL
- OPPOSED

Price Action can adjust Setup Score only modestly.

It cannot create an entry if the original trend / structure / wave conditions do
not already trigger.

## Strong Price Action Veto

A single Hammer, Engulfing candle, trendline or pattern cannot block a trade.

A strong Veto requires:
- substantial directional opposition, and
- opposition from at least two independent Price Action families.

Families:
- Zones
- Trendlines
- Candlestick patterns
- Chart patterns

This reduces the risk of overreacting to a single noisy pattern.

## Measuring whether V2.6 helps

Every Paper trade now stores:
- price_action_state
- price_action_score
- aligned/opposed PA evidence

The Price Action tab compares actual results for:
- ALIGNED
- NEUTRAL
- OPPOSED

Metrics include:
- trades
- W/L
- Win Rate
- Net P&L
- Avg R
- MFE / MAE
- Capture Efficiency

The Lane Lab performs the same comparison independently for:
- SCALP
- INTRADAY
- SWING

This lets later versions decide from evidence whether specific Price Action rules
should receive more weight, less weight, or be removed.

## Important

Price Action recognition is heuristic technical analysis, not a deterministic
forecast. V2.6 remains Paper / Research only and sends no real orders.

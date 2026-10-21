# BTC Analyzer V2.4 — Performance Analytics & Experiment History

V2.4 keeps the Quality-First methodology. No new market indicator is added.

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

V2.4 adds a dedicated Performance tab.

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

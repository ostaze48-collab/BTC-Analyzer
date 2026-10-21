# BTC Analyzer V2.2 — Calibration & Trade Quality

V2.2 continues the current rule: do not add new indicators unless the data proves they add value.
This release focuses on calibration, opportunity lifecycle and execution-quality measurement.

## Stable Opportunity IDs
Each evolving SCALP / INTRADAY / SWING setup gets one persistent ID instead of being counted again every engine cycle.

Lifecycle:
- FORMING
- READY
- TRIGGERED
- CLOSED

## Stricter A+
SCALP A+ is capped to A when 15m support or 3m confirmation is missing.
The trade may still be allowed at A if the remaining Quality-First rules pass.

## Clearer terminology
- Setup Score is not a probability.
- LONG Direction Score / SHORT Direction Score are directional scores, not probabilities.
- Regime Strength replaces the misleading word Confidence in the UI.

## Entry Quality Diagnostics
Every lane now reports:
- Entry Timing: EARLY / OPTIMAL / ACCEPTABLE / LATE
- Chasing Risk: LOW / MEDIUM / HIGH
- Available R:R
- R:R Gate PASS / BLOCK
- structural obstacle when available from existing support/resistance

No new indicator is used for these diagnostics.

## R:R Gate
Minimum available structural R:R:
- SCALP: 1.20R
- INTRADAY: 1.40R
- SWING: 1.60R

A setup remains WAIT if available R:R is below its lane threshold.

## Chasing protection
HIGH chasing risk keeps the lane at WAIT.
This uses the existing wave state and overextension flag.

## MFE / MAE
Primary paper trades now track:
- MFE price / MFE in R
- MAE price / MAE in R

## Capture Efficiency
Closed trades calculate positive realized R / MFE R, capped at 0–100%.

## Performance by Market Regime
Actual closed primary trades are grouped by lane + market regime with:
- trades
- W/L and win rate
- net P&L
- Avg R
- Avg MFE / MAE
- Capture Efficiency

Market Regime remains research-only in V2.2.

## Calibration tables
Research compares actual closed trades by:
- Entry Timing
- Chasing Risk

## Non-destructive database migration
V2.2 keeps:
- paper_v2.db
- research_v2.db
- shadow_v2.db

and adds:
- opportunities_v2.db

Missing V2.2 columns are added automatically to existing V2.0/V2.1 databases.
Historical trades are not deleted.

New migrated fields include:
- opportunity_id
- market_regime
- entry_timing
- chasing_risk
- available_rr
- structural_obstacle
- MFE / MAE
- capture efficiency

Old historical rows may show blank/UNKNOWN for fields that did not exist when recorded.

## Render persistence
Keep a Persistent Disk mounted at /var/data and:

DATA_DIR=/var/data

## Paper / Research only
V2.2 sends no real orders and does not guarantee profit.

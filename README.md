# BTC Analyzer V2.1 — Quality & Measurement Release

V2.0 freezes indicator expansion and focuses on:
1. data quality,
2. decision methodology,
3. result measurement,
4. interface clarity.

## Main methodological changes

### Closed-candle analysis
All timeframe analysis uses closed candles only.
The live BTC price is fetched separately and is used for the virtual execution layer.

This reduces repainting from a still-forming 1H/4H/1D candle.

Custom 12D and 2W candles are also kept out of analysis until their full daily bucket is complete.

### Macro de-duplication
1Y / 6M / 3M are rolling daily contexts and are highly correlated.
V2.0 median-combines them into one macro-context vote instead of counting them as three independent votes.

### One decision orchestrator
The analyzer produces market facts.
The Decision Engine alone creates SCALP / INTRADAY / SWING decisions.

`Setup Score` is a rule-based score, not a claimed success probability.

## Main paper P&L account

Only the primary virtual trades from:
- SCALP
- INTRADAY
- SWING

are included in Total P&L.

Shadow A/B/C/D trades are research-only and do NOT increase or reduce the account total.

The Dashboard reports realized:
- Today
- This week
- This month
- Total

Each period includes:
- Gross Profit
- Gross Loss
- Fees
- Net P&L
- Total R
- W/L
- Win Rate

Default reporting timezone is UTC+3 and can be changed in `config.json`.

### Partial-exit simulation
Main virtual trades use:
- 50% at TP1
- remaining 50% toward TP2
- original stop remains active

If Stop and Target are both touched in the same closed 1m candle,
V2.0 uses the conservative assumption: Stop happened first.

Paper fees and slippage are configurable.
They default to 0.0 bps so V2.0 does not pretend to know the user's real execution costs.

## Better Shadow comparison

The Scalp A/B/C/D laboratory now separates:
- Missed Winner
- Avoided Loser
- Neutral Miss

This is more useful than treating every missing strict trigger as a "missed opportunity".

## Resilience

If a new cycle fails after the system has already produced a good state:
- the Dashboard stays alive,
- the last successful analysis remains visible,
- status becomes `DEGRADED`,
- System Health shows the current error and age of the last successful cycle.

## Data request caching

Long timeframes are not downloaded every engine cycle.
Each timeframe has a different refresh TTL.

## Interface

Tabs:
- الرئيسية
- الفريمات
- Scalp Lab
- Research
- System Health

The Overview puts realized P&L and the three decision lanes first.

## Files

- `btc_analyzer/data.py` — Binance public data, caching, closed candles
- `btc_analyzer/analysis.py` — technical and wave analysis
- `btc_analyzer/context.py` — Bitcoin Context / optional Bitbo
- `btc_analyzer/decision.py` — SCALP / INTRADAY / SWING
- `btc_analyzer/paper.py` — primary account, P&L accounting
- `btc_analyzer/research.py` — snapshots and Shadow comparison
- `engine.py` — orchestration and Last-Good-State
- `static/` — separate Dashboard HTML/CSS/JS

## Render

Upload all V2.0 files to the repository, then:

Manual Deploy -> Clear build cache & deploy

For persistent research/P&L data, mount a Render Persistent Disk at:

`/var/data`

and add:

`DATA_DIR=/var/data`

Optional Bitbo:

`BITBO_API_KEY=...`

Never commit the Bitbo key to GitHub.

## New database files

V2.0 intentionally uses new databases:
- `paper_v2.db`
- `research_v2.db`
- `shadow_v2.db`

This prevents old V1 research methodology from being silently mixed with V2.0 results.

Old databases are not deleted.

## Important

This is a research and paper-trading system.
It does not send real orders.
No indicator or score guarantees profit.


## V2.1 additions

- Open Trades panel with OPEN / TP1_HIT, age, unrealized P&L, Current R and distances to SL/TP1/TP2.
- Unrealized P&L is separate from realized day/week/month/total P&L.
- Paper Risk Guard: daily loss limit, consecutive-loss pause and maximum open trades.
- Market Regime classifier: TREND / PULLBACK / RANGE / COMPRESSION / EXHAUSTION / REVERSAL_CANDIDATE / HIGH_VOL / MIXED.
- Market Regime is research/display-only in V2.1 and does not alter paper decisions.
- V2.0 already used full-bucket validation for custom 12D/2W candles; V2.1 retains that closed-bar protection.

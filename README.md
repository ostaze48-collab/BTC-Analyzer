# BTC Analyzer V1.4 — Research & Persistence

## New
- Saves a decision snapshot every 5 minutes by default, including WAIT.
- Stores WHY WAIT, warnings, vetoes, hierarchy, evidence families and timeframes.
- Tracks observed price after 15m, 1h, 4h, 12h and 24h.
- Tracks MFE and MAE for each snapshot.
- Dashboard includes Research Memory and quality statistics.
- CSV export at `/api/research.csv`.
- Persistent-storage ready through environment variable `DATA_DIR`.

## Render persistent storage
The app works without a persistent disk, but local SQLite files may be lost on redeploy/restart.

For durable research data:
1. Add a Persistent Disk to the Render service.
2. Mount it at `/var/data`.
3. Add environment variable:
   `DATA_DIR=/var/data`
4. Redeploy.

Then `/diag` should show:
`"persistent_requested": true`

## Databases
- `paper.db` — actual paper LONG/SHORT signals.
- `research.db` — all research snapshots, including WAIT decisions.

## Important
Research/Paper only. No real orders are placed.

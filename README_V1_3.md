# BTC AI Trader V1.3

V1.3 adds a deterministic market-structure research layer to the existing three-brain + Master system.

## Added

- Confirmed Swing High / Swing Low using 2-left / 2-right pivots.
- BOS and CHoCH detection from confirmed swing levels.
- Active 3-candle Fair Value Gap detection.
- Heuristic Order Block: last opposite candle before the latest BOS/CHoCH.
- Market-structure context is included in brain voting with deliberately small weights.
- Mobile chart controls for Swing/BOS/CHoCH and FVG/Order Block layers.
- Semi-transparent FVG/OB bands on the chart.
- Replay optimization: unchanged higher-timeframe snapshots are cached.

## Safety / research assumptions

- Unconfirmed pivots are never used as completed swings.
- FVGs disappear after a full fill through the far boundary.
- Order Block output is explicitly heuristic, not an institutional-flow claim.
- These features do not bypass the existing Risk Gate.
- The application remains Paper Trading only.

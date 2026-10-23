# Public Research Policy

هذا الملف يثبت سياسة تطوير BTC AI Trader: نستفيد من المشاريع والاستراتيجيات العامة لتقليل زمن البحث، لكن لا ننقل ادعاءات الربحية أو نتائج backtest كما هي.

## المشاريع المرجعية

- Freqtrade / FreqAI: lookahead analysis, recursive analysis, protections, dry-run, strategy collections.
- Jesse: strict train/test separation, optimization, significance testing, Monte Carlo, rich risk metrics.
- VectorBT: fast large-scale parameter/feature screening.
- NautilusTrader: same event-driven core between backtest and live, realistic execution architecture.
- QuantConnect LEAN: fill/fee/slippage/margin reality models and modular research/live engine.
- Hummingbot: prototype vs production controller separation, paper trading, modular executors.
- Public Freqtrade strategies: source of candidate ideas only (trend, mean-reversion, pattern, dynamic stops, multi-timeframe filters).

## قاعدة الثقة

أي فكرة عامة تبدأ كـ CANDIDATE أو SHADOW_ONLY. لا يسمح لها بالتأثير على MASTER بسبب شهرتها أو Backtest منشور.

Promotion path:

1. Source review / license review.
2. Remove lookahead and future leakage.
3. Recursive/startup stability check.
4. Re-implement concept in our own deterministic module.
5. Compare against simple baselines on identical data/cost assumptions.
6. Chronological train/validation/holdout or walk-forward.
7. Monte Carlo / bootstrap robustness.
8. Parameter sensitivity: nearby parameters should not collapse.
9. Regime analysis: trend/range/breakout/high-volatility.
10. Paper/shadow observation.
11. Only then assign bounded decision weight.

## Baseline strategy zoo

Every major model must beat or complement at least these simple baselines:

- Buy & Hold (macro reference only).
- EMA trend (20/50 and 50/200 variants).
- Donchian breakout.
- RSI/Bollinger mean reversion.
- ATR breakout/trend.
- Simple candlestick/pattern filter.
- Multi-timeframe trend filter.
- Fixed R:R + ATR stop baseline.

A complex model is rejected if its OOS improvement over a simpler baseline is not material after fees/slippage.

## Anti-overfitting rules

- Never select a model from the same period used for final evaluation.
- Do not promote based on win rate alone.
- Penalize tiny samples.
- Track Profit Factor, expectancy / avg R, max drawdown, Sharpe/Sortino/Calmar when meaningful, MFE/MAE and stability by regime.
- Record number of parameter/feature trials to account for data-mining risk.
- Prefer broad stable plateaus over a single best parameter point.
- Features with high correlation/redundancy are grouped rather than counted as independent votes.
- Public strategies with extraordinary historical results receive *more* scrutiny, not less.

## Execution realism

Backtests must include:

- exchange fees,
- configurable slippage/spread,
- conservative same-candle TP/SL ambiguity,
- latency/fill assumptions where applicable,
- funding for futures when relevant,
- no use of incomplete future candles,
- identical signal logic between replay and paper/live paths.

## Current policy for external intelligence

- Cycle/valuation models: bounded macro context only.
- Bitcoin network intelligence: SHADOW_ONLY until incremental OOS edge is proven.
- Derivatives intelligence: SHADOW_ONLY until incremental OOS edge is proven.
- Any future news/sentiment/AI/LLM feature: SHADOW_ONLY first.

## Definition of success

The goal is not to find the prettiest historical equity curve. The goal is a reproducible process where a model repeatedly adds risk-adjusted value outside the data used to design it.

Real-money execution remains disabled until the Readiness Gate is satisfied and a separate tiny-capital pilot is explicitly authorized.

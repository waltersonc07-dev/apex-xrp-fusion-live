# Phase 10 — Filter Comparison

Side-by-side comparison of baseline (no filters) vs filtered backtests. Both runs use the **same non-optimized** variant parameters; the only difference is the entry filter layer.

## Filter configuration (filtered run)

- Session filter: enabled (skip Friday & Sunday entries)
- Regime filter:  enabled, regimes allowed = `['trending']`

## Per-variant metrics (in-sample)

| Symbol | Variant | Metric | Baseline | Filtered | Δ |
|---|---|---|---:|---:|---:|
| EURUSD | V0 | trades | 86 | 15 | -71 |
| EURUSD | V0 | profit_factor | 1.16 | 0.34 | -0.82 |
| EURUSD | V0 | max_drawdown_pct | 2.7 | 1.5 | -1.2 |
| EURUSD | V0 | sharpe | 0.70 | -6.47 | -7.18 |
| EURUSD | V0 | net_profit | 202 | -129 | -330 |
| EURUSD | V1 | trades | 175 | 21 | -154 |
| EURUSD | V1 | profit_factor | 1.54 | 0.62 | -0.92 |
| EURUSD | V1 | max_drawdown_pct | 2.9 | 1.2 | -1.6 |
| EURUSD | V1 | sharpe | 1.85 | -2.86 | -4.71 |
| EURUSD | V1 | net_profit | 1196 | -87 | -1284 |
| EURUSD | V2 | trades | 36 | 14 | -22 |
| EURUSD | V2 | profit_factor | 1.14 | 1.94 | 0.80 |
| EURUSD | V2 | max_drawdown_pct | 3.8 | 1.0 | -2.8 |
| EURUSD | V2 | sharpe | 0.86 | 4.02 | 3.17 |
| EURUSD | V2 | net_profit | 138 | 305 | 167 |
| EURUSD | V3 | trades | 105 | 21 | -84 |
| EURUSD | V3 | profit_factor | 1.15 | 1.13 | -0.02 |
| EURUSD | V3 | max_drawdown_pct | 4.7 | 2.4 | -2.3 |
| EURUSD | V3 | sharpe | 0.87 | 0.76 | -0.11 |
| EURUSD | V3 | net_profit | 354 | 60 | -294 |
| GBPUSD | V0 | trades | 105 | 6 | -99 |
| GBPUSD | V0 | profit_factor | 0.72 | 1.31 | 0.58 |
| GBPUSD | V0 | max_drawdown_pct | 6.1 | 0.2 | -5.8 |
| GBPUSD | V0 | sharpe | -1.80 | 1.68 | 3.48 |
| GBPUSD | V0 | net_profit | -391 | 11 | 401 |
| GBPUSD | V1 | trades | 183 | 16 | -167 |
| GBPUSD | V1 | profit_factor | 0.94 | 0.80 | -0.14 |
| GBPUSD | V1 | max_drawdown_pct | 6.3 | 0.9 | -5.4 |
| GBPUSD | V1 | sharpe | -0.28 | -1.37 | -1.09 |
| GBPUSD | V1 | net_profit | -146 | -27 | 119 |
| GBPUSD | V2 | trades | 38 | 12 | -26 |
| GBPUSD | V2 | profit_factor | 0.66 | 0.25 | -0.41 |
| GBPUSD | V2 | max_drawdown_pct | 5.6 | 2.9 | -2.8 |
| GBPUSD | V2 | sharpe | -2.56 | -9.75 | -7.19 |
| GBPUSD | V2 | net_profit | -368 | -287 | 81 |
| GBPUSD | V3 | trades | 100 | 16 | -84 |
| GBPUSD | V3 | profit_factor | 0.80 | 0.57 | -0.23 |
| GBPUSD | V3 | max_drawdown_pct | 7.5 | 2.8 | -4.7 |
| GBPUSD | V3 | sharpe | -1.25 | -3.65 | -2.41 |
| GBPUSD | V3 | net_profit | -446 | -186 | 260 |
| XAUUSD | V0 | trades | 100 | 18 | -82 |
| XAUUSD | V0 | profit_factor | 0.74 | 0.19 | -0.55 |
| XAUUSD | V0 | max_drawdown_pct | 8.7 | 3.4 | -5.4 |
| XAUUSD | V0 | sharpe | -1.47 | -10.87 | -9.40 |
| XAUUSD | V0 | net_profit | -516 | -335 | 181 |
| XAUUSD | V1 | trades | 156 | 25 | -131 |
| XAUUSD | V1 | profit_factor | 0.83 | 0.15 | -0.68 |
| XAUUSD | V1 | max_drawdown_pct | 8.6 | 4.5 | -4.1 |
| XAUUSD | V1 | sharpe | -0.92 | -12.15 | -11.23 |
| XAUUSD | V1 | net_profit | -505 | -453 | 52 |
| XAUUSD | V2 | trades | 54 | 27 | -27 |
| XAUUSD | V2 | profit_factor | 2.01 | 1.58 | -0.43 |
| XAUUSD | V2 | max_drawdown_pct | 3.6 | 3.7 | 0.1 |
| XAUUSD | V2 | sharpe | 2.97 | 1.97 | -1.00 |
| XAUUSD | V2 | net_profit | 1766 | 506 | -1260 |
| XAUUSD | V3 | trades | 111 | 19 | -92 |
| XAUUSD | V3 | profit_factor | 0.98 | 0.53 | -0.45 |
| XAUUSD | V3 | max_drawdown_pct | 8.7 | 4.1 | -4.6 |
| XAUUSD | V3 | sharpe | -0.03 | -3.96 | -3.93 |
| XAUUSD | V3 | net_profit | -74 | -262 | -188 |
| USDJPY | V0 | trades | 100 | 10 | -90 |
| USDJPY | V0 | profit_factor | 1.10 | 5.59 | 4.49 |
| USDJPY | V0 | max_drawdown_pct | 5.8 | 0.5 | -5.2 |
| USDJPY | V0 | sharpe | 0.38 | 6.54 | 6.16 |
| USDJPY | V0 | net_profit | 144 | 649 | 505 |
| USDJPY | V1 | trades | 181 | 26 | -155 |
| USDJPY | V1 | profit_factor | 1.16 | 2.75 | 1.60 |
| USDJPY | V1 | max_drawdown_pct | 5.1 | 1.4 | -3.7 |
| USDJPY | V1 | sharpe | 0.59 | 3.48 | 2.90 |
| USDJPY | V1 | net_profit | 359 | 582 | 223 |
| USDJPY | V2 | trades | 35 | 12 | -23 |
| USDJPY | V2 | profit_factor | 3.01 | 6.78 | 3.77 |
| USDJPY | V2 | max_drawdown_pct | 4.7 | 1.9 | -2.8 |
| USDJPY | V2 | sharpe | 3.38 | 7.56 | 4.18 |
| USDJPY | V2 | net_profit | 2270 | 1742 | -528 |
| USDJPY | V3 | trades | 111 | 14 | -97 |
| USDJPY | V3 | profit_factor | 0.92 | 0.65 | -0.27 |
| USDJPY | V3 | max_drawdown_pct | 8.0 | 1.5 | -6.5 |
| USDJPY | V3 | sharpe | -0.33 | -2.41 | -2.08 |
| USDJPY | V3 | net_profit | -193 | -78 | 116 |

## Gate status

| Symbol | Variant | Baseline gate | Filtered gate |
|---|---|---|---|
| EURUSD | V0 | BLOCK_LIVE | BLOCK_LIVE |
| EURUSD | V1 | BLOCK_LIVE | BLOCK_LIVE |
| EURUSD | V2 | BLOCK_LIVE | BLOCK_LIVE |
| EURUSD | V3 | BLOCK_LIVE | BLOCK_LIVE |
| GBPUSD | V0 | BLOCK_LIVE | BLOCK_LIVE |
| GBPUSD | V1 | BLOCK_LIVE | BLOCK_LIVE |
| GBPUSD | V2 | BLOCK_LIVE | BLOCK_LIVE |
| GBPUSD | V3 | BLOCK_LIVE | BLOCK_LIVE |
| XAUUSD | V0 | BLOCK_LIVE | BLOCK_LIVE |
| XAUUSD | V1 | BLOCK_LIVE | BLOCK_LIVE |
| XAUUSD | V2 | BLOCK_LIVE | BLOCK_LIVE |
| XAUUSD | V3 | BLOCK_LIVE | BLOCK_LIVE |
| USDJPY | V0 | BLOCK_LIVE | BLOCK_LIVE |
| USDJPY | V1 | BLOCK_LIVE | BLOCK_LIVE |
| USDJPY | V2 | BLOCK_LIVE | BLOCK_LIVE |
| USDJPY | V3 | BLOCK_LIVE | BLOCK_LIVE |

## Safety

Every variant on every symbol — in both runs — still recommends `BACKTEST_ONLY`. Filters are an entry mask; they do not unlock any live-trading flag. See [SAFETY.md](../SAFETY.md).


# Phase 10 — Filter Comparison

Side-by-side comparison of baseline (no filters) vs filtered backtests. Both runs use the **same non-optimized** variant parameters; the only difference is the entry filter layer.

## Filter configuration (filtered run)

- Session filter: enabled (skip Friday & Sunday entries)
- Regime filter:  enabled, regimes allowed = `['trending']`

## Per-variant metrics (in-sample)

| Symbol | Variant | Metric | Baseline | Filtered | Δ |
|---|---|---|---:|---:|---:|
| EURUSD | V0 | trades | 40 | 4 | -36 |
| EURUSD | V0 | profit_factor | 1.26 | 1.82 | 0.56 |
| EURUSD | V0 | max_drawdown_pct | 1.3 | 0.4 | -0.9 |
| EURUSD | V0 | sharpe | 1.07 | 3.35 | 2.27 |
| EURUSD | V0 | net_profit | 148 | 31 | -117 |
| EURUSD | V1 | trades | 98 | 5 | -93 |
| EURUSD | V1 | profit_factor | 1.25 | 1.67 | 0.42 |
| EURUSD | V1 | max_drawdown_pct | 2.5 | 0.4 | -2.2 |
| EURUSD | V1 | sharpe | 1.11 | 2.72 | 1.61 |
| EURUSD | V1 | net_profit | 301 | 28 | -273 |
| EURUSD | V2 | trades | 16 | 9 | -7 |
| EURUSD | V2 | profit_factor | 0.92 | 0.80 | -0.12 |
| EURUSD | V2 | max_drawdown_pct | 1.8 | 1.8 | -0.0 |
| EURUSD | V2 | sharpe | -0.43 | -1.38 | -0.94 |
| EURUSD | V2 | net_profit | -38 | -50 | -12 |
| EURUSD | V3 | trades | 54 | 11 | -43 |
| EURUSD | V3 | profit_factor | 0.83 | 1.58 | 0.74 |
| EURUSD | V3 | max_drawdown_pct | 4.7 | 1.1 | -3.6 |
| EURUSD | V3 | sharpe | -1.10 | 2.25 | 3.36 |
| EURUSD | V3 | net_profit | -178 | 80 | 257 |
| GBPUSD | V0 | trades | 46 | 3 | -43 |
| GBPUSD | V0 | profit_factor | 1.12 | 0.85 | -0.27 |
| GBPUSD | V0 | max_drawdown_pct | 1.5 | 0.1 | -1.4 |
| GBPUSD | V0 | sharpe | 0.67 | -0.93 | -1.60 |
| GBPUSD | V0 | net_profit | 59 | -2 | -61 |
| GBPUSD | V1 | trades | 87 | 9 | -78 |
| GBPUSD | V1 | profit_factor | 1.37 | 1.98 | 0.61 |
| GBPUSD | V1 | max_drawdown_pct | 2.0 | 0.2 | -1.8 |
| GBPUSD | V1 | sharpe | 1.74 | 4.10 | 2.36 |
| GBPUSD | V1 | net_profit | 364 | 37 | -327 |
| GBPUSD | V2 | trades | 17 | 7 | -10 |
| GBPUSD | V2 | profit_factor | 0.95 | 0.00 | -0.95 |
| GBPUSD | V2 | max_drawdown_pct | 2.3 | 2.8 | 0.6 |
| GBPUSD | V2 | sharpe | -0.23 | -35.24 | -35.01 |
| GBPUSD | V2 | net_profit | -20 | -282 | -262 |
| GBPUSD | V3 | trades | 55 | 11 | -44 |
| GBPUSD | V3 | profit_factor | 0.46 | 0.10 | -0.36 |
| GBPUSD | V3 | max_drawdown_pct | 6.9 | 3.0 | -4.0 |
| GBPUSD | V3 | sharpe | -5.12 | -15.94 | -10.82 |
| GBPUSD | V3 | net_profit | -629 | -277 | 352 |
| XAUUSD | V0 | trades | 55 | 12 | -43 |
| XAUUSD | V0 | profit_factor | 1.00 | 0.21 | -0.79 |
| XAUUSD | V0 | max_drawdown_pct | 6.0 | 1.7 | -4.3 |
| XAUUSD | V0 | sharpe | 0.05 | -8.70 | -8.74 |
| XAUUSD | V0 | net_profit | -2 | -167 | -165 |
| XAUUSD | V1 | trades | 72 | 17 | -55 |
| XAUUSD | V1 | profit_factor | 1.01 | 0.53 | -0.49 |
| XAUUSD | V1 | max_drawdown_pct | 6.1 | 2.1 | -3.9 |
| XAUUSD | V1 | sharpe | 0.11 | -3.40 | -3.51 |
| XAUUSD | V1 | net_profit | 18 | -121 | -139 |
| XAUUSD | V2 | trades | 29 | 14 | -15 |
| XAUUSD | V2 | profit_factor | 1.99 | 2.66 | 0.67 |
| XAUUSD | V2 | max_drawdown_pct | 3.6 | 1.5 | -2.1 |
| XAUUSD | V2 | sharpe | 3.45 | 6.05 | 2.59 |
| XAUUSD | V2 | net_profit | 834 | 475 | -358 |
| XAUUSD | V3 | trades | 57 | 9 | -48 |
| XAUUSD | V3 | profit_factor | 1.42 | 0.98 | -0.44 |
| XAUUSD | V3 | max_drawdown_pct | 3.2 | 1.7 | -1.5 |
| XAUUSD | V3 | sharpe | 1.65 | -0.06 | -1.71 |
| XAUUSD | V3 | net_profit | 676 | -4 | -680 |
| USDJPY | V0 | trades | 61 | 4 | -57 |
| USDJPY | V0 | profit_factor | 1.50 | 19.41 | 17.91 |
| USDJPY | V0 | max_drawdown_pct | 4.9 | 0.1 | -4.9 |
| USDJPY | V0 | sharpe | 1.55 | 8.76 | 7.21 |
| USDJPY | V0 | net_profit | 382 | 161 | -221 |
| USDJPY | V1 | trades | 90 | 7 | -83 |
| USDJPY | V1 | profit_factor | 1.37 | 5.26 | 3.89 |
| USDJPY | V1 | max_drawdown_pct | 5.1 | 0.3 | -4.9 |
| USDJPY | V1 | sharpe | 1.19 | 5.88 | 4.69 |
| USDJPY | V1 | net_profit | 361 | 149 | -212 |
| USDJPY | V2 | trades | 15 | 12 | -3 |
| USDJPY | V2 | profit_factor | 3.53 | 1.09 | -2.44 |
| USDJPY | V2 | max_drawdown_pct | 3.8 | 3.0 | -0.8 |
| USDJPY | V2 | sharpe | 3.90 | 0.46 | -3.44 |
| USDJPY | V2 | net_profit | 1250 | 48 | -1201 |
| USDJPY | V3 | trades | 52 | 11 | -41 |
| USDJPY | V3 | profit_factor | 1.17 | 0.26 | -0.90 |
| USDJPY | V3 | max_drawdown_pct | 4.4 | 1.2 | -3.2 |
| USDJPY | V3 | sharpe | 0.81 | -7.98 | -8.78 |
| USDJPY | V3 | net_profit | 194 | -123 | -317 |

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


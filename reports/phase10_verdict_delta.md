# Phase 10 Verdict Delta — Filters OFF vs ON (20-year history)

Filter config: session filter (skip Fri/Sun entries) + regime filter (trending only).
Data: ~5000 daily bars per symbol (2006–2026, sourced via Yahoo).

**Both runs: 16/16 BLOCK_LIVE.** No variant qualifies as a MICRO_LIVE candidate.

## In-sample delta

| Symbol | Variant | Trades base→filt | PF base→filt | Sharpe base→filt | Verdict |
|---|---|---|---|---|---|
| EURUSD | V0 | 86 → 15 | 1.16 → 0.34 | 0.70 → -6.47 | BLOCK |
| EURUSD | V1 | 175 → 21 | 1.54 → 0.62 | 1.85 → -2.86 | BLOCK |
| EURUSD | V2 | 36 → 14 | 1.14 → 1.94 | 0.86 → 4.02 | BLOCK |
| EURUSD | V3 | 105 → 21 | 1.15 → 1.13 | 0.87 → 0.76 | BLOCK |
| GBPUSD | V0 | 105 → 6 | 0.72 → 1.31 | -1.80 → 1.68 | BLOCK |
| GBPUSD | V1 | 183 → 16 | 0.94 → 0.80 | -0.28 → -1.37 | BLOCK |
| GBPUSD | V2 | 38 → 12 | 0.66 → 0.25 | -2.56 → -9.75 | BLOCK |
| GBPUSD | V3 | 100 → 16 | 0.80 → 0.57 | -1.25 → -3.65 | BLOCK |
| XAUUSD | V0 | 100 → 18 | 0.74 → 0.19 | -1.47 → -10.87 | BLOCK |
| XAUUSD | V1 | 156 → 25 | 0.83 → 0.15 | -0.92 → -12.15 | BLOCK |
| XAUUSD | V2 | 54 → 27 | 2.01 → 1.58 | 2.97 → 1.97 | BLOCK |
| XAUUSD | V3 | 111 → 19 | 0.98 → 0.53 | -0.03 → -3.96 | BLOCK |
| USDJPY | V0 | 100 → 10 | 1.10 → 5.59 | 0.38 → 6.54 | BLOCK |
| USDJPY | V1 | 181 → 26 | 1.16 → 2.75 | 0.59 → 3.48 | BLOCK |
| USDJPY | V2 | 35 → 12 | 3.01 → 6.78 | 3.38 → 7.56 | BLOCK |
| USDJPY | V3 | 111 → 14 | 0.92 → 0.65 | -0.33 → -2.41 | BLOCK |

## Key observations

- **Extended history hurts trade count after filtering.** The 20-year window includes long stretches (2008 crisis, 2014–2017 USD strength, COVID flash) where regimes classify as ranging or choppy. The trending-only whitelist correctly excludes them.
- **PR #7 finding**: simply pulling more bars does NOT trivially solve the 40-trade floor. The bottleneck is *trending bars*, not total bars.
- **Promising signals on filtered run**: EURUSD V2 (PF 1.94, Sharpe 4.02 on n=14), USDJPY V0/V2 (PF >5 but n=10–12). All blocked on trades.
- **All variants blocked.** Filter remains honest — separates good from bad without producing false PASSes.

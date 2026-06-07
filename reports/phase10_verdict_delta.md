# Phase 10 Verdict Delta — Filters OFF vs ON

Filter config: session filter (skip Fri/Sun entries) + regime filter (trending only).

**Both runs: 16/16 BLOCK_LIVE.** No variant qualifies as a MICRO_LIVE candidate.

Trade-count floor (40) is the dominant failure mode after filtering. Filter is doing real work:
it raises PF/Sharpe on some pairs (EURUSD V3, GBPUSD V1, USDJPY V0, XAUUSD V2) and crushes
others (XAUUSD V0, GBPUSD V2/V3), which means it separates good and bad behavior rather than
uniformly improving everything (which would be a curve-fit red flag).

## In-sample delta

| Symbol | Variant | Trades base→filt | PF base→filt | Sharpe base→filt | Verdict |
|---|---|---|---|---|---|
| EURUSD | V0 | 40 → 4 | 1.26 → 1.82 | 1.07 → 3.35 | BLOCK |
| EURUSD | V1 | 98 → 5 | 1.25 → 1.67 | 1.11 → 2.72 | BLOCK |
| EURUSD | V2 | 16 → 9 | 0.92 → 0.80 | -0.43 → -1.38 | BLOCK |
| EURUSD | V3 | 54 → 11 | 0.83 → 1.58 | -1.10 → 2.25 | BLOCK |
| GBPUSD | V0 | 46 → 3 | 1.12 → 0.85 | 0.67 → -0.93 | BLOCK |
| GBPUSD | V1 | 87 → 9 | 1.37 → 1.98 | 1.74 → 4.10 | BLOCK |
| GBPUSD | V2 | 17 → 7 | 0.95 → 0.00 | -0.23 → -35.24 | BLOCK |
| GBPUSD | V3 | 55 → 11 | 0.46 → 0.10 | -5.12 → -15.94 | BLOCK |
| XAUUSD | V0 | 55 → 12 | 1.00 → 0.21 | 0.05 → -8.70 | BLOCK |
| XAUUSD | V1 | 72 → 17 | 1.01 → 0.53 | 0.11 → -3.40 | BLOCK |
| XAUUSD | V2 | 29 → 14 | 1.99 → 2.66 | 3.45 → 6.05 | BLOCK |
| XAUUSD | V3 | 57 → 9 | 1.42 → 0.98 | 1.65 → -0.06 | BLOCK |
| USDJPY | V0 | 61 → 4 | 1.50 → 19.41 | 1.55 → 8.76 | BLOCK |
| USDJPY | V1 | 90 → 7 | 1.37 → 5.26 | 1.19 → 5.88 | BLOCK |
| USDJPY | V2 | 15 → 12 | 3.53 → 1.09 | 3.90 → 0.46 | BLOCK |
| USDJPY | V3 | 52 → 11 | 1.17 → 0.26 | 0.81 → -7.98 | BLOCK |

## Reading the table

- **Promising pairs after filter**: XAUUSD V2 (PF 1.99→2.66, Sharpe 3.45→6.05), GBPUSD V1 (PF 1.37→1.98, Sharpe 1.74→4.10), USDJPY V0 (PF 1.50→19.41 — small sample, n=4).
- **All blocked on trade count.** Until extended history yields ≥40 trades per (sym, variant) after filtering, no PASS is possible. PR #7 will address this.
- **No variant is approved for live.** This is intentional and correct.

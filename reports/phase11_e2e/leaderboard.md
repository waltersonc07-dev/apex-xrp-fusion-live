# Phase 11 — Grid Search Summary (PR 2)

- grid version: `1`
- total combinations: **123** (cap 140)
- per-variant counts: `V0=36`, `V1=36`, `V2=24`, `V3=27`
- rows written: **492**
- csv: `reports/phase11_e2e/leaderboard.csv`

> Runtime mode: **BACKTEST_ONLY**. No live trading. This report cannot toggle any live-trading flag.

> Per-symbol acceptance gate is active (PR 3). The portfolio aggregation + per-pair >40% cap lands in PR 4; even the highest verdict label remains research-only.

## Verdict counts

- `BLOCKED`: 492 row(s)
- `WATCH`: 0 row(s)
- `VALIDATED_RESEARCH_CANDIDATE`: 0 row(s)
- `MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW`: 0 row(s)

_No VALIDATED_RESEARCH_CANDIDATE or MICRO_LIVE_CANDIDATE rows in this run. All OK rows are BLOCKED or WATCH._

## Skip / data-availability summary

- `OK`: 492 row(s)

## Top 10 by median OOS PF — EURUSD

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V0 | `atr_stop_mult=1.5`, `ema_fast=21`, `ema_slow=34`, `rsi_length=21` | 1.997 | 0.000 | 3.261 | 0.79 | 20 |
| V0 | `atr_stop_mult=1.5`, `ema_fast=21`, `ema_slow=34`, `rsi_length=10` | 1.934 | 0.000 | 0.000 | 1.39 | 36 |
| V1 | `atr_stop_mult=1.5`, `ema_fast=21`, `ema_slow=55`, `rsi_length=21` | 1.879 | 0.513 | 3.407 | 1.67 | 62 |
| V1 | `atr_stop_mult=1.5`, `ema_fast=21`, `ema_slow=89`, `rsi_length=21` | 1.879 | 0.438 | 3.407 | 1.75 | 66 |
| V0 | `atr_stop_mult=2.5`, `ema_fast=21`, `ema_slow=34`, `rsi_length=21` | 1.797 | 0.000 | 2.941 | 0.54 | 20 |
| V1 | `atr_stop_mult=2.5`, `ema_fast=21`, `ema_slow=55`, `rsi_length=21` | 1.723 | 0.512 | 2.918 | 1.01 | 62 |
| V1 | `atr_stop_mult=2.5`, `ema_fast=21`, `ema_slow=89`, `rsi_length=21` | 1.723 | 0.437 | 2.918 | 1.06 | 66 |
| V0 | `atr_stop_mult=1.5`, `ema_fast=21`, `ema_slow=55`, `rsi_length=10` | 1.709 | 0.000 | 2.841 | 1.39 | 43 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=5` | 1.644 | 0.000 | 0.000 | 2.02 | 13 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=10` | 1.644 | 0.000 | 0.000 | 2.02 | 13 |

## Top 10 by median OOS PF — GBPUSD

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V0 | `atr_stop_mult=2.5`, `ema_fast=13`, `ema_slow=34`, `rsi_length=10` | 1.992 | 1.144 | 4.113 | 0.40 | 43 |
| V0 | `atr_stop_mult=1.5`, `ema_fast=13`, `ema_slow=34`, `rsi_length=10` | 1.989 | 1.028 | 4.113 | 0.76 | 43 |
| V0 | `atr_stop_mult=2.5`, `ema_fast=13`, `ema_slow=55`, `rsi_length=21` | 1.852 | 0.493 | 3.719 | 1.07 | 34 |
| V0 | `atr_stop_mult=1.5`, `ema_fast=13`, `ema_slow=55`, `rsi_length=21` | 1.851 | 0.474 | 3.719 | 1.86 | 34 |
| V0 | `atr_stop_mult=2.5`, `ema_fast=13`, `ema_slow=34`, `rsi_length=14` | 1.694 | 0.413 | 3.579 | 0.57 | 34 |
| V0 | `atr_stop_mult=1.5`, `ema_fast=13`, `ema_slow=34`, `rsi_length=14` | 1.690 | 0.401 | 3.579 | 0.95 | 34 |
| V0 | `atr_stop_mult=2.5`, `ema_fast=13`, `ema_slow=55`, `rsi_length=14` | 1.589 | 0.413 | 2.671 | 0.90 | 42 |
| V0 | `atr_stop_mult=1.5`, `ema_fast=13`, `ema_slow=55`, `rsi_length=14` | 1.447 | 0.401 | 2.172 | 1.49 | 42 |
| V1 | `atr_stop_mult=1.5`, `ema_fast=13`, `ema_slow=55`, `rsi_length=14` | 1.442 | 0.476 | 2.172 | 2.16 | 71 |
| V1 | `atr_stop_mult=2.5`, `ema_fast=13`, `ema_slow=34`, `rsi_length=10` | 1.391 | 0.662 | 2.056 | 1.06 | 73 |

## Top 10 by median OOS PF — USDJPY

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=5` | 3.625 | 0.000 | 6.523 | 1.20 | 15 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=10` | 3.625 | 0.000 | 6.523 | 1.20 | 15 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=20` | 3.625 | 0.000 | 6.523 | 1.20 | 15 |
| V0 | `atr_stop_mult=2.5`, `ema_fast=21`, `ema_slow=34`, `rsi_length=21` | 3.258 | 0.384 | 3.628 | 1.06 | 29 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=20`, `donchian_out=5` | 3.028 | 0.000 | 5.265 | 1.16 | 15 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=20`, `donchian_out=10` | 3.028 | 0.000 | 5.265 | 1.16 | 15 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=20`, `donchian_out=20` | 3.028 | 0.000 | 5.265 | 1.16 | 15 |
| V0 | `atr_stop_mult=1.5`, `ema_fast=21`, `ema_slow=89`, `rsi_length=21` | 2.635 | 0.375 | 5.081 | 1.81 | 40 |
| V1 | `atr_stop_mult=1.5`, `ema_fast=21`, `ema_slow=89`, `rsi_length=21` | 2.615 | 0.399 | 3.988 | 2.27 | 65 |
| V0 | `atr_stop_mult=2.5`, `ema_fast=21`, `ema_slow=89`, `rsi_length=21` | 2.615 | 0.339 | 5.638 | 1.22 | 40 |

## Top 10 by median OOS PF — XAUUSD

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=5` | 52.988 | 1.164 | 6.788 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=10` | 52.988 | 1.164 | 6.788 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=20` | 52.988 | 1.164 | 6.788 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=40`, `donchian_out=5` | 52.533 | 1.448 | 7.345 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=40`, `donchian_out=10` | 52.533 | 1.448 | 7.345 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=40`, `donchian_out=20` | 52.533 | 1.448 | 7.345 | 0.51 | 12 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=5` | 51.790 | 0.961 | 7.926 | 1.02 | 13 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=10` | 51.790 | 0.961 | 7.926 | 1.02 | 13 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=20` | 51.790 | 0.961 | 7.926 | 1.02 | 13 |
| V3 | `atr_stop_mult=2.5`, `bb_length=30`, `bb_std=2.5` | 9.721 | 0.000 | 9.175 | 1.51 | 13 |

---

Source: `src/phase11_search.py` (PR 2 of N). Acceptance gate with Bonferroni-adjusted p-values and primary/control split is scheduled for phase11/pr3 and phase11/pr4 per `docs/phase11_design.md` Amendment A.
# Phase 11 — Grid Search Summary (PR 2)

- grid version: `1`
- total combinations: **123** (cap 140)
- per-variant counts: `V0=36`, `V1=36`, `V2=24`, `V3=27`
- rows written: **96**
- csv: `/tmp/pr5_smoke.csv`

> Runtime mode: **BACKTEST_ONLY**. No live trading. This report cannot toggle any live-trading flag.

> Per-symbol acceptance gate is active (PR 3). The portfolio aggregation + per-pair >40% cap lands in PR 4; even the highest verdict label remains research-only.

## Verdict counts

- `BLOCKED`: 96 row(s)
- `WATCH`: 0 row(s)
- `VALIDATED_RESEARCH_CANDIDATE`: 0 row(s)
- `MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW`: 0 row(s)

_No VALIDATED_RESEARCH_CANDIDATE or MICRO_LIVE_CANDIDATE rows in this run. All OK rows are BLOCKED or WATCH._

## Skip / data-availability summary

- `OK`: 96 row(s)

## Top 10 by median OOS PF — EURUSD

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=5` | 1.643 | 0.000 | 0.000 | 2.02 | 13 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=10` | 1.643 | 0.000 | 0.000 | 2.02 | 13 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=20` | 1.643 | 0.000 | 0.000 | 2.02 | 13 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=5` | 1.352 | 0.000 | 0.000 | 2.05 | 14 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=10` | 1.352 | 0.000 | 0.000 | 2.05 | 14 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=20` | 1.352 | 0.000 | 0.000 | 2.05 | 14 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=5` | 1.239 | 0.000 | 1.185 | 3.06 | 22 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=10` | 1.239 | 0.000 | 1.185 | 3.06 | 22 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=20` | 1.239 | 0.000 | 1.185 | 3.06 | 22 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=40`, `donchian_out=5` | 1.025 | 0.000 | 0.000 | 2.03 | 14 |

## Top 10 by median OOS PF — GBPUSD

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V2 | `atr_stop_mult=2.0`, `donchian_in=10`, `donchian_out=5` | 0.862 | 0.485 | -0.862 | 1.73 | 27 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=10`, `donchian_out=10` | 0.862 | 0.485 | -0.862 | 1.73 | 27 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=5` | 0.835 | 0.082 | -1.060 | 1.52 | 18 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=10` | 0.835 | 0.082 | -1.060 | 1.52 | 18 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=20` | 0.835 | 0.082 | -1.060 | 1.52 | 18 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=10`, `donchian_out=5` | 0.795 | 0.518 | -1.397 | 2.04 | 29 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=10`, `donchian_out=10` | 0.795 | 0.518 | -1.397 | 2.04 | 29 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=5` | 0.795 | 0.072 | -1.397 | 1.53 | 20 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=10` | 0.795 | 0.072 | -1.397 | 1.53 | 20 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=20` | 0.795 | 0.072 | -1.397 | 1.53 | 20 |

## Top 10 by median OOS PF — USDJPY

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=5` | 3.526 | 0.000 | 6.633 | 1.23 | 15 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=10` | 3.526 | 0.000 | 6.633 | 1.23 | 15 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=20`, `donchian_out=20` | 3.526 | 0.000 | 6.633 | 1.23 | 15 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=20`, `donchian_out=5` | 2.959 | 0.000 | 5.365 | 1.19 | 15 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=20`, `donchian_out=10` | 2.959 | 0.000 | 5.365 | 1.19 | 15 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=20`, `donchian_out=20` | 2.959 | 0.000 | 5.365 | 1.19 | 15 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=5` | 2.686 | 0.000 | 5.657 | 1.03 | 11 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=10` | 2.686 | 0.000 | 5.657 | 1.03 | 11 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=20` | 2.686 | 0.000 | 5.657 | 1.03 | 11 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=5` | 2.258 | 0.000 | 3.891 | 1.55 | 18 |

## Top 10 by median OOS PF — XAUUSD

| Variant | Params | Median OOS PF | Worst-fold OOS PF | Median OOS Sharpe | Max OOS DD% | Total OOS trades |
|---------|--------|--------------:|------------------:|------------------:|------------:|-----------------:|
| V2 | `atr_stop_mult=2.0`, `donchian_in=40`, `donchian_out=5` | 99.000 | 1.466 | 7.454 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=40`, `donchian_out=10` | 99.000 | 1.466 | 7.454 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.0`, `donchian_in=40`, `donchian_out=20` | 99.000 | 1.466 | 7.454 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=5` | 99.000 | 1.178 | 6.925 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=10` | 99.000 | 1.178 | 6.925 | 0.51 | 12 |
| V2 | `atr_stop_mult=2.5`, `donchian_in=40`, `donchian_out=20` | 99.000 | 1.178 | 6.925 | 0.51 | 12 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=5` | 99.000 | 0.972 | 8.003 | 1.02 | 13 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=10` | 99.000 | 0.972 | 8.003 | 1.02 | 13 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=40`, `donchian_out=20` | 99.000 | 0.972 | 8.003 | 1.02 | 13 |
| V2 | `atr_stop_mult=1.5`, `donchian_in=20`, `donchian_out=5` | 9.209 | 0.598 | 8.962 | 3.02 | 26 |

---

Source: `src/phase11_search.py` (PR 2 of N). Acceptance gate with Bonferroni-adjusted p-values and primary/control split is scheduled for phase11/pr3 and phase11/pr4 per `docs/phase11_design.md` Amendment A.
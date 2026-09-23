# Stacked MTF v3.3 — Walk-Forward / OOS Check

**Research only.** No live trading. LIVE flags untouched. No IBKR order APIs.
Generated from local data on 2026-09-22 (EDT).

## Setup

| Item | Value |
|------|-------|
| Strategy | Stacked MTF v3.3 (15m + 2H, long-only, `freshOnly=False`, stop OFF) |
| Data | `data/raw/xrpusdt_15m.csv` — 130,533 bars, 2023-01-01 → 2026-09-22 03:15 UTC |
| Costs | `fee_bps=5`, `slippage_bps=2` (per side); entry-on-close |
| Engine | `src/strategy_stacked_mtf.py` → `run_stacked_mtf_backtest` |
| Split (primary) | **Before / on-or-after 2025-09-01 UTC** — matches Pine `splitDate` in `pine/xrp_stacked_mtf_v3.3.pine` |
| Initial equity | $10,000 (settings.yaml backtest default) |

IS and OOS were run as **separate** backtests on sliced OHLCV (independent indicator warm-up). Trade counts therefore do not sum exactly to the full-sample run.

Trade journals:

- `journals/stacked_mtf_wf_is_trades.csv`
- `journals/stacked_mtf_wf_oos_trades.csv`
- `journals/stacked_mtf_wf_full_trades.csv`

---

## Headline: Pine-matching IS / OOS split (2025-09-01)

| Window | Bars | Date range (UTC) | Trades | Net PnL | PF | Win rate | Max DD % |
|--------|-----:|------------------|-------:|--------:|---:|---------:|---------:|
| **In-sample (IS)** | 93,499 | 2023-01-01 → 2025-08-31 | **347** | **+6,083.19** | **1.277** | **32.0%** | **27.17%** |
| **Out-of-sample (OOS)** | 37,034 | 2025-09-01 → 2026-09-22 | **138** | **+2,850.52** | **1.321** | **23.2%** | **17.68%** |
| Full sample (context) | 130,533 | 2023-01-01 → 2026-09-22 | 481 | +11,444.02 | 1.317 | 29.9% | 27.17% |

**Both IS and OOS are net-positive with PF > 1.2 under the stated costs.** OOS win rate is weaker than IS (23% vs 32%), but PF is similar because winners are larger.

### Cost detail (IS / OOS)

| | Gross | Fees | Slippage cost | Net |
|--|------:|-----:|--------------:|----:|
| IS | 8,968.63 | 2,885.44 | 1,154.18 | 6,083.19 |
| OOS | 3,960.91 | 1,110.39 | 444.15 | 2,850.52 |

---

## Critical caveat: OOS is spike-dominated (Aug 2026)

**OOS profitability is not broad-based.** It is dominated by a single explosive period in August 2026:

| Slice | Trades | Net PnL |
|-------|-------:|--------:|
| OOS total | 138 | +2,850.52 |
| **2026-08 only** | **6** | **+3,782.03** |
| OOS **excluding** 2026-08 | 132 | **−931.50** |
| Single largest OOS trade (entry 2026-08-19 → exit 2026-08-22) | 1 | **+4,150.25** |
| OOS excluding that one trade | 137 | **−1,299.73** |

That one trade alone exceeds total OOS net. Several OOS months are negative (e.g. 2025-09 −551, 2025-12 −538, 2026-04 −396, 2026-05 −381).

**Interpretation:** headline OOS “pass” (positive net, PF 1.32) is **fragile**. Without the Aug-2026 spike, OOS fails. Do not treat this as robust out-of-sample validation for live unlock.

IS also has concentration (best IS month 2024-11 ≈ +4,639 ≈ 76% of IS net), but the OOS concentration is more severe: removing one month flips OOS from profit to loss.

---

## Yearly calendar splits (secondary)

Each year run as its own backtest (same fees/slippage). 2026 is partial (through 2026-09-22).

| Year | Bars | Trades | Net PnL | PF | Win rate | Max DD % |
|------|-----:|-------:|--------:|---:|---------:|---------:|
| 2023 | 35,035 | 120 | **−1,659.81** | 0.763 | 30.8% | 21.16% |
| 2024 | 35,136 | 131 | **+5,071.43** | 1.709 | 34.4% | 12.37% |
| 2025 | 35,040 | 148 | **+1,317.64** | 1.103 | 27.0% | 20.78% |
| 2026 (YTD) | 25,322 | 83 | **+5,346.60** | 1.928 | 26.5% | 13.44% |

**Note:** 2023 loses after costs; 2025 barely clears PF 1.1; 2024 and 2026 drive most of the edge. 2026’s strong year number is again heavily tied to the Aug spike.

---

## Buy-and-hold XRP (same windows, no fees)

Close-to-close buy-and-hold on $10k notional for context (not leveraged; no fees modeled):

| Window | Start px | End px | Return % | Approx max DD % | $ PnL on 10k |
|--------|---------:|-------:|---------:|----------------:|-------------:|
| Full | 0.3386 | 1.5146 | **+347.3%** | −72.9% | +34,731 |
| IS (to 2025-08-31) | 0.3386 | 2.7773 | **+720.2%** | −54.1% | +72,023 |
| OOS (from 2025-09-01) | 2.7624 | 1.5146 | **−45.2%** | −68.9% | −4,517 |

Strategy vs B&H:

- **Full / IS:** buy-and-hold crushed the strategy on return, with far larger drawdowns.
- **OOS:** buy-and-hold lost ~45% while the strategy was +~$2.85k — but that OOS edge is the spike-fragile result above, not a clean alpha claim.

---

## Method notes

1. Split aligns with Pine analytics input `timestamp("2025-09-01T00:00:00")`.
2. Generic `src/walk_forward.py` targets the older Apex strategy via `run_backtest_on_df`; this report uses Stacked MTF’s own engine instead.
3. `flip_exits` counter in summarize may under-count; journals use `exit_reason=stack_flip` (and rare `end_of_test`). Use trades / net / PF / WR / DD as authoritative.
4. LIVE unlock / SAFETY / IBKR: **unchanged**. This does not satisfy a robust OOS gate by itself.

## Verdict (research)

| Check | Result |
|-------|--------|
| IS net > 0, PF > 1 | Pass |
| OOS net > 0, PF > 1 (headline) | Pass |
| OOS robust without spike month | **Fail** (ex-Aug 2026 ≈ −$932) |
| All calendar years profitable | **Fail** (2023 negative) |
| Suitable to unlock live | **No** — spike-dependent OOS; leave LIVE blocked |


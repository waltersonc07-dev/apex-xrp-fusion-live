# EUR/USD H1 Strategy — 16-Year Validation Verdict

Status: **DO NOT TRADE LIVE. BACKTEST_ONLY.** This document records the decisive test of the ER trend-breakout strategy (and upgrades) on 16.5 years of clean Dukascopy H1 data.

## Question asked

Can the EUR/USD H1 ER Trend Breakout (which showed PF 1.19 on 3.3 years of OANDA data) go micro-live? And do ADX + circuit-breaker + position-sizing upgrades make it ready?

## Data

Dukascopy EUR/USD H1, 2010-01 -> 2026-06, 111,579 raw bars (98,050 weekday bars after filtering). Bid side. This spans the 2010-12 EU debt crisis, 2014-15 USD bull trend, 2017 range, 2020 COVID shock, 2022 rate-hike trend, and 2023-26 — many regimes. Cost: 1.3 pip round-trip throughout.

## Result 1 — The current production strategy FAILS on 16 years

ER trend breakout, long-only (lb20, ER>=0.30, TP100/SL50):

| Metric | 3.3-yr OANDA (looked good) | 16-yr Dukascopy (the truth) |
|---|---|---|
| Profit factor | 1.19 | **0.94 (losing)** |
| Net | +$495 | **-801 pips** |
| Profitable years | 3 of 4 | **7 of 17** |
| Max drawdown | $541 | 1,961 pips |

The 3.3-year sample sat in a favorable recent stretch (2025 alone was +609 pips, PF 1.79). Across a full decade-plus the strategy loses money. The recent window was not representative.

## Result 2 — The requested upgrades do NOT rescue it

| Upgrade | Best result (16yr) | Verdict |
|---|---|---|
| ADX trend filter (>=15..35) | every threshold LOSES MORE (ADX25 = -2,078 pips) | hurts |
| Regime circuit breaker (2-5 consec losses) | -1,684 to -2,316 pips | no help |
| Higher ER (0.6) | +22 pips, 1/5 years positive, n=140 | noise |
| Wider targets | -1,500 to -1,900 pips | no help |

ADX hurt because strong-ADX breakouts were already late entries. Losing streaks weren't clustered, so the circuit breaker had nothing to catch.

## Result 3 — Best candidate found (4H), still fails the gate

Per prior research ("4H beats 1H, wide targets, both legs"), the strongest survivor was a 4H both-legs breakout (lb30, TP200/SL100):

- 16yr: PF 1.13, +1,741 pips, 11/17 years positive, not outlier-driven (top-3 wins = 4%)
- Walk-forward 5 folds: median PF 1.15, **worst fold PF 0.82**
- Phase 11 gate (median OOS PF >= 1.30 AND worst >= 1.0): **FAIL**

Critically, the edge is DECAYING:
- 2010-2015: strong (PF 1.25, 1.47, 1.82, 1.36, 1.45)
- 2016-2026: weakening (2019: 0.50, 2021: 0.52, 2023: 0.71, 2026: 0.60)
- Most-recent fold (2022-2026): PF 0.82 (losing)

A fading edge is the opposite of a live candidate.

## Verdict

**No micro-live.** No version tested passes the APEX Phase 11 validation gate. The current production strategy is unprofitable over 16 years; the upgrades make it worse; the best alternative (4H) is decaying and fails walk-forward. This confirms the prior 10-year finding: no simple EUR/USD price-pattern carries a durable, tradeable edge.

The validation gate did its job — it prevented a live drawdown.

## Honest strategic options going forward

1. **Multi-instrument portfolio.** A weak per-market edge (PF ~1.1) can become tradeable when diversified across uncorrelated pairs/assets (e.g. the existing XAUUSD, GBPUSD, XRP grid). Test the 4H breakout as a portfolio, not a single market.
2. **Different edge type.** Price-pattern breakouts are crowded. Carry, calendar/seasonality, volatility-regime, or news-reaction edges are structurally different and worth testing on this data.
3. **Accept FX H1/4H has no retail edge** and redirect effort to the parts of APEX with more promise.
4. **Execution alpha, not signal alpha.** If you must trade, focus on cost reduction and risk management around a tiny edge rather than chasing a signal that does not exist.

## Files
- `eurusd_h1_dukascopy.csv` — 16.5yr H1 dataset (reusable for all future FX tests)
- `backtest_engine.py` — reusable engine (load, v1, v2, ADX, circuit breaker, walk-forward)
- `eurusd_h1_er_breakout.pine` — the strategy (kept for reference / paper only)

---
Data: Dukascopy EUR/USD H1 bid, 2010-2026. All figures net of 1.3 pip round-trip cost. Method: chronological walk-forward, no parameter peeking across folds.

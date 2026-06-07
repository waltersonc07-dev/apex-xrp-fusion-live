# Phase 11 — Walk-Forward Optimization: Design Document

**Status**: Design only. **No code in this PR.** Implementation will come in Phase 11 PR series after this design is reviewed and approved.

**Goal**: Find robust variant parameters via walk-forward optimization with strict out-of-sample testing, without falling into the small-sample / overfit / curve-fit traps that the Phase 10 validation gate exists to prevent.

**Non-goals (explicit)**:
- Do NOT lower any Phase 10 gate (40-trade floor, PF 1.5, Sharpe 0.8, etc.) to make Phase 11 "succeed."
- Do NOT enable any live trading flag.
- Do NOT touch validation_gate.py, risk_engine.py, webhook_server.py, exchange_client.py, settings.yaml, .env.example, render.yaml in Phase 11 PRs unless the change is itself a safety hardening.
- Do NOT introduce new symbols. Phase 11 stays on EURUSD/GBPUSD/XAUUSD primary + USDJPY control.

---

## 1. Why walk-forward, not grid search on all data

Optimizing parameters on the *entire* history and reporting the best result is the classic backtest overfit. The selected parameters fit the noise as well as the signal. Walk-forward optimization (WFO) breaks history into rolling in-sample (IS) / out-of-sample (OOS) windows. Parameters are tuned on IS only and **scored on OOS**. The OOS score is the honest performance estimate.

WFO has three practical benefits:

1. **Distinguishes signal from overfit.** If IS Sharpe is high but OOS Sharpe collapses, the parameter is curve-fit. Throw it out.
2. **Adaptive parameters allowed.** Re-fitting per window simulates how the system would actually be re-tuned over time.
3. **Stress-tests regime stability.** Each window covers a different market era. A robust parameter set survives multiple eras.

## 2. WFO design — 5-fold expanding window

Phase 11 uses a **5-fold expanding-window** walk-forward, not a sliding window. Reasoning:

| Approach | Pro | Con |
|---|---|---|
| Sliding (constant IS size) | Same statistical power per window | Discards early history; per-fold OOS too small with daily bars |
| Expanding (growing IS, fixed OOS) | Uses more data per fold; reflects how the system grows | Earlier folds have less power |

We pick expanding because Phase 10 already showed that *bars are scarce* and we cannot afford to discard early history.

### 2.1 Window construction

With ~5000 daily bars per symbol (20 years), Phase 11 splits as:

| Fold | IS start | IS end | OOS start | OOS end | OOS bars |
|---|---|---|---|---|---|
| 1 | bar 210 (post warm-up) | 1800 | 1801 | 2500 | 700 |
| 2 | 210 | 2500 | 2501 | 3200 | 700 |
| 3 | 210 | 3200 | 3201 | 3900 | 700 |
| 4 | 210 | 3900 | 3901 | 4600 | 700 |
| 5 | 210 | 4600 | 4601 | end (~5000) | ~400 |

This gives **5 OOS windows × 4 symbols = 20 OOS evaluations per variant**. Even at the post-filter trade density seen in PR #7 (~16 trades / 5000 bars), each OOS window should produce 1–4 trades — small per-window, but aggregated across folds and symbols, it produces enough samples to be meaningful.

### 2.2 Acceptance rule (proposed)

A variant **PASSes Phase 11** if and only if all of:

- **Median OOS PF ≥ 1.3** across the 5 folds.
- **Median OOS Sharpe ≥ 0.7** across the 5 folds.
- **At least 3 of 5 folds** have OOS PF > 1.0 (stability).
- **Aggregated OOS trade count across all 5 folds × all 4 symbols ≥ 40** (statistical floor preserved at the portfolio level — does NOT lower per-symbol floor).
- **Per-fold IS-to-OOS Sharpe degradation ≤ 30%** (catches overfit: if IS Sharpe drops by more than 30% in OOS, the parameter is curve-fit and rejected).
- All Phase 10 safety gates still apply at the aggregated level (max DD, stress tests, beat buy-and-hold).

These thresholds are **proposed**; they get reviewed and frozen in the first Phase 11 implementation PR.

## 3. Parameter search space

Phase 11 will tune four variants. Search ranges are intentionally narrow to limit the search space (and thus overfit risk):

### V0 — EMA pullback
- `ema_fast`: [13, 21, 34] (3 values)
- `ema_slow`: [34, 55, 89] (3 values, must be > fast)
- `rsi_period`: [10, 14, 21] (3 values)
- `atr_stop_mult`: [1.5, 2.0, 2.5] (3 values)
- Total combos: ~50 (after fast<slow constraint)

### V1 — Mirror of V0
Same ranges as V0.

### V2 — Donchian breakout
- `donchian_entry`: [10, 20, 40] (3 values)
- `donchian_exit`: [5, 10, 20] (3 values, must be ≤ entry)
- `atr_stop_mult`: [1.5, 2.0, 2.5] (3 values)
- Total combos: ~18

### V3 — Bollinger fade
- `bb_period`: [14, 20, 30] (3 values)
- `bb_std`: [1.5, 2.0, 2.5] (3 values)
- `mid_exit`: [true, false] (2 values)
- Total combos: ~18

**Total search size across all variants**: ~140 combinations. Small enough to exhaustively grid-search in minutes; large enough to provide meaningful tuning.

## 4. Multiple-testing correction

Searching 50 combinations per variant means the probability of finding a "good" parameter by chance is non-trivial. Phase 11 will apply a **Bonferroni-adjusted threshold** at the variant level: required OOS PF and Sharpe scale up by `sqrt(N_combos)`. Concretely:

- V0 (50 combos): required median OOS PF ≥ 1.3 × √50/√10 ≈ 2.0.
- V2 (18 combos): required median OOS PF ≥ 1.3 × √18/√10 ≈ 1.55.

This is conservative. The right correction is a topic for the implementation PR; Bonferroni is the strictest reasonable choice and serves as the design's default.

## 5. Portfolio aggregation

A separate Phase 11 PR will add a **portfolio-level scoring layer** on top of per-symbol scoring:

- **Equally-weighted portfolio**: take per-symbol OOS trade series, weight equally, compute portfolio PF/Sharpe/DD.
- **Aggregated trade count** is the sum across symbols × folds. With 4 symbols × 5 folds × ~10 trades each = ~200 trades — comfortably above the statistical floor.
- **Portfolio PASS criteria** mirror per-symbol but at the aggregate level. A variant might PASS at the portfolio level without PASSing at any individual symbol — that's acceptable provided the per-symbol behavior isn't catastrophic on any one pair (max per-symbol DD ≤ 30%, no per-symbol PF < 0.7 in any fold).

The portfolio layer is what gives Phase 11 a realistic path to MICRO_LIVE candidates without relaxing the per-symbol gate.

## 6. Bayesian extension (optional, post-MVP)

Beyond the frequentist gate, Phase 11+ may add a Bayesian posterior PF using a Jeffreys prior. The decision rule becomes:

> "Approve as MICRO_LIVE candidate if posterior P(true PF > 1.2 | observed trades) ≥ 0.8."

This handles small samples honestly: with few trades, the prior dominates and conclusions are humble. With many trades, the data dominates. Either way, the threshold is interpretable.

This is **not** required for the first Phase 11 PR but is the natural next step.

## 7. Phase 11 PR plan (proposed)

| PR | Scope | Acceptance |
|---|---|---|
| Phase 11 / PR 1 | Walk-forward orchestrator + 5-fold splitter + per-fold reporter (no parameter search yet — just runs default params through WFO) | Reproduces PR #7 numbers when fed default params; new tests cover splitter invariants (no leakage, monotone windows, correct OOS sizes) |
| Phase 11 / PR 2 | Grid search engine + per-variant search space registry | Search runs in <5 min locally; CSV of all (variant, params, fold, OOS metrics) saved to `reports/phase11_search.csv` |
| Phase 11 / PR 3 | Acceptance gate (median, stability, degradation rules) + multiple-testing correction | New gate runs after Phase 10 gate; emits PASS/BLOCK to `reports/phase11_verdict.md`; existing Phase 10 gate is NOT modified |
| Phase 11 / PR 4 | Portfolio aggregation layer | Portfolio scoring report; integration test: at least one variant should not catastrophically fail on any single symbol |
| Phase 11 / PR 5 | Bayesian extension (optional) | Posterior PF reported alongside frequentist; can be toggled off |

Each PR follows the Phase 10 conventions:
- Branch naming: `phase11/prN-<slug>`.
- Squash-merge.
- Safety check + tests must be green.
- Author: `waltersonc07-dev`.
- Read-only cron unchanged.

## 8. What Phase 11 will NOT do

- **No live trading.** All work stays in `BACKTEST_ONLY`.
- **No new symbols.** EURUSD/GBPUSD/XAUUSD/USDJPY only.
- **No intraday data.** Daily bars only.
- **No relaxation of Phase 10 gates.** They stand. Phase 11 is an additional layer on top.
- **No XRP strategy changes.** That code is frozen.
- **No optimization on test data.** All optimization happens on IS; OOS is held out.

## 9. Risk register

| Risk | Mitigation |
|---|---|
| Walk-forward overfit (parameters tuned on early data don't survive recent data) | Per-fold IS→OOS degradation cap (30%) catches this and rejects the variant |
| Multiple-testing false discovery | Bonferroni correction (Section 4) |
| Lookahead bias in IS window | Splitter enforces strict cutoff; new tests verify no future bar leaks into IS |
| Survivorship bias on data | Yahoo data has no survivorship issue for FX/gold (no delisting); flagged for review on any future symbol addition |
| Regime-specific overfit (parameters fit one fold's regime) | At least 3/5 folds must have OOS PF > 1.0 — single-fold winners are rejected |
| Capacity / slippage drift | Phase 10 stress tests (2× fees, 2× slippage) apply at the aggregated portfolio level |

## 10. Cross-references

- `docs/phase10_threshold_review.md` (PR #8) — why Phase 10 gates stay where they are.
- `config/settings.yaml` — gate thresholds, untouched by Phase 11.
- `src/validation_gate.py` — Phase 10 gate, untouched by Phase 11.
- `src/phase10_filters.py` — filters used as-is in Phase 11 WFO.
- `src/phase10_fx_gold_daily.py` — backtest engine, called from new Phase 11 orchestrator.
- `SAFETY.md` — the safety contract Phase 11 PRs must continue to honor.

## 11. Open questions for owner review

These are the decisions worth confirming before Phase 11 / PR 1 lands:

1. **5 folds correct?** Or prefer 3 or 7?
2. **30% IS→OOS Sharpe degradation cap** — too strict, too loose?
3. **Bonferroni** vs Benjamini–Hochberg for multiple-testing correction?
4. **Portfolio scoring weights** — equal-weight, or volatility-target each symbol?
5. **Phase 11 acceptance thresholds (median OOS PF ≥ 1.3, Sharpe ≥ 0.7)** — keep, tighten, or loosen?

Defaults are reasonable starting points; the owner can override before implementation.

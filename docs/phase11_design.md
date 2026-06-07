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

---

# Phase 11 Amendment A — Owner Decisions (2026-06-07)

**Status**: Binding. These rules supersede any conflicting default above and MUST be implemented by the first Phase 11 code PR (`phase11/pr1-walkforward-orchestrator`). No Phase 11 variant coding may begin until each item below is wired into code and protected by a test.

The owner reviewed the design and approved Phase 11 with stricter anti-overfit guardrails. The decisions, verbatim by item, are codified here.

## A.1 Walk-forward design — APPROVED

Keep the **5-fold expanding** WFO from Section 2. Expanding (train on past, test on future) matches real trading and is preferred over random splits.

## A.2 Parameter grid — APPROVED with cap and freeze rule

- Keep the ~140-combination grid defined in Section 3.
- **Hard cap**: the total grid size MUST NOT exceed **140 combinations** across all variants combined.
- **Freeze rule**: the grid is frozen *before* the first WFO run. The frozen grid is checked into `config/phase11_grid.yaml` in Phase 11 / PR 2.
- **No post-hoc additions**: if a parameter is added or a range widened after results are seen, the entire Phase 11 run is invalidated and must restart from PR 1.
- Any pre-run change to the grid requires a written justification committed to `docs/phase11_grid_changelog.md` *before* the run, including: parameter added/changed, prior, hypothesis, expected effect.

**Rationale**: more combinations = more data-mining risk. The grid must be a pre-registered hypothesis, not a search-until-you-find exercise.

## A.3 Multiple-testing correction — APPROVED with full reporting

Replace Section 4's single-number Bonferroni with a **two-track report**. For every variant × parameter combination, the Phase 11 verdict report MUST include:

| Column | Definition |
|---|---|
| `raw_p` | Uncorrected p-value for the OOS performance vs the null (PF = 1.0) |
| `bonferroni_p` | `raw_p × N_tested` where `N_tested` is the total grid size (cap 140) |
| `n_tested` | The actual grid size used in this run (must equal the frozen grid size) |
| `survives_raw` | `raw_p < 0.05` |
| `survives_bonferroni` | `bonferroni_p < 0.05` |
| `verdict` | `PASS` only if `survives_bonferroni == true` AND all gates in A.5 pass |

Both tracks are reported so reviewers can see whether a "winner" is real or simply lucky. Acceptance still requires the **Bonferroni-adjusted** result to survive; raw is informational only.

## A.4 Portfolio aggregation — APPROVED with primary/control split

Section 5's portfolio layer is amended to **separate primary from control assets**:

- **Primary assets** (eligible to drive a PASS verdict): EURUSD, GBPUSD, XAUUSD.
- **Control assets** (informational only, can BLOCK but cannot PASS): USDJPY and any future non-primary pair.
- The portfolio PF/Sharpe/DD used in the acceptance gate is computed on **primary assets only**.
- Control assets are reported alongside but a control failure does NOT block a primary PASS — *unless* the control failure is catastrophic (per-control PF < 0.5 in 3 of 5 folds), in which case the variant is downgraded to `WATCH` and cannot become a MICRO_LIVE candidate.

**Rationale**: a strategy that only works on one random pair is weaker than one that generalizes; but a weak control pair shouldn't destroy a valid primary edge.

## A.5 Acceptance gate — APPROVED with two added rules

The Section 2.2 gate is amended. A variant PASSes Phase 11 if and only if **ALL** of the following hold (existing rules in regular type, **new rules in bold**):

1. Median OOS PF ≥ **1.30** across the 5 folds (primary portfolio).
2. Median OOS Sharpe ≥ **0.70** across the 5 folds (primary portfolio).
3. At least **3 of 5 folds** have OOS PF > 1.0.
4. Per-fold IS→OOS Sharpe degradation ≤ **30%**.
5. Aggregated OOS trade count across 5 folds × 3 primary symbols ≥ **40**.
6. **NEW — Minimum OOS trades per fold**: every one of the 5 folds must have ≥ **5 OOS trades** at the primary-portfolio level. A fold with fewer than 5 trades is treated as `INSUFFICIENT_DATA` and the variant is BLOCKed regardless of other metrics.
7. **NEW — No single-pair dominance**: no single primary pair may contribute more than **40%** of total net profit across the full WFO. If one pair exceeds 40%, the variant is downgraded to `WATCH` and cannot become a MICRO_LIVE candidate.
8. Bonferroni-adjusted p-value < 0.05 (from A.3).
9. All Phase 10 safety gates still apply at the aggregated level (max DD, stress tests, beat buy-and-hold).

**Rationale**: rules 6 and 7 prevent one lucky pair or one lucky fold from carrying the whole result.

## A.6 Ranking rule — APPROVED, no best-PF-only ranking

The Phase 11 verdict report MUST rank candidates by a composite score, **NOT** by best PF alone. The ranking order, in priority:

1. **Median OOS PF** (primary portfolio)
2. **Worst-fold OOS PF** (stability)
3. **OOS Sharpe**
4. **Maximum drawdown** (smaller is better)
5. **Consistency across pairs** — measured as standard deviation of per-pair OOS PF; lower is better
6. **Parameter simplicity** — variants with fewer tuned parameters break ties

The report includes all six columns, sorted by rule 1, with ties broken by rule 2, etc. **The single highest-PF variant is NOT the recommended candidate** unless it also wins on stability.

**Rationale**: the best live candidate is not the highest PF — it is the most repeatable one.

## A.7 Live readiness — APPROVED, never auto-activate

Even if a variant passes every gate above, Phase 11 output is **never** a green light for live trading. The verdict report uses exactly these labels:

| Label | Meaning |
|---|---|
| `BLOCKED` | Fails any gate in A.5 |
| `WATCH` | Passes some but fails a downgrade rule (A.4 control catastrophe or A.5 rule 7 dominance) |
| `VALIDATED_RESEARCH_CANDIDATE` | Passes all Phase 11 gates; suitable for further research, NOT live |
| `MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW` | Passes all Phase 11 gates AND has 60+ days of paper-trading evidence; still requires explicit owner sign-off in `docs/microlive_approvals.md` before any flag flip |

**Actual runtime mode remains `BACKTEST_ONLY`** regardless of verdict. `LIVE_TRADING`, `MICRO_LIVE`, and `FULL_LIVE` stay `false`. No code path in Phase 11 may set, suggest, or auto-toggle any of these flags. The flip is always a manual owner action in the Render dashboard.

## A.8 Implementation checklist (binding on Phase 11 / PR 1)

The first Phase 11 code PR is BLOCKed from merge until each item is implemented and covered by a test:

- [ ] Frozen grid file `config/phase11_grid.yaml` with `n_combos ≤ 140`, validated at startup
- [ ] Grid changelog file `docs/phase11_grid_changelog.md` initialized
- [ ] Verdict report emits all 6 columns from A.3 (raw_p, bonferroni_p, n_tested, survives_raw, survives_bonferroni, verdict)
- [ ] Primary/control split in portfolio aggregator (A.4)
- [ ] Acceptance gate enforces rules 6 and 7 from A.5 (min-trades-per-fold, no-single-pair-dominance)
- [ ] Ranking output sorts by composite key from A.6
- [ ] Verdict labels restricted to the four strings in A.7
- [ ] Test: a synthetic single-pair-dominant variant is downgraded to WATCH
- [ ] Test: a synthetic low-OOS-trade fold blocks the variant
- [ ] Test: a synthetic high-raw / failed-Bonferroni result is BLOCKed (not PASSed)
- [ ] Test: no code path can set `risk.mode`, `LIVE_TRADING`, `MICRO_LIVE`, or `FULL_LIVE`

## A.9 Supersession notes

Where this amendment conflicts with sections 1–11 above, **this amendment wins**. Specifically:

- Section 2.2 acceptance rule → superseded by A.5
- Section 4 multiple-testing handling → superseded by A.3
- Section 5 portfolio aggregation → superseded by A.4 (primary/control split)
- Section 7 PR plan → PR 1 scope expanded by A.8 checklist
- Section 11 open questions → resolved by owner; defaults stand as amended

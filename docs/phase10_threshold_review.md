# Phase 10 — Validation Gate Threshold Review

**Status**: Discussion-only. **No code or config change in this PR.** Any change to thresholds must come in a separate, deliberate PR after this discussion is resolved.

**Owner decision required (recorded in conversation)**: keep `min_trades_per_asset = 40`.

This document records *why* the floor stays at 40, what alternatives were considered, and what evidence would be needed to revisit each threshold.

---

## 1. Current thresholds (config/settings.yaml + validation_gate.py)

| Threshold | Value | Rule |
|---|---|---|
| `min_profit_factor` | 1.50 | In-sample PF must clear |
| `min_oos_profit_factor` | 1.20 | Out-of-sample PF must clear |
| `max_drawdown_pct` | 25.0 | Max drawdown cap |
| `min_sharpe` | 0.80 | In-sample Sharpe must clear |
| `min_trades_per_asset` | **40** | In-sample trade count floor |
| `must_beat_buy_and_hold` | true | Strategy must beat passive |
| `stress_2x_fees_profitable` | true | Must remain profitable at 2× fees |
| `stress_2x_slippage_profitable` | true | Must remain profitable at 2× slippage |
| `walk_forward_unstable_max` | 1 | At most 1 losing window of N |

Source: `config/settings.yaml` (not modified in this PR).

## 2. The 40-trade floor — current bottleneck

After PR #7 (20-year history) the filtered run produces these trade counts:

| Symbol | V0 | V1 | V2 | V3 |
|---|---|---|---|---|
| EURUSD | 15 | 21 | 14 | 21 |
| GBPUSD | 6 | 16 | 12 | 16 |
| XAUUSD | 18 | 25 | 27 | 19 |
| USDJPY | 10 | 26 | 12 | 14 |

**Median: 16 trades.** **Zero variants ≥ 40.** Several pairs show promising PF/Sharpe (EURUSD V2 PF 1.94 Sharpe 4.02; USDJPY V0 PF 5.59 Sharpe 6.54; USDJPY V2 PF 6.78 Sharpe 7.56) — but on tiny samples that the gate refuses to certify.

## 3. Why we keep 40

### 3.1 Statistical reasoning

A profit factor or Sharpe estimated from `n < 30` trades is dominated by noise. The 95% confidence interval on PF widens roughly as `1/√n`:

- n=10 → PF CI ≈ [0.4 × point, 2.5 × point]. A point estimate of 2.0 means the true PF could be anywhere from 0.8 to 5.0.
- n=30 → CI ≈ [0.65 × point, 1.55 × point]. Tighter but still wide.
- n=40 → CI ≈ [0.70 × point, 1.45 × point]. The first sample size at which we can defensibly say PF > 1.5 with reasonable confidence.

40 trades is the floor most quantitative trading texts recommend as the absolute minimum for ratios to mean anything. It is not aggressive — it is the lower bound.

### 3.2 Walk-forward viability

The walk-forward test uses 3 windows. At 40 trades total, each window has ~13 trades — already too few for stable per-window metrics. Going *below* 40 would make walk-forward stability checks essentially noise. Going *above* 40 would be safer but make Phase 10 impractical on daily bars.

### 3.3 Operational reality

A variant that produces fewer than 40 trades in 20 years on daily bars is producing **fewer than 2 trades per year per symbol**. Even if such a variant has a real edge, the realized P&L cadence is too slow to validate before drift kills it.

## 4. Alternatives considered

### Option A — Lower to 30 (rejected)

**Pro**: Several promising filtered variants would become testable (XAUUSD V2 n=27 would still fail; USDJPY V1 n=26 would still fail; nothing actually clears 30 either in this dataset).

**Con**: Even if we lowered to 30, **no variant clears it** in the current data. Lowering would deliver no PASSes — it would only erode the statistical floor for future PRs.

**Verdict**: Rejected. No win, statistical cost.

### Option B — Lower to 20 (strongly rejected)

**Pro**: Variants like XAUUSD V2 (n=27), USDJPY V1 (n=26), and EURUSD V1/V3 (n=21) would clear.

**Con**: At n=20, a PF point estimate of 2.0 has a 95% CI of roughly [0.55, 3.6]. We would be certifying variants whose true PF could be below 1.0. This is exactly the kind of small-sample overfit that the gate exists to prevent. It also makes the walk-forward 3-window test mathematically meaningless.

**Verdict**: Strongly rejected.

### Option C — Keep 40, broaden the regime whitelist (deferred to Phase 11)

**Pro**: Including `ranging` regimes for mean-reversion variants (V3 Bollinger) could yield more trades without lowering the statistical floor.

**Con**: This is a *strategy* change, not a *threshold* change. It belongs in Phase 11 design (PR #9), not in a threshold-review PR.

**Verdict**: Defer to PR #9.

### Option D — Move to higher-frequency bars (out of Phase 10 scope)

**Pro**: 4-hour or 1-hour bars would produce vastly more trades per year, easily clearing 40.

**Con**: Phase 10 is explicitly daily research. Intraday work requires intraday data, intraday regime classification, session-of-day filters (not session-of-week), and very different slippage/fee assumptions. Out of scope.

**Verdict**: Deferred to a future phase. Not a Phase 10 decision.

## 5. What would change my mind on the 40 floor

1. **Multi-asset portfolio scoring.** If we aggregate across symbols (e.g., 4 symbols × 1 variant = 80+ trades pooled), per-portfolio metrics can clear. This requires a portfolio-level metric definition that the gate does not currently support. Worth designing in Phase 11.
2. **Bayesian PF with a prior.** Replace the point-estimate gate with a posterior probability that true PF > 1. Different math, same conservatism, smaller sample needs. Also Phase 11+.
3. **Walk-forward dominance.** If walk-forward shows 3/3 windows profitable with consistent PF across all 3, we have weak evidence of stability even at small n. The current gate already requires walk-forward stability — but tightening walk-forward instead of relaxing trade count is the right direction.

## 6. Decision

**Keep `min_trades_per_asset = 40`.** No code change in this PR. This document is the audit trail.

Revisit only if:
- A future PR provides Bayesian or portfolio-aggregated scoring, **or**
- Operational evidence (paper trading + manual review) shows a specific variant deserves bespoke handling, in which case it gets a manual MICRO_LIVE candidate review per `SAFETY.md`, not a gate change.

## 7. Cross-references

- `config/settings.yaml` — defines all thresholds.
- `src/validation_gate.py` — enforces them.
- `tests/test_validation_gate.py` — proves enforcement.
- `tests/test_phase10_filtered_verdict.py` — guards against accidental PASS sneaking into main.
- `reports/phase10_verdict_filtered.md` — current 16/16 BLOCK status.
- `docs/phase11_design.md` (PR #9, upcoming) — walk-forward design that may address the small-sample bottleneck without lowering this floor.

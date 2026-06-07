# Phase 11 — Grid Changelog

This file records every change to `config/phase11_grid.yaml` **before** that change is used in a walk-forward optimization run. Per `docs/phase11_design.md` Amendment A § A.2:

> Any pre-run change to the grid requires a written justification committed to `docs/phase11_grid_changelog.md` *before* the run, including: parameter added/changed, prior, hypothesis, expected effect.

> No post-hoc additions: if a parameter is added or a range widened after results are seen, the entire Phase 11 run is invalidated and must restart from PR 1.

Each entry follows the template:

```
## NNN — YYYY-MM-DD — short title
- Author:
- Parameter(s) added/changed/removed:
- Prior (what the grid looked like before):
- Hypothesis (what we expect this change to test):
- Expected effect (on combo count, on which variant, on which gate):
- Reviewed by:
```

---

## 001 — 2026-06-07 — Initial freeze (pre-WFO baseline)

- **Author**: waltersonc07-dev
- **Parameter(s) added/changed/removed**:
  - Removed `V3.mid_exit` (boolean toggle from design doc Section 3). The Phase 10 engine (`src/phase10_fx_gold_daily.py::_v3_signals`) does not implement a Bollinger-mid-band exit, so the toggle would have no effect. Adding it would create a "ghost" parameter — the grid-search engine would generate paired runs with identical results, doubling the V3 combo count for no information.
  - Trimmed `V0.ema_fast` and `V1.ema_fast` from `[13, 21, 34]` to `[13, 21]` (dropped 34). The design doc estimated ~50 combos per V0/V1; the full 3×3 EMA pair grid produces 8 valid (fast < slow) pairs × 3 RSI × 3 ATR = 72 combos per variant, which would total 195 across all four variants and breach the 140 cap.
  - Trimmed `V0.atr_stop_mult` and `V1.atr_stop_mult` from `[1.5, 2.0, 2.5]` to `[1.5, 2.5]`. Same rationale: needed to keep the total under the hard cap. The 2.0 mid-value is still represented in V2 and V3 grids, so the loss of information at the V0/V1 level is limited to the interior point.
- **Prior**: empty (this is the initial freeze; no `config/phase11_grid.yaml` existed before this entry).
- **Hypothesis**: A 123-combo grid spread across four variants is enough to characterize the parameter sensitivity of each strategy family while staying comfortably below the 140 cap. The dropped `ema_fast = 34` and `atr_stop_mult = 2.0` points are documented and recoverable in a future explicitly-justified expansion if Phase 11 results suggest the boundary cases matter.
- **Expected effect**:
  - V0: 36 combos (was 72 in the full grid)
  - V1: 36 combos (was 72 in the full grid)
  - V2: 24 combos (was 27 in the full grid; engine doesn't change)
  - V3: 27 combos (was 18 in design doc estimate; ATR triplet added for consistency with V0–V2)
  - **Total: 123 combos** (under the 140 hard cap by 17 combos)
  - Gate impact: none in PR 2 (acceptance gate lands in PR 3). The narrower V0/V1 grid will slightly reduce the false-discovery surface area that the Bonferroni correction in PR 3 must cover.
- **Reviewed by**: pending owner review (this is the initial PR; owner approves by merging phase11/pr2-grid-search)

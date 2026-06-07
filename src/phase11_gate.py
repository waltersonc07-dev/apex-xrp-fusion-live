"""
Phase 11 — Acceptance gate + raw/Bonferroni p-values + verdict labels (PR 3).

This module is the per-combo acceptance gate (Amendment A § A.3 + § A.5).
It is layered on top of ``run_grid_search`` output (PR 2) and emits a
verdict for each ``(combo × symbol)`` row.

PR 3 scope (this file):

  1. p-value estimator — one-sided one-sample t-test of per-fold OOS
     Sharpe ratios vs 0 (alternative = greater). This tests the null
     "the variant has zero risk-adjusted edge in OOS." We use OOS
     Sharpe (not OOS PF directly) because Sharpe is approximately
     normal across folds and gives a defensible parametric p-value
     without bootstrap. ``raw_p`` is informational only; the gate uses
     the Bonferroni-adjusted value.
  2. Bonferroni adjustment — ``bonferroni_p = min(1.0, raw_p * n_tested)``
     where ``n_tested`` is the frozen grid size (cap 140). This is the
     strictest reasonable multiple-testing correction per Amendment A.
  3. Per-combo verdict labels (Amendment A § A.6):
        BLOCKED
        WATCH
        VALIDATED_RESEARCH_CANDIDATE
        MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW
     Even the highest label requires explicit manual owner approval to
     enable live trading. Runtime is ALWAYS ``BACKTEST_ONLY``.

PR 3 deliberately ships WITHOUT:

  * Primary/control portfolio aggregation. PR 3 emits a per-symbol gate
    only. PR 4 will aggregate folds across the three primary symbols
    (EURUSD / GBPUSD / XAUUSD), score the portfolio, and enforce the
    per-pair >40% net-profit cap. The per-symbol gate is still useful
    on its own as a diagnostic and as a strict upper bound: nothing
    that fails the per-symbol gate can pass the portfolio gate.
  * Bayesian posterior intervals (PR 5).

This module does not import or touch ``validation_gate``, ``risk_engine``,
``webhook_server``, or ``exchange_client``. It cannot toggle any live
trading flag.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence


# Acceptance gate thresholds (Amendment A § A.5, primary portfolio).
# These are also used as the per-symbol gate in PR 3 (defense-in-depth:
# nothing that fails per-symbol can pass at the portfolio level either).
MIN_MEDIAN_OOS_PF: float = 1.30
MIN_MEDIAN_OOS_SHARPE: float = 0.70
MIN_FOLDS_WITH_OOS_PF_GT_1: int = 3
MIN_FOLD_OOS_TRADES: int = 5
MIN_TOTAL_OOS_TRADES: int = 40
MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT: float = 30.0
SIGNIFICANCE_ALPHA: float = 0.05

# Worst-fold OOS PF bar for the MICRO_LIVE_CANDIDATE label. This is
# stricter than the median bar — it requires every fold to be profitable
# (PF > 1.0). The label itself is research-only; live trading still
# requires manual owner approval.
MIN_WORST_FOLD_OOS_PF_FOR_MICRO_LIVE: float = 1.00


# Verdict labels — see Amendment A § A.6 in docs/phase11_design.md.
VERDICT_BLOCKED = "BLOCKED"
VERDICT_WATCH = "WATCH"
VERDICT_VALIDATED_RESEARCH_CANDIDATE = "VALIDATED_RESEARCH_CANDIDATE"
VERDICT_MICRO_LIVE_CANDIDATE = "MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW"

ALL_VERDICTS: tuple[str, ...] = (
    VERDICT_BLOCKED,
    VERDICT_WATCH,
    VERDICT_VALIDATED_RESEARCH_CANDIDATE,
    VERDICT_MICRO_LIVE_CANDIDATE,
)


@dataclass(frozen=True)
class GateResult:
    """Outcome of applying the acceptance gate to a single combo×symbol row."""
    raw_p: float
    bonferroni_p: float
    n_tested: int
    survives_raw: bool
    survives_bonferroni: bool
    verdict: str
    # Human-readable reason that landed this verdict. Stored so reviewers
    # can audit why something was blocked or downgraded.
    reason: str


# ---------------------------------------------------------------------------
# p-value math
# ---------------------------------------------------------------------------


def _student_t_sf(t: float, df: int) -> float:
    """Survival function of Student's t (one-sided upper tail).

    Pure-Python implementation using the regularized incomplete beta
    function so we don't take a hard dependency on scipy in CI. Accurate
    to ~1e-9 for the small df we use here (df = n_folds - 1, typically
    4). For df <= 0 or t == NaN we return 1.0 (no evidence).
    """
    if df <= 0 or not _isfinite(t):
        return 1.0
    # P(T > t) = 0.5 * I_{x}(df/2, 1/2) where x = df / (df + t**2),
    # and the sign of t selects the tail.
    x = df / (df + t * t)
    a = df / 2.0
    b = 0.5
    ib = _regularized_incomplete_beta(x, a, b)
    if t >= 0.0:
        return 0.5 * ib
    else:
        return 1.0 - 0.5 * ib


def _isfinite(x: float) -> bool:
    try:
        return math.isfinite(x)
    except (TypeError, ValueError):
        return False


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    """Regularized incomplete beta function I_x(a, b).

    Uses the continued-fraction expansion (Numerical Recipes 6.4) which
    converges quickly for the parameter ranges we hit (a small int/half,
    b = 0.5, x in (0, 1)).
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    # Use the symmetry I_x(a,b) = 1 - I_{1-x}(b,a) when x is large for
    # better convergence of the continued fraction.
    if x >= (a + 1.0) / (a + b + 2.0):
        return 1.0 - _regularized_incomplete_beta(1.0 - x, b, a)
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(math.log(x) * a + math.log1p(-x) * b + lbeta) / a
    return front * _betacf(x, a, b)


def _betacf(x: float, a: float, b: float, max_iter: int = 200,
            eps: float = 3e-12) -> float:
    """Continued-fraction expansion used by ``_regularized_incomplete_beta``."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h


def one_sided_t_pvalue(fold_oos_sharpes: Sequence[float]) -> float:
    """One-sided one-sample t-test of fold OOS Sharpes vs 0.

    Null: mean OOS Sharpe = 0. Alternative: mean > 0.

    Returns p in [0, 1]. Degenerate inputs (n < 2, zero variance, NaN)
    return 1.0 — no evidence against the null.
    """
    n = len(fold_oos_sharpes)
    if n < 2:
        return 1.0
    xs = [float(x) for x in fold_oos_sharpes if _isfinite(x)]
    if len(xs) < 2:
        return 1.0
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    if var <= 0.0 or not _isfinite(var):
        # All identical Sharpes — degenerate. Return a trivially
        # discriminating value: 0.0 if mean > 0, else 1.0. Bonferroni
        # will still multiply by n_tested.
        return 0.0 if mean > 0.0 else 1.0
    se = math.sqrt(var / len(xs))
    if se <= 0.0:
        return 0.0 if mean > 0.0 else 1.0
    t = mean / se
    return _student_t_sf(t, df=len(xs) - 1)


def bonferroni_adjust(raw_p: float, n_tested: int) -> float:
    """Bonferroni adjustment, clamped to [0, 1]."""
    if n_tested <= 0:
        return raw_p
    val = raw_p * float(n_tested)
    if val < 0.0:
        return 0.0
    if val > 1.0:
        return 1.0
    return val


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------


def _count_folds_with_oos_pf_gt_1(fold_payloads: Iterable[dict]) -> int:
    cnt = 0
    for f in fold_payloads:
        pf = f.get("oos_pf")
        if pf is None:
            continue
        try:
            if float(pf) > 1.0:
                cnt += 1
        except (TypeError, ValueError):
            continue
    return cnt


def evaluate_gate(
    *,
    status: str,
    summary: dict,
    folds: Sequence[dict] | None,
    n_tested: int,
) -> GateResult:
    """Apply the acceptance gate to a single (combo × symbol) result.

    ``folds`` is the per-fold payload list from the orchestrator. We
    extract OOS Sharpes from it to compute the p-value. ``summary`` is
    the orchestrator's per-symbol summary dict. ``n_tested`` is the
    frozen grid size used for Bonferroni adjustment.
    """
    # 0. INSUFFICIENT_DATA / ERROR rows: BLOCK with raw_p = 1.0.
    if status != "OK" or not summary:
        return GateResult(
            raw_p=1.0,
            bonferroni_p=1.0,
            n_tested=n_tested,
            survives_raw=False,
            survives_bonferroni=False,
            verdict=VERDICT_BLOCKED,
            reason=f"status={status!r} or empty summary",
        )

    folds = folds or []

    # 1. Compute p-values up front so we always emit them, even when
    #    other gate checks block the row. (Reviewers want to see p
    #    next to a BLOCKED label too.)
    fold_oos_sharpes: list[float] = []
    for f in folds:
        s = f.get("oos_sharpe")
        if s is None:
            continue
        try:
            fold_oos_sharpes.append(float(s))
        except (TypeError, ValueError):
            continue
    raw_p = one_sided_t_pvalue(fold_oos_sharpes)
    adj_p = bonferroni_adjust(raw_p, n_tested)
    survives_raw = raw_p < SIGNIFICANCE_ALPHA
    survives_bonferroni = adj_p < SIGNIFICANCE_ALPHA

    # 2. Structural / data sufficiency gates (Amendment A § A.5).
    min_fold_trades = int(summary.get("min_fold_oos_trades", 0) or 0)
    total_trades = int(summary.get("total_oos_trades", 0) or 0)
    median_pf = float(summary.get("median_oos_pf", 0.0) or 0.0)
    worst_pf = float(summary.get("worst_fold_oos_pf", 0.0) or 0.0)
    median_sharpe = float(summary.get("median_oos_sharpe", 0.0) or 0.0)
    max_degradation = float(
        summary.get("max_is_to_oos_sharpe_degradation_pct", 0.0) or 0.0
    )
    folds_above_one = _count_folds_with_oos_pf_gt_1(folds)

    failed_gates: list[str] = []
    if min_fold_trades < MIN_FOLD_OOS_TRADES:
        failed_gates.append(
            f"min_fold_oos_trades={min_fold_trades} < {MIN_FOLD_OOS_TRADES}"
        )
    if total_trades < MIN_TOTAL_OOS_TRADES:
        failed_gates.append(
            f"total_oos_trades={total_trades} < {MIN_TOTAL_OOS_TRADES}"
        )
    if median_pf < MIN_MEDIAN_OOS_PF:
        failed_gates.append(
            f"median_oos_pf={median_pf:.3f} < {MIN_MEDIAN_OOS_PF:.2f}"
        )
    if median_sharpe < MIN_MEDIAN_OOS_SHARPE:
        failed_gates.append(
            f"median_oos_sharpe={median_sharpe:.3f} < "
            f"{MIN_MEDIAN_OOS_SHARPE:.2f}"
        )
    if folds_above_one < MIN_FOLDS_WITH_OOS_PF_GT_1:
        failed_gates.append(
            f"folds_with_oos_pf>1={folds_above_one} < "
            f"{MIN_FOLDS_WITH_OOS_PF_GT_1}"
        )
    if max_degradation > MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT:
        failed_gates.append(
            f"max_is_to_oos_sharpe_degradation_pct={max_degradation:.1f}% > "
            f"{MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT:.0f}%"
        )

    if failed_gates:
        return GateResult(
            raw_p=raw_p,
            bonferroni_p=adj_p,
            n_tested=n_tested,
            survives_raw=survives_raw,
            survives_bonferroni=survives_bonferroni,
            verdict=VERDICT_BLOCKED,
            reason="; ".join(failed_gates),
        )

    # 3. All structural gates passed. Decide between WATCH /
    #    VALIDATED_RESEARCH_CANDIDATE / MICRO_LIVE_CANDIDATE based on
    #    Bonferroni significance and worst-fold OOS PF.
    if not survives_bonferroni:
        return GateResult(
            raw_p=raw_p,
            bonferroni_p=adj_p,
            n_tested=n_tested,
            survives_raw=survives_raw,
            survives_bonferroni=False,
            verdict=VERDICT_WATCH,
            reason=(
                f"structural gates pass; bonferroni_p={adj_p:.4f} "
                f">= {SIGNIFICANCE_ALPHA}"
            ),
        )

    if worst_pf < MIN_WORST_FOLD_OOS_PF_FOR_MICRO_LIVE:
        return GateResult(
            raw_p=raw_p,
            bonferroni_p=adj_p,
            n_tested=n_tested,
            survives_raw=survives_raw,
            survives_bonferroni=True,
            verdict=VERDICT_VALIDATED_RESEARCH_CANDIDATE,
            reason=(
                f"all gates pass + bonferroni significant; "
                f"worst_fold_oos_pf={worst_pf:.3f} < "
                f"{MIN_WORST_FOLD_OOS_PF_FOR_MICRO_LIVE:.2f} "
                "blocks MICRO_LIVE label"
            ),
        )

    return GateResult(
        raw_p=raw_p,
        bonferroni_p=adj_p,
        n_tested=n_tested,
        survives_raw=survives_raw,
        survives_bonferroni=True,
        verdict=VERDICT_MICRO_LIVE_CANDIDATE,
        reason=(
            "all structural gates + bonferroni + worst-fold PF >= 1.0. "
            "Manual owner approval required before any live trading. "
            "Runtime stays BACKTEST_ONLY."
        ),
    )

"""
Phase 11 — Optional Bayesian extension (PR 5).

Reports posterior credible intervals for portfolio OOS profit factor
alongside the frequentist t-test p-value produced by ``phase11_gate``
and ``phase11_portfolio``. The Bayesian layer is informational only:
the acceptance gate (Amendment A) does NOT depend on it. Toggle-off
is supported via the CLI flag ``--no-bayesian``.

Why this is here
================

The frequentist Bonferroni gate gives a binary survives / does-not-survive
decision. With only 5 folds per combo, an interval estimate is more
honest than a point estimate of OOS PF: it tells the reviewer how wide
the uncertainty actually is. A combo with median PF 1.50 but 90 %
credible interval [0.7, 3.3] is a very different bet from a combo with
median PF 1.40 and 90 % interval [1.2, 1.7], even though their
Bonferroni p-values might both pass.

Model
=====

We model the fold-level OOS profit factor as a lognormal random
variable. This is the standard choice in the trading-systems literature:

  * PF is strictly positive and right-skewed.
  * log(PF) is approximately normal across independent fold windows.

The prior on log(PF) is a normal-inverse-chi-squared (Murphy 2007 §3.5),
which is the conjugate prior for an unknown mean + variance. We use
weakly-informative defaults (``mu0 = 0`` → prior median PF = 1.0,
``kappa0 = 1``, ``nu0 = 1``, ``sigma2_0 = 0.25``) so that with 5 folds
the data dominates the prior.

The posterior predictive for log(PF) is a Student-t. We draw quantiles
analytically from the Student-t — no sampling. This module remains
pure-Python (no scipy dependency in CI) and uses
``phase11_gate._student_t_sf`` to compute tail probabilities.

The fold-level posterior is then averaged across folds to give a
combo-level (portfolio-level) posterior. ``posterior_pf_p05``,
``posterior_pf_p50``, ``posterior_pf_p95``, and
``posterior_pf_prob_gt_1`` are emitted.

This module does NOT touch ``validation_gate``, ``risk_engine``,
``webhook_server``, or ``exchange_client``. It cannot toggle any
live-trading flag. Runtime stays ``BACKTEST_ONLY``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from .phase11_gate import _isfinite, _student_t_sf


# Weakly-informative Normal-Inverse-Chi-Squared prior on log(PF).
# Prior median PF = exp(MU0) = 1.0 — symmetric around break-even.
DEFAULT_MU0: float = 0.0
DEFAULT_KAPPA0: float = 1.0          # prior strength on the mean
DEFAULT_NU0: float = 1.0             # prior strength on the variance
DEFAULT_SIGMA2_0: float = 0.25       # prior variance of log(PF) ~ sd 0.5


@dataclass(frozen=True)
class PosteriorPF:
    """Posterior credible interval and survival probability for OOS PF."""
    p05: float          # 5th percentile of the predictive distribution
    p50: float          # median
    p95: float          # 95th percentile
    prob_gt_1: float    # posterior probability that PF > 1.0
    n_observations: int


# ---------------------------------------------------------------------------
# Student-t quantile (numerical inversion of the survival function)
# ---------------------------------------------------------------------------


def _student_t_quantile(p: float, df: float) -> float:
    """Quantile function of Student-t via numerical inversion.

    Returns t such that P(T <= t | df) = p. We use bisection over a
    wide bracket because the survival function ``_student_t_sf`` is
    monotonic. Accurate to ~1e-6.
    """
    if not _isfinite(p) or p <= 0.0:
        return -1e9
    if p >= 1.0:
        return 1e9
    # Bisection on F(t) = 1 - sf(t) = p  <=>  sf(t) = 1 - p
    target_sf = 1.0 - p
    lo, hi = -50.0, 50.0
    for _ in range(120):
        mid = 0.5 * (lo + hi)
        sf_mid = _student_t_sf(mid, df=int(round(df)) if df >= 1 else 1)
        if sf_mid > target_sf:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-9:
            break
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Posterior over log(PF) given fold observations
# ---------------------------------------------------------------------------


def _log_pf_observations(fold_pfs: Sequence[float]) -> list[float]:
    """Convert fold-level OOS PFs to log(PF) observations.

    Drops non-finite or non-positive values (e.g. PF = 0 when a fold
    had only losers, or PF = inf when a fold had no losers). We replace
    extreme finite values with clipped log-PF in [-3, 3] (matches PF
    in [0.05, 20]) so a single zero-loss fold doesn't dominate.
    """
    out: list[float] = []
    for pf in fold_pfs:
        try:
            x = float(pf)
        except (TypeError, ValueError):
            continue
        if not _isfinite(x) or x <= 0.0:
            continue
        lpf = math.log(x)
        if lpf < -3.0:
            lpf = -3.0
        elif lpf > 3.0:
            lpf = 3.0
        out.append(lpf)
    return out


def posterior_log_pf_params(
    fold_pfs: Sequence[float],
    mu0: float = DEFAULT_MU0,
    kappa0: float = DEFAULT_KAPPA0,
    nu0: float = DEFAULT_NU0,
    sigma2_0: float = DEFAULT_SIGMA2_0,
) -> tuple[float, float, float, int]:
    """Compute the posterior NIX parameters and effective df + scale.

    Returns ``(mu_n, scale, df, n_obs)`` such that the posterior
    predictive for log(PF) is ``mu_n + scale * T_df``.
    """
    obs = _log_pf_observations(fold_pfs)
    n = len(obs)
    if n == 0:
        # Prior only. Predictive: mu0 + sqrt(sigma2_0 * (1 + 1/kappa0)) * T_{nu0}
        scale = math.sqrt(sigma2_0 * (1.0 + 1.0 / max(kappa0, 1e-9)))
        return mu0, scale, nu0, 0

    x_bar = sum(obs) / n
    if n >= 2:
        s2 = sum((x - x_bar) ** 2 for x in obs) / (n - 1)
    else:
        s2 = 0.0

    kappa_n = kappa0 + n
    nu_n = nu0 + n
    mu_n = (kappa0 * mu0 + n * x_bar) / kappa_n
    sigma2_n = (
        nu0 * sigma2_0
        + (n - 1) * s2
        + (kappa0 * n / kappa_n) * (x_bar - mu0) ** 2
    ) / nu_n
    # Posterior predictive scale for one future log(PF).
    scale = math.sqrt(sigma2_n * (1.0 + 1.0 / kappa_n))
    return mu_n, scale, nu_n, n


def posterior_pf_interval(
    fold_pfs: Sequence[float],
    mu0: float = DEFAULT_MU0,
    kappa0: float = DEFAULT_KAPPA0,
    nu0: float = DEFAULT_NU0,
    sigma2_0: float = DEFAULT_SIGMA2_0,
) -> PosteriorPF:
    """5th/50th/95th percentile and P(PF > 1) under the posterior."""
    mu_n, scale, df, n_obs = posterior_log_pf_params(
        fold_pfs, mu0=mu0, kappa0=kappa0, nu0=nu0, sigma2_0=sigma2_0,
    )
    # Predictive: log(PF) ~ mu_n + scale * T_df
    t05 = _student_t_quantile(0.05, df)
    t50 = _student_t_quantile(0.50, df)   # 0 for any df
    t95 = _student_t_quantile(0.95, df)
    p05 = math.exp(mu_n + scale * t05)
    p50 = math.exp(mu_n + scale * t50)
    p95 = math.exp(mu_n + scale * t95)

    # P(PF > 1) = P(log PF > 0) = sf((0 - mu_n) / scale) under t_df
    if scale > 0.0 and _isfinite(scale):
        z = -mu_n / scale
        prob_gt_1 = _student_t_sf(z, df=int(round(df)) if df >= 1 else 1)
    else:
        prob_gt_1 = 1.0 if mu_n > 0.0 else 0.0

    return PosteriorPF(
        p05=float(p05),
        p50=float(p50),
        p95=float(p95),
        prob_gt_1=float(prob_gt_1),
        n_observations=n_obs,
    )


# ---------------------------------------------------------------------------
# Convenience: portfolio-level posterior from PortfolioFold objects
# ---------------------------------------------------------------------------


def posterior_for_portfolio(folds) -> PosteriorPF:
    """Extract fold OOS PFs from a PortfolioFold sequence and compute
    the posterior. Works with anything that has an ``.oos_pf`` attribute
    or dict key.
    """
    pfs: list[float] = []
    for f in folds:
        if isinstance(f, dict):
            pf = f.get("oos_pf")
        else:
            pf = getattr(f, "oos_pf", None)
        if pf is not None:
            try:
                pfs.append(float(pf))
            except (TypeError, ValueError):
                continue
    return posterior_pf_interval(pfs)

"""
Phase 11 — Bayesian extension tests (PR 5).

Covers:
  * Posterior interval ordering (p05 < p50 < p95)
  * Monotonicity: more positive PF observations → higher p50 + prob_gt_1
  * Prior-only behavior with zero observations
  * Degenerate inputs: empty, all-zero, all-infinity, mixed
  * Log-PF clipping at [-3, +3] so extreme folds don't dominate
  * Posterior columns appear in portfolio CSV when include_posterior=True
  * Posterior columns are blank when include_posterior=False
  * PortfolioVerdict.posterior_pf is None when toggle is off, populated when on
  * Locked column-order test still passes (regression guard for PR 4)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from src.phase11_bayesian import (
    DEFAULT_KAPPA0,
    DEFAULT_MU0,
    DEFAULT_NU0,
    DEFAULT_SIGMA2_0,
    PosteriorPF,
    _log_pf_observations,
    _student_t_quantile,
    posterior_for_portfolio,
    posterior_log_pf_params,
    posterior_pf_interval,
)
from src.phase11_portfolio import (
    PORTFOLIO_CSV_COLUMNS,
    PortfolioVerdict,
    build_portfolio_verdicts,
    write_portfolio_csv,
)
from src.phase11_search import SearchRow


# ---------------------------------------------------------------------------
# Helpers — small synthetic SearchRow fixtures (mirrors test_phase11_portfolio)
# ---------------------------------------------------------------------------


def _fold(*, gp: float, gl: float, sharpe: float, trades: int = 10,
          dd: float = 5.0, deg: float = 10.0, net: float | None = None) -> dict:
    if net is None:
        net = gp - gl
    return {
        "oos_sharpe": sharpe,
        "oos_pf": (gp / gl) if gl > 0 else 999.0,
        "oos_trades": trades,
        "oos_max_dd_pct": dd,
        "is_to_oos_sharpe_degradation_pct": deg,
        "oos_metrics": {
            "gross_profit": gp, "gross_loss": gl, "net_profit": net,
        },
    }


def _five_passing_folds(symbol_net: float = 100.0) -> list[dict]:
    return [
        _fold(gp=140.0, gl=100.0, sharpe=1.0, trades=10, net=symbol_net)
        for _ in range(5)
    ]


def _row(symbol: str, folds: list[dict]) -> SearchRow:
    return SearchRow(
        combo_key="V0|ema_fast=13,ema_slow=55",
        variant="V0",
        params={"ema_fast": 13, "ema_slow": 55},
        symbol=symbol,
        status="OK",
        n_folds=len(folds),
        summary={
            "median_oos_pf": 1.4,
            "worst_fold_oos_pf": 1.4,
            "median_oos_sharpe": 1.0,
            "max_oos_dd_pct": 5.0,
            "max_is_to_oos_sharpe_degradation_pct": 10.0,
            "total_oos_trades": sum(int(f.get("oos_trades", 0)) for f in folds),
            "min_fold_oos_trades": min(
                int(f.get("oos_trades", 0)) for f in folds
            ),
            "folds_with_oos_pf_gt_1": 5,
        },
        folds=folds,
        gate=None,
    )


# ---------------------------------------------------------------------------
# Student-t quantile sanity
# ---------------------------------------------------------------------------


def test_student_t_quantile_median_is_zero():
    for df in (1, 2, 5, 10, 30):
        q = _student_t_quantile(0.5, df)
        assert abs(q) < 1e-3, f"median for df={df} should be ~0, got {q}"


def test_student_t_quantile_symmetric_and_monotonic():
    # Quantile should be monotonically increasing in p.
    qs = [_student_t_quantile(p, 5) for p in (0.05, 0.25, 0.50, 0.75, 0.95)]
    for a, b in zip(qs, qs[1:]):
        assert a < b, f"quantile not monotonic: {qs}"
    # Roughly symmetric: q(0.05) ≈ -q(0.95)
    assert abs(qs[0] + qs[-1]) < 0.05


# ---------------------------------------------------------------------------
# _log_pf_observations: filtering + clipping
# ---------------------------------------------------------------------------


def test_log_pf_observations_drops_nonfinite_and_nonpositive():
    obs = _log_pf_observations([1.0, 0.0, -1.0, float("inf"), float("nan"), 2.0])
    # Keeps 1.0 -> 0.0 and 2.0 -> ln 2
    assert len(obs) == 2
    assert obs[0] == pytest.approx(0.0)
    assert obs[1] == pytest.approx(math.log(2.0))


def test_log_pf_observations_clips_extremes():
    # PF=100 -> log≈4.6 -> clipped to 3.0
    # PF=0.001 -> log≈-6.9 -> clipped to -3.0
    obs = _log_pf_observations([100.0, 0.001, 1.5])
    assert obs[0] == 3.0
    assert obs[1] == -3.0
    assert obs[2] == pytest.approx(math.log(1.5))


# ---------------------------------------------------------------------------
# Posterior math: ordering, monotonicity, prior-only
# ---------------------------------------------------------------------------


def test_posterior_interval_ordering():
    post = posterior_pf_interval([1.4] * 5)
    assert post.p05 < post.p50 < post.p95
    assert 0.0 <= post.prob_gt_1 <= 1.0
    assert post.n_observations == 5


def test_posterior_prior_only_centered_at_one():
    # No data -> predictive median exp(mu0) = 1.0
    post = posterior_pf_interval([])
    assert post.p50 == pytest.approx(1.0, abs=1e-6)
    assert post.prob_gt_1 == pytest.approx(0.5, abs=1e-2)
    assert post.n_observations == 0
    # Wide credible interval since prior is weak (sigma2_0 = 0.25)
    assert post.p05 < 0.5
    assert post.p95 > 2.0


def test_posterior_monotonic_in_observations():
    # More positive PF data -> higher p50 and higher prob_gt_1.
    losing = posterior_pf_interval([0.5, 0.6, 0.55, 0.7, 0.45])
    flat = posterior_pf_interval([1.0, 1.05, 0.95, 1.0, 1.02])
    winning = posterior_pf_interval([1.4, 1.5, 1.3, 1.6, 1.4])
    great = posterior_pf_interval([2.0, 2.2, 1.9, 2.1, 2.3])

    assert losing.p50 < flat.p50 < winning.p50 < great.p50
    assert losing.prob_gt_1 < flat.prob_gt_1 < winning.prob_gt_1 < great.prob_gt_1
    # Losing series should give prob_gt_1 < 0.25, winning > 0.75
    assert losing.prob_gt_1 < 0.25
    assert winning.prob_gt_1 > 0.75


def test_posterior_winning_series_specific_range():
    # Sanity-tested values from the design phase.
    post = posterior_pf_interval([1.4, 1.4, 1.4, 1.4, 1.4])
    assert 1.2 < post.p50 < 1.45
    assert post.prob_gt_1 > 0.75


def test_posterior_losing_series_specific_range():
    post = posterior_pf_interval([0.5, 0.5, 0.5, 0.5, 0.5])
    assert 0.45 < post.p50 < 0.75
    assert post.prob_gt_1 < 0.25


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------


def test_posterior_all_zero_falls_back_to_prior():
    # PF=0 means "fold had no winners". Dropped, so prior-only.
    post = posterior_pf_interval([0.0, 0.0, 0.0])
    assert post.n_observations == 0
    assert post.p50 == pytest.approx(1.0, abs=1e-6)


def test_posterior_all_infinity_falls_back_to_prior():
    # PF=inf means "fold had no losers". Dropped, so prior-only.
    post = posterior_pf_interval([float("inf"), float("inf")])
    assert post.n_observations == 0
    assert post.p50 == pytest.approx(1.0, abs=1e-6)


def test_posterior_single_observation_works():
    post = posterior_pf_interval([1.5])
    assert post.n_observations == 1
    assert post.p05 < post.p50 < post.p95
    # Single obs blends with prior centered at 1 -> p50 between 1 and 1.5
    assert 1.0 < post.p50 < 1.5


# ---------------------------------------------------------------------------
# posterior_log_pf_params details
# ---------------------------------------------------------------------------


def test_posterior_params_match_prior_when_empty():
    mu, scale, df, n = posterior_log_pf_params([])
    assert mu == DEFAULT_MU0
    assert df == DEFAULT_NU0
    assert n == 0
    assert scale > 0


def test_posterior_params_mu_shifts_toward_data():
    # All observations at log(2) -> posterior mean should be between
    # prior mu0 (=0) and the data mean (=log 2 ≈ 0.693).
    mu, _scale, _df, n = posterior_log_pf_params([2.0] * 5)
    assert n == 5
    assert 0.0 < mu < math.log(2.0)


# ---------------------------------------------------------------------------
# posterior_for_portfolio: works with dicts AND objects
# ---------------------------------------------------------------------------


def test_posterior_for_portfolio_extracts_from_dicts():
    folds = [{"oos_pf": 1.4}, {"oos_pf": 1.3}, {"oos_pf": 1.5}]
    post = posterior_for_portfolio(folds)
    assert post.n_observations == 3
    assert post.p50 > 1.0


def test_posterior_for_portfolio_extracts_from_objects():
    class _F:
        def __init__(self, pf): self.oos_pf = pf
    folds = [_F(1.4), _F(1.3), _F(1.5)]
    post = posterior_for_portfolio(folds)
    assert post.n_observations == 3
    assert post.p50 > 1.0


def test_posterior_for_portfolio_empty_returns_prior():
    post = posterior_for_portfolio([])
    assert post.n_observations == 0
    assert post.p50 == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Wiring into PortfolioVerdict + CSV
# ---------------------------------------------------------------------------


def _three_pair_rows() -> list[SearchRow]:
    return [
        _row("EURUSD", _five_passing_folds()),
        _row("GBPUSD", _five_passing_folds()),
        _row("XAUUSD", _five_passing_folds()),
    ]


def test_build_verdicts_populates_posterior_when_toggle_on():
    verdicts = build_portfolio_verdicts(
        _three_pair_rows(), n_tested=123, include_posterior=True,
    )
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.posterior_pf is not None
    assert isinstance(v.posterior_pf, PosteriorPF)
    assert v.posterior_pf.p05 < v.posterior_pf.p50 < v.posterior_pf.p95


def test_build_verdicts_omits_posterior_when_toggle_off():
    verdicts = build_portfolio_verdicts(
        _three_pair_rows(), n_tested=123, include_posterior=False,
    )
    assert len(verdicts) == 1
    assert verdicts[0].posterior_pf is None


def test_portfolio_csv_has_posterior_columns_when_enabled(tmp_path: Path):
    verdicts = build_portfolio_verdicts(
        _three_pair_rows(), n_tested=123, include_posterior=True,
    )
    p = tmp_path / "portfolio.csv"
    write_portfolio_csv(verdicts, p)
    with p.open() as fh:
        reader = csv.DictReader(fh)
        row = next(reader)
    # All four posterior cells populated.
    for col in ("posterior_pf_p05", "posterior_pf_p50",
                "posterior_pf_p95", "posterior_pf_prob_gt_1"):
        assert row[col] != "", f"{col} should not be empty"
        # Should parse as float.
        float(row[col])


def test_portfolio_csv_posterior_blank_when_disabled(tmp_path: Path):
    verdicts = build_portfolio_verdicts(
        _three_pair_rows(), n_tested=123, include_posterior=False,
    )
    p = tmp_path / "portfolio.csv"
    write_portfolio_csv(verdicts, p)
    with p.open() as fh:
        reader = csv.DictReader(fh)
        row = next(reader)
    for col in ("posterior_pf_p05", "posterior_pf_p50",
                "posterior_pf_p95", "posterior_pf_prob_gt_1"):
        assert row[col] == "", f"{col} should be blank when toggle off"


def test_portfolio_csv_columns_ends_with_posterior_block():
    # Append-only contract: PR 5 posterior columns are the last 4.
    assert PORTFOLIO_CSV_COLUMNS[-4:] == (
        "posterior_pf_p05",
        "posterior_pf_p50",
        "posterior_pf_p95",
        "posterior_pf_prob_gt_1",
    )
    # Total locked count after PR 5.
    assert len(PORTFOLIO_CSV_COLUMNS) == 29

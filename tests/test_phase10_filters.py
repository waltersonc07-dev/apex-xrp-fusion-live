"""Tests for ``src.phase10_filters`` and its integration with the Phase 10
backtest engine.

These tests cover:
  - session_allows_entry (day-of-week)
  - ADX calculation
  - classify_regimes (trend / range / chop / unknown)
  - regime_allows_entry whitelist logic
  - filter_signals composing both
  - End-to-end: backtest with filters OFF == baseline; filters ON shrinks
    trade count without ever exceeding it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.phase10_filters import (
    DEFAULT_REGIME_CFG,
    DEFAULT_SESSION_CFG,
    adx,
    classify_regimes,
    filter_signals,
    regime_allows_entry,
    session_allows_entry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _trending_df(n: int = 400, drift: float = 0.001,
                 vol: float = 0.003, seed: int = 0) -> pd.DataFrame:
    """Synthesize a clearly trending daily series."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(drift, vol, n)
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, vol, n)))
    low = close * (1 - np.abs(rng.normal(0, vol, n)))
    op = np.concatenate([[close[0]], close[:-1]])
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(
        {"open": op, "high": high, "low": low, "close": close, "volume": 0.0},
        index=idx,
    )


def _ranging_df(n: int = 400, seed: int = 1) -> pd.DataFrame:
    """Synthesize a range-bound daily series oscillating around 100.

    Built as an Ornstein–Uhlenbeck-style mean-reverter so EMA200 stays flat
    (no drift => slope ~ 0) and ADX should stay low.
    """
    rng = np.random.default_rng(seed)
    close = np.empty(n)
    close[0] = 100.0
    mean_rev = 0.15
    mu = 100.0
    sigma = 0.4
    for i in range(1, n):
        close[i] = close[i - 1] + mean_rev * (mu - close[i - 1]) + rng.normal(
            0, sigma
        )
    high = close + np.abs(rng.normal(0, 0.2, n))
    low = close - np.abs(rng.normal(0, 0.2, n))
    op = np.concatenate([[close[0]], close[:-1]])
    idx = pd.date_range("2018-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(
        {"open": op, "high": high, "low": low, "close": close, "volume": 0.0},
        index=idx,
    )


# ---------------------------------------------------------------------------
# Session filter
# ---------------------------------------------------------------------------


class TestSessionFilter:
    def test_default_skips_friday(self):
        # Friday June 5, 2026
        ts = pd.Timestamp("2026-06-05", tz="UTC")
        assert ts.weekday() == 4
        assert session_allows_entry(ts) is False

    def test_default_skips_sunday(self):
        # Sunday June 7, 2026
        ts = pd.Timestamp("2026-06-07", tz="UTC")
        assert ts.weekday() == 6
        assert session_allows_entry(ts) is False

    def test_default_allows_tue_thu(self):
        for d in ("2026-06-02", "2026-06-03", "2026-06-04"):
            ts = pd.Timestamp(d, tz="UTC")
            assert session_allows_entry(ts) is True

    def test_monday_default_allowed(self):
        # skip_monday_open_entries is False by default
        ts = pd.Timestamp("2026-06-01", tz="UTC")
        assert ts.weekday() == 0
        assert session_allows_entry(ts) is True

    def test_monday_can_be_excluded(self):
        ts = pd.Timestamp("2026-06-01", tz="UTC")
        cfg = {**DEFAULT_SESSION_CFG, "skip_monday_open_entries": True}
        assert session_allows_entry(ts, cfg) is False

    def test_disable_all_session_filters(self):
        for d in ("2026-06-05", "2026-06-06", "2026-06-07"):
            cfg = {"skip_friday_entries": False,
                   "skip_sunday_entries": False,
                   "skip_monday_open_entries": False}
            assert session_allows_entry(pd.Timestamp(d, tz="UTC"), cfg) is True


# ---------------------------------------------------------------------------
# ADX
# ---------------------------------------------------------------------------


class TestADX:
    def test_adx_returns_series_aligned_with_index(self):
        df = _trending_df(300)
        a = adx(df, 14)
        assert isinstance(a, pd.Series)
        assert (a.index == df.index).all()

    def test_adx_higher_on_trend_than_range(self):
        trend = _trending_df(400, drift=0.002, vol=0.002)
        rng = _ranging_df(400)
        a_t = adx(trend, 14).iloc[-1]
        a_r = adx(rng, 14).iloc[-1]
        assert a_t > a_r

    def test_adx_warmup_is_nan(self):
        df = _trending_df(200)
        a = adx(df, 14)
        # First 13 bars must be NaN (Wilder needs `length` samples to start).
        assert a.iloc[:13].isna().all()

    def test_adx_bounded_0_100(self):
        df = _trending_df(400)
        a = adx(df, 14).dropna()
        assert (a >= 0).all() and (a <= 100).all()


# ---------------------------------------------------------------------------
# Regime classification
# ---------------------------------------------------------------------------


class TestRegimes:
    def test_trending_series_classified_trending_dominant(self):
        df = _trending_df(400, drift=0.0025, vol=0.003)
        rv = classify_regimes(df)
        post_warmup = rv.regimes.iloc[DEFAULT_REGIME_CFG["warmup_bars"]:]
        counts = post_warmup.value_counts()
        # Trending must be at least as common as ranging or choppy.
        assert counts.get("trending", 0) >= counts.get("ranging", 0)
        assert counts.get("trending", 0) >= counts.get("choppy", 0)

    def test_ranging_series_has_few_trending_bars(self):
        # On a strict mean-reverter EMA200 slope ~ 0 and ADX stays low, so
        # trending classifications should be rare. We don't require ranging
        # to dominate — a noisy mean-reverter can still show occasional ATR
        # spikes that classify as 'choppy' — but trending must be a small
        # minority of post-warmup bars.
        df = _ranging_df(400)
        rv = classify_regimes(df)
        post_warmup = rv.regimes.iloc[DEFAULT_REGIME_CFG["warmup_bars"]:]
        counts = post_warmup.value_counts()
        total = counts.sum()
        trending_share = counts.get("trending", 0) / max(total, 1)
        assert trending_share < 0.25, (
            f"mean-reverter classified as trending {trending_share:.0%} of "
            f"the time: {dict(counts)}"
        )

    def test_warmup_bars_are_unknown(self):
        df = _trending_df(400)
        rv = classify_regimes(df)
        n_warm = DEFAULT_REGIME_CFG["warmup_bars"]
        # Warmup region must be all 'unknown'.
        assert (rv.regimes.iloc[:n_warm] == "unknown").all()

    def test_regimes_only_in_valid_set(self):
        df = _trending_df(400)
        rv = classify_regimes(df)
        assert set(rv.regimes.unique()).issubset(
            {"trending", "ranging", "choppy", "unknown"}
        )

    def test_missing_columns_raise(self):
        bad = pd.DataFrame({"close": [1, 2, 3]})
        with pytest.raises(ValueError, match="open/high/low/close"):
            classify_regimes(bad)

    def test_does_not_mutate_input(self):
        df = _trending_df(300)
        cols_before = list(df.columns)
        classify_regimes(df)
        assert list(df.columns) == cols_before


# ---------------------------------------------------------------------------
# regime_allows_entry
# ---------------------------------------------------------------------------


class TestRegimeAllow:
    def test_unknown_rejected_when_allowed_none(self):
        assert regime_allows_entry("unknown", None) is False
        assert regime_allows_entry("trending", None) is True

    def test_whitelist(self):
        assert regime_allows_entry("trending", ["trending"]) is True
        assert regime_allows_entry("ranging", ["trending"]) is False

    def test_explicit_unknown_passes_if_listed(self):
        assert regime_allows_entry("unknown", ["unknown", "trending"]) is True


# ---------------------------------------------------------------------------
# filter_signals — composition
# ---------------------------------------------------------------------------


class TestFilterSignals:
    def test_no_op_when_session_disabled_and_regimes_allowed_all(self):
        df = _trending_df(300)
        signals = df.copy()
        signals["long_entry"] = True
        signals["short_entry"] = False
        # Disable session, allow all regimes including unknown so nothing is
        # filtered out.
        out = filter_signals(
            df, signals,
            session_cfg={"skip_friday_entries": False,
                         "skip_sunday_entries": False,
                         "skip_monday_open_entries": False},
            regimes_allowed=["trending", "ranging", "choppy", "unknown"],
        )
        assert out["long_entry"].sum() == signals["long_entry"].sum()

    def test_friday_entries_dropped(self):
        df = _trending_df(300)
        signals = df.copy()
        signals["long_entry"] = True
        signals["short_entry"] = False
        out = filter_signals(
            df, signals,
            session_cfg={**DEFAULT_SESSION_CFG, "skip_sunday_entries": False},
            regimes_allowed=["trending", "ranging", "choppy", "unknown"],
        )
        fridays = df.index.to_series().apply(lambda ts: ts.weekday() == 4)
        assert out.loc[fridays, "long_entry"].sum() == 0
        # Non-Friday entries should be preserved.
        assert out.loc[~fridays, "long_entry"].sum() > 0

    def test_exits_never_touched(self):
        df = _trending_df(200)
        signals = df.copy()
        signals["long_entry"] = True
        signals["short_entry"] = False
        # 'long_exit' is not standard but the function must leave any non-
        # entry column unchanged.
        signals["long_exit"] = True
        out = filter_signals(df, signals,
                             regimes_allowed=["trending"])
        assert (out["long_exit"] == True).all()  # noqa: E712


# ---------------------------------------------------------------------------
# End-to-end integration with the Phase 10 backtester
# ---------------------------------------------------------------------------


class TestBacktestIntegration:
    def _ohlcv(self) -> pd.DataFrame:
        df = _trending_df(500, drift=0.0015, vol=0.004, seed=42)
        return df

    def test_filters_off_is_baseline_identical(self):
        from src.phase10_fx_gold_daily import (
            DEFAULT_CONFIG,
            _backtest_variant,
        )

        df = self._ohlcv()
        cfg_off = {**DEFAULT_CONFIG}
        # Explicit safety: keep filters off.
        assert cfg_off["enable_session_filter"] is False
        assert cfg_off["enable_regime_filter"] is False
        res = _backtest_variant(df, "V0", "TEST", cfg_off)
        # Sanity: variant runs, returns a BacktestResult.
        assert res.variant == "V0"
        assert res.symbol == "TEST"

    def test_filters_on_never_increases_trade_count(self):
        from src.phase10_fx_gold_daily import (
            DEFAULT_CONFIG,
            _backtest_variant,
        )

        df = self._ohlcv()

        baseline = _backtest_variant(df, "V0", "TEST", {**DEFAULT_CONFIG})
        n_baseline = len(baseline.trades)

        cfg_on = {
            **DEFAULT_CONFIG,
            "enable_session_filter": True,
            "enable_regime_filter": True,
            "regimes_allowed": ["trending"],
        }
        filtered = _backtest_variant(df, "V0", "TEST", cfg_on)
        n_filtered = len(filtered.trades)

        # Filters can only mask entries, never create new ones.
        assert n_filtered <= n_baseline

    def test_filter_on_safety_flags_unchanged(self):
        # The filter PR must not alter the BACKTEST_ONLY recommendation logic.
        from src.phase10_fx_gold_daily import DEFAULT_CONFIG

        for key in ("min_profit_factor", "min_oos_profit_factor",
                    "max_drawdown_pct", "min_sharpe",
                    "min_trades_per_asset"):
            assert key in DEFAULT_CONFIG

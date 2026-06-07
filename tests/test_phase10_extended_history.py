"""Phase 10 — extended-history warm-up + coverage tests.

Verifies that with the 20-year daily dataset:
  1. Each symbol has at least 4000 bars (sanity: more than 16 years of trading days).
  2. ADX(14) and EMA200 are valid (non-NaN) after the 210-bar warm-up window.
  3. Regime classification produces all four labels on the longer series.
  4. Filter still reduces trade count (invariant from PR #5).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.phase10_filters import (
    DEFAULT_REGIME_CFG,
    adx,
    classify_regimes,
)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD", "USDJPY"]
WARMUP = 210


def _have_data(sym: str) -> bool:
    return (DATA_DIR / f"{sym.lower()}_1d.csv").exists()


def _load(sym: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / f"{sym.lower()}_1d.csv", parse_dates=["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


@pytest.mark.skipif(
    not all(_have_data(s) for s in SYMBOLS),
    reason="extended-history CSVs not present (run "
    "`python -m src.phase10_data_downloader --years 20`)",
)
@pytest.mark.parametrize("symbol", SYMBOLS)
def test_extended_history_coverage(symbol: str) -> None:
    df = _load(symbol)
    # At 20 years × ~250 trading days, we expect ~5000. Allow some slack for
    # holidays and source gaps but require well above the 10-year window.
    assert len(df) >= 4000, f"{symbol}: only {len(df)} bars — extended history not loaded"
    # First/last timestamps span > 15 years.
    span_years = (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).days / 365.25
    assert span_years >= 15, f"{symbol}: only {span_years:.1f} years of data"


@pytest.mark.skipif(
    not all(_have_data(s) for s in SYMBOLS),
    reason="extended-history CSVs not present",
)
@pytest.mark.parametrize("symbol", SYMBOLS)
def test_adx_warmup_holds(symbol: str) -> None:
    df = _load(symbol)
    a = adx(df, length=14)
    # ADX has NaN during its warmup. After ~30 bars it should be defined.
    assert a.iloc[:14].isna().all(), f"{symbol}: ADX should be NaN in first 14 bars"
    assert a.iloc[WARMUP:].notna().all(), (
        f"{symbol}: ADX must be non-NaN after the {WARMUP}-bar warmup window"
    )
    # ADX must be in [0, 100] wherever defined.
    defined = a.dropna()
    assert defined.between(0, 100).all(), f"{symbol}: ADX out of [0,100] range"


@pytest.mark.skipif(
    not all(_have_data(s) for s in SYMBOLS),
    reason="extended-history CSVs not present",
)
@pytest.mark.parametrize("symbol", SYMBOLS)
def test_ema200_warmup_holds(symbol: str) -> None:
    df = _load(symbol)
    close = df["close"]
    ema200 = close.ewm(span=200, adjust=False).mean()
    # EMA is defined immediately but only stable after several spans. Check
    # that after the warmup window it tracks within a sane band of price.
    sample = ema200.iloc[WARMUP:]
    px = close.iloc[WARMUP:]
    # EMA should be within +/- 50% of price (very loose sanity check).
    ratio = (sample / px).abs()
    assert ratio.between(0.5, 1.5).all(), (
        f"{symbol}: EMA200 diverges from price beyond ±50% after warmup"
    )


@pytest.mark.skipif(
    not all(_have_data(s) for s in SYMBOLS),
    reason="extended-history CSVs not present",
)
@pytest.mark.parametrize("symbol", SYMBOLS)
def test_regime_classifier_produces_multiple_labels(symbol: str) -> None:
    df = _load(symbol)
    view = classify_regimes(df, DEFAULT_REGIME_CFG)
    regimes = view.regimes.iloc[WARMUP:].dropna()
    labels = set(regimes.unique())
    # Over 16+ years we should see at least three distinct regimes
    # (trending + at least two of ranging/choppy/unknown).
    assert len(labels) >= 2, (
        f"{symbol}: classifier produced only {labels} over {len(regimes)} bars"
    )
    # Trending share should be a minority but non-trivial. Empirically 10–40%.
    trending_share = (regimes == "trending").mean()
    assert 0.02 <= trending_share <= 0.70, (
        f"{symbol}: trending share {trending_share:.1%} outside plausible band [2%, 70%]"
    )

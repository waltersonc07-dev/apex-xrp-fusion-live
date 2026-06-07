"""
Phase 11 splitter invariants (PR 1).

Tests cover the four invariants from Amendment A § A.5 implementation rules
plus the warmup contract from Section 2.1 of the design doc:

  1. No leakage: ``fold.oos_start == fold.is_end`` for every fold.
  2. Monotone OOS windows: ``fold[k].oos_end <= fold[k+1].oos_end``.
  3. Expanding IS: ``fold[k].is_end <= fold[k+1].is_end``.
  4. Warmup respected: ``fold[k].is_start >= warmup_bars``.
  5. OOS slices disjoint and cover the post-warmup tail.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.phase11_orchestrator import (
    DEFAULT_N_FOLDS,
    DEFAULT_WARMUP_BARS,
    Fold,
    Phase11Splitter,
)


def _df(n: int) -> pd.DataFrame:
    # The splitter only inspects len(df); column values don't matter here.
    return pd.DataFrame({"close": range(n)})


def test_splitter_produces_n_folds_for_realistic_size() -> None:
    splitter = Phase11Splitter()
    folds = splitter.split(_df(5000))
    assert len(folds) == DEFAULT_N_FOLDS


def test_splitter_no_leakage_per_fold() -> None:
    splitter = Phase11Splitter()
    folds = splitter.split(_df(5000))
    for f in folds:
        # No gap, no overlap: OOS starts exactly where IS ends.
        assert f.oos_start == f.is_end, f"leakage in fold {f.index}"


def test_splitter_monotone_oos_end() -> None:
    splitter = Phase11Splitter()
    folds = splitter.split(_df(5000))
    for prev, nxt in zip(folds, folds[1:]):
        assert nxt.oos_end >= prev.oos_end


def test_splitter_expanding_is() -> None:
    splitter = Phase11Splitter()
    folds = splitter.split(_df(5000))
    # is_start stays fixed (expanding window starts at warmup); is_end grows.
    for f in folds:
        assert f.is_start == DEFAULT_WARMUP_BARS
    for prev, nxt in zip(folds, folds[1:]):
        assert nxt.is_end >= prev.is_end


def test_splitter_respects_warmup() -> None:
    splitter = Phase11Splitter()
    folds = splitter.split(_df(5000))
    for f in folds:
        assert f.is_start >= DEFAULT_WARMUP_BARS


def test_splitter_oos_slices_disjoint() -> None:
    splitter = Phase11Splitter()
    folds = splitter.split(_df(5000))
    seen = set()
    for f in folds:
        rng = range(f.oos_start, f.oos_end)
        for idx in rng:
            assert idx not in seen, f"overlap at idx {idx}"
            seen.add(idx)


def test_splitter_oos_covers_post_warmup_tail_when_aligned() -> None:
    # Last fold absorbs the remainder, so the union of OOS slices ends at n.
    splitter = Phase11Splitter()
    n = 5000
    folds = splitter.split(_df(n))
    assert folds[-1].oos_end == n


def test_splitter_rejects_too_few_bars() -> None:
    splitter = Phase11Splitter(min_bars=1000)
    with pytest.raises(ValueError, match="at least 1000 bars"):
        splitter.split(_df(500))


def test_splitter_rejects_invalid_n_folds() -> None:
    with pytest.raises(ValueError, match="n_folds must be >= 2"):
        Phase11Splitter(n_folds=1)


def test_splitter_rejects_negative_warmup() -> None:
    with pytest.raises(ValueError, match="warmup_bars must be >= 0"):
        Phase11Splitter(warmup_bars=-1)


def test_splitter_rejects_warmup_consuming_history() -> None:
    splitter = Phase11Splitter(warmup_bars=2000, min_bars=1000)
    # 1500 bars after warmup leaves only -500 usable → ValueError surface
    # is the chunk-collapse or warmup-consumes check; either is acceptable.
    with pytest.raises(ValueError):
        splitter.split(_df(1500))


def test_fold_validates_leakage_in_post_init() -> None:
    with pytest.raises(ValueError, match="leakage"):
        Fold(index=1, is_start=0, is_end=100, oos_start=99, oos_end=200)


def test_fold_validates_empty_windows() -> None:
    with pytest.raises(ValueError, match="empty IS window"):
        Fold(index=1, is_start=100, is_end=100, oos_start=100, oos_end=200)
    with pytest.raises(ValueError, match="empty OOS window"):
        Fold(index=1, is_start=0, is_end=100, oos_start=100, oos_end=100)


def test_splitter_three_folds_smaller_history() -> None:
    # Custom fold count + small min_bars should still produce a valid split.
    splitter = Phase11Splitter(n_folds=3, warmup_bars=50, min_bars=500)
    folds = splitter.split(_df(800))
    assert len(folds) == 3
    for f in folds:
        assert f.is_start == 50
        assert f.oos_start == f.is_end
    assert folds[-1].oos_end == 800

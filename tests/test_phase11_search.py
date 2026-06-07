"""
Phase 11 — Grid search engine tests (PR 2).

Covers:
  * run_grid_search returns one row per (combo × symbol)
  * variant_filter restricts to the requested variants
  * INSUFFICIENT_DATA rows are surfaced when a symbol has too few bars
  * CSV writer emits the locked column order and one row per result
  * render_summary_markdown contains the required sections and the
    BACKTEST_ONLY notice (defense-in-depth on what we print)
  * Source-scan safety invariants still hold for the new modules
    (covered by the parametric test in test_phase11_safety_invariants.py)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest
import yaml

from src.phase11_grid import GridCombo, GridSpec, load_grid
from src.phase11_search import (
    CSV_COLUMNS,
    render_summary_markdown,
    run_grid_search,
    write_csv,
)
from src.phase11_orchestrator import Phase11Splitter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ohlcv(n: int, start: float = 1.10) -> pd.DataFrame:
    idx = pd.date_range("2010-01-01", periods=n, freq="D", tz="UTC")
    closes = [start + 0.0005 * i for i in range(n)]
    highs = [c * 1.002 for c in closes]
    lows = [c * 0.998 for c in closes]
    opens = [c * 0.999 for c in closes]
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": 0.0},
        index=idx,
    )


def _tiny_grid() -> GridSpec:
    """A 3-combo grid for fast tests: 1 V0, 1 V2, 1 V3."""
    return GridSpec(
        version=1, hard_cap=140,
        combos=(
            GridCombo(variant="V0", params={
                "ema_fast": 13, "ema_slow": 55,
                "rsi_length": 14, "atr_stop_mult": 2.0,
            }),
            GridCombo(variant="V2", params={
                "donchian_in": 20, "donchian_out": 10, "atr_stop_mult": 2.0,
            }),
            GridCombo(variant="V3", params={
                "bb_length": 20, "bb_std": 2.0, "atr_stop_mult": 2.0,
            }),
        ),
        per_variant_counts={"V0": 1, "V1": 0, "V2": 1, "V3": 1},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_grid_search_returns_one_row_per_combo_per_symbol() -> None:
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000), "GBPUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)
    assert len(rows) == len(grid.combos) * len(data)


def test_variant_filter_restricts_results() -> None:
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid, variant_filter=["V0"])
    assert all(r.variant == "V0" for r in rows)
    assert len(rows) == 1   # only the V0 combo × 1 symbol


def test_insufficient_data_path_surfaces_as_row_status() -> None:
    grid = _tiny_grid()
    data = {"SHORT": _ohlcv(500), "EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)
    short_rows = [r for r in rows if r.symbol == "SHORT"]
    long_rows = [r for r in rows if r.symbol == "EURUSD"]
    assert all(r.status == "INSUFFICIENT_DATA" for r in short_rows)
    assert all(r.status == "OK" for r in long_rows)


def test_csv_writer_emits_locked_column_order(tmp_path: Path) -> None:
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)
    csv_path = tmp_path / "out.csv"
    write_csv(rows, csv_path)
    with csv_path.open() as fh:
        reader = csv.reader(fh)
        header = next(reader)
        body = list(reader)
    assert header == list(CSV_COLUMNS)
    assert len(body) == len(rows)


def test_csv_writer_round_trips_params_json(tmp_path: Path) -> None:
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)
    csv_path = tmp_path / "out.csv"
    write_csv(rows, csv_path)
    with csv_path.open() as fh:
        first = next(csv.DictReader(fh))
    # params_json column must be valid JSON and round-trip to a dict.
    import json
    parsed = json.loads(first["params_json"])
    assert isinstance(parsed, dict)


def test_render_summary_contains_required_sections() -> None:
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)
    md = render_summary_markdown(rows, grid)
    assert "# Phase 11 — Grid Search Summary (PR 2)" in md
    assert "BACKTEST_ONLY" in md
    assert "Top 10 by median OOS PF" in md


def test_render_summary_with_no_ok_rows_does_not_crash() -> None:
    grid = _tiny_grid()
    data = {"SHORT": _ohlcv(500)}
    rows = run_grid_search(data, grid)
    md = render_summary_markdown(rows, grid)
    # Either the "no OK rows" notice or the skip summary should appear; both
    # are acceptable, but we must never crash and we must keep the header.
    assert "Phase 11 — Grid Search Summary" in md
    assert "INSUFFICIENT_DATA" in md


def test_grid_search_runs_against_frozen_grid_subset() -> None:
    """Use the actual frozen grid but filter to V2 (smallest) for speed."""
    grid = load_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(
        data, grid, variant_filter=["V2"],
        splitter=Phase11Splitter(n_folds=3, warmup_bars=210, min_bars=500),
    )
    # V2 has 24 combos in the frozen grid × 1 symbol.
    assert len(rows) == 24
    assert all(r.variant == "V2" for r in rows)


def test_csv_columns_constant_is_locked() -> None:
    """If this test fails, someone reordered or renamed the CSV columns.

    PR 3 may APPEND columns (raw_p, bonferroni_p, n_tested, survives_raw,
    survives_bonferroni, verdict) but must NEVER reorder or rename existing
    ones — downstream reports and the gate rely on this contract.
    """
    expected_prefix = (
        "combo_key", "variant", "params_json", "symbol", "status",
        "n_folds", "median_oos_pf", "worst_fold_oos_pf",
        "median_oos_sharpe", "max_oos_dd_pct",
        "max_is_to_oos_sharpe_degradation_pct",
        "total_oos_trades", "min_fold_oos_trades",
    )
    assert CSV_COLUMNS[:len(expected_prefix)] == expected_prefix

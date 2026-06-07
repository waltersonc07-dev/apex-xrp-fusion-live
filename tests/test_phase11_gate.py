"""
Phase 11 — Acceptance gate tests (PR 3).

Covers:
  * One-sided t-test p-value math vs known critical values
  * Bonferroni adjustment with clamping
  * Verdict label decision tree:
      BLOCKED (INSUFFICIENT_DATA)
      BLOCKED (per-fold trade floor)
      BLOCKED (total-trade floor)
      BLOCKED (median OOS PF floor)
      BLOCKED (median OOS Sharpe floor)
      BLOCKED (fewer than 3 folds with OOS PF > 1)
      BLOCKED (IS->OOS degradation cap)
      WATCH (structural gates pass but Bonferroni fails)
      VALIDATED_RESEARCH_CANDIDATE (Bonferroni passes; worst-fold < 1.0)
      MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW (all gates + worst-fold >= 1.0)
  * Wiring: attach_gate_results uses GridSpec.total as n_tested
  * CSV emits the appended PR 3 columns with the correct values
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from src.phase11_gate import (
    ALL_VERDICTS,
    MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT,
    MIN_MEDIAN_OOS_PF,
    MIN_TOTAL_OOS_TRADES,
    SIGNIFICANCE_ALPHA,
    VERDICT_BLOCKED,
    VERDICT_MICRO_LIVE_CANDIDATE,
    VERDICT_VALIDATED_RESEARCH_CANDIDATE,
    VERDICT_WATCH,
    _student_t_sf,
    bonferroni_adjust,
    evaluate_gate,
    one_sided_t_pvalue,
)
from src.phase11_grid import GridCombo, GridSpec
from src.phase11_search import (
    CSV_COLUMNS,
    SearchRow,
    attach_gate_results,
    run_grid_search,
    write_csv,
)


# ---------------------------------------------------------------------------
# p-value math
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "t,df,expected",
    [
        (2.776, 4, 0.025),   # df=4 two-sided 0.05 critical value
        (0.0, 4, 0.5),
        (1.533, 4, 0.10),    # df=4 one-sided 0.10
        (-1.0, 4, 0.8130),
    ],
)
def test_student_t_sf_matches_known_critical_values(t, df, expected):
    got = _student_t_sf(t, df)
    assert abs(got - expected) < 5e-4, (t, df, got, expected)


def test_one_sided_t_pvalue_strong_positive_sharpes_significant():
    # Tight positive cluster -> tiny p
    p = one_sided_t_pvalue([1.0, 1.1, 0.9, 1.2, 1.0])
    assert p < 0.001


def test_one_sided_t_pvalue_negative_sharpes_nonsignificant():
    p = one_sided_t_pvalue([-0.1, -0.2, 0.0, -0.1, 0.1])
    assert p > 0.5


def test_one_sided_t_pvalue_degenerate_inputs_return_one():
    assert one_sided_t_pvalue([]) == 1.0
    assert one_sided_t_pvalue([0.5]) == 1.0
    # Constant non-positive series with zero variance -> 1.0
    assert one_sided_t_pvalue([0.0, 0.0, 0.0]) == 1.0


def test_bonferroni_adjust_clamps_to_one():
    assert bonferroni_adjust(0.01, 123) == pytest.approx(1.0)  # 1.23 -> 1.0
    assert bonferroni_adjust(0.001, 123) == pytest.approx(0.123)
    # n_tested <= 0 is a no-op
    assert bonferroni_adjust(0.05, 0) == 0.05


# ---------------------------------------------------------------------------
# Helpers for verdict tests
# ---------------------------------------------------------------------------


def _passing_summary(**overrides) -> dict:
    """Summary that passes every structural gate by default."""
    base = {
        "median_oos_pf": 1.50,
        "worst_fold_oos_pf": 1.10,
        "median_oos_sharpe": 0.90,
        "max_oos_dd_pct": 12.0,
        "max_is_to_oos_sharpe_degradation_pct": 15.0,
        "total_oos_trades": 80,
        "min_fold_oos_trades": 10,
    }
    base.update(overrides)
    return base


def _passing_folds(oos_sharpe: float = 1.0, oos_pf: float = 1.3) -> list[dict]:
    """5 folds, all with positive OOS Sharpe and OOS PF > 1 -> low p-value."""
    return [
        {"oos_pf": oos_pf, "oos_sharpe": oos_sharpe, "oos_trades": 12}
        for _ in range(5)
    ]


# ---------------------------------------------------------------------------
# Verdict decision tree
# ---------------------------------------------------------------------------


def test_blocked_on_insufficient_data():
    g = evaluate_gate(
        status="INSUFFICIENT_DATA", summary={}, folds=[], n_tested=123,
    )
    assert g.verdict == VERDICT_BLOCKED
    assert g.raw_p == 1.0 and g.bonferroni_p == 1.0
    assert g.survives_raw is False and g.survives_bonferroni is False


def test_blocked_on_per_fold_trade_floor():
    s = _passing_summary(min_fold_oos_trades=4)
    g = evaluate_gate(
        status="OK", summary=s, folds=_passing_folds(), n_tested=123,
    )
    assert g.verdict == VERDICT_BLOCKED
    assert "min_fold_oos_trades" in g.reason


def test_blocked_on_total_trade_floor():
    s = _passing_summary(total_oos_trades=MIN_TOTAL_OOS_TRADES - 1)
    g = evaluate_gate(
        status="OK", summary=s, folds=_passing_folds(), n_tested=123,
    )
    assert g.verdict == VERDICT_BLOCKED
    assert "total_oos_trades" in g.reason


def test_blocked_on_median_pf_floor():
    s = _passing_summary(median_oos_pf=MIN_MEDIAN_OOS_PF - 0.1)
    g = evaluate_gate(
        status="OK", summary=s, folds=_passing_folds(), n_tested=123,
    )
    assert g.verdict == VERDICT_BLOCKED
    assert "median_oos_pf" in g.reason


def test_blocked_on_median_sharpe_floor():
    s = _passing_summary(median_oos_sharpe=0.5)
    g = evaluate_gate(
        status="OK", summary=s, folds=_passing_folds(), n_tested=123,
    )
    assert g.verdict == VERDICT_BLOCKED
    assert "median_oos_sharpe" in g.reason


def test_blocked_when_too_few_folds_above_pf_one():
    # 5 folds but only 2 have oos_pf > 1
    folds = [
        {"oos_pf": 1.5, "oos_sharpe": 1.0, "oos_trades": 12},
        {"oos_pf": 1.5, "oos_sharpe": 1.0, "oos_trades": 12},
        {"oos_pf": 0.8, "oos_sharpe": 0.4, "oos_trades": 12},
        {"oos_pf": 0.9, "oos_sharpe": 0.5, "oos_trades": 12},
        {"oos_pf": 0.7, "oos_sharpe": 0.3, "oos_trades": 12},
    ]
    g = evaluate_gate(
        status="OK", summary=_passing_summary(), folds=folds, n_tested=123,
    )
    assert g.verdict == VERDICT_BLOCKED
    assert "folds_with_oos_pf>1" in g.reason


def test_blocked_on_is_to_oos_degradation_cap():
    s = _passing_summary(
        max_is_to_oos_sharpe_degradation_pct=MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT + 5,
    )
    g = evaluate_gate(
        status="OK", summary=s, folds=_passing_folds(), n_tested=123,
    )
    assert g.verdict == VERDICT_BLOCKED
    assert "is_to_oos_sharpe_degradation" in g.reason


def test_watch_when_structural_pass_but_bonferroni_fails():
    # Lower-magnitude positive Sharpes -> raw_p small but Bonferroni
    # (multiplied by 123) lands above alpha.
    folds = [
        {"oos_pf": 1.1, "oos_sharpe": 0.30, "oos_trades": 12},
        {"oos_pf": 1.1, "oos_sharpe": 0.35, "oos_trades": 12},
        {"oos_pf": 1.1, "oos_sharpe": 0.28, "oos_trades": 12},
        {"oos_pf": 1.1, "oos_sharpe": 0.32, "oos_trades": 12},
        {"oos_pf": 1.1, "oos_sharpe": 0.30, "oos_trades": 12},
    ]
    g = evaluate_gate(
        status="OK", summary=_passing_summary(), folds=folds, n_tested=123,
    )
    # raw should be tiny (very tight cluster around 0.31), bonferroni
    # blown up. But median Sharpe (0.30) fails the 0.70 floor first, so
    # we'd block on that. Use a passing-Sharpe summary instead.
    g = evaluate_gate(
        status="OK",
        summary=_passing_summary(median_oos_sharpe=0.30),
        folds=folds, n_tested=123,
    )
    # Falls on median_oos_sharpe floor -> BLOCKED, not WATCH. We need
    # the gate's WATCH path: structural pass + bonferroni fail.
    # Use moderate-Sharpe but lots of noise so raw_p is between 0.001
    # and 0.05, then Bonferroni pushes it over alpha.
    folds2 = [
        {"oos_pf": 1.4, "oos_sharpe": 0.90, "oos_trades": 12},
        {"oos_pf": 1.4, "oos_sharpe": 1.10, "oos_trades": 12},
        {"oos_pf": 1.4, "oos_sharpe": 0.80, "oos_trades": 12},
        {"oos_pf": 1.4, "oos_sharpe": 1.00, "oos_trades": 12},
        {"oos_pf": 1.4, "oos_sharpe": 0.85, "oos_trades": 12},
    ]
    g = evaluate_gate(
        status="OK", summary=_passing_summary(),
        folds=folds2, n_tested=10000,   # huge n_tested -> Bonferroni busts
    )
    assert g.verdict == VERDICT_WATCH
    assert g.survives_raw is True
    assert g.survives_bonferroni is False


def test_validated_research_candidate_when_worst_fold_below_one():
    """Bonferroni passes but worst-fold OOS PF < 1.0 -> research label."""
    s = _passing_summary(worst_fold_oos_pf=0.95)
    folds = _passing_folds(oos_sharpe=1.2, oos_pf=1.4)
    g = evaluate_gate(status="OK", summary=s, folds=folds, n_tested=123)
    assert g.verdict == VERDICT_VALIDATED_RESEARCH_CANDIDATE
    assert g.survives_bonferroni is True


def test_micro_live_candidate_when_all_gates_and_worst_fold_above_one():
    s = _passing_summary(worst_fold_oos_pf=1.20)
    folds = _passing_folds(oos_sharpe=1.2, oos_pf=1.4)
    g = evaluate_gate(status="OK", summary=s, folds=folds, n_tested=123)
    assert g.verdict == VERDICT_MICRO_LIVE_CANDIDATE
    assert g.survives_bonferroni is True
    # Highest label MUST still say manual review required
    assert "manual" in g.reason.lower()


def test_all_verdicts_tuple_is_stable():
    assert ALL_VERDICTS == (
        VERDICT_BLOCKED,
        VERDICT_WATCH,
        VERDICT_VALIDATED_RESEARCH_CANDIDATE,
        VERDICT_MICRO_LIVE_CANDIDATE,
    )


# ---------------------------------------------------------------------------
# Wiring: attach_gate_results + CSV output
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
        ),
        per_variant_counts={"V0": 1, "V1": 0, "V2": 1, "V3": 0},
    )


def test_attach_gate_results_populates_gate_on_every_row():
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)
    gated = attach_gate_results(rows, n_tested=grid.total)
    assert len(gated) == len(rows)
    assert all(r.gate is not None for r in gated)
    assert all(r.gate.verdict in ALL_VERDICTS for r in gated)
    assert all(r.gate.n_tested == grid.total for r in gated)


def test_csv_includes_pr3_gate_columns(tmp_path: Path):
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)
    rows = attach_gate_results(rows, n_tested=grid.total)
    csv_path = tmp_path / "out.csv"
    write_csv(rows, csv_path)
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        first = next(reader)
    # PR 3 appended columns must exist and be populated
    for col in (
        "raw_p", "bonferroni_p", "n_tested",
        "survives_raw", "survives_bonferroni", "verdict", "gate_reason",
    ):
        assert col in first, f"missing column {col}"
        assert first[col] != "", f"empty {col} after attach_gate_results"
    assert first["verdict"] in ALL_VERDICTS
    assert first["survives_raw"] in ("true", "false")
    assert first["survives_bonferroni"] in ("true", "false")
    assert int(first["n_tested"]) == grid.total


def test_csv_gate_columns_empty_when_gate_not_attached(tmp_path: Path):
    """If attach_gate_results is skipped, gate columns are blank \u2014
    preserves backward compatibility with PR 2 callers."""
    grid = _tiny_grid()
    data = {"EURUSD": _ohlcv(2000)}
    rows = run_grid_search(data, grid)  # no attach_gate_results call
    csv_path = tmp_path / "out.csv"
    write_csv(rows, csv_path)
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        first = next(reader)
    assert first["verdict"] == ""
    assert first["raw_p"] == ""
    assert first["bonferroni_p"] == ""


def test_csv_columns_constant_appends_pr3_columns():
    """The locked-prefix contract still holds; PR 3 columns are appended."""
    expected_prefix = (
        "combo_key", "variant", "params_json", "symbol", "status",
        "n_folds", "median_oos_pf", "worst_fold_oos_pf",
        "median_oos_sharpe", "max_oos_dd_pct",
        "max_is_to_oos_sharpe_degradation_pct",
        "total_oos_trades", "min_fold_oos_trades",
    )
    expected_suffix = (
        "raw_p", "bonferroni_p", "n_tested",
        "survives_raw", "survives_bonferroni", "verdict", "gate_reason",
    )
    assert CSV_COLUMNS[:len(expected_prefix)] == expected_prefix
    assert CSV_COLUMNS[len(expected_prefix):] == expected_suffix

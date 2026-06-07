"""
Phase 11 orchestrator behavior (PR 1).

Covers:
  * Orchestrator returns the documented per-symbol shape.
  * Verdict label is always a member of the restricted set (Amendment A § A.7).
  * PR 1 verdict is BLOCKED (acceptance gate not implemented yet).
  * INSUFFICIENT_DATA path is gracefully handled when a symbol's CSV is short.
  * Ranking is sorted by composite key (A.6).
  * Report markdown contains all required headers and the BACKTEST_ONLY notice.
  * Unknown variant is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from src.phase11_orchestrator import (
    ALLOWED_VERDICTS,
    VERDICT_BLOCKED,
    FoldResult,
    Phase11Splitter,
    _composite_ranking,
    _median,
    render_orchestrator_markdown,
    run_orchestrator,
)


def _ohlcv(n: int, start: float = 1.10) -> pd.DataFrame:
    # Simple deterministic random-walk-ish series so the backtest engine has
    # something to work with. Values don't matter for orchestrator-shape tests;
    # the backtest may produce zero trades and that's fine.
    idx = pd.date_range("2010-01-01", periods=n, freq="D", tz="UTC")
    closes = [start + 0.0005 * i for i in range(n)]
    highs = [c * 1.002 for c in closes]
    lows = [c * 0.998 for c in closes]
    opens = [c * 0.999 for c in closes]
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": 0.0},
        index=idx,
    )


def test_run_orchestrator_unknown_variant() -> None:
    with pytest.raises(ValueError, match="unknown variant"):
        run_orchestrator({"EURUSD": _ohlcv(2000)}, variant="VX")


def test_run_orchestrator_returns_documented_shape() -> None:
    report = run_orchestrator({"EURUSD": _ohlcv(2000)}, variant="V0")
    assert set(report.keys()) >= {
        "variant", "n_folds", "warmup_bars", "per_symbol",
        "verdict", "verdict_reason", "ranking",
    }
    assert report["variant"] == "V0"
    assert report["n_folds"] == 5
    assert "EURUSD" in report["per_symbol"]


def test_verdict_label_is_in_allowed_set() -> None:
    report = run_orchestrator({"EURUSD": _ohlcv(2000)}, variant="V0")
    assert report["verdict"] in ALLOWED_VERDICTS


def test_pr1_verdict_is_blocked_by_design() -> None:
    # Per design doc: until phase11/pr3 lands the acceptance gate, nothing
    # can earn a PASS. This is intentional and must remain true.
    report = run_orchestrator({"EURUSD": _ohlcv(2000)}, variant="V0")
    assert report["verdict"] == VERDICT_BLOCKED
    assert "not yet implemented" in report["verdict_reason"]


def test_insufficient_data_path_does_not_crash() -> None:
    # 500 bars < default min_bars (1000) → splitter raises, orchestrator
    # records INSUFFICIENT_DATA and continues with other symbols.
    report = run_orchestrator(
        {"EURUSD": _ohlcv(500), "GBPUSD": _ohlcv(2000)},
        variant="V0",
    )
    assert report["per_symbol"]["EURUSD"]["status"] == "INSUFFICIENT_DATA"
    assert report["per_symbol"]["GBPUSD"]["status"] == "OK"


def test_per_symbol_ok_payload_includes_summary_and_folds() -> None:
    report = run_orchestrator({"EURUSD": _ohlcv(2000)}, variant="V0")
    payload = report["per_symbol"]["EURUSD"]
    assert payload["status"] == "OK"
    assert len(payload["folds"]) == 5
    s = payload["summary"]
    for key in (
        "median_oos_pf", "worst_fold_oos_pf", "median_oos_sharpe",
        "max_oos_dd_pct", "max_is_to_oos_sharpe_degradation_pct",
        "total_oos_trades", "min_fold_oos_trades",
    ):
        assert key in s


def test_render_markdown_contains_required_headers() -> None:
    report = run_orchestrator({"EURUSD": _ohlcv(2000)}, variant="V0")
    md = render_orchestrator_markdown(report)
    assert "# Phase 11 — Walk-Forward Orchestrator (PR 1)" in md
    assert "BACKTEST_ONLY" in md
    assert "Composite ranking" in md
    # No live-trading vocabulary should appear in the rendered report.
    for forbidden in ("LIVE_TRADING=true", "MICRO_LIVE=true", "FULL_LIVE=true"):
        assert forbidden not in md


def test_median_helper() -> None:
    assert _median([]) == 0.0
    assert _median([1.0]) == 1.0
    assert _median([1.0, 3.0]) == 2.0
    assert _median([5.0, 1.0, 3.0]) == 3.0


def _fr(sym: str, fold: int, oos_sharpe: float, oos_pf: float,
        oos_dd: float = 5.0, oos_trades: int = 10) -> FoldResult:
    return FoldResult(
        symbol=sym, variant="V0", fold=fold,
        is_metrics={"sharpe": 1.0, "profit_factor": 1.2, "trades": 20,
                    "max_drawdown_pct": 5.0},
        oos_metrics={"sharpe": oos_sharpe, "profit_factor": oos_pf,
                     "trades": oos_trades, "max_drawdown_pct": oos_dd},
    )


def test_composite_ranking_sorts_by_priority_keys() -> None:
    per_symbol = {
        "A": {"status": "OK", "summary": {
            "median_oos_pf": 1.2, "worst_fold_oos_pf": 0.9,
            "median_oos_sharpe": 0.6, "max_oos_dd_pct": 10.0,
            "max_is_to_oos_sharpe_degradation_pct": 5.0,
            "total_oos_trades": 40, "min_fold_oos_trades": 5,
        }, "folds": []},
        "B": {"status": "OK", "summary": {
            "median_oos_pf": 1.5, "worst_fold_oos_pf": 1.1,
            "median_oos_sharpe": 0.8, "max_oos_dd_pct": 8.0,
            "max_is_to_oos_sharpe_degradation_pct": 10.0,
            "total_oos_trades": 50, "min_fold_oos_trades": 6,
        }, "folds": []},
        "C": {"status": "OK", "summary": {
            "median_oos_pf": 1.5, "worst_fold_oos_pf": 0.95,
            "median_oos_sharpe": 0.75, "max_oos_dd_pct": 12.0,
            "max_is_to_oos_sharpe_degradation_pct": 20.0,
            "total_oos_trades": 35, "min_fold_oos_trades": 3,
        }, "folds": []},
    }
    ranked = _composite_ranking(per_symbol)
    # Tie on median_oos_pf (B and C at 1.5): B wins on worst_fold (1.1 > 0.95).
    # A is last (lower median_oos_pf).
    assert [r["symbol"] for r in ranked] == ["B", "C", "A"]


def test_fold_result_handles_infinite_pf() -> None:
    fr = FoldResult(
        symbol="EURUSD", variant="V0", fold=1,
        is_metrics={"sharpe": 1.0},
        oos_metrics={"profit_factor": float("inf"), "sharpe": 2.0, "trades": 5},
    )
    # Infinity replaced with finite sentinel so downstream sorting/stats work.
    assert fr.oos_pf == 99.0


def test_fold_result_degradation_with_zero_is_sharpe() -> None:
    fr = FoldResult(
        symbol="EURUSD", variant="V0", fold=1,
        is_metrics={"sharpe": 0.0},
        oos_metrics={"sharpe": 0.5, "profit_factor": 1.3, "trades": 5},
    )
    # Undefined → treated as failure (100% degradation) so degradation gates
    # can't be gamed by negative-IS edge cases.
    assert fr.is_to_oos_sharpe_degradation_pct == 100.0


def test_fold_result_degradation_negative_clamped_to_zero() -> None:
    fr = FoldResult(
        symbol="EURUSD", variant="V0", fold=1,
        is_metrics={"sharpe": 1.0},
        oos_metrics={"sharpe": 1.5, "profit_factor": 1.3, "trades": 5},
    )
    # OOS better than IS → 0% degradation (we don't reward negative deg).
    assert fr.is_to_oos_sharpe_degradation_pct == 0.0

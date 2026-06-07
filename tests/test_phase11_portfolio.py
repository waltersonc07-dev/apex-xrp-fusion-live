"""
Phase 11 — Portfolio aggregation tests (PR 4).

Covers:
  * aggregate_portfolio_folds equal-weights primary symbols correctly
  * Portfolio fold OOS PF derived from summed gross profit / |gross loss|
  * Per-pair >40% net-profit concentration cap blocks the portfolio
  * Control catastrophic failure (3 of 5 folds PF<0.5) downgrades
    MICRO_LIVE_CANDIDATE -> WATCH (but not below)
  * build_portfolio_verdicts emits one verdict per combo, INSUFFICIENT_DATA
    when any primary symbol is missing
  * Portfolio CSV has locked column order and gate columns populated
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.phase11_gate import (
    VERDICT_BLOCKED,
    VERDICT_MICRO_LIVE_CANDIDATE,
    VERDICT_VALIDATED_RESEARCH_CANDIDATE,
    VERDICT_WATCH,
)
from src.phase11_portfolio import (
    CONTROL_CATASTROPHIC_FOLD_COUNT,
    CONTROL_CATASTROPHIC_PF_BAR,
    MAX_PER_PAIR_NET_PROFIT_SHARE,
    PORTFOLIO_CSV_COLUMNS,
    PRIMARY_PORTFOLIO_SYMBOLS,
    PortfolioVerdict,
    aggregate_portfolio_folds,
    build_portfolio_verdicts,
    evaluate_portfolio_gate,
    render_portfolio_markdown,
    summarize_portfolio,
    write_portfolio_csv,
)
from src.phase11_search import SearchRow


# ---------------------------------------------------------------------------
# Fixtures: synthetic fold payloads
# ---------------------------------------------------------------------------


def _fold(
    *, gp: float, gl: float, sharpe: float, trades: int = 10,
    dd: float = 5.0, deg: float = 10.0, net: float | None = None,
) -> dict:
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
    """5 folds with consistent OOS PF ~1.4 and good Sharpes."""
    return [
        _fold(gp=140.0, gl=100.0, sharpe=1.0, trades=10, net=symbol_net)
        for _ in range(5)
    ]


def _five_catastrophic_folds() -> list[dict]:
    """5 folds with OOS PF ~0.4 (below the 0.5 control bar)."""
    return [
        _fold(gp=40.0, gl=100.0, sharpe=-0.5, trades=10, dd=20.0, net=-60.0)
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
                (int(f.get("oos_trades", 0)) for f in folds), default=0,
            ),
        },
        folds=tuple(folds),
    )


# ---------------------------------------------------------------------------
# aggregate_portfolio_folds
# ---------------------------------------------------------------------------


def test_aggregate_portfolio_folds_sums_gross_pl_and_averages_sharpe():
    primary = {
        "EURUSD": [_fold(gp=100.0, gl=50.0, sharpe=1.0, trades=10)],
        "GBPUSD": [_fold(gp=80.0,  gl=40.0, sharpe=0.8, trades=8)],
        "XAUUSD": [_fold(gp=200.0, gl=100.0, sharpe=1.2, trades=12)],
    }
    folds = aggregate_portfolio_folds(primary)
    assert len(folds) == 1
    f = folds[0]
    # (100+80+200) / (50+40+100) = 380 / 190 = 2.0
    assert f.oos_pf == pytest.approx(2.0, abs=1e-9)
    # Sharpe = mean(1.0, 0.8, 1.2) = 1.0
    assert f.oos_sharpe == pytest.approx(1.0, abs=1e-9)
    assert f.oos_trades == 30
    assert set(f.net_profit_by_symbol.keys()) == set(primary)


def test_aggregate_portfolio_folds_handles_uneven_fold_counts():
    primary = {
        "EURUSD": [_fold(gp=100, gl=50, sharpe=1.0)] * 3,
        "GBPUSD": [_fold(gp=80,  gl=40, sharpe=0.8)] * 5,
        "XAUUSD": [_fold(gp=200, gl=100, sharpe=1.2)] * 5,
    }
    folds = aggregate_portfolio_folds(primary)
    # Truncates to the shortest input length.
    assert len(folds) == 3


# ---------------------------------------------------------------------------
# summarize_portfolio: concentration + control diagnostics
# ---------------------------------------------------------------------------


def test_summarize_portfolio_computes_per_pair_share():
    primary = {
        # EURUSD dominates: 90 units of |net profit| out of 100 total
        "EURUSD": [_fold(gp=180, gl=90, sharpe=1.0, net=90.0)],
        "GBPUSD": [_fold(gp=15,  gl=10, sharpe=0.5, net=5.0)],
        "XAUUSD": [_fold(gp=15,  gl=10, sharpe=0.5, net=5.0)],
    }
    folds = aggregate_portfolio_folds(primary)
    s = summarize_portfolio(folds)
    assert s.max_per_pair_net_profit_share == pytest.approx(0.9, abs=1e-9)
    assert s.net_profit_share_by_symbol["EURUSD"] == pytest.approx(0.9, abs=1e-9)


def test_summarize_portfolio_flags_control_catastrophe():
    folds = aggregate_portfolio_folds({
        "EURUSD": _five_passing_folds(),
        "GBPUSD": _five_passing_folds(),
        "XAUUSD": _five_passing_folds(),
    })
    control = {"USDJPY": _five_catastrophic_folds()}
    s = summarize_portfolio(folds, control_folds=control)
    assert s.control_catastrophic is True
    assert s.control_folds_below_bar["USDJPY"] == 5


def test_summarize_portfolio_no_control_catastrophe_when_under_threshold():
    folds = aggregate_portfolio_folds({
        "EURUSD": _five_passing_folds(),
        "GBPUSD": _five_passing_folds(),
        "XAUUSD": _five_passing_folds(),
    })
    # Only 2 catastrophic folds out of 5 -> not catastrophic (< 3)
    control_folds = [
        _fold(gp=40, gl=100, sharpe=-0.5),
        _fold(gp=40, gl=100, sharpe=-0.5),
        _fold(gp=140, gl=100, sharpe=0.8),
        _fold(gp=140, gl=100, sharpe=0.8),
        _fold(gp=140, gl=100, sharpe=0.8),
    ]
    s = summarize_portfolio(folds, control_folds={"USDJPY": control_folds})
    assert s.control_catastrophic is False
    assert s.control_folds_below_bar["USDJPY"] == 2


# ---------------------------------------------------------------------------
# Portfolio gate
# ---------------------------------------------------------------------------


def test_portfolio_gate_blocks_on_per_pair_concentration():
    primary = {
        "EURUSD": [_fold(gp=180, gl=90, sharpe=1.0, net=90.0, trades=10)] * 5,
        "GBPUSD": [_fold(gp=15,  gl=10, sharpe=0.8, net=5.0,  trades=10)] * 5,
        "XAUUSD": [_fold(gp=15,  gl=10, sharpe=0.9, net=5.0,  trades=10)] * 5,
    }
    folds = aggregate_portfolio_folds(primary)
    s = summarize_portfolio(folds)
    assert s.max_per_pair_net_profit_share > MAX_PER_PAIR_NET_PROFIT_SHARE
    gate, downgrades = evaluate_portfolio_gate(
        summary=s, folds=folds, n_tested=123,
    )
    assert gate.verdict == VERDICT_BLOCKED
    assert "max_per_pair_net_profit_share" in gate.reason


def test_portfolio_gate_passes_when_balanced():
    primary = {
        "EURUSD": [_fold(gp=140, gl=100, sharpe=1.0, net=40.0, trades=10)] * 5,
        "GBPUSD": [_fold(gp=140, gl=100, sharpe=1.0, net=40.0, trades=10)] * 5,
        "XAUUSD": [_fold(gp=140, gl=100, sharpe=1.0, net=40.0, trades=10)] * 5,
    }
    folds = aggregate_portfolio_folds(primary)
    s = summarize_portfolio(folds)
    gate, _ = evaluate_portfolio_gate(summary=s, folds=folds, n_tested=1)
    # Balanced, strong, tiny n_tested -> bonferroni survives.
    assert gate.verdict in (
        VERDICT_VALIDATED_RESEARCH_CANDIDATE, VERDICT_MICRO_LIVE_CANDIDATE,
    )


def test_portfolio_gate_downgrades_micro_live_to_watch_on_control_catastrophe():
    primary = {
        "EURUSD": [_fold(gp=140, gl=100, sharpe=1.0, net=40.0, trades=10)] * 5,
        "GBPUSD": [_fold(gp=140, gl=100, sharpe=1.0, net=40.0, trades=10)] * 5,
        "XAUUSD": [_fold(gp=140, gl=100, sharpe=1.0, net=40.0, trades=10)] * 5,
    }
    folds = aggregate_portfolio_folds(primary)
    s = summarize_portfolio(
        folds, control_folds={"USDJPY": _five_catastrophic_folds()},
    )
    # Pre-conditions: balanced + strong + control catastrophic.
    assert s.control_catastrophic is True
    gate, downgrades = evaluate_portfolio_gate(
        summary=s, folds=folds, n_tested=1,
    )
    assert gate.verdict == VERDICT_WATCH
    assert any("control" in d for d in downgrades)
    assert "downgraded to WATCH" in gate.reason


# ---------------------------------------------------------------------------
# build_portfolio_verdicts (combines per-symbol SearchRows -> portfolio)
# ---------------------------------------------------------------------------


def test_build_portfolio_verdicts_emits_one_per_combo():
    rows = [
        _row("EURUSD", _five_passing_folds()),
        _row("GBPUSD", _five_passing_folds()),
        _row("XAUUSD", _five_passing_folds()),
        _row("USDJPY", _five_passing_folds()),
    ]
    verdicts = build_portfolio_verdicts(rows, n_tested=123)
    assert len(verdicts) == 1
    assert verdicts[0].status == "OK"
    assert verdicts[0].variant == "V0"
    assert verdicts[0].n_primary_folds == 5
    assert verdicts[0].gate.verdict in (
        VERDICT_BLOCKED, VERDICT_WATCH,
        VERDICT_VALIDATED_RESEARCH_CANDIDATE, VERDICT_MICRO_LIVE_CANDIDATE,
    )


def test_build_portfolio_verdicts_insufficient_data_when_primary_missing():
    # Missing XAUUSD -> portfolio cannot be aggregated.
    rows = [
        _row("EURUSD", _five_passing_folds()),
        _row("GBPUSD", _five_passing_folds()),
    ]
    verdicts = build_portfolio_verdicts(rows, n_tested=123)
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.status == "INSUFFICIENT_DATA"
    assert v.n_primary_folds == 0
    assert v.gate.verdict == VERDICT_BLOCKED
    assert "missing" in v.gate.reason.lower()


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------


def test_portfolio_csv_locked_column_order(tmp_path: Path):
    rows = [
        _row("EURUSD", _five_passing_folds()),
        _row("GBPUSD", _five_passing_folds()),
        _row("XAUUSD", _five_passing_folds()),
    ]
    verdicts = build_portfolio_verdicts(rows, n_tested=123)
    p = tmp_path / "portfolio.csv"
    write_portfolio_csv(verdicts, p)
    with p.open() as fh:
        reader = csv.reader(fh)
        header = next(reader)
        body = list(reader)
    assert tuple(header) == PORTFOLIO_CSV_COLUMNS
    assert len(body) == len(verdicts)


def test_portfolio_csv_populates_gate_and_concentration_cells(tmp_path: Path):
    rows = [
        _row("EURUSD", _five_passing_folds()),
        _row("GBPUSD", _five_passing_folds()),
        _row("XAUUSD", _five_passing_folds()),
    ]
    verdicts = build_portfolio_verdicts(rows, n_tested=123)
    p = tmp_path / "portfolio.csv"
    write_portfolio_csv(verdicts, p)
    with p.open() as fh:
        first = next(csv.DictReader(fh))
    assert first["verdict"] in (
        VERDICT_BLOCKED, VERDICT_WATCH,
        VERDICT_VALIDATED_RESEARCH_CANDIDATE, VERDICT_MICRO_LIVE_CANDIDATE,
    )
    assert first["survives_raw"] in ("true", "false")
    assert first["survives_bonferroni"] in ("true", "false")
    assert int(first["n_tested"]) == 123
    assert int(first["n_primary_folds"]) == 5
    # net_profit_share_json round-trips to a dict
    parsed = json.loads(first["net_profit_share_json"])
    assert isinstance(parsed, dict)
    assert set(parsed.keys()) == set(PRIMARY_PORTFOLIO_SYMBOLS)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_portfolio_markdown_lists_candidates_and_safety_notice():
    rows = [
        _row("EURUSD", _five_passing_folds()),
        _row("GBPUSD", _five_passing_folds()),
        _row("XAUUSD", _five_passing_folds()),
    ]
    verdicts = build_portfolio_verdicts(rows, n_tested=1)
    md = render_portfolio_markdown(verdicts, n_tested=1)
    assert "Phase 11 — Portfolio Verdicts" in md
    assert "BACKTEST_ONLY" in md
    assert "Verdict counts" in md


def test_constants_are_exposed_for_documentation():
    assert MAX_PER_PAIR_NET_PROFIT_SHARE == 0.40
    assert CONTROL_CATASTROPHIC_PF_BAR == 0.50
    assert CONTROL_CATASTROPHIC_FOLD_COUNT == 3

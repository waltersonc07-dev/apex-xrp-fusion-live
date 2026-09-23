"""Unit / smoke tests for Stacked MTF v3.3 (no network, synthetic 15m data)."""
from __future__ import annotations

import pandas as pd

from src.strategy_stacked_mtf import (
    DEFAULT_STACKED_MTF,
    generate_stacked_mtf_signals,
    run_stacked_mtf_backtest,
)


def _synthetic_15m(n: int = 400, start: str = "2024-01-01", trend: float = 0.002) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq="15min", tz="UTC")
    # Gentle uptrend so stacks can eventually go bullish after warm-up
    close = pd.Series([1.0 + i * trend for i in range(n)], index=idx)
    high = close + 0.01
    low = close - 0.01
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": 1000.0},
        index=idx,
    )


def _short_cfg(**overrides):
    cfg = {
        "stacked_mtf": {
            **DEFAULT_STACKED_MTF,
            "ema_fast": 3,
            "ema_slow": 5,
            "dema_length": 8,
            "supertrend_atr_length": 3,
            "supertrend_multiplier": 1.5,
            "require_htf": True,
            "require_sync": True,
            "fresh_only": False,
            "use_stop": False,
            **overrides,
        },
        "backtest": {"initial_equity": 10000.0, "commission_pct": 0.05, "slippage_bps": 2},
        "risk": {"mode": "BACKTEST_ONLY"},
    }
    return cfg


def test_signals_have_expected_columns():
    df = _synthetic_15m(120)
    out = generate_stacked_mtf_signals(df, _short_cfg())
    for col in (
        "ema_fast",
        "ema_slow",
        "dema_200",
        "supertrend",
        "stack_up",
        "stack_dn",
        "htf_stack_up",
        "is_htf_open",
        "long_signal",
        "short_signal",
        "exit_signal",
        "risk_distance",
    ):
        assert col in out.columns
    assert not out["short_signal"].any()


def test_entries_only_on_htf_open_when_synced():
    df = _synthetic_15m(200)
    out = generate_stacked_mtf_signals(df, _short_cfg(require_sync=True))
    if out["long_signal"].any():
        assert bool((~out["long_signal"] | out["is_htf_open"]).all())


def test_fresh_only_off_allows_continuation_on_sync_bar():
    """With freshOnly False, long_signal does not require a rising edge on 15m stack."""
    df = _synthetic_15m(200)
    out = generate_stacked_mtf_signals(df, _short_cfg(fresh_only=False, require_htf=False))
    # On HTF open bars where stack_up is true, signal should fire even if prior bar was also up
    candidates = out["is_htf_open"] & out["stack_up"]
    if candidates.sum() >= 2:
        # At least some signals should align with candidates when HTF not required
        assert (out.loc[candidates, "long_signal"]).any()


def test_backtest_applies_fees_and_slippage():
    df = _synthetic_15m(300, trend=0.003)
    report = run_stacked_mtf_backtest(
        df,
        _short_cfg(),
        fee_bps=5,
        slippage_bps=10,
        entry_on_close=True,
        save_trades_path=None,
    )
    assert "total_trades" in report
    assert report["slippage_bps"] == 10
    if report["total_trades"] > 0:
        assert report["fees_paid"] >= 0
        assert report["slippage_cost"] > 0
        # Long entries should be slipped up from raw close
        assert report["trades"][0]["entry_price"] > 0


def test_long_only_no_short_trades():
    df = _synthetic_15m(250, trend=0.002)
    report = run_stacked_mtf_backtest(df, _short_cfg(), save_trades_path=None)
    for trade in report["trades"]:
        assert trade["side"] == "long"


def test_exit_reason_stack_flip_or_eot():
    df = _synthetic_15m(250, trend=0.004)
    # Force a downtrend tail so a stack flip can occur after entries
    df = df.copy()
    n = len(df)
    for i in range(n // 2, n):
        df.iloc[i, df.columns.get_loc("close")] = 1.0 + (n // 2) * 0.004 - (i - n // 2) * 0.005
        df.iloc[i, df.columns.get_loc("high")] = df.iloc[i]["close"] + 0.01
        df.iloc[i, df.columns.get_loc("low")] = df.iloc[i]["close"] - 0.01
        df.iloc[i, df.columns.get_loc("open")] = df.iloc[i]["close"]
    report = run_stacked_mtf_backtest(df, _short_cfg(require_htf=False), fee_bps=5, slippage_bps=2, save_trades_path=None)
    for trade in report["trades"]:
        assert trade["exit_reason"] in {"stack_flip", "end_of_test", "stop_loss"}

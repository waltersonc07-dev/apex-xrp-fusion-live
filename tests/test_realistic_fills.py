import pandas as pd

from src.backtest_engine import run_realistic_backtest


def base_config(policy="stop_first", slippage_bps=10):
    return {
        "strategy": {"min_rr": 2.0, "use_flip_exit": True},
        "risk": {"mode": "BACKTEST_ONLY", "normal_live_risk_pct": 0.25, "allow_leverage": True},
        "backtest": {"initial_equity": 10000, "same_bar_policy": policy, "commission_pct": 0.0, "slippage_bps": slippage_bps},
    }


def patch_signals(monkeypatch, rows):
    import src.backtest_engine as engine

    df = pd.DataFrame(rows)
    df.index = pd.date_range("2026-01-01", periods=len(df), freq="h", tz="UTC")
    monkeypatch.setattr(engine, "generate_signals", lambda source, cfg: df)


def test_same_bar_tp_and_sl_stop_first(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": True, "short_signal": False, "stop_loss": 95, "take_profit": 110},
        {"open": 100, "high": 111, "low": 94, "close": 100, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), base_config("stop_first", 0), save_trades_path=None)
    assert result["trades"][0]["exit_reason"] == "ambiguous_stop_first"
    assert result["trades"][0]["realized_r_multiple"] < 0


def test_slippage_applied_against_long_trader(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": True, "short_signal": False, "stop_loss": 95, "take_profit": 111},
        {"open": 100, "high": 112, "low": 99, "close": 111, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), base_config(slippage_bps=10), save_trades_path=None)
    assert result["trades"][0]["entry_price"] > 100


def test_slippage_applied_against_short_trader(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": False, "short_signal": True, "stop_loss": 105, "take_profit": 89},
        {"open": 100, "high": 101, "low": 88, "close": 89, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), base_config(slippage_bps=10), save_trades_path=None)
    assert result["trades"][0]["entry_price"] < 100

import pandas as pd

from src.backtest_engine import run_realistic_backtest


def config():
    return {
        "strategy": {"min_rr": 2.0, "use_flip_exit": True},
        "risk": {"mode": "BACKTEST_ONLY", "normal_live_risk_pct": 0.25, "allow_leverage": True},
        "backtest": {"initial_equity": 10000, "same_bar_policy": "stop_first", "commission_pct": 0.05, "slippage_bps": 0},
    }


def signal_frame(rows):
    df = pd.DataFrame(rows)
    df.index = pd.date_range("2026-01-01", periods=len(df), freq="h", tz="UTC")
    return df


def patch_signals(monkeypatch, rows):
    import src.backtest_engine as engine

    monkeypatch.setattr(engine, "generate_signals", lambda df, cfg: signal_frame(rows))


def test_long_stop_hit(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": True, "short_signal": False, "stop_loss": 95, "take_profit": 110},
        {"open": 100, "high": 101, "low": 94, "close": 96, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), config(), save_trades_path=None)
    trade = result["trades"][0]
    assert trade["exit_reason"] == "stop_loss"
    assert trade["realized_r_multiple"] < 0


def test_long_take_profit_hit(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": True, "short_signal": False, "stop_loss": 95, "take_profit": 110},
        {"open": 100, "high": 111, "low": 99, "close": 110, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), config(), save_trades_path=None)
    assert result["trades"][0]["exit_reason"] == "take_profit"


def test_short_stop_hit(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": False, "short_signal": True, "stop_loss": 105, "take_profit": 90},
        {"open": 100, "high": 106, "low": 99, "close": 104, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), config(), save_trades_path=None)
    assert result["trades"][0]["exit_reason"] == "stop_loss"


def test_short_take_profit_hit(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": False, "short_signal": True, "stop_loss": 105, "take_profit": 90},
        {"open": 100, "high": 101, "low": 89, "close": 90, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), config(), save_trades_path=None)
    assert result["trades"][0]["exit_reason"] == "take_profit"


def test_fees_applied_both_sides(monkeypatch):
    patch_signals(monkeypatch, [
        {"open": 100, "high": 101, "low": 99, "close": 100, "long_signal": True, "short_signal": False, "stop_loss": 95, "take_profit": 110},
        {"open": 100, "high": 111, "low": 99, "close": 110, "long_signal": False, "short_signal": False, "stop_loss": None, "take_profit": None},
    ])
    result = run_realistic_backtest(pd.DataFrame({"close": [1, 2]}), config(), save_trades_path=None)
    trade = result["trades"][0]
    assert trade["fees"] > 0
    assert trade["net_pnl"] < trade["gross_pnl"]


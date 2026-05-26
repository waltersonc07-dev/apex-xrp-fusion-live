import pandas as pd

from src.stress_test import run_stress_tests


def test_stress_test_returns_all_required_scenarios(monkeypatch):
    import src.stress_test as st

    def fake_backtest(*args, **kwargs):
        return {"net_profit": 100, "profit_factor": 1.5, "max_drawdown_pct": 1, "total_trades": 10}

    monkeypatch.setattr(st, "run_backtest_on_df", fake_backtest)
    result = run_stress_tests(pd.DataFrame({"close": [1, 2, 3]}), {
        "strategy": {"supertrend_multiplier": 3.0, "stop_atr_mult": 1.5, "ema_fast": 9, "ema_slow": 21},
        "stress_test": {
            "supertrend_multipliers": [2.8, 3.0, 3.2],
            "stop_atr_multipliers": [1.3, 1.5, 1.7],
        },
    })
    for key in ["normal", "doubled_fees", "slippage_2x", "slippage_3x", "delayed_entry_1", "delayed_entry_2", "parameter_tests"]:
        assert key in result
    assert len(result["parameter_tests"]) == 9


def test_doubled_fees_scenario_doubles_fees_and_slippage(monkeypatch):
    import src.stress_test as st

    calls = []

    def fake_backtest(df, config, fee_bps=5, slippage_bps=2, **kwargs):
        calls.append((fee_bps, slippage_bps))
        return {"net_profit": 100, "profit_factor": 1.5, "max_drawdown_pct": 1, "total_trades": 10}

    monkeypatch.setattr(st, "run_backtest_on_df", fake_backtest)
    run_stress_tests(pd.DataFrame({"close": [1, 2, 3]}), {
        "strategy": {"supertrend_multiplier": 3.0, "stop_atr_mult": 1.5, "ema_fast": 9, "ema_slow": 21},
        "stress_test": {
            "supertrend_multipliers": [3.0],
            "stop_atr_multipliers": [1.5],
        },
    }, base_fee_bps=5, base_slippage_bps=2)
    assert calls[1] == (10, 4)

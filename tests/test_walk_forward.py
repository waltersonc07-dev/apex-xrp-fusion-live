from src.walk_forward import run_walk_forward
import pandas as pd


def test_walk_forward_fails_if_oos_negative(monkeypatch):
    import src.walk_forward as wf

    results = [
        {"net_profit": 100, "profit_factor": 1.5, "max_drawdown_pct": 1, "total_trades": 10, "expectancy": 1},
        {"net_profit": 100, "profit_factor": 1.5, "max_drawdown_pct": 1, "total_trades": 10, "expectancy": 1},
        {"net_profit": -1, "profit_factor": 0.9, "max_drawdown_pct": 1, "total_trades": 10, "expectancy": -1},
    ]

    def fake_backtest(*args, **kwargs):
        return results.pop(0)

    monkeypatch.setattr(wf, "run_backtest_on_df", fake_backtest)
    df = pd.DataFrame({"open": range(10), "high": range(10), "low": range(10), "close": range(10), "volume": range(10)})
    result = run_walk_forward(df, {"validation": {"min_oos_profit_factor": 1.20}})
    assert not result["passed"]

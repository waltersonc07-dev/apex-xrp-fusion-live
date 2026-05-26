import pandas as pd

from src.core_diagnostic import (
    VARIANT_FAMILIES,
    VARIANT_ROWS,
    run_core_diagnostic,
    select_v7_combo_in_sample_only,
)
from src.strategy import generate_signals


def base_config():
    return {
        "strategy": {
            "supertrend_atr_length": 3,
            "supertrend_multiplier": 1.5,
            "ema_fast": 2,
            "ema_slow": 3,
            "dema_length": 3,
            "atr_length": 3,
            "stop_atr_mult": 1.5,
            "tp_atr_mult": 3.0,
            "min_rr": 1.5,
            "resistance_buffer_pct": 0.01,
            "support_buffer_pct": 0.01,
            "use_flip_exit": True,
        },
        "risk": {"normal_live_risk_pct": 0.25, "allow_leverage": False, "mode": "BACKTEST_ONLY"},
        "backtest": {"initial_equity": 10000, "same_bar_policy": "stop_first", "entry_on_close": False},
        "levels": {"resistance": [100], "support": [0.1]},
    }


def sample_df(rows=80):
    idx = pd.date_range("2024-01-01", periods=rows, freq="1h", tz="UTC")
    close = pd.Series([1 + i * 0.01 for i in range(rows)], index=idx)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.02,
            "low": close - 0.02,
            "close": close,
            "volume": [100] * rows,
        },
        index=idx,
    )


def test_core_diagnostic_uses_nine_rows(monkeypatch):
    import src.core_diagnostic as cd

    def fake_backtest(df, config, fee_bps=5, slippage_bps=2, **kwargs):
        return {
            "net_profit": 10 - fee_bps - slippage_bps,
            "profit_factor": 1.1,
            "max_drawdown_pct": 2,
            "win_rate": 50,
            "total_trades": 12,
            "expectancy": 1,
        }

    monkeypatch.setattr(cd, "run_backtest_on_df", fake_backtest)
    result = run_core_diagnostic(sample_df(), base_config())
    assert result["variant_rows_tested"] == 9
    assert result["variant_families"] == 8
    assert [row["variant"] for row in result["rows"]] == VARIANT_ROWS
    assert VARIANT_FAMILIES == 8


def test_v3_uses_true_four_hour_dema_slope_column():
    cfg = base_config()
    cfg["strategy"]["use_4h_dema_slope"] = True
    out = generate_signals(sample_df(120), cfg)
    assert "dema_4h_slope" in out.columns
    assert out["dema_4h_slope"].iloc[-1] > 0


def test_v7_selection_uses_only_in_sample(monkeypatch):
    import src.core_diagnostic as cd

    seen_lengths = []

    def fake_backtest(df, config, *args, **kwargs):
        seen_lengths.append(len(df))
        return {
            "net_profit": 100 if config["strategy"].get("adx_min") == 18 else 1,
            "profit_factor": 2.0 if config["strategy"].get("adx_min") == 18 else 1.0,
            "max_drawdown_pct": 1,
            "win_rate": 50,
            "total_trades": 10,
            "expectancy": 1,
        }

    monkeypatch.setattr(cd, "run_backtest_on_df", fake_backtest)
    _, selected = select_v7_combo_in_sample_only(sample_df(100), base_config())
    assert all(length == 60 for length in seen_lengths)
    assert "V5A_ADX_18" in selected

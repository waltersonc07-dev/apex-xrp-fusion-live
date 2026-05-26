from copy import deepcopy

import pandas as pd

from src.core_diagnostic import (
    LEADERBOARD_COLUMNS,
    _validate_variant,
    build_v7_combo,
    run_core_diagnostic,
    split_in_sample_oos,
    variant_configs,
    write_core_diagnostic_csv,
    write_core_diagnostic_report,
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


def sample_df(rows=100):
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


def fake_metrics(side_mode="both", trades=20, pf=1.2, wr=45, dd=5, net=100):
    sides = []
    if side_mode == "long":
        sides = ["long"] * trades
    elif side_mode == "short":
        sides = ["short"] * trades
    else:
        sides = ["long" if i % 2 == 0 else "short" for i in range(trades)]
    trade_rows = []
    for i, side in enumerate(sides):
        win = i < int(trades * wr / 100)
        trade_rows.append(
            {
                "side": side,
                "net_pnl": 10 if win else -5,
                "realized_r_multiple": 1.0 if win else -1.0,
                "planned_rr_at_entry": 2.0,
                "exit_reason": "take_profit" if win else "stop_loss",
            }
        )
    return {
        "net_profit": net,
        "profit_factor": pf,
        "max_drawdown_pct": dd,
        "win_rate": wr,
        "total_trades": trades,
        "expectancy": net / max(trades, 1),
        "average_realized_r": 0.2,
        "average_planned_rr": 2.0,
        "stop_loss_exits": max(1, trades - int(trades * wr / 100)),
        "take_profit_exits": int(trades * wr / 100),
        "flip_exits": 0,
        "trades": trade_rows,
    }


def test_v0_baseline_runs_trade_count_positive(monkeypatch):
    import src.core_diagnostic as cd

    monkeypatch.setattr(cd, "run_backtest_on_df", lambda *args, **kwargs: fake_metrics(trades=30))
    result = run_core_diagnostic(sample_df(), base_config())
    v0 = next(row for row in result["rows"] if row["variant_name"] == "V0_BASELINE_BOTH")
    assert v0["trades"] > 0


def test_v1_all_trades_long_only(monkeypatch):
    import src.core_diagnostic as cd

    def fake_backtest(df, config, *args, **kwargs):
        side = "long" if not config["strategy"].get("trade_shorts", True) else "both"
        return fake_metrics(side_mode=side)

    monkeypatch.setattr(cd, "run_backtest_on_df", fake_backtest)
    result = run_core_diagnostic(sample_df(), base_config())
    v1 = next(row for row in result["rows"] if row["variant_name"] == "V1_LONG_ONLY")
    assert v1["long_trades"] > 0
    assert v1["short_trades"] == 0


def test_v2_all_trades_short_only(monkeypatch):
    import src.core_diagnostic as cd

    def fake_backtest(df, config, *args, **kwargs):
        side = "short" if not config["strategy"].get("trade_longs", True) else "both"
        return fake_metrics(side_mode=side)

    monkeypatch.setattr(cd, "run_backtest_on_df", fake_backtest)
    result = run_core_diagnostic(sample_df(), base_config())
    v2 = next(row for row in result["rows"] if row["variant_name"] == "V2_SHORT_ONLY")
    assert v2["short_trades"] > 0
    assert v2["long_trades"] == 0


def test_filter_variants_trade_counts_differ(monkeypatch):
    import src.core_diagnostic as cd

    def fake_backtest(df, config, *args, **kwargs):
        if config["strategy"].get("use_4h_dema_slope"):
            return fake_metrics(trades=18)
        if config["strategy"].get("use_pullback_location"):
            return fake_metrics(trades=12)
        if config["strategy"].get("adx_min") == 18:
            return fake_metrics(trades=16)
        if config["strategy"].get("adx_min") == 20:
            return fake_metrics(trades=10)
        return fake_metrics(trades=20)

    monkeypatch.setattr(cd, "run_backtest_on_df", fake_backtest)
    result = run_core_diagnostic(sample_df(), base_config())
    rows = {row["variant_name"]: row for row in result["rows"]}
    assert rows["V3_4H_TREND_FILTER"]["trades"] != rows["V0_BASELINE_BOTH"]["trades"]
    assert rows["V4_PULLBACK_LOCATION"]["trades"] != rows["V0_BASELINE_BOTH"]["trades"]
    assert rows["V5A_ADX_18"]["trades"] != rows["V0_BASELINE_BOTH"]["trades"]
    assert rows["V5B_ADX_20"]["trades"] <= rows["V5A_ADX_18"]["trades"]


def test_v6_rsi_filter_signal_rows_have_correct_momentum():
    cfg = base_config()
    cfg["strategy"].update({"use_rsi_momentum": True, "rsi_length": 3})
    out = generate_signals(sample_df(80), cfg)
    long_rows = out[out["long_signal"]]
    short_rows = out[out["short_signal"]]
    assert (long_rows["rsi"] > 50).all()
    assert (short_rows["rsi"] < 50).all()


def test_v7_combo_does_not_mutate_baseline_config(monkeypatch):
    import src.core_diagnostic as cd

    cfg = base_config()
    original = deepcopy(cfg)
    in_sample_metrics = {name: fake_metrics(pf=1.0 + i / 10, trades=200) for i, name in enumerate(variant_configs(cfg))}
    monkeypatch.setattr(cd, "run_backtest_on_df", lambda *args, **kwargs: fake_metrics(trades=200, pf=2.0))
    build_v7_combo(sample_df(), cfg, in_sample_metrics)
    assert cfg == original


def test_no_variant_has_impossible_metrics(monkeypatch):
    import src.core_diagnostic as cd

    monkeypatch.setattr(cd, "run_backtest_on_df", lambda *args, **kwargs: fake_metrics(pf=1.2, wr=55, dd=4))
    result = run_core_diagnostic(sample_df(), base_config())
    for row in result["rows"]:
        assert row["profit_factor"] != float("inf")
        assert row["win_rate"] != 100
        assert row["max_drawdown_pct"] != 0.0


def test_micro_live_not_recommended_unless_all_gates_pass():
    failing, mode, _ = _validate_variant(fake_metrics(pf=1.49, trades=200), fake_metrics(pf=1.3), fake_metrics(net=100))
    passing, pass_mode, _ = _validate_variant(fake_metrics(pf=1.6, wr=45, dd=5, net=500, trades=200), fake_metrics(pf=1.3), fake_metrics(net=100))
    assert failing == "BLOCK_LIVE"
    assert mode == "BACKTEST_ONLY"
    assert passing == "PASS_MICRO_LIVE"
    assert pass_mode == "MICRO_LIVE"


def test_leaderboard_csv_created_with_correct_columns(tmp_path, monkeypatch):
    import src.core_diagnostic as cd

    monkeypatch.setattr(cd, "run_backtest_on_df", lambda *args, **kwargs: fake_metrics())
    result = run_core_diagnostic(sample_df(), base_config())
    path = tmp_path / "leaderboard.csv"
    write_core_diagnostic_csv(result, path)
    df = pd.read_csv(path)
    assert list(df.columns) == LEADERBOARD_COLUMNS


def test_report_markdown_created_and_not_empty(tmp_path, monkeypatch):
    import src.core_diagnostic as cd

    monkeypatch.setattr(cd, "run_backtest_on_df", lambda *args, **kwargs: fake_metrics())
    result = run_core_diagnostic(sample_df(), base_config())
    path = tmp_path / "report.md"
    write_core_diagnostic_report(result, path)
    assert path.exists()
    assert path.read_text(encoding="utf-8").strip()


def test_oos_period_uses_last_twenty_percent():
    df = sample_df(100)
    in_sample, oos = split_in_sample_oos(df, 0.20)
    assert len(in_sample) == 80
    assert len(oos) == 20
    assert oos.index[0] == df.index[80]

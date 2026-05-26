from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

import pandas as pd

from .backtest import load_config, run_backtest_on_df
from .data_loader import load_ohlcv_csv


VARIANT_ROWS = [
    "V0_BASELINE_BOTH",
    "V1_LONG_ONLY",
    "V2_SHORT_ONLY",
    "V3_4H_TREND_FILTER",
    "V4_PULLBACK_LOCATION",
    "V5A_ADX_18",
    "V5B_ADX_20",
    "V6_RSI_MOMENTUM",
    "V7_COMBO_MINIMAL",
]
VARIANT_FAMILIES = 8


def _strategy_patch(config: dict, **values) -> dict:
    patched = deepcopy(config)
    patched["strategy"].update(values)
    return patched


def variant_configs(base_config: dict) -> dict[str, dict]:
    return {
        "V0_BASELINE_BOTH": _strategy_patch(base_config, trade_longs=True, trade_shorts=True),
        "V1_LONG_ONLY": _strategy_patch(base_config, trade_longs=True, trade_shorts=False),
        "V2_SHORT_ONLY": _strategy_patch(base_config, trade_longs=False, trade_shorts=True),
        "V3_4H_TREND_FILTER": _strategy_patch(base_config, use_4h_dema_slope=True),
        "V4_PULLBACK_LOCATION": _strategy_patch(base_config, use_pullback_location=True),
        "V5A_ADX_18": _strategy_patch(base_config, adx_min=18),
        "V5B_ADX_20": _strategy_patch(base_config, adx_min=20),
        "V6_RSI_MOMENTUM": _strategy_patch(base_config, use_rsi_momentum=True),
    }


def _score(metrics: dict) -> tuple[float, float, float]:
    return (
        float(metrics.get("profit_factor", 0.0)),
        float(metrics.get("net_profit", 0.0)),
        -float(metrics.get("max_drawdown_pct", 0.0)),
    )


def _split_in_sample(df: pd.DataFrame, train_fraction: float = 0.60) -> pd.DataFrame:
    split = max(1, int(len(df) * train_fraction))
    return df.iloc[:split].copy()


def select_v7_combo_in_sample_only(df: pd.DataFrame, base_config: dict, base_fee_bps: float = 5, base_slippage_bps: float = 2) -> tuple[dict, list[str]]:
    in_sample = _split_in_sample(df)
    candidates = [
        ("V3_4H_TREND_FILTER", {"use_4h_dema_slope": True}),
        ("V4_PULLBACK_LOCATION", {"use_pullback_location": True}),
        ("V5A_ADX_18", {"adx_min": 18}),
        ("V5B_ADX_20", {"adx_min": 20}),
        ("V6_RSI_MOMENTUM", {"use_rsi_momentum": True}),
    ]
    selected: dict = {}
    selected_names: list[str] = []
    current_metrics = run_backtest_on_df(in_sample, _strategy_patch(base_config), base_fee_bps, base_slippage_bps, save_trades_path=None)
    current_score = _score(current_metrics)

    for name, patch in candidates:
        test_patch = {**selected, **patch}
        test_config = _strategy_patch(base_config, **test_patch)
        metrics = run_backtest_on_df(in_sample, test_config, base_fee_bps, base_slippage_bps, save_trades_path=None)
        if _score(metrics) > current_score:
            selected.update(patch)
            selected_names.append(name)
            current_score = _score(metrics)

    return _strategy_patch(base_config, **selected), selected_names


def _row(name: str, metrics: dict, stress_metrics: dict | None = None, selected_filters: list[str] | None = None) -> dict:
    return {
        "variant": name,
        "net_profit": metrics.get("net_profit", 0.0),
        "profit_factor": metrics.get("profit_factor", 0.0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
        "win_rate": metrics.get("win_rate", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        "expectancy": metrics.get("expectancy", 0.0),
        "double_cost_net_profit": (stress_metrics or {}).get("net_profit", 0.0),
        "double_cost_profit_factor": (stress_metrics or {}).get("profit_factor", 0.0),
        "selected_filters": ",".join(selected_filters or []),
    }


def run_core_diagnostic(df: pd.DataFrame, config: dict, base_fee_bps: float = 5, base_slippage_bps: float = 2) -> dict:
    configs = variant_configs(config)
    v7_config, selected_filters = select_v7_combo_in_sample_only(df, config, base_fee_bps, base_slippage_bps)
    configs["V7_COMBO_MINIMAL"] = v7_config

    rows: list[dict] = []
    for name in VARIANT_ROWS:
        metrics = run_backtest_on_df(df, configs[name], base_fee_bps, base_slippage_bps, save_trades_path=None)
        double_cost_metrics = run_backtest_on_df(df, configs[name], base_fee_bps * 2, base_slippage_bps * 2, save_trades_path=None)
        rows.append(_row(name, metrics, double_cost_metrics, selected_filters if name == "V7_COMBO_MINIMAL" else None))

    leaderboard = sorted(rows, key=lambda item: (item["profit_factor"], item["net_profit"]), reverse=True)
    return {
        "variant_rows_tested": len(rows),
        "variant_families": VARIANT_FAMILIES,
        "rows": rows,
        "leaderboard": leaderboard,
        "v7_selected_filters": selected_filters,
    }


def write_core_diagnostic_report(result: dict, path: str | Path = "reports/core_diagnostic_report.md") -> None:
    lines = [
        "# Core Diagnostic Report",
        "",
        f"VARIANT ROWS TESTED: {result['variant_rows_tested']}",
        f"VARIANT FAMILIES: {result['variant_families']}",
        "",
        "V7 selection rule: filters are selected using in-sample results only; OOS is reserved for final validation after the combo is fixed.",
        "Stress rule: double-cost metrics double both commission and slippage.",
        "",
        "| Rank | Variant | Net Profit | Profit Factor | Max DD % | Win Rate % | Trades | Double-Cost Net | Double-Cost PF | Selected Filters |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rank, row in enumerate(result["leaderboard"], start=1):
        lines.append(
            f"| {rank} | {row['variant']} | {row['net_profit']:.2f} | {row['profit_factor']:.3f} | "
            f"{row['max_drawdown_pct']:.2f} | {row['win_rate']:.2f} | {row['total_trades']} | "
            f"{row['double_cost_net_profit']:.2f} | {row['double_cost_profit_factor']:.3f} | {row['selected_filters']} |"
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CSV with timestamp, open, high, low, close, volume")
    args = parser.parse_args()
    df = load_ohlcv_csv(args.csv)
    config = load_config()
    result = run_core_diagnostic(df, config)
    write_core_diagnostic_report(result)
    print(f"VARIANT ROWS TESTED: {result['variant_rows_tested']}")
    print(f"VARIANT FAMILIES: {result['variant_families']}")
    print("LEADERBOARD:")
    for rank, row in enumerate(result["leaderboard"], start=1):
        print(
            f"{rank}. {row['variant']} PF={row['profit_factor']:.3f} "
            f"NET={row['net_profit']:.2f} DD={row['max_drawdown_pct']:.2f}% "
            f"TRADES={row['total_trades']} DOUBLE_COST_PF={row['double_cost_profit_factor']:.3f}"
        )
    print("REPORT: reports/core_diagnostic_report.md")


if __name__ == "__main__":
    main()

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path

import pandas as pd

from .backtest import run_backtest_on_df


def _with_strategy_value(config: dict, key: str, value) -> dict:
    new_config = deepcopy(config)
    new_config["strategy"][key] = value
    return new_config


def run_stress_tests(df: pd.DataFrame, config: dict, base_fee_bps: float = 5, base_slippage_bps: float = 2) -> dict:
    stress_cfg = config["stress_test"]
    summary = {
        "normal": run_backtest_on_df(df, config, base_fee_bps, base_slippage_bps, save_trades_path=None),
        "doubled_fees": run_backtest_on_df(df, config, base_fee_bps * 2, base_slippage_bps, save_trades_path=None),
        "slippage_2x": run_backtest_on_df(df, config, base_fee_bps, base_slippage_bps * 2, save_trades_path=None),
        "slippage_3x": run_backtest_on_df(df, config, base_fee_bps, base_slippage_bps * 3, save_trades_path=None),
        "delayed_entry_1": run_backtest_on_df(df, config, base_fee_bps, base_slippage_bps, entry_delay_candles=1, save_trades_path=None),
        "delayed_entry_2": run_backtest_on_df(df, config, base_fee_bps, base_slippage_bps, entry_delay_candles=2, save_trades_path=None),
        "parameter_tests": [],
    }

    for mult in stress_cfg["supertrend_multipliers"]:
        test_config = _with_strategy_value(config, "supertrend_multiplier", mult)
        result = run_backtest_on_df(df, test_config, base_fee_bps, base_slippage_bps, save_trades_path=None)
        summary["parameter_tests"].append({"parameter": "supertrend_multiplier", "value": mult, "metrics": result})
    for mult in stress_cfg["stop_atr_multipliers"]:
        test_config = _with_strategy_value(config, "stop_atr_mult", mult)
        result = run_backtest_on_df(df, test_config, base_fee_bps, base_slippage_bps, save_trades_path=None)
        summary["parameter_tests"].append({"parameter": "stop_atr_mult", "value": mult, "metrics": result})
    for fast, slow in [(8, 21), (9, 21), (10, 24)]:
        test_config = _with_strategy_value(_with_strategy_value(config, "ema_fast", fast), "ema_slow", slow)
        result = run_backtest_on_df(df, test_config, base_fee_bps, base_slippage_bps, save_trades_path=None)
        summary["parameter_tests"].append({"parameter": "ema_pair", "value": f"{fast}/{slow}", "metrics": result})

    summary["doubled_fees_profitable"] = summary["doubled_fees"]["net_profit"] > 0
    summary["increased_slippage_profitable"] = summary["slippage_2x"]["net_profit"] > 0 and summary["slippage_3x"]["net_profit"] > 0
    profitable_params = [item for item in summary["parameter_tests"] if item["metrics"]["net_profit"] > 0 and item["metrics"]["profit_factor"] >= 1.20]
    summary["parameter_robustness_acceptable"] = len(profitable_params) >= max(1, int(len(summary["parameter_tests"]) * 0.60))
    scenario_metrics = [summary[key] for key in ["normal", "doubled_fees", "slippage_2x", "slippage_3x", "delayed_entry_1", "delayed_entry_2"]]
    scenario_metrics.extend(item["metrics"] for item in summary["parameter_tests"])
    summary["impossible_values"] = any(
        metrics.get("total_trades", 0) >= 100
        and (metrics.get("win_rate", 0) >= 99 or math.isinf(metrics.get("profit_factor", 0)))
        for metrics in scenario_metrics
    )
    summary["parameter_engine_failure"] = any(
        item["metrics"].get("total_trades", 0) > 0
        and item["metrics"].get("net_profit", 0) == 0
        and item["metrics"].get("profit_factor", 0) == 0
        for item in summary["parameter_tests"]
    )
    return summary


def write_stress_report(summary: dict, path: str | Path = "reports/stress_test_report.md") -> None:
    lines = ["# Stress Test Report", ""]
    for key in ["normal", "doubled_fees", "slippage_2x", "slippage_3x", "delayed_entry_1", "delayed_entry_2"]:
        metrics = summary[key]
        lines.extend([
            f"## {key}",
            f"- net_profit: {metrics['net_profit']}",
            f"- profit_factor: {metrics['profit_factor']}",
            f"- max_drawdown_pct: {metrics['max_drawdown_pct']}",
            f"- total_trades: {metrics['total_trades']}",
            "",
        ])
    lines.append("## Parameter Tests")
    for item in summary["parameter_tests"]:
        metrics = item["metrics"]
        lines.append(f"- {item['parameter']}={item['value']}: net_profit={metrics['net_profit']}, profit_factor={metrics['profit_factor']}")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")

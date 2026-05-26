from __future__ import annotations

from pathlib import Path

import pandas as pd

from .backtest import run_backtest_on_df


def split_walk_forward(df: pd.DataFrame, train_pct: float = 0.60, validation_pct: float = 0.20) -> dict[str, pd.DataFrame]:
    n = len(df)
    train_end = int(n * train_pct)
    validation_end = int(n * (train_pct + validation_pct))
    return {
        "in_sample": df.iloc[:train_end].copy(),
        "recent_validation": df.iloc[train_end:validation_end].copy(),
        "out_of_sample": df.iloc[validation_end:].copy(),
    }


def run_walk_forward(df: pd.DataFrame, config: dict) -> dict:
    splits = split_walk_forward(df)
    results = {}
    for name, split_df in splits.items():
        results[name] = run_backtest_on_df(split_df, config, save_trades_path=None)

    passed = (
        results["in_sample"]["net_profit"] > 0
        and results["recent_validation"]["net_profit"] > 0
        and results["out_of_sample"]["net_profit"] > 0
        and results["out_of_sample"]["profit_factor"] >= config["validation"]["min_oos_profit_factor"]
    )
    return {"passed": passed, "splits": results}


def write_walk_forward_report(result: dict, path: str | Path = "reports/walk_forward_report.md") -> None:
    lines = ["# Walk-Forward Report", "", f"- passed: {result['passed']}", ""]
    for name, metrics in result["splits"].items():
        lines.extend([
            f"## {name}",
            f"- net_profit: {metrics['net_profit']}",
            f"- profit_factor: {metrics['profit_factor']}",
            f"- max_drawdown_pct: {metrics['max_drawdown_pct']}",
            f"- total_trades: {metrics['total_trades']}",
            f"- expectancy: {metrics['expectancy']}",
            "",
        ])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


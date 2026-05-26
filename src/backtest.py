from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .backtest_engine import run_realistic_backtest
from .data_loader import load_ohlcv_csv


def load_config(path: str | Path = "config/settings.yaml") -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def run_backtest_on_df(
    df,
    config: dict,
    fee_bps: float = 5,
    slippage_bps: float = 2,
    entry_delay_candles: int = 1,
    initial_equity: float = 10000.0,
    save_trades_path: str | Path | None = "journals/backtest_trades.csv",
) -> dict:
    _ = initial_equity
    return run_realistic_backtest(df, config, fee_bps=fee_bps, slippage_bps=slippage_bps, entry_delay_candles=entry_delay_candles, save_trades_path=save_trades_path)


def run_backtest(csv_path: str | Path, config: dict, fee_bps: float = 5, slippage_bps: float = 2) -> dict:
    df = load_ohlcv_csv(csv_path)
    return run_backtest_on_df(df, config, fee_bps=fee_bps, slippage_bps=slippage_bps)


def write_report(report: dict, path: str | Path = "reports/backtest_report.md") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    lines = ["# APEX XRP Fusion Live Backtest Report", ""]
    for key, value in report.items():
        if key == "trades":
            continue
        lines.append(f"- {key}: {value}")
    lines.extend(["", "Stress tests to run before micro live: doubled fees, increased slippage, and parameter perturbation."])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CSV with timestamp, open, high, low, close, volume")
    args = parser.parse_args()
    config = load_config()
    report = run_backtest(args.csv, config)
    write_report(report)
    print(report)


if __name__ == "__main__":
    main()

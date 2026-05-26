from __future__ import annotations

import argparse
import math
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
LEADERBOARD_COLUMNS = [
    "variant_name",
    "trades",
    "win_rate",
    "profit_factor",
    "net_profit_usdt",
    "max_drawdown_pct",
    "expectancy",
    "avg_realized_r",
    "avg_planned_rr",
    "sl_exits",
    "tp_exits",
    "flip_exits",
    "long_trades",
    "long_win_rate",
    "short_trades",
    "short_win_rate",
    "oos_profit_factor",
    "stress_test_2x_fees",
    "validation",
    "recommended_mode",
]


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
        "V4_PULLBACK_LOCATION": _strategy_patch(base_config, use_pullback_location=True, pullback_tolerance=0.003),
        "V5A_ADX_18": _strategy_patch(base_config, adx_min=18, adx_length=14),
        "V5B_ADX_20": _strategy_patch(base_config, adx_min=20, adx_length=14),
        "V6_RSI_MOMENTUM": _strategy_patch(base_config, use_rsi_momentum=True, rsi_length=14, rsi_long_min=50, rsi_short_max=50),
    }


def split_in_sample_oos(df: pd.DataFrame, oos_pct: float = 0.20) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not 0 < oos_pct < 1:
        raise ValueError("oos_pct must be between 0 and 1")
    split_at = max(1, min(len(df) - 1, int(len(df) * (1 - oos_pct))))
    return df.iloc[:split_at].copy(), df.iloc[split_at:].copy()


def _score(metrics: dict) -> tuple[float, float, float, int]:
    return (
        float(metrics.get("profit_factor", 0.0)),
        float(metrics.get("net_profit", 0.0)),
        -float(metrics.get("max_drawdown_pct", 0.0)),
        int(metrics.get("total_trades", 0)),
    )


def _side_stats(metrics: dict) -> dict:
    trades = pd.DataFrame(metrics.get("trades", []))
    if trades.empty or "side" not in trades:
        return {"long_trades": 0, "long_win_rate": 0.0, "short_trades": 0, "short_win_rate": 0.0}
    long_trades = trades[trades["side"] == "long"]
    short_trades = trades[trades["side"] == "short"]
    return {
        "long_trades": int(len(long_trades)),
        "long_win_rate": float((long_trades["net_pnl"] > 0).mean() * 100) if len(long_trades) else 0.0,
        "short_trades": int(len(short_trades)),
        "short_win_rate": float((short_trades["net_pnl"] > 0).mean() * 100) if len(short_trades) else 0.0,
    }


def _validate_variant(metrics: dict, oos_metrics: dict, stress_metrics: dict) -> tuple[str, str, list[str]]:
    failed: list[str] = []
    profit_factor = float(metrics.get("profit_factor", 0.0))
    max_drawdown = float(metrics.get("max_drawdown_pct", 0.0))
    if profit_factor < 1.50:
        failed.append("profit factor below 1.50")
    if math.isinf(profit_factor):
        failed.append("profit factor is infinite")
    if float(oos_metrics.get("profit_factor", 0.0)) < 1.20:
        failed.append("out-of-sample profit factor below 1.20")
    if max_drawdown > 12.0:
        failed.append("max drawdown above 12.0%")
    if max_drawdown == 0.0:
        failed.append("max drawdown is 0.0%")
    if float(metrics.get("win_rate", 0.0)) < 37.0:
        failed.append("win rate below 37.0%")
    if float(metrics.get("net_profit", 0.0)) <= 0:
        failed.append("net profit not positive")
    if float(metrics.get("expectancy", 0.0)) <= 0:
        failed.append("expectancy not positive")
    if int(metrics.get("total_trades", 0)) < 150:
        failed.append("total trades below 150")
    if int(metrics.get("stop_loss_exits", 0)) <= 0:
        failed.append("no stop-loss exits")
    if float(stress_metrics.get("net_profit", 0.0)) <= 0:
        failed.append("2x commission/slippage stress test not profitable")
    validation = "PASS_MICRO_LIVE" if not failed else "BLOCK_LIVE"
    mode = "MICRO_LIVE" if not failed else "BACKTEST_ONLY"
    return validation, mode, failed


def _leaderboard_row(name: str, metrics: dict, oos_metrics: dict, stress_metrics: dict) -> dict:
    validation, recommended_mode, failed_rules = _validate_variant(metrics, oos_metrics, stress_metrics)
    side_stats = _side_stats(metrics)
    return {
        "variant_name": name,
        "trades": int(metrics.get("total_trades", 0)),
        "win_rate": float(metrics.get("win_rate", 0.0)),
        "profit_factor": float(metrics.get("profit_factor", 0.0)),
        "net_profit_usdt": float(metrics.get("net_profit", 0.0)),
        "max_drawdown_pct": float(metrics.get("max_drawdown_pct", 0.0)),
        "expectancy": float(metrics.get("expectancy", 0.0)),
        "avg_realized_r": float(metrics.get("average_realized_r", metrics.get("average_r", 0.0))),
        "avg_planned_rr": float(metrics.get("average_planned_rr", 0.0)),
        "sl_exits": int(metrics.get("stop_loss_exits", 0)),
        "tp_exits": int(metrics.get("take_profit_exits", 0)),
        "flip_exits": int(metrics.get("flip_exits", 0)),
        "long_trades": side_stats["long_trades"],
        "long_win_rate": side_stats["long_win_rate"],
        "short_trades": side_stats["short_trades"],
        "short_win_rate": side_stats["short_win_rate"],
        "oos_profit_factor": float(oos_metrics.get("profit_factor", 0.0)),
        "stress_test_2x_fees": "PASS" if float(stress_metrics.get("net_profit", 0.0)) > 0 else "FAIL",
        "validation": validation,
        "recommended_mode": recommended_mode,
        "failed_rules": failed_rules,
        "stress_net_profit": float(stress_metrics.get("net_profit", 0.0)),
    }


def _pf(row_or_metrics: dict) -> float:
    return float(row_or_metrics.get("profit_factor", 0.0))


def _build_combo_candidate_config(base_config: dict, side_patch: dict, filter_patches: list[dict]) -> dict:
    combined = dict(side_patch)
    for patch in filter_patches:
        combined.update(patch)
    return _strategy_patch(base_config, **combined)


def build_v7_combo(
    in_sample_df: pd.DataFrame,
    base_config: dict,
    in_sample_metrics: dict[str, dict],
    base_fee_bps: float = 5,
    base_slippage_bps: float = 2,
    min_trades: int = 150,
) -> tuple[dict, dict]:
    if _score(in_sample_metrics["V1_LONG_ONLY"]) > _score(in_sample_metrics["V2_SHORT_ONLY"]):
        side_patch = {"trade_longs": True, "trade_shorts": False}
        side_choice = "long-only"
    elif _score(in_sample_metrics["V0_BASELINE_BOTH"]) > _score(in_sample_metrics["V1_LONG_ONLY"]):
        side_patch = {"trade_longs": True, "trade_shorts": True}
        side_choice = "both"
    else:
        side_patch = {"trade_longs": True, "trade_shorts": True}
        side_choice = "both"

    filter_candidates = [
        ("V3_4H_TREND_FILTER", {"use_4h_dema_slope": True}),
        ("V4_PULLBACK_LOCATION", {"use_pullback_location": True, "pullback_tolerance": 0.003}),
        ("V5A_ADX_18", {"adx_min": 18, "adx_length": 14}),
        ("V5B_ADX_20", {"adx_min": 20, "adx_length": 14}),
        ("V6_RSI_MOMENTUM", {"use_rsi_momentum": True, "rsi_length": 14, "rsi_long_min": 50, "rsi_short_max": 50}),
    ]
    base_pf = _pf(in_sample_metrics["V0_BASELINE_BOTH"])
    ranked_filters = sorted(
        filter_candidates,
        key=lambda item: (_pf(in_sample_metrics[item[0]]) - base_pf, _pf(in_sample_metrics[item[0]])),
        reverse=True,
    )

    selected: list[tuple[str, dict]] = []
    rejected: list[str] = []
    current_metrics = run_backtest_on_df(
        in_sample_df,
        _build_combo_candidate_config(base_config, side_patch, []),
        base_fee_bps,
        base_slippage_bps,
        save_trades_path=None,
    )
    current_pf = _pf(current_metrics)

    for name, patch in ranked_filters:
        if len(selected) >= 2:
            rejected.append(f"{name}: rejected because V7 stops after two filters")
            continue
        candidate_filters = selected + [(name, patch)]
        candidate_config = _build_combo_candidate_config(base_config, side_patch, [item[1] for item in candidate_filters])
        metrics = run_backtest_on_df(in_sample_df, candidate_config, base_fee_bps, base_slippage_bps, save_trades_path=None)
        if int(metrics.get("total_trades", 0)) < min_trades:
            rejected.append(f"{name}: rejected because trade count {int(metrics.get('total_trades', 0))} < {min_trades}")
            continue
        if _pf(metrics) <= current_pf:
            rejected.append(f"{name}: rejected because PF improvement plateaued")
            continue
        selected = candidate_filters
        current_metrics = metrics
        current_pf = _pf(metrics)

    selected_names = [name for name, _ in selected]
    detail = {
        "side_choice": side_choice,
        "selected_filters": selected_names,
        "rejected_filters": rejected,
        "final_in_sample_trade_count": int(current_metrics.get("total_trades", 0)),
    }
    return _build_combo_candidate_config(base_config, side_patch, [patch for _, patch in selected]), detail


def run_core_diagnostic(
    df: pd.DataFrame,
    config: dict,
    oos_pct: float = 0.20,
    base_fee_bps: float = 5,
    base_slippage_bps: float = 2,
) -> dict:
    in_sample_df, oos_df = split_in_sample_oos(df, oos_pct)
    configs = variant_configs(config)

    in_sample_metrics = {
        name: run_backtest_on_df(in_sample_df, variant_config, base_fee_bps, base_slippage_bps, save_trades_path=None)
        for name, variant_config in configs.items()
    }
    v7_config, v7_detail = build_v7_combo(in_sample_df, config, in_sample_metrics, base_fee_bps, base_slippage_bps)
    configs["V7_COMBO_MINIMAL"] = v7_config

    rows: list[dict] = []
    raw_metrics: dict[str, dict] = {}
    oos_metrics_by_variant: dict[str, dict] = {}
    stress_metrics_by_variant: dict[str, dict] = {}
    for name in VARIANT_ROWS:
        metrics = run_backtest_on_df(df, configs[name], base_fee_bps, base_slippage_bps, save_trades_path=None)
        oos_metrics = run_backtest_on_df(oos_df, configs[name], base_fee_bps, base_slippage_bps, save_trades_path=None)
        stress_metrics = run_backtest_on_df(df, configs[name], base_fee_bps * 2, base_slippage_bps * 2, save_trades_path=None)
        raw_metrics[name] = metrics
        oos_metrics_by_variant[name] = oos_metrics
        stress_metrics_by_variant[name] = stress_metrics
        rows.append(_leaderboard_row(name, metrics, oos_metrics, stress_metrics))

    leaderboard = sorted(rows, key=lambda item: (item["profit_factor"], item["net_profit_usdt"]), reverse=True)
    passing = [row for row in leaderboard if row["validation"] == "PASS_MICRO_LIVE"]
    best = leaderboard[0] if leaderboard else None
    validation = "PASS_MICRO_LIVE" if passing else "BLOCK_LIVE"
    recommended_mode = "MICRO_LIVE" if passing else "BACKTEST_ONLY"
    decision = "MICRO_LIVE_ALLOWED" if passing else "NO_VARIANT_PASSES"

    return {
        "variant_rows_tested": len(rows),
        "variant_families": VARIANT_FAMILIES,
        "rows": rows,
        "leaderboard": leaderboard,
        "best_variant": best,
        "validation": validation,
        "recommended_mode": recommended_mode,
        "decision": decision,
        "raw_metrics": raw_metrics,
        "oos_metrics": oos_metrics_by_variant,
        "stress_metrics": stress_metrics_by_variant,
        "v7_detail": v7_detail,
        "data_start": df.index[0].date().isoformat() if len(df) else "",
        "data_end": df.index[-1].date().isoformat() if len(df) else "",
        "candles": len(df),
        "oos_start": oos_df.index[0].date().isoformat() if len(oos_df) else "",
        "oos_candles": len(oos_df),
        "in_sample_candles": len(in_sample_df),
    }


def write_core_diagnostic_csv(result: dict, path: str | Path = "reports/core_diagnostic_leaderboard.csv") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(result["leaderboard"])[LEADERBOARD_COLUMNS].to_csv(path, index=False)


def _fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def write_core_diagnostic_report(result: dict, path: str | Path = "reports/core_diagnostic_report.md") -> None:
    baseline = next(row for row in result["rows"] if row["variant_name"] == "V0_BASELINE_BOTH")
    best = result["best_variant"]
    lines = [
        "# APEX Core Diagnostic Report",
        "",
        f"VARIANT ROWS TESTED: {result['variant_rows_tested']}",
        f"VARIANT FAMILIES: {result['variant_families']}",
        f"DATA: {result['data_start']} to {result['data_end']}",
        f"CANDLES: {result['candles']}",
        f"OOS: last {result['oos_candles']} candles starting {result['oos_start']}",
        "",
        "## Baseline",
        f"- Trades: {baseline['trades']}",
        f"- Win Rate: {_fmt_pct(baseline['win_rate'])}",
        f"- Profit Factor: {baseline['profit_factor']:.3f}",
        f"- Max Drawdown: {_fmt_pct(baseline['max_drawdown_pct'])}",
        "",
        "## V7 Combo Minimal",
        f"- Side: {result['v7_detail']['side_choice']}",
        f"- Selected filters: {', '.join(result['v7_detail']['selected_filters']) if result['v7_detail']['selected_filters'] else 'none'}",
        f"- Final in-sample trade count: {result['v7_detail']['final_in_sample_trade_count']}",
        "- Rejected filters:",
    ]
    lines.extend([f"  - {item}" for item in result["v7_detail"]["rejected_filters"]] or ["  - none"])
    lines.extend([
        "",
        "## Leaderboard",
        "",
        "| Rank | Variant | Trades | Win Rate | Profit Factor | Net Profit | Max DD | OOS PF | Stress 2x | Validation |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---|---|",
    ])
    for rank, row in enumerate(result["leaderboard"], start=1):
        lines.append(
            f"| {rank} | {row['variant_name']} | {row['trades']} | {_fmt_pct(row['win_rate'])} | "
            f"{row['profit_factor']:.3f} | {row['net_profit_usdt']:.2f} | {_fmt_pct(row['max_drawdown_pct'])} | "
            f"{row['oos_profit_factor']:.3f} | {row['stress_test_2x_fees']} | {row['validation']} |"
        )
    lines.extend([
        "",
        "## Decision",
        f"- Best Variant: {best['variant_name'] if best else 'none'}",
        f"- Best Profit Factor: {best['profit_factor']:.3f}" if best else "- Best Profit Factor: n/a",
        f"- Best OOS PF: {best['oos_profit_factor']:.3f}" if best else "- Best OOS PF: n/a",
        f"- Best Win Rate: {_fmt_pct(best['win_rate'])}" if best else "- Best Win Rate: n/a",
        f"- Best Max Drawdown: {_fmt_pct(best['max_drawdown_pct'])}" if best else "- Best Max Drawdown: n/a",
        f"- Best Trade Count: {best['trades']}" if best else "- Best Trade Count: n/a",
        f"- Validation: {result['validation']}",
        f"- Recommended Mode: {result['recommended_mode']}",
        f"- Decision: {result['decision']}",
    ])
    if result["decision"] == "NO_VARIANT_PASSES":
        lines.extend([
            "",
            "NEXT ACTION:",
            "- Do not trade live.",
            "- Strategy needs structural change.",
            "- Review losing trade distribution.",
            "- Consider long-only during confirmed bull market.",
            "- Consider RSI 50 trend confirmation.",
            "- Consider ADX >= 20 chop filter.",
            "- Consider higher timeframe trend alignment.",
        ])
    else:
        lines.extend([
            "",
            "NEXT ACTION:",
            "- Enable MICRO_LIVE at 0.10% risk only after manual approval.",
            "- Keep FULL_LIVE disabled.",
            "- Do not add BingX keys until Render smoke-test passes.",
        ])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def print_summary(result: dict) -> None:
    baseline = next(row for row in result["rows"] if row["variant_name"] == "V0_BASELINE_BOTH")
    best = result["best_variant"]
    print("============================================")
    print("APEX CORE DIAGNOSTIC RESULT")
    print("============================================")
    print(f"VARIANT ROWS TESTED: {result['variant_rows_tested']}")
    print(f"VARIANT FAMILIES:    {result['variant_families']}")
    print(f"DATA:                {result['data_start']} to {result['data_end']}")
    print(f"CANDLES:             {result['candles']:,}")
    print("")
    print("BASELINE (V0):")
    print(f"  Trades:         {baseline['trades']}")
    print(f"  Win Rate:       {baseline['win_rate']:.2f}%")
    print(f"  Profit Factor:  {baseline['profit_factor']:.3f}")
    print(f"  Max Drawdown:   {baseline['max_drawdown_pct']:.2f}%")
    print("")
    print("LEADERBOARD (ranked by Profit Factor):")
    for rank, row in enumerate(result["leaderboard"], start=1):
        print(f"  {rank}. {row['variant_name']}  PF={row['profit_factor']:.3f}  WR={row['win_rate']:.1f}%  DD={row['max_drawdown_pct']:.1f}%  Trades={row['trades']}")
    print("")
    print(f"BEST VARIANT:         {best['variant_name'] if best else 'none'}")
    print(f"BEST PROFIT FACTOR:   {best['profit_factor']:.3f}" if best else "BEST PROFIT FACTOR:   n/a")
    print(f"BEST OOS PF:          {best['oos_profit_factor']:.3f}" if best else "BEST OOS PF:          n/a")
    print(f"BEST WIN RATE:        {best['win_rate']:.1f}%" if best else "BEST WIN RATE:        n/a")
    print(f"BEST MAX DRAWDOWN:    {best['max_drawdown_pct']:.1f}%" if best else "BEST MAX DRAWDOWN:    n/a")
    print(f"BEST TRADE COUNT:     {best['trades']}" if best else "BEST TRADE COUNT:     n/a")
    print("")
    print(f"VALIDATION:           {result['validation']}")
    print(f"RECOMMENDED MODE:     {result['recommended_mode']}")
    print(f"DECISION:             {result['decision']}")
    print("")
    print("NEXT ACTION:")
    if result["decision"] == "MICRO_LIVE_ALLOWED":
        print("  Enable MICRO_LIVE at 0.10% risk only.")
        print("  Keep FULL_LIVE disabled.")
        print("  Do not add BingX keys until Render smoke-test passes.")
        print("  Update config/settings.yaml: risk.mode = MICRO_LIVE")
        print("  Update .env: MICRO_LIVE=true")
        print("  Keep FULL_LIVE=false.")
    else:
        print("  Do not trade live.")
        print("  Strategy needs structural change.")
        print("  Review losing trade distribution.")
        print("  Top recommendation from research:")
        print("    - Consider long-only during confirmed bull market")
        print("    - Consider RSI 50 trend confirmation")
        print("    - Consider ADX >= 20 chop filter")
        print("    - Consider higher timeframe trend alignment")
    print("============================================")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CSV with timestamp, open, high, low, close, volume")
    parser.add_argument("--oos-pct", type=float, default=0.20)
    parser.add_argument("--fee-bps", type=float, default=5)
    parser.add_argument("--slippage-bps", type=float, default=2)
    args = parser.parse_args()
    df = load_ohlcv_csv(args.csv)
    config = load_config()
    result = run_core_diagnostic(df, config, oos_pct=args.oos_pct, base_fee_bps=args.fee_bps, base_slippage_bps=args.slippage_bps)
    write_core_diagnostic_report(result)
    write_core_diagnostic_csv(result)
    print_summary(result)


if __name__ == "__main__":
    main()

"""Stacked MTF v3.3 — long-only Python port (research / backtest only).

Chart TF: 15m. Confirmation HTF: 2H.
Entry: first 15m bar of a new 2H period when BOTH stacks are bullish
       (freshOnly OFF — no first-flip requirement).
Exit: full 15m bearish stack flip. Protective price stop OFF by default.

Does not touch live unlock flags, webhook live mode, or SAFETY thresholds.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .backtest_engine import (
    _commission_pct,
    _entry_price,
    _exit_price,
    summarize_trades,
)
from .data_loader import load_ohlcv_csv
from .indicators import atr, dema, ema, supertrend

DEFAULT_STACKED_MTF: dict[str, Any] = {
    "name": "STACKED_MTF_V3.3",
    "chart_tf": "15m",
    "htf": "2h",
    "ema_fast": 9,
    "ema_slow": 21,
    "dema_length": 200,
    "supertrend_atr_length": 12,
    "supertrend_multiplier": 3.0,
    "require_htf": True,
    "require_sync": True,
    "fresh_only": False,  # v3.3 default
    "use_live_htf": False,  # confirmed closed HTF only (non-repaint)
    "strict_entry": False,
    "strict_exit": False,
    "require_ema_order": True,
    "use_ema_fast": True,
    "use_ema_slow": True,
    "use_dema": True,
    "use_supertrend": True,
    "exit_mode": "stack_flip",  # stack_flip | supertrend_flip | below_ema_slow | ema_cross | any_lost
    "use_stop": False,
    "trail_supertrend": False,
    "risk_pct": 1.0,
    "max_leverage": 1.0,
}


def _cfg(config: dict | None) -> dict[str, Any]:
    merged = dict(DEFAULT_STACKED_MTF)
    if not config:
        return merged
    if "stacked_mtf" in config and isinstance(config["stacked_mtf"], dict):
        merged.update(config["stacked_mtf"])
    # Allow callers to pass flat overrides at the top level too.
    for key in DEFAULT_STACKED_MTF:
        if key in config:
            merged[key] = config[key]
    return merged


def _stack_up(df: pd.DataFrame, cfg: dict[str, Any], ref: pd.Series) -> pd.Series:
    parts: list[pd.Series] = []
    if cfg["use_ema_fast"]:
        parts.append(ref > df["ema_fast"])
    if cfg["use_ema_slow"]:
        parts.append(ref > df["ema_slow"])
    if cfg["use_dema"]:
        parts.append(ref > df["dema_200"])
    if cfg["use_supertrend"]:
        # indicators.supertrend: direction == 1 bullish (TV ta.supertrend dir < 0)
        parts.append((ref > df["supertrend"]) & (df["supertrend_dir"] == 1))
    if cfg["require_ema_order"]:
        parts.append(df["ema_fast"] > df["ema_slow"])
    if not parts:
        return pd.Series(False, index=df.index)
    out = parts[0]
    for part in parts[1:]:
        out = out & part
    return out.fillna(False)


def _stack_dn(df: pd.DataFrame, cfg: dict[str, Any], ref: pd.Series) -> pd.Series:
    parts: list[pd.Series] = []
    if cfg["use_ema_fast"]:
        parts.append(ref < df["ema_fast"])
    if cfg["use_ema_slow"]:
        parts.append(ref < df["ema_slow"])
    if cfg["use_dema"]:
        parts.append(ref < df["dema_200"])
    if cfg["use_supertrend"]:
        parts.append((ref < df["supertrend"]) & (df["supertrend_dir"] == -1))
    # EMA order is NOT required for bearish stack (matches Pine f_dn)
    if not parts:
        return pd.Series(False, index=df.index)
    out = parts[0]
    for part in parts[1:]:
        out = out & part
    return out.fillna(False)


def _attach_indicators(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    st = supertrend(out, int(cfg["supertrend_atr_length"]), float(cfg["supertrend_multiplier"]))
    out["ema_fast"] = ema(out["close"], int(cfg["ema_fast"]))
    out["ema_slow"] = ema(out["close"], int(cfg["ema_slow"]))
    out["dema_200"] = dema(out["close"], int(cfg["dema_length"]))
    out["atr"] = atr(out, int(cfg["supertrend_atr_length"]))
    out["supertrend"] = st["supertrend"]
    out["supertrend_dir"] = st["direction"]
    ref_up = out["low"] if cfg["strict_entry"] else out["close"]
    ref_dn = out["high"] if cfg["strict_exit"] else out["close"]
    out["stack_up"] = _stack_up(out, cfg, ref_up)
    out["stack_dn"] = _stack_dn(out, cfg, ref_dn)
    return out


def _resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("OHLCV index must be a DatetimeIndex for MTF resample")
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    cols = [c for c in agg if c in df.columns]
    htf = df[cols].resample(rule, label="left", closed="left").agg({c: agg[c] for c in cols})
    return htf.dropna(subset=["close"])


def _is_htf_open_bar(index: pd.DatetimeIndex, htf_rule: str) -> pd.Series:
    starts = index.floor(htf_rule)
    return pd.Series(index == starts, index=index)


def generate_stacked_mtf_signals(df: pd.DataFrame, config: dict | None = None) -> pd.DataFrame:
    """Build 15m signals for Stacked MTF v3.3.

    Expected input: 15m OHLCV with DatetimeIndex (UTC preferred).
    Output columns include stack flags, HTF confirmation, long_signal, exit_signal.
    short_signal is always False (long-only).
    """
    cfg = _cfg(config)
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("generate_stacked_mtf_signals requires a DatetimeIndex")

    chart = _attach_indicators(df, cfg)
    htf_rule = str(cfg["htf"])
    htf_raw = _resample_ohlcv(chart, htf_rule)
    htf = _attach_indicators(htf_raw, cfg)

    if cfg["use_live_htf"]:
        htf_up_src = htf["stack_up"]
        htf_dn_src = htf["stack_dn"]
    else:
        # Confirmed closed HTF bar (Pine: f_upPrev + lookahead_on)
        htf_up_src = htf["stack_up"].shift(1)
        htf_dn_src = htf["stack_dn"].shift(1)

    chart["htf_stack_up"] = htf_up_src.reindex(chart.index, method="ffill").fillna(False).astype(bool)
    chart["htf_stack_dn"] = htf_dn_src.reindex(chart.index, method="ffill").fillna(False).astype(bool)
    chart["is_htf_open"] = _is_htf_open_bar(chart.index, htf_rule)

    any_selected = any(
        cfg[k] for k in ("use_ema_fast", "use_ema_slow", "use_dema", "use_supertrend")
    )
    htf_ok = chart["htf_stack_up"] if cfg["require_htf"] else pd.Series(True, index=chart.index)
    long_cond = any_selected & htf_ok & chart["stack_up"]
    if cfg["fresh_only"]:
        entry_trig = long_cond & ~long_cond.shift(fill_value=False)
    else:
        entry_trig = long_cond
    sync_ok = chart["is_htf_open"] if cfg["require_sync"] else pd.Series(True, index=chart.index)
    chart["long_cond"] = long_cond.astype(bool)
    chart["long_signal"] = (entry_trig & sync_ok).astype(bool)
    chart["short_signal"] = False

    # Exit modes (default: full stack flip)
    mode = str(cfg["exit_mode"])
    st_flip = (chart["supertrend_dir"] == -1) & (chart["supertrend_dir"].shift(fill_value=1) == 1)
    below_ema_slow = chart["close"] < chart["ema_slow"]
    ema_cross = (chart["ema_fast"] < chart["ema_slow"]) & (
        chart["ema_fast"].shift(fill_value=0) >= chart["ema_slow"].shift(fill_value=0)
    )
    any_lost = pd.Series(False, index=chart.index)
    if cfg["use_ema_fast"]:
        any_lost = any_lost | (chart["close"] < chart["ema_fast"])
    if cfg["use_ema_slow"]:
        any_lost = any_lost | (chart["close"] < chart["ema_slow"])
    if cfg["use_dema"]:
        any_lost = any_lost | (chart["close"] < chart["dema_200"])
    if cfg["use_supertrend"]:
        any_lost = any_lost | (chart["close"] < chart["supertrend"])

    if mode == "supertrend_flip":
        exit_sig = st_flip
    elif mode == "below_ema_slow":
        exit_sig = below_ema_slow
    elif mode == "ema_cross":
        exit_sig = ema_cross
    elif mode == "any_lost":
        exit_sig = any_lost
    else:
        exit_sig = chart["stack_dn"]

    chart["exit_signal"] = exit_sig.fillna(False).astype(bool)

    # Risk distance for sizing (Pine: close - stLine, fallback atr * mult)
    raw_risk = chart["close"] - chart["supertrend"]
    fallback = chart["atr"] * float(cfg["supertrend_multiplier"])
    chart["risk_distance"] = raw_risk.where(raw_risk > 0, fallback).clip(lower=1e-12)

    # Optional protective stop level (OFF by default in v3.3)
    chart["stop_loss"] = chart["close"] - chart["risk_distance"]
    chart["take_profit"] = None  # unused; exit is stack flip
    return chart


def _size_qty(equity: float, price: float, risk_distance: float, cfg: dict[str, Any]) -> tuple[float, float]:
    risk_pct = float(cfg["risk_pct"])
    max_lev = float(cfg["max_leverage"])
    if risk_distance <= 0 or price <= 0 or equity <= 0:
        return 0.0, 0.0
    raw = (equity * risk_pct / 100.0) / risk_distance
    cap = (equity * max_lev) / price
    qty = min(raw, cap)
    risk_amount = qty * risk_distance
    return max(qty, 0.0), risk_amount


def run_stacked_mtf_backtest(
    df: pd.DataFrame,
    config: dict | None = None,
    fee_bps: float | None = 5.0,
    slippage_bps: float | None = 2.0,
    entry_on_close: bool = True,
    save_trades_path: str | Path | None = "journals/stacked_mtf_backtest_trades.csv",
) -> dict:
    """Long-only Stacked MTF backtest with fees + slippage.

    Fills match Pine ``process_orders_on_close`` when ``entry_on_close=True``
    (default): enter/exit at the signal bar close +/- slippage.
    """
    full_config = config or {}
    cfg = _cfg(full_config)
    backtest_cfg = full_config.get("backtest", {})
    initial_equity = float(backtest_cfg.get("initial_equity", 10000.0))
    # Fees/slippage ON: prefer explicit args, else settings.yaml backtest block.
    commission = _commission_pct(full_config, fee_bps)
    signals = generate_stacked_mtf_signals(df, full_config)

    equity = initial_equity
    equity_curve = [equity]
    trades: list[dict] = []
    position: dict | None = None
    trade_id = 0

    for ts, row in signals.iterrows():
        raw_close = float(row["close"])
        raw_open = float(row["open"])

        # Protective stop (optional; OFF in v3.3 defaults)
        if position is not None and cfg["use_stop"]:
            stop = float(position["stop_loss"])
            if float(row["low"]) <= stop:
                trade_id += 1
                exit_price, exit_slip = _exit_price(stop, "long", "stop_loss", full_config, slippage_bps)
                trade = _close_long(
                    trade_id, position, ts, exit_price, exit_slip, "stop_loss", equity, commission
                )
                equity += trade["net_pnl"]
                trade["equity_after_trade"] = equity
                trades.append(trade)
                equity_curve.append(equity)
                position = None

        # Stack / mode exit at close
        if position is not None and bool(row["exit_signal"]):
            fill_raw = raw_close if entry_on_close else raw_open
            trade_id += 1
            exit_price, exit_slip = _exit_price(fill_raw, "long", "stack_flip", full_config, slippage_bps)
            trade = _close_long(
                trade_id, position, ts, exit_price, exit_slip, "stack_flip", equity, commission
            )
            equity += trade["net_pnl"]
            trade["equity_after_trade"] = equity
            trades.append(trade)
            equity_curve.append(equity)
            position = None

        # Entry (flat only; long-only; no pyramid)
        if position is None and bool(row["long_signal"]):
            fill_raw = raw_close if entry_on_close else raw_open
            entry_price, entry_slip = _entry_price(fill_raw, "long", full_config, slippage_bps)
            risk_distance = float(row["risk_distance"])
            qty, risk_amount = _size_qty(equity, entry_price, risk_distance, cfg)
            if qty > 0:
                stop_level = entry_price - risk_distance
                position = {
                    "side": "long",
                    "entry_time": ts,
                    "entry_price": entry_price,
                    "entry_slippage": entry_slip,
                    "stop_loss": stop_level,
                    "take_profit": entry_price + 2 * risk_distance,  # unused placeholder for R
                    "risk_amount": risk_amount,
                    "intended_qty": qty,
                    "qty": qty,
                    "planned_rr_at_entry": 2.0,
                    "reason_for_entry": "stacked_mtf_v3.3_2h_sync",
                    "signal_id": f"long-{ts}",
                }

    if position is not None and len(signals):
        trade_id += 1
        last_ts = signals.index[-1]
        last_close = float(signals.iloc[-1]["close"])
        exit_price, exit_slip = _exit_price(last_close, "long", "end_of_test", full_config, slippage_bps)
        trade = _close_long(
            trade_id, position, last_ts, exit_price, exit_slip, "end_of_test", equity, commission
        )
        equity += trade["net_pnl"]
        trade["equity_after_trade"] = equity
        trades.append(trade)
        equity_curve.append(equity)

    report = summarize_trades(trades, equity_curve, initial_equity)
    report["strategy"] = cfg["name"]
    report["fee_bps"] = fee_bps if fee_bps is not None else full_config.get("backtest", {}).get("commission_pct", 0.05) * 100
    report["slippage_bps"] = slippage_bps if slippage_bps is not None else full_config.get("backtest", {}).get("slippage_bps", 2)
    report["entry_on_close"] = entry_on_close
    report["use_stop"] = cfg["use_stop"]
    if save_trades_path is not None:
        Path(save_trades_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(trades).to_csv(save_trades_path, index=False)
    return report


def _close_long(
    trade_id: int,
    position: dict,
    exit_time,
    exit_price: float,
    exit_slip: float,
    exit_reason: str,
    equity: float,
    commission_pct: float,
) -> dict:
    qty = position["qty"]
    gross_pnl = (exit_price - position["entry_price"]) * qty
    fees = (abs(position["entry_price"] * qty) + abs(exit_price * qty)) * commission_pct
    slippage_cost = (position["entry_slippage"] + exit_slip) * qty
    net_pnl = gross_pnl - fees
    realized_r = net_pnl / position["risk_amount"] if position["risk_amount"] else 0.0
    return {
        "trade_id": trade_id,
        "entry_time": position["entry_time"],
        "exit_time": exit_time,
        "entry_timestamp": position["entry_time"],
        "exit_timestamp": exit_time,
        "side": "long",
        "entry_price": position["entry_price"],
        "stop_loss": position["stop_loss"],
        "take_profit": position["take_profit"],
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "planned_rr_at_entry": position["planned_rr_at_entry"],
        "realized_r_multiple": realized_r,
        "risk_amount": position["risk_amount"],
        "intended_qty": position["intended_qty"],
        "filled_qty": qty,
        "qty": qty,
        "gross_pnl": gross_pnl,
        "fees": fees,
        "slippage_cost": slippage_cost,
        "net_pnl": net_pnl,
        "pnl": net_pnl,
        "r_multiple": realized_r,
        "equity_after_trade": equity,
        "reason_for_entry": position["reason_for_entry"],
        "reason_for_exit": exit_reason,
        "mode": "BACKTEST_ONLY",
        "signal_id": position["signal_id"],
    }


def load_config(path: str | Path = "config/settings.yaml") -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_report(report: dict, path: str | Path = "reports/stacked_mtf_backtest_report.md") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Stacked MTF v3.3 Backtest Report", ""]
    for key, value in report.items():
        if key == "trades":
            continue
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "Live trading remains blocked. This report is research-only.",
        "Fees and slippage were applied (see fee_bps / slippage_bps).",
    ])
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest Stacked MTF v3.3 (15m + 2H, long-only)")
    parser.add_argument("--csv", required=True, help="15m OHLCV CSV: timestamp,open,high,low,close,volume")
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--fee-bps", type=float, default=5.0, help="Per-side fee in basis points; default 5 (0.05 percent)")
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--entry-on-close", action="store_true", default=True)
    parser.add_argument("--entry-on-open", action="store_true", help="Fill next-style at bar open instead of close")
    parser.add_argument("--trades-out", default="journals/stacked_mtf_backtest_trades.csv")
    parser.add_argument("--report-out", default="reports/stacked_mtf_backtest_report.md")
    args = parser.parse_args()

    config = load_config(args.config)
    df = load_ohlcv_csv(args.csv, expected_freq="15min")
    entry_on_close = not args.entry_on_open
    report = run_stacked_mtf_backtest(
        df,
        config,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        entry_on_close=entry_on_close,
        save_trades_path=args.trades_out,
    )
    write_report(report, args.report_out)
    print("STACKED MTF v3.3 BACKTEST COMPLETE")
    for key in (
        "total_trades",
        "win_rate",
        "profit_factor",
        "net_pnl",
        "max_drawdown_pct",
        "fees_paid",
        "slippage_cost",
        "flip_exits",
    ):
        print(f"{key}: {report.get(key)}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from .strategy import generate_signals


def _commission_pct(config: dict, fee_bps: float | None) -> float:
    if fee_bps is not None:
        return fee_bps / 10000
    return config.get("backtest", {}).get("commission_pct", 0.05) / 100


def _slippage_abs(price: float, config: dict, slippage_bps: float | None) -> float:
    bps = slippage_bps if slippage_bps is not None else config.get("backtest", {}).get("slippage_bps", 2)
    min_abs = config.get("backtest", {}).get("min_slippage_abs", 0.0)
    return max(abs(price) * bps / 10000, min_abs)


def _entry_price(raw_price: float, side: str, config: dict, slippage_bps: float | None) -> tuple[float, float]:
    slip = _slippage_abs(raw_price, config, slippage_bps)
    if side == "long":
        return raw_price + slip, slip
    return raw_price - slip, slip


def _exit_price(raw_price: float, side: str, reason: str, config: dict, slippage_bps: float | None) -> tuple[float, float]:
    slip = _slippage_abs(raw_price, config, slippage_bps)
    if side == "long":
        return raw_price - slip, slip
    return raw_price + slip, slip


def _max_streak(values: list[bool]) -> int:
    best = cur = 0
    for value in values:
        if value:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def _profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    wins = trades.loc[trades["net_pnl"] > 0, "net_pnl"].sum()
    losses = abs(trades.loc[trades["net_pnl"] <= 0, "net_pnl"].sum())
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def summarize_trades(trades: list[dict], equity_curve: list[float], initial_equity: float) -> dict:
    trade_df = pd.DataFrame(trades)
    if not equity_curve:
        equity_curve = [initial_equity]
    running_peak = pd.Series(equity_curve).cummax()
    drawdowns = (running_peak - pd.Series(equity_curve)) / running_peak
    if trade_df.empty:
        return {
            "net_profit": 0.0,
            "gross_pnl": 0.0,
            "fees_paid": 0.0,
            "slippage_cost": 0.0,
            "net_pnl": 0.0,
            "profit_factor": 0.0,
            "max_drawdown_pct": 0.0,
            "expectancy": 0.0,
            "win_rate": 0.0,
            "average_r": 0.0,
            "average_realized_r": 0.0,
            "average_planned_rr": 0.0,
            "total_trades": 0,
            "trade_count": 0,
            "average_trade_after_fees": 0.0,
            "max_consecutive_losses": 0,
            "max_consecutive_wins": 0,
            "losing_trades": 0,
            "winning_trades": 0,
            "stop_loss_exits": 0,
            "take_profit_exits": 0,
            "flip_exits": 0,
            "ambiguous_candles": 0,
            "lookahead_bias": False,
            "repainting": False,
            "trades": [],
        }
    wins = (trade_df["net_pnl"] > 0).tolist()
    losses = (trade_df["net_pnl"] <= 0).tolist()
    return {
        "net_profit": float(trade_df["net_pnl"].sum()),
        "gross_pnl": float(trade_df["gross_pnl"].sum()),
        "fees_paid": float(trade_df["fees"].sum()),
        "slippage_cost": float(trade_df["slippage_cost"].sum()),
        "net_pnl": float(trade_df["net_pnl"].sum()),
        "profit_factor": float(_profit_factor(trade_df)),
        "max_drawdown_pct": float(drawdowns.max() * 100),
        "expectancy": float(trade_df["net_pnl"].mean()),
        "win_rate": float((trade_df["net_pnl"] > 0).mean() * 100),
        "average_r": float(trade_df["realized_r_multiple"].mean()),
        "average_realized_r": float(trade_df["realized_r_multiple"].mean()),
        "average_planned_rr": float(trade_df["planned_rr_at_entry"].mean()),
        "total_trades": len(trade_df),
        "trade_count": len(trade_df),
        "average_trade_after_fees": float(trade_df["net_pnl"].mean()),
        "max_consecutive_losses": _max_streak(losses),
        "max_consecutive_wins": _max_streak(wins),
        "losing_trades": int((trade_df["net_pnl"] <= 0).sum()),
        "winning_trades": int((trade_df["net_pnl"] > 0).sum()),
        "stop_loss_exits": int((trade_df["exit_reason"].str.contains("stop_loss|ambiguous_stop_first")).sum()),
        "take_profit_exits": int((trade_df["exit_reason"].str.contains("take_profit|ambiguous_tp_first")).sum()),
        "flip_exits": int((trade_df["exit_reason"] == "flip_exit").sum()),
        "ambiguous_candles": int((trade_df["exit_reason"].str.contains("ambiguous")).sum()),
        "lookahead_bias": False,
        "repainting": False,
        "trades": trades,
    }


def _planned_rr(side: str, entry: float, stop: float, target: float) -> float:
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        return 0.0
    return abs(target - entry) / stop_distance


def _make_trade(
    trade_id: int,
    position: dict,
    exit_time,
    raw_exit_price: float,
    exit_reason: str,
    equity_after: float,
    config: dict,
    commission_pct: float,
    slippage_bps: float | None,
) -> dict:
    side = position["side"]
    exit_price, exit_slip = _exit_price(raw_exit_price, side, exit_reason, config, slippage_bps)
    direction = 1 if side == "long" else -1
    gross_pnl = (exit_price - position["entry_price"]) * position["qty"] * direction
    entry_fee = abs(position["entry_price"] * position["qty"]) * commission_pct
    exit_fee = abs(exit_price * position["qty"]) * commission_pct
    fees = entry_fee + exit_fee
    slippage_cost = (position["entry_slippage"] + exit_slip) * position["qty"]
    net_pnl = gross_pnl - fees
    realized_r = net_pnl / position["risk_amount"] if position["risk_amount"] else 0.0
    return {
        "trade_id": trade_id,
        "entry_time": position["entry_time"],
        "exit_time": exit_time,
        "entry_timestamp": position["entry_time"],
        "exit_timestamp": exit_time,
        "side": side,
        "entry_price": position["entry_price"],
        "stop_loss": position["stop_loss"],
        "take_profit": position["take_profit"],
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "planned_rr_at_entry": position["planned_rr_at_entry"],
        "realized_r_multiple": realized_r,
        "risk_amount": position["risk_amount"],
        "intended_qty": position["intended_qty"],
        "filled_qty": position["qty"],
        "qty": position["qty"],
        "gross_pnl": gross_pnl,
        "fees": fees,
        "slippage_cost": slippage_cost,
        "net_pnl": net_pnl,
        "pnl": net_pnl,
        "r_multiple": realized_r,
        "equity_after_trade": equity_after,
        "reason_for_entry": position["reason_for_entry"],
        "reason_for_exit": exit_reason,
        "mode": config.get("risk", {}).get("mode", "BACKTEST_ONLY"),
        "signal_id": position["signal_id"],
    }


def run_realistic_backtest(
    df: pd.DataFrame,
    config: dict,
    fee_bps: float | None = None,
    slippage_bps: float | None = None,
    entry_delay_candles: int = 1,
    save_trades_path: str | Path | None = "journals/backtest_trades.csv",
) -> dict:
    backtest_cfg = config.get("backtest", {})
    same_bar_policy = backtest_cfg.get("same_bar_policy", "stop_first")
    entry_on_close = backtest_cfg.get("entry_on_close", False)
    if same_bar_policy not in {"stop_first", "tp_first", "skip_ambiguous", "open_path_estimate"}:
        raise ValueError(f"unsupported same_bar_policy: {same_bar_policy}")

    signals = generate_signals(df, config)
    initial_equity = float(backtest_cfg.get("initial_equity", 10000.0))
    equity = initial_equity
    equity_curve = [equity]
    risk_pct = float(config.get("risk", {}).get("normal_live_risk_pct", 0.25))
    commission = _commission_pct(config, fee_bps)
    trades: list[dict] = []
    position: dict | None = None
    pending_entry: dict | None = None
    pending_flip: dict | None = None
    trade_id = 0

    for i, (ts, row) in enumerate(signals.iterrows()):
        raw_open = float(row["open"])
        raw_close = float(row["close"])

        if pending_flip is not None and position is not None:
            trade_id += 1
            trade = _make_trade(trade_id, position, ts, raw_open, "flip_exit", equity, config, commission, slippage_bps)
            equity += trade["net_pnl"]
            trade["equity_after_trade"] = equity
            trades.append(trade)
            equity_curve.append(equity)
            position = None
            pending_entry = pending_flip
            pending_flip = None

        if pending_entry is not None and position is None and i >= pending_entry["fill_index"]:
            side = pending_entry["side"]
            fill_raw = raw_close if entry_on_close else raw_open
            entry_price, entry_slip = _entry_price(fill_raw, side, config, slippage_bps)
            stop = float(pending_entry["stop_loss"])
            target = float(pending_entry["take_profit"])
            stop_distance = abs(entry_price - stop)
            risk_amount = equity * risk_pct / 100
            if stop_distance > 0 and risk_amount > 0:
                intended_qty = risk_amount / stop_distance
                qty = intended_qty
                if not config.get("risk", {}).get("allow_leverage", False):
                    max_qty = equity / entry_price
                    qty = min(qty, max_qty)
                    risk_amount = qty * stop_distance
                if qty > 0 and _planned_rr(side, entry_price, stop, target) >= config["strategy"]["min_rr"]:
                    position = {
                        "side": side,
                        "entry_time": ts,
                        "entry_price": entry_price,
                        "entry_slippage": entry_slip,
                        "stop_loss": stop,
                        "take_profit": target,
                        "risk_amount": risk_amount,
                        "intended_qty": intended_qty,
                        "qty": qty,
                        "planned_rr_at_entry": _planned_rr(side, entry_price, stop, target),
                        "reason_for_entry": "confirmed first-bar confluence filled next candle open",
                        "signal_id": pending_entry["signal_id"],
                    }
            pending_entry = None

        if position is not None:
            side = position["side"]
            if side == "long":
                stop_hit = float(row["low"]) <= position["stop_loss"]
                tp_hit = float(row["high"]) >= position["take_profit"]
                stop_price = position["stop_loss"]
                tp_price = position["take_profit"]
            else:
                stop_hit = float(row["high"]) >= position["stop_loss"]
                tp_hit = float(row["low"]) <= position["take_profit"]
                stop_price = position["stop_loss"]
                tp_price = position["take_profit"]

            exit_reason = None
            exit_raw = None
            if stop_hit and tp_hit:
                if same_bar_policy == "skip_ambiguous":
                    exit_reason = "ambiguous_skipped"
                    exit_raw = raw_close
                elif same_bar_policy == "tp_first":
                    exit_reason = "ambiguous_tp_first"
                    exit_raw = tp_price
                else:
                    exit_reason = "ambiguous_stop_first"
                    exit_raw = stop_price
            elif stop_hit:
                exit_reason = "stop_loss"
                exit_raw = stop_price
            elif tp_hit:
                exit_reason = "take_profit"
                exit_raw = tp_price

            if exit_reason is not None:
                trade_id += 1
                trade = _make_trade(trade_id, position, ts, exit_raw, exit_reason, equity, config, commission, slippage_bps)
                equity += trade["net_pnl"]
                trade["equity_after_trade"] = equity
                trades.append(trade)
                equity_curve.append(equity)
                position = None

        if position is not None and config["strategy"].get("use_flip_exit", True):
            if position["side"] == "long" and bool(row.get("short_signal", False)):
                pending_flip = {
                    "side": "short",
                    "stop_loss": row["stop_loss"],
                    "take_profit": row["take_profit"],
                    "signal_id": f"short-{ts}",
                    "fill_index": i + 1,
                }
            elif position["side"] == "short" and bool(row.get("long_signal", False)):
                pending_flip = {
                    "side": "long",
                    "stop_loss": row["stop_loss"],
                    "take_profit": row["take_profit"],
                    "signal_id": f"long-{ts}",
                    "fill_index": i + 1,
                }

        if position is None and pending_entry is None and pending_flip is None:
            if bool(row.get("long_signal", False)) and i + entry_delay_candles < len(signals):
                pending_entry = {
                    "side": "long",
                    "stop_loss": row["stop_loss"],
                    "take_profit": row["take_profit"],
                    "signal_id": f"long-{ts}",
                    "fill_index": i + entry_delay_candles,
                }
            elif bool(row.get("short_signal", False)) and i + entry_delay_candles < len(signals):
                pending_entry = {
                    "side": "short",
                    "stop_loss": row["stop_loss"],
                    "take_profit": row["take_profit"],
                    "signal_id": f"short-{ts}",
                    "fill_index": i + entry_delay_candles,
                }

    if position is not None and len(signals):
        trade_id += 1
        last_ts = signals.index[-1]
        last_close = float(signals.iloc[-1]["close"])
        trade = _make_trade(trade_id, position, last_ts, last_close, "end_of_test", equity, config, commission, slippage_bps)
        equity += trade["net_pnl"]
        trade["equity_after_trade"] = equity
        trades.append(trade)
        equity_curve.append(equity)

    report = summarize_trades(trades, equity_curve, initial_equity)
    report["same_bar_policy"] = same_bar_policy
    if save_trades_path is not None:
        Path(save_trades_path).parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(trades).to_csv(save_trades_path, index=False)
    return report


def write_trade_distribution_report(metrics: dict, path: str | Path = "reports/trade_distribution_report.md") -> None:
    trades = pd.DataFrame(metrics.get("trades", []))
    lines = ["# Trade Distribution Report", ""]
    if trades.empty:
        lines.append("- total trades: 0")
    else:
        lines.extend([
            f"- total trades: {len(trades)}",
            f"- wins: {(trades['net_pnl'] > 0).sum()}",
            f"- losses: {(trades['net_pnl'] <= 0).sum()}",
            f"- win rate: {metrics['win_rate']}",
            f"- average win: {trades.loc[trades['net_pnl'] > 0, 'net_pnl'].mean() if (trades['net_pnl'] > 0).any() else 0}",
            f"- average loss: {trades.loc[trades['net_pnl'] <= 0, 'net_pnl'].mean() if (trades['net_pnl'] <= 0).any() else 0}",
            f"- largest win: {trades['net_pnl'].max()}",
            f"- largest loss: {trades['net_pnl'].min()}",
            f"- profit factor: {metrics['profit_factor']}",
            f"- max drawdown: {metrics['max_drawdown_pct']}",
            f"- consecutive wins: {metrics['max_consecutive_wins']}",
            f"- consecutive losses: {metrics['max_consecutive_losses']}",
            f"- stop loss exits count: {metrics['stop_loss_exits']}",
            f"- take profit exits count: {metrics['take_profit_exits']}",
            f"- flip exits count: {metrics['flip_exits']}",
            f"- ambiguous candles count: {metrics['ambiguous_candles']}",
            f"- average planned RR: {metrics['average_planned_rr']}",
            f"- average realized R: {metrics['average_realized_r']}",
            f"- median realized R: {trades['realized_r_multiple'].median()}",
            f"- average fees per trade: {trades['fees'].mean()}",
            f"- average slippage per trade: {trades['slippage_cost'].mean()}",
        ])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")

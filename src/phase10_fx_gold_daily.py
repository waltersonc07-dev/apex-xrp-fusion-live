"""
Phase 10 — FX / Gold daily-trend research module.

Purpose
-------
The XRP 1H trend-following family failed validation in phases 5 through 9
(see reports/live_unlock_report.md and the Phase 5A/7A/8A history). The
APEX framework — backtest engine, validation gate, walk-forward,
stress tests, trade audit, risk engine, three-layer live lock — is sound.
What is missing is a strategy with a real edge.

Phase 10 pivots the strategy hypothesis to **daily-timeframe** trend
following on three high-liquidity, high-data-quality instruments:

    Primary: EURUSD, GBPUSD, XAUUSD (gold)
    Control: USDJPY  (benchmark; not a primary optimization target)

This module is **standalone**:

    * It does not import the XRP strategy or XRP backtest engine.
    * It does not modify config/settings.yaml, .env, render.yaml, or any
      live-flag. It is research-only.
    * It reuses the existing validation philosophy (PF >= 1.50, OOS PF
      >= 1.20, max DD <= 25%, trades >= 40 per asset, beats buy-and-hold,
      walk-forward stable, 2x fees / 2x slippage stress) but applies it
      to FX/Gold daily timeframes and adds an FX-appropriate Sharpe gate
      (>= 0.8).
    * It tests four non-optimized variants. Parameters are conventional
      defaults from published trend-following literature; they are NOT
      tuned in-sample.

Until PR 3 (data ingestion) is merged, this module is exercised on
synthetic test fixtures and on whatever CSVs the user drops into
`data/raw/`. The verdict report defaults to a BLOCK_LIVE-style header
so nothing here can be mistaken for a tradeable signal.

Variants
--------
V0  Long-only daily trend.
    Regime:    close > EMA(200)
    Entry:     EMA(21) > EMA(55) AND RSI(14) crosses up through 50
    Stop:      entry - ATR(14) * 2.0
    Exit:      daily close back below EMA(21), executed at next open

V1  Both-sides version of V0 (mirror logic for shorts).

V2  Long-only Donchian-20 breakout with EMA(200) regime gate.
    Entry:     close > highest_high(prev 20 bars) AND close > EMA(200)
    Stop:      entry - ATR(14) * 2.0
    Exit:      close < lowest_low(prev 10 bars)

V3  Both-sides Bollinger-squeeze volatility expansion.
    Setup:     20-bar Bollinger Band width < 30th percentile (rolling 100)
    Trigger:   close breaks above upper band (long) or below lower (short)
    Stop:      mid band at entry
    Exit:      close back through mid band

Pip / contract math
-------------------
FX pairs are priced in dollars per unit of base currency; we trade
notional = risk_capital / stop_distance_in_price. Gold (XAUUSD) is
priced in dollars per ounce; same formula applies. Fees and slippage
are expressed in basis points of price, consistent with the XRP engine.

This is research code. Do not connect it to any execution path.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yaml

from .indicators import atr, ema, rsi

# ---------------------------------------------------------------------------
# Configuration constants — these are research defaults, not user-tunable
# parameters. Optimizing them inside this PR would be the exact overfitting
# trap the gate is designed to catch.
# ---------------------------------------------------------------------------

PHASE10_VARIANTS = ("V0", "V1", "V2", "V3")
PRIMARY_SYMBOLS = ("EURUSD", "GBPUSD", "XAUUSD")
CONTROL_SYMBOLS = ("USDJPY",)

DEFAULT_CONFIG: dict = {
    "ema_regime": 200,
    "ema_fast": 21,
    "ema_slow": 55,
    "rsi_length": 14,
    "rsi_cross_level": 50,
    "atr_length": 14,
    "atr_stop_mult": 2.0,
    "donchian_in": 20,
    "donchian_out": 10,
    "bb_length": 20,
    "bb_std": 2.0,
    "squeeze_percentile": 30,
    "squeeze_lookback": 100,
    "initial_equity": 10_000.0,
    "risk_per_trade_pct": 0.5,
    "commission_bps_per_side": 1.0,   # 1 bp per side  ≈ 0.01%
    "slippage_bps_per_side": 0.5,     # 0.5 bp per side
    "min_trades_per_asset": 40,
    "min_profit_factor": 1.50,
    "min_oos_profit_factor": 1.20,
    "max_drawdown_pct": 25.0,
    "min_sharpe": 0.8,
    "oos_fraction": 0.20,
    "wf_windows": 3,
    "stress_fee_multiplier": 2.0,
    "stress_slippage_multiplier": 2.0,
    # ----- Filters (Phase 10 PR 5). Defaults preserve baseline behavior. -----
    # When ``enable_session_filter`` or ``enable_regime_filter`` is False the
    # corresponding filter is a no-op, so the unfiltered verdict reproduces
    # the original Phase 10 numbers bit-for-bit.
    "enable_session_filter": False,
    "enable_regime_filter": False,
    "session_cfg": None,        # falls back to DEFAULT_SESSION_CFG when used
    "regime_cfg": None,         # falls back to DEFAULT_REGIME_CFG when used
    "regimes_allowed": None,    # None = all regimes except 'unknown'
}


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    side: str               # "long" or "short"
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: pd.Timestamp
    exit_price: float
    stop_price: float
    size_units: float
    gross_pnl: float
    fees: float
    slippage_cost: float
    net_pnl: float
    exit_reason: str        # "stop_loss", "trail_exit", "session_end"
    realized_r: float


@dataclass
class BacktestResult:
    variant: str
    symbol: str
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Indicator helpers specific to Phase 10 (kept local so the module is
# self-contained even if src/indicators.py changes later)
# ---------------------------------------------------------------------------


def _bollinger(series: pd.Series, length: int, num_std: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = series.rolling(length, min_periods=length).mean()
    sd = series.rolling(length, min_periods=length).std(ddof=0)
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    return upper, mid, lower


def _donchian(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series]:
    upper = df["high"].rolling(length, min_periods=length).max().shift(1)
    lower = df["low"].rolling(length, min_periods=length).min().shift(1)
    return upper, lower


# ---------------------------------------------------------------------------
# Variant signal builders. Each returns two boolean columns: long_entry,
# short_entry. Signals are evaluated on the close of bar N; execution is
# always at the open of bar N+1 (no lookahead).
# ---------------------------------------------------------------------------


def _v0_signals(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    out["ema_regime"] = ema(out["close"], cfg["ema_regime"])
    out["ema_fast"] = ema(out["close"], cfg["ema_fast"])
    out["ema_slow"] = ema(out["close"], cfg["ema_slow"])
    out["rsi"] = rsi(out["close"], cfg["rsi_length"])
    rsi_cross_up = (out["rsi"] > cfg["rsi_cross_level"]) & (
        out["rsi"].shift(1) <= cfg["rsi_cross_level"]
    )
    long_regime = out["close"] > out["ema_regime"]
    trend = out["ema_fast"] > out["ema_slow"]
    out["long_entry"] = long_regime & trend & rsi_cross_up
    out["short_entry"] = False
    return out


def _v1_signals(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = _v0_signals(df, cfg)
    rsi_cross_dn = (out["rsi"] < cfg["rsi_cross_level"]) & (
        out["rsi"].shift(1) >= cfg["rsi_cross_level"]
    )
    short_regime = out["close"] < out["ema_regime"]
    short_trend = out["ema_fast"] < out["ema_slow"]
    out["short_entry"] = short_regime & short_trend & rsi_cross_dn
    return out


def _v2_signals(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    out["ema_regime"] = ema(out["close"], cfg["ema_regime"])
    upper, lower = _donchian(out, cfg["donchian_in"])
    out["donchian_high"] = upper
    out["donchian_low"] = lower
    out["long_entry"] = (out["close"] > upper) & (out["close"] > out["ema_regime"])
    out["short_entry"] = False
    return out


def _v3_signals(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    upper, mid, lower = _bollinger(out["close"], cfg["bb_length"], cfg["bb_std"])
    out["bb_upper"] = upper
    out["bb_mid"] = mid
    out["bb_lower"] = lower
    width = (upper - lower) / mid
    threshold = width.rolling(cfg["squeeze_lookback"], min_periods=cfg["squeeze_lookback"]).quantile(
        cfg["squeeze_percentile"] / 100.0
    )
    squeezed = width.shift(1) < threshold.shift(1)
    out["long_entry"] = squeezed & (out["close"] > upper)
    out["short_entry"] = squeezed & (out["close"] < lower)
    return out


VARIANT_SIGNAL_BUILDERS: dict[str, Callable[[pd.DataFrame, dict], pd.DataFrame]] = {
    "V0": _v0_signals,
    "V1": _v1_signals,
    "V2": _v2_signals,
    "V3": _v3_signals,
}


# Exit rules differ per variant.
def _exit_rule(variant: str, row: pd.Series, prev_row: pd.Series, cfg: dict) -> bool:
    """Return True if the current bar's CLOSE triggers an exit.

    Exits are then executed at the OPEN of the following bar.
    """
    side = row["_side"]
    if variant in ("V0", "V1"):
        # Exit when daily close moves back through the fast EMA against position
        if side == "long":
            return row["close"] < row["ema_fast"]
        return row["close"] > row["ema_fast"]
    if variant == "V2":
        # Donchian exit: close beyond opposite N-bar low/high
        if side == "long":
            return row["close"] < row["donchian_low"]
        return False  # V2 is long-only
    if variant == "V3":
        # Exit when close crosses back through mid band
        if side == "long":
            return row["close"] < row["bb_mid"]
        return row["close"] > row["bb_mid"]
    return False


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------


def _position_size(equity: float, entry: float, stop: float, risk_pct: float) -> float:
    """Compute notional units sized so that hitting the stop loses risk_pct of equity.

    Works for FX pairs (price = quote per base) and for gold (price = USD/oz)
    because the dollar P&L per unit of move is always (exit_price - entry_price)
    in the quote currency. For non-USD-quoted pairs the caller would need to
    convert; this module sticks to USD-quoted instruments (EURUSD, GBPUSD,
    XAUUSD) and USDJPY which we treat in pip terms.
    """
    risk_dollars = equity * (risk_pct / 100.0)
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        return 0.0
    return risk_dollars / stop_distance


def _apply_costs(notional_pnl: float, entry: float, exit_price: float,
                 size: float, fee_bps: float, slip_bps: float) -> tuple[float, float, float]:
    """Return (gross_pnl, fees, slippage) for one round trip."""
    notional_in = entry * size
    notional_out = exit_price * size
    fees = (notional_in + notional_out) * (fee_bps / 10_000.0)
    slippage = (notional_in + notional_out) * (slip_bps / 10_000.0)
    return notional_pnl, fees, slippage


def _backtest_variant(
    df: pd.DataFrame,
    variant: str,
    symbol: str,
    cfg: dict,
    fee_bps: float | None = None,
    slip_bps: float | None = None,
) -> BacktestResult:
    """Run one variant on one symbol's daily OHLCV."""
    fee_bps = cfg["commission_bps_per_side"] if fee_bps is None else fee_bps
    slip_bps = cfg["slippage_bps_per_side"] if slip_bps is None else slip_bps

    sigs = VARIANT_SIGNAL_BUILDERS[variant](df, cfg)
    sigs["atr"] = atr(sigs, cfg["atr_length"])

    # ----- Optional Phase 10 PR 5 filters (session + regime) -----------------
    # Both filters only mask *entries*; exits are never touched. When the
    # config flags are False the original signal columns flow through
    # unchanged, so the unfiltered backtest is bit-identical to PR 2.
    if cfg.get("enable_session_filter") or cfg.get("enable_regime_filter"):
        from .phase10_filters import (  # local import: keeps module load light
            classify_regimes,
            filter_signals,
        )

        regime_view = None
        regimes_allowed = None
        if cfg.get("enable_regime_filter"):
            regime_view = classify_regimes(sigs, cfg.get("regime_cfg"))
            regimes_allowed = cfg.get("regimes_allowed")
            sigs["_regime"] = regime_view.regimes
            sigs["_adx"] = regime_view.adx
        session_cfg = cfg.get("session_cfg") if cfg.get(
            "enable_session_filter"
        ) else {"skip_friday_entries": False,
                "skip_sunday_entries": False,
                "skip_monday_open_entries": False}
        sigs = filter_signals(
            sigs,
            sigs,
            session_cfg=session_cfg,
            regime_view=regime_view,
            regimes_allowed=regimes_allowed,
        )

    equity = cfg["initial_equity"]
    equity_curve: list[float] = [equity]
    trades: list[Trade] = []

    in_pos = False
    side = ""
    entry_price = stop_price = size = 0.0
    entry_time = pd.NaT
    pending_exit_reason = ""

    for i in range(1, len(sigs)):
        prev = sigs.iloc[i - 1]
        cur = sigs.iloc[i]

        # ----- Execute pending exit at this bar's OPEN -----
        if in_pos and pending_exit_reason:
            exit_price = cur["open"]
            gross = (exit_price - entry_price) * size if side == "long" else (entry_price - exit_price) * size
            _, fees, slipc = _apply_costs(gross, entry_price, exit_price, size, fee_bps, slip_bps)
            net = gross - fees - slipc
            realized_r = (net / (equity * cfg["risk_per_trade_pct"] / 100.0)) if equity > 0 else 0.0
            trades.append(Trade(
                side=side, entry_time=entry_time, entry_price=entry_price,
                exit_time=cur.name, exit_price=exit_price, stop_price=stop_price,
                size_units=size, gross_pnl=gross, fees=fees, slippage_cost=slipc,
                net_pnl=net, exit_reason=pending_exit_reason, realized_r=realized_r,
            ))
            equity += net
            equity_curve.append(equity)
            in_pos = False
            pending_exit_reason = ""

        # ----- Manage open position intrabar (stop first) -----
        if in_pos:
            if side == "long" and cur["low"] <= stop_price:
                exit_price = stop_price  # assume stop fills at stop, slip applied
                gross = (exit_price - entry_price) * size
                _, fees, slipc = _apply_costs(gross, entry_price, exit_price, size, fee_bps, slip_bps)
                net = gross - fees - slipc
                realized_r = -1.0  # stop hit ≈ planned -1R minus costs
                trades.append(Trade(
                    side=side, entry_time=entry_time, entry_price=entry_price,
                    exit_time=cur.name, exit_price=exit_price, stop_price=stop_price,
                    size_units=size, gross_pnl=gross, fees=fees, slippage_cost=slipc,
                    net_pnl=net, exit_reason="stop_loss", realized_r=realized_r,
                ))
                equity += net
                equity_curve.append(equity)
                in_pos = False
            elif side == "short" and cur["high"] >= stop_price:
                exit_price = stop_price
                gross = (entry_price - exit_price) * size
                _, fees, slipc = _apply_costs(gross, entry_price, exit_price, size, fee_bps, slip_bps)
                net = gross - fees - slipc
                trades.append(Trade(
                    side=side, entry_time=entry_time, entry_price=entry_price,
                    exit_time=cur.name, exit_price=exit_price, stop_price=stop_price,
                    size_units=size, gross_pnl=gross, fees=fees, slippage_cost=slipc,
                    net_pnl=net, exit_reason="stop_loss", realized_r=-1.0,
                ))
                equity += net
                equity_curve.append(equity)
                in_pos = False
            else:
                # Check trail/exit rule on close; queue for next-bar open
                cur_row = cur.copy()
                cur_row["_side"] = side
                if _exit_rule(variant, cur_row, prev, cfg):
                    pending_exit_reason = "trail_exit"

        # ----- New entry on prev bar signal -----
        if not in_pos and i + 1 < len(sigs):
            if prev.get("long_entry", False) and not np.isnan(prev.get("atr", np.nan)):
                entry_price = cur["open"]
                stop_price = entry_price - prev["atr"] * cfg["atr_stop_mult"]
                size = _position_size(equity, entry_price, stop_price, cfg["risk_per_trade_pct"])
                if size > 0:
                    in_pos = True
                    side = "long"
                    entry_time = cur.name
            elif prev.get("short_entry", False) and not np.isnan(prev.get("atr", np.nan)):
                entry_price = cur["open"]
                stop_price = entry_price + prev["atr"] * cfg["atr_stop_mult"]
                size = _position_size(equity, entry_price, stop_price, cfg["risk_per_trade_pct"])
                if size > 0:
                    in_pos = True
                    side = "short"
                    entry_time = cur.name

    # Close any open position at the last bar's close
    if in_pos:
        last = sigs.iloc[-1]
        exit_price = last["close"]
        gross = (exit_price - entry_price) * size if side == "long" else (entry_price - exit_price) * size
        _, fees, slipc = _apply_costs(gross, entry_price, exit_price, size, fee_bps, slip_bps)
        net = gross - fees - slipc
        trades.append(Trade(
            side=side, entry_time=entry_time, entry_price=entry_price,
            exit_time=last.name, exit_price=exit_price, stop_price=stop_price,
            size_units=size, gross_pnl=gross, fees=fees, slippage_cost=slipc,
            net_pnl=net, exit_reason="session_end", realized_r=net / max(equity * cfg["risk_per_trade_pct"] / 100.0, 1e-9),
        ))
        equity += net
        equity_curve.append(equity)

    metrics = _summarize(trades, equity_curve, cfg["initial_equity"], df)
    return BacktestResult(variant=variant, symbol=symbol, trades=trades,
                          equity_curve=equity_curve, metrics=metrics)


def _summarize(trades: list[Trade], equity_curve: list[float],
               initial_equity: float, df: pd.DataFrame) -> dict:
    if not trades:
        return {
            "trades": 0, "win_rate": 0.0, "profit_factor": 0.0,
            "net_profit": 0.0, "max_drawdown_pct": 0.0, "expectancy": 0.0,
            "sharpe": 0.0, "buy_and_hold_return_pct": _buy_and_hold(df),
            "strategy_return_pct": 0.0, "stop_loss_exits": 0, "losing_trades": 0,
        }
    nets = np.array([t.net_pnl for t in trades])
    wins = nets[nets > 0]
    losses = nets[nets <= 0]
    pf = float(wins.sum() / abs(losses.sum())) if losses.sum() != 0 else (float("inf") if wins.sum() > 0 else 0.0)
    eq = pd.Series(equity_curve)
    drawdown = (eq.cummax() - eq) / eq.cummax()
    daily_returns = eq.pct_change().dropna()
    sharpe = float(daily_returns.mean() / daily_returns.std() * math.sqrt(252)) if daily_returns.std() > 0 else 0.0
    return {
        "trades": len(trades),
        "win_rate": float((nets > 0).mean() * 100),
        "profit_factor": pf,
        "net_profit": float(nets.sum()),
        "strategy_return_pct": float((equity_curve[-1] / initial_equity - 1) * 100),
        "max_drawdown_pct": float(drawdown.max() * 100),
        "expectancy": float(nets.mean()),
        "sharpe": sharpe,
        "buy_and_hold_return_pct": _buy_and_hold(df),
        "stop_loss_exits": int(sum(1 for t in trades if t.exit_reason == "stop_loss")),
        "losing_trades": int((nets <= 0).sum()),
    }


def _buy_and_hold(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float((df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100)


# ---------------------------------------------------------------------------
# Splits and walk-forward
# ---------------------------------------------------------------------------


def split_oos(df: pd.DataFrame, oos_fraction: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_at = max(1, min(len(df) - 1, int(len(df) * (1 - oos_fraction))))
    return df.iloc[:split_at].copy(), df.iloc[split_at:].copy()


def walk_forward(df: pd.DataFrame, variant: str, symbol: str, cfg: dict,
                 windows: int) -> list[dict]:
    """Roll forward N equal-sized OOS chunks. Each window uses the cumulative
    history before it for context but is scored on its own OOS slice.
    """
    if windows <= 1 or len(df) < windows * 50:
        return []
    window_size = len(df) // windows
    results = []
    for w in range(1, windows + 1):
        start = (w - 1) * window_size
        end = w * window_size if w < windows else len(df)
        slice_df = df.iloc[start:end].copy()
        res = _backtest_variant(slice_df, variant, symbol, cfg)
        results.append({
            "window": w,
            "trades": res.metrics["trades"],
            "profit_factor": res.metrics["profit_factor"],
            "max_drawdown_pct": res.metrics["max_drawdown_pct"],
            "net_profit": res.metrics["net_profit"],
            "sharpe": res.metrics["sharpe"],
        })
    return results


# ---------------------------------------------------------------------------
# Gate evaluation — mirrors the philosophy of src/validation_gate.py but
# tuned to daily timeframe (lower trade count, FX-appropriate Sharpe).
# ---------------------------------------------------------------------------


def evaluate_gate(in_sample: dict, oos: dict, stress_2x_fees: dict,
                  stress_2x_slip: dict, wf_results: list[dict], cfg: dict) -> dict:
    failed: list[str] = []

    pf = in_sample.get("profit_factor", 0.0)
    if pf == float("inf"):
        failed.append("profit factor is infinite (suspicious)")
    elif pf < cfg["min_profit_factor"]:
        failed.append(f"profit factor {pf:.2f} below {cfg['min_profit_factor']:.2f}")

    oos_pf = oos.get("profit_factor", 0.0)
    if oos_pf < cfg["min_oos_profit_factor"]:
        failed.append(f"out-of-sample profit factor {oos_pf:.2f} below {cfg['min_oos_profit_factor']:.2f}")

    dd = in_sample.get("max_drawdown_pct", 100.0)
    if dd > cfg["max_drawdown_pct"]:
        failed.append(f"max drawdown {dd:.1f}% above {cfg['max_drawdown_pct']:.1f}%")

    sharpe = in_sample.get("sharpe", 0.0)
    if sharpe < cfg["min_sharpe"]:
        failed.append(f"sharpe {sharpe:.2f} below {cfg['min_sharpe']:.2f}")

    trades = in_sample.get("trades", 0)
    if trades < cfg["min_trades_per_asset"]:
        failed.append(f"trades {trades} below {cfg['min_trades_per_asset']}")

    strategy_ret = in_sample.get("strategy_return_pct", 0.0)
    buy_hold = in_sample.get("buy_and_hold_return_pct", 0.0)
    if strategy_ret <= buy_hold:
        failed.append(f"strategy return {strategy_ret:.1f}% does not beat buy-and-hold {buy_hold:.1f}%")

    if not stress_2x_fees.get("profit_factor", 0.0) >= 1.0:
        failed.append("doubled-fees stress test not profitable")
    if not stress_2x_slip.get("profit_factor", 0.0) >= 1.0:
        failed.append("doubled-slippage stress test not profitable")

    if wf_results:
        wf_passes = sum(1 for w in wf_results if w["profit_factor"] >= 1.0)
        if wf_passes < len(wf_results) - 1:  # allow at most 1 losing window
            failed.append(f"walk-forward unstable: {wf_passes}/{len(wf_results)} windows profitable")

    passed = not failed
    return {
        "passed": passed,
        "status": "PASS_MICRO_LIVE_CANDIDATE" if passed else "BLOCK_LIVE",
        "recommended_mode": "BACKTEST_ONLY",  # Phase 10 NEVER unlocks live by itself
        "failed_rules": failed,
    }


# ---------------------------------------------------------------------------
# Orchestration: run all variants × symbols and emit a markdown verdict.
# ---------------------------------------------------------------------------


def load_settings_validation(repo_root: Path) -> dict:
    """Read config/settings.yaml read-only just so we can echo the project's
    validation thresholds in the verdict header. Never writes."""
    path = repo_root / "config" / "settings.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def run_phase10(
    data_by_symbol: dict[str, pd.DataFrame],
    cfg: dict | None = None,
    variants: tuple[str, ...] = PHASE10_VARIANTS,
) -> dict:
    """Run all variants on each symbol's daily OHLCV DataFrame.

    Args
    ----
    data_by_symbol : dict[symbol -> daily OHLCV DataFrame with columns
        ['open','high','low','close','volume'] indexed by Timestamp]
    cfg : optional override of DEFAULT_CONFIG
    variants : which variants to run
    """
    cfg = {**DEFAULT_CONFIG, **(cfg or {})}
    output: dict = {"variants": variants, "symbols": list(data_by_symbol.keys()),
                    "results": {}, "gates": {}, "config": cfg}

    for symbol, df in data_by_symbol.items():
        output["results"][symbol] = {}
        output["gates"][symbol] = {}
        if len(df) < cfg["ema_regime"] + 50:
            # Not enough data to evaluate the EMA(200) regime fairly.
            for v in variants:
                output["gates"][symbol][v] = {
                    "passed": False, "status": "BLOCK_LIVE",
                    "failed_rules": [f"insufficient history: {len(df)} bars"],
                    "recommended_mode": "BACKTEST_ONLY",
                }
            continue
        in_df, oos_df = split_oos(df, cfg["oos_fraction"])
        for v in variants:
            in_res = _backtest_variant(in_df, v, symbol, cfg)
            oos_res = _backtest_variant(oos_df, v, symbol, cfg)
            stress_fees = _backtest_variant(
                in_df, v, symbol, cfg,
                fee_bps=cfg["commission_bps_per_side"] * cfg["stress_fee_multiplier"],
            )
            stress_slip = _backtest_variant(
                in_df, v, symbol, cfg,
                slip_bps=cfg["slippage_bps_per_side"] * cfg["stress_slippage_multiplier"],
            )
            wf = walk_forward(df, v, symbol, cfg, cfg["wf_windows"])
            gate = evaluate_gate(in_res.metrics, oos_res.metrics,
                                 stress_fees.metrics, stress_slip.metrics, wf, cfg)
            output["results"][symbol][v] = {
                "in_sample": in_res.metrics,
                "out_of_sample": oos_res.metrics,
                "stress_2x_fees": stress_fees.metrics,
                "stress_2x_slip": stress_slip.metrics,
                "walk_forward": wf,
            }
            output["gates"][symbol][v] = gate
    return output


def _render_compare_markdown(baseline: dict, filtered: dict,
                             filter_cfg: dict) -> str:
    """Render a side-by-side comparison of baseline vs filtered Phase 10.

    The table shows trades / PF / max DD / net profit for every (symbol,
    variant) pair. We never imply a filter "wins" — we just surface the
    deltas honestly. The reader (and the Phase 10 gate) decides.
    """
    lines: list[str] = [
        "# Phase 10 — Filter Comparison",
        "",
        "Side-by-side comparison of baseline (no filters) vs filtered "
        "backtests. Both runs use the **same non-optimized** variant"
        " parameters; the only difference is the entry filter layer.",
        "",
        "## Filter configuration (filtered run)",
        "",
        f"- Session filter: enabled (skip Friday & Sunday entries)",
        f"- Regime filter:  enabled, regimes allowed = "
        f"`{filter_cfg.get('regimes_allowed')}`",
        "",
        "## Per-variant metrics (in-sample)",
        "",
        "| Symbol | Variant | Metric | Baseline | Filtered | Δ |",
        "|---|---|---|---:|---:|---:|",
    ]

    symbols = baseline.get("symbols", [])
    variants = baseline.get("variants", [])
    for symbol in symbols:
        b_sym = baseline.get("results", {}).get(symbol, {})
        f_sym = filtered.get("results", {}).get(symbol, {})
        for variant in variants:
            b = (b_sym.get(variant) or {}).get("in_sample", {})
            f = (f_sym.get(variant) or {}).get("in_sample", {})
            if not b and not f:
                continue
            for metric, fmt in (
                ("trades", "{:.0f}"),
                ("profit_factor", "{:.2f}"),
                ("max_drawdown_pct", "{:.1f}"),
                ("sharpe", "{:.2f}"),
                ("net_profit", "{:.0f}"),
            ):
                bv = b.get(metric, 0.0) or 0.0
                fv = f.get(metric, 0.0) or 0.0
                delta = fv - bv
                lines.append(
                    f"| {symbol} | {variant} | {metric} | "
                    f"{fmt.format(bv)} | {fmt.format(fv)} | "
                    f"{fmt.format(delta)} |"
                )

    lines += [
        "",
        "## Gate status",
        "",
        "| Symbol | Variant | Baseline gate | Filtered gate |",
        "|---|---|---|---|",
    ]
    for symbol in symbols:
        for variant in variants:
            b_gate = ((baseline.get("gates", {}).get(symbol) or {})
                      .get(variant) or {})
            f_gate = ((filtered.get("gates", {}).get(symbol) or {})
                      .get(variant) or {})
            lines.append(
                f"| {symbol} | {variant} | "
                f"{b_gate.get('status', '?')} | "
                f"{f_gate.get('status', '?')} |"
            )

    lines += [
        "",
        "## Safety",
        "",
        "Every variant on every symbol — in both runs — still recommends "
        "`BACKTEST_ONLY`. Filters are an entry mask; they do not unlock "
        "any live-trading flag. See [SAFETY.md](../SAFETY.md).",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_verdict_markdown(report: dict, repo_root: Path) -> str:
    cfg = report["config"]
    lines = [
        "# Phase 10 Verdict — FX / Gold Daily Trend Discovery",
        "",
        "## Status",
        "",
        "Live trading remains **BACKTEST_ONLY**. This module never unlocks live mode.",
        "Any 'PASS' below means the candidate variant qualifies for **manual review**",
        "as a MICRO_LIVE candidate. Live activation still requires explicit owner approval.",
        "",
        "## Gate thresholds (daily timeframe)",
        "",
        f"- Min profit factor: {cfg['min_profit_factor']:.2f}",
        f"- Min OOS profit factor: {cfg['min_oos_profit_factor']:.2f}",
        f"- Max drawdown: {cfg['max_drawdown_pct']:.1f}%",
        f"- Min Sharpe: {cfg['min_sharpe']:.2f}",
        f"- Min trades per asset: {cfg['min_trades_per_asset']}",
        "- Must beat buy-and-hold of the same asset",
        "- Must survive 2x fees and 2x slippage (PF >= 1.0)",
        "- Walk-forward: at most 1 losing window of N",
        "",
        "## Variants (non-optimized defaults)",
        "",
        "- V0: long-only EMA200 regime + EMA21/55 trend + RSI(14) cross 50, ATR(14)*2 stop, EMA21 trail",
        "- V1: V0 mirrored both sides",
        "- V2: long-only Donchian(20) breakout with EMA200 regime, Donchian(10) exit",
        "- V3: both-sides Bollinger squeeze breakout, mid-band exit",
        "",
        "## Results",
        "",
    ]

    for symbol in report["symbols"]:
        lines.append(f"### {symbol}")
        lines.append("")
        lines.append("| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for v in report["variants"]:
            r = report["results"].get(symbol, {}).get(v)
            g = report["gates"].get(symbol, {}).get(v, {})
            if r is None:
                lines.append(f"| {v} | — | — | — | — | — | — | — | — | {g.get('status', 'N/A')} |")
                continue
            ins = r["in_sample"]
            oos = r["out_of_sample"]
            verdict = "PASS_CANDIDATE" if g.get("passed") else "BLOCK"
            lines.append(
                f"| {v} | {ins['trades']} | {ins['win_rate']:.1f} | {ins['profit_factor']:.2f} "
                f"| {oos['profit_factor']:.2f} | {ins['max_drawdown_pct']:.1f} "
                f"| {ins['sharpe']:.2f} | {ins['strategy_return_pct']:.1f} "
                f"| {ins['buy_and_hold_return_pct']:.1f} | {verdict} |"
            )
        lines.append("")
        # Failed-rule detail
        for v in report["variants"]:
            g = report["gates"].get(symbol, {}).get(v, {})
            if not g.get("passed") and g.get("failed_rules"):
                lines.append(f"**{symbol} / {v} failed rules:**")
                lines.extend([f"- {rule}" for rule in g["failed_rules"]])
                lines.append("")

    lines.extend([
        "## Safety reminder",
        "",
        "- `risk.mode` remains `BACKTEST_ONLY`.",
        "- `LIVE_TRADING`, `MICRO_LIVE`, `FULL_LIVE` remain `false`.",
        "- No API keys are added by this module.",
        "- A `PASS_CANDIDATE` verdict is research signal only and does not authorize",
        "  any live order. See SAFETY.md.",
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Accept timestamp/datetime/date column
    for col in ("timestamp", "datetime", "date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
            df = df.set_index(col).sort_index()
            break
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df[["open", "high", "low", "close", "volume"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 10 — FX/Gold daily research")
    parser.add_argument("--data-dir", default="data/raw",
                        help="Directory containing <symbol>_1d.csv files")
    parser.add_argument("--symbols", nargs="+",
                        default=list(PRIMARY_SYMBOLS) + list(CONTROL_SYMBOLS))
    parser.add_argument("--output", default="reports/phase10_verdict.md")
    parser.add_argument("--json-output", default="reports/phase10_verdict.json")
    parser.add_argument(
        "--filters", choices=["off", "session", "regime", "both"],
        default="off",
        help="Apply Phase 10 PR 5 filters. 'off' reproduces the PR 2 baseline.",
    )
    parser.add_argument(
        "--regimes-allowed", nargs="+", default=None,
        help="Whitelist of regimes (trending/ranging/choppy). "
             "Default: all except 'unknown'.",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="Run BOTH baseline and filtered variants; write a side-by-side "
             "comparison report to reports/phase10_filter_compare.md.",
    )
    args = parser.parse_args(argv)

    cfg_override: dict = {}
    if args.filters in ("session", "both"):
        cfg_override["enable_session_filter"] = True
    if args.filters in ("regime", "both"):
        cfg_override["enable_regime_filter"] = True
    if args.regimes_allowed:
        cfg_override["regimes_allowed"] = args.regimes_allowed

    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / args.data_dir

    data_by_symbol: dict[str, pd.DataFrame] = {}
    for symbol in args.symbols:
        candidates = [
            data_dir / f"{symbol.lower()}_1d.csv",
            data_dir / f"{symbol}_1d.csv",
            data_dir / f"{symbol.lower()}_daily.csv",
        ]
        path = next((p for p in candidates if p.exists()), None)
        if path is None:
            print(f"[phase10] WARN: no daily CSV found for {symbol} in {data_dir}")
            continue
        data_by_symbol[symbol] = _load_csv(path)

    if not data_by_symbol:
        print("[phase10] No data found. PR 3 will provide the data downloader.")
        # Still write a placeholder verdict so dashboards have something to read.
        placeholder = {
            "variants": PHASE10_VARIANTS,
            "symbols": list(args.symbols),
            "results": {},
            "gates": {s: {v: {"passed": False, "status": "BLOCK_LIVE",
                              "failed_rules": ["no data available yet — see PR 3"],
                              "recommended_mode": "BACKTEST_ONLY"}
                          for v in PHASE10_VARIANTS} for s in args.symbols},
            "config": DEFAULT_CONFIG,
        }
        out_path = repo_root / args.output
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_verdict_markdown(placeholder, repo_root))
        json_path = repo_root / args.json_output
        json_path.write_text(json.dumps(placeholder, default=str, indent=2))
        return 0

    report = run_phase10(data_by_symbol, cfg=cfg_override or None)
    out_path = repo_root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_verdict_markdown(report, repo_root))
    json_path = repo_root / args.json_output
    json_path.write_text(json.dumps(report, default=str, indent=2))
    print(f"[phase10] Wrote {out_path}")
    print(f"[phase10] Wrote {json_path}")

    if args.compare:
        baseline_report = run_phase10(data_by_symbol, cfg=None)
        filtered_cfg = {
            "enable_session_filter": True,
            "enable_regime_filter": True,
            "regimes_allowed": args.regimes_allowed or ["trending"],
        }
        filtered_report = run_phase10(data_by_symbol, cfg=filtered_cfg)
        compare_md = _render_compare_markdown(
            baseline_report, filtered_report, filtered_cfg
        )
        compare_path = repo_root / "reports" / "phase10_filter_compare.md"
        compare_path.parent.mkdir(parents=True, exist_ok=True)
        compare_path.write_text(compare_md)
        print(f"[phase10] Wrote {compare_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

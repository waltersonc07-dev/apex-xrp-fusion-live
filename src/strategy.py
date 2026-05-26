from __future__ import annotations

import pandas as pd

from .indicators import atr, dema, ema, rsi, supertrend


def _near_level(price: float, levels: list[float], buffer_pct: float) -> bool:
    if not levels:
        return False
    return any(abs(price - level) / price * 100 <= buffer_pct for level in levels)


def _next_level(price: float, levels: list[float], side: str) -> float | None:
    if side == "long":
        candidates = [level for level in levels if level > price]
        return min(candidates) if candidates else None
    candidates = [level for level in levels if level < price]
    return max(candidates) if candidates else None


def _adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    atr_values = atr(df, length).replace(0, float("nan"))
    plus_di = 100 * plus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr_values
    minus_di = 100 * minus_dm.ewm(alpha=1 / length, adjust=False).mean() / atr_values
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, float("nan"))) * 100
    return dx.ewm(alpha=1 / length, adjust=False).mean().fillna(0.0)


def _four_hour_dema_slope(close: pd.Series, length: int, lookback_bars: int = 5) -> pd.Series:
    if not isinstance(close.index, pd.DatetimeIndex):
        return pd.Series(0.0, index=close.index)
    close_4h = close.resample("4h", label="right", closed="right").last().dropna()
    dema_4h = dema(close_4h, length)
    slope_4h = dema_4h - dema_4h.shift(lookback_bars)
    return slope_4h.reindex(close.index, method="ffill").fillna(0.0)


def generate_signals(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    cfg = config["strategy"]
    levels = config["levels"]
    out = df.copy()
    st = supertrend(out, cfg["supertrend_atr_length"], cfg["supertrend_multiplier"])
    out["ema_fast"] = ema(out["close"], cfg["ema_fast"])
    out["ema_slow"] = ema(out["close"], cfg["ema_slow"])
    out["dema_200"] = dema(out["close"], cfg["dema_length"])
    out["atr"] = atr(out, cfg["atr_length"])
    out["supertrend"] = st["supertrend"]
    out["supertrend_dir"] = st["direction"]
    if cfg.get("adx_min") is not None:
        out["adx"] = _adx(out, int(cfg.get("adx_length", 14)))
    if cfg.get("use_rsi_momentum"):
        out["rsi"] = rsi(out["close"], int(cfg.get("rsi_length", 14)))
    if cfg.get("use_4h_dema_slope"):
        out["dema_4h_slope"] = _four_hour_dema_slope(out["close"], cfg["dema_length"])

    long_states = []
    short_states = []
    long_signals = []
    short_signals = []
    stops = []
    targets = []
    rr_values = []

    for _, row in out.iterrows():
        price = float(row["close"])
        long_stop = price - float(row["atr"]) * cfg["stop_atr_mult"]
        long_tp = price + float(row["atr"]) * cfg["tp_atr_mult"]
        short_stop = price + float(row["atr"]) * cfg["stop_atr_mult"]
        short_tp = price - float(row["atr"]) * cfg["tp_atr_mult"]

        nearest_resistance = _next_level(price, levels["resistance"], "long")
        nearest_support = _next_level(price, levels["support"], "short")
        long_target = min(long_tp, nearest_resistance) if nearest_resistance else long_tp
        short_target = max(short_tp, nearest_support) if nearest_support else short_tp

        long_rr = (long_target - price) / max(price - long_stop, 1e-12)
        short_rr = (price - short_target) / max(short_stop - price, 1e-12)
        long_blocked = _near_level(price, levels["resistance"][:3], cfg["resistance_buffer_pct"])
        short_blocked = _near_level(price, levels["support"][:3], cfg["support_buffer_pct"])
        long_location_ok = True
        short_location_ok = True
        if cfg.get("use_pullback_location"):
            location_buffer = float(cfg.get("pullback_buffer_pct", 0.75))
            long_location_ok = _near_level(price, levels["support"], location_buffer)
            short_location_ok = _near_level(price, levels["resistance"], location_buffer)
        long_4h_ok = True
        short_4h_ok = True
        if cfg.get("use_4h_dema_slope"):
            long_4h_ok = float(row["dema_4h_slope"]) > 0
            short_4h_ok = float(row["dema_4h_slope"]) < 0
        adx_ok = True
        if cfg.get("adx_min") is not None:
            adx_ok = float(row["adx"]) >= float(cfg["adx_min"])
        long_rsi_ok = True
        short_rsi_ok = True
        if cfg.get("use_rsi_momentum"):
            long_rsi_ok = float(row["rsi"]) >= float(cfg.get("rsi_long_min", 50))
            short_rsi_ok = float(row["rsi"]) <= float(cfg.get("rsi_short_max", 50))

        long_state = (
            cfg.get("trade_longs", True)
            and row["supertrend_dir"] == 1
            and row["ema_fast"] > row["ema_slow"]
            and price > row["dema_200"]
            and not long_blocked
            and long_rr >= cfg["min_rr"]
            and long_location_ok
            and long_4h_ok
            and adx_ok
            and long_rsi_ok
        )
        short_state = (
            cfg.get("trade_shorts", True)
            and row["supertrend_dir"] == -1
            and row["ema_fast"] < row["ema_slow"]
            and price < row["dema_200"]
            and not short_blocked
            and short_rr >= cfg["min_rr"]
            and short_location_ok
            and short_4h_ok
            and adx_ok
            and short_rsi_ok
        )
        long_states.append(bool(long_state))
        short_states.append(bool(short_state))
        stops.append(long_stop if long_state else short_stop if short_state else None)
        targets.append(long_target if long_state else short_target if short_state else None)
        rr_values.append(long_rr if long_state else short_rr if short_state else None)

    out["long_state"] = long_states
    out["short_state"] = short_states
    out["long_signal"] = out["long_state"] & ~out["long_state"].shift(fill_value=False)
    out["short_signal"] = out["short_state"] & ~out["short_state"].shift(fill_value=False)
    out["stop_loss"] = stops
    out["take_profit"] = targets
    out["rr"] = rr_values
    return out

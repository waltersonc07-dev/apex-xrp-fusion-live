from __future__ import annotations

import pandas as pd

from .indicators import atr, dema, ema, supertrend


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

        long_state = (
            row["supertrend_dir"] == 1
            and row["ema_fast"] > row["ema_slow"]
            and price > row["dema_200"]
            and not long_blocked
            and long_rr >= cfg["min_rr"]
        )
        short_state = (
            row["supertrend_dir"] == -1
            and row["ema_fast"] < row["ema_slow"]
            and price < row["dema_200"]
            and not short_blocked
            and short_rr >= cfg["min_rr"]
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


from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def dema(series: pd.Series, length: int) -> pd.Series:
    first = ema(series, length)
    second = ema(first, length)
    return 2 * first - second


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / length, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / length, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def supertrend(df: pd.DataFrame, length: int = 12, multiplier: float = 3.0) -> pd.DataFrame:
    data = df.copy()
    data["atr"] = atr(data, length)
    hl2 = (data["high"] + data["low"]) / 2
    upper_basic = hl2 + multiplier * data["atr"]
    lower_basic = hl2 - multiplier * data["atr"]

    upper = upper_basic.copy()
    lower = lower_basic.copy()
    direction = pd.Series(1, index=data.index, dtype=int)
    line = pd.Series(np.nan, index=data.index, dtype=float)

    for i in range(1, len(data)):
        prev = data.index[i - 1]
        cur = data.index[i]
        if upper_basic.loc[cur] < upper.loc[prev] or data["close"].loc[prev] > upper.loc[prev]:
            upper.loc[cur] = upper_basic.loc[cur]
        else:
            upper.loc[cur] = upper.loc[prev]

        if lower_basic.loc[cur] > lower.loc[prev] or data["close"].loc[prev] < lower.loc[prev]:
            lower.loc[cur] = lower_basic.loc[cur]
        else:
            lower.loc[cur] = lower.loc[prev]

        if direction.loc[prev] == -1 and data["close"].loc[cur] > upper.loc[cur]:
            direction.loc[cur] = 1
        elif direction.loc[prev] == 1 and data["close"].loc[cur] < lower.loc[cur]:
            direction.loc[cur] = -1
        else:
            direction.loc[cur] = direction.loc[prev]

        line.loc[cur] = lower.loc[cur] if direction.loc[cur] == 1 else upper.loc[cur]

    line.iloc[0] = lower.iloc[0]
    return pd.DataFrame({"supertrend": line, "direction": direction, "atr": data["atr"]}, index=data.index)


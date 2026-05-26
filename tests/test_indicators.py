import pandas as pd

from src.indicators import atr, dema, ema, supertrend


def sample_df():
    return pd.DataFrame({
        "open": [1, 2, 3, 4, 5, 6],
        "high": [2, 3, 4, 5, 6, 7],
        "low": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
        "close": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
        "volume": [100] * 6,
    })


def test_ema_calculation():
    result = ema(pd.Series([1, 2, 3]), 2)
    assert round(result.iloc[-1], 4) == 2.5556


def test_dema_calculation():
    result = dema(pd.Series([1, 2, 3, 4]), 2)
    assert result.iloc[-1] > ema(pd.Series([1, 2, 3, 4]), 2).iloc[-1]


def test_atr_calculation():
    result = atr(sample_df(), 3)
    assert result.notna().all()
    assert result.iloc[-1] > 0


def test_supertrend_direction():
    result = supertrend(sample_df(), 3, 2)
    assert set(result["direction"].unique()).issubset({-1, 1})


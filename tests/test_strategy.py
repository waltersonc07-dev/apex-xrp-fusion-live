import pandas as pd

from src.strategy import generate_signals


def config():
    return {
        "strategy": {
            "supertrend_atr_length": 3,
            "supertrend_multiplier": 1.5,
            "ema_fast": 2,
            "ema_slow": 3,
            "dema_length": 3,
            "atr_length": 3,
            "stop_atr_mult": 1.5,
            "tp_atr_mult": 3.0,
            "min_rr": 1.9,
            "resistance_buffer_pct": 0.01,
            "support_buffer_pct": 0.01,
        },
        "levels": {"resistance": [100], "support": [0.1]},
    }


def test_long_signal_transition():
    df = pd.DataFrame({
        "open": [1, 2, 3, 4, 5, 6, 7],
        "high": [2, 3, 4, 5, 6, 7, 8],
        "low": [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
        "close": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5],
        "volume": [100] * 7,
    })
    out = generate_signals(df, config())
    assert out["long_signal"].sum() <= out["long_state"].sum()
    assert not (out["long_signal"] & out["long_signal"].shift(fill_value=False)).any()


def test_short_signal_transition():
    df = pd.DataFrame({
        "open": [7, 6, 5, 4, 3, 2, 1],
        "high": [8, 7, 6, 5, 4, 3, 2],
        "low": [6.5, 5.5, 4.5, 3.5, 2.5, 1.5, 0.5],
        "close": [7.5, 6.5, 5.5, 4.5, 3.5, 2.5, 1.5],
        "volume": [100] * 7,
    })
    out = generate_signals(df, config())
    assert out["short_signal"].sum() <= out["short_state"].sum()
    assert not (out["short_signal"] & out["short_signal"].shift(fill_value=False)).any()


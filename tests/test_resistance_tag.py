"""Tests for notify-only v3.4-tag entry context tags (no network)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.alert_notify import format_alert
from src.resistance_tag import EntryTagger, format_tag, pivots


def test_pivots_confirmed_only_and_strict_left():
    v = np.array([1, 2, 5, 3, 2, 1, 1, 5, 5, 2, 1.0])
    ph = pivots(v, 2, 2, "high")
    assert ph[2] == 5          # clean pivot
    assert np.isnan(ph[8])     # equal to left neighbour -> not a pivot (strict left)
    assert ph[7] == 5          # ties allowed on the right
    assert np.isnan(ph[-1]) and np.isnan(ph[-2])  # cannot be confirmed yet


def _synthetic(n=2000):
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    t = np.arange(n)
    close = 1.0 + 0.05 * np.sin(t / 60.0) + 0.0001 * t
    df = pd.DataFrame({"open": close, "high": close + 0.004, "low": close - 0.004, "close": close, "volume": 1.0}, index=idx)
    df["open"] = df["close"].shift(1).fillna(df["close"].iloc[0])
    return df


def test_tag_uses_only_completed_htf_bars():
    df = _synthetic()
    ts = df.index[1600]
    base = EntryTagger(df).tag(ts)
    # mutate the future (and the current, still-forming 2H bar after ts): tag must not change
    fut = df.copy()
    fut.loc[fut.index > ts, ["high", "close", "open"]] += 1.0
    assert EntryTagger(fut).tag(ts)["res_level"] == base["res_level"] or (
        np.isnan(base["res_level"]) and np.isnan(EntryTagger(fut).tag(ts)["res_level"]))


def test_format_and_alert_passthrough():
    txt = format_tag("NEAR", 1.5464, 0.0153, "2H", False, np.nan, np.nan, True)
    assert txt == "⚠️ Near resistance 1.5464 (+0.02 ATR2H, 2H) | rejection candle"
    raw = ('{"action":"ENTRY","strategy":"StackedMTF_v3.4tag","symbol":"XRPUSDT","tf":"15","price":1.546,'
           '"note":"Long entry — 15m+2H stack synced | ' + txt + '","res_state":"NEAR","res_level":1.5464,'
           '"res_atr2h":0.015,"res_tf":"2H","rejection":true,"triangle":false,"tri_upper":null,"tri_lower":null}')
    payload = json.loads(raw)
    out = format_alert(payload)
    assert "Near resistance 1.5464" in out and out.startswith("ENTRY XRPUSDT @ 1.546")

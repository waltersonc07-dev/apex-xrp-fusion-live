"""Notify-only caution lines for Stacked MTF v3.5 TEST (Python reference of the Pine block).

Mirror of the "Caution lines + score" section of ``pine/xrp_stacked_mtf_v3.5_test.pine``.
It NEVER changes entries, exits or sizing and never places orders. It only builds the
text appended to ENTRY alerts. Every value uses closed bars only:

* ``shooting_star``: bearish mirror of the research WICK rule
  (analysis/yt_J8tcoEiCI7k/cs_lib.py) on 15m bars: upper wick >= 2 x body and
  >= 50% of range, lower wick <= 30% of range, range >= 0.5 x ATR(14), after a
  6-bar rise (close[i-1] > close[i-7]). ``star_recent`` = on bar i or any of the
  7 bars before it (8 closed 15m bars = the last 2 hours).
* ``bear_mom_res``: the research 2H "MOM at KEY" short trigger, used as a warning
  for longs. On the last COMPLETED 2H bar: two red bars, the 2nd body bigger, and a
  KEY double-top touch (last two confirmed swing highs, pivot L=R=5, within
  1 x ATR14(2H); high within +/-0.5 ATR of the latest; close below it) on that bar
  or the 3 before it. Pivot: strictly above the 5 left highs, >= the 5 right highs.
* near resistance: ``src.resistance_tag`` (v3.4-tag) state == "NEAR".
* macro: a scheduled CPI / NFP / FOMC release 0..24h after the bar close.

The 2H bars are built from 15m bars the same way the Pine script builds them
(new bar when the UTC 2H bucket changes), so a 2H value is only used after the
bar has fully completed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WARN_ORDER = ("macro", "star", "bearmom", "near")
LINES = {
    "star": "⚠ shooting star <2h",
    "bearmom": "⚠ 2H bear momentum at resistance",
    "near": "⚠ near resistance",
}


def _atr_stream(h, l, c, n):
    """TradingView ta.atr(n): RMA of TR, seeded with the SMA of the first n TRs; TR[0] = high - low."""
    out = np.full(len(c), np.nan)
    s = 0.0
    a = np.nan
    for i in range(len(c)):
        tr = h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if i < n:
            s += tr
            if i == n - 1:
                a = s / n
        else:
            a = (a * (n - 1) + tr) / n
        out[i] = a
    return out


def shooting_star(df15: pd.DataFrame, atr_len: int = 14) -> np.ndarray:
    o, h, l, c = (df15[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    at = _atr_stream(h, l, c, atr_len)
    body = np.abs(c - o)
    rng = h - l
    uw = h - np.maximum(o, c)
    lw = np.minimum(o, c) - l
    c1 = np.r_[np.nan, c[:-1]]
    c7 = np.r_[np.full(7, np.nan), c[:-7]]
    with np.errstate(invalid="ignore"):
        star = (uw >= 2.0 * body) & (uw >= 0.5 * rng) & (lw <= 0.3 * rng) & (rng >= 0.5 * at) & (c1 > c7)
    return np.nan_to_num(star).astype(bool)


def star_recent(star: np.ndarray, bars: int = 8) -> np.ndarray:
    return pd.Series(star.astype(float)).rolling(bars, min_periods=1).max().to_numpy() > 0


def bear_mom_res(df15: pd.DataFrame, piv: int = 5, key_look: int = 4, atr_len: int = 14, tf: str = "2h") -> np.ndarray:
    """Streaming mirror of Pine f_bearMomRes: value on each 15m bar = signal of the last completed 2H bar."""
    o, h, l, c = (df15[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    bucket = df15.index.floor(tf).asi8
    out = np.zeros(len(c), bool)
    cO = cH = cL = cC = pC = atrR = np.nan
    trSum, trN = 0.0, 0
    hs: list[float] = []
    keyQ: list[bool] = []
    phCur = phPrev = prvO = prvC = np.nan
    sig = False
    for i in range(len(c)):
        newBar = i == 0 or bucket[i] != bucket[i - 1]
        if newBar and not np.isnan(cC):
            tr = cH - cL if np.isnan(pC) else max(cH - cL, abs(cH - pC), abs(cL - pC))
            if trN < atr_len:
                trSum += tr
                trN += 1
                if trN == atr_len:
                    atrR = trSum / atr_len
            else:
                atrR = (atrR * (atr_len - 1) + tr) / atr_len
            pC = cC
            hs.append(cH)
            if len(hs) > 2 * piv + 1:
                hs.pop(0)
            if len(hs) == 2 * piv + 1:
                ch = hs[piv]
                if all(hs[m] < ch for m in range(piv)) and all(hs[m] <= ch for m in range(piv + 1, 2 * piv + 1)):
                    phPrev, phCur = phCur, ch
            major = not np.isnan(phCur) and not np.isnan(phPrev) and not np.isnan(atrR) and abs(phCur - phPrev) <= atrR
            key = bool(major and phCur - 0.5 * atrR <= cH <= phCur + 0.5 * atrR and cC < phCur)
            keyQ.append(key)
            if len(keyQ) > key_look:
                keyQ.pop(0)
            mom = (not np.isnan(prvO)) and cC < cO and prvC < prvO and abs(cC - cO) > abs(prvC - prvO)
            sig = bool(mom and any(keyQ))
            prvO, prvC = cO, cC
        if newBar or np.isnan(cH):
            cO, cH, cL, cC = o[i], h[i], l[i], c[i]
        else:
            cH = max(cH, h[i])
            cL = min(cL, l[i])
            cC = c[i]
        out[i] = sig
    return out


def macro_due(close_times_utc: pd.DatetimeIndex, events_utc: list[pd.Timestamp], ahead_h: float = 24.0) -> np.ndarray:
    """True when a release time t satisfies 0 <= t - bar_close <= ahead_h (Pine f_macro on time_close)."""
    ev = np.sort(np.array([pd.Timestamp(t).as_unit("ns").value for t in events_utc], dtype=np.int64))
    tc = pd.DatetimeIndex(close_times_utc).as_unit("ns").asi8   # pandas 3 may store us/s units
    j = np.searchsorted(ev, tc, side="left")
    nxt = np.where(j < len(ev), ev[np.minimum(j, len(ev) - 1)], np.iinfo(np.int64).max)
    return (nxt - tc) <= int(ahead_h * 3600e9)


def caution_score(warn: dict) -> int:
    return int(sum(bool(warn.get(k)) for k in WARN_ORDER))


def caution_text(warn: dict) -> str:
    """Lines appended AFTER the existing macro line (Pine cautionTxt). Uses real newlines."""
    n = caution_score(warn)
    out = [LINES[k] for k in ("star", "bearmom", "near") if warn.get(k)]
    risk = "Risk: consider HALF size (advisory only — rules unchanged)" if n >= 2 else "Risk: normal size per plan (advisory)"
    out.append(f"Caution {n}/4 · {risk}")
    return "\n".join(out)

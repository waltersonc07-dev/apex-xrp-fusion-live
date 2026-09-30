"""Notify-only entry context tags for Stacked MTF (v3.4-tag).

Python reference for the Pine logic in ``pine/xrp_stacked_mtf_v3.4_tag.pine``.
It never changes entries or exits and never places orders. It only builds the
text appended to ENTRY alerts.

Every value for an entry on the first 15m bar of HTF period k uses completed
HTF bars <= k-1 only (confirmed pivots, no lookahead):

* Nearest overhead resistance: the lowest confirmed swing-high pivot above the
  entry close. Pivots come from 2H (left/right = 3) and 4H (left/right = 2), within
  the last ``lookback`` HTF bars. Distance is measured in ATR(12) of the last
  closed 2H bar. NEAR when the distance is <= ``near_atr`` (default 1.0).
* Triangle / compression (2H): the last ``n_piv`` confirmed pivot highs are
  strictly descending AND the last ``n_piv`` pivot lows are strictly ascending.
  Upper and lower lines run through the last two pivots of each side, projected
  to bar k. The entry counts as "inside" when lower <= close <= upper, and upper
  must still be > lower (apex not passed).
* Rejection note (only reported when NEAR): the entry bar or the prior 15m bar
  has upper wick > 2 x body, or close-location (close-low)/(high-low) < 0.4.

Pivot definition: high[j] is the max of window [j-L, j+R], strictly greater than
the L bars on its left (ties allowed on the right). Pivot lows mirror this.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

AGG = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}


def resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    cols = [c for c in AGG if c in df.columns]
    out = df[cols].resample(rule, label="left", closed="left").agg({c: AGG[c] for c in cols})
    return out.dropna(subset=["close"])


def atr_rma(df: pd.DataFrame, length: int = 12) -> np.ndarray:
    """TradingView ta.atr: RMA of true range, seeded with the SMA of the first ``length`` TRs."""
    h, l, c = (df[k].to_numpy(float) for k in ("high", "low", "close"))
    pc = np.r_[np.nan, c[:-1]]
    tr = np.where(np.isnan(pc), h - l, np.maximum.reduce([h - l, np.abs(h - pc), np.abs(l - pc)]))
    out = np.full(len(tr), np.nan)
    if len(tr) < length:
        return out
    out[length - 1] = tr[:length].mean()
    for i in range(length, len(tr)):
        out[i] = (out[i - 1] * (length - 1) + tr[i]) / length
    return out


def pivots(values: np.ndarray, left: int, right: int, kind: str = "high") -> np.ndarray:
    """Pivot value at the pivot bar index (NaN elsewhere). Confirmed at index j + right."""
    v = values if kind == "high" else -values
    n = len(v)
    out = np.full(n, np.nan)
    for j in range(left, n - right):
        w = v[j - left : j + right + 1]
        if v[j] == w.max() and (v[j - left : j] < v[j]).all():
            out[j] = values[j]
    return out


def _active(piv: np.ndarray, k: int, right: int, lookback: int) -> list[int]:
    """Indices j of pivots confirmed by bar k-1 (j + right <= k - 1) and within lookback (k - j <= lookback)."""
    lo = max(0, k - lookback)
    return [j for j in range(lo, max(lo, k - right)) if not np.isnan(piv[j])]


@dataclass
class TagConfig:
    near_atr: float = 1.0
    atr_len: int = 12
    left_2h: int = 3
    right_2h: int = 3
    left_4h: int = 2
    right_4h: int = 2
    lookback: int = 90
    tri_pivots: int = 2
    wick_body_mult: float = 2.0
    clv_weak: float = 0.4


class EntryTagger:
    """Precompute HTF pivots once, then tag any 15m entry timestamp (bar open time, UTC)."""

    def __init__(self, df15: pd.DataFrame, cfg: TagConfig | None = None):
        self.cfg = cfg or TagConfig()
        self.df15 = df15
        c = self.cfg
        self.h2 = resample(df15, "2h")
        self.h4 = resample(df15, "4h")
        self.atr2 = atr_rma(self.h2, c.atr_len)
        self.ph2 = pivots(self.h2["high"].to_numpy(float), c.left_2h, c.right_2h, "high")
        self.pl2 = pivots(self.h2["low"].to_numpy(float), c.left_2h, c.right_2h, "low")
        self.ph4 = pivots(self.h4["high"].to_numpy(float), c.left_4h, c.right_4h, "high")

    def tag(self, ts: pd.Timestamp) -> dict:
        c = self.cfg
        bar = self.df15.loc[ts]
        close = float(bar["close"])
        k2 = int(self.h2.index.searchsorted(ts.floor("2h")))
        k4 = int(self.h4.index.searchsorted(ts.floor("4h")))
        atr2 = self.atr2[k2 - 1] if k2 >= 1 else np.nan
        lv2 = [self.ph2[j] for j in _active(self.ph2, k2, c.right_2h, c.lookback)]
        lv4 = [self.ph4[j] for j in _active(self.ph4, k4, c.right_4h, c.lookback)]
        above = [(v, "2H") for v in lv2 if v > close] + [(v, "4H") for v in lv4 if v > close]
        res, res_tf = (min(above) if above else (np.nan, ""))
        dist = (res - close) / atr2 if above and atr2 > 0 else np.nan
        if np.isnan(atr2):
            res_state = "NA"
        elif not above:
            res_state = "NONE"
        else:
            res_state = "NEAR" if dist <= c.near_atr else "CLEAR"

        # triangle / compression on 2H
        hi_idx = _active(self.ph2, k2, c.right_2h, c.lookback)[-c.tri_pivots:]
        lo_idx = _active(self.pl2, k2, c.right_2h, c.lookback)[-c.tri_pivots:]
        tri, up_line, lo_line = False, np.nan, np.nan
        if len(hi_idx) == c.tri_pivots and len(lo_idx) == c.tri_pivots:
            hv = [self.ph2[j] for j in hi_idx]
            lvv = [self.pl2[j] for j in lo_idx]
            if all(b < a for a, b in zip(hv, hv[1:])) and all(b > a for a, b in zip(lvv, lvv[1:])):
                (j1, j2), (i1, i2) = hi_idx[-2:], lo_idx[-2:]
                up_line = hv[-1] + (hv[-1] - hv[-2]) / (j2 - j1) * (k2 - j2)
                lo_line = lvv[-1] + (lvv[-1] - lvv[-2]) / (i2 - i1) * (k2 - i2)
                tri = bool(up_line > lo_line and lo_line <= close <= up_line)

        # rejection candle note (entry bar or prior 15m bar)
        i = self.df15.index.get_loc(ts)
        rej = False
        for b in (self.df15.iloc[i], self.df15.iloc[i - 1] if i >= 1 else None):
            if b is None:
                continue
            body = abs(b["close"] - b["open"])
            uw = b["high"] - max(b["open"], b["close"])
            rng = b["high"] - b["low"]
            clv = (b["close"] - b["low"]) / rng if rng > 0 else 0.5
            if uw > c.wick_body_mult * body or clv < c.clv_weak:
                rej = True
        return {
            "close": close, "atr2h": atr2, "res_state": res_state, "res_level": res, "res_tf": res_tf,
            "res_atr2h": dist, "triangle": tri, "tri_upper": up_line, "tri_lower": lo_line,
            "rejection": bool(rej and res_state == "NEAR"), "text": format_tag(res_state, res, dist, res_tf, tri, up_line, lo_line, rej),
        }


def format_tag(state, res, dist, tf, tri, up, lo, rej) -> str:
    parts = []
    if state == "NEAR":
        parts.append(f"⚠️ Near resistance {res:.4f} (+{dist:.2f} ATR2H, {tf})")
        if rej:
            parts.append("rejection candle")
    elif state == "CLEAR":
        parts.append(f"✅ Clear to next resistance {res:.4f} (+{dist:.2f} ATR2H, {tf})")
    elif state == "NONE":
        parts.append("✅ No swing-high resistance in lookback")
    else:
        parts.append("resistance n/a (warm-up)")
    if tri:
        parts.append(f"Inside triangle — wait for 2H breakout close (upper {up:.4f} / lower {lo:.4f})")
    return " | ".join(parts)

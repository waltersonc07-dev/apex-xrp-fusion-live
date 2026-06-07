"""Phase 10 — session and regime filters.

Two orthogonal filters that any Phase 10 variant can opt into:

1. **Session filter** (daily timeframe). Pure day-of-week filtering. The most
   defensible cuts on daily bars are:

   - Drop **Friday entries** (gap-over-weekend risk; positions opened on Friday
     close are exposed to Monday's open gap before any stop/TP can fire).
   - Drop **Sunday/Monday open** entries on FX (Sunday-open candles distort
     the daily picture; FX brokers price Sunday very thin liquidity). Gold
     futures GC=F doesn't have this issue but the rule is harmless there
     because GC=F doesn't have a Sunday bar to begin with.

   Both rules are conservative and optional. They are evaluated as
   ``allow_entry(timestamp, cfg) -> bool``.

2. **Regime classifier**. At each bar, classify the market into one of:

   - ``trending``  — ADX(14) >= 25 **and** |EMA200 slope| > slope_threshold
   - ``ranging``   — ADX(14) < 20 and ATR%/close in a normal band
   - ``choppy``    — high ATR% relative to its 60-day median, ADX < 20 (rapid
                     reversals, hard for trend systems)
   - ``unknown``   — not enough warm-up data

   Variants then opt in via ``regimes_allowed`` config. The Phase 10 module
   composes this with the existing variant signals; if a signal fires but the
   regime is not in ``regimes_allowed``, the trade is skipped.

These filters are **research-only**. They never reference live trading flags,
API keys, the XRP strategy, or the validation gate. Test coverage in
``tests/test_phase10_filters.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

import numpy as np
import pandas as pd


Regime = Literal["trending", "ranging", "choppy", "unknown"]


# ---------------------------------------------------------------------------
# Session filter (day-of-week on daily bars)
# ---------------------------------------------------------------------------


DEFAULT_SESSION_CFG = {
    "skip_friday_entries": True,
    "skip_sunday_entries": True,
    "skip_monday_open_entries": False,  # off by default — common false signal
}


def session_allows_entry(timestamp: pd.Timestamp, cfg: dict | None = None) -> bool:
    """Return True iff a new entry is permitted on this daily bar.

    Day-of-week mapping (pandas): Monday=0, ..., Friday=4, Saturday=5, Sunday=6.
    """
    cfg = {**DEFAULT_SESSION_CFG, **(cfg or {})}
    dow = pd.Timestamp(timestamp).weekday()
    if cfg["skip_friday_entries"] and dow == 4:
        return False
    if cfg["skip_sunday_entries"] and dow == 6:
        return False
    if cfg["skip_monday_open_entries"] and dow == 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Indicators needed for regime classification
# ---------------------------------------------------------------------------


def _wilder_ema(series: pd.Series, length: int) -> pd.Series:
    """Wilder's smoothing (used by ADX). Equivalent to EMA with alpha=1/length."""
    alpha = 1.0 / length
    return series.ewm(alpha=alpha, adjust=False, min_periods=length).mean()


def adx(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average Directional Index. Returns a Series aligned with df.index.

    Implementation follows Wilder (1978): smoothed TR, +DM, -DM with Wilder's
    EMA, then DX = 100 * |+DI - -DI| / (+DI + -DI), then ADX = Wilder EMA(DX).
    """
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    atr_w = _wilder_ema(tr, length)
    plus_di = 100.0 * _wilder_ema(plus_dm, length) / atr_w.replace(0, np.nan)
    minus_di = 100.0 * _wilder_ema(minus_dm, length) / atr_w.replace(0, np.nan)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _wilder_ema(dx, length)


# ---------------------------------------------------------------------------
# Regime classifier
# ---------------------------------------------------------------------------


DEFAULT_REGIME_CFG = {
    "adx_length": 14,
    "ema_slope_length": 20,        # bars over which to measure EMA200 slope
    "ema_slope_threshold": 0.0005, # ~5 bps per bar on FX (~0.05% / day)
    "trend_adx_min": 25.0,
    "range_adx_max": 20.0,
    "atr_length": 14,
    "atrp_chop_quantile": 0.80,    # ATR%/close above 80th percentile = choppy
    "warmup_bars": 210,            # >= EMA200 + ADX warmup
}


@dataclass(frozen=True)
class RegimeView:
    regimes: pd.Series      # str per bar in {"trending","ranging","choppy","unknown"}
    adx: pd.Series
    ema200_slope: pd.Series
    atrp: pd.Series         # ATR / close


def classify_regimes(df: pd.DataFrame, cfg: dict | None = None) -> RegimeView:
    """Classify each bar into trending / ranging / choppy / unknown.

    ``df`` must be a daily OHLCV DataFrame indexed by tz-aware timestamps with
    columns at least ``open, high, low, close``. The function never mutates
    ``df``.
    """
    cfg = {**DEFAULT_REGIME_CFG, **(cfg or {})}
    if not {"open", "high", "low", "close"}.issubset(df.columns):
        raise ValueError(
            "classify_regimes requires open/high/low/close columns"
        )

    close = df["close"].astype(float)
    ema200 = close.ewm(span=200, adjust=False, min_periods=200).mean()
    slope = (ema200 - ema200.shift(cfg["ema_slope_length"])) \
        / ema200.shift(cfg["ema_slope_length"]).replace(0, np.nan)

    adx_series = adx(df, cfg["adx_length"])

    # ATR % of close
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr_series = _wilder_ema(tr, cfg["atr_length"])
    atrp = atr_series / close.replace(0, np.nan)

    # Rolling 60-day quantile threshold for chop detection.
    chop_threshold = atrp.rolling(60, min_periods=30).quantile(
        cfg["atrp_chop_quantile"]
    )

    regimes = pd.Series("unknown", index=df.index, dtype=object)

    # Warm-up gate: need at least warmup_bars of data before we trust the
    # classification.
    warm_mask = np.arange(len(df)) >= cfg["warmup_bars"]

    is_trending = (
        (adx_series >= cfg["trend_adx_min"])
        & (slope.abs() >= cfg["ema_slope_threshold"])
    )
    is_choppy = (
        (atrp > chop_threshold)
        & (adx_series < cfg["range_adx_max"])
    )
    is_ranging = (
        (adx_series < cfg["range_adx_max"])
        & ~is_choppy
    )

    regimes_arr = np.where(
        warm_mask & is_trending.fillna(False), "trending",
        np.where(
            warm_mask & is_choppy.fillna(False), "choppy",
            np.where(
                warm_mask & is_ranging.fillna(False), "ranging",
                "unknown",
            ),
        ),
    )
    regimes = pd.Series(regimes_arr, index=df.index, dtype=object)

    return RegimeView(
        regimes=regimes,
        adx=adx_series,
        ema200_slope=slope,
        atrp=atrp,
    )


def regime_allows_entry(
    regime: str, allowed: Iterable[str] | None
) -> bool:
    """Return True iff the bar's regime is in the ``allowed`` whitelist.

    If ``allowed`` is None, no regime filter is applied (open to all regimes).
    The string ``"unknown"`` is rejected unless explicitly listed in
    ``allowed`` — we never trade in regions where the classifier hasn't warmed
    up.
    """
    if allowed is None:
        return regime != "unknown"
    return regime in set(allowed)


# ---------------------------------------------------------------------------
# Composite filter — what variants call
# ---------------------------------------------------------------------------


def filter_signals(
    df: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    session_cfg: dict | None = None,
    regime_view: RegimeView | None = None,
    regimes_allowed: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Apply session + regime filters to a signals DataFrame in-place-style.

    ``signals`` must have a boolean column ``"long_entry"`` and/or
    ``"short_entry"``. Any row failing the filters has its entry columns set
    to False. Exit columns are never touched (we always allow exits).
    """
    if regime_view is None:
        regime_view = classify_regimes(df)

    session_ok = df.index.to_series().map(
        lambda ts: session_allows_entry(ts, session_cfg)
    )
    regime_ok = regime_view.regimes.map(
        lambda r: regime_allows_entry(r, regimes_allowed)
    )

    keep = session_ok & regime_ok
    out = signals.copy()
    for col in ("long_entry", "short_entry"):
        if col in out.columns:
            out[col] = out[col] & keep
    return out

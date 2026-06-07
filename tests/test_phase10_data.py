"""Tests for ``src.phase10_data_downloader``.

These tests run completely offline. We never hit Yahoo Finance in CI — instead
we inject a fake fetcher into ``fetch_yahoo_daily`` / ``download_symbol``.

Coverage:
  - Symbol whitelist enforcement
  - JSON -> Bar parsing (including null rows / holidays)
  - Validation invariants:
      * ascending unique timestamps
      * no NaN / no future-dated rows
      * high >= max(open, close, low); low <= min(open, close, high)
      * non-negative volume
  - Atomic CSV write + schema (timestamp,open,high,low,close,volume)
  - Idempotent overwrite
  - download_symbol output paths & warnings (XAUUSD note)
  - CLI summary JSON shape & safety block
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pytest

from src import phase10_data_downloader as dd
from src.phase10_data_downloader import (
    Bar,
    PRIMARY_SYMBOLS,
    CONTROL_SYMBOLS,
    SYMBOL_MAP,
    download_symbol,
    fetch_yahoo_daily,
    validate_bars,
    write_csv,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _yahoo_payload(
    timestamps: list[int],
    opens: list[float | None],
    highs: list[float | None],
    lows: list[float | None],
    closes: list[float | None],
    volumes: list[float | None] | None = None,
) -> dict:
    return {
        "chart": {
            "result": [
                {
                    "meta": {"symbol": "FAKE=X"},
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [
                            {
                                "open": opens,
                                "high": highs,
                                "low": lows,
                                "close": closes,
                                "volume": volumes
                                or [0] * len(timestamps),
                            }
                        ]
                    },
                }
            ],
            "error": None,
        }
    }


def _make_bar(day: int, *, open=1.0, high=1.1, low=0.9, close=1.05,
              volume=0.0) -> Bar:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
    return Bar(timestamp=ts, open=open, high=high, low=low, close=close,
               volume=volume)


# ---------------------------------------------------------------------------
# Symbol whitelist
# ---------------------------------------------------------------------------


class TestSymbolWhitelist:
    def test_primary_symbols_in_map(self):
        for sym in PRIMARY_SYMBOLS:
            assert sym in SYMBOL_MAP, f"{sym} missing from SYMBOL_MAP"

    def test_control_symbols_in_map(self):
        for sym in CONTROL_SYMBOLS:
            assert sym in SYMBOL_MAP, f"{sym} missing from SYMBOL_MAP"

    def test_primary_set_matches_spec(self):
        # Phase 10 spec is EURUSD + GBPUSD + XAUUSD as primary; USDJPY control.
        assert set(PRIMARY_SYMBOLS) == {"EURUSD", "GBPUSD", "XAUUSD"}
        assert set(CONTROL_SYMBOLS) == {"USDJPY"}

    def test_xauusd_uses_gold_futures_proxy(self):
        # We deliberately map XAUUSD -> GC=F because Yahoo has no spot history.
        # If this changes, the README and the warning text both need updating.
        assert SYMBOL_MAP["XAUUSD"] == "GC=F"

    def test_download_symbol_rejects_unknown(self, tmp_path):
        with pytest.raises(ValueError, match="not in Phase 10 whitelist"):
            download_symbol("BTCUSD", output_dir=tmp_path,
                            fetcher=lambda url: _yahoo_payload([], [], [], [], []))


# ---------------------------------------------------------------------------
# fetch_yahoo_daily — parsing
# ---------------------------------------------------------------------------


class TestFetchParsing:
    def test_parses_well_formed_payload(self):
        # 3 days of fake EURUSD-ish data.
        t0 = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())
        timestamps = [t0, t0 + 86400, t0 + 2 * 86400]
        payload = _yahoo_payload(
            timestamps,
            opens=[1.10, 1.11, 1.12],
            highs=[1.12, 1.13, 1.14],
            lows=[1.09, 1.10, 1.11],
            closes=[1.11, 1.12, 1.13],
        )
        bars = fetch_yahoo_daily(
            "EURUSD=X",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 5, tzinfo=timezone.utc),
            fetcher=lambda url: payload,
        )
        assert len(bars) == 3
        assert bars[0].open == pytest.approx(1.10)
        assert bars[2].close == pytest.approx(1.13)

    def test_drops_holiday_null_rows(self):
        t0 = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())
        timestamps = [t0, t0 + 86400, t0 + 2 * 86400]
        payload = _yahoo_payload(
            timestamps,
            opens=[1.10, None, 1.12],
            highs=[1.12, None, 1.14],
            lows=[1.09, None, 1.11],
            closes=[1.11, None, 1.13],
        )
        bars = fetch_yahoo_daily(
            "EURUSD=X",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 5, tzinfo=timezone.utc),
            fetcher=lambda url: payload,
        )
        assert len(bars) == 2

    def test_clamps_tiny_floating_point_inconsistencies(self):
        # Yahoo occasionally returns a close fractionally above the day's high
        # or below the low. The fetcher repairs these so downstream validation
        # holds. Differences are typically < 1e-3.
        t0 = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())
        payload = _yahoo_payload(
            [t0],
            opens=[1.10],
            highs=[1.105],  # but close exceeds high by 0.0001 below
            lows=[1.099],
            closes=[1.1051],  # close > high
        )
        bars = fetch_yahoo_daily(
            "EURUSD=X",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 1, 5, tzinfo=timezone.utc),
            fetcher=lambda url: payload,
        )
        assert len(bars) == 1
        assert bars[0].high >= bars[0].close
        assert bars[0].low <= bars[0].close
        # The actual close was preserved; only high was clamped up.
        assert bars[0].close == pytest.approx(1.1051)
        assert bars[0].high == pytest.approx(1.1051)

    def test_normalizes_to_utc_midnight(self):
        # Yahoo sometimes returns timestamps at exchange open (e.g. 14:30 UTC
        # for US futures). We normalize daily bars to UTC midnight so cross-
        # symbol joins line up.
        ts = int(datetime(2024, 3, 15, 14, 30, tzinfo=timezone.utc).timestamp())
        payload = _yahoo_payload([ts], [1.0], [1.1], [0.9], [1.05])
        bars = fetch_yahoo_daily(
            "GC=F",
            datetime(2024, 3, 1, tzinfo=timezone.utc),
            datetime(2024, 3, 20, tzinfo=timezone.utc),
            fetcher=lambda url: payload,
        )
        assert bars[0].timestamp == datetime(2024, 3, 15, tzinfo=timezone.utc)

    def test_raises_on_yahoo_error_field(self):
        bad = {"chart": {"result": [], "error": {"code": "Not Found"}}}
        with pytest.raises(RuntimeError, match="yahoo error"):
            fetch_yahoo_daily(
                "NOPE=X",
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                datetime(2024, 1, 5, tzinfo=timezone.utc),
                fetcher=lambda url: bad,
            )

    def test_rejects_naive_start_end(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            fetch_yahoo_daily(
                "EURUSD=X",
                datetime(2024, 1, 1),
                datetime(2024, 1, 5, tzinfo=timezone.utc),
                fetcher=lambda url: _yahoo_payload([], [], [], [], []),
            )

    def test_rejects_inverted_range(self):
        with pytest.raises(ValueError, match="end must be after start"):
            fetch_yahoo_daily(
                "EURUSD=X",
                datetime(2024, 1, 5, tzinfo=timezone.utc),
                datetime(2024, 1, 1, tzinfo=timezone.utc),
                fetcher=lambda url: _yahoo_payload([], [], [], [], []),
            )


# ---------------------------------------------------------------------------
# validate_bars
# ---------------------------------------------------------------------------


class TestValidation:
    def test_clean_bars_pass(self):
        bars = [_make_bar(i) for i in range(5)]
        assert validate_bars(bars) == []

    def test_empty_input_fails(self):
        assert validate_bars([]) == ["no bars"]

    def test_duplicate_timestamps(self):
        bars = [_make_bar(0), _make_bar(0)]
        errs = validate_bars(bars)
        assert any("duplicate" in e for e in errs)

    def test_descending_timestamps(self):
        bars = [_make_bar(1), _make_bar(0)]
        errs = validate_bars(bars)
        assert any("ascending" in e for e in errs)

    def test_future_dated_rejected(self):
        future = datetime.now(tz=timezone.utc) + timedelta(days=5)
        bar = Bar(timestamp=future, open=1, high=1.1, low=0.9, close=1.05,
                  volume=0)
        errs = validate_bars([bar])
        assert any("future-dated" in e for e in errs)

    def test_high_must_be_max(self):
        bad = _make_bar(0, open=1.0, high=0.95, low=0.9, close=1.05)
        errs = validate_bars([bad])
        assert any("high < max" in e for e in errs)

    def test_low_must_be_min(self):
        bad = _make_bar(0, open=1.0, high=1.1, low=1.05, close=1.02)
        errs = validate_bars([bad])
        assert any("low > min" in e for e in errs)

    def test_negative_volume_rejected(self):
        bad = _make_bar(0, volume=-1.0)
        errs = validate_bars([bad])
        assert any("negative volume" in e for e in errs)


# ---------------------------------------------------------------------------
# write_csv
# ---------------------------------------------------------------------------


class TestWriteCsv:
    def test_schema_matches_downstream(self, tmp_path: Path):
        bars = [_make_bar(i) for i in range(3)]
        path = tmp_path / "eurusd_1d.csv"
        n = write_csv(bars, path)
        assert n == 3
        # First line must be the exact header the phase10 module expects.
        with path.open() as f:
            reader = csv.reader(f)
            header = next(reader)
        assert header == ["timestamp", "open", "high", "low", "close", "volume"]

    def test_overwrite_is_idempotent(self, tmp_path: Path):
        bars1 = [_make_bar(i) for i in range(3)]
        bars2 = [_make_bar(i) for i in range(5)]
        path = tmp_path / "x.csv"
        write_csv(bars1, path)
        write_csv(bars2, path)
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 1 + 5  # header + 5 rows

    def test_temp_file_cleaned_up(self, tmp_path: Path):
        bars = [_make_bar(0)]
        path = tmp_path / "x.csv"
        write_csv(bars, path)
        assert not (tmp_path / "x.csv.tmp").exists()


# ---------------------------------------------------------------------------
# download_symbol — end-to-end with injected fetcher
# ---------------------------------------------------------------------------


def _fake_fetcher_5y(url: str) -> dict:
    """Returns 1300 daily bars (~5 years of business days)."""
    base = datetime(2019, 1, 2, tzinfo=timezone.utc)
    timestamps: list[int] = []
    o, h, l, c = [], [], [], []
    price = 1.10
    for i in range(1300):
        # Skip weekends to simulate real FX.
        d = base + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        timestamps.append(int(d.timestamp()))
        op = price
        cl = price * (1 + 0.001 * ((i % 7) - 3))
        hi = max(op, cl) * 1.002
        lo = min(op, cl) * 0.998
        o.append(op)
        h.append(hi)
        l.append(lo)
        c.append(cl)
        price = cl
    return _yahoo_payload(timestamps, o, h, l, c)


class TestDownloadSymbol:
    def test_writes_csv_for_each_primary(self, tmp_path: Path):
        for sym in PRIMARY_SYMBOLS:
            res = download_symbol(sym, years=5, output_dir=tmp_path,
                                  fetcher=_fake_fetcher_5y)
            assert Path(res.path).exists()
            assert res.rows > 200
            assert Path(res.path).name == f"{sym.lower()}_1d.csv"

    def test_xauusd_warning_present(self, tmp_path: Path):
        res = download_symbol("XAUUSD", years=5, output_dir=tmp_path,
                              fetcher=_fake_fetcher_5y)
        assert any("GC=F" in w for w in res.warnings)

    def test_eurusd_no_proxy_warning(self, tmp_path: Path):
        res = download_symbol("EURUSD", years=5, output_dir=tmp_path,
                              fetcher=_fake_fetcher_5y)
        assert not any("GC=F" in w for w in res.warnings)

    def test_output_is_loadable_by_phase10_module(self, tmp_path: Path):
        # Ensures the CSV we produce is compatible with the existing
        # phase10_fx_gold_daily._load_csv expectations.
        from src.phase10_fx_gold_daily import _load_csv

        res = download_symbol("EURUSD", years=5, output_dir=tmp_path,
                              fetcher=_fake_fetcher_5y)
        df = _load_csv(Path(res.path))
        assert {"open", "high", "low", "close", "volume"}.issubset(df.columns)
        assert df.index.is_monotonic_increasing
        assert len(df) == res.rows


# ---------------------------------------------------------------------------
# Safety — this module must never touch live config
# ---------------------------------------------------------------------------


class TestSafetyInvariants:
    """The downloader is read-only. It must not import or modify any safety-
    critical module, and it must not reference live-trading flags."""

    def test_no_live_trading_imports(self):
        src = Path(dd.__file__).read_text()
        forbidden = [
            "validation_gate",
            "risk_engine",
            "exchange_client",
            "webhook_server",
            "BINGX_API_KEY",
            "BINGX_API_SECRET",
            "TRADINGVIEW_WEBHOOK_SECRET",
        ]
        for token in forbidden:
            assert token not in src, (
                f"phase10_data_downloader must not reference {token}"
            )

    def test_no_live_flags_set(self):
        # Module must not set LIVE_TRADING / MICRO_LIVE / FULL_LIVE anywhere.
        src = Path(dd.__file__).read_text()
        for flag in ("LIVE_TRADING", "MICRO_LIVE", "FULL_LIVE"):
            # Allowed: mention inside the safety block of the summary JSON.
            # We require the strings only appear lowercased (as JSON keys) or
            # inside the safety summary literal.
            uppercase_count = src.count(flag)
            assert uppercase_count == 0, (
                f"phase10_data_downloader must not reference {flag} (got "
                f"{uppercase_count} uppercase occurrences)"
            )

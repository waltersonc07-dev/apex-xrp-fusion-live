from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

from .data_loader import validate_ohlcv_csv


BINANCE_KLINES_URLS = [
    "https://api.binance.com/api/v3/klines",
    "https://api.binance.us/api/v3/klines",
]
TIMEFRAME_TO_MS = {"1h": 60 * 60 * 1000}


def _parse_datetime_ms(value: str | None) -> int | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def fetch_klines(symbol: str, interval: str, start_ms: int | None = None, end_ms: int | None = None, limit: int = 1000) -> list[list]:
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    if start_ms is not None:
        params["startTime"] = start_ms
    if end_ms is not None:
        params["endTime"] = end_ms
    last_error: Exception | None = None
    for base_url in BINANCE_KLINES_URLS:
        url = f"{base_url}?{urlencode(params)}"
        try:
            with urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"all OHLCV sources failed: {last_error}")


def download_ohlcv(
    symbol: str,
    timeframe: str,
    output: str | Path,
    start: str | None = "2021-01-01T00:00:00Z",
    end: str | None = None,
    sleep_seconds: float = 0.05,
) -> dict:
    if timeframe not in TIMEFRAME_TO_MS:
        raise ValueError(f"unsupported timeframe: {timeframe}")

    start_ms = _parse_datetime_ms(start)
    end_ms = _parse_datetime_ms(end)
    step_ms = TIMEFRAME_TO_MS[timeframe]
    rows: list[dict] = []

    while True:
        batch = fetch_klines(symbol, timeframe, start_ms=start_ms, end_ms=end_ms)
        if not batch:
            break
        for item in batch:
            rows.append({
                "timestamp": pd.to_datetime(item[0], unit="ms", utc=True).isoformat(),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
            })
        last_open_ms = int(batch[-1][0])
        next_start = last_open_ms + step_ms
        if len(batch) < 1000 or (end_ms is not None and next_start >= end_ms):
            break
        start_ms = next_start
        time.sleep(sleep_seconds)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("no OHLCV data returned")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False, columns=["timestamp", "open", "high", "low", "close", "volume"])
    return validate_ohlcv_csv(target)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XRPUSDT")
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--output", default="data/raw/xrpusdt_1h.csv")
    parser.add_argument("--start", default="2021-01-01T00:00:00Z")
    parser.add_argument("--end", default=None)
    args = parser.parse_args()

    result = download_ohlcv(args.symbol, args.timeframe, args.output, args.start, args.end)
    print("DATA DOWNLOAD COMPLETE")
    print(f"VALID: {result['valid']}")
    print(f"ROWS: {result['rows']}")
    print(f"START: {result['start']}")
    print(f"END: {result['end']}")
    if result["errors"]:
        print("ERRORS:")
        for error in result["errors"]:
            print(f"- {error}")
    if result["warnings"]:
        print("WARNINGS:")
        for warning in result["warnings"]:
            print(f"- {warning}")


if __name__ == "__main__":
    main()

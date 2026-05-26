from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def validate_ohlcv_csv(path: str | Path, expected_freq: str = "1h") -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    target = Path(path)

    if not target.exists():
        return {"valid": False, "errors": [f"file not found: {target}"], "warnings": [], "rows": 0, "start": None, "end": None}

    try:
        df = pd.read_csv(target)
    except Exception as exc:
        return {"valid": False, "errors": [f"failed to read csv: {exc}"], "warnings": [], "rows": 0, "start": None, "end": None}

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        errors.append(f"missing required columns: {', '.join(missing_columns)}")
        return {"valid": False, "errors": errors, "warnings": warnings, "rows": len(df), "start": None, "end": None}

    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    except Exception as exc:
        errors.append(f"invalid timestamps: {exc}")
        return {"valid": False, "errors": errors, "warnings": warnings, "rows": len(df), "start": None, "end": None}

    numeric_columns = ["open", "high", "low", "close", "volume"]
    for column in numeric_columns:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if df[REQUIRED_COLUMNS].isna().any().any():
        errors.append("missing OHLCV values")
    if not df["timestamp"].is_monotonic_increasing:
        errors.append("timestamps must be sorted ascending")
    if df["timestamp"].duplicated().any():
        errors.append("duplicate timestamps detected")
    if (df["high"] < df[["open", "close", "low"]].max(axis=1)).any():
        errors.append("high must be >= open, close, and low")
    if (df["low"] > df[["open", "close", "high"]].min(axis=1)).any():
        errors.append("low must be <= open, close, and high")
    if (df["volume"] < 0).any():
        errors.append("volume must be >= 0")

    if len(df) >= 2:
        deltas = df["timestamp"].diff().dropna()
        expected = pd.Timedelta(expected_freq)
        missing = deltas[deltas > expected]
        abnormal = deltas[deltas > expected * 3]
        if not missing.empty:
            warnings.append(f"missing {expected_freq} candles detected: {len(missing)} gap(s)")
        if not abnormal.empty:
            warnings.append(f"abnormal timestamp gaps detected: {len(abnormal)} gap(s)")

    start = df["timestamp"].iloc[0].isoformat() if len(df) else None
    end = df["timestamp"].iloc[-1].isoformat() if len(df) else None
    return {"valid": not errors, "errors": errors, "warnings": warnings, "rows": len(df), "start": start, "end": end}


def load_ohlcv_csv(path: str | Path, expected_freq: str = "1h") -> pd.DataFrame:
    validation = validate_ohlcv_csv(path, expected_freq)
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    for column in ["open", "high", "low", "close", "volume"]:
        df[column] = pd.to_numeric(df[column], errors="raise")
    return df.set_index("timestamp").sort_index()


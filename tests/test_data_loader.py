from pathlib import Path

from src.data_loader import validate_ohlcv_csv


def write_csv(path: Path, rows: list[str]) -> None:
    path.write_text("timestamp,open,high,low,close,volume\n" + "\n".join(rows), encoding="utf-8")


def test_data_loader_rejects_duplicate_timestamps(tmp_path):
    csv_path = tmp_path / "data.csv"
    write_csv(csv_path, [
        "2026-01-01 00:00:00,1,2,0.5,1.5,100",
        "2026-01-01 00:00:00,1,2,0.5,1.5,100",
    ])
    result = validate_ohlcv_csv(csv_path)
    assert not result["valid"]
    assert any("duplicate" in error for error in result["errors"])


def test_data_loader_rejects_missing_ohlcv(tmp_path):
    csv_path = tmp_path / "data.csv"
    write_csv(csv_path, [
        "2026-01-01 00:00:00,1,2,0.5,,100",
        "2026-01-01 01:00:00,1,2,0.5,1.5,100",
    ])
    result = validate_ohlcv_csv(csv_path)
    assert not result["valid"]
    assert any("missing OHLCV" in error for error in result["errors"])


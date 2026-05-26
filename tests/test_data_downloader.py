from src.data_downloader import download_ohlcv


def test_data_downloader_saves_valid_csv(monkeypatch, tmp_path):
    import src.data_downloader as downloader

    def fake_fetch(symbol, interval, start_ms=None, end_ms=None, limit=1000):
        return [
            [1767225600000, "1.0", "1.2", "0.9", "1.1", "100"],
            [1767229200000, "1.1", "1.3", "1.0", "1.2", "110"],
        ]

    monkeypatch.setattr(downloader, "fetch_klines", fake_fetch)
    result = download_ohlcv("XRPUSDT", "1h", tmp_path / "xrp.csv", start="2026-01-01T00:00:00Z")
    assert result["valid"]
    assert result["rows"] == 2


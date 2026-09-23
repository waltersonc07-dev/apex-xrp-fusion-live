#!/usr/bin/env python3
"""Thin CLI wrapper for Stacked MTF v3.3 backtest (fees + slippage ON).

Usage (from repo root, venv active):

    python scripts/run_stacked_mtf_backtest.py --csv data/raw/xrpusdt_15m.csv

Or as a module:

    python -m src.strategy_stacked_mtf --csv data/raw/xrpusdt_15m.csv

Requires a local 15m OHLCV CSV (timestamp,open,high,low,close,volume).
Download example (needs network):

    python -m src.data_downloader --symbol XRPUSDT --timeframe 15m \\
        --output data/raw/xrpusdt_15m.csv --start 2023-01-01T00:00:00Z

Does not place trades or unlock live mode.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.strategy_stacked_mtf import main

if __name__ == "__main__":
    main()

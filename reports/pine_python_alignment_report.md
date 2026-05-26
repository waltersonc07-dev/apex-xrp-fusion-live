# Pine/Python Alignment Report

- Supertrend ATR length: Python=12, Pine target=12, aligned=True
- Supertrend multiplier: Python=3.0, Pine target=3.0, aligned=True
- EMA fast: Python=9, Pine target=9, aligned=True
- EMA slow: Python=21, Pine target=21, aligned=True
- DEMA length: Python=200, Pine target=200, aligned=True
- ATR stop multiplier: Python=1.5, Pine target=1.5, aligned=True
- TP ATR multiplier: Python=3.0, Pine target=3.0, aligned=True
- Flip exit enabled: Python=True, Pine target=True, aligned=True

## Execution Notes
- Pine uses `process_orders_on_close=true`; validation Python uses next-candle-open fills by default for conservative live-readiness testing.
- Both Python and Pine use first-bar transition signals to avoid repeated signal spam.
- Python validation uses `same_bar_policy=stop_first`; optimistic `tp_first` is not used for live unlock validation.

## Mismatches
- none
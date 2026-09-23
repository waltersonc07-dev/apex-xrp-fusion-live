# Stacked MTF v3.3 (research variant)

Long-only multi-timeframe stack strategy ported from
`pine/xrp_stacked_mtf_v3.3.pine`. **Research / backtest only — live remains blocked.**

## Rules (defaults)

| Item | Value |
|------|--------|
| Chart TF | 15m |
| Confirmation HTF | 2H (confirmed closed bar; non-repainting) |
| Stack | EMA9, EMA21, DEMA200, SuperTrend all bullish |
| Bullish stack | close above each line; SuperTrend direction bullish; EMA9 > EMA21 |
| Bearish stack (exit) | close below each line; SuperTrend bearish (no EMA-order requirement) |
| Entry | First 15m bar after a new 2H period opens, when **both** 15m and 2H stacks are up |
| `freshOnly` | **OFF** (v3.3) — do not require the 15m stack to first flip true on that bar |
| Exit | Full 15m stack flip (`stack_dn`) |
| Protective price stop | **OFF** by default |
| Side | Long only |

## Differences from Fusion Live v1

| | Fusion Live v1 | Stacked MTF v3.3 |
|--|----------------|------------------|
| Timeframe | 1H | 15m + 2H confirmation |
| Direction | Long and short | Long only |
| Entry | First-bar confluence on 1H (ST + EMA order + DEMA + RR/levels) | 2H-synced re-arm when both stacks are already up |
| Exit | ATR stop/target and optional flip | Full stack flip (no fixed SL/TP by default) |
| Levels / RR gate | Yes (support/resistance, min RR) | No |
| Live / webhook | Primary strategy path (still blocked by validation) | Research-only; does not unlock live |

## Python modules

- `src/strategy_stacked_mtf.py` — signal generation + dedicated backtest (fees/slippage ON)
- `scripts/run_stacked_mtf_backtest.py` — thin CLI wrapper
- Pine reference: `pine/xrp_stacked_mtf_v3.3.pine`

## How to run a backtest

```bash
cd /path/to/apex-xrp-fusion-live
source .venv/bin/activate   # or Windows equivalent

# Need local 15m data first (network download):
python -m src.data_downloader --symbol XRPUSDT --timeframe 15m \
  --output data/raw/xrpusdt_15m.csv --start 2023-01-01T00:00:00Z

python scripts/run_stacked_mtf_backtest.py --csv data/raw/xrpusdt_15m.csv \
  --fee-bps 5 --slippage-bps 2
# equivalent:
python -m src.strategy_stacked_mtf --csv data/raw/xrpusdt_15m.csv
```

Outputs:

- `journals/stacked_mtf_backtest_trades.csv`
- `reports/stacked_mtf_backtest_report.md`

Default fills are **on bar close** (Pine `process_orders_on_close`). Pass `--entry-on-open` for open fills.

## Safety

- Does **not** change live unlock flags, webhook live mode, or SAFETY thresholds.
- Recommended mode remains `BACKTEST_ONLY` until the Fusion validation gate (or a future dedicated gate) passes.

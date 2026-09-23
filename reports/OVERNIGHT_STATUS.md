# Overnight Status — 2026-09-21 (EDT)

Unattended run on `/workspace/apex-xrp-fusion-live`. No live trades. No IBKR orders. SAFETY / live unlock flags unchanged (`LIVE_TRADING=false`, `risk.mode: BACKTEST_ONLY`, `IBKR_ENABLED=false`).

## What shipped locally

| Item | Status |
|------|--------|
| Venv (`.venv`) | OK — pandas/numpy/httpx import clean |
| Real XRPUSDT 15m OHLC | `data/raw/xrpusdt_15m.csv` — **130,533** bars, **2023-01-01 → 2026-09-22 03:15 UTC**, ~6.9 MB |
| Data source | Binance.US klines (`.com` returns HTTP 451 from this host). H1 2023 backfilled from `data.binance.vision` monthly archives |
| Downloader tweak | `src/data_downloader.py` prefers `api.binance.us` before `api.binance.com` |
| Stacked MTF v3.3 backtest | Ran with `--fee-bps 5 --slippage-bps 2` (fees ON) |
| Report | `reports/stacked_mtf_backtest_report.md` |
| Trade journal | `journals/stacked_mtf_backtest_trades.csv` (481 trades) |
| Prior local work already in tree | Stacked MTF strategy/Pine/docs, IBKR read-only stub + plan, smoke tests — left uncommitted for push |

## Backtest headline metrics (fees + slippage ON)

Source: real Binance XRPUSDT 15m, Stacked MTF v3.3, long-only, entry-on-close.

| Metric | Value |
|--------|------:|
| Total trades | **481** |
| Net PnL | **11,444.02** |
| Gross PnL | 16,127.00 |
| Fees paid | 4,682.98 |
| Slippage cost | 1,873.19 |
| Profit factor | **1.317** |
| Max drawdown % | **27.17%** |
| Win rate | **29.94%** (144 W / 337 L) |
| Expectancy / avg trade | 23.79 |
| Max consecutive losses | 13 |
| fee_bps / slippage_bps | 5.0 / 2.0 |
| Lookahead / repaint flags | False / False |

Command:

```bash
python scripts/run_stacked_mtf_backtest.py \
  --csv data/raw/xrpusdt_15m.csv --fee-bps 5 --slippage-bps 2
```

## Caveats

1. **Not live-validated.** Gate remains `BLOCK_LIVE`. This is research-only.
2. **Exit accounting quirk:** report shows `flip_exits: 0` / `use_stop: False`, but journal `exit_reason` values are mostly `stack_flip` (and end-of-test). Treat PF/net/DD/WR as authoritative; exit-type counters may under-count.
3. **Venue mix:** live path of downloader is Binance.US; early 2023 months came from global Binance Vision archives. Small gaps flagged by validator (2 missing-candle warnings / 1 abnormal gap).
4. **Costs matter:** ~$6.5k combined fees+slippage vs ~$16k gross — results sensitive to fee assumptions.
5. **No walk-forward / OOS / stress refresh** on this overnight pass — only the stacked MTF full-sample backtest was re-run on real data.
6. Synthetic smoke CSV remains at `data/raw/xrpusdt_15m_synthetic_smoke.csv` (prior 1-trade toy report was from that).

## Still blocked (needs human)

| Blocker | Why |
|---------|-----|
| **GitHub write / push** | `GH_TOKEN` unset; non-interactive push skipped. Working tree left dirty/ready. Remote: `origin` → `waltersonc07-dev/apex-xrp-fusion-live` |
| **TradingView login** | No credentials / browser session for alert/Pine publish |
| **Gmail auth** | MCP/mail not authenticated for overnight notify |
| **Live / micro-live unlock** | Intentionally not touched; validation gate still blocks |
| **IBKR live orders** | Forbidden by overnight constraints and `IBKR_ENABLED=false` |

## Deliverable zip

`/workspace/apex-xrp-fusion-live-overnight.zip` — code + docs + reports + journals + raw CSV (~6.9 MB, under 50 MB threshold). Excludes `.venv`.

## Git working tree (ready to push when token available)

Modified: `.env.example`, `src/data_downloader.py`  
Untracked (among others): stacked MTF sources/docs/Pine/tests, IBKR stub/plan, backtest report/journal, this status file.

Do **not** commit `data/raw/*.csv` (gitignored). Push when a write token is available:

```bash
git add -A   # respects .gitignore
git status
git commit -m "..."
git push origin main
```

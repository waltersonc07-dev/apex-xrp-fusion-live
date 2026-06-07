# APEX XRP Fusion Live v1

## What This Is

APEX XRP Fusion Live v1 is a professional XRPUSDT 1H trading research and automation framework. It combines TradingView Pine strategy logic, Python validation, realistic backtesting, risk controls, webhook intake, dry-run execution, journaling, and reports.

This is not a proven live-money system yet. Current mode remains blocked until validation improves.

## Official Architecture

1. Market Research: Perplexity, macro context, XRP news, liquidity zones, and a daily fundamental score.
2. Strategy Logic: XRPUSDT 1H, Supertrend ATR 12 / multiplier 3.0, EMA 9 / EMA 21, 1H DEMA 200, ATR stop/target, and first-bar signals only.
3. Realistic Backtesting: next-candle entry, fixed SL/TP at entry, stop-first same-bar policy, fees, slippage, and no fake-perfect results.
4. Risk Management: risk per trade, daily loss limit, weekly loss limit, max open positions, no martingale, no averaging down, and no live trading unless validation passes.
5. Execution: TradingView alert, webhook server, Python risk engine, and exchange client stub/dry-run by default.
6. Journal / Analytics: every signal, rejection, trade, PnL, R-multiple, and risk-engine decision.
7. AI Optimization / Automation: Codex, Claude, and ChatGPT improve the system only after data proves the change.

## Official Strategy

LONG:

- Supertrend bullish
- EMA 9 > EMA 21
- close > 1H DEMA 200
- RR >= 2
- fundamental gate allows trading

SHORT:

- Supertrend bearish
- EMA 9 < EMA 21
- close < 1H DEMA 200
- RR >= 2
- fundamental gate allows trading

## Current Status

- Phase 1 framework: complete
- Phase 2 validation gate: complete
- Phase 3A data downloader: complete
- Phase 3B realistic backtest engine: complete
- Live trading: blocked
- Validation currently: `BLOCK_LIVE`
- Recommended mode: `BACKTEST_ONLY`
- Exchange execution: stub/dry-run by default

Latest realistic validation:

```text
WIN RATE: 30.02%
PROFIT FACTOR: 0.859
MAX DRAWDOWN: 24.10%
TOTAL TRADES: 916
VALIDATION RESULT: BLOCK_LIVE
RECOMMENDED MODE: BACKTEST_ONLY
```

## Install

```powershell
cd C:\Users\produ\apex-xrp-fusion-live
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Download Data

```powershell
.\.venv\Scripts\python.exe -m src.data_downloader --symbol XRPUSDT --timeframe 1h --output data/raw/xrpusdt_1h.csv
```

The CSV must contain:

```text
timestamp,open,high,low,close,volume
```

## Run Validation

```powershell
.\.venv\Scripts\python.exe -m src.run_validation --csv data/raw/xrpusdt_1h.csv
```

Generated reports include:

- `reports/backtest_report.md`
- `reports/walk_forward_report.md`
- `reports/stress_test_report.md`
- `reports/trade_audit_report.md`
- `reports/trade_distribution_report.md`
- `reports/pine_python_alignment_report.md`
- `reports/live_unlock_report.md`

## Run Core Diagnostic

Run the expanded 9-row strategy diagnostic leaderboard:

```powershell
.\.venv\Scripts\python.exe -m src.core_diagnostic --csv data/raw/xrpusdt_1h.csv
```

The reports are written to `reports/core_diagnostic_report.md` and `reports/core_diagnostic_leaderboard.csv`. It tests 9 variant rows across 8 variant families, uses the last 20% of candles as OOS, and keeps live trading blocked unless every diagnostic gate passes.

## TradingView Pine Script

Paste this file into TradingView Pine Editor:

```text
pine/apex_xrp_fusion_live_v1.pine
```

Add it to an XRPUSDT 1H chart.

## TradingView Webhook

Endpoint:

```text
/webhook/tradingview
```

Local server:

```powershell
uvicorn src.webhook_server:app --host 0.0.0.0 --port 8000
```

The webhook validates the shared secret, builds a signal, runs the risk engine before any execution call, and journals the decision. Stub/dry-run execution is only called after risk-engine approval.

## Render Deployment

Service:

```text
apex-xrp-fusion-live
```

1. Push repo to:
   https://github.com/waltersonc07-dev/apex-xrp-fusion-live.git
2. In Render, create a new Web Service:
   `apex-xrp-fusion-live`
3. Connect GitHub repo:
   `apex-xrp-fusion-live`
4. Build command:
   `pip install -r requirements.txt`
5. Start command:
   `uvicorn src.webhook_server:app --host 0.0.0.0 --port $PORT`
6. Required safe environment variables:

```text
LIVE_TRADING=false
MICRO_LIVE=false
FULL_LIVE=false
RISK_MODE=BACKTEST_ONLY
TRADINGVIEW_WEBHOOK_SECRET=<set manually>
```

Do not add real API keys until validation qualifies the system and you intentionally move to a controlled micro-live stage.

## Environment

Use `.env.example` as the template. Do not commit `.env`.

Required safe defaults:

```text
LIVE_TRADING=false
MICRO_LIVE=false
FULL_LIVE=false
RISK_MODE=BACKTEST_ONLY
```

## Safety Rules

- Do not enable `MICRO_LIVE` unless validation passes.
- Do not enable `FULL_LIVE`.
- Do not set `LIVE_TRADING=true` yet.
- Do not add real API keys until the system qualifies.
- Keep `RISK_MODE=BACKTEST_ONLY` until validation passes.
- Keep `risk.mode: BACKTEST_ONLY` in `config/settings.yaml`.
- Current fundamental score is below the live threshold, so live trading remains blocked.

## GitHub

Repo:

```text
https://github.com/waltersonc07-dev/apex-xrp-fusion-live.git
```

Safety overview: see [SAFETY.md](SAFETY.md) for the three-layer live-trading lock and how to verify it.

Suggested commands after tests and validation pass:

```powershell
cd C:\Users\produ\apex-xrp-fusion-live
git add .
git commit -m "Migrate project identity to apex-xrp-fusion-live"
git push -u origin main
```

If the current branch is `master`, use the matching branch name or rename only after confirming it is safe.

## Shut Down

1. Keep or set `risk.mode: BACKTEST_ONLY`.
2. Set `LIVE_TRADING=false`.
3. Set `MICRO_LIVE=false`.
4. Set `FULL_LIVE=false`.
5. Stop the FastAPI server.
6. Disable TradingView alerts.

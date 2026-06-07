# Phase 10 Verdict — FX / Gold Daily Trend Discovery

## Status

Live trading remains **BACKTEST_ONLY**. This module never unlocks live mode.
Any 'PASS' below means the candidate variant qualifies for **manual review**
as a MICRO_LIVE candidate. Live activation still requires explicit owner approval.

## Gate thresholds (daily timeframe)

- Min profit factor: 1.50
- Min OOS profit factor: 1.20
- Max drawdown: 25.0%
- Min Sharpe: 0.80
- Min trades per asset: 40
- Must beat buy-and-hold of the same asset
- Must survive 2x fees and 2x slippage (PF >= 1.0)
- Walk-forward: at most 1 losing window of N

## Variants (non-optimized defaults)

- V0: long-only EMA200 regime + EMA21/55 trend + RSI(14) cross 50, ATR(14)*2 stop, EMA21 trail
- V1: V0 mirrored both sides
- V2: long-only Donchian(20) breakout with EMA200 regime, Donchian(10) exit
- V3: both-sides Bollinger squeeze breakout, mid-band exit

## Results

### EURUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 40 | 42.5 | 1.26 | 1.20 | 1.3 | 1.07 | 1.5 | -3.1 | BLOCK |
| V1 | 98 | 42.9 | 1.25 | 0.97 | 2.5 | 1.11 | 3.0 | -3.1 | BLOCK |
| V2 | 16 | 25.0 | 0.92 | 0.67 | 1.8 | -0.43 | -0.4 | -3.1 | BLOCK |
| V3 | 54 | 29.6 | 0.83 | 0.60 | 4.7 | -1.10 | -1.8 | -3.1 | BLOCK |

**EURUSD / V0 failed rules:**
- profit factor 1.26 below 1.50
- walk-forward unstable: 1/3 windows profitable

**EURUSD / V1 failed rules:**
- profit factor 1.25 below 1.50
- out-of-sample profit factor 0.97 below 1.20

**EURUSD / V2 failed rules:**
- profit factor 0.92 below 1.50
- out-of-sample profit factor 0.67 below 1.20
- sharpe -0.43 below 0.80
- trades 16 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

**EURUSD / V3 failed rules:**
- profit factor 0.83 below 1.50
- out-of-sample profit factor 0.60 below 1.20
- sharpe -1.10 below 0.80
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

### GBPUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 46 | 39.1 | 1.12 | 1.33 | 1.5 | 0.67 | 0.6 | -13.2 | BLOCK |
| V1 | 87 | 39.1 | 1.37 | 1.28 | 2.0 | 1.74 | 3.6 | -13.2 | BLOCK |
| V2 | 17 | 35.3 | 0.95 | 1.18 | 2.3 | -0.23 | -0.2 | -13.2 | BLOCK |
| V3 | 55 | 36.4 | 0.46 | 0.30 | 6.9 | -5.12 | -6.3 | -13.2 | BLOCK |

**GBPUSD / V0 failed rules:**
- profit factor 1.12 below 1.50
- sharpe 0.67 below 0.80

**GBPUSD / V1 failed rules:**
- profit factor 1.37 below 1.50

**GBPUSD / V2 failed rules:**
- profit factor 0.95 below 1.50
- out-of-sample profit factor 1.18 below 1.20
- sharpe -0.23 below 0.80
- trades 17 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

**GBPUSD / V3 failed rules:**
- profit factor 0.46 below 1.50
- out-of-sample profit factor 0.30 below 1.20
- sharpe -5.12 below 0.80
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

### XAUUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 55 | 30.9 | 1.00 | 4.42 | 6.0 | 0.05 | -0.0 | 91.4 | BLOCK |
| V1 | 72 | 33.3 | 1.01 | 4.42 | 6.1 | 0.11 | 0.2 | 91.4 | BLOCK |
| V2 | 29 | 37.9 | 1.99 | 6.26 | 3.6 | 3.45 | 8.3 | 91.4 | BLOCK |
| V3 | 57 | 29.8 | 1.42 | 3.21 | 3.2 | 1.65 | 6.8 | 91.4 | BLOCK |

**XAUUSD / V0 failed rules:**
- profit factor 1.00 below 1.50
- sharpe 0.05 below 0.80
- strategy return -0.0% does not beat buy-and-hold 91.4%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**XAUUSD / V1 failed rules:**
- profit factor 1.01 below 1.50
- sharpe 0.11 below 0.80
- strategy return 0.2% does not beat buy-and-hold 91.4%
- doubled-fees stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**XAUUSD / V2 failed rules:**
- trades 29 below 40
- strategy return 8.3% does not beat buy-and-hold 91.4%

**XAUUSD / V3 failed rules:**
- profit factor 1.42 below 1.50
- strategy return 6.8% does not beat buy-and-hold 91.4%

### USDJPY

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 61 | 27.9 | 1.50 | 1.31 | 4.9 | 1.55 | 3.8 | 42.2 | BLOCK |
| V1 | 90 | 34.4 | 1.37 | 0.86 | 5.1 | 1.19 | 3.6 | 42.2 | BLOCK |
| V2 | 15 | 26.7 | 3.53 | 1.48 | 3.8 | 3.90 | 12.5 | 42.2 | BLOCK |
| V3 | 52 | 34.6 | 1.17 | 0.45 | 4.4 | 0.81 | 1.9 | 42.2 | BLOCK |

**USDJPY / V0 failed rules:**
- strategy return 3.8% does not beat buy-and-hold 42.2%

**USDJPY / V1 failed rules:**
- profit factor 1.37 below 1.50
- out-of-sample profit factor 0.86 below 1.20
- strategy return 3.6% does not beat buy-and-hold 42.2%

**USDJPY / V2 failed rules:**
- trades 15 below 40
- strategy return 12.5% does not beat buy-and-hold 42.2%

**USDJPY / V3 failed rules:**
- profit factor 1.17 below 1.50
- out-of-sample profit factor 0.45 below 1.20
- strategy return 1.9% does not beat buy-and-hold 42.2%

## Safety reminder

- `risk.mode` remains `BACKTEST_ONLY`.
- `LIVE_TRADING`, `MICRO_LIVE`, `FULL_LIVE` remain `false`.
- No API keys are added by this module.
- A `PASS_CANDIDATE` verdict is research signal only and does not authorize
  any live order. See SAFETY.md.

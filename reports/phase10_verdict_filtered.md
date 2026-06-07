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
| V0 | 15 | 40.0 | 0.34 | 0.00 | 1.5 | -6.47 | -1.3 | -16.6 | BLOCK |
| V1 | 21 | 42.9 | 0.62 | 7.40 | 1.2 | -2.86 | -0.9 | -16.6 | BLOCK |
| V2 | 14 | 42.9 | 1.94 | 0.07 | 1.0 | 4.02 | 3.1 | -16.6 | BLOCK |
| V3 | 21 | 33.3 | 1.13 | 1.31 | 2.4 | 0.76 | 0.6 | -16.6 | BLOCK |

**EURUSD / V0 failed rules:**
- profit factor 0.34 below 1.50
- out-of-sample profit factor 0.00 below 1.20
- sharpe -6.47 below 0.80
- trades 15 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**EURUSD / V1 failed rules:**
- profit factor 0.62 below 1.50
- sharpe -2.86 below 0.80
- trades 21 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**EURUSD / V2 failed rules:**
- out-of-sample profit factor 0.07 below 1.20
- trades 14 below 40

**EURUSD / V3 failed rules:**
- profit factor 1.13 below 1.50
- sharpe 0.76 below 0.80
- trades 21 below 40

### GBPUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 6 | 50.0 | 1.31 | 0.63 | 0.2 | 1.68 | 0.1 | -32.8 | BLOCK |
| V1 | 16 | 43.8 | 0.80 | 0.58 | 0.9 | -1.37 | -0.3 | -32.8 | BLOCK |
| V2 | 12 | 25.0 | 0.25 | 0.08 | 2.9 | -9.75 | -2.9 | -32.8 | BLOCK |
| V3 | 16 | 31.2 | 0.57 | 0.18 | 2.8 | -3.65 | -1.9 | -32.8 | BLOCK |

**GBPUSD / V0 failed rules:**
- profit factor 1.31 below 1.50
- out-of-sample profit factor 0.63 below 1.20
- trades 6 below 40
- walk-forward unstable: 1/3 windows profitable

**GBPUSD / V1 failed rules:**
- profit factor 0.80 below 1.50
- out-of-sample profit factor 0.58 below 1.20
- sharpe -1.37 below 0.80
- trades 16 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

**GBPUSD / V2 failed rules:**
- profit factor 0.25 below 1.50
- out-of-sample profit factor 0.08 below 1.20
- sharpe -9.75 below 0.80
- trades 12 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

**GBPUSD / V3 failed rules:**
- profit factor 0.57 below 1.50
- out-of-sample profit factor 0.18 below 1.20
- sharpe -3.65 below 0.80
- trades 16 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

### XAUUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 18 | 16.7 | 0.19 | 1.69 | 3.4 | -10.87 | -3.4 | 190.5 | BLOCK |
| V1 | 25 | 16.0 | 0.15 | 1.69 | 4.5 | -12.15 | -4.5 | 190.5 | BLOCK |
| V2 | 27 | 29.6 | 1.58 | 23.94 | 3.7 | 1.97 | 5.1 | 190.5 | BLOCK |
| V3 | 19 | 26.3 | 0.53 | 2.04 | 4.1 | -3.96 | -2.6 | 190.5 | BLOCK |

**XAUUSD / V0 failed rules:**
- profit factor 0.19 below 1.50
- sharpe -10.87 below 0.80
- trades 18 below 40
- strategy return -3.4% does not beat buy-and-hold 190.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

**XAUUSD / V1 failed rules:**
- profit factor 0.15 below 1.50
- sharpe -12.15 below 0.80
- trades 25 below 40
- strategy return -4.5% does not beat buy-and-hold 190.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**XAUUSD / V2 failed rules:**
- trades 27 below 40
- strategy return 5.1% does not beat buy-and-hold 190.5%

**XAUUSD / V3 failed rules:**
- profit factor 0.53 below 1.50
- sharpe -3.96 below 0.80
- trades 19 below 40
- strategy return -2.6% does not beat buy-and-hold 190.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

### USDJPY

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 10 | 50.0 | 5.59 | 1.29 | 0.5 | 6.54 | 6.5 | 17.5 | BLOCK |
| V1 | 26 | 42.3 | 2.75 | 1.29 | 1.4 | 3.48 | 5.8 | 17.5 | BLOCK |
| V2 | 12 | 41.7 | 6.78 | 0.86 | 1.9 | 7.56 | 17.4 | 17.5 | BLOCK |
| V3 | 14 | 28.6 | 0.65 | 1.61 | 1.5 | -2.41 | -0.8 | 17.5 | BLOCK |

**USDJPY / V0 failed rules:**
- trades 10 below 40
- strategy return 6.5% does not beat buy-and-hold 17.5%

**USDJPY / V1 failed rules:**
- trades 26 below 40
- strategy return 5.8% does not beat buy-and-hold 17.5%

**USDJPY / V2 failed rules:**
- out-of-sample profit factor 0.86 below 1.20
- trades 12 below 40
- strategy return 17.4% does not beat buy-and-hold 17.5%

**USDJPY / V3 failed rules:**
- profit factor 0.65 below 1.50
- sharpe -2.41 below 0.80
- trades 14 below 40
- strategy return -0.8% does not beat buy-and-hold 17.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

## Safety reminder

- `risk.mode` remains `BACKTEST_ONLY`.
- `LIVE_TRADING`, `MICRO_LIVE`, `FULL_LIVE` remain `false`.
- No API keys are added by this module.
- A `PASS_CANDIDATE` verdict is research signal only and does not authorize
  any live order. See SAFETY.md.

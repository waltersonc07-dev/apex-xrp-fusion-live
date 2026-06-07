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
| V0 | 86 | 38.4 | 1.16 | 1.09 | 2.7 | 0.70 | 2.0 | -16.6 | BLOCK |
| V1 | 175 | 42.3 | 1.54 | 0.84 | 2.9 | 1.85 | 12.0 | -16.6 | BLOCK |
| V2 | 36 | 33.3 | 1.14 | 0.39 | 3.8 | 0.86 | 1.4 | -16.6 | BLOCK |
| V3 | 105 | 36.2 | 1.15 | 0.94 | 4.7 | 0.87 | 3.5 | -16.6 | BLOCK |

**EURUSD / V0 failed rules:**
- profit factor 1.16 below 1.50
- out-of-sample profit factor 1.09 below 1.20
- sharpe 0.70 below 0.80

**EURUSD / V1 failed rules:**
- out-of-sample profit factor 0.84 below 1.20

**EURUSD / V2 failed rules:**
- profit factor 1.14 below 1.50
- out-of-sample profit factor 0.39 below 1.20
- trades 36 below 40
- walk-forward unstable: 1/3 windows profitable

**EURUSD / V3 failed rules:**
- profit factor 1.15 below 1.50
- out-of-sample profit factor 0.94 below 1.20

### GBPUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 105 | 36.2 | 0.72 | 1.11 | 6.1 | -1.80 | -3.9 | -32.8 | BLOCK |
| V1 | 183 | 33.9 | 0.94 | 1.03 | 6.3 | -0.28 | -1.5 | -32.8 | BLOCK |
| V2 | 38 | 34.2 | 0.66 | 1.94 | 5.6 | -2.56 | -3.7 | -32.8 | BLOCK |
| V3 | 100 | 35.0 | 0.80 | 0.40 | 7.5 | -1.25 | -4.5 | -32.8 | BLOCK |

**GBPUSD / V0 failed rules:**
- profit factor 0.72 below 1.50
- out-of-sample profit factor 1.11 below 1.20
- sharpe -1.80 below 0.80
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

**GBPUSD / V1 failed rules:**
- profit factor 0.94 below 1.50
- out-of-sample profit factor 1.03 below 1.20
- sharpe -0.28 below 0.80
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

**GBPUSD / V2 failed rules:**
- profit factor 0.66 below 1.50
- sharpe -2.56 below 0.80
- trades 38 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**GBPUSD / V3 failed rules:**
- profit factor 0.80 below 1.50
- out-of-sample profit factor 0.40 below 1.20
- sharpe -1.25 below 0.80
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

### XAUUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 100 | 27.0 | 0.74 | 4.27 | 8.7 | -1.47 | -5.2 | 190.5 | BLOCK |
| V1 | 156 | 27.6 | 0.83 | 4.47 | 8.6 | -0.92 | -5.1 | 190.5 | BLOCK |
| V2 | 54 | 29.6 | 2.01 | 7.01 | 3.6 | 2.97 | 17.7 | 190.5 | BLOCK |
| V3 | 111 | 26.1 | 0.98 | 2.18 | 8.7 | -0.03 | -0.7 | 190.5 | BLOCK |

**XAUUSD / V0 failed rules:**
- profit factor 0.74 below 1.50
- sharpe -1.47 below 0.80
- strategy return -5.2% does not beat buy-and-hold 190.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

**XAUUSD / V1 failed rules:**
- profit factor 0.83 below 1.50
- sharpe -0.92 below 0.80
- strategy return -5.1% does not beat buy-and-hold 190.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**XAUUSD / V2 failed rules:**
- strategy return 17.7% does not beat buy-and-hold 190.5%

**XAUUSD / V3 failed rules:**
- profit factor 0.98 below 1.50
- sharpe -0.03 below 0.80
- strategy return -0.7% does not beat buy-and-hold 190.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

### USDJPY

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 100 | 23.0 | 1.10 | 1.16 | 5.8 | 0.38 | 1.4 | 17.5 | BLOCK |
| V1 | 181 | 33.7 | 1.16 | 0.84 | 5.1 | 0.59 | 3.6 | 17.5 | BLOCK |
| V2 | 35 | 25.7 | 3.01 | 2.20 | 4.7 | 3.38 | 22.7 | 17.5 | BLOCK |
| V3 | 111 | 28.8 | 0.92 | 0.64 | 8.0 | -0.33 | -1.9 | 17.5 | BLOCK |

**USDJPY / V0 failed rules:**
- profit factor 1.10 below 1.50
- out-of-sample profit factor 1.16 below 1.20
- sharpe 0.38 below 0.80
- strategy return 1.4% does not beat buy-and-hold 17.5%

**USDJPY / V1 failed rules:**
- profit factor 1.16 below 1.50
- out-of-sample profit factor 0.84 below 1.20
- sharpe 0.59 below 0.80
- strategy return 3.6% does not beat buy-and-hold 17.5%

**USDJPY / V2 failed rules:**
- trades 35 below 40

**USDJPY / V3 failed rules:**
- profit factor 0.92 below 1.50
- out-of-sample profit factor 0.64 below 1.20
- sharpe -0.33 below 0.80
- strategy return -1.9% does not beat buy-and-hold 17.5%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

## Safety reminder

- `risk.mode` remains `BACKTEST_ONLY`.
- `LIVE_TRADING`, `MICRO_LIVE`, `FULL_LIVE` remain `false`.
- No API keys are added by this module.
- A `PASS_CANDIDATE` verdict is research signal only and does not authorize
  any live order. See SAFETY.md.

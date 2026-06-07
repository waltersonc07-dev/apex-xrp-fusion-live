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
| V0 | 4 | 75.0 | 1.82 | 0.00 | 0.4 | 3.35 | 0.3 | -3.1 | BLOCK |
| V1 | 5 | 60.0 | 1.67 | 0.00 | 0.4 | 2.72 | 0.3 | -3.1 | BLOCK |
| V2 | 9 | 22.2 | 0.80 | inf | 1.8 | -1.38 | -0.5 | -3.1 | BLOCK |
| V3 | 11 | 18.2 | 1.58 | 1.67 | 1.1 | 2.25 | 0.8 | -3.1 | BLOCK |

**EURUSD / V0 failed rules:**
- out-of-sample profit factor 0.00 below 1.20
- trades 4 below 40
- walk-forward unstable: 1/3 windows profitable

**EURUSD / V1 failed rules:**
- out-of-sample profit factor 0.00 below 1.20
- trades 5 below 40

**EURUSD / V2 failed rules:**
- profit factor 0.80 below 1.50
- sharpe -1.38 below 0.80
- trades 9 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**EURUSD / V3 failed rules:**
- trades 11 below 40

### GBPUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 3 | 33.3 | 0.85 | 0.72 | 0.1 | -0.93 | -0.0 | -13.2 | BLOCK |
| V1 | 9 | 44.4 | 1.98 | 0.72 | 0.2 | 4.10 | 0.4 | -13.2 | BLOCK |
| V2 | 7 | 0.0 | 0.00 | 0.33 | 2.8 | -35.24 | -2.8 | -13.2 | BLOCK |
| V3 | 11 | 18.2 | 0.10 | 0.34 | 3.0 | -15.94 | -2.8 | -13.2 | BLOCK |

**GBPUSD / V0 failed rules:**
- profit factor 0.85 below 1.50
- out-of-sample profit factor 0.72 below 1.20
- sharpe -0.93 below 0.80
- trades 3 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

**GBPUSD / V1 failed rules:**
- out-of-sample profit factor 0.72 below 1.20
- trades 9 below 40
- walk-forward unstable: 1/3 windows profitable

**GBPUSD / V2 failed rules:**
- profit factor 0.00 below 1.50
- out-of-sample profit factor 0.33 below 1.20
- sharpe -35.24 below 0.80
- trades 7 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

**GBPUSD / V3 failed rules:**
- profit factor 0.10 below 1.50
- out-of-sample profit factor 0.34 below 1.20
- sharpe -15.94 below 0.80
- trades 11 below 40
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 0/3 windows profitable

### XAUUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 12 | 33.3 | 0.21 | 2.96 | 1.7 | -8.70 | -1.7 | 91.4 | BLOCK |
| V1 | 17 | 41.2 | 0.53 | 2.96 | 2.1 | -3.40 | -1.2 | 91.4 | BLOCK |
| V2 | 14 | 50.0 | 2.66 | 12.72 | 1.5 | 6.05 | 4.8 | 91.4 | BLOCK |
| V3 | 9 | 33.3 | 0.98 | inf | 1.7 | -0.06 | -0.0 | 91.4 | BLOCK |

**XAUUSD / V0 failed rules:**
- profit factor 0.21 below 1.50
- sharpe -8.70 below 0.80
- trades 12 below 40
- strategy return -1.7% does not beat buy-and-hold 91.4%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**XAUUSD / V1 failed rules:**
- profit factor 0.53 below 1.50
- sharpe -3.40 below 0.80
- trades 17 below 40
- strategy return -1.2% does not beat buy-and-hold 91.4%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

**XAUUSD / V2 failed rules:**
- trades 14 below 40
- strategy return 4.8% does not beat buy-and-hold 91.4%

**XAUUSD / V3 failed rules:**
- profit factor 0.98 below 1.50
- sharpe -0.06 below 0.80
- trades 9 below 40
- strategy return -0.0% does not beat buy-and-hold 91.4%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable

### USDJPY

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | 4 | 75.0 | 19.41 | 0.00 | 0.1 | 8.76 | 1.6 | 42.2 | BLOCK |
| V1 | 7 | 57.1 | 5.26 | 0.00 | 0.3 | 5.88 | 1.5 | 42.2 | BLOCK |
| V2 | 12 | 8.3 | 1.09 | 0.00 | 3.0 | 0.46 | 0.5 | 42.2 | BLOCK |
| V3 | 11 | 27.3 | 0.26 | 0.00 | 1.2 | -7.98 | -1.2 | 42.2 | BLOCK |

**USDJPY / V0 failed rules:**
- out-of-sample profit factor 0.00 below 1.20
- trades 4 below 40
- strategy return 1.6% does not beat buy-and-hold 42.2%

**USDJPY / V1 failed rules:**
- out-of-sample profit factor 0.00 below 1.20
- trades 7 below 40
- strategy return 1.5% does not beat buy-and-hold 42.2%

**USDJPY / V2 failed rules:**
- profit factor 1.09 below 1.50
- out-of-sample profit factor 0.00 below 1.20
- sharpe 0.46 below 0.80
- trades 12 below 40
- strategy return 0.5% does not beat buy-and-hold 42.2%
- walk-forward unstable: 1/3 windows profitable

**USDJPY / V3 failed rules:**
- profit factor 0.26 below 1.50
- out-of-sample profit factor 0.00 below 1.20
- sharpe -7.98 below 0.80
- trades 11 below 40
- strategy return -1.2% does not beat buy-and-hold 42.2%
- doubled-fees stress test not profitable
- doubled-slippage stress test not profitable
- walk-forward unstable: 1/3 windows profitable

## Safety reminder

- `risk.mode` remains `BACKTEST_ONLY`.
- `LIVE_TRADING`, `MICRO_LIVE`, `FULL_LIVE` remain `false`.
- No API keys are added by this module.
- A `PASS_CANDIDATE` verdict is research signal only and does not authorize
  any live order. See SAFETY.md.

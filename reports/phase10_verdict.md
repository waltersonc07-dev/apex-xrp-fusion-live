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
| V0 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V1 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V2 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V3 | — | — | — | — | — | — | — | — | BLOCK_LIVE |

**EURUSD / V0 failed rules:**
- no data available yet — see PR 3

**EURUSD / V1 failed rules:**
- no data available yet — see PR 3

**EURUSD / V2 failed rules:**
- no data available yet — see PR 3

**EURUSD / V3 failed rules:**
- no data available yet — see PR 3

### GBPUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V1 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V2 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V3 | — | — | — | — | — | — | — | — | BLOCK_LIVE |

**GBPUSD / V0 failed rules:**
- no data available yet — see PR 3

**GBPUSD / V1 failed rules:**
- no data available yet — see PR 3

**GBPUSD / V2 failed rules:**
- no data available yet — see PR 3

**GBPUSD / V3 failed rules:**
- no data available yet — see PR 3

### XAUUSD

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V1 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V2 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V3 | — | — | — | — | — | — | — | — | BLOCK_LIVE |

**XAUUSD / V0 failed rules:**
- no data available yet — see PR 3

**XAUUSD / V1 failed rules:**
- no data available yet — see PR 3

**XAUUSD / V2 failed rules:**
- no data available yet — see PR 3

**XAUUSD / V3 failed rules:**
- no data available yet — see PR 3

### USDJPY

| Variant | Trades | Win% | PF | OOS PF | DD% | Sharpe | Strat% | B&H% | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| V0 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V1 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V2 | — | — | — | — | — | — | — | — | BLOCK_LIVE |
| V3 | — | — | — | — | — | — | — | — | BLOCK_LIVE |

**USDJPY / V0 failed rules:**
- no data available yet — see PR 3

**USDJPY / V1 failed rules:**
- no data available yet — see PR 3

**USDJPY / V2 failed rules:**
- no data available yet — see PR 3

**USDJPY / V3 failed rules:**
- no data available yet — see PR 3

## Safety reminder

- `risk.mode` remains `BACKTEST_ONLY`.
- `LIVE_TRADING`, `MICRO_LIVE`, `FULL_LIVE` remain `false`.
- No API keys are added by this module.
- A `PASS_CANDIDATE` verdict is research signal only and does not authorize
  any live order. See SAFETY.md.

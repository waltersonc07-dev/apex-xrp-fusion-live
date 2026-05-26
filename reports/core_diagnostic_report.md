# APEX Core Diagnostic Report

VARIANT ROWS TESTED: 9
VARIANT FAMILIES: 8
DATA: 2021-01-01 to 2026-05-26
CANDLES: 25417
OOS: last 5084 candles starting 2025-10-26

## Baseline
- Trades: 916
- Win Rate: 30.02%
- Profit Factor: 0.859
- Max Drawdown: 24.10%

## V7 Combo Minimal
- Side: both
- Selected filters: V4_PULLBACK_LOCATION, V3_4H_TREND_FILTER
- Final in-sample trade count: 330
- Rejected filters:
  - V5B_ADX_20: rejected because V7 stops after two filters
  - V5A_ADX_18: rejected because V7 stops after two filters
  - V6_RSI_MOMENTUM: rejected because V7 stops after two filters

## Leaderboard

| Rank | Variant | Trades | Win Rate | Profit Factor | Net Profit | Max DD | OOS PF | Stress 2x | Validation |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | V7_COMBO_MINIMAL | 387 | 33.85% | 1.008 | 58.66 | 12.81% | 1.364 | FAIL | BLOCK_LIVE |
| 2 | V2_SHORT_ONLY | 495 | 31.72% | 0.930 | -629.28 | 11.25% | 0.999 | FAIL | BLOCK_LIVE |
| 3 | V3_4H_TREND_FILTER | 535 | 31.78% | 0.925 | -709.34 | 14.91% | 1.188 | FAIL | BLOCK_LIVE |
| 4 | V4_PULLBACK_LOCATION | 681 | 31.28% | 0.913 | -1054.67 | 17.40% | 0.883 | FAIL | BLOCK_LIVE |
| 5 | V5B_ADX_20 | 708 | 30.79% | 0.899 | -1222.49 | 18.61% | 1.062 | FAIL | BLOCK_LIVE |
| 6 | V5A_ADX_18 | 776 | 30.67% | 0.887 | -1511.55 | 20.45% | 1.042 | FAIL | BLOCK_LIVE |
| 7 | V0_BASELINE_BOTH | 916 | 30.02% | 0.859 | -2144.85 | 24.10% | 0.918 | FAIL | BLOCK_LIVE |
| 8 | V6_RSI_MOMENTUM | 921 | 29.75% | 0.846 | -2341.32 | 26.44% | 0.881 | FAIL | BLOCK_LIVE |
| 9 | V1_LONG_ONLY | 411 | 27.98% | 0.782 | -1634.85 | 17.51% | 0.794 | FAIL | BLOCK_LIVE |

## Decision
- Best Variant: V7_COMBO_MINIMAL
- Best Profit Factor: 1.008
- Best OOS PF: 1.364
- Best Win Rate: 33.85%
- Best Max Drawdown: 12.81%
- Best Trade Count: 387
- Validation: BLOCK_LIVE
- Recommended Mode: BACKTEST_ONLY
- Decision: NO_VARIANT_PASSES

NEXT ACTION:
- Do not trade live.
- Strategy needs structural change.
- Review losing trade distribution.
- Consider long-only during confirmed bull market.
- Consider RSI 50 trend confirmation.
- Consider ADX >= 20 chop filter.
- Consider higher timeframe trend alignment.
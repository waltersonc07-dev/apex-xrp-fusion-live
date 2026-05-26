# Core Diagnostic Report

VARIANT ROWS TESTED: 9
VARIANT FAMILIES: 8

V7 selection rule: filters are selected using in-sample results only; OOS is reserved for final validation after the combo is fixed.
Stress rule: double-cost metrics double both commission and slippage.

| Rank | Variant | Net Profit | Profit Factor | Max DD % | Win Rate % | Trades | Double-Cost Net | Double-Cost PF | Selected Filters |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | V4_PULLBACK_LOCATION | 268.25 | 1.497 | 1.75 | 43.75 | 32 | 52.90 | 1.097 |  |
| 2 | V7_COMBO_MINIMAL | -369.75 | 0.957 | 11.35 | 32.20 | 472 | -1614.30 | 0.803 | V3_4H_TREND_FILTER,V5A_ADX_18,V6_RSI_MOMENTUM |
| 3 | V2_SHORT_ONLY | -629.28 | 0.930 | 11.25 | 31.72 | 495 | -2108.94 | 0.758 |  |
| 4 | V3_4H_TREND_FILTER | -709.34 | 0.925 | 14.91 | 31.78 | 535 | -2169.57 | 0.762 |  |
| 5 | V5B_ADX_20 | -1222.49 | 0.899 | 18.61 | 30.79 | 708 | -2633.09 | 0.767 |  |
| 6 | V5A_ADX_18 | -1511.55 | 0.887 | 20.45 | 30.67 | 776 | -3150.52 | 0.745 |  |
| 7 | V0_BASELINE_BOTH | -2144.85 | 0.859 | 24.10 | 30.02 | 916 | -4047.54 | 0.712 |  |
| 8 | V6_RSI_MOMENTUM | -2341.32 | 0.846 | 26.44 | 29.75 | 921 | -4111.97 | 0.707 |  |
| 9 | V1_LONG_ONLY | -1634.85 | 0.782 | 17.51 | 27.98 | 411 | -2534.66 | 0.652 |  |
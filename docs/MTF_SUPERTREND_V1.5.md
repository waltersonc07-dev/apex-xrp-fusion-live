# XRP MTF Supertrend v1.5

Research strategy (chosen 2026-09-23 over Stacked MTF for forward work).

- Chart: `BINANCE:XRPUSDT` **15m**
- Bias: 1H close vs 1H DEMA200
- Entry: 15m DEMA200 + EMA9/21 + SuperTrend flip
- Exit: SuperTrend stop or opposite flip
- Engine commission/slippage = 0; read cost sweep + IS/OOS from the on-chart analytics table
- Alerts: `alert()` ENTRY/EXIT once-per-bar-close JSON (`strategy`: `MTF_Supertrend_v1.5`) → Render `/webhook/alert` → Telegram + Grok chat mirror
- **No live broker orders** from this path

Pine: `pine/xrp_mtf_supertrend_v1.5.pine` (paste helper: `_paste.pine`)

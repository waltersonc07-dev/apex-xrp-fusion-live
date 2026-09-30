# Stacked MTF v3.4-tag: notify-only entry context tags

`pine/xrp_stacked_mtf_v3.4_tag.pine` is **v3.3 with identical entry, exit and sizing logic**. The only change is that the ENTRY alert
note (and extra JSON fields) carries context tags. Tags never block, delay or modify a trade, and nothing here places orders or touches live flags.
Python reference: `src/resistance_tag.py` (tests: `tests/test_resistance_tag.py`).

## Tags (computed only from completed 2H/4H bars; confirmed pivots; no lookahead)

HTF bars are assembled on the 15m chart from chart bars. No `request.security` is used. At the first 15m bar of 2H bar *k*, only pivots
confirmed by bars <= k-1 are used, and the distance unit is ATR(12) of the last closed 2H bar.

| Tag | Rule |
|---|---|
| `⚠️ Near resistance P (+d ATR2H, TF)` | Nearest confirmed swing-high pivot above the entry close (2H L/R=3, 4H L/R=2, lookback 90 HTF bars) is <= 1.0 ATR2H away |
| `✅ Clear to next resistance P (+d ATR2H, TF)` | Nearest such pivot is > 1.0 ATR2H away |
| `✅ No swing-high resistance in lookback` | No pivot above price in the lookback |
| `rejection candle` (only with Near) | Entry bar or prior 15m bar: upper wick > 2x body, or close-location (C-L)/(H-L) < 0.4 |
| `Inside triangle — wait for 2H breakout close (upper U / lower L)` | Last 2 confirmed 2H pivot highs descending AND last 2 pivot lows ascending; lines through them projected to now; lower <= close <= upper |

Extra JSON fields: `res_state` (NEAR/CLEAR/NONE/NA), `res_level`, `res_atr2h`, `res_tf`, `rejection`, `triangle`, `tri_upper`, `tri_lower`.
The Render `/webhook/alert` parser (`src/alert_notify.py`) needs no change: `note` goes to Telegram, and the whole payload
(including the extra fields) is stored in the `/alerts/recent` buffer. `strategy` is now `StackedMTF_v3.4tag`.

Also fixed: v3.3 used `exitShort` in the EXIT alert before it was declared. v3.4-tag declares it earlier.

## Historical frequency (XRPUSDT Binance 15m, 765 baseline v3.3 entries 2020-03 → 2026-09-29, 0.10% RT fees)

| Tag | Fires | PF of tagged entries (IS / OOS) |
|---|---|---|
| Near resistance (<=1 ATR2H) | 588 (76.9%) | 1.11 / 1.46 (untagged: 0.97 / 1.92) |
| Near + rejection candle | 398 (52.0%) | 0.95 / 1.26 |
| Near, no rejection | 190 (24.8%) | 1.50 / 1.90 |
| Inside 2H triangle | 28 (3.7%) | 1.15 / 1.05 |

IS/OOS split is 2024-10-08. The "Near" tag alone does **not** separate good from bad baseline entries. Entries within 0.1 ATR2H
of a pivot actually did best (PF 2.04, often a break through a wick high). The only informative sub-signal was near + rejection candle.
Treat the tags as context, not a rule. On 2026-09-29 10:15 ET the tag read:
`⚠️ Near resistance 1.5464 (+0.02 ATR2H, 2H) | rejection candle` (no triangle: the last two 2H pivot lows were descending, 1.4703 → 1.4663).

## Installing on TradingView (manual; nothing is changed automatically)

1. Open the XRPUSDT **15m** chart, open Pine Editor, create a new strategy script, paste `pine/xrp_stacked_mtf_v3.4_tag.pine`, and click *Save* and *Add to chart*.
   Keep the same inputs as v3.3 (defaults are identical) and compare the Strategy Tester trade list with v3.3. The trades should be identical.
2. In the Alerts panel, create a new alert. Condition: *XRP Stacked MTF v3.4-tag …* → **"alert() function calls only"**. Trigger: once per bar close.
   Webhook URL: the same Render `/webhook/alert` URL you use for v3.3, with the same secret mechanism. Message box: leave it; alert() supplies the JSON.
3. Confirm one v3.4-tag alert arrives in Telegram and `/alerts/recent`. Then pause or delete the old v3.3 alert to avoid duplicate ENTRY/EXIT messages.

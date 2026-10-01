# Stacked MTF v3.5 TEST: C1 one-2H-close entry delay + macro warning (notify-only)

`pine/xrp_stacked_mtf_v3.5_test.pine` = v3.4-tag (commit 7f4ab05: exit-path EXIT alerts, endTime 2099,
commission 0.1%/side, slippage 2 ticks) **plus** two changes. Nothing here places orders, touches BingX/IBKR or changes live flags.

- Title: `XRP Stacked MTF v3.5 TEST`. All alert JSON uses `"strategy":"v3.5-test"`, which Telegram prints on line 2,
  so these show up as test alerts. The ENTRY note also starts with `[v3.5 TEST]`. No change to `src/alert_notify.py` is needed.
- Sizing is unchanged (`close - SuperTrend`, falling back to 3 x ATR). ATR sizing was tested and rejected
  (`analysis/claude_round3_2026-09-30.md`: lower MAR at every grid point and at matched exposure).

## 1. C1: delay entry by one 2H close (input `useC1`, default ON)

```pine
var bool prevSyncLong = false
delayOK = useC1 ? prevSyncLong : true
enterLong = inRange and flat and entryTrig and syncOK and delayOK
// LOAD-BEARING ORDER: this block must stay AFTER enterLong
if is2hOpen
    prevSyncLong := longCond
```

So entry happens at a fresh 2H open only if `longCond` (15m stack up AND confirmed 2H stack up) also held at the previous 2H open.
This is the same as "wait one 2H close, and enter if the signal still holds".

- **Ordering is load-bearing.** This follows Claude review #3. If the update block is moved above `enterLong`, C1 silently becomes
  "longCond true once", i.e. no delay at all, and nothing fails to compile. The Pine has a boxed warning about this, and
  `tests/test_v35_pine.py` asserts the textual order.
- **`longCond`, not `entryTrig`.** With `freshOnly = false` (the default) the two are identical. If `freshOnly` is ever turned on, C1's meaning
  changes: it still checks "stack up at the previous 2H open", not "a fresh trigger fired there". Re-validate before toggling it.
- `prevSyncLong` updates at every 2H open, whether or not a position is open. This matches the Python rule `lg[i-8]`.
  On a cold start the first 2H open cannot enter, which is expected.

## 2. Macro warning (informational, ENTRY alert only)

When a US CPI, NFP (Employment Situation) or FOMC statement is due within the next `macroAheadH` hours (default 24),
measured from the entry bar's close, the ENTRY note gets an extra line. The Pine emits a JSON-escaped `\n`, so Telegram shows it as its own line:

```
⚠ macro <24h: CPI in 23.5h (Oct 14 08:30 ET)
```

- It **never** filters, delays or resizes anything. The earlier analysis found that a macro blackout does not beat random skipping
  (C3: 61/49/80 null percentiles).
- Events already released are not flagged.
- The list is the hardcoded input `macroEvents`, in UTC, written as `LABEL@YYYY-MM-DDTHH:MM`. It is parsed once on the first bar.
  The dashboard shows how many events loaded.

| Event | ET | UTC (input) | Source |
|---|---|---|---|
| NFP (Sep 2026) | Fri 2026-10-02 08:30 EDT | 12:30 | [BLS Employment Situation schedule](https://www.bls.gov/schedule/news_release/empsit.htm) |
| CPI (Sep 2026) | Wed 2026-10-14 08:30 EDT | 12:30 | [BLS CPI schedule](https://www.bls.gov/schedule/news_release/cpi.htm) |
| FOMC | Wed 2026-10-28 14:00 EDT | 18:00 | [Fed FOMC calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) (Oct 27-28), [Fed Oct 2026 calendar](https://www.federalreserve.gov/newsevents/2026-october.htm) (2:00 p.m.) |
| NFP (Oct 2026) | Fri 2026-11-06 08:30 EST | 13:30 | BLS empsit |
| CPI (Oct 2026) | Tue 2026-11-10 08:30 EST | 13:30 | BLS CPI |
| NFP (Nov 2026) | Fri 2026-12-04 08:30 EST | 13:30 | BLS empsit |
| FOMC (SEP) | Wed 2026-12-09 14:00 EST | 19:00 | Fed calendar (Dec 8-9) |
| CPI (Nov 2026) | Thu 2026-12-10 08:30 EST | 13:30 | BLS CPI |
| FOMC | Wed 2027-01-27 14:00 EST | 19:00 | Fed calendar, 2027 (Jan 26-27) |
| FOMC (SEP) | Wed 2027-03-17 14:00 EDT | 18:00 | Fed 2027 (Mar 16-17) |
| FOMC | Wed 2027-04-28 14:00 EDT | 18:00 | Fed 2027 (Apr 27-28) |
| FOMC (SEP) | Wed 2027-06-09 14:00 EDT | 18:00 | Fed 2027 (Jun 8-9) |
| FOMC | Wed 2027-07-28 14:00 EDT | 18:00 | Fed 2027 (Jul 27-28) |
| FOMC (SEP) | Wed 2027-09-15 14:00 EDT | 18:00 | Fed 2027 (Sep 14-15) |
| FOMC | Wed 2027-10-27 14:00 EDT | 18:00 | Fed 2027 (Oct 26-27) |
| FOMC (SEP) | Wed 2027-12-08 14:00 EST | 19:00 | Fed 2027 (Dec 7-8) |

Gaps and caveats. The dates were checked on 2026-10-01 against bls.gov and federalreserve.gov; nothing was guessed.

- **2027 CPI and NFP are not included.** BLS has not published its 2027 schedule yet: the CPI and Employment Situation schedule pages
  end at the Nov 2026 reference month, and `bls.gov/schedule/2027/` returns 404. Add those dates to `macroEvents` once BLS posts them.
- **2027 FOMC dates are tentative.** The Fed says each date is tentative until it is confirmed at the meeting before it.
  The 2:00 p.m. ET statement time is the Fed's standing practice, confirmed on every 2026 monthly calendar. The 2027 monthly calendars are not published yet.
- **Shutdowns can move BLS dates.** The 2025 and 2026 lapses in appropriations did
  ([BLS revised dates](https://www.bls.gov/bls/2025-lapse-revised-release-dates.htm)). If BLS reschedules, edit the input.
- **ET to UTC conversion.** EDT (UTC-4) applies until 2026-11-01 and again 2027-03-14 → 2027-11-07. EST (UTC-5) applies otherwise.

## 3. Validation (2026-10-01)

**Reference backtest.** Run `analysis/v35/validate_c1.py`, which uses the book_methods engine and data
(Binance XRPUSDT 15m 2020-01 → 2026-09-30, fill at the 15m close, stack-flip exit, 0.10% RT, IS/OOS split 2024-10-08).

| rule | trades (IS/OOS) | PF | IS PF | OOS PF | PF @0.20% RT | 1%-sized net / maxDD |
|---|---|---|---|---|---|---|
| v3.3 baseline | 774 (557/217) | 1.19 | 1.06 | 1.59 | 1.11 | +189.0% / 43.9% |
| **C1** | **489 (353/136)** | **1.42** | **1.21** | **2.09** | **1.31** (IS 1.12 / OOS 1.93) | +211.3% / **33.1%** |

Random-skip null (1000 sims, blocking the same 1,410 candidate bars at random), as percentiles ALL/IS/OOS:

| null run | ALL | IS | OOS |
|---|---|---|---|
| seed 7 | 99.5 | 96.4 | 97.6 |
| seed 20260930 | 98.8 | 95.1 | 97.7 |
| book_methods main table | 99 | 95 | 97 |

**Pine-to-Python equivalence.** The same script also emulates the Pine statement order bar by bar:
- `var prevSyncLong`
- `longCond = 15m up and 2H up`
- `enterLong = flat and longCond and is2hOpen and prevSyncLong`
- then the `if is2hOpen` update
- exits on the pre-bar position, with orders filling at the bar close (`process_orders_on_close`)

| emulation | trades | result |
|---|---|---|
| C1 off | 774 | identical to the engine baseline |
| C1, correct order | 489 | identical to the Python rule `lg & lg[i-8]`, trade by trade (489 common, 0 only-Pine, 0 only-Python), even with the 15 gaps in the 15m data |
| C1, update moved above `enterLong` (negative control) | 774 | identical to the baseline, i.e. no filtering at all. This confirms Claude's ordering warning. |

**Static checks.**
- `tests/test_v35_pine.py` checks the ordering, unchanged non-C1 logic and sizing, the no-lookahead pattern, the title and tag, the macro list against the official dates, the macro window, and that the ENTRY payload parses.
- The full suite passes.
- The Pine parses with `pynescript`, a local grammar parser, not TradingView's compiler. A deliberately broken copy fails to parse.

**No lookahead.** The HTF stack comes from `request.security(..., f_upPrev()/f_dnPrev(), lookahead_on)`, where the function returns `v[1]`
inside the 2H context. That gives the last *closed* 2H bar, both historically and live, which is the standard non-repainting form.
`lookahead_off` without an offset is used only for the opt-in `useLiveHTF` path, which is labelled REPAINTS and defaults to off.
The C1 state is a plain `var` updated on chart bars and does not use `request.security`.

## 4. Caveats

- **The IS margin is thin.** IS PF is 1.21 (1.12 at 0.20% RT), and the IS null percentile is 95-96, right at the bar.
  Most of the improvement is in the shorter OOS window.
- **Many variants were tested.** 22 variants plus 7 robustness variants, so one marginal pass could be chance.
- **Forward-test before switching.** Run v3.5 TEST alongside the live v3.3/v3.4 alerts on TradingView, as notify-only, before any switch.
- **C1 delays every entry by one 2H bar.** It cannot take the 45 baseline trades that exited before the next 2H open, all of which were losses, but it also misses the first 2H of every move.

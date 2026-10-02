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

## 5. Caution lines + caution score (2026-10-02, informational only)

Walter approved: "Add shooting-star note. Do everything that helps to be careful." Input group 12 (`useCaution`, default ON).
The ENTRY note gets extra lines, **each only when true**, then a score and an advisory risk line. Telegram (`format_alert`) shows each on its own line:

| line | rule (closed bars only, no `request.security`, no lookahead) | source |
|---|---|---|
| `⚠ macro <24h: …` | unchanged (section 2) | — |
| `⚠ shooting star <2h` | bearish mirror of the research WICK rule on 15m: upper wick ≥ 2×body and ≥ 50% of range, lower wick ≤ 30% of range, range ≥ 0.5×ATR(14), after a 6-bar rise (`close[1] > close[7]`); on the entry bar or any of the 7 before it (8 closed 15m bars) | `analysis/yt_J8tcoEiCI7k` near-miss "veto bear WICK 15m last8" |
| `⚠ 2H bear momentum at resistance` | last COMPLETED 2H bar (built from chart bars): red, previous red, body bigger, plus a KEY double-top touch on it or the 3 before (last two confirmed 2H pivot highs, L=R=5, within 1×ATR14(2H); high within ±0.5 ATR of the latest; close below it) | same report, "2H-bar SHORT MOM at KEY" |
| `⚠ near resistance` | the v3.4-tag `resState == "NEAR"` (≤ `nearAtr` × ATR2H below a 2H/4H pivot high), reused as-is | PR #19 |
| `Caution N/4 · Risk: …` | N = count of the four warnings; N ≥ 2 → "consider HALF size (advisory only — rules unchanged)", else "normal size per plan (advisory)" | — |

Extra ENTRY JSON fields: `caution`, `w_macro`, `w_star`, `w_bearmom`, `w_near`, `half_size_hint`, `bar_close` (UTC ISO of the 15m bar close).
Python reference: `src/caution_lines.py`. The dashboard has a "Caution (info only)" row.

Example (a real C1 entry, 2026-09-03 14:00 ET, rebuilt with the Pine formulas by `analysis/v35/example_alert.py`), Telegram text:

```
ENTRY XRPUSDT @ 1.4677
v3.5-test
[v3.5 TEST] Long entry — 15m+2H stack synced, C1 held 2 x 2H opens | ⚠️ Near resistance 1.4726 (+0.20 ATR2H, 2H)
⚠ macro <24h: NFP in 18.2h (Sep 04 08:30 ET)
⚠ near resistance
Caution 2/4 · Risk: consider HALF size (advisory only — rules unchanged)
```

**Nothing here blocks, delays or resizes a trade.** Proof (`analysis/v35/caution_stats.py`, output in `caution_stats_out.txt`):
- The C1 trade list is unchanged: 489 trades (IS 353 / OOS 136), PF 1.42 (IS 1.21 / OOS 2.09); the bar-by-bar Pine-order emulation with the caution
  flags computed in the loop is identical trade by trade (sha `54207bca4fc8ff8f`). `validate_c1.py` still reproduces 489 / 1.42.
- Every `strategy.` line is identical to v3.4-tag; caution variables never appear in entry/exit/sizing lines (`tests/test_v35_caution.py`).
- Pine ↔ research parity over all 236,401 15m bars: shooting-star bars 9,691 vs 9,691 (0 mismatches), "<2h" flag 0 mismatches,
  2H bear-momentum flag 0 mismatches. No-lookahead is also tested by truncating the data (flags up to bar k never change).

### Historical relationship to C1 outcomes — DESCRIPTIVE ONLY, not a filter

Same 489 C1 trades, 0.10% RT. "rank" = percentile of the subset's PF among 2,000 random subsets of the same size (seed 20260930).
These were looked at **after** the patterns were chosen on this same data, so they are not evidence of an edge.

| group | n (IS/OOS) | win % | PF | PF IS | PF OOS | avg % | rank |
|---|---|---|---|---|---|---|---|
| all C1 | 489 (353/136) | 32.7 | 1.42 | 1.21 | 2.09 | +0.48 | – |
| macro <24h ON | 42 (30/12) | 21.4 | 0.72 | 1.16 | 0.00 | −0.46 | 14.5 |
| macro off | 447 (323/124) | 33.8 | 1.51 | 1.21 | 2.61 | +0.57 | 93.0 |
| shooting star <2h ON | 216 (146/70) | 34.3 | 1.10 | 1.04 | 1.26 | +0.12 | 9.2 |
| shooting star off | 273 (207/66) | 31.5 | 1.67 | 1.33 | 3.13 | +0.77 | 88.4 |
| 2H bear momentum at resistance ON | **0** | – | – | – | – | – | – |
| near resistance ON | 337 (248/89) | 31.8 | 1.42 | 1.07 | 2.73 | +0.44 | 49.2 |
| near resistance off | 152 (105/47) | 34.9 | 1.41 | 1.45 | 1.30 | +0.59 | 50.2 |
| score 0 | 77 (54/23) | 35.1 | 1.52 | 1.03 | 3.51 | +0.72 | 60.0 |
| score 1 | 242 (183/59) | 33.1 | 1.77 | 1.68 | 2.06 | +0.82 | 92.2 |
| **score ≥ 2** | 170 (116/54) | 31.2 | 0.91 | 0.64 | 1.60 | −0.11 | 3.9 |
| score ≤ 1 | 319 (237/82) | 33.5 | 1.69 | 1.49 | 2.46 | +0.80 | 95.0 |

Reading it honestly:
- **2H bear momentum at resistance never coincided with a C1 entry** (0/489; 2 of 2,868 v3.3 2H-open long bars). C1 needs the 2H stack up on
  that same completed 2H bar, so two strong red 2H bars there are structurally rare. The line will almost never print.
- **Near resistance** is on 69% of entries and does not separate outcomes (PF 1.42 vs 1.41).
- **Shooting star** and **macro** subsets did worse on average, but neither is significant (ranks 9.2 and 14.5) and both flip by year
  (star-ON yearly PF 1.73, 0.83, 0.95, 0.48, 1.54, 1.70, 0.34; macro-ON 0.43, 3.0, 0.86, 0.31, 0.0, 0.0, 0.0 with only 3–12 trades a year).
- **Score ≥ 2** (170 trades, 157 of them = 2/4, 13 = 3/4): PF 0.91 vs 1.69, but IS 0.64 vs OOS 1.60 (still profitable OOS) and yearly PF
  0.22, 1.32, 0.37, 0.26, 1.62, 2.31, 0.37. A what-if with half notional on score ≥ 2 (100% notional otherwise, compounded, not the
  risk-% sizing) gave +554% / maxDD 49.9% vs +450% / 59.3% at full size: in-sample and post-hoc, so it only justifies an *advisory* line.
- Earlier, using the star as a **veto** failed the OOS null (82.5) and the robustness scan (1/72). It stays a note, not a rule.

### Forward paper-tracking log (not wired into any routine)

`analysis/v35/forward_log/`: `schema.csv` (columns), `forward_log.py` (`entry` / `exit` / `ingest recent_alerts.json` / `summary`,
idempotent, ignores non-`v3.5-test` alerts), `test_forward_log.py`. Judge the warnings only on alerts after 2026-10-02.
At ~70 C1 trades a year and ~35% of them at score ≥ 2, it needs 1–2 years before saying anything.

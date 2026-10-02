"""v3.5 TEST caution lines + score: notify-only isolation, closed-bar/no-lookahead, Pine <-> Python parity, alert text.
No TradingView, no network. Full-history parity/trade-list proof: analysis/v35/caution_stats.py (489 trades, PF 1.42)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.alert_notify import format_alert
from src.caution_lines import LINES, bear_mom_res, caution_score, caution_text, macro_due, shooting_star, star_recent

ROOT = Path(__file__).resolve().parents[1]
PINE = (ROOT / "pine" / "xrp_stacked_mtf_v3.5_test.pine").read_text(encoding="utf-8")
V34 = (ROOT / "pine" / "xrp_stacked_mtf_v3.4_tag.pine").read_text(encoding="utf-8")
CODE = [ln for ln in PINE.splitlines() if not ln.lstrip().startswith("//")]
CAUTION_NAMES = ("useCaution", "cwAtr14", "cwBody", "cwRng", "cwUw", "cwLw", "cwStar", "cwStarN", "warnStar", "warnBearMom",
                 "warnNear", "warnMacro", "cautionN", "cautionRisk", "cautionTxt", "cautionJson", "f_bearMomRes")
TRADE_TOKENS = ("strategy.", "enterLong =", "exitSig =", "exitFired =", "sizeFor", "riskDist", "stopLevel", "prevSyncLong",
                "longCond", "delayOK", "entryTrig", "syncOK", "flat =", "inRange =")


def _uses(name):
    return [ln for ln in CODE if re.search(rf"\b{name}\b", ln)]


def test_caution_never_feeds_trading_logic():
    for name in CAUTION_NAMES:
        for ln in _uses(name):
            assert not any(t in ln for t in TRADE_TOKENS), (name, ln)
    # cautionTxt / cautionJson: one definition + the single ENTRY alert line, nothing else
    for name in ("cautionTxt", "cautionJson"):
        u = _uses(name)
        assert len(u) == 2 and u[0].startswith(f"{name} = "), u
        assert u[1].lstrip().startswith('alert(useTags ? alertJsonX("ENTRY"') and u[1].count(name) == 2
    # the ENTRY alert sits inside `if enterLong`
    i = PINE.index('alert(useTags ? alertJsonX("ENTRY"')
    assert PINE.rfind("if enterLong\n", 0, i) > PINE.rfind("\nif ", 0, i) - 1


def test_order_and_trade_lines_identical_to_v34():
    lines = lambda s: {ln for ln in s.splitlines() if "strategy." in ln and not ln.lstrip().startswith("//")}
    assert lines(PINE) == lines(V34)                                   # every position/order/equity line unchanged
    assert PINE.count("strategy.entry(") == 1 and PINE.count("strategy.close(") == 1
    assert PINE.count("strategy.close_all(") == 1 and PINE.count("strategy.exit(") == 1
    assert "enterLong = inRange and flat and entryTrig and syncOK and delayOK\n" in PINE
    # caution block lives after all entry/exit/order code and before the alert block
    i_blk = PINE.index("// Caution lines + score — NOTIFY-ONLY")
    assert PINE.index("strategy.close_all(") < i_blk < PINE.index("// Alerts (notify-only")


def test_caution_block_closed_bars_no_lookahead():
    blk = PINE[PINE.index("// Caution lines + score — NOTIFY-ONLY"):PINE.index("// Alerts (notify-only")]
    code = "\n".join(ln for ln in blk.splitlines() if not ln.lstrip().startswith("//"))
    for bad in ("request.security", "lookahead", "timenow", "barstate.isrealtime", "calc_on_every_tick", "[-"):
        assert bad not in code, bad
    assert len([ln for ln in CODE if "request.security(" in ln]) == 4    # unchanged from v3.5 base
    assert "calc_on_every_tick = false" in PINE and "alert.freq_once_per_bar_close" in PINE
    # history-dependent calls at global scope (executed every bar), not inside if-blocks
    for ln in ("warnBearMom = f_bearMomRes(\"120\", 5, 4, 14)", "cwStarN = math.sum(cwStar ? 1 : 0, 8)", "cwAtr14 = ta.atr(14)"):
        assert "\n" + ln + "\n" in PINE, ln
    # 2H value is set only when a NEW 2H bar starts, from the bar that just COMPLETED (cO/cH/cL/cC before reset)
    fb = blk[blk.index("f_bearMomRes(tf"):blk.index("warnBearMom =")]
    assert fb.index("if newBar and not na(cC)") < fb.index("sig := mom and anyKey") < fb.index("if newBar or na(cH)")


def test_pine_constants_match_research_definition():
    assert ("cwStar = cwUw >= 2.0 * cwBody and cwUw >= 0.5 * cwRng and cwLw <= 0.3 * cwRng and cwRng >= 0.5 * cwAtr14 "
            "and close[1] > close[7]\n") in PINE
    assert "math.abs(phCur - phPrev) <= 1.0 * atrR" in PINE
    assert "cH >= phCur - 0.5 * atrR and cH <= phCur + 0.5 * atrR and cC < phCur" in PINE
    assert "cC < cO and prvC < prvO and math.abs(cC - cO) > math.abs(prvC - prvO)" in PINE
    assert "isPH := isPH and array.get(hs, m) < ch" in PINE and "isPH := isPH and array.get(hs, m) <= ch" in PINE
    assert 'warnNear = resState == "NEAR"' in PINE and "warnMacro = macroHit" in PINE


def test_alert_strings_match_python_reference():
    for txt in LINES.values():
        assert f'"\\\\n{txt}"' in PINE, txt
    assert '"\\\\nCaution " + str.tostring(cautionN) + "/4 · " + cautionRisk' in PINE
    for risk in ("Risk: consider HALF size (advisory only — rules unchanged)", "Risk: normal size per plan (advisory)"):
        assert f'"{risk}"' in PINE and risk in caution_text({"star": True, "near": True}) + caution_text({})
    assert "cautionN >= 2 ?" in PINE
    assert "cautionN = (warnMacro ? 1 : 0) + (warnStar ? 1 : 0) + (warnBearMom ? 1 : 0) + (warnNear ? 1 : 0)\n" in PINE


def test_entry_payload_telegram_text():
    note = ("[v3.5 TEST] Long entry — 15m+2H stack synced, C1 held 2 x 2H opens | ⚠️ Near resistance 1.4726 (+0.20 ATR2H, 2H)"
            "\\n⚠ macro <24h: NFP in 18.2h (Sep 04 08:30 ET)\\n⚠ near resistance\\nCaution 2/4 · Risk: consider HALF size (advisory only — rules unchanged)")
    raw = ('{"action":"ENTRY","strategy":"v3.5-test","symbol":"XRPUSDT","tf":"15","price":1.4677,"note":"' + note + '"'
           ',"res_state":"NEAR","caution":2,"w_macro":true,"w_star":false,"w_bearmom":false,"w_near":true,"half_size_hint":true'
           ',"bar_close":"2026-09-03T18:15:00Z"}')
    p = json.loads(raw)
    out = format_alert(p).splitlines()
    assert out[:2] == ["ENTRY XRPUSDT @ 1.4677", "v3.5-test"]
    assert out[3:] == ["⚠ macro <24h: NFP in 18.2h (Sep 04 08:30 ET)", "⚠ near resistance",
                       "Caution 2/4 · Risk: consider HALF size (advisory only — rules unchanged)"]
    w = dict(macro=p["w_macro"], star=p["w_star"], bearmom=p["w_bearmom"], near=p["w_near"])
    assert caution_score(w) == p["caution"] and caution_text(w).splitlines() == out[4:]


def test_score_counts():
    assert caution_score({}) == 0 and caution_text({}) == "Caution 0/4 · Risk: normal size per plan (advisory)"
    t = caution_text(dict(macro=True, star=True, bearmom=True, near=True)).splitlines()
    assert t == [LINES["star"], LINES["bearmom"], LINES["near"], "Caution 4/4 · Risk: consider HALF size (advisory only — rules unchanged)"]
    assert caution_text(dict(star=True)).endswith("Caution 1/4 · Risk: normal size per plan (advisory)")


def _df(rows, start="2026-01-01", freq="15min"):
    idx = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx).assign(volume=1.0)


def test_shooting_star_synthetic():
    rows = [(1.00 + 0.01 * k, 1.012 + 0.01 * k, 0.998 + 0.01 * k, 1.01 + 0.01 * k) for k in range(30)]  # steady rise
    o = rows[-1][3]
    rows.append((o, o + 0.08, o - 0.002, o + 0.005))     # long upper wick, small body, tiny lower wick, big range
    df = _df(rows)
    s = shooting_star(df)
    assert s[-1] and not s[:-1].any()
    rec = star_recent(np.r_[s, np.zeros(10, bool)], 8)
    assert rec[30:38].all() and not rec[38:].any()       # "<2h" = this + next 7 closed 15m bars only


def _random_df(n=3000, seed=1):
    rng = np.random.default_rng(seed)
    c = 1.5 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.003, n)))
    l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.003, n)))
    return _df(list(zip(o, h, l, c)))


def test_no_lookahead_truncation():
    df = _random_df()
    s_full, b_full = shooting_star(df), bear_mom_res(df)
    assert s_full.any() and b_full.any()
    for k in (500, 1234, 2001, 2999):
        assert (shooting_star(df.iloc[:k]) == s_full[:k]).all()
        assert (bear_mom_res(df.iloc[:k]) == b_full[:k]).all()


def test_bear_mom_constant_within_2h_and_only_from_completed_bars():
    df = _random_df(seed=7)
    b = bear_mom_res(df)
    bucket = df.index.floor("2h")
    for _, g in pd.Series(b, index=df.index).groupby(bucket):
        assert g.nunique() == 1                                  # set at the 2H open, held for the whole 2H period
    # changing bars inside the current (forming) 2H bar cannot change the flag on that bar
    i = int(np.flatnonzero(df.index == df.index.floor("2h"))[200])
    df2 = df.copy(); df2.iloc[i:i + 8, :4] = df2.iloc[i:i + 8, :4] * 1.2
    assert (bear_mom_res(df2)[: i + 8] == b[: i + 8]).all()


def test_macro_due_window():
    ev = [pd.Timestamp("2026-10-14 12:30", tz="UTC")]
    t = pd.DatetimeIndex([pd.Timestamp("2026-10-13 13:00", tz="UTC"), pd.Timestamp("2026-10-13 12:00", tz="UTC"),
                          pd.Timestamp("2026-10-14 12:45", tz="UTC")]).as_unit("s")     # unit-agnostic (pandas 3)
    assert macro_due(t, ev, 24.0).tolist() == [True, False, False]

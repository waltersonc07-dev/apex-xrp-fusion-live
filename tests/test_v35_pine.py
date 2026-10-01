"""Static checks on pine/xrp_stacked_mtf_v3.5_test.pine (v3.5 TEST: C1 delay + macro warning). No TradingView, no network."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.alert_notify import format_alert

ROOT = Path(__file__).resolve().parents[1]
PINE = (ROOT / "pine" / "xrp_stacked_mtf_v3.5_test.pine").read_text(encoding="utf-8")
V34 = (ROOT / "pine" / "xrp_stacked_mtf_v3.4_tag.pine").read_text(encoding="utf-8")

# Official schedules (checked 2026-10-01): bls.gov/schedule/news_release/{cpi,empsit}.htm, federalreserve.gov fomccalendars.htm
EXPECTED_EVENTS_ET = [
    ("NFP", "2026-10-02 08:30"), ("CPI", "2026-10-14 08:30"), ("FOMC", "2026-10-28 14:00"),
    ("NFP", "2026-11-06 08:30"), ("CPI", "2026-11-10 08:30"), ("NFP", "2026-12-04 08:30"),
    ("FOMC", "2026-12-09 14:00"), ("CPI", "2026-12-10 08:30"),
    ("FOMC", "2027-01-27 14:00"), ("FOMC", "2027-03-17 14:00"), ("FOMC", "2027-04-28 14:00"), ("FOMC", "2027-06-09 14:00"),
    ("FOMC", "2027-07-28 14:00"), ("FOMC", "2027-09-15 14:00"), ("FOMC", "2027-10-27 14:00"), ("FOMC", "2027-12-08 14:00"),
]


def _et_to_utc(s: str) -> datetime:
    from zoneinfo import ZoneInfo
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc)


def _pine_events() -> list[tuple[str, datetime]]:
    m = re.search(r'macroEvents = input\.string\("([^"]+)"', PINE)
    assert m, "macroEvents input missing"
    out = []
    for item in m.group(1).replace(" ", "").split(","):
        label, d = item.split("@")
        out.append((label, datetime.strptime(d, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)))
    return out


def _macro_hits(now: datetime, ahead_h: float = 24.0) -> list[str]:
    """Python mirror of Pine f_macro: releases with 0 <= t - now <= ahead."""
    return [lbl for lbl, t in _pine_events() if timedelta(0) <= t - now <= timedelta(hours=ahead_h)]


def test_c1_gate_and_load_bearing_order():
    i_delay = PINE.index("delayOK = useC1 ? prevSyncLong : true\n")
    i_enter = PINE.index("enterLong = inRange and flat and entryTrig and syncOK and delayOK\n")
    i_upd = PINE.index("if is2hOpen\n    prevSyncLong := longCond\n")
    assert PINE.index("var bool prevSyncLong = false\n") < i_delay < i_enter < i_upd
    assert PINE.count("prevSyncLong :=") == 1                     # single writer
    assert "LOAD-BEARING ORDER" in PINE and "NOT entryTrig" in PINE
    assert 'useC1 = input.bool(true, "C1: delay entry by one 2H close' in PINE
    # nothing between enterLong and the update block reads/writes position or orders
    assert "strategy." not in PINE[i_enter:i_upd]


def test_logic_outside_c1_unchanged_vs_v34():
    for line in ["longCond = anySelected and htfOK and stackUp\n", "entryTrig = freshOnly ? (longCond and not longCond[1]) : longCond\n",
                 "syncOK = requireSync ? is2hOpen : true\n", "rawRisk = close - stLine\n",
                 "riskDist = rawRisk > syminfo.mintick ? rawRisk : atrVal * stMult\n", "    q = sizeFor(riskDist)\n",
                 "exitFired = strategy.position_size > 0 and exitSig\n", 'freshOnly = input.bool(false,']:
        assert line in PINE and line in V34
    assert "atrMult" not in PINE and "f_atrPrev" not in PINE          # ATR sizing rejected
    assert PINE.count("strategy.entry(") == 1 and PINE.count("strategy.close(") == 1
    assert PINE.count("strategy.close_all(") == 1 and PINE.count("strategy.exit(") == 1


def test_no_lookahead_htf():
    lines = [ln for ln in PINE.splitlines() if "request.security(" in ln and not ln.lstrip().startswith("//")]
    assert len(lines) == 4
    for ln in lines:
        if "lookahead_on" in ln:
            assert "Prev()" in ln, ln                                  # confirmed HTF bar: [1] inside the HTF context
        else:                                                          # only the opt-in repainting "live" path
            assert "lookahead_off" in ln and ln.startswith(("htfUpLive", "htfDnLive")), ln
    assert "useLiveHTF = input.bool(false" in PINE


def test_test_title_and_tag():
    assert 'strategy("XRP Stacked MTF v3.5 TEST"' in PINE
    assert '"strategy":"v3.5-test"' in PINE and "StackedMTF_v3.4tag" not in PINE
    assert "commission_value = 0.1," in PINE and "slippage = 2," in PINE
    assert 'timestamp("2099-12-31T23:59:00"), "Backtest end"' in PINE


def test_macro_events_match_official_schedule():
    ev = _pine_events()
    assert [(l, t) for l, t in ev] == [(l, _et_to_utc(s)) for l, s in EXPECTED_EVENTS_ET]
    assert [t for _, t in ev] == sorted(t for _, t in ev)
    assert {l for l, _ in ev} == {"CPI", "NFP", "FOMC"}


def test_macro_window_mirror():
    cpi = _et_to_utc("2026-10-14 08:30")
    assert _macro_hits(cpi - timedelta(hours=23, minutes=30)) == ["CPI"]
    assert _macro_hits(cpi - timedelta(hours=24, minutes=15)) == []
    assert _macro_hits(cpi + timedelta(minutes=15)) == []            # already released -> no warning
    assert _macro_hits(_et_to_utc("2026-12-09 12:00")) == ["FOMC", "CPI"]


def test_macro_is_entry_only_and_informational():
    uses = [ln for ln in PINE.splitlines() if "macroTxt" in ln and not ln.lstrip().startswith("//")]
    assert len(uses) == 2 and uses[0].startswith("macroTxt = ")
    assert 'alertJsonX("ENTRY"' in uses[1] and 'alertJson("ENTRY"' in uses[1]
    for name in ("macroHit", "macroList"):                           # never feeds entry/exit/sizing
        for ln in PINE.splitlines():
            if name in ln and ("enterLong =" in ln or "exitSig =" in ln or "sizeFor" in ln):
                raise AssertionError(ln)


def test_entry_payload_with_macro_line_parses():
    pine_note = "[v3.5 TEST] Long entry — 15m+2H stack synced, C1 held 2 x 2H opens | ✅ Clear\\n⚠ macro <24h: CPI in 23.5h (Oct 14 08:30 ET)"
    raw = '{"action":"ENTRY","strategy":"v3.5-test","symbol":"XRPUSDT","tf":"15","price":1.5229,"note":"' + pine_note + '"}'
    out = format_alert(json.loads(raw)).splitlines()
    assert out[:2] == ["ENTRY XRPUSDT @ 1.5229", "v3.5-test"]
    assert out[-1] == "⚠ macro <24h: CPI in 23.5h (Oct 14 08:30 ET)"

"""Static checks on pine/xrp_stacked_mtf_v3.4_tag.pine alert coverage and defaults (no TradingView, no network)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from src.alert_notify import format_alert

PINE = (Path(__file__).resolve().parents[1] / "pine" / "xrp_stacked_mtf_v3.4_tag.pine").read_text(encoding="utf-8")


def test_every_exit_path_has_exit_alert():
    assert 'alert(alertJson("EXIT", exitShort)' in PINE                       # stack-flip / signal exit
    assert re.search(r'if stopFilled\n\s+alert\(alertJson\("EXIT", "L-Stop filled', PINE)
    assert re.search(r'if windowExitAlert\n\s+alert\(alertJson\("EXIT", "Window end', PINE)
    assert 'strategy.closedtrades.exit_id(i) == "L-Stop"' in PINE
    # exactly the three order paths that can close the long
    assert PINE.count("strategy.close(") == 1 and PINE.count("strategy.close_all(") == 1 and PINE.count("strategy.exit(") == 1


def test_defaults_costs_and_window():
    assert "commission_value = 0.1," in PINE and re.search(r"slippage = [12],", PINE)
    assert 'timestamp("2099-12-31T23:59:00"), "Backtest end"' in PINE
    assert "strategy.closedtrades.profit(i) + strategy.closedtrades.commission(i)" in PINE


def test_entry_exit_logic_unchanged():
    assert "enterLong = inRange and flat and entryTrig and syncOK\n" in PINE
    assert "exitFired = strategy.position_size > 0 and exitSig\n" in PINE


def test_new_exit_payloads_parse_like_existing_exit():
    for note in ["Stack flip", "L-Stop filled @ 1.5229", "Window end — force-closed (flattenEnd)"]:
        raw = ('{"action":"EXIT","strategy":"StackedMTF_v3.4tag","symbol":"XRPUSDT","tf":"15","price":1.5229,"note":"' + note + '"}')
        out = format_alert(json.loads(raw))
        assert out.splitlines() == ["EXIT XRPUSDT @ 1.5229", "StackedMTF_v3.4tag", note]

"""Regression: filtered Phase 10 verdict must BLOCK every (symbol, variant).

If this test ever fails it means a variant passed the validation gate with
filters ON. That is *not* a green light to flip MICRO_LIVE — it is a green
light for a human to manually review the candidate, per SAFETY.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPORTS = Path(__file__).resolve().parents[1] / "reports"
VERDICT_JSON = REPORTS / "phase10_verdict_filtered.json"


def _has_verdict_file() -> bool:
    return VERDICT_JSON.exists()


@pytest.mark.skipif(
    not _has_verdict_file(),
    reason="phase10_verdict_filtered.json not present (run "
    "`python -m src.phase10_fx_gold_daily --filters both "
    "--regimes-allowed trending --output reports/phase10_verdict_filtered.md "
    "--json-output reports/phase10_verdict_filtered.json` to generate).",
)
def test_filtered_verdict_blocks_all_variants():
    """Every (symbol, variant) must BLOCK under the filtered run.

    A PASS here would require manual review before any live activation —
    this test should be updated in the same PR that approves such a candidate.
    """
    data = json.loads(VERDICT_JSON.read_text())
    results = data["results"]

    passes = []
    for symbol, variants in results.items():
        for vname, v in variants.items():
            verdict = v.get("verdict", "BLOCK")
            if verdict == "PASS":
                passes.append(f"{symbol}/{vname}")

    assert not passes, (
        "Filtered Phase 10 verdict has PASS candidates that need manual review "
        f"before any MICRO_LIVE flip: {passes}. Do NOT auto-merge a change to "
        "this test — update it deliberately as part of the candidate-approval PR."
    )


@pytest.mark.skipif(
    not _has_verdict_file(),
    reason="phase10_verdict_filtered.json not present",
)
def test_filtered_verdict_has_all_symbols_and_variants():
    """The filtered verdict must cover the full universe — no silent drops."""
    data = json.loads(VERDICT_JSON.read_text())
    results = data["results"]
    expected_symbols = {"EURUSD", "GBPUSD", "XAUUSD", "USDJPY"}
    expected_variants = {"V0", "V1", "V2", "V3"}

    assert set(results.keys()) == expected_symbols, (
        f"Filtered verdict missing symbols: expected {expected_symbols}, got {set(results.keys())}"
    )
    for sym, variants in results.items():
        assert set(variants.keys()) == expected_variants, (
            f"{sym}: expected variants {expected_variants}, got {set(variants.keys())}"
        )


@pytest.mark.skipif(
    not _has_verdict_file(),
    reason="phase10_verdict_filtered.json not present",
)
def test_filtered_verdict_records_filter_config():
    """The filtered verdict JSON must record that filters were ON.

    Prevents accidentally committing a baseline run under the filtered filename.
    """
    data = json.loads(VERDICT_JSON.read_text())
    cfg = data.get("config", {})
    assert cfg.get("enable_session_filter") is True, (
        f"phase10_verdict_filtered.json must have enable_session_filter=True; got {cfg!r}"
    )
    assert cfg.get("enable_regime_filter") is True, (
        f"phase10_verdict_filtered.json must have enable_regime_filter=True; got {cfg!r}"
    )

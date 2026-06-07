"""
Phase 11 — Frozen grid loader and validator tests (PR 2).

Covers Amendment A § A.2 invariants:

  1. Hard cap is enforced (loader rejects > HARD_CAP combos).
  2. Ghost parameters (names the engine does not read) are rejected.
  3. Empty value lists are rejected (would silently collapse combos).
  4. Unknown constraint names are rejected.
  5. Missing 'variants' or unexpected variant set is rejected.
  6. Declarative constraints actually filter combinations
     (fast_less_than_slow, exit_le_entry).
  7. Frozen file checked in at config/phase11_grid.yaml loads and totals
     match the docs/phase11_grid_changelog.md entry #001 figures
     (V0=36, V1=36, V2=24, V3=27, TOTAL=123).
  8. GridCombo.key is stable and deterministic.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.phase11_grid import (
    ALLOWED_PARAMETER_NAMES,
    DEFAULT_GRID_PATH,
    EXPECTED_VARIANTS,
    GridCombo,
    GridValidationError,
    HARD_CAP,
    load_grid,
    summarize,
)


# ---------------------------------------------------------------------------
# Real frozen grid (the one checked into config/)
# ---------------------------------------------------------------------------


def test_frozen_grid_loads_without_error() -> None:
    spec = load_grid()
    assert spec.total > 0
    assert spec.hard_cap <= HARD_CAP


def test_frozen_grid_counts_match_changelog_entry_001() -> None:
    spec = load_grid()
    # Numbers from docs/phase11_grid_changelog.md entry #001.
    assert spec.per_variant_counts == {"V0": 36, "V1": 36, "V2": 24, "V3": 27}
    assert spec.total == 123


def test_frozen_grid_total_under_hard_cap() -> None:
    spec = load_grid()
    assert spec.total <= HARD_CAP, (
        f"frozen grid has {spec.total} combos, exceeds HARD_CAP={HARD_CAP}"
    )


def test_summarize_includes_per_variant_counts() -> None:
    spec = load_grid()
    text = summarize(spec)
    for v in EXPECTED_VARIANTS:
        assert v in text


def test_frozen_grid_uses_only_engine_keys() -> None:
    spec = load_grid()
    for combo in spec.combos:
        unknown = set(combo.params.keys()) - ALLOWED_PARAMETER_NAMES
        assert not unknown, (
            f"combo {combo.key} has ghost parameter(s) {unknown}"
        )


def test_frozen_grid_constraints_applied() -> None:
    """fast_less_than_slow and exit_le_entry must actually filter combos."""
    spec = load_grid()
    for combo in spec.combos:
        if combo.variant in ("V0", "V1"):
            assert combo.params["ema_fast"] < combo.params["ema_slow"], (
                f"combo {combo.key} violates fast_less_than_slow"
            )
        if combo.variant == "V2":
            assert combo.params["donchian_out"] <= combo.params["donchian_in"], (
                f"combo {combo.key} violates exit_le_entry"
            )


# ---------------------------------------------------------------------------
# Synthetic grids — round-trip through a tmp YAML file
# ---------------------------------------------------------------------------


def _write_grid(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "grid.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _baseline_payload() -> dict:
    """A minimum-valid grid covering all four expected variants."""
    return {
        "version": 1,
        "hard_cap": 140,
        "variants": {
            "V0": {"parameters": {
                "ema_fast": [13], "ema_slow": [34], "rsi_length": [14],
                "atr_stop_mult": [2.0],
            }, "constraints": ["fast_less_than_slow"]},
            "V1": {"parameters": {
                "ema_fast": [13], "ema_slow": [34], "rsi_length": [14],
                "atr_stop_mult": [2.0],
            }, "constraints": ["fast_less_than_slow"]},
            "V2": {"parameters": {
                "donchian_in": [20], "donchian_out": [10],
                "atr_stop_mult": [2.0],
            }, "constraints": ["exit_le_entry"]},
            "V3": {"parameters": {
                "bb_length": [20], "bb_std": [2.0], "atr_stop_mult": [2.0],
            }},
        },
    }


def test_loader_rejects_exceeding_hard_cap(tmp_path: Path) -> None:
    payload = _baseline_payload()
    # Inflate V0 well over the cap. 6 params with the constraint pruning
    # still leaves >140 combos.
    payload["variants"]["V0"]["parameters"] = {
        "ema_fast":      list(range(5, 13)),   # 8 values
        "ema_slow":      [200],
        "rsi_length":    list(range(5, 25)),   # 20 values
        "atr_stop_mult": [1.0, 1.5, 2.0],      # 3 values
    }
    grid_path = _write_grid(tmp_path, payload)
    with pytest.raises(GridValidationError, match="exceeds the .* HARD_CAP"):
        load_grid(grid_path)


def test_loader_rejects_declared_hard_cap_above_module_cap(tmp_path: Path) -> None:
    payload = _baseline_payload()
    payload["hard_cap"] = 1000
    grid_path = _write_grid(tmp_path, payload)
    with pytest.raises(GridValidationError, match="exceeds the module-level"):
        load_grid(grid_path)


def test_loader_rejects_ghost_parameter(tmp_path: Path) -> None:
    payload = _baseline_payload()
    payload["variants"]["V3"]["parameters"]["mid_exit"] = [True, False]
    grid_path = _write_grid(tmp_path, payload)
    with pytest.raises(GridValidationError, match="unknown parameter"):
        load_grid(grid_path)


def test_loader_rejects_empty_value_list(tmp_path: Path) -> None:
    payload = _baseline_payload()
    payload["variants"]["V2"]["parameters"]["donchian_in"] = []
    grid_path = _write_grid(tmp_path, payload)
    with pytest.raises(GridValidationError, match="non-empty list"):
        load_grid(grid_path)


def test_loader_rejects_unknown_constraint(tmp_path: Path) -> None:
    payload = _baseline_payload()
    payload["variants"]["V0"]["constraints"] = ["something_invented"]
    grid_path = _write_grid(tmp_path, payload)
    with pytest.raises(GridValidationError, match="unknown constraint"):
        load_grid(grid_path)


def test_loader_rejects_missing_variant(tmp_path: Path) -> None:
    payload = _baseline_payload()
    del payload["variants"]["V3"]
    grid_path = _write_grid(tmp_path, payload)
    with pytest.raises(GridValidationError, match="variants must be exactly"):
        load_grid(grid_path)


def test_loader_rejects_missing_top_level_key(tmp_path: Path) -> None:
    payload = _baseline_payload()
    del payload["hard_cap"]
    grid_path = _write_grid(tmp_path, payload)
    with pytest.raises(GridValidationError, match="missing required top-level"):
        load_grid(grid_path)


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(GridValidationError, match="not found"):
        load_grid(tmp_path / "does_not_exist.yaml")


def test_constraint_prunes_invalid_combinations(tmp_path: Path) -> None:
    """fast_less_than_slow must drop (21, 21) and (34, 21) style pairs."""
    payload = _baseline_payload()
    payload["variants"]["V0"]["parameters"] = {
        "ema_fast": [13, 21, 34],
        "ema_slow": [21, 34],
        "rsi_length": [14],
        "atr_stop_mult": [2.0],
    }
    grid_path = _write_grid(tmp_path, payload)
    spec = load_grid(grid_path)
    # Valid pairs: (13,21)(13,34)(21,34) = 3. Other variants contribute 1 each.
    assert spec.per_variant_counts["V0"] == 3


def test_constraint_exit_le_entry_prunes_v2(tmp_path: Path) -> None:
    payload = _baseline_payload()
    payload["variants"]["V2"]["parameters"] = {
        "donchian_in": [10, 20, 40],
        "donchian_out": [5, 10, 20],
        "atr_stop_mult": [2.0],
    }
    grid_path = _write_grid(tmp_path, payload)
    spec = load_grid(grid_path)
    # Valid pairs where out<=in: (10,5)(10,10)(20,5)(20,10)(20,20)(40,5)(40,10)(40,20) = 8.
    assert spec.per_variant_counts["V2"] == 8


# ---------------------------------------------------------------------------
# GridCombo.key
# ---------------------------------------------------------------------------


def test_grid_combo_key_is_stable_and_sorted() -> None:
    # Same params, different insertion order — key must match.
    c1 = GridCombo(variant="V0", params={"a": 1, "b": 2})
    c2 = GridCombo(variant="V0", params={"b": 2, "a": 1})
    assert c1.key == c2.key == "V0|a=1,b=2"


def test_grid_combo_key_differs_on_variant() -> None:
    c1 = GridCombo(variant="V0", params={"a": 1})
    c2 = GridCombo(variant="V1", params={"a": 1})
    assert c1.key != c2.key

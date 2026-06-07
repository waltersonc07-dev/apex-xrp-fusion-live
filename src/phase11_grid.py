"""
Phase 11 — Frozen Parameter Grid loader and validator.

Loads ``config/phase11_grid.yaml`` and produces the canonical list of
(variant, params) combinations that the grid-search engine in
``src.phase11_search`` will evaluate.

This module is the single enforcement point for Amendment A § A.2 of
``docs/phase11_design.md``:

  * HARD CAP of 140 combinations across all variants combined.
  * Every parameter name must map to a key the Phase 10 backtest engine
    actually reads (no "ghost" parameters).
  * Constraint declarations (``fast_less_than_slow``, ``exit_le_entry``) are
    applied during enumeration so the loader's combination count matches
    the search engine's actual run count.

The loader is intentionally strict: any mismatch, missing constraint, or
cap violation raises ``GridValidationError`` at import / load time. The
search engine refuses to run on an invalid grid.

This module is read-only. It does not write to ``config/``, ``.env*``,
``render.yaml``, or any execution path. The safety-invariant scan in
``tests/test_phase11_safety_invariants.py`` covers this file as well as
``src/phase11_orchestrator.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from pathlib import Path

import yaml


# Hard cap from Amendment A § A.2. Encoded here as well as in the YAML so a
# YAML tampered to raise its own cap still trips the loader.
HARD_CAP = 140

# Engine cfg keys the Phase 11 grid is allowed to tune. Anything outside
# this set is rejected by the loader as a "ghost" parameter. The set
# tracks what ``src.phase10_fx_gold_daily`` actually reads in its variant
# signal builders and exit/risk-sizing layer.
ALLOWED_PARAMETER_NAMES = frozenset({
    "ema_fast",
    "ema_slow",
    "rsi_length",
    "atr_stop_mult",
    "donchian_in",
    "donchian_out",
    "bb_length",
    "bb_std",
})

# Supported declarative constraints. Each maps to a callable that returns
# True when a candidate parameter dict is *valid* (i.e. the constraint is
# satisfied) and the combination should be kept.
CONSTRAINT_VALIDATORS = {
    "fast_less_than_slow": lambda p: p.get("ema_fast", 0) < p.get("ema_slow", 0),
    "exit_le_entry":       lambda p: p.get("donchian_out", 0) <= p.get("donchian_in", 0),
}

# The four Phase 10 variants — must exactly match keys in the YAML.
EXPECTED_VARIANTS = ("V0", "V1", "V2", "V3")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRID_PATH = REPO_ROOT / "config" / "phase11_grid.yaml"


class GridValidationError(ValueError):
    """Raised when the frozen Phase 11 grid violates any A.2 invariant."""


@dataclass(frozen=True)
class GridCombo:
    """One concrete (variant, params) combination from the grid."""
    variant: str
    params: dict          # NOTE: dataclass field is dict, but we treat it as
                          # immutable. We use ``hash`` indirectly via the
                          # ``key`` property; do not mutate ``params``.

    @property
    def key(self) -> str:
        """Stable string key for sorting / deduping. Deterministic across runs."""
        items = sorted(self.params.items())
        body = ",".join(f"{k}={v}" for k, v in items)
        return f"{self.variant}|{body}"


@dataclass(frozen=True)
class GridSpec:
    """Result of loading and expanding the frozen grid."""
    version: int
    hard_cap: int
    combos: tuple[GridCombo, ...]
    per_variant_counts: dict[str, int]

    @property
    def total(self) -> int:
        return len(self.combos)


def load_grid(path: Path | None = None) -> GridSpec:
    """Load + validate + expand ``config/phase11_grid.yaml``.

    Raises ``GridValidationError`` on any A.2 invariant violation.
    """
    path = path or DEFAULT_GRID_PATH
    if not path.exists():
        raise GridValidationError(f"frozen grid file not found at {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _validate_top_level(raw, path)

    declared_cap = int(raw["hard_cap"])
    if declared_cap > HARD_CAP:
        raise GridValidationError(
            f"grid declares hard_cap={declared_cap} which exceeds the "
            f"module-level HARD_CAP={HARD_CAP} from Amendment A § A.2"
        )

    variants = raw["variants"]
    if set(variants.keys()) != set(EXPECTED_VARIANTS):
        raise GridValidationError(
            f"grid variants must be exactly {set(EXPECTED_VARIANTS)}, "
            f"got {set(variants.keys())}"
        )

    combos: list[GridCombo] = []
    per_variant_counts: dict[str, int] = {}
    for variant in EXPECTED_VARIANTS:  # deterministic order
        spec = variants[variant]
        v_combos = _expand_variant(variant, spec)
        per_variant_counts[variant] = len(v_combos)
        combos.extend(v_combos)

    total = len(combos)
    if total == 0:
        raise GridValidationError("frozen grid expanded to zero combinations")
    if total > HARD_CAP:
        raise GridValidationError(
            f"frozen grid has {total} combinations which exceeds the "
            f"Amendment A § A.2 HARD_CAP of {HARD_CAP}"
        )

    return GridSpec(
        version=int(raw["version"]),
        hard_cap=declared_cap,
        combos=tuple(combos),
        per_variant_counts=per_variant_counts,
    )


def _validate_top_level(raw: dict, path: Path) -> None:
    required = {"version", "hard_cap", "variants"}
    missing = required - set(raw.keys())
    if missing:
        raise GridValidationError(
            f"frozen grid {path} missing required top-level keys: {sorted(missing)}"
        )
    if not isinstance(raw["variants"], dict) or not raw["variants"]:
        raise GridValidationError(
            f"frozen grid {path} 'variants' must be a non-empty mapping"
        )


def _expand_variant(variant: str, spec: dict) -> list[GridCombo]:
    if "parameters" not in spec or not isinstance(spec["parameters"], dict):
        raise GridValidationError(
            f"variant {variant!r}: missing or invalid 'parameters' mapping"
        )
    params = spec["parameters"]

    # Reject ghost parameters before enumeration so the error message is
    # specific to the offending name.
    unknown = set(params.keys()) - ALLOWED_PARAMETER_NAMES
    if unknown:
        raise GridValidationError(
            f"variant {variant!r}: unknown parameter(s) {sorted(unknown)}; "
            f"allowed names are {sorted(ALLOWED_PARAMETER_NAMES)}. "
            f"This usually means the parameter is not read by any "
            f"src/phase10_fx_gold_daily.py variant builder."
        )

    # Reject empty value lists explicitly — these would silently collapse
    # the variant to zero combos and pass the cap check trivially.
    for name, values in params.items():
        if not isinstance(values, list) or len(values) == 0:
            raise GridValidationError(
                f"variant {variant!r} parameter {name!r}: "
                f"must be a non-empty list, got {values!r}"
            )

    constraints = spec.get("constraints") or []
    if not isinstance(constraints, list):
        raise GridValidationError(
            f"variant {variant!r}: 'constraints' must be a list, "
            f"got {type(constraints).__name__}"
        )
    unknown_constraints = set(constraints) - set(CONSTRAINT_VALIDATORS.keys())
    if unknown_constraints:
        raise GridValidationError(
            f"variant {variant!r}: unknown constraint(s) "
            f"{sorted(unknown_constraints)}; "
            f"supported: {sorted(CONSTRAINT_VALIDATORS.keys())}"
        )

    # Deterministic enumeration: sort parameter names so the product order
    # is stable across runs and Python versions.
    names = sorted(params.keys())
    value_lists = [params[n] for n in names]
    out: list[GridCombo] = []
    for values in product(*value_lists):
        candidate = dict(zip(names, values))
        if all(CONSTRAINT_VALIDATORS[c](candidate) for c in constraints):
            out.append(GridCombo(variant=variant, params=candidate))
    return out


def summarize(spec: GridSpec) -> str:
    """Human-readable one-shot summary of a loaded grid."""
    lines = [
        f"Phase 11 frozen grid v{spec.version} — "
        f"{spec.total} combinations (cap {spec.hard_cap})",
    ]
    for variant in EXPECTED_VARIANTS:
        lines.append(f"  {variant}: {spec.per_variant_counts.get(variant, 0)}")
    return "\n".join(lines)

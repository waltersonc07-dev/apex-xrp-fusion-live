"""
Phase 11 safety-invariant tests (Amendment A § A.8 item 11).

Asserts that no Phase 11 code path can set, suggest, or auto-toggle any of:

    risk.mode, LIVE_TRADING, MICRO_LIVE, FULL_LIVE

The check is a static source scan of every ``src/phase11*.py`` file. Any
assignment, mutation, or environment write touching these names fails the
test. Read-only references (e.g. a constant string in a log line, or
documentation in a docstring) are allowed.

Why a static scan: an integration test can only prove that *the paths it
exercises* don't flip a flag. A source scan proves no path can. This is the
right safety posture for live-trading guardrails.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

# Names that must never appear on the LHS of an assignment, in os.environ writes,
# or as YAML/dict mutations within Phase 11 source files.
FORBIDDEN_NAMES = {
    "LIVE_TRADING",
    "MICRO_LIVE",
    "FULL_LIVE",
}
# The dotted attribute "risk.mode" is handled specifically below.


def _phase11_files() -> list[Path]:
    return sorted(SRC_DIR.glob("phase11*.py"))


def test_phase11_files_exist() -> None:
    files = _phase11_files()
    assert files, "expected at least one src/phase11*.py file"


@pytest.mark.parametrize("path", _phase11_files(), ids=lambda p: p.name)
def test_phase11_source_does_not_assign_live_flags(path: Path) -> None:
    """No Phase 11 file may assign LIVE_TRADING / MICRO_LIVE / FULL_LIVE."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[str] = []

    for node in ast.walk(tree):
        # Plain assignment: LIVE_TRADING = True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                violations.extend(_collect_forbidden_targets(target, path))
        # Augmented assignment: LIVE_TRADING |= True
        elif isinstance(node, ast.AugAssign):
            violations.extend(_collect_forbidden_targets(node.target, path))
        # Annotated assignment: LIVE_TRADING: bool = True
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            violations.extend(_collect_forbidden_targets(node.target, path))
        # os.environ["LIVE_TRADING"] = "true"  /  os.environ.update({...})
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            violations.extend(_collect_forbidden_targets(node, path))

    assert not violations, (
        f"Phase 11 file {path.name} contains forbidden live-flag assignments:\n"
        + "\n".join(violations)
    )


@pytest.mark.parametrize("path", _phase11_files(), ids=lambda p: p.name)
def test_phase11_source_does_not_mutate_risk_mode(path: Path) -> None:
    """No Phase 11 file may assign to ``risk.mode`` (or ``cfg['risk']['mode']``).

    We catch:
      * attribute writes like ``settings.risk.mode = ...``
      * subscript writes like ``cfg["risk"]["mode"] = ...``
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if _is_risk_mode_write(target):
                    violations.append(f"line {target.lineno}: writes risk.mode")
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            if node.target is not None and _is_risk_mode_write(node.target):
                violations.append(f"line {node.lineno}: writes risk.mode")

    assert not violations, (
        f"Phase 11 file {path.name} mutates risk.mode:\n" + "\n".join(violations)
    )


@pytest.mark.parametrize("path", _phase11_files(), ids=lambda p: p.name)
def test_phase11_source_does_not_import_execution_modules(path: Path) -> None:
    """Phase 11 must not import the live-trading or exchange modules.

    Importing them is not a flip by itself, but it removes a layer of
    defense-in-depth: a research module that cannot reach an execution
    function cannot accidentally call one.
    """
    forbidden_modules = {
        "src.exchange_client", ".exchange_client",
        "src.webhook_server", ".webhook_server",
        "src.risk_engine", ".risk_engine",
    }
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in forbidden_modules:
                    violations.append(f"line {node.lineno}: imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = ("." * (node.level or 0)) + (node.module or "")
            if mod in forbidden_modules:
                violations.append(f"line {node.lineno}: imports from {mod}")

    assert not violations, (
        f"Phase 11 file {path.name} imports forbidden execution modules:\n"
        + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_forbidden_targets(target: ast.AST, path: Path) -> list[str]:
    """Return human-readable violations for any forbidden write target."""
    out: list[str] = []
    # Plain name: LIVE_TRADING = ...
    if isinstance(target, ast.Name) and target.id in FORBIDDEN_NAMES:
        out.append(f"line {target.lineno}: writes {target.id}")
    # Tuple/list unpacking: (LIVE_TRADING, x) = ...
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            out.extend(_collect_forbidden_targets(elt, path))
    # Attribute write: cfg.LIVE_TRADING = ...
    elif isinstance(target, ast.Attribute) and target.attr in FORBIDDEN_NAMES:
        out.append(f"line {target.lineno}: writes .{target.attr}")
    # Subscript: os.environ["LIVE_TRADING"] = ...   or   d["LIVE_TRADING"] = ...
    elif isinstance(target, ast.Subscript):
        key = _const_str(target.slice)
        if key in FORBIDDEN_NAMES:
            out.append(f"line {target.lineno}: writes subscript ['{key}']")
    return out


def _is_risk_mode_write(target: ast.AST) -> bool:
    """Detect writes to risk.mode in either attribute or subscript form."""
    # Attribute form: <expr>.risk.mode = ...
    if isinstance(target, ast.Attribute) and target.attr == "mode":
        inner = target.value
        if isinstance(inner, ast.Attribute) and inner.attr == "risk":
            return True
    # Subscript form: cfg["risk"]["mode"] = ...
    if isinstance(target, ast.Subscript):
        key = _const_str(target.slice)
        if key == "mode" and isinstance(target.value, ast.Subscript):
            inner_key = _const_str(target.value.slice)
            if inner_key == "risk":
                return True
    return False


def _const_str(node: ast.AST) -> str | None:
    """Return the string constant inside a subscript slice, if present."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # py<3.9 Index wrapper — harmless to support.
    if isinstance(node, ast.Index):  # type: ignore[attr-defined]
        return _const_str(node.value)
    return None

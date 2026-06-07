"""Tests for the APEX safe-defaults checker (scripts/check_safe_defaults.py).

These tests confirm:
  1. The repository as currently committed passes the checker.
  2. Each unsafe modification is detected (env flag flipped to true, risk.mode
     changed, FULL_LIVE approved, a fake secret added to .env.example).

The tests work by copying the repo's safety-relevant files into a temp dir,
mutating one file at a time, and re-running the checker pointed at that dir.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_safe_defaults.py"


def _load_checker_with_root(tmp_root: Path):
    """Load the checker module with its REPO_ROOT pointed at tmp_root."""
    spec = importlib.util.spec_from_file_location("check_safe_defaults", CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO_ROOT = tmp_root
    module.ENV_EXAMPLE = tmp_root / ".env.example"
    module.RENDER_YAML = tmp_root / "render.yaml"
    module.SETTINGS_YAML = tmp_root / "config" / "settings.yaml"
    module.VALIDATION_GATE_PY = tmp_root / "src" / "validation_gate.py"
    module.VALIDATION_GATE_TEST = tmp_root / "tests" / "test_validation_gate.py"
    module.failures = []  # reset module-level list
    return module


def _stage_repo(tmp_path: Path) -> Path:
    """Copy only the files the checker inspects into a clean tmp dir."""
    (tmp_path / "config").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    shutil.copy(REPO_ROOT / ".env.example", tmp_path / ".env.example")
    shutil.copy(REPO_ROOT / "render.yaml", tmp_path / "render.yaml")
    shutil.copy(REPO_ROOT / "config" / "settings.yaml", tmp_path / "config" / "settings.yaml")
    # Touch sentinel files so Layer 3 check passes.
    (tmp_path / "src" / "validation_gate.py").write_text("# sentinel\n")
    (tmp_path / "tests" / "test_validation_gate.py").write_text("# sentinel\n")
    return tmp_path


def test_committed_repo_passes_check(tmp_path):
    staged = _stage_repo(tmp_path)
    checker = _load_checker_with_root(staged)
    rc = checker.main()
    assert rc == 0, f"committed repo should pass; failures={checker.failures}"


def test_live_trading_true_in_env_fails(tmp_path):
    staged = _stage_repo(tmp_path)
    env = (staged / ".env.example").read_text()
    (staged / ".env.example").write_text(env.replace("LIVE_TRADING=false", "LIVE_TRADING=true"))
    checker = _load_checker_with_root(staged)
    assert checker.main() == 1
    assert any("LIVE_TRADING" in f for f in checker.failures)


def test_risk_mode_changed_in_yaml_fails(tmp_path):
    staged = _stage_repo(tmp_path)
    settings = staged / "config" / "settings.yaml"
    text = settings.read_text().replace("mode: BACKTEST_ONLY", "mode: MICRO_LIVE")
    settings.write_text(text)
    checker = _load_checker_with_root(staged)
    assert checker.main() == 1
    assert any("risk.mode" in f for f in checker.failures)


def test_full_live_approval_fails(tmp_path):
    staged = _stage_repo(tmp_path)
    settings = staged / "config" / "settings.yaml"
    text = settings.read_text().replace(
        "allow_full_live_after_pass: false", "allow_full_live_after_pass: true"
    )
    settings.write_text(text)
    checker = _load_checker_with_root(staged)
    assert checker.main() == 1
    assert any("allow_full_live_after_pass" in f for f in checker.failures)


def test_committed_secret_in_env_example_fails(tmp_path):
    staged = _stage_repo(tmp_path)
    env_file = staged / ".env.example"
    text = env_file.read_text().replace("BINGX_API_KEY=", "BINGX_API_KEY=AKIA1234567890ABCD")
    env_file.write_text(text)
    checker = _load_checker_with_root(staged)
    assert checker.main() == 1
    assert any("BINGX_API_KEY" in f for f in checker.failures)


def test_render_yaml_live_trading_true_fails(tmp_path):
    staged = _stage_repo(tmp_path)
    render = staged / "render.yaml"
    text = render.read_text().replace(
        '- key: LIVE_TRADING\n        value: "false"',
        '- key: LIVE_TRADING\n        value: "true"',
    )
    render.write_text(text)
    checker = _load_checker_with_root(staged)
    assert checker.main() == 1
    assert any("LIVE_TRADING" in f for f in checker.failures)


def test_cli_invocation_returns_zero_on_clean_repo():
    """Smoke-test the script as a real CLI against the actual repo."""
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "passed" in result.stdout.lower()

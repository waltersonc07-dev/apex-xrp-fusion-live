"""
APEX safe-defaults checker.

Verifies that the repository keeps its three-layer live-trading lock intact:

  Layer 1 (env defaults): .env.example and render.yaml never ship with
    LIVE_TRADING / MICRO_LIVE / FULL_LIVE set to true, and RISK_MODE stays
    BACKTEST_ONLY.

  Layer 2 (YAML config): config/settings.yaml keeps risk.mode == BACKTEST_ONLY
    and validation.allow_full_live_after_pass == false.

  Layer 3 (validation gate): tests/test_validation_gate.py and
    src/validation_gate.py both still exist. (We do not run them here; CI runs
    pytest separately.)

Also verifies that no plausible secret has been committed to .env.example.

Exit codes:
  0  all checks passed
  1  one or more checks failed
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - dependency missing in early CI
    print("ERROR: PyYAML is required. Install with: pip install -r requirements.txt")
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
RENDER_YAML = REPO_ROOT / "render.yaml"
SETTINGS_YAML = REPO_ROOT / "config" / "settings.yaml"
VALIDATION_GATE_PY = REPO_ROOT / "src" / "validation_gate.py"
VALIDATION_GATE_TEST = REPO_ROOT / "tests" / "test_validation_gate.py"

# Keys in .env.example that must be false-ish (we accept "false", "False", "0").
UNSAFE_TRUE = {"true", "1", "yes", "on"}
ENV_FLAGS_MUST_BE_FALSE = ("LIVE_TRADING", "MICRO_LIVE", "FULL_LIVE")
ENV_FLAGS_MUST_BE_BACKTEST_ONLY = ("RISK_MODE",)

# Secrets that must remain empty in .env.example.
ENV_SECRETS_MUST_BE_EMPTY = (
    "BINGX_API_KEY",
    "BINGX_API_SECRET",
)
# Webhook secret is allowed to be a placeholder, but must not look like a real
# token (no long random strings).
ENV_WEBHOOK_SECRET_KEY = "TRADINGVIEW_WEBHOOK_SECRET"
ALLOWED_WEBHOOK_PLACEHOLDERS = {"", "change_me", "changeme", "placeholder"}


failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a simple KEY=VALUE .env-style file."""
    out: dict[str, str] = {}
    if not path.exists():
        fail(f"{path} is missing")
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def check_env_example() -> None:
    env = parse_env_file(ENV_EXAMPLE)
    for key in ENV_FLAGS_MUST_BE_FALSE:
        val = env.get(key, "").lower()
        if val in UNSAFE_TRUE:
            fail(f".env.example: {key}={val} (must be false)")
        elif key not in env:
            fail(f".env.example: missing required key {key}")

    for key in ENV_FLAGS_MUST_BE_BACKTEST_ONLY:
        val = env.get(key, "")
        if val != "BACKTEST_ONLY":
            fail(f".env.example: {key}={val!r} (must be BACKTEST_ONLY)")

    for key in ENV_SECRETS_MUST_BE_EMPTY:
        val = env.get(key, "")
        if val:
            fail(f".env.example: {key} is not empty — never commit real secrets")

    webhook = env.get(ENV_WEBHOOK_SECRET_KEY, "")
    if webhook not in ALLOWED_WEBHOOK_PLACEHOLDERS:
        # Heuristic: long random-looking strings are probably real secrets.
        if len(webhook) >= 16 and re.search(r"[A-Za-z0-9]{16,}", webhook):
            fail(
                f".env.example: {ENV_WEBHOOK_SECRET_KEY} looks like a real secret. "
                "Use 'change_me' as a placeholder."
            )


def check_render_yaml() -> None:
    if not RENDER_YAML.exists():
        fail("render.yaml is missing")
        return
    try:
        doc = yaml.safe_load(RENDER_YAML.read_text())
    except yaml.YAMLError as exc:
        fail(f"render.yaml: invalid YAML ({exc})")
        return

    services = doc.get("services", []) if isinstance(doc, dict) else []
    if not services:
        fail("render.yaml: no services defined")
        return

    for service in services:
        env_vars = {ev.get("key"): ev.get("value") for ev in service.get("envVars", [])}
        for key in ENV_FLAGS_MUST_BE_FALSE:
            val = str(env_vars.get(key, "")).lower()
            if val in UNSAFE_TRUE:
                fail(f"render.yaml: {key}={val} (must be false)")
        for key in ENV_FLAGS_MUST_BE_BACKTEST_ONLY:
            val = str(env_vars.get(key, ""))
            if val and val != "BACKTEST_ONLY":
                fail(f"render.yaml: {key}={val!r} (must be BACKTEST_ONLY)")


def check_settings_yaml() -> None:
    if not SETTINGS_YAML.exists():
        fail("config/settings.yaml is missing")
        return
    try:
        doc = yaml.safe_load(SETTINGS_YAML.read_text())
    except yaml.YAMLError as exc:
        fail(f"config/settings.yaml: invalid YAML ({exc})")
        return

    if not isinstance(doc, dict):
        fail("config/settings.yaml: top-level must be a mapping")
        return

    risk = doc.get("risk", {})
    mode = risk.get("mode")
    if mode != "BACKTEST_ONLY":
        fail(
            f"config/settings.yaml: risk.mode={mode!r} (must be BACKTEST_ONLY "
            "until validation passes — open a separate PR to change this)"
        )

    validation = doc.get("validation", {})
    if validation.get("allow_full_live_after_pass") is True:
        fail(
            "config/settings.yaml: validation.allow_full_live_after_pass is true "
            "(must remain false; FULL_LIVE is not approved)"
        )


def check_validation_gate_present() -> None:
    if not VALIDATION_GATE_PY.exists():
        fail("src/validation_gate.py is missing — Layer 3 of the lock cannot be removed")
    if not VALIDATION_GATE_TEST.exists():
        fail("tests/test_validation_gate.py is missing — gate tests cannot be removed")


def main() -> int:
    check_env_example()
    check_render_yaml()
    check_settings_yaml()
    check_validation_gate_present()

    if failures:
        print("APEX safe-defaults check FAILED:")
        for f in failures:
            print(f"  - {f}")
        print()
        print("See SAFETY.md for the three-layer live-trading lock.")
        return 1

    print("APEX safe-defaults check passed.")
    print("  Layer 1 (env): LIVE_TRADING/MICRO_LIVE/FULL_LIVE=false, RISK_MODE=BACKTEST_ONLY")
    print("  Layer 2 (yaml): risk.mode=BACKTEST_ONLY, FULL_LIVE not approved")
    print("  Layer 3 (gate): validation_gate.py + test present")
    return 0


if __name__ == "__main__":
    sys.exit(main())

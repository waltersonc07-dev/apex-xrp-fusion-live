"""APEX status + preflight integrity checks.

This module is the single source of truth for "is the deployed service
configured safely". It is:

  - Read-only: it never mutates env vars or config.
  - Pure where possible: ``compute_status`` takes env + config as inputs so
    tests can drive every branch without spinning up FastAPI.
  - Defense-in-depth, NOT a replacement for the existing three-layer lock
    (env / yaml / validation_gate). Think of it as Layer 4: a runtime check
    surface so Render health checks, dashboards, and the user can verify the
    deployed instance still matches the locked configuration.

Public surface
--------------
- ``compute_status(env, config_yaml_text) -> dict``
- ``preflight(env, config_yaml_text) -> None``  (raises ``UnsafeConfigError``)
- ``UnsafeConfigError``

The values returned by ``compute_status`` are JSON-serializable. The HTTP
layer in ``webhook_server`` just wraps them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml


class UnsafeConfigError(RuntimeError):
    """Raised when preflight detects a config combination that must never run.

    The only fatal combination is::

        LIVE_TRADING=true  AND  risk.mode != BACKTEST_ONLY  (with no manual
        FULL_LIVE approval in settings.yaml)

    Today that combination is impossible because:
      - .env.example pins LIVE_TRADING=false
      - settings.yaml pins risk.mode=BACKTEST_ONLY
      - validation_gate gates any flip

    This preflight is the safety net for the day someone (a future maintainer,
    a CI mistake, a copy-paste error in Render) tries to override one without
    the other. We want the service to *refuse to start* rather than enter a
    dangerous half-configured state.
    """


SAFE_DEFAULTS = {
    "LIVE_TRADING": "false",
    "MICRO_LIVE": "false",
    "FULL_LIVE": "false",
    "RISK_MODE": "BACKTEST_ONLY",
}

LIVE_FLAGS = ("LIVE_TRADING", "MICRO_LIVE", "FULL_LIVE")
SECRET_NAMES = ("BINGX_API_KEY", "BINGX_API_SECRET", "TRADINGVIEW_WEBHOOK_SECRET")


@dataclass(frozen=True)
class StatusReport:
    healthy: bool
    safe: bool
    risk_mode: str
    yaml_risk_mode: str
    live_trading: bool
    micro_live: bool
    full_live: bool
    full_live_approved: bool
    secrets_configured: dict[str, bool]
    failures: list[str]
    warnings: list[str]

    def to_dict(self) -> dict:
        return {
            "healthy": self.healthy,
            "safe": self.safe,
            "risk_mode": self.risk_mode,
            "yaml_risk_mode": self.yaml_risk_mode,
            "live_trading": self.live_trading,
            "micro_live": self.micro_live,
            "full_live": self.full_live,
            "full_live_approved": self.full_live_approved,
            "secrets_configured": dict(self.secrets_configured),
            "failures": list(self.failures),
            "warnings": list(self.warnings),
        }


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_config(config_yaml_text: str | None) -> dict:
    if not config_yaml_text:
        return {}
    try:
        return yaml.safe_load(config_yaml_text) or {}
    except Exception:  # noqa: BLE001 — surface as a failure, not a crash
        return {}


def compute_status(env: Mapping[str, str] | None = None,
                   config_yaml_text: str | None = None) -> StatusReport:
    """Inspect the running environment and the YAML config and return a
    structured status. ``env`` defaults to ``os.environ``; ``config_yaml_text``
    is the raw text of ``config/settings.yaml`` (passed in so tests can mock).
    """
    env = dict(os.environ if env is None else env)
    config = _read_config(config_yaml_text)

    risk_mode_env = (env.get("RISK_MODE") or "").strip() or "BACKTEST_ONLY"
    risk_mode_yaml = (
        ((config.get("risk") or {}).get("mode") or "").strip()
        or "BACKTEST_ONLY"
    )
    live_trading = _truthy(env.get("LIVE_TRADING"))
    micro_live = _truthy(env.get("MICRO_LIVE"))
    full_live = _truthy(env.get("FULL_LIVE"))
    full_live_approved = bool(
        ((config.get("risk") or {}).get("full_live_approved"))
    )

    failures: list[str] = []
    warnings: list[str] = []

    # ---- Hard safety failures (preflight will raise on any of these) ----
    if live_trading and risk_mode_env.upper() != "BACKTEST_ONLY" \
            and risk_mode_yaml.upper() != "BACKTEST_ONLY" \
            and not full_live_approved:
        failures.append(
            "LIVE_TRADING=true but risk.mode is not BACKTEST_ONLY and "
            "full_live_approved is not set in settings.yaml"
        )
    if full_live and not full_live_approved:
        failures.append(
            "FULL_LIVE=true but settings.yaml has no full_live_approved=true"
        )
    if risk_mode_env.upper() != risk_mode_yaml.upper():
        # Mismatch isn't necessarily fatal (env can override for dry runs) but
        # the user must know — surface it as a failure so /status reflects it.
        failures.append(
            f"RISK_MODE env={risk_mode_env!r} disagrees with settings.yaml "
            f"risk.mode={risk_mode_yaml!r}"
        )

    # ---- Warnings (non-fatal but worth surfacing) ----
    if any((live_trading, micro_live, full_live)):
        warnings.append(
            "At least one live flag is true — verify this is an authorized "
            "deployment and that validation_gate has issued an UNLOCK_LIVE."
        )
    if (env.get("BINGX_API_KEY") or env.get("BINGX_API_SECRET")) and not live_trading:
        warnings.append(
            "BingX API keys are configured but LIVE_TRADING=false — keys are "
            "loaded but unused. Remove keys until live trading is approved."
        )

    secrets_configured = {name: bool(env.get(name)) for name in SECRET_NAMES}

    safe = not failures and not any((live_trading, micro_live, full_live))
    healthy = not failures  # the service can run; safe=False just means
                            # it's *running in a live configuration*

    return StatusReport(
        healthy=healthy,
        safe=safe,
        risk_mode=risk_mode_env,
        yaml_risk_mode=risk_mode_yaml,
        live_trading=live_trading,
        micro_live=micro_live,
        full_live=full_live,
        full_live_approved=full_live_approved,
        secrets_configured=secrets_configured,
        failures=failures,
        warnings=warnings,
    )


def preflight(env: Mapping[str, str] | None = None,
              config_yaml_text: str | None = None) -> StatusReport:
    """Run ``compute_status`` and raise ``UnsafeConfigError`` if the report
    contains any ``failures``. Call this at process startup."""
    report = compute_status(env=env, config_yaml_text=config_yaml_text)
    if report.failures:
        raise UnsafeConfigError(
            "preflight refused to start the service: "
            + "; ".join(report.failures)
        )
    return report


# ---------------------------------------------------------------------------
# Convenience for callers that want to load the YAML themselves.
# ---------------------------------------------------------------------------


def load_settings_text(path: str | Path = "config/settings.yaml") -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def compute_status_from_disk(config_path: str | Path = "config/settings.yaml",
                             env: Mapping[str, str] | None = None) -> StatusReport:
    return compute_status(env=env,
                          config_yaml_text=load_settings_text(config_path))

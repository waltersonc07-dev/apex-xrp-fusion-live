"""Tests for ``src.status_endpoint`` and the new FastAPI routes.

These tests exercise compute_status / preflight purely as functions so they
run instantly with no FastAPI startup overhead. The HTTP routes are then
exercised through FastAPI's TestClient.
"""

from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest

from src.status_endpoint import (
    UnsafeConfigError,
    compute_status,
    compute_status_from_disk,
    load_settings_text,
    preflight,
)


SAFE_YAML = dedent(
    """\
    risk:
      mode: BACKTEST_ONLY
      full_live_approved: false
    """
)

LIVE_APPROVED_YAML = dedent(
    """\
    risk:
      mode: LIVE
      full_live_approved: true
    """
)

SAFE_ENV = {
    "LIVE_TRADING": "false",
    "MICRO_LIVE": "false",
    "FULL_LIVE": "false",
    "RISK_MODE": "BACKTEST_ONLY",
}


# ---------------------------------------------------------------------------
# compute_status — happy path
# ---------------------------------------------------------------------------


class TestCompute:
    def test_safe_defaults_report_healthy_and_safe(self):
        r = compute_status(env=SAFE_ENV, config_yaml_text=SAFE_YAML)
        assert r.healthy is True
        assert r.safe is True
        assert r.failures == []
        assert r.live_trading is False
        assert r.micro_live is False
        assert r.full_live is False
        assert r.risk_mode == "BACKTEST_ONLY"
        assert r.yaml_risk_mode == "BACKTEST_ONLY"

    def test_to_dict_is_json_serializable(self):
        import json

        r = compute_status(env=SAFE_ENV, config_yaml_text=SAFE_YAML)
        json.dumps(r.to_dict())  # must not raise


# ---------------------------------------------------------------------------
# compute_status — failure modes
# ---------------------------------------------------------------------------


class TestUnsafeCombinations:
    def test_live_trading_with_backtest_only_env_is_safe(self):
        # If risk.mode stays BACKTEST_ONLY everywhere, LIVE_TRADING=true alone
        # is a warning (deployment misconfig) but not a hard failure.
        env = {**SAFE_ENV, "LIVE_TRADING": "true"}
        r = compute_status(env=env, config_yaml_text=SAFE_YAML)
        # Not a failure because env risk_mode is still BACKTEST_ONLY.
        # But "safe" must be False — a live flag is set.
        assert r.safe is False
        assert any("live flag is true" in w for w in r.warnings)

    def test_live_trading_with_live_yaml_no_approval_fails(self):
        env = {**SAFE_ENV, "LIVE_TRADING": "true", "RISK_MODE": "LIVE"}
        yaml = dedent(
            """\
            risk:
              mode: LIVE
              full_live_approved: false
            """
        )
        r = compute_status(env=env, config_yaml_text=yaml)
        assert r.healthy is False
        assert any("LIVE_TRADING=true" in f for f in r.failures)

    def test_full_live_without_yaml_approval_fails(self):
        env = {**SAFE_ENV, "FULL_LIVE": "true"}
        r = compute_status(env=env, config_yaml_text=SAFE_YAML)
        assert r.healthy is False
        assert any("FULL_LIVE=true" in f for f in r.failures)

    def test_env_yaml_risk_mode_mismatch_fails(self):
        env = {**SAFE_ENV, "RISK_MODE": "MICRO_LIVE"}
        r = compute_status(env=env, config_yaml_text=SAFE_YAML)
        assert r.healthy is False
        assert any("disagrees" in f for f in r.failures)

    def test_micro_live_flag_makes_unsafe_but_not_fatal(self):
        env = {**SAFE_ENV, "MICRO_LIVE": "true"}
        r = compute_status(env=env, config_yaml_text=SAFE_YAML)
        # No fatal failures, but safe=False because a live flag is set.
        assert r.healthy is True
        assert r.safe is False


# ---------------------------------------------------------------------------
# Secrets visibility
# ---------------------------------------------------------------------------


class TestSecrets:
    def test_secret_booleans_only(self):
        env = {**SAFE_ENV, "BINGX_API_KEY": "abc",
               "BINGX_API_SECRET": "", "TRADINGVIEW_WEBHOOK_SECRET": "xyz"}
        r = compute_status(env=env, config_yaml_text=SAFE_YAML)
        assert r.secrets_configured == {
            "BINGX_API_KEY": True,
            "BINGX_API_SECRET": False,
            "TRADINGVIEW_WEBHOOK_SECRET": True,
        }

    def test_key_set_without_live_warns(self):
        env = {**SAFE_ENV, "BINGX_API_KEY": "abc"}
        r = compute_status(env=env, config_yaml_text=SAFE_YAML)
        assert any("API keys are configured but LIVE_TRADING=false" in w
                   for w in r.warnings)

    def test_to_dict_does_not_leak_secret_values(self):
        env = {**SAFE_ENV, "BINGX_API_KEY": "super-secret-key",
               "TRADINGVIEW_WEBHOOK_SECRET": "tv-secret-value"}
        r = compute_status(env=env, config_yaml_text=SAFE_YAML)
        as_str = repr(r.to_dict())
        assert "super-secret-key" not in as_str
        assert "tv-secret-value" not in as_str


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------


class TestPreflight:
    def test_safe_config_does_not_raise(self):
        report = preflight(env=SAFE_ENV, config_yaml_text=SAFE_YAML)
        assert report.healthy is True

    def test_unsafe_config_raises(self):
        env = {**SAFE_ENV, "FULL_LIVE": "true"}
        with pytest.raises(UnsafeConfigError, match="FULL_LIVE"):
            preflight(env=env, config_yaml_text=SAFE_YAML)

    def test_unsafe_config_raises_with_message(self):
        env = {**SAFE_ENV, "RISK_MODE": "MICRO_LIVE"}
        with pytest.raises(UnsafeConfigError) as excinfo:
            preflight(env=env, config_yaml_text=SAFE_YAML)
        assert "preflight refused" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# Disk loader
# ---------------------------------------------------------------------------


class TestDiskLoader:
    def test_load_settings_text_returns_empty_on_missing_file(self, tmp_path):
        assert load_settings_text(tmp_path / "nope.yaml") == ""

    def test_load_settings_text_reads_file(self, tmp_path):
        p = tmp_path / "s.yaml"
        p.write_text("hello: world\n")
        assert "hello: world" in load_settings_text(p)

    def test_compute_status_from_disk_uses_real_settings(self):
        repo_root = Path(__file__).resolve().parent.parent
        with patch.dict(os.environ, SAFE_ENV, clear=False):
            r = compute_status_from_disk(repo_root / "config" / "settings.yaml")
        # The committed settings.yaml must keep us in BACKTEST_ONLY.
        assert r.yaml_risk_mode.upper() == "BACKTEST_ONLY"
        assert r.healthy is True


# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


class TestRoutes:
    def _make_client(self, env: dict):
        # Import inside the test so preflight uses the patched env.
        from fastapi.testclient import TestClient

        with patch.dict(os.environ, env, clear=False):
            import importlib
            import src.webhook_server as ws
            importlib.reload(ws)
            client = TestClient(ws.app)
            # Enter context manager to trigger startup events.
            with client as c:
                yield c

    def test_health_returns_ok(self):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, SAFE_ENV, clear=False):
            import importlib
            import src.webhook_server as ws
            importlib.reload(ws)
            with TestClient(ws.app) as client:
                r = client.get("/health")
                assert r.status_code == 200
                assert r.json() == {"status": "ok"}

    def test_status_returns_safe_payload(self):
        from fastapi.testclient import TestClient
        with patch.dict(os.environ, SAFE_ENV, clear=False):
            import importlib
            import src.webhook_server as ws
            importlib.reload(ws)
            with TestClient(ws.app) as client:
                r = client.get("/status")
                assert r.status_code == 200
                payload = r.json()
                assert payload["healthy"] is True
                assert payload["safe"] is True
                assert payload["live_trading"] is False
                assert payload["full_live"] is False
                assert payload["risk_mode"].upper() == "BACKTEST_ONLY"
                # Failures must be empty for the committed config.
                assert payload["failures"] == []

    def test_startup_refuses_unsafe_env(self):
        from fastapi.testclient import TestClient
        bad_env = {**SAFE_ENV, "FULL_LIVE": "true"}
        with patch.dict(os.environ, bad_env, clear=False):
            import importlib
            import src.webhook_server as ws
            importlib.reload(ws)
            with pytest.raises(UnsafeConfigError):
                with TestClient(ws.app):
                    pass


# ---------------------------------------------------------------------------
# Journal honors APEX_JOURNAL_DIR
# ---------------------------------------------------------------------------


class TestJournalDirOverride:
    def test_journal_path_honors_env(self, tmp_path):
        from src import journal as journal_mod
        with patch.dict(os.environ, {"APEX_JOURNAL_DIR": str(tmp_path)},
                        clear=False):
            p = journal_mod.journal_path("trades.csv")
            assert p == tmp_path / "trades.csv"

    def test_write_journal_writes_under_override_dir(self, tmp_path):
        from src.journal import write_journal
        with patch.dict(os.environ, {"APEX_JOURNAL_DIR": str(tmp_path)},
                        clear=False):
            write_journal({
                "timestamp": "2026-01-01T00:00:00Z",
                "symbol": "XRPUSDT",
                "action": "BUY",
                "price": "1.0",
                "stop_loss": "0.9",
                "take_profit": "1.2",
                "risk_pct": "1",
                "qty": "100",
                "fundamental_score": "0",
                "technical_reason": "test",
                "risk_engine_decision": "rejected",
                "result": "rejected",
                "notes": "unit test",
            })
            files = list(tmp_path.glob("*.csv"))
            assert files, "journal CSV not written"
            assert "BUY" in files[0].read_text()

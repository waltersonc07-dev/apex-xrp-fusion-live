from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from .exchange_client import ExchangeClient
from .fundamental_gate import load_daily_score
from .journal import write_journal
from .risk_engine import approve_trade
from .status_endpoint import (
    UnsafeConfigError,
    compute_status_from_disk,
    preflight,
    load_settings_text,
)

load_dotenv()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Refuse to come up if the env+yaml combination is unsafe.

    On a normal deployment this is a no-op: LIVE_TRADING/MICRO_LIVE/FULL_LIVE
    are all false and risk.mode is BACKTEST_ONLY. The check exists so a
    misconfigured Render redeploy (e.g. someone flips LIVE_TRADING=true
    without updating settings.yaml and approving FULL_LIVE) fails fast at
    startup instead of silently accepting webhooks.
    """
    try:
        preflight(env=os.environ, config_yaml_text=load_settings_text())
    except UnsafeConfigError as exc:
        print(f"[preflight] REFUSING TO START: {exc}", flush=True)
        raise
    yield


app = FastAPI(title="APEX XRP Fusion Live", lifespan=_lifespan)


@app.get("/health")
def health() -> dict:
    """Lightweight liveness probe. Always returns 200 once the app booted."""
    return {"status": "ok"}


@app.get("/status")
def status() -> dict:
    """Full config integrity report. Read-only; safe to expose publicly
    because it never returns secret values, only booleans for whether each
    expected secret env var is set."""
    return compute_status_from_disk().to_dict()


def load_config(path: str | Path = "config/settings.yaml") -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def validate_secret(provided: str | None, config: dict) -> bool:
    env_name = config["execution"]["webhook_secret_env"]
    expected = os.getenv(env_name)
    return bool(expected) and provided == expected


@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request, x_webhook_secret: str | None = Header(default=None)):
    config = load_config()
    payload = await request.json()
    if payload.get("symbol") != config["strategy"]["symbol"]:
        raise HTTPException(status_code=400, detail="unsupported symbol")

    secret_valid = validate_secret(payload.get("secret") or x_webhook_secret, config)
    score = load_daily_score().get("total_score", 0)
    signal = {
        "signal_id": payload.get("signal_id"),
        "webhook_secret_valid": secret_valid,
        "price": float(payload["price"]),
        "stop_loss": float(payload["stop_loss"]),
        "take_profit": float(payload["take_profit"]),
        "rr": abs(float(payload["take_profit"]) - float(payload["price"])) / max(abs(float(payload["price"]) - float(payload["stop_loss"])), 1e-12),
    }
    account_state = {"equity": 1000.0, "daily_loss_pct": 0, "weekly_loss_pct": 0, "open_positions": 0, "trades_today": 0, "seen_signal_ids": set()}
    market_state = {"spread_pct": float(payload.get("spread_pct", 0.05)), "max_spread_pct": 0.25}
    decision = approve_trade(signal, account_state, market_state, score, config)
    print(
        "webhook decision "
        f"signal_id={payload.get('signal_id')} "
        f"symbol={payload.get('symbol')} "
        f"action={payload.get('action')} "
        f"approved={decision['approved']} "
        f"reason={decision['reason']} "
        f"mode={decision['mode']}",
        flush=True,
    )

    result = {"risk_engine": decision, "exchange": None}
    if decision["approved"]:
        result["exchange"] = ExchangeClient(config["execution"]["exchange"]).place_order(payload, decision["mode"], risk_approved=decision["approved"])

    write_journal({
        "timestamp": payload.get("timestamp"),
        "symbol": payload.get("symbol"),
        "action": payload.get("action"),
        "price": payload.get("price"),
        "stop_loss": payload.get("stop_loss"),
        "take_profit": payload.get("take_profit"),
        "risk_pct": payload.get("risk_pct"),
        "qty": decision.get("qty"),
        "fundamental_score": score,
        "technical_reason": payload.get("technical_reason", ""),
        "risk_engine_decision": decision["reason"],
        "result": "approved" if decision["approved"] else "rejected",
        "notes": payload.get("notes", ""),
    })
    return result

from __future__ import annotations

import os
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request

from .exchange_client import ExchangeClient
from .fundamental_gate import load_daily_score
from .journal import write_journal
from .risk_engine import approve_trade

load_dotenv()
app = FastAPI(title="APEX XRP Fusion Live")
logger = logging.getLogger("apex.webhook")


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
    logger.info(
        "webhook decision signal_id=%s symbol=%s action=%s approved=%s reason=%s mode=%s",
        payload.get("signal_id"),
        payload.get("symbol"),
        payload.get("action"),
        decision["approved"],
        decision["reason"],
        decision["mode"],
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

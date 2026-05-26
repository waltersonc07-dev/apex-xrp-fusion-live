from __future__ import annotations

from .fundamental_gate import live_allowed, trade_mode


def position_size(account_equity: float, risk_pct: float, entry_price: float, stop_price: float) -> tuple[float, float]:
    risk_amount = account_equity * risk_pct / 100
    stop_distance = abs(entry_price - stop_price)
    if stop_distance <= 0:
        return 0.0, risk_amount
    return risk_amount / stop_distance, risk_amount


def approve_trade(signal: dict, account_state: dict, market_state: dict, fundamental_score: int, config: dict) -> dict:
    mode = config["risk"].get("mode", "BACKTEST_ONLY")
    risk = config["risk"]
    min_rr = config["strategy"]["min_rr"]

    if mode == "BACKTEST_ONLY":
        return {"approved": False, "reason": "BACKTEST_ONLY mode blocks live orders", "qty": 0, "risk_amount": 0, "mode": mode}
    if not signal.get("webhook_secret_valid", False):
        return {"approved": False, "reason": "invalid webhook secret", "qty": 0, "risk_amount": 0, "mode": mode}
    if signal.get("signal_id") in account_state.get("seen_signal_ids", set()):
        return {"approved": False, "reason": "duplicate signal_id", "qty": 0, "risk_amount": 0, "mode": mode}
    if account_state.get("daily_loss_pct", 0) >= risk["max_daily_loss_pct"]:
        return {"approved": False, "reason": "daily loss limit hit", "qty": 0, "risk_amount": 0, "mode": mode}
    if account_state.get("weekly_loss_pct", 0) >= risk["max_weekly_loss_pct"]:
        return {"approved": False, "reason": "weekly loss limit hit", "qty": 0, "risk_amount": 0, "mode": mode}
    if account_state.get("open_positions", 0) >= risk["max_open_positions"]:
        return {"approved": False, "reason": "max open positions reached", "qty": 0, "risk_amount": 0, "mode": mode}
    if account_state.get("trades_today", 0) >= risk["max_trades_per_day"]:
        return {"approved": False, "reason": "max trades per day reached", "qty": 0, "risk_amount": 0, "mode": mode}
    if signal.get("rr", 0) < min_rr:
        return {"approved": False, "reason": "risk/reward below minimum", "qty": 0, "risk_amount": 0, "mode": mode}
    if not live_allowed(fundamental_score, mode, config):
        return {"approved": False, "reason": f"fundamental gate {trade_mode(fundamental_score, config)}", "qty": 0, "risk_amount": 0, "mode": mode}
    if market_state.get("spread_pct", 0) > market_state.get("max_spread_pct", 0.25):
        return {"approved": False, "reason": "spread too wide", "qty": 0, "risk_amount": 0, "mode": mode}

    risk_pct = risk["micro_live_risk_pct"] if mode == "MICRO_LIVE" else risk["normal_live_risk_pct"]
    qty, risk_amount = position_size(account_state["equity"], risk_pct, signal["price"], signal["stop_loss"])
    if qty <= 0:
        return {"approved": False, "reason": "invalid position size", "qty": 0, "risk_amount": risk_amount, "mode": mode}
    return {"approved": True, "reason": "approved", "qty": qty, "risk_amount": risk_amount, "mode": mode}


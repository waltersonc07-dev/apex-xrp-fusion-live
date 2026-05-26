from src.risk_engine import approve_trade, position_size


def config(mode="MICRO_LIVE"):
    return {
        "strategy": {"min_rr": 2.0},
        "risk": {
            "mode": mode,
            "micro_live_risk_pct": 0.10,
            "normal_live_risk_pct": 0.25,
            "max_daily_loss_pct": 1.0,
            "max_weekly_loss_pct": 2.0,
            "max_trades_per_day": 2,
            "max_open_positions": 1,
        },
        "fundamental_gate": {
            "full_allowed_score": 26,
            "reduced_allowed_score": 22,
            "micro_only_score": 17,
            "block_below_score": 17,
        },
    }


def signal(**overrides):
    base = {"signal_id": "abc", "webhook_secret_valid": True, "price": 1.4, "stop_loss": 1.35, "take_profit": 1.5, "rr": 2.0}
    base.update(overrides)
    return base


def account(**overrides):
    base = {"equity": 1000, "daily_loss_pct": 0, "weekly_loss_pct": 0, "open_positions": 0, "trades_today": 0, "seen_signal_ids": set()}
    base.update(overrides)
    return base


def test_position_sizing():
    qty, risk_amount = position_size(1000, 0.1, 1.4, 1.35)
    assert round(risk_amount, 2) == 1.0
    assert round(qty, 2) == 20.0


def test_reject_daily_loss_exceeded():
    result = approve_trade(signal(), account(daily_loss_pct=1.0), {"spread_pct": 0.01}, 26, config())
    assert not result["approved"]
    assert "daily" in result["reason"]


def test_reject_fundamental_score_below_17():
    result = approve_trade(signal(), account(), {"spread_pct": 0.01}, 16, config())
    assert not result["approved"]
    assert "fundamental" in result["reason"]


def test_reject_rr_below_2():
    result = approve_trade(signal(rr=1.5), account(), {"spread_pct": 0.01}, 26, config())
    assert not result["approved"]
    assert "risk/reward" in result["reason"]


def test_duplicate_signal_prevention():
    result = approve_trade(signal(), account(seen_signal_ids={"abc"}), {"spread_pct": 0.01}, 26, config())
    assert not result["approved"]
    assert "duplicate" in result["reason"]


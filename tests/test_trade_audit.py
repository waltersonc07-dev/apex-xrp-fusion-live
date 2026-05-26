from src.trade_audit import audit_trades


def test_trade_audit_flags_rr_below_2():
    result = audit_trades([
        {
            "entry_time": "2026-01-01",
            "exit_time": "2026-01-01 01:00",
            "entry_price": 1.0,
            "exit_price": 1.05,
            "stop_loss": 0.95,
            "take_profit": 1.05,
            "risk_amount": 1,
            "planned_rr_at_entry": 1.0,
            "realized_r_multiple": 1.0,
            "fees": 0.01,
            "slippage_cost": 0.01,
            "qty": 1,
            "side": "long",
            "reason_for_entry": "test",
            "reason_for_exit": "test",
            "mode": "BACKTEST_ONLY",
        }
    ], {"strategy": {"min_rr": 2.0}, "risk": {"micro_live_risk_pct": 0.10, "normal_live_risk_pct": 0.25}})
    assert not result["passed"]
    assert any("planned RR below 2" in issue for issue in result["issues"])


def test_trade_audit_allows_realized_r_below_2_when_planned_rr_valid():
    result = audit_trades([
        {
            "entry_time": "2026-01-01",
            "exit_time": "2026-01-01 01:00",
            "entry_price": 1.0,
            "exit_price": 1.01,
            "stop_loss": 0.95,
            "take_profit": 1.10,
            "risk_amount": 1,
            "planned_rr_at_entry": 2.0,
            "realized_r_multiple": 0.2,
            "fees": 0.01,
            "slippage_cost": 0.01,
            "qty": 1,
            "side": "long",
            "reason_for_entry": "test",
            "reason_for_exit": "flip_exit",
            "mode": "BACKTEST_ONLY",
        }
    ], {"strategy": {"min_rr": 2.0}, "risk": {"micro_live_risk_pct": 0.10, "normal_live_risk_pct": 0.25}})
    assert result["passed"]

from src.validation_gate import evaluate_validation


def config():
    return {
        "validation": {
            "min_profit_factor": 1.50,
            "min_oos_profit_factor": 1.20,
            "max_drawdown_pct": 12.0,
            "min_total_trades": 150,
            "require_positive_expectancy": True,
            "require_positive_average_trade_after_fees": True,
            "require_doubled_fees_profitability": True,
            "require_increased_slippage_profitability": True,
            "require_parameter_robustness": True,
            "allow_micro_live_after_pass": True,
            "allow_full_live_after_pass": False,
        },
        "risk": {"micro_live_risk_pct": 0.10, "max_weekly_loss_pct": 2.0},
    }


def passing_metrics():
    return {
        "net_profit": 1000,
        "profit_factor": 1.6,
        "out_of_sample_profit_factor": 1.3,
        "max_drawdown_pct": 8,
        "expectancy": 5,
        "average_trade_after_fees": 5,
        "total_trades": 160,
        "max_consecutive_losses": 5,
        "stress_test_doubled_fees_profitable": True,
        "stress_test_increased_slippage_profitable": True,
        "parameter_perturbation_acceptable": True,
        "lookahead_bias": False,
        "repainting": False,
        "walk_forward_passed": True,
        "trade_audit_passed": True,
        "losing_trades": 50,
        "stop_loss_exits": 40,
    }


def test_validation_gate_blocks_low_profit_factor():
    metrics = passing_metrics()
    metrics["profit_factor"] = 1.49
    result = evaluate_validation(metrics, config())
    assert result["recommended_mode"] == "BACKTEST_ONLY"
    assert any("profit factor" in rule for rule in result["failed_rules"])


def test_validation_gate_blocks_high_drawdown():
    metrics = passing_metrics()
    metrics["max_drawdown_pct"] = 12.1
    result = evaluate_validation(metrics, config())
    assert result["status"] == "BLOCK_LIVE"
    assert any("drawdown" in rule for rule in result["failed_rules"])


def test_validation_gate_allows_micro_live_only_if_all_rules_pass():
    result = evaluate_validation(passing_metrics(), config())
    assert result["status"] == "PASS_MICRO_LIVE"
    assert result["recommended_mode"] == "MICRO_LIVE"
    assert result["risk_pct"] == 0.10

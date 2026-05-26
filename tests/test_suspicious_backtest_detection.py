from src.validation_gate import evaluate_validation


def cfg():
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
        },
        "risk": {"micro_live_risk_pct": 0.10, "max_weekly_loss_pct": 2.0},
    }


def suspicious_metrics():
    return {
        "net_profit": 1000,
        "profit_factor": float("inf"),
        "out_of_sample_profit_factor": 2.0,
        "max_drawdown_pct": 0,
        "expectancy": 10,
        "average_trade_after_fees": 10,
        "total_trades": 200,
        "max_consecutive_losses": 0,
        "stress_test_doubled_fees_profitable": True,
        "stress_test_increased_slippage_profitable": True,
        "parameter_perturbation_acceptable": True,
        "lookahead_bias": False,
        "repainting": False,
        "walk_forward_passed": True,
        "trade_audit_passed": True,
        "win_rate": 100,
        "losing_trades": 0,
        "stop_loss_exits": 0,
    }


def test_suspicious_metrics_block_live():
    result = evaluate_validation(suspicious_metrics(), cfg())
    assert result["status"] == "BLOCK_LIVE"
    assert "suspicious win rate" in result["failed_rules"]
    assert "infinite profit factor" in result["failed_rules"]


def test_no_losing_trades_blocks_live():
    metrics = suspicious_metrics()
    metrics["profit_factor"] = 2.0
    metrics["win_rate"] = 80
    metrics["max_drawdown_pct"] = 5
    result = evaluate_validation(metrics, cfg())
    assert "no losing trades detected" in result["failed_rules"]

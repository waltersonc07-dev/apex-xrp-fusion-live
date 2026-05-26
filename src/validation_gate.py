from __future__ import annotations

import math


def evaluate_validation(metrics: dict, config: dict) -> dict:
    validation = config["validation"]
    risk = config.get("risk", {})
    failed: list[str] = []
    warnings: list[str] = []

    def fail(rule: str) -> None:
        failed.append(rule)

    if metrics.get("net_profit", 0) <= 0:
        fail("net profit must be positive")
    if metrics.get("profit_factor", 0) < validation["min_profit_factor"]:
        fail(f"profit factor below {validation['min_profit_factor']:.2f}")
    if metrics.get("out_of_sample_profit_factor", 0) < validation["min_oos_profit_factor"]:
        fail(f"out-of-sample profit factor below {validation['min_oos_profit_factor']:.2f}")
    if metrics.get("max_drawdown_pct", 100) > validation["max_drawdown_pct"]:
        fail(f"max drawdown above {validation['max_drawdown_pct']:.1f}%")
    if validation["require_positive_expectancy"] and metrics.get("expectancy", 0) <= 0:
        fail("expectancy must be positive")
    if validation["require_positive_average_trade_after_fees"] and metrics.get("average_trade_after_fees", 0) <= 0:
        fail("average trade after fees must be positive")
    if metrics.get("total_trades", metrics.get("trade_count", 0)) < validation["min_total_trades"]:
        fail(f"total trades below {validation['min_total_trades']}")

    micro_risk = risk.get("micro_live_risk_pct", 0.10)
    max_losses = metrics.get("max_consecutive_losses", 0)
    weekly_limit = risk.get("max_weekly_loss_pct", 2.0)
    if max_losses * micro_risk > weekly_limit:
        fail("max consecutive losses not survivable under micro risk")

    if validation["require_doubled_fees_profitability"] and not metrics.get("stress_test_doubled_fees_profitable", False):
        fail("doubled-fees stress test not profitable")
    if validation["require_increased_slippage_profitability"] and not metrics.get("stress_test_increased_slippage_profitable", False):
        fail("increased-slippage stress test not profitable")
    if validation["require_parameter_robustness"] and not metrics.get("parameter_perturbation_acceptable", False):
        fail("parameter perturbation not acceptable")
    if metrics.get("lookahead_bias", False):
        fail("lookahead bias flag set")
    if metrics.get("repainting", False):
        fail("repainting flag set")
    if metrics.get("walk_forward_passed") is False:
        fail("walk-forward validation failed")
    if metrics.get("trade_audit_passed") is False:
        fail("trade audit failed")
    total_trades = metrics.get("total_trades", metrics.get("trade_count", 0))
    win_rate = metrics.get("win_rate", 0)
    profit_factor = metrics.get("profit_factor", 0)
    max_drawdown = metrics.get("max_drawdown_pct", 0)
    losing_trades = metrics.get("losing_trades", 0)
    stop_exits = metrics.get("stop_loss_exits", 0)
    if total_trades >= 100 and win_rate >= 95:
        fail("suspicious win rate")
    if isinstance(profit_factor, (int, float)) and math.isinf(profit_factor):
        fail("infinite profit factor")
    if total_trades >= 100 and max_drawdown == 0:
        fail("zero drawdown with many trades")
    if total_trades > 0 and losing_trades == 0:
        fail("no losing trades detected")
    if total_trades > 0 and stop_exits == 0:
        fail("no stop-loss exits detected")
    if metrics.get("unrealistic_average_trade", False):
        fail("unrealistic average trade after fees")
    if metrics.get("stress_test_impossible_values", False):
        fail("stress test returned impossible values")
    if metrics.get("parameter_engine_failure", False):
        fail("parameter set returned engine failure values")

    passed = not failed
    allow_micro = validation.get("allow_micro_live_after_pass", True)
    status = "PASS_MICRO_LIVE" if passed and allow_micro else "BLOCK_LIVE"
    recommended = "MICRO_LIVE" if status == "PASS_MICRO_LIVE" else "BACKTEST_ONLY"
    return {
        "passed": passed,
        "status": status,
        "failed_rules": failed,
        "warnings": warnings,
        "recommended_mode": recommended,
        "risk_pct": risk.get("micro_live_risk_pct", 0.10),
    }


def write_live_unlock_report(result: dict, path: str = "reports/live_unlock_report.md") -> None:
    from pathlib import Path

    lines = [
        "# APEX XRP Fusion Live Unlock Report",
        "",
        f"- passed: {result['passed']}",
        f"- status: {result['status']}",
        f"- recommended_mode: {result['recommended_mode']}",
        f"- risk_pct: {result['risk_pct']}",
        "",
        "## Failed Rules",
    ]
    lines.extend([f"- {rule}" for rule in result["failed_rules"]] or ["- none"])
    lines.extend(["", "FULL_LIVE remains disabled."])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")

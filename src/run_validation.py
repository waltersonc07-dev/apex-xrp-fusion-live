from __future__ import annotations

import argparse

from .backtest import load_config, run_backtest_on_df, write_report
from .backtest_engine import write_trade_distribution_report
from .alignment_report import write_pine_python_alignment_report
from .data_loader import load_ohlcv_csv, validate_ohlcv_csv
from .stress_test import run_stress_tests, write_stress_report
from .trade_audit import audit_trades, write_trade_audit_report
from .validation_gate import evaluate_validation, write_live_unlock_report
from .walk_forward import run_walk_forward, write_walk_forward_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CSV with timestamp, open, high, low, close, volume")
    args = parser.parse_args()

    config = load_config()
    write_pine_python_alignment_report(config)
    data_result = validate_ohlcv_csv(args.csv)
    if not data_result["valid"]:
        print("BACKTEST RESULT: FAIL")
        print("VALIDATION RESULT: BLOCK_LIVE")
        print("RECOMMENDED MODE: BACKTEST_ONLY")
        print("FAILED RULES:")
        for error in data_result["errors"]:
            print(f"- {error}")
        print("NEXT ACTION: Fix data. Do not trade live.")
        return

    df = load_ohlcv_csv(args.csv)
    backtest = run_backtest_on_df(df, config)
    write_report(backtest)
    write_trade_distribution_report(backtest)
    walk_forward = run_walk_forward(df, config)
    write_walk_forward_report(walk_forward)
    stress = run_stress_tests(df, config)
    write_stress_report(stress)
    audit = audit_trades(backtest["trades"], config)
    write_trade_audit_report(audit)

    metrics = {
        **backtest,
        "out_of_sample_profit_factor": walk_forward["splits"]["out_of_sample"]["profit_factor"],
        "walk_forward_passed": walk_forward["passed"],
        "stress_test_doubled_fees_profitable": stress["doubled_fees_profitable"],
        "stress_test_increased_slippage_profitable": stress["increased_slippage_profitable"],
        "parameter_perturbation_acceptable": stress["parameter_robustness_acceptable"],
        "stress_test_impossible_values": stress["impossible_values"],
        "parameter_engine_failure": stress["parameter_engine_failure"],
        "trade_audit_passed": audit["passed"],
    }
    gate = evaluate_validation(metrics, config)
    write_live_unlock_report(gate)

    print("BACKTEST ENGINE: REALISTIC")
    print(f"SAME BAR POLICY: {backtest.get('same_bar_policy', 'stop_first')}")
    print(f"BACKTEST RESULT: {'PASS' if backtest['net_profit'] > 0 else 'FAIL'}")
    print(f"WIN RATE: {backtest['win_rate']:.2f}%")
    print(f"PROFIT FACTOR: {backtest['profit_factor']}")
    print(f"MAX DRAWDOWN: {backtest['max_drawdown_pct']:.2f}%")
    print(f"TOTAL TRADES: {backtest['total_trades']}")
    print(f"STOP LOSS EXITS: {backtest['stop_loss_exits']}")
    print(f"TAKE PROFIT EXITS: {backtest['take_profit_exits']}")
    print(f"FLIP EXITS: {backtest['flip_exits']}")
    print(f"VALIDATION RESULT: {gate['status']}")
    print(f"RECOMMENDED MODE: {gate['recommended_mode']}")
    print(f"RISK: {gate['risk_pct']:.2f}%")
    print("FAILED RULES:")
    if gate["failed_rules"]:
        for rule in gate["failed_rules"]:
            print(f"- {rule}")
    else:
        print("- none")
    if gate["status"] == "PASS_MICRO_LIVE":
        print("NEXT ACTION: Enable MICRO_LIVE only, keep FULL_LIVE disabled.")
    else:
        print("NEXT ACTION: Improve strategy or data. Do not trade live.")


if __name__ == "__main__":
    main()

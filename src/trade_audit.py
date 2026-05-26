from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_TRADE_FIELDS = [
    "entry_time",
    "exit_time",
    "entry_price",
    "exit_price",
    "stop_loss",
    "take_profit",
    "risk_amount",
    "planned_rr_at_entry",
    "realized_r_multiple",
    "fees",
    "slippage_cost",
    "qty",
    "side",
    "reason_for_entry",
    "reason_for_exit",
]


def audit_trades(trades: list[dict] | pd.DataFrame, config: dict) -> dict:
    df = pd.DataFrame(trades)
    issues: list[str] = []
    warnings: list[str] = []
    if df.empty:
        return {"passed": False, "issues": ["no trades to audit"], "warnings": [], "trade_count": 0}

    missing = [field for field in REQUIRED_TRADE_FIELDS if field not in df.columns]
    if missing:
        issues.append(f"missing trade fields: {', '.join(missing)}")
        return {"passed": False, "issues": issues, "warnings": warnings, "trade_count": len(df)}

    if df["stop_loss"].isna().any():
        issues.append("missing stop loss")
    if df["take_profit"].isna().any():
        issues.append("missing take profit")
    stop_distance = abs(df["entry_price"] - df["stop_loss"])
    if (stop_distance <= 0).any():
        issues.append("negative or zero stop distance")
    if (df["planned_rr_at_entry"] < config["strategy"]["min_rr"]).any():
        issues.append("planned RR below 2")
    if (df["risk_amount"] <= 0).any():
        issues.append("risk amount invalid")
    if (df["qty"] <= 0).any():
        issues.append("qty invalid")
    if "signal_id" in df.columns and df["signal_id"].duplicated().any():
        issues.append("duplicate signal")
    if "mode" in df.columns and (df["mode"] != "BACKTEST_ONLY").any():
        issues.append("trades opened outside allowed mode")
    if "position_overlap" in df.columns and df["position_overlap"].any():
        issues.append("position opened while already in position")

    max_risk_amount = 10000 * config["risk"]["normal_live_risk_pct"] / 100
    if (df["risk_amount"] > max_risk_amount * 1.05).any():
        issues.append("trade risk exceeds allowed risk")

    return {"passed": not issues, "issues": issues, "warnings": warnings, "trade_count": len(df)}


def write_trade_audit_report(result: dict, path: str | Path = "reports/trade_audit_report.md") -> None:
    lines = ["# Trade Audit Report", "", f"- passed: {result['passed']}", f"- trade_count: {result['trade_count']}", "", "## Issues"]
    lines.extend([f"- {issue}" for issue in result["issues"]] or ["- none"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {warning}" for warning in result["warnings"]] or ["- none"])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")

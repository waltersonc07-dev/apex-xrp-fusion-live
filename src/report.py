from __future__ import annotations

from pathlib import Path


def markdown_report(metrics: dict, path: str | Path = "reports/backtest_report.md") -> None:
    lines = ["# APEX XRP Fusion Live Report", ""]
    lines += [f"- {key}: {value}" for key, value in metrics.items()]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


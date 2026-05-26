from __future__ import annotations

from pathlib import Path


def write_pine_python_alignment_report(config: dict, path: str | Path = "reports/pine_python_alignment_report.md") -> None:
    strategy = config["strategy"]
    checks = [
        ("Supertrend ATR length", strategy["supertrend_atr_length"], 12),
        ("Supertrend multiplier", strategy["supertrend_multiplier"], 3.0),
        ("EMA fast", strategy["ema_fast"], 9),
        ("EMA slow", strategy["ema_slow"], 21),
        ("DEMA length", strategy["dema_length"], 200),
        ("ATR stop multiplier", strategy["stop_atr_mult"], 1.5),
        ("TP ATR multiplier", strategy["tp_atr_mult"], 3.0),
        ("Flip exit enabled", strategy["use_flip_exit"], True),
    ]
    lines = ["# Pine/Python Alignment Report", ""]
    mismatches = []
    for label, actual, expected in checks:
        ok = actual == expected
        lines.append(f"- {label}: Python={actual}, Pine target={expected}, aligned={ok}")
        if not ok:
            mismatches.append(label)
    lines.extend([
        "",
        "## Execution Notes",
        "- Pine uses `process_orders_on_close=true`; validation Python uses next-candle-open fills by default for conservative live-readiness testing.",
        "- Both Python and Pine use first-bar transition signals to avoid repeated signal spam.",
        "- Python validation uses `same_bar_policy=stop_first`; optimistic `tp_first` is not used for live unlock validation.",
        "",
        "## Mismatches",
    ])
    lines.extend([f"- {item}" for item in mismatches] or ["- none"])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


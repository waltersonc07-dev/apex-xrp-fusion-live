from __future__ import annotations

import csv
from pathlib import Path


FIELDS = [
    "timestamp",
    "symbol",
    "action",
    "price",
    "stop_loss",
    "take_profit",
    "risk_pct",
    "qty",
    "fundamental_score",
    "technical_reason",
    "risk_engine_decision",
    "result",
    "pnl",
    "r_multiple",
    "notes",
]


def write_journal(row: dict, path: str | Path = "journals/trades.csv") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    exists = target.exists()
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in FIELDS})


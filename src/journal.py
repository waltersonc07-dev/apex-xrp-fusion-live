from __future__ import annotations

import csv
import os
from pathlib import Path


# Where journals live. Defaults to ./journals/ for local dev, but on Render
# we set ``APEX_JOURNAL_DIR`` to the mount point of a persistent disk so
# trades survive container restarts. See render.yaml for the (commented-out)
# disk block — free tier does not support disks; this becomes active when the
# service upgrades.
DEFAULT_JOURNAL_DIR = os.getenv("APEX_JOURNAL_DIR", "journals")


def journal_path(filename: str = "trades.csv") -> Path:
    """Resolve the journal file path. Honors ``APEX_JOURNAL_DIR``."""
    base = Path(os.getenv("APEX_JOURNAL_DIR", DEFAULT_JOURNAL_DIR))
    return base / filename


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


def write_journal(row: dict, path: str | Path | None = None) -> None:
    target = Path(path) if path is not None else journal_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    exists = target.exists()
    with target.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in FIELDS})


from __future__ import annotations

import json
from pathlib import Path


def load_daily_score(path: str | Path = "fundamentals/daily_score.json") -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def trade_mode(total_score: int, config: dict) -> str:
    gate = config["fundamental_gate"]
    if total_score >= gate["full_allowed_score"]:
        return "FULL_ALLOWED"
    if total_score >= gate["reduced_allowed_score"]:
        return "REDUCED_ALLOWED"
    if total_score >= gate["micro_only_score"]:
        return "MICRO_ONLY"
    return "BLOCK_LIVE"


def live_allowed(total_score: int, mode: str, config: dict) -> bool:
    gate_mode = trade_mode(total_score, config)
    if gate_mode == "BLOCK_LIVE":
        return False
    if mode == "FULL_LIVE":
        return gate_mode in {"FULL_ALLOWED", "REDUCED_ALLOWED"}
    if mode == "MICRO_LIVE":
        return gate_mode in {"FULL_ALLOWED", "REDUCED_ALLOWED", "MICRO_ONLY"}
    return False


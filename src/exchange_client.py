from __future__ import annotations

import os


class ExchangeClient:
    def __init__(self, exchange: str = "BINGX") -> None:
        self.exchange = exchange

    def can_trade_real(self, mode: str, risk_approved: bool = False) -> bool:
        if not risk_approved or mode == "BACKTEST_ONLY":
            return False
        live = os.getenv("LIVE_TRADING", "false").lower() == "true"
        api_key = bool(os.getenv("BINGX_API_KEY"))
        api_secret = bool(os.getenv("BINGX_API_SECRET"))
        mode_enabled = os.getenv(mode, "false").lower() == "true"
        return live and mode_enabled and api_key and api_secret and mode in {"MICRO_LIVE", "FULL_LIVE"}

    def place_order(self, order: dict, mode: str, risk_approved: bool = False) -> dict:
        if not self.can_trade_real(mode, risk_approved=risk_approved):
            return {"status": "dry_run", "exchange": self.exchange, "order": order}
        return {"status": "blocked_stub", "exchange": self.exchange, "reason": "real exchange adapter not implemented"}

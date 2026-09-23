"""Interactive Brokers client stub — research / dry-run only.

This module intentionally has **no live order path**. It exists so research
code can depend on a stable shape (account summary, contract search, price
snapshot) without wiring IBKR MCP or TWS/Gateway order APIs.

Safety invariants (see SAFETY.md and docs/IBKR_READONLY_PLAN.md):
- ``IBKR_ENABLED`` defaults to false; when false, methods return dry-run
  placeholders and never contact a broker.
- There is no ``create_order`` / ``place_order`` that can submit to IBKR.
- Instrument mapping is TBD: this repo targets CEX-style ``XRPUSDT``;
  IBKR exposes CRYPTO / ETF / futures products under different contract
  specs. Do not assume 1:1 symbol equivalence.

Future wiring into ``ExchangeClient`` (not done here):
- ``ExchangeClient`` stays the execution façade used by ``webhook_server``.
- After validation_gate unlock, a gated adapter may delegate read-only
  calls here and keep ``place_order`` behind the same LIVE_TRADING /
  MICRO_LIVE / risk.mode checks as BingX. Until then, this stub never
  participates in order routing.
"""

from __future__ import annotations

import os
from typing import Any


# Repo strategy symbol vs IBKR product space — mapping is not implemented.
REPO_SYMBOL = "XRPUSDT"
IBKR_INSTRUMENT_NOTE = (
    "Instrument mismatch: strategy symbol is CEX-style XRPUSDT; "
    "IBKR offers CRYPTO (e.g. XRP.USD), ETF, and futures under different "
    "conids/secTypes. Mapping TBD — do not place orders against an "
    "unmapped contract."
)


def ibkr_enabled() -> bool:
    """Return True only when IBKR_ENABLED is explicitly set true.

    Even when True, this stub still refuses live orders; it only allows
    dry-run / NotImplemented read shapes for local research.
    """
    return os.getenv("IBKR_ENABLED", "false").lower() == "true"


class IbkrClient:
    """Read-only-shaped IBKR stub. No create_order that can fire."""

    def __init__(self, account_id: str | None = None) -> None:
        self.account_id = account_id or os.getenv("IBKR_ACCOUNT_ID", "")
        self.enabled = ibkr_enabled()
        self.dry_run = True  # always; live orders are not implemented

    def _placeholder(self, method: str, **extra: Any) -> dict[str, Any]:
        return {
            "status": "dry_run",
            "broker": "IBKR",
            "method": method,
            "ibkr_enabled": self.enabled,
            "instrument_note": IBKR_INSTRUMENT_NOTE,
            "repo_symbol": REPO_SYMBOL,
            **extra,
        }

    def get_account_summary(self) -> dict[str, Any]:
        """Account summary placeholder. Never hits a live IBKR API."""
        if not self.enabled:
            return self._placeholder(
                "get_account_summary",
                account_id=self.account_id or None,
                summary=None,
                reason="IBKR_ENABLED=false",
            )
        # Enabled but still stubbed: research shape only.
        return self._placeholder(
            "get_account_summary",
            account_id=self.account_id or None,
            summary={
                "NetLiquidation": None,
                "BuyingPower": None,
                "TotalCashValue": None,
            },
            reason="stub_no_live_connection",
        )

    def search_contracts(self, query: str) -> dict[str, Any]:
        """Contract search placeholder. Does not call IBKR search APIs."""
        q = (query or "").strip()
        return self._placeholder(
            "search_contracts",
            query=q,
            contracts=[],
            reason=(
                "stub_no_live_connection"
                if self.enabled
                else "IBKR_ENABLED=false"
            ),
        )

    def get_price_snapshot(self, contract: dict[str, Any] | str) -> dict[str, Any]:
        """Price snapshot placeholder. Does not fetch live quotes."""
        return self._placeholder(
            "get_price_snapshot",
            contract=contract,
            snapshot=None,
            reason=(
                "stub_no_live_connection"
                if self.enabled
                else "IBKR_ENABLED=false"
            ),
        )

    def create_order(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        """Explicitly refuse order creation.

        Present only so accidental call sites fail closed with a clear
        error instead of silently no-oping into a future live path.
        Live IBKR orders are forbidden until validation_gate passes and
        a human unlock — this method must never submit to a broker.
        """
        raise NotImplementedError(
            "IbkrClient.create_order is forbidden: live IBKR orders are "
            "disabled until validation_gate unlock. See docs/IBKR_READONLY_PLAN.md"
        )

    def place_order(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        """Alias refuse path — same policy as create_order."""
        raise NotImplementedError(
            "IbkrClient.place_order is forbidden: live IBKR orders are "
            "disabled until validation_gate unlock. See docs/IBKR_READONLY_PLAN.md"
        )

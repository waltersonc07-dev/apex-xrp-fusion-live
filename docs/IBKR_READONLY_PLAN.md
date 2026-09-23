# IBKR read-only → dry-run → gated orders plan

**Status**: Research scaffolding only. No live IBKR order APIs. `IBKR_ENABLED=false` by default (see `.env.example`). `risk.mode` remains `BACKTEST_ONLY`; `LIVE_TRADING` / `MICRO_LIVE` / `FULL_LIVE` stay false. Do not weaken SAFETY.md gates.

**Context**: This repo’s primary execution path is CEX-style BingX via `src/exchange_client.py` (`execution.exchange: BINGX`, symbol `XRPUSDT`). Interactive Brokers is a **separate** research track with an explicit instrument mismatch (below).

## Instrument mismatch (blocking for any order path)

| Layer | Identity |
|---|---|
| Repo strategy | `XRPUSDT` (CEX perpetual/spot style) |
| IBKR | CRYPTO (e.g. XRP.USD), ETF wrappers, or futures — different `conid` / `secType` / currency / sizing |

**Mapping is TBD.** Until a documented contract map exists and is validated, no IBKR order code may be enabled. Read-only stubs must surface this note (see `src/ibkr_client.py`).

## Three-step plan

### Step 1 — Read-only market + account

- Use `src/ibkr_client.py` shapes only: `get_account_summary`, `search_contracts`, `get_price_snapshot`.
- With `IBKR_ENABLED=false`, methods return dry-run placeholders and never contact a broker.
- Even if `IBKR_ENABLED=true` later for local experiments, the stub still does **not** open a live session or submit orders; a real read-only adapter would replace placeholders behind the same flag and still omit order APIs.
- Do **not** call IBKR MCP order tools from this repo or from assistants working here.

Exit criteria: account/market helpers are callable in unit tests without network; instrument note is documented; SAFETY defaults unchanged.

### Step 2 — Dry-run journal

- Route hypothetical IBKR intents through the existing journal (`src/journal.py` / `journals/`) with `result=dry_run` (or equivalent notes), mirroring `ExchangeClient.place_order` dry-run behavior.
- No broker submission. Journal rows are for research audit only.
- Keep `ExchangeClient` as the webhook execution façade; do not dual-route live webhooks to IBKR.

Exit criteria: a dry-run path can record intended symbol/side/qty/price without any IBKR order call; CI/safety scripts still pass.

### Step 3 — Gated orders only after `validation_gate` passes

- Real IBKR orders are allowed **only** after:
  1. `src/validation_gate.py` returns an unlock consistent with SAFETY.md (today: gate blocks live),
  2. `config/settings.yaml` `risk.mode` is intentionally moved off `BACKTEST_ONLY` by a human-approved change,
  3. Env unlocks: `LIVE_TRADING` and the appropriate `MICRO_LIVE` / `FULL_LIVE` flags,
  4. Documented XRPUSDT ↔ IBKR contract mapping is reviewed and checked in,
  5. Order APIs live behind `ExchangeClient` (or a thin adapter it owns) — **not** as free-standing `IbkrClient.create_order`.
- Until all of the above, `IbkrClient.create_order` / `place_order` must raise `NotImplementedError` (current behavior).

Exit criteria: same three-layer lock as BingX (env + YAML mode + validation gate); no IBKR order path that bypasses them.

## How this plugs into `exchange_client` later

Today:

```text
webhook_server → ExchangeClient(exchange=BINGX).place_order(...)
                     └─ dry_run / blocked_stub (no real adapter)
```

Later (proposed; not implemented in this change):

```text
webhook_server → ExchangeClient
                     ├─ BingX adapter (existing plan)
                     └─ optional IBKR read-only / dry-run delegate
                            └─ IbkrClient (this stub → future read-only client)
                     └─ place_order still gated by can_trade_real(...)
                            + validation_gate + instrument map
```

Recommended integration rules when wiring:

1. Keep `can_trade_real` / dry-run semantics; add IBKR credentials checks only inside a gated branch.
2. Do not import or call IBKR order MCP tools from `exchange_client`.
3. Prefer composition (`ExchangeClient` holds an `IbkrClient` for reads) over forking webhook logic.
4. Leave `risk.mode` and live env flags alone until Step 3 unlock criteria are met.

## Files in this scaffolding

| File | Role |
|---|---|
| `.env.example` | `IBKR_ENABLED=false` + comments forbidding live orders |
| `src/ibkr_client.py` | Read-only-shaped stub; order methods raise |
| `docs/IBKR_READONLY_PLAN.md` | This plan |

`config/settings.yaml` risk/live flags are **not** changed by this work.

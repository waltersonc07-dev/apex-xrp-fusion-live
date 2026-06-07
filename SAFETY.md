# APEX Live-Trading Safety

This document describes the three independent layers that prevent APEX from sending real orders. All three must be intentionally unlocked before any real capital is at risk. None of them may be bypassed automatically by an AI assistant, a script, or a CI job.

## Layer 1 — Environment variables

Defined in `.env.example` and enforced in `render.yaml`. Safe defaults:

```text
LIVE_TRADING=false
MICRO_LIVE=false
FULL_LIVE=false
RISK_MODE=BACKTEST_ONLY
```

If any of these are set to a non-safe value while `risk.mode` in `config/settings.yaml` is `BACKTEST_ONLY`, the webhook server must refuse to start (enforced by `scripts/check_safe_defaults.py`).

## Layer 2 — Configuration file

`config/settings.yaml` carries the canonical mode:

```yaml
risk:
  mode: BACKTEST_ONLY
```

Allowed values, in increasing risk:

- `BACKTEST_ONLY` — research only, no orders, no API client calls
- `MICRO_LIVE` — real orders permitted at `risk.micro_live_risk_pct`, gated behind a passing validation report
- `FULL_LIVE` — real orders permitted at `risk.normal_live_risk_pct`, additionally gated behind `validation.allow_full_live_after_pass: true`

Today both `allow_micro_live_after_pass` and `allow_full_live_after_pass` are governed by `src/validation_gate.py`. `FULL_LIVE` is disabled at the gate even if the YAML is hand-edited.

## Layer 3 — Validation gate

`src/validation_gate.py` reads the latest backtest, walk-forward, stress-test, and trade-audit reports and decides whether to allow `MICRO_LIVE`. The current strategy fails every rule in `reports/live_unlock_report.md`, so the gate returns `BLOCK_LIVE`.

The gate is the only place in the codebase that may flip the runtime mode. No other module — including AI-generated changes — may write `risk.mode` directly.

## Verifying the lock

Run any of these at any time to confirm the system is safe:

```bash
python scripts/check_safe_defaults.py
python -m src.run_validation --csv data/raw/xrpusdt_1h.csv
cat reports/live_unlock_report.md
```

CI runs `scripts/check_safe_defaults.py` on every push and pull request. A pull request that disables the safety defaults will fail CI and cannot be merged without manual override.

## Rules for AI assistants working in this repo

Any AI assistant (Codex, Claude, Perplexity Computer, Gemini, etc.) that opens a pull request against this repository must follow these rules:

1. Never set `LIVE_TRADING`, `MICRO_LIVE`, or `FULL_LIVE` to `true` without an explicit, written request from the repository owner in the PR description.
2. Never change `risk.mode` away from `BACKTEST_ONLY` in `config/settings.yaml` without the same explicit written request.
3. Never commit secrets. `.env` is gitignored; `TRADINGVIEW_WEBHOOK_SECRET`, `BINGX_API_KEY`, and `BINGX_API_SECRET` must remain empty in `.env.example`.
4. Never weaken thresholds in `validation:` (e.g. lowering `min_profit_factor`, `min_oos_profit_factor`, or raising `max_drawdown_pct`) without a separate PR that explains the regime change.
5. Never delete or skip tests in `tests/test_validation_gate.py`, `tests/test_risk_engine.py`, or `tests/test_suspicious_backtest_detection.py`.

A PR that violates any of the above must be rejected.

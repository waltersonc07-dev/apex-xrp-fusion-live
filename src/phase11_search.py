"""
Phase 11 — Grid search engine + per-symbol acceptance gate (PR 2 + PR 3).

Walks the frozen parameter grid (``src.phase11_grid``) through the
walk-forward orchestrator (``src.phase11_orchestrator``) and writes one
row per (variant, params, symbol) combination to a CSV plus a Markdown
summary.

PR 2 contributed:
  * Per-combo run of the orchestrator across all symbols.
  * Locked CSV schema (`combo_key` ... `min_fold_oos_trades`).
  * Markdown summary with informational top-10 rankings.

PR 3 contributes (this revision):
  * Per-symbol acceptance gate via ``src.phase11_gate``.
  * Appends to ``CSV_COLUMNS``: ``raw_p``, ``bonferroni_p``, ``n_tested``,
    ``survives_raw``, ``survives_bonferroni``, ``verdict``, ``gate_reason``.
    Existing 13 columns are untouched — the schema lock test still holds.
  * Markdown summary now reports verdict counts and lists
    VALIDATED_RESEARCH_CANDIDATE / MICRO_LIVE_CANDIDATE rows.

PR 3 still defers to later PRs:
  * Primary/control portfolio aggregation + per-pair >40% cap → PR 4.
  * Bayesian posterior intervals                              → PR 5.

``n_tested`` for the Bonferroni adjustment is sourced directly from
``GridSpec.total`` so the gate's correction always matches the frozen
grid size that produced the rows.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from .phase10_fx_gold_daily import (
    CONTROL_SYMBOLS,
    DEFAULT_CONFIG,
    PRIMARY_SYMBOLS,
    _load_csv,
)
from .phase11_gate import (
    ALL_VERDICTS,
    GateResult,
    VERDICT_BLOCKED,
    VERDICT_MICRO_LIVE_CANDIDATE,
    VERDICT_VALIDATED_RESEARCH_CANDIDATE,
    VERDICT_WATCH,
    evaluate_gate,
)
from .phase11_grid import GridSpec, load_grid, summarize as summarize_grid
from .phase11_portfolio import (
    build_portfolio_verdicts,
    render_portfolio_markdown,
    write_portfolio_csv,
)
from .phase11_orchestrator import (
    DEFAULT_N_FOLDS,
    DEFAULT_WARMUP_BARS,
    Phase11Splitter,
    run_orchestrator,
)


# CSV column order is locked. PR 2 froze the first 13 columns; PR 3
# APPENDS gate columns (raw_p ... gate_reason) per the contract in
# ``tests/test_phase11_search.py::test_csv_columns_constant_is_locked``.
# Future PRs may also append but must NEVER reorder or rename anything.
CSV_COLUMNS: tuple[str, ...] = (
    "combo_key",
    "variant",
    "params_json",
    "symbol",
    "status",                          # OK / INSUFFICIENT_DATA
    "n_folds",
    "median_oos_pf",
    "worst_fold_oos_pf",
    "median_oos_sharpe",
    "max_oos_dd_pct",
    "max_is_to_oos_sharpe_degradation_pct",
    "total_oos_trades",
    "min_fold_oos_trades",
    # ---- PR 3: acceptance gate columns ----------------------------------
    "raw_p",
    "bonferroni_p",
    "n_tested",
    "survives_raw",
    "survives_bonferroni",
    "verdict",
    "gate_reason",
)


@dataclass(frozen=True)
class SearchRow:
    combo_key: str
    variant: str
    params: dict
    symbol: str
    status: str                        # "OK" or "INSUFFICIENT_DATA"
    n_folds: int
    summary: dict                      # full per-symbol summary dict from orchestrator
    folds: tuple = ()                  # per-fold payloads (dicts) for the gate's p-value
    gate: GateResult | None = None     # populated by attach_gate_results()

    def to_csv_row(self) -> dict:
        s = self.summary or {}
        row = {
            "combo_key": self.combo_key,
            "variant": self.variant,
            "params_json": json.dumps(self.params, sort_keys=True),
            "symbol": self.symbol,
            "status": self.status,
            "n_folds": self.n_folds,
            "median_oos_pf": _fmt(s.get("median_oos_pf")),
            "worst_fold_oos_pf": _fmt(s.get("worst_fold_oos_pf")),
            "median_oos_sharpe": _fmt(s.get("median_oos_sharpe")),
            "max_oos_dd_pct": _fmt(s.get("max_oos_dd_pct")),
            "max_is_to_oos_sharpe_degradation_pct":
                _fmt(s.get("max_is_to_oos_sharpe_degradation_pct")),
            "total_oos_trades": _intfmt(s.get("total_oos_trades")),
            "min_fold_oos_trades": _intfmt(s.get("min_fold_oos_trades")),
        }
        # PR 3 gate columns. Empty if attach_gate_results hasn't run.
        g = self.gate
        if g is None:
            row.update({
                "raw_p": "", "bonferroni_p": "", "n_tested": "",
                "survives_raw": "", "survives_bonferroni": "",
                "verdict": "", "gate_reason": "",
            })
        else:
            row.update({
                "raw_p": _fmt(g.raw_p),
                "bonferroni_p": _fmt(g.bonferroni_p),
                "n_tested": str(int(g.n_tested)),
                "survives_raw": "true" if g.survives_raw else "false",
                "survives_bonferroni":
                    "true" if g.survives_bonferroni else "false",
                "verdict": g.verdict,
                "gate_reason": g.reason,
            })
        return row


def _fmt(v) -> str:
    if v is None:
        return ""
    try:
        return f"{float(v):.6f}"
    except (TypeError, ValueError):
        return ""


def _intfmt(v) -> str:
    if v is None:
        return ""
    try:
        return str(int(v))
    except (TypeError, ValueError):
        return ""


def run_grid_search(
    data_by_symbol: dict[str, pd.DataFrame],
    grid: GridSpec,
    splitter: Phase11Splitter | None = None,
    base_cfg: dict | None = None,
    variant_filter: Iterable[str] | None = None,
) -> list[SearchRow]:
    """Walk every combo through the orchestrator and return per-symbol rows.

    Args
    ----
    data_by_symbol : OHLCV data per symbol.
    grid           : Loaded + validated GridSpec from ``load_grid()``.
    splitter       : Optional override of the 5-fold expanding splitter.
    base_cfg       : Optional dict merged into the orchestrator config
                     beneath each combo's params (combo params win).
    variant_filter : Optional iterable of variants to run; useful for
                     quick iteration. None = walk the entire grid.

    Returns
    -------
    list[SearchRow] — one row per (combo × symbol). Deterministic order.
    """
    splitter = splitter or Phase11Splitter()
    base_cfg = base_cfg or {}
    keep_variants = (
        set(variant_filter) if variant_filter is not None else None
    )

    rows: list[SearchRow] = []
    for combo in grid.combos:
        if keep_variants is not None and combo.variant not in keep_variants:
            continue
        cfg = {**DEFAULT_CONFIG, **base_cfg, **combo.params}
        report = run_orchestrator(
            data_by_symbol,
            variant=combo.variant,
            cfg=cfg,
            splitter=splitter,
        )
        for symbol, payload in report["per_symbol"].items():
            if payload.get("status") != "OK":
                rows.append(SearchRow(
                    combo_key=combo.key,
                    variant=combo.variant,
                    params=dict(combo.params),
                    symbol=symbol,
                    status=payload.get("status", "ERROR"),
                    n_folds=splitter.n_folds,
                    summary={},
                    folds=(),
                ))
                continue
            rows.append(SearchRow(
                combo_key=combo.key,
                variant=combo.variant,
                params=dict(combo.params),
                symbol=symbol,
                status="OK",
                n_folds=splitter.n_folds,
                summary=payload["summary"],
                folds=tuple(_fold_payload(f) for f in payload.get("folds", [])),
            ))
    return rows


def _fold_payload(f) -> dict:
    """Coerce an orchestrator FoldResult into a plain dict for the gate."""
    if isinstance(f, dict):
        return f
    return {
        "oos_pf": getattr(f, "oos_pf", None),
        "oos_sharpe": getattr(f, "oos_sharpe", None),
        "oos_trades": getattr(f, "oos_trades", None),
        "oos_max_dd_pct": getattr(f, "oos_max_dd_pct", None),
        "is_to_oos_sharpe_degradation_pct":
            getattr(f, "is_to_oos_sharpe_degradation_pct", None),
        "oos_metrics": dict(getattr(f, "oos_metrics", {}) or {}),
    }


def attach_gate_results(
    rows: list[SearchRow], n_tested: int,
) -> list[SearchRow]:
    """Run the PR 3 acceptance gate against each row.

    Returns a NEW list of rows with ``gate`` populated. ``n_tested`` is
    used as the Bonferroni multiplier. Pass ``grid.total`` from the same
    grid that produced these rows.
    """
    out: list[SearchRow] = []
    for r in rows:
        gate = evaluate_gate(
            status=r.status,
            summary=r.summary,
            folds=list(r.folds),
            n_tested=n_tested,
        )
        out.append(SearchRow(
            combo_key=r.combo_key,
            variant=r.variant,
            params=dict(r.params),
            symbol=r.symbol,
            status=r.status,
            n_folds=r.n_folds,
            summary=dict(r.summary or {}),
            folds=r.folds,
            gate=gate,
        ))
    return out


def write_csv(rows: list[SearchRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS))
        writer.writeheader()
        for r in rows:
            writer.writerow(r.to_csv_row())


def render_summary_markdown(
    rows: list[SearchRow], grid: GridSpec, csv_path: Path | None = None,
) -> str:
    """Render a human-readable summary of the grid-search run."""
    # Verdict counts — only meaningful once attach_gate_results has run.
    verdict_counts: dict[str, int] = {v: 0 for v in ALL_VERDICTS}
    gated_rows: list[SearchRow] = [r for r in rows if r.gate is not None]
    for r in gated_rows:
        verdict_counts[r.gate.verdict] = verdict_counts.get(r.gate.verdict, 0) + 1

    lines: list[str] = [
        "# Phase 11 — Grid Search Summary (PR 2)",
        "",
        f"- grid version: `{grid.version}`",
        f"- total combinations: **{grid.total}** (cap {grid.hard_cap})",
        f"- per-variant counts: " + ", ".join(
            f"`{v}={grid.per_variant_counts.get(v, 0)}`"
            for v in sorted(grid.per_variant_counts)
        ),
        f"- rows written: **{len(rows)}**",
    ]
    if csv_path is not None:
        lines.append(f"- csv: `{csv_path}`")
    lines.append("")
    lines.append(
        "> Runtime mode: **BACKTEST_ONLY**. No live trading. "
        "This report cannot toggle any live-trading flag."
    )
    lines.append("")
    if gated_rows:
        lines.append(
            "> Per-symbol acceptance gate is active (PR 3). The portfolio "
            "aggregation + per-pair >40% cap lands in PR 4; even the "
            "highest verdict label remains research-only."
        )
    else:
        lines.append(
            "> Acceptance gate has NOT been applied to these rows. Call "
            "``attach_gate_results(rows, grid.total)`` before rendering for "
            "verdict columns to be meaningful."
        )
    lines.append("")
    if gated_rows:
        lines.append("## Verdict counts")
        lines.append("")
        for v in ALL_VERDICTS:
            lines.append(f"- `{v}`: {verdict_counts.get(v, 0)} row(s)")
        lines.append("")

        candidates = [
            r for r in gated_rows
            if r.gate.verdict in (
                VERDICT_VALIDATED_RESEARCH_CANDIDATE,
                VERDICT_MICRO_LIVE_CANDIDATE,
            )
        ]
        if candidates:
            lines.append("## Candidates surfaced by the gate")
            lines.append("")
            lines.append(
                "| Variant | Symbol | Params | Verdict | Median OOS PF | "
                "Worst-fold OOS PF | bonferroni_p |"
            )
            lines.append(
                "|---------|--------|--------|---------|--------------:|"
                "------------------:|-------------:|"
            )
            for r in candidates:
                s = r.summary
                g = r.gate
                params_str = ", ".join(
                    f"`{k}={v}`" for k, v in sorted(r.params.items())
                )
                lines.append(
                    f"| {r.variant} | {r.symbol} | {params_str} | "
                    f"{g.verdict} | "
                    f"{float(s.get('median_oos_pf', 0)):.3f} | "
                    f"{float(s.get('worst_fold_oos_pf', 0)):.3f} | "
                    f"{g.bonferroni_p:.4f} |"
                )
            lines.append("")
        else:
            lines.append(
                "_No VALIDATED_RESEARCH_CANDIDATE or MICRO_LIVE_CANDIDATE "
                "rows in this run. All OK rows are BLOCKED or WATCH._"
            )
            lines.append("")

    lines.append("## Skip / data-availability summary")
    lines.append("")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    if by_status:
        for k in sorted(by_status):
            lines.append(f"- `{k}`: {by_status[k]} row(s)")
    else:
        lines.append("_no rows_")
    lines.append("")

    # Best 10 per symbol by median OOS PF — informational only, not a verdict.
    ok_rows = [r for r in rows if r.status == "OK" and r.summary]
    if not ok_rows:
        lines.append(
            "_No OK rows to rank. Run "
            "`python -m src.phase10_data_downloader --years 20` first._"
        )
        return "\n".join(lines)

    by_symbol: dict[str, list[SearchRow]] = {}
    for r in ok_rows:
        by_symbol.setdefault(r.symbol, []).append(r)

    for symbol in sorted(by_symbol):
        srows = sorted(
            by_symbol[symbol],
            key=lambda r: (
                -float(r.summary.get("median_oos_pf", 0.0)),
                -float(r.summary.get("worst_fold_oos_pf", 0.0)),
                -float(r.summary.get("median_oos_sharpe", 0.0)),
                float(r.summary.get("max_oos_dd_pct", 0.0)),
            ),
        )[:10]
        lines.append(f"## Top 10 by median OOS PF — {symbol}")
        lines.append("")
        lines.append(
            "| Variant | Params | Median OOS PF | Worst-fold OOS PF | "
            "Median OOS Sharpe | Max OOS DD% | Total OOS trades |"
        )
        lines.append(
            "|---------|--------|--------------:|------------------:|"
            "------------------:|------------:|-----------------:|"
        )
        for r in srows:
            s = r.summary
            params_str = ", ".join(f"`{k}={v}`" for k, v in sorted(r.params.items()))
            lines.append(
                f"| {r.variant} | {params_str} | "
                f"{float(s.get('median_oos_pf', 0)):.3f} | "
                f"{float(s.get('worst_fold_oos_pf', 0)):.3f} | "
                f"{float(s.get('median_oos_sharpe', 0)):.3f} | "
                f"{float(s.get('max_oos_dd_pct', 0)):.2f} | "
                f"{int(s.get('total_oos_trades', 0))} |"
            )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "Source: `src/phase11_search.py` (PR 2 of N). Acceptance gate "
        "with Bonferroni-adjusted p-values and primary/control split is "
        "scheduled for phase11/pr3 and phase11/pr4 per "
        "`docs/phase11_design.md` Amendment A."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_symbols(data_dir: Path, symbols: Iterable[str]) -> dict[str, pd.DataFrame]:
    by_symbol: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        path = data_dir / f"{sym.lower()}_1d.csv"
        if path.exists():
            by_symbol[sym] = _load_csv(path)
    return by_symbol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 11 — frozen-grid walk-forward search (PR 2)"
    )
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument(
        "--symbols",
        default=",".join(PRIMARY_SYMBOLS + CONTROL_SYMBOLS),
    )
    parser.add_argument(
        "--variants", default=None,
        help="Comma-separated variants to run (default: all in grid).",
    )
    parser.add_argument("--n-folds", type=int, default=DEFAULT_N_FOLDS)
    parser.add_argument("--warmup-bars", type=int, default=DEFAULT_WARMUP_BARS)
    parser.add_argument(
        "--output-csv",
        default="reports/phase11_search.csv",
    )
    parser.add_argument(
        "--output-md",
        default="reports/phase11_search.md",
    )
    parser.add_argument(
        "--output-portfolio-csv",
        default="reports/phase11_portfolio.csv",
    )
    parser.add_argument(
        "--output-portfolio-md",
        default="reports/phase11_portfolio.md",
    )
    args = parser.parse_args(argv)

    grid = load_grid()
    print(summarize_grid(grid))

    data_dir = Path(args.data_dir)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    by_symbol = _load_symbols(data_dir, symbols)
    if not by_symbol:
        print(
            f"No symbol CSVs found in {data_dir}. "
            "Run `python -m src.phase10_data_downloader --years 20` first."
        )
        return 0

    splitter = Phase11Splitter(
        n_folds=args.n_folds, warmup_bars=args.warmup_bars
    )
    variant_filter = (
        [v.strip().upper() for v in args.variants.split(",") if v.strip()]
        if args.variants
        else None
    )
    rows = run_grid_search(
        by_symbol, grid, splitter=splitter, variant_filter=variant_filter
    )
    rows = attach_gate_results(rows, n_tested=grid.total)
    csv_path = Path(args.output_csv)
    write_csv(rows, csv_path)
    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        render_summary_markdown(rows, grid, csv_path=csv_path), encoding="utf-8",
    )
    print(f"Wrote {csv_path} ({len(rows)} rows)")
    print(f"Wrote {md_path}")

    # PR 4: aggregate to portfolio verdicts. Write only if any primary
    # symbols are present in the run, otherwise the portfolio CSV is
    # all-INSUFFICIENT_DATA noise.
    portfolio_verdicts = build_portfolio_verdicts(rows, n_tested=grid.total)
    if portfolio_verdicts:
        portfolio_csv = Path(args.output_portfolio_csv)
        write_portfolio_csv(portfolio_verdicts, portfolio_csv)
        portfolio_md = Path(args.output_portfolio_md)
        portfolio_md.parent.mkdir(parents=True, exist_ok=True)
        portfolio_md.write_text(
            render_portfolio_markdown(portfolio_verdicts, n_tested=grid.total),
            encoding="utf-8",
        )
        print(f"Wrote {portfolio_csv} ({len(portfolio_verdicts)} combos)")
        print(f"Wrote {portfolio_md}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

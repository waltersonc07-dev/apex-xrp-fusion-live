"""
Phase 11 — Grid search engine (PR 2 of N).

Walks the frozen parameter grid (``src.phase11_grid``) through the
walk-forward orchestrator (``src.phase11_orchestrator``) and writes one
row per (variant, params, symbol) combination to a CSV plus a Markdown
summary.

PR 2 deliberately ships WITHOUT:

  * raw + Bonferroni p-value columns      (deferred to phase11/pr3 — needs
                                           an explicit null and a p-value
                                           estimator)
  * primary/control portfolio aggregation (deferred to phase11/pr4)
  * acceptance gate (Amendment A § A.5)   (deferred to phase11/pr3)

What PR 2 DOES ship:

  1. ``run_grid_search()`` — walks every combo through the orchestrator
     and collects per-symbol summaries. No verdict is emitted at the
     combo level; the verdict still comes from the orchestrator and is
     still ``BLOCKED`` by design until PR 3.
  2. CSV writer with a stable, documented column order. Schema is
     locked here so PR 3 only ADDS columns (raw_p, bonferroni_p,
     survives_*, verdict) — never reorders or renames.
  3. CLI: ``python -m src.phase11_search --variants V0,V2 --symbols EURUSD``
     for quick iteration. Defaults walk the full grid across all 4 symbols.

The acceptance gate's ``n_tested`` count (Amendment A § A.3) will be
sourced from the loaded ``GridSpec.total`` in PR 3 — same source of
truth as this module's row count.
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
from .phase11_grid import GridSpec, load_grid, summarize as summarize_grid
from .phase11_orchestrator import (
    DEFAULT_N_FOLDS,
    DEFAULT_WARMUP_BARS,
    Phase11Splitter,
    run_orchestrator,
)


# CSV column order is locked. PR 3 may APPEND columns
# (raw_p, bonferroni_p, n_tested, survives_raw, survives_bonferroni, verdict)
# but must NOT reorder or rename.
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
    # ---- columns reserved for PR 3 (must stay at the end) ---------------
    # raw_p, bonferroni_p, n_tested, survives_raw, survives_bonferroni, verdict
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

    def to_csv_row(self) -> dict:
        s = self.summary or {}
        return {
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
            ))
    return rows


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
    lines.append(
        "> Acceptance gate, raw + Bonferroni p-value columns, and the "
        "primary/control portfolio split land in phase11/pr3 and "
        "phase11/pr4. PR 2 emits raw per-symbol metrics only."
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
    csv_path = Path(args.output_csv)
    write_csv(rows, csv_path)
    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        render_summary_markdown(rows, grid, csv_path=csv_path), encoding="utf-8",
    )
    print(f"Wrote {csv_path} ({len(rows)} rows)")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

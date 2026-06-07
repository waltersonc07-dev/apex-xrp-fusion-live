"""
Phase 11 — Walk-Forward Orchestrator (PR 1 of N).

This module implements the *minimum viable* Phase 11 walk-forward optimization
framework, per ``docs/phase11_design.md`` Amendment A. PR 1 deliberately ships
without:

  * grid search       (deferred to phase11/pr2)
  * frozen grid file  (deferred to phase11/pr2 — there is nothing to freeze yet)
  * Bonferroni p-values  (deferred to phase11/pr3 — requires a search space)
  * portfolio aggregation with primary/control split (deferred to phase11/pr4)

What it DOES ship:

  1. ``Phase11Splitter`` — 5-fold expanding-window splitter with strict
     leakage-free fold construction (Section 2 of the design doc).
  2. ``run_orchestrator()`` — runs default Phase 10 parameters through the
     5-fold WFO and emits per-fold OOS metrics (IS Sharpe + OOS Sharpe,
     IS→OOS degradation, OOS PF, trade count, max DD).
  3. A *composite* ranking scaffold (Amendment A § A.6) — even though there's
     only one variant×params combo today, the ranking machinery is in place
     so PR 2's grid search drops straight in.
  4. Verdict labels constrained to the four strings in Amendment A § A.7.
     There is NO code path that can set ``risk.mode``, ``LIVE_TRADING``,
     ``MICRO_LIVE``, or ``FULL_LIVE``. ``test_phase11_safety_invariants.py``
     enforces this with a source scan.
  5. CLI entry point that mirrors the Phase 10 CLI style.

Design contract (binding):
  * Read-only: never touches config/, .env*, render.yaml, validation_gate.py,
    risk_engine.py, webhook_server.py, exchange_client.py, or strategy.py.
  * Runtime mode is BACKTEST_ONLY at all times. This module does not even
    import the live-trading or exchange modules.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd

from .phase10_fx_gold_daily import (
    DEFAULT_CONFIG,
    PHASE10_VARIANTS,
    PRIMARY_SYMBOLS,
    CONTROL_SYMBOLS,
    _backtest_variant,
    _load_csv,
)


# ---------------------------------------------------------------------------
# Verdict labels — restricted set per Amendment A § A.7.
# Any other label is a bug; the unit tests assert membership in this set.
# ---------------------------------------------------------------------------

VERDICT_BLOCKED = "BLOCKED"
VERDICT_WATCH = "WATCH"
VERDICT_VALIDATED_RESEARCH = "VALIDATED_RESEARCH_CANDIDATE"
VERDICT_MICRO_LIVE_MANUAL = "MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW"

ALLOWED_VERDICTS: frozenset[str] = frozenset({
    VERDICT_BLOCKED,
    VERDICT_WATCH,
    VERDICT_VALIDATED_RESEARCH,
    VERDICT_MICRO_LIVE_MANUAL,
})


# Default Phase 11 WFO parameters. These are documentation-driven (Section
# 2.1 of the design doc) and may be overridden by the caller; the splitter
# enforces consistency. Changing the defaults requires a docs update.
DEFAULT_N_FOLDS = 5
DEFAULT_WARMUP_BARS = 210   # EMA(200) + ADX warmup
DEFAULT_MIN_BARS = 1000     # below this, splitter refuses to construct folds


# ---------------------------------------------------------------------------
# Splitter — 5-fold expanding window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fold:
    """One walk-forward fold. Indices are half-open: [start, end)."""
    index: int          # 1..n_folds
    is_start: int       # in-sample start (>= warmup_bars)
    is_end: int         # in-sample end (exclusive)
    oos_start: int      # out-of-sample start (== is_end, no gap, no overlap)
    oos_end: int        # out-of-sample end (exclusive)

    def __post_init__(self) -> None:
        if self.is_start >= self.is_end:
            raise ValueError(f"fold {self.index}: empty IS window")
        if self.oos_start >= self.oos_end:
            raise ValueError(f"fold {self.index}: empty OOS window")
        if self.oos_start != self.is_end:
            raise ValueError(
                f"fold {self.index}: leakage — oos_start {self.oos_start} "
                f"!= is_end {self.is_end}"
            )

    @property
    def is_len(self) -> int:
        return self.is_end - self.is_start

    @property
    def oos_len(self) -> int:
        return self.oos_end - self.oos_start


class Phase11Splitter:
    """Build a 5-fold expanding-window split of a time-indexed DataFrame.

    Invariants enforced (and tested):
      * No leakage: ``fold.oos_start == fold.is_end`` for every fold.
      * Monotone: ``fold[k].oos_end <= fold[k+1].oos_end``.
      * IS expands: ``fold[k].is_end <= fold[k+1].is_end``.
      * Warmup respected: ``fold[k].is_start >= warmup_bars`` for every fold.
      * OOS slices are disjoint and cover the post-warmup tail of history.
    """

    def __init__(
        self,
        n_folds: int = DEFAULT_N_FOLDS,
        warmup_bars: int = DEFAULT_WARMUP_BARS,
        min_bars: int = DEFAULT_MIN_BARS,
    ) -> None:
        if n_folds < 2:
            raise ValueError("n_folds must be >= 2")
        if warmup_bars < 0:
            raise ValueError("warmup_bars must be >= 0")
        self.n_folds = n_folds
        self.warmup_bars = warmup_bars
        self.min_bars = min_bars

    def split(self, df: pd.DataFrame) -> list[Fold]:
        n = len(df)
        if n < self.min_bars:
            raise ValueError(
                f"need at least {self.min_bars} bars for {self.n_folds}-fold "
                f"WFO; got {n}"
            )
        usable = n - self.warmup_bars
        # OOS chunk size is roughly equal across folds; the last fold absorbs
        # the remainder so total OOS coverage == usable - (initial IS budget).
        # We reserve an initial IS budget so fold 1 has enough room to fit.
        # The design doc proposes an initial IS = 60% of usable; later folds
        # add equal OOS chunks until exhausted.
        initial_is = int(usable * 0.60)
        if initial_is <= 0:
            raise ValueError("warmup_bars consumes all of history")
        remaining_oos = usable - initial_is
        chunk = remaining_oos // self.n_folds
        if chunk < 1:
            raise ValueError(
                f"OOS chunk size collapsed to 0 — need more bars or fewer folds"
            )

        folds: list[Fold] = []
        is_start = self.warmup_bars
        is_end = is_start + initial_is
        for k in range(1, self.n_folds + 1):
            oos_start = is_end
            if k < self.n_folds:
                oos_end = oos_start + chunk
            else:
                # Last fold absorbs the remainder, never overshooting n.
                oos_end = n
            if oos_end > n:
                oos_end = n
            folds.append(
                Fold(
                    index=k,
                    is_start=is_start,
                    is_end=is_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                )
            )
            # Expanding window: next IS includes everything up to the OOS we
            # just scored.
            is_end = oos_end
        return folds


# ---------------------------------------------------------------------------
# Orchestrator — runs default params through WFO per symbol
# ---------------------------------------------------------------------------


@dataclass
class FoldResult:
    symbol: str
    variant: str
    fold: int
    is_metrics: dict = field(default_factory=dict)
    oos_metrics: dict = field(default_factory=dict)

    @property
    def is_sharpe(self) -> float:
        return float(self.is_metrics.get("sharpe", 0.0))

    @property
    def oos_sharpe(self) -> float:
        return float(self.oos_metrics.get("sharpe", 0.0))

    @property
    def oos_pf(self) -> float:
        pf = self.oos_metrics.get("profit_factor", 0.0)
        if pf == float("inf"):
            # Replace infinity with a large finite sentinel so ranking/stats
            # don't blow up. 99.0 is well above any realistic PF.
            return 99.0
        return float(pf)

    @property
    def oos_trades(self) -> int:
        return int(self.oos_metrics.get("trades", 0))

    @property
    def oos_max_dd_pct(self) -> float:
        return float(self.oos_metrics.get("max_drawdown_pct", 0.0))

    @property
    def is_to_oos_sharpe_degradation_pct(self) -> float:
        """Percent decline from IS Sharpe to OOS Sharpe.

        Positive = degradation (OOS worse than IS).
        Negative = OOS *better* than IS (unusual; we report as 0% degradation).
        If IS Sharpe is <= 0 the metric is undefined and we return 100%
        (treated as failure) so degradation gates can't be gamed by negative IS.
        """
        if self.is_sharpe <= 0:
            return 100.0
        deg = (self.is_sharpe - self.oos_sharpe) / self.is_sharpe * 100.0
        return max(0.0, float(deg))


def _backtest_slice(
    df: pd.DataFrame,
    variant: str,
    symbol: str,
    cfg: dict,
    start: int,
    end: int,
) -> dict:
    """Run the Phase 10 backtest on a half-open index slice and return metrics."""
    sub = df.iloc[start:end].copy()
    res = _backtest_variant(sub, variant, symbol, cfg)
    return res.metrics


def run_orchestrator(
    data_by_symbol: dict[str, pd.DataFrame],
    variant: str = "V0",
    cfg: dict | None = None,
    splitter: Phase11Splitter | None = None,
) -> dict:
    """Run Phase 11 WFO with default params on each symbol.

    Returns a dict with per-symbol fold results, a per-symbol summary, and
    a placeholder verdict (always ``BLOCKED`` in PR 1 because the acceptance
    gate from § A.5 is not implemented until PR 3).
    """
    if variant not in PHASE10_VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; choose from {PHASE10_VARIANTS}")
    cfg = {**DEFAULT_CONFIG, **(cfg or {})}
    splitter = splitter or Phase11Splitter()

    per_symbol: dict[str, dict] = {}
    for symbol, df in data_by_symbol.items():
        try:
            folds = splitter.split(df)
        except ValueError as exc:
            per_symbol[symbol] = {
                "status": "INSUFFICIENT_DATA",
                "reason": str(exc),
                "folds": [],
            }
            continue

        fold_results: list[FoldResult] = []
        for fold in folds:
            is_m = _backtest_slice(df, variant, symbol, cfg, fold.is_start, fold.is_end)
            oos_m = _backtest_slice(df, variant, symbol, cfg, fold.oos_start, fold.oos_end)
            fold_results.append(
                FoldResult(
                    symbol=symbol,
                    variant=variant,
                    fold=fold.index,
                    is_metrics=is_m,
                    oos_metrics=oos_m,
                )
            )

        per_symbol[symbol] = {
            "status": "OK",
            "folds": fold_results,
            "summary": _summarize_symbol(fold_results),
        }

    # PR 1 verdict: always BLOCKED. The acceptance gate (A.5) and the
    # composite ranking (A.6) need the grid search infrastructure that PR 2
    # introduces. Until then, nothing can earn a PASS, by design.
    verdict = VERDICT_BLOCKED
    verdict_reason = (
        "Phase 11 acceptance gate not yet implemented "
        "(deferred to phase11/pr3); orchestrator runs default params only."
    )

    return {
        "variant": variant,
        "n_folds": splitter.n_folds,
        "warmup_bars": splitter.warmup_bars,
        "per_symbol": per_symbol,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "ranking": _composite_ranking(per_symbol),
    }


def _summarize_symbol(folds: list[FoldResult]) -> dict:
    """Per-symbol fold summary used by the verdict report."""
    if not folds:
        return {}
    oos_pfs = [f.oos_pf for f in folds]
    oos_sharpes = [f.oos_sharpe for f in folds]
    oos_dds = [f.oos_max_dd_pct for f in folds]
    degrade = [f.is_to_oos_sharpe_degradation_pct for f in folds]
    return {
        "median_oos_pf": _median(oos_pfs),
        "worst_fold_oos_pf": min(oos_pfs),
        "median_oos_sharpe": _median(oos_sharpes),
        "max_oos_dd_pct": max(oos_dds),
        "max_is_to_oos_sharpe_degradation_pct": max(degrade),
        "total_oos_trades": sum(f.oos_trades for f in folds),
        "min_fold_oos_trades": min(f.oos_trades for f in folds),
    }


def _composite_ranking(per_symbol: dict) -> list[dict]:
    """Composite-ranking scaffold per Amendment A § A.6.

    With only one variant in PR 1 this returns a one-row table per symbol;
    PR 2's grid search will produce many rows that this function will sort.
    Sort order (priority): median OOS PF DESC, worst-fold OOS PF DESC,
    median OOS Sharpe DESC, max DD ASC.
    """
    rows: list[dict] = []
    for symbol, payload in per_symbol.items():
        if payload.get("status") != "OK":
            continue
        s = payload["summary"]
        rows.append({
            "symbol": symbol,
            "median_oos_pf": s["median_oos_pf"],
            "worst_fold_oos_pf": s["worst_fold_oos_pf"],
            "median_oos_sharpe": s["median_oos_sharpe"],
            "max_oos_dd_pct": s["max_oos_dd_pct"],
            "total_oos_trades": s["total_oos_trades"],
        })
    rows.sort(
        key=lambda r: (
            -r["median_oos_pf"],
            -r["worst_fold_oos_pf"],
            -r["median_oos_sharpe"],
            r["max_oos_dd_pct"],
        )
    )
    return rows


def _median(values: Iterable[float]) -> float:
    arr = sorted(values)
    n = len(arr)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return float(arr[mid])
    return float((arr[mid - 1] + arr[mid]) / 2.0)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_orchestrator_markdown(report: dict) -> str:
    """Render a human-readable Phase 11 orchestrator report."""
    lines: list[str] = []
    lines.append("# Phase 11 — Walk-Forward Orchestrator (PR 1)")
    lines.append("")
    lines.append(f"- variant: `{report['variant']}`")
    lines.append(f"- n_folds: `{report['n_folds']}`")
    lines.append(f"- warmup_bars: `{report['warmup_bars']}`")
    lines.append(f"- verdict: **{report['verdict']}**")
    lines.append(f"- reason: {report['verdict_reason']}")
    lines.append("")
    lines.append("> Runtime mode: **BACKTEST_ONLY**. No live trading. "
                 "This report cannot toggle any live-trading flag.")
    lines.append("")
    lines.append("## Per-symbol fold detail")
    lines.append("")
    for symbol, payload in report["per_symbol"].items():
        lines.append(f"### {symbol}")
        if payload.get("status") != "OK":
            lines.append(f"- status: `{payload.get('status')}`")
            lines.append(f"- reason: {payload.get('reason', '')}")
            lines.append("")
            continue
        s = payload["summary"]
        lines.append(
            "| Fold | IS Sharpe | OOS Sharpe | OOS PF | OOS trades | "
            "OOS MaxDD% | IS→OOS deg % |"
        )
        lines.append(
            "|-----:|----------:|-----------:|-------:|-----------:|"
            "-----------:|-------------:|"
        )
        for f in payload["folds"]:
            lines.append(
                f"| {f.fold} | {f.is_sharpe:.3f} | {f.oos_sharpe:.3f} | "
                f"{f.oos_pf:.3f} | {f.oos_trades} | "
                f"{f.oos_max_dd_pct:.2f} | "
                f"{f.is_to_oos_sharpe_degradation_pct:.1f} |"
            )
        lines.append("")
        lines.append(
            f"- median OOS PF: **{s['median_oos_pf']:.3f}** | "
            f"worst-fold OOS PF: **{s['worst_fold_oos_pf']:.3f}** | "
            f"median OOS Sharpe: **{s['median_oos_sharpe']:.3f}** | "
            f"max OOS DD: **{s['max_oos_dd_pct']:.2f}%** | "
            f"total OOS trades: **{s['total_oos_trades']}** | "
            f"min fold OOS trades: **{s['min_fold_oos_trades']}**"
        )
        lines.append("")
    lines.append("## Composite ranking (Amendment A § A.6)")
    lines.append("")
    lines.append(
        "Sorted by: median OOS PF → worst-fold OOS PF → median OOS Sharpe "
        "→ max DD. With one variant in PR 1, this is a per-symbol table; "
        "PR 2's grid search will expand it across parameter combinations."
    )
    lines.append("")
    if not report["ranking"]:
        lines.append("_no rankable rows_")
    else:
        lines.append(
            "| Symbol | Median OOS PF | Worst-fold OOS PF | "
            "Median OOS Sharpe | Max OOS DD% | Total OOS trades |"
        )
        lines.append(
            "|--------|--------------:|------------------:|"
            "------------------:|------------:|-----------------:|"
        )
        for r in report["ranking"]:
            lines.append(
                f"| {r['symbol']} | {r['median_oos_pf']:.3f} | "
                f"{r['worst_fold_oos_pf']:.3f} | "
                f"{r['median_oos_sharpe']:.3f} | "
                f"{r['max_oos_dd_pct']:.2f} | {r['total_oos_trades']} |"
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Source: `src/phase11_orchestrator.py` (PR 1 of N). "
                 "Acceptance gate, grid search, Bonferroni reporting, and "
                 "primary/control split are scheduled for later PRs per "
                 "`docs/phase11_design.md` Amendment A.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_symbols(data_dir: Path, symbols: Iterable[str]) -> dict[str, pd.DataFrame]:
    """Load symbol CSVs from ``data_dir`` (gitignored). Skip missing files."""
    by_symbol: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        path = data_dir / f"{sym.lower()}_1d.csv"
        if not path.exists():
            continue
        by_symbol[sym] = _load_csv(path)
    return by_symbol


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 11 — walk-forward orchestrator (PR 1)"
    )
    parser.add_argument("--data-dir", default="data/raw",
                        help="Directory containing <symbol>_1d.csv files")
    parser.add_argument(
        "--symbols",
        default=",".join(PRIMARY_SYMBOLS + CONTROL_SYMBOLS),
        help="Comma-separated symbols to evaluate",
    )
    parser.add_argument("--variant", default="V0", choices=list(PHASE10_VARIANTS))
    parser.add_argument("--n-folds", type=int, default=DEFAULT_N_FOLDS)
    parser.add_argument("--warmup-bars", type=int, default=DEFAULT_WARMUP_BARS)
    parser.add_argument(
        "--output",
        default="reports/phase11_orchestrator.md",
        help="Markdown output path",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional JSON dump of the report (folds serialized as dicts).",
    )
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    by_symbol = _load_symbols(data_dir, symbols)
    if not by_symbol:
        print(
            f"No symbol CSVs found in {data_dir}. "
            "Run `python -m src.phase10_data_downloader --years 20` first."
        )
        # Still emit an empty report so the pipeline can run.
        report = {
            "variant": args.variant,
            "n_folds": args.n_folds,
            "warmup_bars": args.warmup_bars,
            "per_symbol": {},
            "verdict": VERDICT_BLOCKED,
            "verdict_reason": "no input data",
            "ranking": [],
        }
    else:
        splitter = Phase11Splitter(
            n_folds=args.n_folds, warmup_bars=args.warmup_bars
        )
        report = run_orchestrator(
            by_symbol, variant=args.variant, splitter=splitter
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_orchestrator_markdown(report), encoding="utf-8")
    print(f"Wrote {out_path}")

    if args.json_output:
        json_path = Path(args.json_output)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = _serialize_for_json(report)
        json_path.write_text(json.dumps(serializable, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {json_path}")
    return 0


def _serialize_for_json(report: dict) -> dict:
    out = {**report, "per_symbol": {}}
    for sym, payload in report["per_symbol"].items():
        if payload.get("status") != "OK":
            out["per_symbol"][sym] = payload
            continue
        out["per_symbol"][sym] = {
            "status": payload["status"],
            "summary": payload["summary"],
            "folds": [
                {
                    "symbol": f.symbol,
                    "variant": f.variant,
                    "fold": f.fold,
                    "is_metrics": f.is_metrics,
                    "oos_metrics": f.oos_metrics,
                    "is_sharpe": f.is_sharpe,
                    "oos_sharpe": f.oos_sharpe,
                    "oos_pf": f.oos_pf,
                    "oos_trades": f.oos_trades,
                    "oos_max_dd_pct": f.oos_max_dd_pct,
                    "is_to_oos_sharpe_degradation_pct":
                        f.is_to_oos_sharpe_degradation_pct,
                }
                for f in payload["folds"]
            ],
        }
    return out


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

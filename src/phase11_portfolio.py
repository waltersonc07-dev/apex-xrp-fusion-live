"""
Phase 11 — Primary/control portfolio aggregation (PR 4).

Implements Amendment A § A.4 + § A.5.6 + § A.5.7:

  * Aggregate fold-level metrics across the three primary symbols
    (EURUSD, GBPUSD, XAUUSD) into one portfolio per combo. The
    per-symbol acceptance gate (PR 3) is necessary but not sufficient;
    the portfolio gate is what actually decides PASS/BLOCK at the
    combo level.
  * Per-pair net-profit cap: if any single primary symbol accounts
    for more than 40% of the absolute total OOS net profit, the
    combo is over-concentrated and the portfolio verdict is BLOCKED
    regardless of how well it scores in aggregate.
  * Control symbol (USDJPY) is reported alongside but does NOT block
    a primary PASS unless the control failure is catastrophic
    (per-fold OOS PF < 0.5 in 3 of 5 folds), in which case the
    portfolio MICRO_LIVE label is downgraded to WATCH.

This module reuses the structural thresholds and verdict labels from
``src.phase11_gate`` — same gate logic, run on portfolio-level
aggregated metrics. The per-symbol PR 3 columns in
``reports/phase11_search.csv`` are not changed; the portfolio output
goes to a SEPARATE CSV (``reports/phase11_portfolio.csv``) and a
separate Markdown report.

PR 4 still ships WITHOUT:
  * Bayesian posterior intervals (PR 5).

This module does not import or touch ``validation_gate``,
``risk_engine``, ``webhook_server``, or ``exchange_client``. Runtime
stays ``BACKTEST_ONLY``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from .phase11_bayesian import PosteriorPF, posterior_for_portfolio
from .phase11_gate import (
    GateResult,
    MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT,
    MIN_FOLDS_WITH_OOS_PF_GT_1,
    MIN_FOLD_OOS_TRADES,
    MIN_MEDIAN_OOS_PF,
    MIN_MEDIAN_OOS_SHARPE,
    MIN_TOTAL_OOS_TRADES,
    MIN_WORST_FOLD_OOS_PF_FOR_MICRO_LIVE,
    SIGNIFICANCE_ALPHA,
    VERDICT_BLOCKED,
    VERDICT_MICRO_LIVE_CANDIDATE,
    VERDICT_VALIDATED_RESEARCH_CANDIDATE,
    VERDICT_WATCH,
    _isfinite,
    bonferroni_adjust,
    one_sided_t_pvalue,
)


# Amendment A § A.5.7: per-pair concentration cap.
MAX_PER_PAIR_NET_PROFIT_SHARE: float = 0.40  # 40 %


# Amendment A § A.4: control-failure threshold for downgrading
# MICRO_LIVE_CANDIDATE -> WATCH. We use 3-of-5 folds with OOS PF < 0.5.
CONTROL_CATASTROPHIC_PF_BAR: float = 0.50
CONTROL_CATASTROPHIC_FOLD_COUNT: int = 3


# Amendment A primary / control split (also exported in
# ``src.phase10_fx_gold_daily`` but re-declared here for clarity and
# to avoid cross-coupling).
PRIMARY_PORTFOLIO_SYMBOLS: tuple[str, ...] = ("EURUSD", "GBPUSD", "XAUUSD")
CONTROL_PORTFOLIO_SYMBOLS: tuple[str, ...] = ("USDJPY",)


@dataclass(frozen=True)
class PortfolioFold:
    """Aggregated fold across primary symbols for a single combo."""
    fold: int
    oos_pf: float
    oos_sharpe: float
    oos_trades: int
    oos_max_dd_pct: float
    is_to_oos_sharpe_degradation_pct: float
    # Net profit per primary symbol within this fold. Used by the
    # per-pair concentration cap.
    net_profit_by_symbol: dict[str, float]


@dataclass(frozen=True)
class PortfolioSummary:
    """Combo-level portfolio summary across all primary folds."""
    median_oos_pf: float
    worst_fold_oos_pf: float
    median_oos_sharpe: float
    max_oos_dd_pct: float
    max_is_to_oos_sharpe_degradation_pct: float
    total_oos_trades: int
    min_fold_oos_trades: int
    folds_with_oos_pf_gt_1: int
    # Per-symbol absolute net-profit share within this combo's primary
    # portfolio. Sums to 1.0 when total |net profit| > 0.
    net_profit_share_by_symbol: dict[str, float]
    max_per_pair_net_profit_share: float
    # Control diagnostics. Empty when no control rows were provided.
    control_catastrophic: bool
    control_folds_below_bar: dict[str, int]


@dataclass(frozen=True)
class PortfolioVerdict:
    """Per-combo portfolio gate output."""
    combo_key: str
    variant: str
    params: dict
    status: str                       # "OK" or "INSUFFICIENT_DATA"
    n_primary_folds: int              # number of aggregated folds (0 if blocked)
    summary: PortfolioSummary
    gate: GateResult
    # Post-gate downgrade applied for control catastrophe / concentration.
    downgrade_reasons: tuple[str, ...]
    # Optional Bayesian posterior on portfolio OOS PF (PR 5). None when
    # the Bayesian layer is toggled off via build_portfolio_verdicts.
    posterior_pf: PosteriorPF | None = None


# ---------------------------------------------------------------------------
# Aggregation primitives
# ---------------------------------------------------------------------------


def _median(xs: Sequence[float]) -> float:
    arr = sorted(float(x) for x in xs if _isfinite(x))
    if not arr:
        return 0.0
    n = len(arr)
    mid = n // 2
    if n % 2 == 1:
        return arr[mid]
    return 0.5 * (arr[mid - 1] + arr[mid])


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0.0 or not _isfinite(denominator):
        return 0.0
    return numerator / denominator


def aggregate_portfolio_folds(
    primary_per_symbol_folds: dict[str, Sequence[dict]],
) -> list[PortfolioFold]:
    """Aggregate per-symbol fold-level payloads into portfolio folds.

    Aggregation rules (Amendment A § A.4):
      * Equal-weight per symbol within a fold.
      * Portfolio fold OOS PF: sum of gross profits across symbols /
        |sum of gross losses across symbols|. We use ``oos_metrics``
        keys ``gross_profit`` and ``gross_loss`` when present; otherwise
        we fall back to ``net_profit`` and a coarse PF reconstruction.
      * Portfolio fold OOS Sharpe: simple mean of per-symbol fold
        Sharpes (equal weight). Approximation of equal-vol weighting
        since we don't have the per-bar returns at this layer.
      * Portfolio fold trades = sum of per-symbol fold trades.
      * Portfolio fold max DD% = max of per-symbol fold DD%.
      * Portfolio IS->OOS Sharpe degradation = max across primary
        symbols (worst-case carries).
    """
    # Align folds by index. All primary symbols are expected to have
    # the same fold count from the same splitter; if not, we take the
    # min length (defensive).
    if not primary_per_symbol_folds:
        return []
    fold_counts = [len(v) for v in primary_per_symbol_folds.values()]
    n_folds = min(fold_counts) if fold_counts else 0
    out: list[PortfolioFold] = []
    for i in range(n_folds):
        gross_profit_sum = 0.0
        gross_loss_sum = 0.0
        sharpes: list[float] = []
        trades = 0
        dds: list[float] = []
        degrades: list[float] = []
        net_by_sym: dict[str, float] = {}
        for sym, folds in primary_per_symbol_folds.items():
            f = folds[i] if i < len(folds) else None
            if f is None:
                continue
            m = f.get("oos_metrics") or {}
            gp = float(m.get("gross_profit", 0.0) or 0.0)
            gl = float(m.get("gross_loss", 0.0) or 0.0)
            # gross_loss is reported as a positive number by phase10;
            # if it's negative (other convention) take abs.
            gl = abs(gl)
            if gp == 0.0 and gl == 0.0:
                # Fallback: reconstruct from net_profit + reported PF.
                np = float(m.get("net_profit", 0.0) or 0.0)
                pf = f.get("oos_pf")
                pf = float(pf) if pf is not None and _isfinite(float(pf)) else 0.0
                if pf > 0.0 and pf != 1.0 and np != 0.0:
                    gross_profit_sum += max(np, 0.0)
                    gross_loss_sum += abs(min(np, 0.0))
                else:
                    gross_profit_sum += max(np, 0.0)
                    gross_loss_sum += abs(min(np, 0.0))
            else:
                gross_profit_sum += gp
                gross_loss_sum += gl
            s = f.get("oos_sharpe")
            if s is not None:
                try:
                    sharpes.append(float(s))
                except (TypeError, ValueError):
                    pass
            try:
                trades += int(f.get("oos_trades", 0) or 0)
            except (TypeError, ValueError):
                pass
            dd = f.get("oos_max_dd_pct")
            if dd is not None:
                try:
                    dds.append(float(dd))
                except (TypeError, ValueError):
                    pass
            deg = f.get("is_to_oos_sharpe_degradation_pct")
            if deg is not None:
                try:
                    degrades.append(float(deg))
                except (TypeError, ValueError):
                    pass
            net_by_sym[sym] = float(m.get("net_profit", 0.0) or 0.0)

        if gross_loss_sum > 0.0:
            pf = gross_profit_sum / gross_loss_sum
        elif gross_profit_sum > 0.0:
            pf = math.inf
        else:
            pf = 0.0
        # Cap to a finite display value (matches phase10 convention).
        if not _isfinite(pf):
            pf = 999.0
        portfolio_sharpe = (sum(sharpes) / len(sharpes)) if sharpes else 0.0
        portfolio_dd = max(dds) if dds else 0.0
        portfolio_deg = max(degrades) if degrades else 0.0
        out.append(PortfolioFold(
            fold=i,
            oos_pf=float(pf),
            oos_sharpe=float(portfolio_sharpe),
            oos_trades=int(trades),
            oos_max_dd_pct=float(portfolio_dd),
            is_to_oos_sharpe_degradation_pct=float(portfolio_deg),
            net_profit_by_symbol=net_by_sym,
        ))
    return out


def summarize_portfolio(
    folds: Sequence[PortfolioFold],
    control_folds: dict[str, Sequence[dict]] | None = None,
) -> PortfolioSummary:
    """Combo-level summary across portfolio folds + control diagnostics."""
    if not folds:
        return PortfolioSummary(
            median_oos_pf=0.0,
            worst_fold_oos_pf=0.0,
            median_oos_sharpe=0.0,
            max_oos_dd_pct=0.0,
            max_is_to_oos_sharpe_degradation_pct=0.0,
            total_oos_trades=0,
            min_fold_oos_trades=0,
            folds_with_oos_pf_gt_1=0,
            net_profit_share_by_symbol={},
            max_per_pair_net_profit_share=0.0,
            control_catastrophic=False,
            control_folds_below_bar={},
        )

    pfs = [f.oos_pf for f in folds]
    sharpes = [f.oos_sharpe for f in folds]
    median_pf = _median(pfs)
    worst_pf = min(pfs)
    median_sharpe = _median(sharpes)
    max_dd = max(f.oos_max_dd_pct for f in folds)
    max_deg = max(f.is_to_oos_sharpe_degradation_pct for f in folds)
    total_trades = sum(f.oos_trades for f in folds)
    min_fold_trades = min(f.oos_trades for f in folds)
    folds_above_one = sum(1 for pf in pfs if pf > 1.0)

    # Net-profit share per symbol over all folds. We use absolute net
    # profit so a symbol that lost a lot but was offset by another
    # symbol's gain still counts as concentration.
    abs_by_sym: dict[str, float] = {}
    for f in folds:
        for sym, np in f.net_profit_by_symbol.items():
            abs_by_sym[sym] = abs_by_sym.get(sym, 0.0) + abs(float(np))
    total_abs = sum(abs_by_sym.values())
    share_by_sym = {
        sym: _safe_div(v, total_abs) for sym, v in abs_by_sym.items()
    } if total_abs > 0.0 else {sym: 0.0 for sym in abs_by_sym}
    max_share = max(share_by_sym.values(), default=0.0)

    # Control catastrophe (Amendment A § A.4): per-control fold OOS PF
    # < 0.5 in 3 of 5 folds for any control symbol.
    control_folds = control_folds or {}
    folds_below_bar: dict[str, int] = {}
    catastrophic = False
    for sym, sym_folds in control_folds.items():
        cnt = 0
        for f in sym_folds:
            pf = f.get("oos_pf")
            try:
                if pf is not None and float(pf) < CONTROL_CATASTROPHIC_PF_BAR:
                    cnt += 1
            except (TypeError, ValueError):
                continue
        folds_below_bar[sym] = cnt
        if cnt >= CONTROL_CATASTROPHIC_FOLD_COUNT:
            catastrophic = True

    return PortfolioSummary(
        median_oos_pf=float(median_pf),
        worst_fold_oos_pf=float(worst_pf),
        median_oos_sharpe=float(median_sharpe),
        max_oos_dd_pct=float(max_dd),
        max_is_to_oos_sharpe_degradation_pct=float(max_deg),
        total_oos_trades=int(total_trades),
        min_fold_oos_trades=int(min_fold_trades),
        folds_with_oos_pf_gt_1=int(folds_above_one),
        net_profit_share_by_symbol=share_by_sym,
        max_per_pair_net_profit_share=float(max_share),
        control_catastrophic=catastrophic,
        control_folds_below_bar=folds_below_bar,
    )


# ---------------------------------------------------------------------------
# Portfolio gate
# ---------------------------------------------------------------------------


def evaluate_portfolio_gate(
    *,
    summary: PortfolioSummary,
    folds: Sequence[PortfolioFold],
    n_tested: int,
) -> tuple[GateResult, tuple[str, ...]]:
    """Apply the acceptance gate to the aggregated portfolio.

    Returns the gate result plus a tuple of post-gate downgrade reasons
    (control catastrophe + per-pair concentration). The gate's verdict
    has already been downgraded to reflect these reasons.
    """
    # Run the shared structural gate logic against the portfolio
    # summary. We re-implement the body here (rather than calling
    # phase11_gate.evaluate_gate) because (a) PortfolioSummary fields
    # differ from per-symbol summary, and (b) the portfolio gate also
    # applies the concentration cap and control downgrade.
    sharpes = [f.oos_sharpe for f in folds]
    raw_p = one_sided_t_pvalue(sharpes)
    adj_p = bonferroni_adjust(raw_p, n_tested)
    survives_raw = raw_p < SIGNIFICANCE_ALPHA
    survives_bonferroni = adj_p < SIGNIFICANCE_ALPHA

    if not folds:
        return GateResult(
            raw_p=1.0,
            bonferroni_p=1.0,
            n_tested=n_tested,
            survives_raw=False,
            survives_bonferroni=False,
            verdict=VERDICT_BLOCKED,
            reason="no aggregated folds",
        ), ()

    failed: list[str] = []
    if summary.min_fold_oos_trades < MIN_FOLD_OOS_TRADES:
        failed.append(
            f"portfolio.min_fold_oos_trades={summary.min_fold_oos_trades} "
            f"< {MIN_FOLD_OOS_TRADES}"
        )
    if summary.total_oos_trades < MIN_TOTAL_OOS_TRADES:
        failed.append(
            f"portfolio.total_oos_trades={summary.total_oos_trades} "
            f"< {MIN_TOTAL_OOS_TRADES}"
        )
    if summary.median_oos_pf < MIN_MEDIAN_OOS_PF:
        failed.append(
            f"portfolio.median_oos_pf={summary.median_oos_pf:.3f} "
            f"< {MIN_MEDIAN_OOS_PF:.2f}"
        )
    if summary.median_oos_sharpe < MIN_MEDIAN_OOS_SHARPE:
        failed.append(
            f"portfolio.median_oos_sharpe={summary.median_oos_sharpe:.3f} "
            f"< {MIN_MEDIAN_OOS_SHARPE:.2f}"
        )
    if summary.folds_with_oos_pf_gt_1 < MIN_FOLDS_WITH_OOS_PF_GT_1:
        failed.append(
            f"portfolio.folds_with_oos_pf>1="
            f"{summary.folds_with_oos_pf_gt_1} "
            f"< {MIN_FOLDS_WITH_OOS_PF_GT_1}"
        )
    if summary.max_is_to_oos_sharpe_degradation_pct > \
            MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT:
        failed.append(
            "portfolio.max_is_to_oos_sharpe_degradation_pct="
            f"{summary.max_is_to_oos_sharpe_degradation_pct:.1f}% "
            f"> {MAX_IS_TO_OOS_SHARPE_DEGRADATION_PCT:.0f}%"
        )

    # Per-pair concentration cap (Amendment A § A.5.7).
    concentration_block = False
    if summary.max_per_pair_net_profit_share > MAX_PER_PAIR_NET_PROFIT_SHARE:
        concentration_block = True
        worst_sym = max(
            summary.net_profit_share_by_symbol.items(),
            key=lambda kv: kv[1], default=("?", 0.0),
        )
        failed.append(
            "portfolio.max_per_pair_net_profit_share="
            f"{summary.max_per_pair_net_profit_share*100:.1f}% "
            f"(worst: {worst_sym[0]}) "
            f"> {MAX_PER_PAIR_NET_PROFIT_SHARE*100:.0f}%"
        )

    if failed:
        return GateResult(
            raw_p=raw_p,
            bonferroni_p=adj_p,
            n_tested=n_tested,
            survives_raw=survives_raw,
            survives_bonferroni=survives_bonferroni,
            verdict=VERDICT_BLOCKED,
            reason="; ".join(failed),
        ), ()

    # Structural pass. Decide label, then apply control downgrade.
    if not survives_bonferroni:
        gate = GateResult(
            raw_p=raw_p, bonferroni_p=adj_p, n_tested=n_tested,
            survives_raw=survives_raw, survives_bonferroni=False,
            verdict=VERDICT_WATCH,
            reason=(
                f"portfolio structural pass; bonferroni_p={adj_p:.4f} "
                f">= {SIGNIFICANCE_ALPHA}"
            ),
        )
    elif summary.worst_fold_oos_pf < MIN_WORST_FOLD_OOS_PF_FOR_MICRO_LIVE:
        gate = GateResult(
            raw_p=raw_p, bonferroni_p=adj_p, n_tested=n_tested,
            survives_raw=survives_raw, survives_bonferroni=True,
            verdict=VERDICT_VALIDATED_RESEARCH_CANDIDATE,
            reason=(
                f"portfolio gate + bonferroni pass; "
                f"worst_fold_oos_pf={summary.worst_fold_oos_pf:.3f} "
                f"< {MIN_WORST_FOLD_OOS_PF_FOR_MICRO_LIVE:.2f} "
                "blocks MICRO_LIVE label"
            ),
        )
    else:
        gate = GateResult(
            raw_p=raw_p, bonferroni_p=adj_p, n_tested=n_tested,
            survives_raw=survives_raw, survives_bonferroni=True,
            verdict=VERDICT_MICRO_LIVE_CANDIDATE,
            reason=(
                "portfolio: all structural + bonferroni + worst-fold PF "
                ">= 1.0. Manual owner approval required before any live "
                "trading. Runtime stays BACKTEST_ONLY."
            ),
        )

    # Control downgrade (Amendment A § A.4).
    downgrades: list[str] = []
    if summary.control_catastrophic and gate.verdict == VERDICT_MICRO_LIVE_CANDIDATE:
        sym_str = ", ".join(
            f"{s}={c} folds<{CONTROL_CATASTROPHIC_PF_BAR}"
            for s, c in summary.control_folds_below_bar.items()
            if c >= CONTROL_CATASTROPHIC_FOLD_COUNT
        )
        gate = GateResult(
            raw_p=gate.raw_p,
            bonferroni_p=gate.bonferroni_p,
            n_tested=gate.n_tested,
            survives_raw=gate.survives_raw,
            survives_bonferroni=gate.survives_bonferroni,
            verdict=VERDICT_WATCH,
            reason=(
                gate.reason + f" | downgraded to WATCH: control "
                f"catastrophic failure ({sym_str})"
            ),
        )
        downgrades.append(f"control catastrophic: {sym_str}")

    return gate, tuple(downgrades)


# ---------------------------------------------------------------------------
# Per-combo portfolio assembly
# ---------------------------------------------------------------------------


def build_portfolio_verdicts(
    gated_rows: Iterable,                # list[SearchRow] from phase11_search
    n_tested: int,
    primary_symbols: tuple[str, ...] = PRIMARY_PORTFOLIO_SYMBOLS,
    control_symbols: tuple[str, ...] = CONTROL_PORTFOLIO_SYMBOLS,
    include_posterior: bool = True,      # PR 5 toggle
) -> list[PortfolioVerdict]:
    """Group ``SearchRow`` rows by combo and emit a portfolio verdict.

    A combo's portfolio is BLOCKED with status INSUFFICIENT_DATA when
    any primary symbol is missing OR has status != "OK".
    """
    # Group rows by combo_key while preserving variant + params.
    by_combo: dict[str, dict] = {}
    for r in gated_rows:
        bucket = by_combo.setdefault(r.combo_key, {
            "variant": r.variant,
            "params": dict(r.params),
            "by_symbol": {},
        })
        bucket["by_symbol"][r.symbol] = r

    out: list[PortfolioVerdict] = []
    for combo_key, bucket in by_combo.items():
        by_sym = bucket["by_symbol"]
        primary_ok = all(
            sym in by_sym and by_sym[sym].status == "OK"
            for sym in primary_symbols
        )
        if not primary_ok:
            # Empty / unusable portfolio. Emit a BLOCKED verdict so
            # downstream readers see every combo.
            empty_summary = summarize_portfolio([], control_folds=None)
            gate = GateResult(
                raw_p=1.0, bonferroni_p=1.0, n_tested=n_tested,
                survives_raw=False, survives_bonferroni=False,
                verdict=VERDICT_BLOCKED,
                reason="one or more primary symbols missing or INSUFFICIENT_DATA",
            )
            out.append(PortfolioVerdict(
                combo_key=combo_key,
                variant=bucket["variant"],
                params=bucket["params"],
                status="INSUFFICIENT_DATA",
                n_primary_folds=0,
                summary=empty_summary,
                gate=gate,
                downgrade_reasons=(),
                posterior_pf=None,
            ))
            continue

        primary_folds = {
            sym: list(by_sym[sym].folds) for sym in primary_symbols
        }
        control_folds = {
            sym: list(by_sym[sym].folds)
            for sym in control_symbols
            if sym in by_sym and by_sym[sym].status == "OK"
        }
        folds = aggregate_portfolio_folds(primary_folds)
        summary = summarize_portfolio(folds, control_folds=control_folds)
        gate, downgrades = evaluate_portfolio_gate(
            summary=summary, folds=folds, n_tested=n_tested,
        )
        posterior = posterior_for_portfolio(folds) if include_posterior else None
        out.append(PortfolioVerdict(
            combo_key=combo_key,
            variant=bucket["variant"],
            params=bucket["params"],
            status="OK",
            n_primary_folds=len(folds),
            summary=summary,
            gate=gate,
            downgrade_reasons=downgrades,
            posterior_pf=posterior,
        ))

    # Sort deterministically for stable CSVs.
    out.sort(key=lambda v: v.combo_key)
    return out


# ---------------------------------------------------------------------------
# CSV / Markdown output
# ---------------------------------------------------------------------------


# Locked column order for the portfolio CSV. PR 5 appends posterior
# columns at the end. Future PRs may also append but must not reorder
# or rename. The lock test in tests/test_phase11_portfolio.py enforces
# the existing prefix.
PORTFOLIO_CSV_COLUMNS: tuple[str, ...] = (
    "combo_key",
    "variant",
    "params_json",
    "status",
    "n_primary_folds",
    "median_oos_pf",
    "worst_fold_oos_pf",
    "median_oos_sharpe",
    "max_oos_dd_pct",
    "max_is_to_oos_sharpe_degradation_pct",
    "total_oos_trades",
    "min_fold_oos_trades",
    "folds_with_oos_pf_gt_1",
    "max_per_pair_net_profit_share",
    "net_profit_share_json",
    "control_catastrophic",
    "control_folds_below_bar_json",
    "raw_p",
    "bonferroni_p",
    "n_tested",
    "survives_raw",
    "survives_bonferroni",
    "verdict",
    "gate_reason",
    "downgrade_reasons",
    # ---- PR 5: optional Bayesian posterior --------------------------
    "posterior_pf_p05",
    "posterior_pf_p50",
    "posterior_pf_p95",
    "posterior_pf_prob_gt_1",
)


def _fmt(v: float) -> str:
    try:
        if not _isfinite(float(v)):
            return ""
        return f"{float(v):.6f}"
    except (TypeError, ValueError):
        return ""


def portfolio_verdict_to_csv_row(v: PortfolioVerdict) -> dict:
    import json
    s = v.summary
    g = v.gate
    return {
        "combo_key": v.combo_key,
        "variant": v.variant,
        "params_json": json.dumps(v.params, sort_keys=True),
        "status": v.status,
        "n_primary_folds": str(int(v.n_primary_folds)),
        "median_oos_pf": _fmt(s.median_oos_pf),
        "worst_fold_oos_pf": _fmt(s.worst_fold_oos_pf),
        "median_oos_sharpe": _fmt(s.median_oos_sharpe),
        "max_oos_dd_pct": _fmt(s.max_oos_dd_pct),
        "max_is_to_oos_sharpe_degradation_pct":
            _fmt(s.max_is_to_oos_sharpe_degradation_pct),
        "total_oos_trades": str(int(s.total_oos_trades)),
        "min_fold_oos_trades": str(int(s.min_fold_oos_trades)),
        "folds_with_oos_pf_gt_1": str(int(s.folds_with_oos_pf_gt_1)),
        "max_per_pair_net_profit_share": _fmt(s.max_per_pair_net_profit_share),
        "net_profit_share_json": json.dumps(
            s.net_profit_share_by_symbol, sort_keys=True,
        ),
        "control_catastrophic": "true" if s.control_catastrophic else "false",
        "control_folds_below_bar_json": json.dumps(
            s.control_folds_below_bar, sort_keys=True,
        ),
        "raw_p": _fmt(g.raw_p),
        "bonferroni_p": _fmt(g.bonferroni_p),
        "n_tested": str(int(g.n_tested)),
        "survives_raw": "true" if g.survives_raw else "false",
        "survives_bonferroni": "true" if g.survives_bonferroni else "false",
        "verdict": g.verdict,
        "gate_reason": g.reason,
        "downgrade_reasons": "; ".join(v.downgrade_reasons),
        # PR 5: posterior columns. Empty when Bayesian layer is off.
        "posterior_pf_p05": _fmt(v.posterior_pf.p05) if v.posterior_pf else "",
        "posterior_pf_p50": _fmt(v.posterior_pf.p50) if v.posterior_pf else "",
        "posterior_pf_p95": _fmt(v.posterior_pf.p95) if v.posterior_pf else "",
        "posterior_pf_prob_gt_1":
            _fmt(v.posterior_pf.prob_gt_1) if v.posterior_pf else "",
    }


def write_portfolio_csv(verdicts: Sequence[PortfolioVerdict], path) -> None:
    import csv
    from pathlib import Path as _Path
    p = _Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(PORTFOLIO_CSV_COLUMNS))
        writer.writeheader()
        for v in verdicts:
            writer.writerow(portfolio_verdict_to_csv_row(v))


def render_portfolio_markdown(
    verdicts: Sequence[PortfolioVerdict], n_tested: int,
) -> str:
    counts: dict[str, int] = {}
    for v in verdicts:
        counts[v.gate.verdict] = counts.get(v.gate.verdict, 0) + 1
    lines: list[str] = [
        "# Phase 11 — Portfolio Verdicts (PR 4)",
        "",
        f"- combos scored: **{len(verdicts)}**",
        f"- Bonferroni n_tested: **{n_tested}**",
        f"- primary symbols: " + ", ".join(
            f"`{s}`" for s in PRIMARY_PORTFOLIO_SYMBOLS
        ),
        f"- control symbols: " + ", ".join(
            f"`{s}`" for s in CONTROL_PORTFOLIO_SYMBOLS
        ),
        "",
        "> Runtime mode: **BACKTEST_ONLY**. Even the highest verdict "
        "(`MICRO_LIVE_CANDIDATE_REQUIRES_MANUAL_REVIEW`) does not enable "
        "live trading. Manual owner approval is the only path to live.",
        "",
        "## Verdict counts",
        "",
    ]
    for v, c in sorted(counts.items()):
        lines.append(f"- `{v}`: {c}")
    lines.append("")
    candidates = [
        x for x in verdicts
        if x.gate.verdict in (
            VERDICT_VALIDATED_RESEARCH_CANDIDATE, VERDICT_MICRO_LIVE_CANDIDATE,
        )
    ]
    if candidates:
        lines.append("## Surfaced candidates")
        lines.append("")
        lines.append(
            "| Variant | Combo | Verdict | Median OOS PF | "
            "Worst-fold OOS PF | bonferroni_p | Max per-pair share |"
        )
        lines.append(
            "|---------|-------|---------|--------------:|"
            "------------------:|-------------:|-------------------:|"
        )
        for v in candidates:
            s = v.summary
            g = v.gate
            lines.append(
                f"| {v.variant} | `{v.combo_key}` | {g.verdict} | "
                f"{s.median_oos_pf:.3f} | {s.worst_fold_oos_pf:.3f} | "
                f"{g.bonferroni_p:.4f} | "
                f"{s.max_per_pair_net_profit_share*100:.1f}% |"
            )
        lines.append("")
    return "\n".join(lines)

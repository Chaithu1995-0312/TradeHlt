"""
qualify_interpreter.py — prove the Interpreter chain end-to-end on REAL data.

Plan 4: register a reference interpreter (Moving Average Cross) as a research
Hypothesis via `InterpreterHypothesis`, run it through the UNCHANGED measurement
stack (`HypothesisRunner` → `forward_walk` → M4 `QualificationGate`), and print the
`EdgeReport` + verdict. This is a CHAIN PROOF, not an edge search — the expected
verdict is NOT PROMOTE. Reuses the gate math in `research.qualification` VERBATIM
(evaluate_pre_bh / benjamini_hochberg / finalize) exactly like `qualify_majors.py`.

Thin wrapper: no business logic, no new statistics.

    python scripts/research/qualify_interpreter.py --instrument BNBUSDT --fast 10 --slow 30
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import research.controls            # noqa: F401  — registers the falsification controls
from research.config import ResearchConfig
from research.costs import CostModel
from research.measurement.metrics import EdgeAggregator
from research.qualification import (
    QualConfig, benjamini_hochberg, evaluate_pre_bh, finalize, _net_rrs,
)
from research.registry import HYPOTHESIS_REGISTRY, register_hypothesis
from research.runner import HypothesisRunner
from utils.console_safe import safe_print

from analytics import metrics_oracle as mo
from interpreters.adapter import InterpreterHypothesis
from interpreters.point_and_figure import PointAndFigureInterpreter
from interpreters.reference import MovingAverageCrossInterpreter


def _build_interpreter(name: str, args):
    """Construct the selected reference/research interpreter (frozen configs)."""
    if name == "ma_cross":
        return MovingAverageCrossInterpreter(fast_period=args.fast, slow_period=args.slow)
    if name == "pnf":
        return PointAndFigureInterpreter()        # PNF-v1 frozen config (no sweep)
    raise SystemExit(f"unknown --interpreter '{name}' (choose ma_cross|pnf)")


def _delta_metrics(outcomes, cost, span_months: float) -> dict:
    """Δ-table row for ONE producer, computed from research Outcomes via the INDEPENDENT
    metrics_oracle (nothing frozen is touched). All NET of the 12bps cost model."""
    net = [cost.net_rr(o.rr_achieved, o.signal.entry, o.signal.sl_atr_mult * o.signal.atr)
           for o in outcomes]
    n = len(net)
    # capture/giveback per outcome on the same risk basis (mfe in R = mfe_price / risk_distance)
    caps, gbs = [], []
    for o, r in zip(outcomes, net):
        risk = o.signal.sl_atr_mult * o.signal.atr
        mfe_rr = (o.mfe / risk) if risk > 0 else 0.0
        c = mo.capture_ratio(r, mfe_rr)
        g = mo.giveback(r, mfe_rr)
        if c is not None:
            caps.append(c)
        if g is not None:
            gbs.append(g)
    return {
        "n": n,
        "trades_per_month": round(n / span_months, 4) if span_months > 0 else 0.0,
        "expectancy_rr": round(mo.expectancy_mean(net), 6),
        "avg_rr": round(mo.expectancy_mean(net), 6),         # realized avg RR == E[R] in R-space
        "profit_factor": round(mo.profit_factor(net), 4),
        "max_drawdown_rr": round(mo.max_drawdown_rr(net), 4),
        "median_capture": None if not caps else round(mo.percentile(caps, 50), 4),
        "median_giveback": None if not gbs else round(mo.percentile(gbs, 50), 4),
        "top5_concentration": (lambda v: None if v is None else round(v, 4))(
            mo.top_n_contribution(net, 5)),
    }


def _winning_control(per_by_hyp, control_names, instruments, agg, cost):
    """Highest pooled NET-expectancy control (mirrors qualify_majors._winning_control)."""
    win_name, win_rrs, win_exp = "none", [], float("-inf")
    for name in sorted(control_names):
        per = {i: per_by_hyp[name][i] for i in instruments}
        rrs: list[float] = []
        for outs in per.values():
            rrs.extend(_net_rrs(outs, cost))
        rep = agg.aggregate(name, sorted(instruments),
                            [o for outs in per.values() for o in outs], cost_model=cost)
        if rep.expectancy_rr > win_exp:
            win_name, win_rrs, win_exp = name, rrs, rep.expectancy_rr
    if win_exp == float("-inf"):
        win_name, win_rrs, win_exp = "none", [], 0.0
    return win_name, win_rrs, win_exp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prove the interpreter chain end-to-end.")
    ap.add_argument("--interpreter", default="ma_cross", choices=["ma_cross", "pnf"])
    ap.add_argument("--instrument", default="BNBUSDT")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--fast", type=int, default=10)     # ma_cross only
    ap.add_argument("--slow", type=int, default=30)     # ma_cross only
    ap.add_argument("--observe-preview", type=int, default=5,
                    help="print provenance for the first N interpreter observations")
    args = ap.parse_args(argv)

    inst = args.instrument
    csv_path = str(Path(args.data_dir) / f"{inst}_M15.csv")
    if not Path(csv_path).exists():
        safe_print(f"[qualify_interpreter] data not found: {csv_path}")
        return 2

    # Build + register the candidate (adapter family='interpreter' → NOT a control).
    interp = _build_interpreter(args.interpreter, args)
    candidate = InterpreterHypothesis(interp)
    register_hypothesis(candidate)

    # Config: force apply_signal_defaults=False so the interpreter's OWN SL/TP geometry
    # is exercised end-to-end (SpineHypothesis convention).
    cfg = dataclasses.replace(ResearchConfig.from_file(), apply_signal_defaults=False)
    runner = HypothesisRunner(cfg)
    cost = CostModel(cfg.round_trip_bps)
    agg = EdgeAggregator()
    qcfg = QualConfig.from_research_config(cfg)
    csv_map = {inst: csv_path}

    # ── Chain observability: prove provenance survives interp→reading→adapter ──────
    _chain_observability_preview(interp, csv_path, inst, cfg, args.observe_preview)

    # ── Measure: candidate + controls through the UNCHANGED stack ─────────────────
    control_names = sorted(n for n, h in HYPOTHESIS_REGISTRY.items() if h.family == "control")
    per_by_hyp = {candidate.name: runner.collect(candidate.name, csv_map)}
    for name in control_names:
        per_by_hyp[name] = runner.collect(name, csv_map)

    win_name, win_rrs, win_exp = _winning_control(per_by_hyp, control_names, [inst], agg, cost)
    per = per_by_hyp[candidate.name]
    report = agg.aggregate(candidate.name, [inst],
                           [o for outs in per.values() for o in outs], cost_model=cost)
    state = evaluate_pre_bh(report, per, win_name, win_rrs, win_exp, qcfg, cost)
    bh = benjamini_hochberg({candidate.name: state.p_value} if state.passed_1_to_6 else {},
                            qcfg.significance_alpha)
    final = finalize(state, bh, qcfg)

    # ── Report ────────────────────────────────────────────────────────────────────
    safe_print("=" * 64)
    safe_print(f"  INTERPRETER CHAIN PROOF — {candidate.name} on {inst}")
    safe_print("=" * 64)
    safe_print(f"  n={final.n}  PF={final.profit_factor}  E[R]={final.expectancy_rr:+.4f}  "
               f"win_rate={final.win_rate:.3f}")
    safe_print(f"  winning_control={win_name} (E[R]={win_exp:+.4f})  p={round(state.p_value, 4)}")
    safe_print(f"  VERDICT: {final.verdict}   (a working chain is the win — PROMOTE is NOT expected)")
    if final.reject_reasons:
        safe_print(f"  reject_reasons: {final.reject_reasons[0]}")

    # ── Δ table: candidate vs winning control (independent oracle; shadow report) ──
    span_months = _span_months(csv_path, inst)
    cand_outs = [o for outs in per.values() for o in outs]
    cand_m = _delta_metrics(cand_outs, cost, span_months)
    if win_name != "none":
        ctrl_outs = [o for outs in per_by_hyp[win_name].values() for o in outs]
        ctrl_m = _delta_metrics(ctrl_outs, cost, span_months)
    else:
        ctrl_m = {k: 0.0 for k in cand_m}

    safe_print("-" * 64)
    safe_print(f"  Δ vs winning control ({win_name})   [candidate − control]")
    keys = ["trades_per_month", "expectancy_rr", "avg_rr", "profit_factor",
            "max_drawdown_rr", "median_capture", "median_giveback", "top5_concentration"]
    for k in keys:
        cv, wv = cand_m.get(k), ctrl_m.get(k)
        if cv is None or wv is None:
            safe_print(f"    {k:<20} cand={cv} ctrl={wv}  Δ=NA")
        else:
            safe_print(f"    {k:<20} cand={cv:+.4f} ctrl={wv:+.4f}  Δ={cv - wv:+.4f}")
    safe_print(f"  VERDICT: {final.verdict}   (a working chain + honest Δ is the win — PROMOTE NOT expected)")
    safe_print("=" * 64)
    return 0


def _span_months(csv_path: str, inst: str) -> float:
    """Calendar-month span of the data (for trades/month). Deterministic, from candle ts."""
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(csv_path, inst).stream())
    if len(candles) < 2:
        return 0.0
    days = (candles[-1].timestamp - candles[0].timestamp).total_seconds() / 86400.0
    return days / 30.4375


def _chain_observability_preview(interp, csv_path, inst, cfg, n_preview: int) -> None:
    """Print provenance for the first few interpreter observations that emit events —
    proving trace_id/observation_time/schema_version survive interp→reading."""
    if n_preview <= 0:
        return
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(csv_path, inst).stream())
    for i, c in enumerate(candles):
        c.index = i
    safe_print(f"[chain] first {n_preview} interpreter observations with events:")
    shown = 0
    for i in range(cfg.warmup, len(candles)):
        lo = max(0, i - cfg.window_size + 1)
        reading = interp.observe(candles[lo:i + 1], {}, {"instrument": inst})
        if not reading.events:
            continue
        ev = reading.events[0]
        safe_print(f"  interp={interp.name} schema={reading.schema_version} "
                   f"impl_v={interp.version()} trace={reading.trace_id} "
                   f"obs_time={reading.observation_time} dir={ev.direction.value} "
                   f"conf={ev.confidence:.3f} strength={ev.strength:.3f}")
        shown += 1
        if shown >= n_preview:
            break
    if shown == 0:
        safe_print("  (no cross events in this series)")


if __name__ == "__main__":
    raise SystemExit(main())

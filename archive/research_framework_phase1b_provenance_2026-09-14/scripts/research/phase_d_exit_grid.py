# -*- coding: utf-8 -*-
"""
phase_d_exit_grid.py — Phase D: maximum recoverable expectancy from exit/cost structure (thin CLI).

Holds entries FIXED and sweeps a 42-cell SL/TP grid under the governing intrabar_fixed + 12bps, on
TWO populations across crypto-6: the toy-hypothesis UNIVERSE (power) and the SPINE's executed trades
(relevance). D1 computes the recoverable-value ceilings (structural / perfect-information / reality
gap / utilization) and prints a REGIME banner (ALPHA vs ENGINEERING) ABOVE any grid table, so the
ceiling gates interpretation before a single cell is read. All math reuses research.exit_grid +
research.forensics + forward_walk + CostModel; this wires config → harvest → disk.

Strict success bar: a cell is a lead ONLY if E_IS>0 AND E_OOS>0 AND sign-consistent. Everything else
(lower MaxDD at flat E, cost recovery) is risk/cost ENGINEERING, never alpha. Doctrine: a lead is a
PRE-REGISTERED OOS CANDIDATE, never an edge.

Deterministic JSON body (no wall-clock); manifest separate.
Usage: python scripts/research/phase_d_exit_grid.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
for _p in (str(_ROOT), str(_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research.hypotheses   # noqa: F401,E402  (register hypotheses incl. spine)
from research.config import ResearchConfig                            # noqa: E402
from research.contracts import Signal                                 # noqa: E402
from research.costs import CostModel                                  # noqa: E402
from research.exit_grid import (                                      # noqa: E402
    Entry, ceilings, pool_cells, sweep_instrument, verdict,
)
from research.forensics import (                                      # noqa: E402
    _classify, _expectancy_decomposition, _loss_mechanisms,
)
from research.indicators import atr as research_atr                   # noqa: E402
from research.measurement.forward_walk import forward_walk, horizon_excursion  # noqa: E402
from research.registry import get_hypothesis                          # noqa: E402
from utils.console_safe import safe_print                            # noqa: E402

DEFAULT_CONFIG = "configs/research/research_config_phase_d.json"


def _load_candles(csv: str, instrument: str) -> list:
    from runtime.backtest_v2 import CandleLoader
    candles = list(CandleLoader(csv, instrument).stream())
    for i, c in enumerate(candles):
        c.index = i
    return candles


def _harvest_universe(hyp, candles, warmup: int, window_size: int) -> list[Entry]:
    out: list[Entry] = []
    n = len(candles)
    for i in range(warmup, n):
        lo = max(0, i - window_size + 1)
        window = candles[lo:i + 1]
        for s in hyp.detect(window, {}, {"instrument": "_"}):
            out.append(Entry(entry_index=i, entry=s.entry, direction=s.direction, atr=s.atr))
    return out


def _harvest_spine(instrument: str, candles, atr_period: int, source) -> list[Entry]:
    out: list[Entry] = []
    for idx, se in sorted(source.entries(instrument).items()):
        if idx < 1 or idx >= len(candles):
            continue
        a = research_atr(candles[max(0, idx - atr_period):idx + 1], atr_period)
        if a > 0:
            out.append(Entry(entry_index=idx, entry=se.entry, direction=se.direction, atr=a))
    return out


def _records_from_entries(entries: list[Entry], candles, cost: CostModel, max_forward: int) -> list[dict]:
    """Forensics-shaped per-trade records at the INCUMBENT (sl=1,tp=2) geometry, for the D1 ceilings."""
    recs: list[dict] = []
    for e in entries:
        if e.atr <= 0:
            continue
        future = candles[e.entry_index + 1: e.entry_index + 1 + max_forward]
        if not future:
            continue
        sig = Signal(instrument="_", timestamp=candles[e.entry_index].timestamp, entry_index=e.entry_index,
                     direction=e.direction, entry=e.entry, sl_atr_mult=1.0, tp_atr_mult=2.0, atr=e.atr)
        ib = forward_walk(sig, future, max_forward=max_forward, exit_model="intrabar_fixed")
        co = forward_walk(sig, future, max_forward=max_forward, exit_model="close_only")
        exc = horizon_excursion(sig, future, max_forward=max_forward)
        risk = 1.0 * e.atr
        net_ib = cost.net_rr(ib.rr_achieved, e.entry, risk)
        recs.append({
            "rr_gross_intrabar": ib.rr_achieved, "rr_net_intrabar": round(net_ib, 6),
            "rr_net_close_only": round(cost.net_rr(co.rr_achieved, e.entry, risk), 6),
            "outcome_intrabar": ib.outcome, "outcome_close_only": co.outcome,
            "max_favorable_excursion_r": exc["mfe_r"], "entry": e.entry, "atr": e.atr,
            "damage_source": _classify(ib, co, net_ib),
        })
    return recs


def _run_population(name: str, harvest_fn, instruments, cfg, cost, sl_grid, tp_grid) -> dict:
    es = cfg["entry_sources"]
    mf = int(cfg["forward_walk"]["max_forward"])
    per_inst_grid: dict[str, dict] = {}
    per_inst_n: dict[str, int] = {}
    pooled_records: list[dict] = []
    for inst in instruments:
        csv = str(Path(cfg["universe"]["data_dir"]) / f"{inst}_M15.csv")
        if not Path(csv).exists():
            continue
        candles = _load_candles(csv, inst)
        entries = harvest_fn(inst, candles)
        per_inst_n[inst] = len(entries)
        if not entries:
            continue
        pooled_records.extend(_records_from_entries(entries, candles, cost, mf))
        per_inst_grid[inst] = sweep_instrument(
            entries, candles, sl_grid=sl_grid, tp_grid=tp_grid,
            max_forward=mf, cost=cost, oos_split=float(cfg["oos"]["split"]))
        safe_print(f"  [{name}] {inst}: entries={len(entries)}")
    decomp = _expectancy_decomposition(pooled_records)
    ceil = ceilings(pooled_records, decomp, widest_sl=float(cfg["ceiling"]["widest_sl_for_min_cost"]),
                    bps=float(cfg["costs"]["round_trip_bps"]))
    pooled = pool_cells(per_inst_grid, sl_grid, tp_grid)
    vd = verdict(pooled)
    loss = _loss_mechanisms(pooled_records)
    return {
        "n_total": len(pooled_records), "per_instrument_n": per_inst_n,
        "regime": ceil["regime"], "ceiling": ceil,
        "expectancy_decomposition": decomp,
        "loss_mechanisms_top": loss[:4],
        "grid": pooled, "verdict": vd,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase_d_exit_grid")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--out", default="results/research/phase_d")
    args = parser.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    os.environ["RESEARCH_SPINE_CONFIG"] = args.config   # spine block read by ProductionSpineSource
    instruments = cfg["universe"]["instruments"]
    cost = CostModel(float(cfg["costs"]["round_trip_bps"]))
    sl_grid = list(cfg["grid"]["sl_atr_mults"])
    tp_grid = list(cfg["grid"]["tp_atr_mults"])
    warmup = int(cfg["harness"]["warmup"])
    window = int(cfg["harness"]["window_size"])
    atr_period = int(cfg["entry_sources"]["atr_period"])
    hyp = get_hypothesis(cfg["entry_sources"]["universe_hypothesis"])

    def harvest_universe(inst, candles):
        return _harvest_universe(hyp, candles, warmup, window)

    from research.adapters.spine_signal_source import ProductionSpineSource
    spine_source = ProductionSpineSource()

    def harvest_spine(inst, candles):
        return _harvest_spine(inst, candles, atr_period, spine_source)

    universe = _run_population("universe", harvest_universe, instruments, cfg, cost, sl_grid, tp_grid)
    spine = _run_population("spine", harvest_spine, instruments, cfg, cost, sl_grid, tp_grid)

    report = {
        "phase": "D1+D2",
        "truth_standard": {"exit_model": cfg["forward_walk"]["exit_model"],
                           "round_trip_bps": cfg["costs"]["round_trip_bps"],
                           "max_forward": cfg["forward_walk"]["max_forward"],
                           "oos_split": cfg["oos"]["split"]},
        "grid_axes": {"sl_atr_mults": sl_grid, "tp_atr_mults": tp_grid, "incumbent": [1.0, 2.0]},
        "populations": {"universe": universe, "spine": spine},
        "summary": {
            "universe_regime": universe["regime"],
            "universe_max_recoverable_E": universe["verdict"]["max_recoverable_E"],
            "universe_has_lead": universe["verdict"]["has_lead"],
            "spine_regime": spine["regime"],
            "spine_has_lead": spine["verdict"]["has_lead"],
            "doctrine": "only E>0 AND OOS counts as success; else risk/cost engineering, never alpha",
        },
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "phase_d_exit_grid.json").write_text(
        json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    (out_dir / "phase_d_manifest.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(),
                    "git_commit": _git_commit(), "config": args.config}, sort_keys=True, indent=2),
        encoding="utf-8")
    _print(report)
    safe_print(f"\n-> {out_dir / 'phase_d_exit_grid.json'}")
    return 0


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def _pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _print(report: dict) -> None:
    for pop in ("universe", "spine"):
        p = report["populations"][pop]
        c = p["ceiling"]
        struct = c["structural_upper_bound"]
        perfect = c["perfect_information_upper_bound"]
        v_entries = (None if (struct is None or perfect in (None, 0))
                     else max(0.0, 1.0 - (struct / perfect)) if perfect > 0 else None)
        safe_print(f"\n{'='*70}\nPHASE D — {pop.upper()}  (n={p['n_total']})")
        if c["regime"] == "ALPHA":
            safe_print("REGIME: ALPHA (ceiling positive — grid may search for a realizable fraction)")
        else:
            safe_print("REGIME: ENGINEERING (alpha ceiling non-positive — grid results are "
                       "cost/risk shaping ONLY, never alpha)")
        safe_print(f"  STRUCTURAL UPPER BOUND      : "
                   f"{'n/a' if struct is None else f'{struct:+.4f} R'}")
        safe_print(f"  PERFECT INFORMATION CEILING : "
                   f"{'n/a' if perfect is None else f'{perfect:+.4f} R'}")
        safe_print(f"  REALITY GAP                 : "
                   f"{'n/a' if c['reality_gap'] is None else f'{c['reality_gap']:+.4f} R'}")
        safe_print(f"  CEILING UTILIZATION         : {_pct(c['ceiling_utilization'])}")
        safe_print(f"  INTERPRETATION  value lost to entries: {_pct(v_entries)}  "
                   f"value lost to exits: {'n/a' if v_entries is None else f'{100*(1-v_entries):.0f}%'}")
        d = p["expectancy_decomposition"]
        safe_print(f"  decomposition: E_gross={d.get('expectancy_gross')} "
                   f"E_net={d.get('expectancy_net')} cost_drag={d.get('cost_drag_rr')}")
        vd = p["verdict"]
        safe_print(f"  GRID: incumbent {vd['incumbent_cell']} E_oos={vd['incumbent_expectancy_oos']}  "
                   f"best {vd['best_cell']} E_oos={vd['best_expectancy_oos']}  "
                   f"max_recoverable_E={vd['max_recoverable_E']}")
        safe_print(f"  VERDICT: {'LEAD(S) ' + str(vd['leads']) if vd['has_lead'] else 'NO LEAD'} "
                   f"(success = E>0 IS&OOS + sign-consistent)")
    s = report["summary"]
    safe_print(f"\n{'='*70}\nSUMMARY: universe={s['universe_regime']}/lead={s['universe_has_lead']}  "
               f"spine={s['spine_regime']}/lead={s['spine_has_lead']}")


if __name__ == "__main__":
    raise SystemExit(main())

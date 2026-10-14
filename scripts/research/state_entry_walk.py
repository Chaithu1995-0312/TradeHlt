"""state_entry_walk.py — CRT engine state-transition events as entries (MC-STATEENTRY-XAUUSD-M15-V1).

Answers: at which engine transition events (SWEEP, DISPLACEMENT, EXPANSION, RETEST, the
traded EXECUTION, the refused confirmations) would an entry have carried positive
multi_tp_walk R over 4..480 forward bars, with close-only exits (no intrabar ordering)?

Thin wrapper: the logic is ``src/research/state_entry/``. Research/diagnostic only —
``economic_claims_allowed: false``, no promotion, no G001, no ACTIVE_VERSION change.

Usage (Windows, repo venv):
    venv\\Scripts\\python.exe scripts\\research\\state_entry_walk.py --csv data\\mt5\\XAUUSD_M15.csv
    # reuse an existing run's events instead of re-running the backtest:
    ... --events results\\<run>\\XAUUSD_events.jsonl
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.production_config import get_active_version, get_prod_section  # noqa: E402
from research.costs import xau_measured_cost_model  # noqa: E402
from research.state_entry.evaluate import POSITIVE, evaluate  # noqa: E402
from research.state_entry.extract import bars_from_candles, extract_units, load_events  # noqa: E402
from research.state_entry.walk import Geometry, walk_all  # noqa: E402

CONTRACT_ID = "MC-STATEENTRY-XAUUSD-M15-V1"
_OUT = _ROOT / "results" / "research" / "state_entry" / "mc_stateentry_xauusd_m15_v1"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_backtest(csv_path: Path, instrument: str) -> Path:
    """One unmodified BacktestRunner run of the ACTIVE config; returns its events.jsonl."""
    from config_layer.production_config import load_prod_config_from_registry
    from runtime.backtest_v2 import (BacktestConfig, BacktestRunner, CandleLoader,
                                     MultiInstrumentRunner)

    crt_cfg = load_prod_config_from_registry(get_active_version(), instrument)
    cfg = BacktestConfig.from_prod_config(
        instrument=instrument, crt_config=crt_cfg,
        pip_size=MultiInstrumentRunner.INSTRUMENT_PIP.get(instrument, 0.0001),
        scorer_mode="calibrated", allow_router_crt_config=False, strategy_id="")
    out_dir = Path(tempfile.mkdtemp(prefix="state_entry_bt_"))
    loader = CandleLoader(str(csv_path), instrument)
    BacktestRunner(cfg, csv_path=str(csv_path)).run(loader.stream(), loader.count(),
                                                   output_dir=str(out_dir))
    found = sorted(out_dir.rglob(f"{instrument}_events.jsonl"))
    if not found:
        raise RuntimeError(f"backtest wrote no {instrument}_events.jsonl under {out_dir}")
    return found[0]


def _geometry() -> Geometry:
    crt = get_prod_section("crt_engine")
    return Geometry(
        sl_atr_buffer=float(crt["sl_atr_buffer"]),
        tp1_mult=float(crt["tp1_atr_multiplier"]),
        tp2_mult=float(crt["tp2_atr_multiplier"]),
        fixed_sl_atr_mult=float(get_prod_section("sl_tp_comparison")["legacy_sl_atr_mult"]),
        partial_fraction=float(get_prod_section("execution_planner")["partial_tp_fraction"]),
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--events", type=Path, default=None,
                    help="existing <instrument>_events.jsonl from a run over the SAME csv")
    ap.add_argument("--out", type=Path, default=_OUT)
    args = ap.parse_args(argv)

    from runtime.backtest_v2 import CandleLoader

    active = get_active_version()
    bars = bars_from_candles(CandleLoader(str(args.csv), args.instrument).stream())
    print(f"[ORIENT] ACTIVE_VERSION={active}  csv={args.csv}  rows={len(bars)}  "
          f"{bars[0].timestamp} -> {bars[-1].timestamp}")

    events_path = args.events or _run_backtest(args.csv, args.instrument)
    events = load_events(events_path)
    print(f"[EVENTS] {events_path}  lines={len(events)}")

    units, ext_counts = extract_units(events, bars)
    g = _geometry()
    cost = xau_measured_cost_model()
    rows, walk_drops = walk_all(units, bars, g, cost)
    result = evaluate(rows, bars, g, cost)

    args.out.mkdir(parents=True, exist_ok=True)
    fingerprint = {
        "contract_id": CONTRACT_ID,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "active_version": active,
        "corpus_path": str(args.csv),
        "corpus_sha256": _sha256(args.csv),
        "corpus_rows": len(bars),
        "events_path": str(events_path),
        "events_sha256": _sha256(events_path),
        "n_units": len(units),
        "extract_counts": ext_counts,
        "walk_drops": walk_drops,
        "n_rows": len(rows),
        "geometry": g.__dict__,
        "cost_model": cost.provenance() if hasattr(cost, "provenance") else cost.source,
    }
    (args.out / "population_fingerprint.json").write_text(json.dumps(fingerprint, indent=2, default=str))
    (args.out / "split_manifest.json").write_text(json.dumps(result["split_manifest"], indent=2))
    (args.out / "metrics.json").write_text(json.dumps(result, indent=2, default=str))
    with open(args.out / "rows.csv", "w", newline="", encoding="utf-8") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    print(f"[UNITS] {ext_counts}")
    print(f"[FAMILY] {result['family_size']} cells with train n>=30, BH q={result['bh_q']}")
    print(f"[VERDICTS] {result['verdict_counts']}")
    print("\nPRIMARY (close_only) cells, holdout mean net R  (diagnostic, not evidence of edge):")
    print(f"{'cell':58s} {'trn_n':>6s} {'trn_net':>8s} {'hld_n':>6s} {'hld_net':>8s} "
          f"{'ref_hld':>8s}  verdict")
    for k, c in sorted(result["cells"].items(),
                       key=lambda kv: -(kv[1]["hold_net"]["mean"] or -9e9)):
        tn, hn = c["train_net"], c["hold_net"]
        ref = c["reference_sl_first"]["hold_net_mean"]
        f = lambda v: f"{v:+.3f}" if isinstance(v, (int, float)) else "   n/a"  # noqa: E731
        print(f"{k:58s} {tn['n']:6d} {f(tn['mean']):>8s} {hn['n']:6d} {f(hn['mean']):>8s} "
              f"{f(ref):>8s}  {c['verdict']}")
    n_pos = result["verdict_counts"].get(POSITIVE, 0)
    print(f"\n{n_pos} POSITIVE cell(s). Outputs: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

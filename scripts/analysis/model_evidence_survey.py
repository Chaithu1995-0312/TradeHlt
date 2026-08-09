"""model_evidence_survey.py — OBSERVATION-ONLY survey of the Layer-7 Model Evidence layer.

Question: over a real gate-ON backtest, what does each model actually testify, and how much do
the testimonies vary? EngineRunner already assembles `engine_results` on every scored bar and
logs it (`Collector.log(record)["engines"]`, both the reject and execute paths). This script
wraps that logger call-through — zero behavior change — and rebuilds an EvidenceSet per record.

Method mirrors scripts/analysis/f048_decision_probe.py: the CLI construction path is replicated
verbatim (the F-057 CRTConfig split-brain lives on the programmatic BacktestRunner(cfg) path, so
the production JSON must be loaded the way backtest_v2.main does).

Usage:
    python scripts/analysis/model_evidence_survey.py --csv data/mt5/XAUUSD_M15.csv [--out x.json]

READ-ONLY with respect to src/ and configs/. Results are DESCRIPTIVE (Authority-Ladder Level <= 1):
a distribution of what models said, never a claim that any of it is economically useful.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from features.model_evidence import ModelEvidenceBuilder  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--instrument", default=None,
                    help="defaults to the CSV stem's leading symbol (e.g. XAUUSD from XAUUSD_M15)")
    ap.add_argument("--out", default=None, help="optional JSON dump of the survey")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    instr = args.instrument or csv_path.stem.split("_")[0].upper()

    from config_layer.production_config import PROD_VERSION
    from runtime.backtest_v2 import (
        BacktestConfig, BacktestRunner, CandleLoader, MultiInstrumentRunner,
        load_prod_config_from_registry, _preflight_dataset, bt_log,
    )

    crt_cfg = load_prod_config_from_registry(PROD_VERSION, instr)
    cfg = BacktestConfig.from_prod_config(crt_config=crt_cfg)
    cfg.instrument = instr
    cfg.pip_size = MultiInstrumentRunner.INSTRUMENT_PIP.get(cfg.instrument, 0.0001)
    if not _preflight_dataset(str(csv_path), cfg.instrument, bt_log):
        print("dataset rejected by L3 pre-flight — aborting survey", file=sys.stderr)
        return 1

    evidence_builder = ModelEvidenceBuilder()

    import core.collector as collector_mod

    sets: list = []
    build_errors: Counter = Counter()
    decisions: Counter = Counter()
    reasons: Counter = Counter()
    # Counted, never silently dropped: a zero result must be diagnosable. "no records at all"
    # (run() never fired) and "records carrying no engines dict" are different facts.
    seen_records = 0
    records_without_engines = 0

    _orig_log = collector_mod.Collector.log

    def _capturing_log(self, record, *a, **kw):
        nonlocal seen_records, records_without_engines
        out = _orig_log(self, record, *a, **kw)
        seen_records += 1
        engines = (record or {}).get("engines")
        if not engines:
            records_without_engines += 1
            return out
        decisions[str((record or {}).get("decision", "?"))] += 1
        reasons[str((record or {}).get("reason", "<none>"))] += 1
        try:
            sets.append(evidence_builder.build(engines))
        except Exception as exc:                # contract violation is the finding, not a crash
            build_errors[f"{type(exc).__name__}: {exc}"] += 1
        return out

    collector_mod.Collector.log = _capturing_log
    try:
        loader = CandleLoader(str(csv_path), cfg.instrument)
        runner = BacktestRunner(cfg, csv_path=str(csv_path))
        runner.run(loader.stream(), loader.count(), "results")
    finally:
        collector_mod.Collector.log = _orig_log

    hashes = Counter(es.evidence_hash for es in sets)
    x_bars = sum(1 for es in sets if es.x_markers)

    print("\n" + "=" * 72)
    print(f"MODEL EVIDENCE SURVEY — {instr} — gate-ON")
    print("=" * 72)
    print(f"declared models   : {list(evidence_builder.models)}")
    print(f"producers         : {list(evidence_builder.producers)} -> slots "
          f"{list(evidence_builder.engine_keys)}")
    print(f"collector records : {seen_records} "
          f"({records_without_engines} carried no engines dict = run() did not score that bar)")
    print(f"evidence sets     : {len(sets)}")
    print(f"distinct hashes   : {len(hashes)}")
    print(f"bars w/ X markers : {x_bars}")
    print(f"decisions         : {dict(decisions)}")
    print(f"reasons           : {dict(reasons)}")
    if build_errors:
        print("BUILD ERRORS (contract violations — the finding, not a crash):")
        for msg, n in build_errors.most_common():
            print(f"  {n:6d}  {msg}")

    if sets:
        print("\nper-model observed range (min / mean / max of the declared output):")
        for model_id in evidence_builder.producers:
            vals = [es.evidence[model_id].value for es in sets
                    if es.evidence[model_id].value is not None]
            sem = evidence_builder.spec(model_id).output_semantic
            if not vals:
                print(f"  {model_id:12s} {sem:28s} (no finite values)")
                continue
            print(f"  {model_id:12s} {sem:28s} "
                  f"{min(vals):+.4f} / {sum(vals)/len(vals):+.4f} / {max(vals):+.4f}   n={len(vals)}")
        print(f"\nabsent (declared, non-producing): {list(sets[0].absent)}")
        print("\nfirst evidence set:")
        print(sets[0].describe())

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "instrument": instr,
            "csv": str(csv_path),
            "declared_models": list(evidence_builder.models),
            "producers": list(evidence_builder.producers),
            "engine_keys": list(evidence_builder.engine_keys),
            "collector_records": seen_records,
            "records_without_engines": records_without_engines,
            "evidence_sets": len(sets),
            "distinct_hashes": len(hashes),
            "x_marker_sets": x_bars,
            "decisions": dict(decisions),
            "reasons": dict(reasons),
            "build_errors": dict(build_errors),
            "top_hashes": hashes.most_common(10),
        }, indent=2), encoding="utf-8")
        print(f"\nwritten -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

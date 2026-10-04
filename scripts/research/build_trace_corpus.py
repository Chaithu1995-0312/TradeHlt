# -*- coding: utf-8 -*-
"""build_trace_corpus.py — Mathematical Trace Corpus from toy-family (+ spine) executions (ERP).

DESCRIPTIVE measurement artifact — NOT an edge claim, NOT a discovery of profitable factors. For every
executed trade of expansion_breakout / mean_reversion / spine on the certified XAUUSD frozen candidate,
join the 38 canonical PIT features AT THE ENTRY BAR to the forward outcome (rr/MFE/MAE/timing). The
question this enables is "what mathematical structures repeatedly FAIL?", never "what is profitable."

PIT-clean: FeaturePipeline is causal (F-051/FC1-A); forward_walk is no-lookahead. Feature rows are keyed
by their true stream position (`_pos`) because FeaturePipeline drops a fixed warmup head + resets index —
so features join to Signal.entry_index by POSITION, not iloc. Corpus is UNTRUSTED_RAW / non-promotable
(§6.5); corpus stays FROZEN_CANDIDATE (read-only); no ACTIVE_VERSION/production change.

Usage:
  python scripts/research/build_trace_corpus.py
  python scripts/research/build_trace_corpus.py --families toy   # skip the (n=1) spine
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import pandas as pd  # noqa: E402

import research.controls    # noqa: F401,E402  (register)
import research.hypotheses  # noqa: F401,E402  (register incl. spine)
from data_ingestion.xauusd_phase1_candidate import PHASE1_STATUS, guard_xauusd_csv_path  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from research.config import ResearchConfig  # noqa: E402
from research.registry import get_hypothesis  # noqa: E402
from research.runner import HypothesisRunner  # noqa: E402
from runtime.backtest_v2 import CandleLoader  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402
from utils.run_manifest import build_manifest, write_run  # noqa: E402

INSTRUMENT = "XAUUSD"
TOY_CONFIG = "configs/research/research_config_fx_metals.json"
SPINE_CONFIG = "configs/research/research_config_spine_xauusd.json"
TOY_FAMILIES = ["expansion_breakout", "mean_reversion"]
OUT_DIR = _ROOT / "results" / "research" / "trace_corpus" / "xauusd"
RUNS_DIR = _ROOT / "results" / "test_runs"


def _feature_lookup(candles: list) -> dict[int, dict]:
    """Map stream-position -> {canonical feature: value}. FeaturePipeline drops a warmup head and
    resets the index, so we carry `_pos` (the true stream position) through and key by it."""
    df = pd.DataFrame([{"timestamp": getattr(c, "timestamp", ""), "open": c.open, "high": c.high,
                        "low": c.low, "close": c.close, "volume": c.volume} for c in candles])
    df["_pos"] = range(len(df))
    enriched, _ = FeaturePipeline(df).run()
    by_pos: dict[int, dict] = {}
    cols = list(CANONICAL_FEATURES)
    for _, row in enriched.iterrows():
        by_pos[int(row["_pos"])] = {f: (None if pd.isna(row[f]) else float(row[f])) for f in cols}
    return by_pos


def _null_features() -> dict:
    return {f: None for f in CANONICAL_FEATURES}


def _trace(family: str, outcome, feats: dict, entry_ts: str) -> dict:
    s = outcome.signal
    row = {
        "trade_id": None,  # filled by caller (family + running index)
        "family": family, "instrument": INSTRUMENT, "timeframe": "M15",
        "entry_index": int(s.entry_index), "entry_timestamp": entry_ts,
        "direction": s.direction, "entry": float(s.entry),
        "atr": float(s.atr), "sl_atr_mult": float(s.sl_atr_mult), "tp_atr_mult": float(s.tp_atr_mult),
        "outcome": outcome.outcome, "rr_achieved": outcome.rr_achieved,
        "mfe": outcome.mfe, "mae": outcome.mae, "duration_candles": outcome.duration_candles,
        "time_to_tp": outcome.time_to_tp, "time_to_failure": outcome.time_to_failure,
        "reached_1r": bool(outcome.reached_1r),
    }
    for name in CANONICAL_FEATURES:
        row[f"feature_{name}"] = feats.get(name)
    return row


def _collect_family(family: str, cfg: ResearchConfig, guarded: str, candles: list,
                    by_pos: dict[int, dict]) -> list[dict]:
    runner = HypothesisRunner(cfg)
    _, outcomes = runner.run_instrument(get_hypothesis(family), guarded, INSTRUMENT)
    rows: list[dict] = []
    n = len(candles)
    for i, oc in enumerate(outcomes):
        ei = int(oc.signal.entry_index)
        entry_ts = str(getattr(candles[ei], "timestamp", "")) if 0 <= ei < n else ""
        r = _trace(family, oc, by_pos.get(ei, _null_features()), entry_ts)
        r["trade_id"] = f"{family}_{i:06d}"
        rows.append(r)
    return rows


# ── Parallel forward_walk path (--jobs > 1) ──────────────────────────────────────────────────────
# Detection stays single-threaded + in-order (byte-matches run_instrument); only the independent,
# deterministic forward_walk is parallel-mapped. A worker loads the guarded candle arrays once and
# rebuilds each future slice locally, so workers receive only lightweight Signals. Outcomes come back
# in signal-emission order (map preserves order + None-skip mirrors run_instrument) → byte-identical to
# the --jobs 1 path (enforced by the determinism gate in tests).
_W: dict = {}


def _init_worker(guarded: str, instrument: str, mf: int, ttl, tm: float, em: str) -> None:
    from runtime.backtest_v2 import CandleLoader
    cs = list(CandleLoader(guarded, instrument).stream())
    _W["hi"] = [c.high for c in cs]
    _W["lo"] = [c.low for c in cs]
    _W["cl"] = [c.close for c in cs]
    _W["n"] = len(cs)
    _W.update(mf=mf, ttl=ttl, tm=tm, em=em)


class _FWBar:
    __slots__ = ("index", "high", "low", "close")

    def __init__(self, i, h, l, c):
        self.index, self.high, self.low, self.close = i, h, l, c


def _future(a: int, b: int):
    b = min(b, _W["n"])
    return [_FWBar(p, _W["hi"][p], _W["lo"][p], _W["cl"][p]) for p in range(a, b)]


def _fw_worker(sig_kind):
    from research.measurement.forward_walk import forward_walk, forward_walk_oco
    sig, kind = sig_kind
    ei = sig.entry_index
    if kind == "oco":
        fut = _future(ei + 1, ei + 1 + _W["mf"] + _W["ttl"])
        if not fut:
            return None
        return forward_walk_oco(sig, fut, max_forward=_W["mf"], entry_ttl=_W["ttl"],
                                trail_mult=_W["tm"], exit_model=_W["em"])
    fut = _future(ei + 1, ei + 1 + _W["mf"])
    if not fut:
        return None
    return forward_walk(sig, fut, max_forward=_W["mf"], trail_mult=_W["tm"], exit_model=_W["em"])


def _collect_signals(hyp, candles: list, cfg: ResearchConfig) -> list:
    """Replicates HypothesisRunner.run_instrument's detection loop EXACTLY (order + apply_signal_defaults),
    emitting (Signal, kind) pairs but NOT running forward_walk (that is parallelized)."""
    ctx = {"instrument": INSTRUMENT}
    sigs: list = []
    n = len(candles)
    for i in range(cfg.warmup, n):
        lo = max(0, i - cfg.window_size + 1)
        window = candles[lo:i + 1]
        for s in hyp.detect(window, {}, ctx):
            if cfg.apply_signal_defaults:
                s = dataclasses.replace(s, sl_atr_mult=cfg.sl_atr_mult, tp_atr_mult=cfg.tp_atr_mult)
            sigs.append((s, "oco" if s.direction == "oco" else "std"))
    return sigs


def _collect_family_parallel(family: str, cfg: ResearchConfig, guarded: str, candles: list,
                             by_pos: dict[int, dict], jobs: int) -> list[dict]:
    sigs = _collect_signals(get_hypothesis(family), candles, cfg)
    with ProcessPoolExecutor(
        max_workers=jobs, initializer=_init_worker,
        initargs=(guarded, INSTRUMENT, cfg.max_forward, cfg.entry_ttl, cfg.trail_mult, cfg.exit_model),
    ) as ex:
        outcomes = [oc for oc in ex.map(_fw_worker, sigs, chunksize=256) if oc is not None]
    rows: list[dict] = []
    n = len(candles)
    for i, oc in enumerate(outcomes):
        ei = int(oc.signal.entry_index)
        entry_ts = str(getattr(candles[ei], "timestamp", "")) if 0 <= ei < n else ""
        r = _trace(family, oc, by_pos.get(ei, _null_features()), entry_ts)
        r["trade_id"] = f"{family}_{i:06d}"
        rows.append(r)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="build_trace_corpus",
                                 description="Descriptive Mathematical Trace Corpus (XAUUSD toy+spine)")
    ap.add_argument("--families", choices=["toy", "all"], default="all",
                    help="'toy' = expansion_breakout+mean_reversion; 'all' also adds spine (n=1)")
    ap.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1),
                    help="parallel forward_walk workers; 1 = sequential run_instrument (determinism reference)")
    ap.add_argument("--out-dir", default=None, help="output dir (default the canonical corpus dir)")
    ap.add_argument("--only", default=None,
                    help="restrict to a single family (skips others + spine) — used by the determinism test")
    args = ap.parse_args(argv)

    def _collect(fam: str, cfg: ResearchConfig) -> list[dict]:
        if args.jobs and args.jobs > 1:
            return _collect_family_parallel(fam, cfg, guarded, candles, by_pos, args.jobs)
        return _collect_family(fam, cfg, guarded, candles, by_pos)

    out_dir = Path(args.out_dir) if args.out_dir else OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    guarded = guard_xauusd_csv_path("data/XAUUSD_M15.csv", INSTRUMENT)
    candles = list(CandleLoader(guarded, INSTRUMENT).stream())
    for i, c in enumerate(candles):
        c.index = i
    safe_print(f"Loaded {len(candles)} candles; building PIT feature matrix...")
    by_pos = _feature_lookup(candles)

    toy_cfg = ResearchConfig.from_file(TOY_CONFIG)
    per_family_counts: dict[str, int] = {}
    combined: list[dict] = []

    toy_families = [args.only] if args.only else TOY_FAMILIES
    for fam in toy_families:
        rows = _collect(fam, toy_cfg)
        (out_dir / f"{fam}.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
        per_family_counts[fam] = len(rows)
        combined.extend(rows)
        safe_print(f"  {fam}: {len(rows)} traces")

    if args.families == "all" and not args.only:
        os.environ["RESEARCH_SPINE_CONFIG"] = SPINE_CONFIG
        spine_cfg = ResearchConfig.from_file(SPINE_CONFIG)
        rows = _collect("spine", spine_cfg)
        (out_dir / "spine.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
        per_family_counts["spine"] = len(rows)
        combined.extend(rows)
        safe_print(f"  spine: {len(rows)} traces")

    (out_dir / "trace_corpus.jsonl").write_text(
        "\n".join(json.dumps(r) for r in combined) + ("\n" if combined else ""), encoding="utf-8")
    try:
        pd.DataFrame(combined).to_parquet(out_dir / "trace_corpus.parquet", index=False)
    except Exception as exc:  # noqa: BLE001 — parquet is a convenience, JSONL is canonical
        safe_print(f"  (parquet skipped: {exc})")

    assertions = {
        "descriptive_only": True, "non_promotable": True,
        "corpus_status": PHASE1_STATUS,
        "n_features": len(CANONICAL_FEATURES),
        "per_family_rows": per_family_counts, "total_rows": len(combined),
        "note": "PIT features (causal FeaturePipeline) at entry joined to no-lookahead forward_walk outcome; "
                "describes failure STRUCTURE, NOT profit; information not authority (D-04, §6.5); no edge claim",
    }
    manifest = build_manifest(
        command="python scripts/research/build_trace_corpus.py",
        argv=sys.argv,
        validation_lens="trace_corpus_descriptive",
        exit_model="intrabar_fixed",
        cost_model_bps=int(toy_cfg.round_trip_bps),
        label_source="forward_walk_intrabar_fixed",
        instruments=[INSTRUMENT], timeframe="M15",
        data_source="local_csv_mt5", network="none", dry_run=True,
        intended_work_item_id="WI-005",
    )
    run_dir = RUNS_DIR / manifest["run_id"]
    write_run(run_dir, manifest, assertions)

    safe_print(f"\nTrace corpus -> {OUT_DIR} (total {len(combined)} traces) | manifest -> {run_dir}")
    safe_print("DESCRIPTIVE / UNTRUSTED_RAW / non-promotable — no edge claim (§6.5).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

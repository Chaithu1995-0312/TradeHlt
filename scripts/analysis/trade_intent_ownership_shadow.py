"""
TRADE_INTENT_OWNERSHIP_SHADOW -- what would option C do to trade intent?

OBSERVATION_ONLY (docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md). This script makes NO
`src/` edit and mutates nothing: it replays the CRT engine and, at every point where intent IS
classified, ALSO computes what the OTHER classifier would have said. Ledger identity is therefore
structural, not merely measured.

BACKGROUND (docs/analysis/trade-intent-caller-census-2026-09-16.md)
------------------------------------------------------------------
`ExecutionEngine._derive_trade_intent` (crt_engine_v2.py:2321) reads a CANONICAL vocabulary but is
fed the 6-key CRT-local `state.cached_features`. They overlap on only `body_ratio` and
`double_sweep`, so `pullback` is dead on TWO independent conditions (`candles_since_sweep` absent
=> csr==99; `momentum_score` absent => mom==0.0) and `liq_sweep` rests on `double_sweep` alone.

Option C (the F-048 treatment, user-selected 2026-09-16) would delete the CRT classifier and let
`ExecutionPlannerV1_2._derive_intent` (execution_planner.py:331) own intent. The two are NOT
label-compatible:

  * CRT returns 4 lowercase labels and ALWAYS classifies (fallthrough `reversal`).
  * The planner returns 5 UPPERCASE labels; its fallthrough is UNKNOWN, which `plan()` converts to
    {"decision": "reject_unknown_intent"} when that flag is set (execution_planner.py:233-238;
    DEFAULT_CONFIG has it True). Its REVERSAL is an EMA-vs-direction test, not a fallthrough.

So option C can REJECT trades the CRT rail currently opens. That is the number this probe exists
to produce.

SEALED PRE-REGISTRATION (E-001; written before any result was read)
-------------------------------------------------------------------
P1  Arm CURRENT is `reversal` on >= 90% of records (pullback structurally dead; breakout needs
    body>0.6 AND disp>threshold on displacement-candle geometry).
P2  Arm CURRENT emits ZERO `pullback`.
P3  Arm C emits at least one `PULLBACK` (it can see the two keys the cache lacks).
P4  Arm C emits at least one `UNKNOWN` (i.e. option C introduces a reject path that does not
    exist today).
P5  n is small enough to be economically INSUFFICIENT (< 30 records).
Each prediction is scored PASS/FAIL in the artifact whether or not it flatters the hypothesis.

DECLARED LIMITATIONS -- these are properties of the measurement, not caveats added afterwards
----------------------------------------------------------------------------------------------
L1  n is tiny. This measures MECHANISM (does the label move, does a new reject appear), NEVER
    economics. No expectancy claim is derivable from it and none is made.
L2  A label difference is PARTLY DEFINITIONAL, not only coverage. Arm CURRENT's rd/disp are
    FM-027/FM-028 (displacement-candle geometry); Arm C's retest_depth/disp_strength are
    FM-021/FM-020 (pipeline quantities), and `body_ratio` differs in SUBJECT (displacement candle
    vs current bar). Disagreement must be attributed to both causes.
L3  Calling `_derive_intent` directly bypasses `plan()`. Only the classifier is under test.
L4  XAUUSD only (standing constraint). BACKTEST_ENGINE_GATE is left at the runtime default; this
    probe never reaches the fusion gate.
L5  Both arms are given the SAME `breakout_disp_threshold` (the engine's resolved value), which is
    what execution_planner.DEFAULT_CONFIG's own comment says they must share. A threshold
    mismatch would manufacture disagreement that is not about vocabulary.

Usage:
    venv/Scripts/python.exe scripts/analysis/trade_intent_ownership_shadow.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
os.chdir(ROOT)

import pandas as pd

from config_layer.crt_engine_v2 import CRTEngine, Direction, ExecutionEngine
from config_layer.execution_planner import ExecutionPlannerV1_2
from config_layer.production_config import (
    get_active_version,
    get_prod_section,
    load_prod_config_from_registry,
)
from features.feature_pipeline import FeaturePipeline
from features.feature_schema import CANONICAL_FEATURES, SCHEMA_VERSION
from runtime.backtest_v2 import HTFBuilder

from xauusd_excel_feature_state_trace import _sha256, load_from_csv

DEFAULT_CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
DEFAULT_OUT = ROOT / "docs" / "governance" / "trade_intent_ownership_shadow.LATEST.json"
INSTRUMENT = "XAUUSD"

# The nine keys ExecutionPlannerV1_2._derive_intent reads (execution_planner.py:348-356).
# All nine are canonical -- verified against CANONICAL_FEATURES at runtime below.
PLANNER_KEYS = (
    "sweep_detected", "double_sweep", "retest_depth", "candles_since_sweep",
    "momentum_score", "body_ratio", "disp_strength", "ema_fast", "ema_slow",
)

PREDICTIONS = {
    "P1_current_reversal_ge_90pct": "Arm CURRENT is `reversal` on >= 90% of records",
    "P2_current_zero_pullback": "Arm CURRENT emits ZERO `pullback`",
    "P3_argC_some_pullback": "Arm C emits at least one `PULLBACK`",
    "P4_argC_some_unknown": "Arm C emits at least one `UNKNOWN` (new reject path)",
    "P5_n_insufficient": "n < 30 (economically INSUFFICIENT)",
}


def _ts_key(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def build_canonical_frame(csv_path: Path) -> tuple[dict[str, int], Any, dict]:
    """Canonical rows + timestamp index, built the way backtest_v2 builds them.

    Reuses `FeaturePipeline.run()` (backtest_v2.py:2033-2034) and the same
    `strftime("%Y-%m-%d %H:%M:%S")` key shape as `feature_ts_to_idx`
    (backtest_v2.py:2053-2057), so a lookup here resolves the SAME row the runtime's
    T-16 fail-closed lookup would resolve for that bar.
    """
    raw = pd.read_csv(csv_path)
    raw.columns = [c.lower() for c in raw.columns]
    fp_cfg = get_prod_section("feature_pipeline")
    enriched_df, feature_vectors = FeaturePipeline(raw, cfg=fp_cfg).run()
    ts_to_idx = {
        _ts_key(ts): i for i, ts in enumerate(pd.to_datetime(enriched_df["timestamp"]))
    }
    return ts_to_idx, feature_vectors, fp_cfg


def canonical_row(feature_vectors, idx: int) -> dict[str, float]:
    row = feature_vectors[idx]
    return {name: float(row[i]) for i, name in enumerate(CANONICAL_FEATURES)}


def tp1_multiplier(cfg, intent: str) -> float:
    """Exactly the lookup build_trade performs (crt_engine_v2.py:2418-2419)."""
    return float(getattr(cfg, f"tp1_atr_multiplier_{intent.lower()}", cfg.tp1_atr_multiplier))


def run(csv_path: Path, out_path: Path) -> dict[str, Any]:
    version = get_active_version()
    cfg = load_prod_config_from_registry(version, INSTRUMENT)
    thr = float(cfg.breakout_disp_threshold)

    # L5: both arms share the engine's resolved threshold.
    planner = ExecutionPlannerV1_2({"breakout_disp_threshold": thr})
    reject_unknown = bool(planner.config["reject_unknown_intent"])

    missing = [k for k in PLANNER_KEYS if k not in CANONICAL_FEATURES]
    if missing:
        raise SystemExit(f"planner keys absent from CANONICAL_FEATURES: {missing}")

    candles, _ = load_from_csv(csv_path)
    ts_to_idx, feature_vectors, _ = build_canonical_frame(csv_path)

    engine = CRTEngine(cfg)
    htf = HTFBuilder(4, INSTRUMENT)
    initialized = False

    # Intercept build_trade so the trade-open subset is OBSERVED, not inferred from state.
    trade_open_bars: set[str] = set()
    orig_build = engine.executor.build_trade

    def build_trade_traced(state, risk_engine=None):  # type: ignore[no-untyped-def]
        trade = orig_build(state, risk_engine)
        if trade is not None:
            rt = state.retest_candle
            if rt is not None:
                trade_open_bars.add(_ts_key(rt.timestamp))
        return trade

    engine.executor.build_trade = build_trade_traced  # type: ignore[method-assign]

    records: list[dict[str, Any]] = []
    lookup_misses = 0
    prev_cache_id: int | None = None

    for candle in candles:
        completed = htf.push(candle)
        if not initialized:
            if completed:
                engine.initialise_range(htf.seed_candles(), htf.current_htf_id, "UNKNOWN")
                initialized = True
            continue

        engine.process_candle(candle, htf.current_htf_id)

        cache = engine.state.cached_features
        if cache is None:
            prev_cache_id = None
            continue
        # A NEWLY built cache means a retest confirmed on this bar (crt_engine_v2.py:1764/:1781).
        if id(cache) == prev_cache_id:
            continue
        prev_cache_id = id(cache)

        key = _ts_key(candle.timestamp)
        idx = ts_to_idx.get(key, -1)
        if idx < 0:
            # Same class as the T-16 miss: recorded, never zero-filled.
            lookup_misses += 1
            continue

        crow = canonical_row(feature_vectors, idx)
        direction = engine.state.direction
        dir_int = 1 if direction == Direction.LONG else (-1 if direction == Direction.SHORT else 0)

        intent_current = ExecutionEngine._derive_trade_intent(cache, thr)
        intent_c, reason_c = planner._derive_intent(crow, {"selected_direction": dir_int})

        records.append({
            "timestamp": key,
            "crt_state": engine.state.current_state.name,
            "direction": direction.name,
            # Filled in AFTER the loop: build_trade fires on a LATER bar than the retest
            # confirmation (soft-confirmation window), so membership tested here would always
            # be False. This is the bug that made the first run report 0 trade-opens.
            "is_trade_open": None,
            "arm_current": {
                "intent": intent_current,
                "tp1_atr_multiplier": tp1_multiplier(cfg, intent_current),
                "cache_keys": sorted(cache.keys()),
                # L2 made MEASURABLE rather than asserted: these are the quantities the CRT arm
                # actually gated on. `rd` here is FM-027 displacement_retrace; Arm C's `rd` is
                # FM-021 retest_depth. Recording both lets the write-up attribute disagreement
                # to definition vs coverage instead of guessing.
                "inputs": {
                    "rd_fm027_displacement_retrace": float(cache.get("displacement_retrace", 0.0)),
                    "disp_fm028_displacement_atr_ratio": float(
                        cache.get("displacement_atr_ratio", 0.0)
                    ),
                    "body_ratio_displacement_candle": float(cache.get("body_ratio", 0.0)),
                    "double_sweep": bool(cache.get("double_sweep", False)),
                },
            },
            "arm_c": {
                "intent": intent_c,
                "reason": reason_c,
                "tp1_atr_multiplier": (
                    None if intent_c == "UNKNOWN" else tp1_multiplier(cfg, intent_c)
                ),
                "is_unknown": intent_c == "UNKNOWN",
                "would_reject": intent_c == "UNKNOWN" and reject_unknown,
                "inputs": {k: crow[k] for k in PLANNER_KEYS},
            },
            "labels_agree": intent_current.upper() == intent_c,
            "tp1_changes": (
                intent_c == "UNKNOWN"
                or tp1_multiplier(cfg, intent_current) != tp1_multiplier(cfg, intent_c)
            ),
        })

    # Resolve the trade-open subset now that every build_trade call has been observed.
    for r in records:
        r["is_trade_open"] = r["timestamp"] in trade_open_bars

    # ── Non-vacuity: a shadow that measured nothing must fail LOUDLY (F-079/F-083 class) ──
    if not records:
        raise SystemExit(
            "NON-VACUITY FAILURE: zero paired observations recorded. A shadow with no records "
            "is indistinguishable from a shadow that agreed on everything. Refusing to emit an "
            "artifact."
        )
    for r in records:
        if not r["arm_current"]["intent"] or not r["arm_c"]["intent"]:
            raise SystemExit(f"NON-VACUITY FAILURE: an arm did not run on record {r['timestamp']}")

    n = len(records)
    cur = Counter(r["arm_current"]["intent"] for r in records)
    arm_c = Counter(r["arm_c"]["intent"] for r in records)
    confusion = Counter(
        (r["arm_current"]["intent"], r["arm_c"]["intent"]) for r in records
    )
    n_unknown = sum(1 for r in records if r["arm_c"]["is_unknown"])
    n_would_reject = sum(1 for r in records if r["arm_c"]["would_reject"])
    n_disagree = sum(1 for r in records if not r["labels_agree"])
    n_tp_changes = sum(1 for r in records if r["tp1_changes"])
    opens = [r for r in records if r["is_trade_open"]]

    # Which QUANTITY gates the pullback band? Option A/B (bind the cache's missing keys, keep
    # FM-027 as rd) and option C (switch wholesale to the pipeline's FM-021 retest_depth) are NOT
    # equivalent -- they differ in the depth quantity, not only in reject semantics. Counting
    # band occupancy under each makes that difference a measurement rather than an assertion.
    band_fm027 = sum(
        1 for r in records
        if 0.3 <= r["arm_current"]["inputs"]["rd_fm027_displacement_retrace"] <= 0.7
    )
    band_fm021 = sum(1 for r in records if 0.3 <= r["arm_c"]["inputs"]["retest_depth"] <= 0.7)

    results = {
        "P1_current_reversal_ge_90pct": cur.get("reversal", 0) / n >= 0.90,
        "P2_current_zero_pullback": cur.get("pullback", 0) == 0,
        "P3_argC_some_pullback": arm_c.get("PULLBACK", 0) >= 1,
        "P4_argC_some_unknown": n_unknown >= 1,
        "P5_n_insufficient": n < 30,
    }

    artifact = {
        "probe": "TRADE_INTENT_OWNERSHIP_SHADOW",
        "version": "1.0.0",
        "task_class": "OBSERVATION_ONLY",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": INSTRUMENT,
        "csv_path": str(csv_path.relative_to(ROOT)),
        "csv_sha256": _sha256(csv_path),
        "active_version": version,
        "schema_version": SCHEMA_VERSION,
        "breakout_disp_threshold": thr,
        "reject_unknown_intent": reject_unknown,
        "n_candles": len(candles),
        "n_records": n,
        "n_trade_opens": len(opens),
        "feature_lookup_misses": lookup_misses,
        "arm_current_distribution": dict(cur),
        "arm_c_distribution": dict(arm_c),
        "confusion_matrix": {f"{a} -> {b}": c for (a, b), c in sorted(confusion.items())},
        "n_labels_disagree": n_disagree,
        "n_tp1_multiplier_changes": n_tp_changes,
        "n_arm_c_unknown": n_unknown,
        "n_arm_c_would_reject": n_would_reject,
        "pullback_band_occupancy": {
            "note": (
                "How many records sit in the 0.3-0.7 pullback depth band under EACH depth "
                "quantity. Option A/B keeps FM-027 (displacement_retrace, cross-candle retrace "
                "of the displacement body); option C switches to FM-021 (retest_depth, the "
                "pipeline quantity). A divergence here means the two options are not "
                "interchangeable."
            ),
            "fm027_displacement_retrace_in_band": band_fm027,
            "fm021_retest_depth_in_band": band_fm021,
            "n": n,
        },
        "trade_open_subset": [
            {
                "timestamp": r["timestamp"],
                "arm_current": r["arm_current"]["intent"],
                "arm_c": r["arm_c"]["intent"],
                "tp1_current": r["arm_current"]["tp1_atr_multiplier"],
                "tp1_arm_c": r["arm_c"]["tp1_atr_multiplier"],
                "would_reject": r["arm_c"]["would_reject"],
            }
            for r in opens
        ],
        "predictions": PREDICTIONS,
        "prediction_results": results,
        "predictions_passed": sum(1 for v in results.values() if v),
        "predictions_total": len(results),
        "authority": "NONE. Mechanism observation only; no economic claim, no G001, no config change.",
        "limitations": [
            "L1 n is tiny -- measures MECHANISM, never economics.",
            "L2 disagreement is PARTLY DEFINITIONAL: FM-027/FM-028 vs FM-021/FM-020, and "
            "body_ratio differs in SUBJECT (displacement candle vs current bar).",
            "L3 _derive_intent called directly, bypassing plan().",
            "L4 XAUUSD only.",
            "L5 both arms share the engine's resolved breakout_disp_threshold.",
        ],
        "records": records,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    print(f"schema {SCHEMA_VERSION} | active {version} | thr {thr} | reject_unknown {reject_unknown}")
    print(f"records (retest confirmations): {n}   trade-opens: {len(opens)}   lookup misses: {lookup_misses}")
    print(f"arm CURRENT : {dict(cur)}")
    print(f"arm C       : {dict(arm_c)}")
    print("confusion   :")
    for (a, b), c in sorted(confusion.items()):
        print(f"   {a:10s} -> {b:10s}  {c}")
    print(f"labels disagree: {n_disagree}/{n}   tp1 multiplier changes: {n_tp_changes}/{n}")
    print(f"arm C UNKNOWN: {n_unknown}   would REJECT under option C: {n_would_reject}")
    print(f"pullback band 0.3-0.7: FM-027 rd in-band {band_fm027}/{n}  vs  FM-021 retest_depth in-band {band_fm021}/{n}")
    print("predictions:")
    for k, v in results.items():
        print(f"   {'PASS' if v else 'FAIL'}  {k}: {PREDICTIONS[k]}")
    print(f"artifact -> {out_path.relative_to(ROOT)}")
    return artifact


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    run(args.csv, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

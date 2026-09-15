"""
retest_divergence_probe.py
================================================================================
Phase A of the "CRT resolver RETEST" diagnostic (2026-09-11 session).

QUESTION
--------
The resolver's RETEST recall is 0.0% against the engine (17 engine RETEST bars,
resolver_n=0), reproduced at every value of `retest_depth_max` already swept
({0.08, 0.15, 0.25} -- `scripts/research/e1_retest_depth_max_probe.py`). That
probe correctly established the THRESHOLD is non-pivotal. It does not establish
WHY the resolver never reaches RETEST at all.

Source comparison (this session) found FOUR independent divergences between the
engine's `try_expansion_to_retest` (crt_engine_v2.py:1606-1653) and the
resolver's RETEST gate (`_continuous_gates_pass`, crt_state_resolver.py:1597-
1601):
  1. different quantity  -- engine: close vs active_range boundary (price
     units); resolver: pipeline `retest_depth` feature (FM-021).
  2. missing rng.size scaling -- engine's static_ceiling = retest_depth_max *
     rng.size; resolver compares retest_depth_max as a bare scalar.
  3. missing ATR ceiling -- engine: adaptive_ceiling = max(static, atr_ceiling
     via retest_atr_depth_fraction); resolver never reads
     `retest_atr_depth_fraction` (0 occurrences, confirmed by grep before this
     script was written).
  4. missing floor -- engine: depth_abs >= retest_min_depth_atr_fraction * atr;
     resolver has no floor and does not even declare the key (0 occurrences).
  Plus a funnel precondition (`current_state in {EXPANSION, RETEST}`) that
  cannot be satisfied while EXPANSION itself only arrives via
  shadow-memory restoration or engine-oracle injection on this corpus
  (continuous_disp_to_expansion defaults False, single read site
  crt_state_resolver.py:1500).

THIS SCRIPT IS AN ATTRIBUTION INSTRUMENT, NOT A FIX.
It does not modify `crt_state_resolver.py`, `crt_engine_v2.py`, or any
`configs/formulas/*.yaml`. It replays the FROZEN events.jsonl (no backtest_v2
re-run -- see the "backtest_v2.py is dirty on this branch" note below) and adds
one read-only instrumentation pass over the resolver using the existing,
behavior-neutral `CRTStateResolver.resolve_metadata()` (pinned inert by
`tests/test_resolver_metadata.py::test_behavior_neutral`), called immediately
before each `resolve()` in the SAME sequential loop `build_resolver_timeline`
already runs -- so `_memory` state at inspection time is authentic, not
reconstructed.

WHY A NEW SCRIPT INSTEAD OF EXTENDING crt_state_confusion_matrix.py
---------------------------------------------------------------------
`build_resolver_timeline` only calls `.resolve()` and returns state labels; it
does not expose per-bar `retest_depth`, `continuous_passed`, or `_memory`
before/after. Re-implementing its feature-vector construction here (rather
than hand-copying a "pure twin" of the funnel itself, which the
`resolve_metadata` docstring explicitly warns against) is the minimum
duplication that stays honest: the STATE-ADVANCING call is still the real
`resolver.resolve()`, unmodified.

WORKTREE NOTE (git status, checked before writing this script)
----------------------------------------------------------------
`src/runtime/backtest_v2.py` is modified on this branch (+169/-3, HTFBuilder +
_preflight_dataset). Verified this script's entire import chain --
`prepare_engine_context` (replays frozen events.jsonl) and
`build_htf_id_timeline`/`compute_enriched_frame`/`CRTStateResolver` (resolver +
FeaturePipeline only) -- imports `backtest_v2` NOWHERE. `crt_parity_sweep.py`
imports it only inside `run_stage_a`'s engine-RE-RUN path
(`_run_engine_candidate`, line ~471), which this script never calls. Confirmed
by grep, not assumed.

Usage
    venv/Scripts/python.exe scripts/research/retest_divergence_probe.py
================================================================================
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts" / "research"))

import pandas as pd  # noqa: E402

import crt_state_confusion_matrix as cm  # noqa: E402

DEFAULT_OHLCV = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
DEFAULT_EVENTS = _ROOT / "results" / "run_20260724_104845_XAUUSD" / "XAUUSD_events.jsonl"
DEFAULT_SUMMARY = _ROOT / "results" / "run_20260724_104845_XAUUSD" / "XAUUSD_summary.json"

PROBE_ROOT = _ROOT / "results" / "analysis" / "retest_divergence_probe"
OUT_JSON = PROBE_ROOT / "retest_divergence_probe.json"

INSTRUMENT = "XAUUSD"


def _engine_retest_raw_indices(engine_ctx: "cm.PreparedEngineContext") -> list[int]:
    """Raw candle indices the engine's timeline counts as RETEST occupancy.

    `state_distribution` (the 17 reference count in market_crt_states.yaml) is
    the engine's ENTER-state per-bar occupancy -- reconstruct_engine_timeline's
    own docstring: "enter_states is what the engine summary's state_distribution
    counts." Matches crt_state_confusion_matrix's own reference-summary loader.
    """
    return [
        i for i, s in enumerate(engine_ctx.timeline.enter_states)
        if s == "RETEST"
    ]


def main() -> int:
    from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
    from features.feature_schema import CANONICAL_FEATURES

    PROBE_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Loading frozen engine timeline from {DEFAULT_EVENTS} ...")
    engine_ctx = cm.prepare_engine_context(
        DEFAULT_OHLCV, DEFAULT_EVENTS, reference_summary_path=DEFAULT_SUMMARY
    )
    retest_raw_idx = set(_engine_retest_raw_indices(engine_ctx))
    print(f"      engine RETEST bars (enter-state occupancy): {len(retest_raw_idx)}")
    if not retest_raw_idx:
        print("      NOTHING TO ATTRIBUTE -- engine has 0 RETEST bars on this replay. Abort.")
        return 1

    print("[2/5] Running FeaturePipeline once (compute_enriched_frame) ...")
    enriched = cm.compute_enriched_frame(DEFAULT_OHLCV)
    source_indices = [int(v) for v in enriched["_src_idx"].tolist()]

    print("[3/5] Constructing resolver (shipped config, base variant == default) ...")
    resolver = CRTStateResolver()
    thr = resolver._config.get("thresholds", {})
    depth_max = float(thr.get("retest_depth_max", 0.25))
    # Declared in market_crt_states.yaml but NOT read by the resolver (confirmed
    # 0 occurrences by grep before this script existed) -- read directly off the
    # loaded config for the "what-if" arithmetic only. Never fed back into the
    # resolver's own gate.
    atr_depth_fraction_declared = thr.get("retest_atr_depth_fraction")
    # Confirmed absent from the resolver's vocabulary entirely (0 occurrences).
    min_depth_atr_fraction_declared = thr.get("retest_min_depth_atr_fraction")

    life = thr.get("lifecycle") or {}
    cph = int(life.get("htf_candles_per_range", 4))
    # n_raw for HTF timeline must be the RAW stream length, not the enriched
    # (post-warmup-drop) length -- mirror build_resolver_timeline exactly.
    n_raw = int(pd.read_csv(DEFAULT_OHLCV).shape[0])
    engine_htf_ids = build_htf_id_timeline(n_raw, candles_per_htf=cph, instrument=INSTRUMENT)

    # Warmup seed (htf_range geometry only) -- mirrors build_resolver_timeline
    # exactly so active_range state at inspection time matches what the F-069
    # parity kernel itself measures, not a divergent bootstrap.
    first_src = int(source_indices[0]) if source_indices else 0
    if getattr(resolver, "_sweep_geometry", "pipeline_swing") == "htf_range" and first_src > 0:
        df_raw = pd.read_csv(DEFAULT_OHLCV)
        df_raw.columns = [c.lower() for c in df_raw.columns]
        raw_o = df_raw["open"].astype(float).tolist()
        raw_h = df_raw["high"].astype(float).tolist()
        raw_l = df_raw["low"].astype(float).tolist()
        raw_c = df_raw["close"].astype(float).tolist()
        for i in range(first_src):
            hid = engine_htf_ids[i] if i < len(engine_htf_ids) else None
            resolver.seed_ohlc(raw_o[i], raw_h[i], raw_l[i], raw_c[i], htf_id=hid)
        resolver.finalize_seed_range()

    ts_col = None
    for cand in ("timestamp", "time", "datetime"):
        if cand in enriched.columns:
            ts_col = cand
            break
    if ts_col is not None:
        enriched = enriched.copy()
        enriched[ts_col] = pd.to_datetime(enriched[ts_col])

    rsi_ob = float(thr.get("rsi_overbought", 70.0))
    rsi_os = float(thr.get("rsi_oversold", 30.0))

    print("[4/5] Sequential resolve() pass -- snapshotting resolve_metadata() "
          "immediately before each resolve() call (injection=none, matching "
          "F-069's primary metric) ...")

    rows: list[dict] = []
    funnel_admitted = 0
    funnel_rejected_precondition = 0

    for row_i, (_, row) in enumerate(enriched.iterrows()):
        fv: dict[str, float] = {}
        for name in CANONICAL_FEATURES:
            if name in enriched.columns:
                val = row[name]
                fv[name] = 0.0 if pd.isna(val) else float(val)
        for name in ("retest_flag", "displacement_flag"):
            if name in enriched.columns:
                val = row[name]
                fv[name] = 0.0 if pd.isna(val) else float(val)
            else:
                fv[name] = 0.0
        rsi = fv.get("rsi_14", 50.0)
        fv["rsi_state"] = 1.0 if rsi > rsi_ob else (-1.0 if rsi < rsi_os else 0.0)

        ts = row[ts_col] if ts_col is not None else None
        if ts is not None and pd.isna(ts):
            ts = None

        src = source_indices[row_i]
        htf_id = engine_htf_ids[src] if 0 <= src < len(engine_htf_ids) else None

        is_target = src in retest_raw_idx
        if is_target:
            # ── Pre-resolve() snapshot: behavior-neutral, pinned inert ──
            meta = resolver.resolve_metadata(fv, timestamp=ts, enforce_required_when=False)
            mem = resolver._memory
            depth_pipeline = fv.get("retest_depth")
            atr_abs = resolver._atr_abs(fv)

            range_size = (mem.range_h_ref - mem.range_l_ref) if mem.range_ready else None
            static_ceiling_if_scaled = (depth_max * range_size) if range_size is not None else None
            atr_ceiling_if_read = (
                float(atr_depth_fraction_declared) * atr_abs
                if atr_depth_fraction_declared is not None and atr_abs is not None
                else None
            )
            adaptive_ceiling_if_fixed = (
                max(v for v in (static_ceiling_if_scaled, atr_ceiling_if_read) if v is not None)
                if (static_ceiling_if_scaled is not None or atr_ceiling_if_read is not None)
                else None
            )
            min_depth_if_declared = (
                float(min_depth_atr_fraction_declared) * atr_abs
                if min_depth_atr_fraction_declared is not None and atr_abs is not None
                else None  # confirmed: this key does not exist in the resolver's config at all
            )

            precondition_ok = mem.current_state in ("EXPANSION", "RETEST")
            if precondition_ok:
                funnel_admitted += 1
            else:
                funnel_rejected_precondition += 1

            rows.append({
                "raw_index": src,
                "timestamp": str(ts) if ts is not None else None,
                "resolver_memory_state_before_bar": mem.current_state,
                "funnel_precondition_ok": precondition_ok,
                "continuous_gate_RETEST_passed": meta.continuous_passed.get("RETEST"),
                "predicate_affinity_RETEST": meta.predicate_affinity.get("RETEST"),
                "projected_funnel_site": meta.projected_funnel_site,
                # divergence 1: quantity
                "depth_pipeline_retest_depth_FM021": depth_pipeline,
                "resolver_gate_compares_this_to": "thresholds.retest_depth_max (bare scalar)",
                "resolver_gate_threshold_value": depth_max,
                "resolver_gate_would_reject": (
                    depth_pipeline is not None and depth_pipeline > depth_max
                ),
                # divergence 2/3/4: what-if arithmetic (NOT fed back into the resolver)
                "range_ready": bool(mem.range_ready),
                "range_size_h_minus_l": range_size,
                "atr_abs_resolved": atr_abs,
                "whatif_static_ceiling_rng_size_scaled": static_ceiling_if_scaled,
                "whatif_atr_ceiling_if_fraction_were_read": atr_ceiling_if_read,
                "whatif_adaptive_ceiling_max_of_both": adaptive_ceiling_if_fixed,
                "whatif_min_depth_floor_if_key_existed": min_depth_if_declared,
            })

        resolved_state = resolver.resolve(
            fv, timestamp=ts, htf_id=htf_id,
            engine_reset=False, engine_state_to=None,  # injection=none
        )
        if is_target:
            rows[-1]["resolver_state_after_this_bar"] = resolved_state

    print(f"      snapshotted {len(rows)}/{len(retest_raw_idx)} target bars "
          f"({len(retest_raw_idx) - len(rows)} fell in FeaturePipeline warmup and "
          "were never presented to the resolver at all -- a 5th, structural "
          "divergence if nonzero)")

    print("[5/5] Attribution summary ...")
    n = len(rows)
    n_funnel_rejected = funnel_rejected_precondition
    n_funnel_admitted = funnel_admitted
    n_gate_would_reject_given_admitted = sum(
        1 for r in rows if r["funnel_precondition_ok"] and r["resolver_gate_would_reject"]
    )
    n_no_pipeline_depth = sum(1 for r in rows if r["depth_pipeline_retest_depth_FM021"] is None)

    summary = {
        "engine_retest_bars_total": len(retest_raw_idx),
        "engine_retest_bars_reached_by_resolver_post_warmup": n,
        "engine_retest_bars_dropped_by_featurepipeline_warmup": len(retest_raw_idx) - n,
        "funnel_precondition_rejected": n_funnel_rejected,
        "funnel_precondition_admitted": n_funnel_admitted,
        "of_admitted_gate_would_still_reject_on_depth_scalar": n_gate_would_reject_given_admitted,
        "bars_with_no_pipeline_retest_depth_value": n_no_pipeline_depth,
        "config_declared_retest_atr_depth_fraction": atr_depth_fraction_declared,
        "config_declared_retest_min_depth_atr_fraction_present": (
            min_depth_atr_fraction_declared is not None
        ),
    }

    verdict_lines = []
    if n == 0:
        verdict_lines.append(
            "INSUFFICIENT EVIDENCE: every engine-RETEST bar fell in FeaturePipeline "
            "warmup; the resolver never saw one of the 17 bars. That IS a finding "
            "(structural, not gate-level) but this probe cannot attribute among "
            "divergences 1-4 without at least one presented bar."
        )
    else:
        if n_funnel_rejected == n:
            verdict_lines.append(
                f"DECISIVE (at n={n}): the funnel precondition "
                "(current_state in {EXPANSION, RETEST}) rejects ALL presented bars "
                "before the depth gate is ever evaluated. Divergences 1-4 are "
                "PRESENT but INERT at this corpus -- fixing the depth quantity/"
                "scaling/ceiling/floor changes nothing until EXPANSION is reachable "
                "on the same bars (continuous_disp_to_expansion=false; ties to the "
                "shadow-vs-continuous EXPANSION finding from this session)."
            )
        elif n_funnel_admitted > 0 and n_gate_would_reject_given_admitted == n_funnel_admitted:
            verdict_lines.append(
                f"DECISIVE (at n={n}): {n_funnel_admitted} bar(s) pass the funnel "
                "precondition but the depth-scalar gate rejects all of them under "
                "the CURRENT (unscaled, no-ceiling, no-floor) comparison. Divergences "
                "1-4 are load-bearing for these bars specifically."
            )
        elif n_funnel_admitted > 0 and n_gate_would_reject_given_admitted < n_funnel_admitted:
            verdict_lines.append(
                f"AMBIGUOUS at n={n_funnel_admitted} admitted bar(s): the current "
                "gate does NOT reject every admitted bar on the depth comparison "
                "alone, yet resolver_n is still 0 elsewhere in the pipeline "
                f"(n={n_funnel_admitted - n_gate_would_reject_given_admitted} pass "
                "depth but do not end in RETEST) -- a fifth mechanism is acting "
                "downstream of _continuous_gates_pass. Do not attribute without "
                "reading rows[] for these specific bars."
            )
        else:
            verdict_lines.append(
                f"MIXED at n={n}: {n_funnel_rejected} precondition-rejected, "
                f"{n_funnel_admitted} admitted. See rows[] for per-bar attribution; "
                "no single divergence dominates at this n."
            )
    verdict_lines.append(
        f"EPISTEMIC GUARD: n={len(retest_raw_idx)} engine RETEST bars total "
        f"({n} reached the resolver). This is a MECHANISM diagnostic, not a "
        "powered economic measurement -- no finding should be registered off "
        "this alone (CLAUDE.md Epistemic Integrity Pre-Registration Ritual, "
        "question 2: could INSUFFICIENT explain the observation)."
    )

    out = {
        "probe": "retest_divergence_probe",
        "purpose": "attribute resolver RETEST recall=0.0% among 4 source-identified "
                   "gate divergences vs the engine + 1 funnel precondition; "
                   "read-only, no config or src changes",
        "ohlcv": str(DEFAULT_OHLCV),
        "events": str(DEFAULT_EVENTS),
        "resolver_config": "configs/formulas/market_crt_states.yaml (shipped, "
                            "no variant, no override -- resolver default)",
        "summary": summary,
        "verdict": verdict_lines,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=False, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_JSON}")
    print("\n".join(verdict_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

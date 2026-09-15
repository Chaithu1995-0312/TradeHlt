"""
link001_choch_measurement.py
================================================================================
Phase B4 of the LINK-001 (change_of_character) binding (2026-09-11 session).

QUESTION
--------
`configs/formulas/crt_resolver_links.yaml` LINK-001 rationale: "Tests whether
giving the resolver access to the reversal/continuation distinction changes
which bars it disagrees with the engine about." Bound 2026-09-11 on
DISPLACEMENT (`change_of_character: {states: [BullishCHoCH, BearishCHoCH],
link: LINK-001}`, AND'd with the existing `displacement_flag` clause). This
script runs `base` (every link off, the shipped default) and `choch`
(LINK-001 only) side by side over the SAME engine timeline and reports whether
the confusion matrix moves.

WHY A NEW SCRIPT INSTEAD OF crt_parity_sweep.py / e1_retest_depth_max_probe.py
---------------------------------------------------------------------------------
`crt_state_confusion_matrix.run_once(config_path=...)` -- the kernel both of
those scripts drive -- predates the LINK/variant system: it constructs
`CRTStateResolver(config_path=config_path)` with no `variant=`/`links=`
passthrough. Extending that shared kernel's signature is a larger, separately-
reviewable change; this script instead reuses its LOWER-level, already-public
building blocks directly -- `prepare_engine_context` (frozen events.jsonl
replay, engine timeline), `compute_enriched_frame` (FeaturePipeline, run once,
shared by both resolver passes), `build_htf_id_timeline`, and `build_confusion`
-- the same functions `build_resolver_timeline` composes internally, just
without its config_path-only constructor call. No existing shared script is
modified.

WORKTREE NOTE (unchanged from retest_divergence_probe.py, re-checked)
------------------------------------------------------------------------
Same import chain as the Phase-A probe: `prepare_engine_context` replays
frozen events.jsonl, `compute_enriched_frame`/`CRTStateResolver` touch only
FeaturePipeline + the resolver. `backtest_v2.py` (dirty on this branch) is
never imported.

Usage
    venv/Scripts/python.exe scripts/research/link001_choch_measurement.py
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
from crt_parity_sweep import anti_simpson_ok, per_state_summary  # noqa: E402

DEFAULT_OHLCV = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
DEFAULT_EVENTS = _ROOT / "results" / "run_20260724_104845_XAUUSD" / "XAUUSD_events.jsonl"
DEFAULT_SUMMARY = _ROOT / "results" / "run_20260724_104845_XAUUSD" / "XAUUSD_summary.json"

PROBE_ROOT = _ROOT / "results" / "analysis" / "link001_choch_measurement"
OUT_JSON = PROBE_ROOT / "link001_choch_measurement.json"

INSTRUMENT = "XAUUSD"


def _run_resolver_pass(resolver, enriched, engine_htf_ids, source_indices,
                        CANONICAL_FEATURES, thr, rsi_ob, rsi_os, ts_col):
    """Drive one resolver instance sequentially over `enriched`; return
    (states, resolution_sites). Mirrors build_resolver_timeline's per-bar
    fv-construction exactly (same feature set, same rsi_state derivation,
    same injection=none semantics) so this is a faithful second instance of
    the SAME procedure that function runs for a single resolver -- not a
    divergent reimplementation."""
    states: list[str] = []
    resolution_sites: list = []
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

        resolved = resolver.resolve(
            fv, timestamp=ts, htf_id=htf_id,
            engine_reset=False, engine_state_to=None,  # injection=none
        )
        states.append(resolved)
        resolution_sites.append(resolver._last_funnel_site)
    return states, resolution_sites


def main() -> int:
    from features.crt_state_resolver import CRTStateResolver, build_htf_id_timeline
    from features.feature_schema import CANONICAL_FEATURES

    PROBE_ROOT.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Loading frozen engine timeline from {DEFAULT_EVENTS} ...")
    engine_ctx = cm.prepare_engine_context(
        DEFAULT_OHLCV, DEFAULT_EVENTS, reference_summary_path=DEFAULT_SUMMARY
    )

    print("[2/4] Running FeaturePipeline once, shared by both resolver passes ...")
    enriched = cm.compute_enriched_frame(DEFAULT_OHLCV)
    source_indices = [int(v) for v in enriched["_src_idx"].tolist()]

    ts_col = None
    for cand in ("timestamp", "time", "datetime"):
        if cand in enriched.columns:
            ts_col = cand
            break
    if ts_col is not None:
        enriched = enriched.copy()
        enriched[ts_col] = pd.to_datetime(enriched[ts_col])

    n_raw = int(pd.read_csv(DEFAULT_OHLCV).shape[0])

    results = {}
    for variant in ("base", "choch"):
        print(f"[3/4] Sequential resolve() pass -- variant={variant!r} ...")
        resolver = CRTStateResolver(variant=variant)
        thr = resolver._config.get("thresholds", {})
        rsi_ob = float(thr.get("rsi_overbought", 70.0))
        rsi_os = float(thr.get("rsi_oversold", 30.0))
        life = thr.get("lifecycle") or {}
        cph = int(life.get("htf_candles_per_range", 4))
        engine_htf_ids = build_htf_id_timeline(n_raw, candles_per_htf=cph, instrument=INSTRUMENT)

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

        res_states, res_sites = _run_resolver_pass(
            resolver, enriched, engine_htf_ids, source_indices,
            CANONICAL_FEATURES, thr, rsi_ob, rsi_os, ts_col,
        )

        engine_states = engine_ctx.timeline.exit_states  # matches run_once's default engine_mode
        report = cm.build_confusion(
            engine_states, res_states, source_indices,
            engine_mode="exit", reference=engine_ctx.reference,
            engine_events=engine_ctx.events, max_episodes=10_000,
            resolution_sites=res_sites,
        )
        results[variant] = {
            "resolver_config": {
                "variant_id": resolver.variant_id,
                "enabled_links": sorted(resolver.enabled_links),
                "required_when_features_count": len(resolver.required_when_features),
            },
            "report": report,
            "per_state": per_state_summary(report),
        }
        print(f"      variant={variant!r}: agreement={report.agreement}/{report.total} "
              f"({report.agreement / report.total:.4%})" if report.total else "      n/a")

    print("[4/4] Comparing base vs choch ...")
    base_ps = results["base"]["per_state"]
    choch_ps = results["choch"]["per_state"]
    ok, violations = anti_simpson_ok(base_ps, choch_ps)

    base_report = results["base"]["report"]
    choch_report = results["choch"]["report"]
    base_agree_pct = base_report.agreement / base_report.total if base_report.total else 0.0
    choch_agree_pct = choch_report.agreement / choch_report.total if choch_report.total else 0.0

    per_state_delta = {}
    for s in sorted(set(base_ps) | set(choch_ps)):
        b = base_ps.get(s, {})
        c = choch_ps.get(s, {})
        per_state_delta[s] = {
            "base": b, "choch": c,
            "resolver_n_delta": (c.get("resolver_n", 0) - b.get("resolver_n", 0))
                if b and c else None,
        }

    n_matrix_cells_changed = sum(
        1 for k in set(base_report.matrix) | set(choch_report.matrix)
        if base_report.matrix.get(k, 0) != choch_report.matrix.get(k, 0)
    )

    verdict_lines = [
        f"base agreement:  {base_report.agreement}/{base_report.total} ({base_agree_pct:.4%})",
        f"choch agreement: {choch_report.agreement}/{choch_report.total} ({choch_agree_pct:.4%})",
        f"agreement delta: {(choch_agree_pct - base_agree_pct):+.4%}",
        f"confusion-matrix cells that changed: {n_matrix_cells_changed}",
        f"anti-Simpson guard (base vs choch, POWERED states only): "
        f"{'PASS' if ok else 'VIOLATIONS: ' + '; '.join(violations)}",
        "AUTHORITY: none. Wiring-phase measurement only (crt_resolver_links.yaml "
        "'no variant is canonical during the wiring phase') -- grants no production "
        "authority regardless of result (CLAUDE.md S6.5).",
    ]
    if n_matrix_cells_changed == 0:
        verdict_lines.append(
            "NULL RESULT: the confusion matrix is byte-identical between base and choch. "
            "The DISPLACEMENT dwell clause this link adds never changes the resolver's "
            "output on this corpus -- either change_of_character rarely/never takes a "
            "non-zero value during DISPLACEMENT dwell here, or (per this session's Phase-A "
            "finding pattern) a different funnel/gate already fully determines these bars "
            "before the when: block is reached. Do not assume a mechanism without reading "
            "results.rows / predicate_affinity -- this script does not attribute a null."
        )

    def _confusion_report_to_dict(r: "cm.ConfusionReport") -> dict:
        return {
            "engine_mode": r.engine_mode,
            "agreement": r.agreement,
            "total": r.total,
            "n_aligned_bars": r.n_aligned_bars,
            "engine_counts": dict(r.engine_counts),
            "resolver_counts": dict(r.resolver_counts),
            "matrix": {f"{k[0]}|{k[1]}": v for k, v in r.matrix.items()},
            "top_confusions": r.top_confusions,
            "residual_site_counts": r.residual_site_counts,
            "residual_pre_predicate": r.residual_pre_predicate,
            "residual_predicate_derived": r.residual_predicate_derived,
            "residual_site_unattributed": r.residual_site_unattributed,
        }

    out = {
        "probe": "link001_choch_measurement",
        "purpose": "measure whether binding LINK-001 (change_of_character on "
                   "DISPLACEMENT) changes resolver/engine agreement vs base; "
                   "wiring-phase only, grants no authority regardless of result",
        "ohlcv": str(DEFAULT_OHLCV),
        "events": str(DEFAULT_EVENTS),
        "base": {
            "resolver_config": results["base"]["resolver_config"],
            "report": _confusion_report_to_dict(base_report),
            "per_state": base_ps,
        },
        "choch": {
            "resolver_config": results["choch"]["resolver_config"],
            "report": _confusion_report_to_dict(choch_report),
            "per_state": choch_ps,
        },
        "per_state_delta": per_state_delta,
        "anti_simpson": {"ok": ok, "violations": violations},
        "verdict": verdict_lines,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2, sort_keys=False, default=str), encoding="utf-8")
    print(f"\nWrote {OUT_JSON}")
    print("\n".join(verdict_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

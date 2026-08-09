#!/usr/bin/env python
"""story_library_build.py — generate the ERP market-STORY golden library (P1 slice).

For every registered StorySpec (research.synthetic.story_registry), builds the intended-vs-produced
trace + six-layer ontology binding and writes deterministic fixtures under
data/synthetic/stories/<story_id>/:
    <ID>.csv              — OHLCV input artifact
    intended_spec.json    — design ground truth + six-layer expectations
    produced_compare.json — what the real engines / forward_walk produced + the binding result
    NARRATIVE.md          — human narration
plus an aggregate data/synthetic/stories/INDEX.json.

Trust: outputs are research fixtures — UNTRUSTED_RAW until flow review (D-04). This grants NO
runtime or promotion authority (§6.5). Geometry lives in CODE (D-23): to change a story, edit its
StorySpec under src/research/synthetic/stories/ and re-run.

Usage:
  PYTHONPATH=src python scripts/research/story_library_build.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))

from research.synthetic.ontology import StoryOntology  # noqa: E402
from research.synthetic.story_builder import build_story  # noqa: E402
from research.synthetic.story_registry import all_stories  # noqa: E402
from utils.run_manifest import build_manifest, write_run  # noqa: E402

OUT_DIR = _ROOT / "data" / "synthetic" / "stories"


def _intended_spec(spec, r: dict) -> dict:
    return {
        "schema_version": "1.0",
        "id": r["id"], "family": r["family"], "instrument": r["instrument"],
        "timeframe": r["timeframe"], "story": r["story"],
        "design_principle": "deterministic_scripted_geometry_not_random",
        "warmup_bars": r["warmup_bars"], "event_bars": r["event_bars"],
        "entry_index": r["entry_index"], "direction": r["direction"],
        "geometry": r["geometry"],
        "engines_intended": r["engines_intended"],
        "expected": {
            "market_states": list(spec.expected_market_states),
            "crt_states": list(spec.expected_crt_states),
            "feature_signature": list(spec.expected_feature_signature),
            "engine_signature": dict(spec.expected_engine_signature),
            "outcome": spec.expected_outcome,
            "rr_min": spec.expected_rr_min,
        },
        "bars": r["bars"],
    }


def _produced_compare(r: dict) -> dict:
    return {
        "id": r["id"],
        "engines_produced": r["engines_produced"],
        "engines_match": r["engines_match"],
        "outcome": r["outcome"],
        "checks": r["checks"],
        "all_critical_pass": r["all_critical_pass"],
        "ontology_binding": r["ontology_binding"],
        "trust": "UNTRUSTED_RAW until flow review (D-04); no runtime/promotion authority",
    }


def _narrative(spec, r: dict) -> str:
    b = r["ontology_binding"]
    lines = [
        f"# Story `{r['id']}` — {r['family']}",
        "",
        f"> {r['story']}",
        f"> Instrument `{r['instrument']}` · {r['timeframe']} · warmup {r['warmup_bars']} + "
        f"{r['event_bars']} event bars.",
        f"> Critical compare: **{'PASS' if r['all_critical_pass'] else 'FAIL'}** · "
        f"Six-layer binding: **{'PASS' if b['all_pass'] else 'FAIL'}**",
        "",
        "## Six-layer ontology binding",
        "",
        "| Layer | Pass |",
        "|---|---|",
    ]
    for k, v in b["layers"].items():
        lines.append(f"| {k} | {'PASS' if v['pass'] else 'FAIL'} |")
    lines += [
        "",
        "## Engine signature (produced vs declared band)",
        "",
        "| Engine | Value | Declared | Produced band |",
        "|---|---|---|---|",
    ]
    for e, d in b["layers"]["l5_engine_signature"]["engines"].items():
        lines.append(f"| {e} | {d['value']} | {d['expected']} | {d['produced']} |")
    lines += [
        "",
        "## Outcome (governing forward_walk, intrabar_fixed)",
        "",
        f"- outcome: **{r['outcome']['outcome']}** · rr_achieved: {r['outcome']['rr_achieved']} · "
        f"time_to_tp: {r['outcome']['time_to_tp']} · duration: {r['outcome']['duration_candles']}",
        "",
        "## CRT skeleton path (semantic -> executable)",
        "",
        f"- derived: `{b['layers']['l3_crt_states']['derived']}` (legal walk: "
        f"{b['layers']['l3_crt_states']['legal_walk']})",
        "",
        "> Research fixture — UNTRUSTED_RAW until flow review; grants no runtime/promotion authority.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    onto = StoryOntology()
    index = []
    all_pass = True
    for spec in all_stories():
        r = build_story(spec, onto)
        sdir = OUT_DIR / r["id"]
        sdir.mkdir(parents=True, exist_ok=True)
        r["df"].to_csv(sdir / f"{r['id'].upper()}.csv", index=False)
        (sdir / "intended_spec.json").write_text(
            json.dumps(_intended_spec(spec, r), indent=2), encoding="utf-8")
        (sdir / "produced_compare.json").write_text(
            json.dumps(_produced_compare(r), indent=2), encoding="utf-8")
        (sdir / "NARRATIVE.md").write_text(_narrative(spec, r), encoding="utf-8")

        story_ok = bool(r["all_critical_pass"] and r["ontology_binding"]["all_pass"])
        all_pass = all_pass and story_ok
        index.append({
            "id": r["id"], "family": r["family"], "outcome": r["outcome"]["outcome"],
            "rr_achieved": r["outcome"]["rr_achieved"],
            "all_critical_pass": r["all_critical_pass"],
            "ontology_binding_all_pass": r["ontology_binding"]["all_pass"],
        })
        print(f"{'PASS' if story_ok else 'FAIL'}  {r['id']:<34} "
              f"CRITICAL={r['all_critical_pass']} BINDING={r['ontology_binding']['all_pass']} "
              f"OUT={r['outcome']['outcome']}")

    (OUT_DIR / "INDEX.json").write_text(
        json.dumps({"n": len(index), "all_pass": all_pass, "stories": index}, indent=2),
        encoding="utf-8")

    # ── provenance manifest (ERP testing-plan §3.3; first real producer, WI-002) ──────────
    assertions = {
        "n_stories": len(index),
        "library_all_pass": all_pass,
        "outcome_coverage": sorted({s["outcome"] for s in index}),
        "active_families": sorted({s["family"] for s in index}),
        "per_story_pass": {s["id"]: bool(s["all_critical_pass"]
                                         and s["ontology_binding_all_pass"]) for s in index},
    }
    manifest = build_manifest(
        command="python scripts/research/story_library_build.py",
        argv=sys.argv,
        validation_lens="synthetic_story_golden",
        exit_model="intrabar_fixed",
        cost_model_bps=0,
        label_source="forward_walk_intrabar_fixed",
        instruments=["SYNTHUSDT"],
        timeframe="M15",
        data_source="synthetic",
        network="none",
        dry_run=True,
        intended_work_item_id="WI-002",
    )
    written = write_run(OUT_DIR, manifest, assertions)

    print(f"\nWrote {len(index)} stories to {OUT_DIR}")
    print(f"Wrote run_manifest ({written['sha256'][:16]}…) to {OUT_DIR}")
    print(f"LIBRARY_ALL_PASS={'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""htf_parent_telemetry_extract.py — structured HTF/parent-CRT telemetry for the
Monthly TradingView <-> Active Production Semantic Comparison Report.

WHAT THIS CLOSES
-----------------
`ParentCRTFeed.push()` (`src/runtime/parent_crt_feed.py`) computes `.bias` /
`.htf_state` / `.objective` on EVERY closed H4 parent, but only logs
(`logger.info(...)`) when `self._track.state != prev` — i.e. only on a C1/C2/C3
state transition. `htf_state` and `objective` continuity BETWEEN transitions
(e.g. an H4 close that stays in DISTRIBUTION_C3 but has its objective flip from
EXISTS to ACHIEVED) has never been persisted anywhere. This script drives
`ParentCRTFeed` directly and reads all three properties after every single
`push()` that returns True, emitting one JSONL row per H4 close regardless of
whether the C1/C2/C3 state changed.

No production code is touched: this reads `.bias`/`.htf_state`/`.objective`
from the existing feed exactly as `backtest_v2.py` does; it does not change
what the feed computes, only what gets persisted for research use.

SECOND JOB (--with-ohlc-check): aggregate the OHLC/clock reconciliation that
`tools/tv_forensic/capture_tv.py` ALREADY computed and stored in each M15
shot's own sidecar JSON (`engine_vs_tv.summary`, `clock.resolved_offset_hours/
decisive`) at capture time. This is deliberately NOT a re-run of
`tools/tv_forensic/engine_data.py`'s `diff_table`/`resolve_offset` — those
assume a 15-minute bar step (`diff_table`'s cursor increments by
`timedelta(minutes=15)` unconditionally), which would be wrong on the H4
shots. Reading each M15 sidecar's own already-verified summary avoids
reintroducing that bug and is strictly more faithful reuse than recomputing.

CORRECTED (2026-08-16): this docstring previously claimed "the sidecars' own
capture-time computation already used the correct per-shot interval" for the
H4 shots too. That was false, and was never checked against source before
being written — `tools/tv_forensic/capture_tv.py`'s `if str(shot.interval) ==
"15":` guard means there IS NO capture-time OHLC/clock computation for an H4
shot at any interval; the diff is skipped entirely, not computed differently.
Both H4 sidecars (03_h4_jul27_31.json, 09_h4_jul15_20.json) had no
`engine_vs_tv` key at all, which this script's rollup then silently summed as
zero bars/zero divergent instead of reporting as unreconciled. Fixed to read
the NOT_APPLICABLE marker `capture_tv.py` now writes for skipped shots
(D-1 in the semantic+screenshot layer review) and to report unreconciled
shots explicitly, never as silent zeros.

WHAT THIS IS NOT
-----------------
Not a new capture (no Playwright, no network call — reads existing files
under tools/tv_forensic/shots/ only). Not a promotion mechanism — never
writes to configs/production/ or ACTIVE_VERSION. Not an OFF-vs-ON shadow
(there is only one config under test: whatever ACTIVE_VERSION currently is).

USAGE
-----
    venv\\Scripts\\python.exe scripts/research/htf_parent_telemetry_extract.py \\
        --csv data/XAUUSD_M15.csv --instrument XAUUSD --with-ohlc-check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

DEFAULT_CSV = "data/XAUUSD_M15.csv"
DEFAULT_OUT_DIR = "results/monthly_tv_semantic_report"
SHOTS_DIR = _ROOT / "tools" / "tv_forensic" / "shots"

# F-077's own published number for this exact corpus (docs/current-findings.md:1154,
# "84 M15 episodes / 15 H4 C3s / 2 RETESTs" against
# results/htfcrt_1month_parent_wired/run_20260816_011239_XAUUSD). A mismatch here means
# this script's harness (candle stream / guard patch / ParentCRTFeed wiring) is wrong,
# not that the corpus changed underneath it.
EXPECTED_DISTRIBUTION_C3_CLOSES = 15


def _extract_telemetry(csv_path: str, instrument: str) -> list[dict]:
    # Process-local CSV scope only (mirrors scripts/research/htf_objective_gate_shadow.py):
    # the Phase-1 XAUUSD guard rewrites any XAUUSD_M15* path to the 2-year frozen candidate;
    # identity-patched here so the one-month corpus streams as-is. Production guard on disk
    # is untouched.
    import runtime.backtest_v2 as bt
    bt.guard_xauusd_csv_path = lambda fp, instrument="", **kw: str(fp)

    from runtime.parent_crt_feed import ParentCRTFeed

    feed = ParentCRTFeed.from_prod_config()
    if feed is None:
        raise RuntimeError(
            "parent_crt.enabled is false on the active config — nothing to extract. "
            "This script measures what the ACTIVE config computes; it does not flip gates."
        )

    loader = bt.CandleLoader(csv_path, instrument)
    rows: list[dict] = []
    for candle in loader.stream():
        closed = feed.push(candle)
        if not closed:
            continue
        parent = feed.track.range  # ParentRange | None (C1 reference), not the OHLC we want
        # feed.push() advances the builder internally; the just-closed parent OHLC is not
        # re-exposed by ParentCRTFeed itself (by design — see its no-lookahead docstring),
        # so we read it back off the same builder the feed owns.
        parent_candle = feed._builder.parent_candle  # noqa: SLF001 — read-only introspection,
        # not a supported public API; acceptable in a research script that must not modify
        # src/runtime/parent_crt_feed.py just to expose a getter for one report.
        rows.append({
            "h4_close_ts": parent_candle.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "h4_close_index": parent_candle.index,
            "parent_ohlc": {
                "open": parent_candle.open, "high": parent_candle.high,
                "low": parent_candle.low, "close": parent_candle.close,
            },
            "track_state": feed.state.name,
            "bias": feed.bias.value,
            "htf_state": feed.htf_state.value,
            "objective_status": feed.objective.status.value,
            "objective_direction": feed.objective.direction.value,
        })
    return rows


def _ohlc_clock_reconciliation() -> dict:
    # Exclude _ANNOTATED sidecars (a different schema, see annotate.py) and any
    # _PRE_* backup snapshot (D-1/D-6 write these before mutating a base sidecar
    # in place, per CLAUDE.md 6.2 rule 4 — they must never be double-counted as
    # if they were additional captured shots).
    sidecars = sorted(
        p for p in SHOTS_DIR.glob("*.json")
        if not p.stem.endswith("_ANNOTATED") and "_PRE_" not in p.stem
    )
    per_shot = []
    unreconciled_shots: list[str] = []
    for p in sidecars:
        d = json.loads(p.read_text(encoding="utf-8"))
        shot = d.get("shot", {})
        clock = d.get("clock", {})
        evt = d.get("engine_vs_tv") or {}
        summary = evt.get("summary")
        # D-1: read the explicit status capture_tv.py now writes (OK / DIVERGENT /
        # NOT_APPLICABLE) instead of inferring meaning from an absent key. A sidecar
        # captured before this fix and not yet backfilled falls through to
        # "UNKNOWN_NOT_RECORDED" — reported honestly, never silently summed as zero.
        status = evt.get("status")
        if status is None:
            status = "UNKNOWN_NOT_RECORDED" if summary is None else "OK_LEGACY_UNMARKED"
        name = shot.get("name", p.stem)
        if summary is None:
            unreconciled_shots.append(name)
        per_shot.append({
            "shot": name,
            "symbol": shot.get("symbol"),
            "interval_min": shot.get("interval"),
            "window": f"{shot.get('start')} -> {shot.get('end')} ({shot.get('clock')})",
            "resolved_offset_hours": clock.get("resolved_offset_hours"),
            "clock_decisive": clock.get("decisive"),
            "engine_vs_tv_status": status,
            "engine_vs_tv_reason": evt.get("reason"),
            "engine_vs_tv_summary": summary,
        })
    total_compared = sum((s["engine_vs_tv_summary"] or {}).get("compared", 0) for s in per_shot)
    total_divergent = sum((s["engine_vs_tv_summary"] or {}).get("divergent", 0) for s in per_shot)

    # D-11: report the defined-vs-captured delta instead of leaving it None for a
    # caller to fill in — nobody did. Ground truth is shot_plan.json's own `shots`
    # dict; a shot missing from disk (h4_july_macro/h4_july_setup as of this
    # review) is named explicitly, not silently absent from every downstream count.
    plan_path = _ROOT / "tools" / "tv_forensic" / "shot_plan.json"
    defined_names: list[str] = []
    never_captured: list[str] = []
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        defined_names = sorted(v["name"] for v in plan.get("shots", {}).values())
        captured_names = {s["shot"] for s in per_shot}
        never_captured = sorted(n for n in defined_names if n not in captured_names)

    return {
        "note": (
            "Aggregated from the pre-computed engine_vs_tv/clock blocks already stored in "
            "each tools/tv_forensic/shots/*.json sidecar at capture time — NOT re-run here "
            "(diff_table is M15-only; a non-M15 shot's engine_vs_tv.status is "
            "NOT_APPLICABLE by construction, not silently absent — see capture_tv.py's "
            "run_shot, D-1 fix, 2026-08-16 semantic+screenshot layer review)."
        ),
        "shots_found_on_disk": len(per_shot),
        "shots_defined_in_shot_plan": len(defined_names) if defined_names else None,
        "shots_never_captured": never_captured,
        "unreconciled_shots": unreconciled_shots,
        "per_shot": per_shot,
        "rollup": {
            "total_bars_compared": total_compared,
            "total_divergent": total_divergent,
            "any_divergent": total_divergent > 0,
            "note": (
                f"Sums only shots with an actual engine_vs_tv.summary "
                f"({len(per_shot) - len(unreconciled_shots)}/{len(per_shot)} captured shots). "
                f"{len(unreconciled_shots)} shot(s) unreconciled: {unreconciled_shots}."
            ),
        },
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument("--with-ohlc-check", action="store_true", default=False)
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = _extract_telemetry(args.csv, args.instrument)
    telemetry_path = out_dir / "htf_parent_telemetry.jsonl"
    with telemetry_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")

    from collections import Counter
    state_counts = Counter(r["track_state"] for r in rows)
    dist_c3 = state_counts.get("DISTRIBUTION_C3", 0)
    non_vacuous = dist_c3 == EXPECTED_DISTRIBUTION_C3_CLOSES

    print(f"[OK] wrote {len(rows)} H4-close rows -> {telemetry_path}")
    print(f"[STATE COUNTS] {dict(state_counts)}")
    print(
        f"[NON-VACUITY CHECK] DISTRIBUTION_C3 closes = {dist_c3} "
        f"(expected {EXPECTED_DISTRIBUTION_C3_CLOSES}, per F-077 on this exact corpus): "
        f"{'PASS' if non_vacuous else 'FAIL - HARNESS BUG, DO NOT TRUST DOWNSTREAM ROWS'}"
    )

    if args.with_ohlc_check:
        recon = _ohlc_clock_reconciliation()
        recon_path = out_dir / "ohlc_clock_reconciliation.json"
        recon_path.write_text(json.dumps(recon, indent=2), encoding="utf-8")
        print(f"[OK] wrote OHLC/clock reconciliation -> {recon_path}")
        print(f"[ROLLUP] {recon['rollup']}")

    print("[SCOPE] Read-only. No configs/production/ file or ACTIVE_VERSION was touched.")
    return 0 if non_vacuous else 1


if __name__ == "__main__":
    raise SystemExit(main())

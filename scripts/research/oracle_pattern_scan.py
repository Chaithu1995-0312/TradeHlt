"""oracle_pattern_scan.py — Stage 3 of the profitable-entry oracle program.

Asks the question the program exists for: at the bars where a trade would have been
profitable, is any declared feature or state reconstructing a pattern?

Runs three levels on TRAIN ONLY:

  L1  marginal      per continuous feature, does it order the outcome at all (AUC), and
                    is the ordering worth anything (top-decile expectancy)?
  L2  conditional   per declared state family and cell, expectancy against the
                    DIRECTION-MATCHED base rate.
  L3  conjunction   depth<=3 combinations of state literals, pruned by effective support.

TRAIN ONLY IS NOT A STYLE CHOICE. The test partition is touched exactly once, at Stage 4,
after candidate patterns are frozen. Mining and evaluating on the same rows would make
every number here a description of noise.

PRECONDITION: the Stage 0.5 harness gate must have PASSED. Without it a null from this
script means "harness unproven", not "no information", and the script refuses to run
rather than emit a number that would be read the wrong way.

Research/diagnostic only. Produces effect sizes, never verdicts: no promotion, no fusion
weight, no G001.

Usage:
    python scripts/research/oracle_pattern_scan.py --split train
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from research.oracle.scan import (  # noqa: E402
    DEFAULT_HORIZON,
    controls,
    effective_n,
    l1_marginal,
    l2_state_cells,
    l3_conjunctions,
    l3_permutation_null,
    partition,
    state_columns,
)

# Raw OHLCV slots. They are declared vector members so they are measured, but a price
# LEVEL on a trending instrument encodes the calendar: a high AUC on `close` means the
# corpus drifted, not that price level predicts anything. Flagged, never silently dropped.
_PRICE_LEVEL_SLOTS = ("open", "high", "low", "close", "volume")

# Known-contaminated inputs, carried from the plan. Results on these are annotated at the
# point of use rather than left for a reader to remember.
_CONTAMINATION_NOTES = {
    "session": "broker-clock mislabel risk (session_timestamp_basis=broker_local)",
    "hour_of_day": "broker-clock mislabel risk (session_timestamp_basis=broker_local)",
    "state__session": "broker-clock mislabel risk (session_timestamp_basis=broker_local)",
    "ema_spread": "FM-022 dimensional mix: saturates, may look inert for a units reason",
    "momentum_score": "FM-023 dimensional mix: saturates, may look inert for a units reason",
    "state__momentum_magnitude": "derived from FM-023, which saturates on this basis",
    "crt_state_resolved": "declarative resolver, NOT the CRT engine; see harness report",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--instrument", default="XAUUSD")
    ap.add_argument("--timeframe", default="M15")
    ap.add_argument("--sl-geom", default="disp_bar")
    ap.add_argument("--tie-break", default="production")
    ap.add_argument("--split", default="train", choices=["train", "test_stride"])
    ap.add_argument("--y-value", default="y_R_net", choices=["y_R_net", "y_R_gross"])
    ap.add_argument("--y-binary", default="y_win", choices=["y_win", "y_win_gross"])
    ap.add_argument("--horizon", type=int, default=DEFAULT_HORIZON)
    ap.add_argument("--min-eff-n", type=int, default=30)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--permutation-null", type=int, default=0,
                    help="permutations for the L3 conjunction null (0 = skip). This is "
                         "the control that turns a raw 'beats base' count into a claim.")
    ap.add_argument("--allow-unproven-harness", action="store_true",
                    help="run without a PASSing Stage 0.5 gate; results are NOT interpretable")
    args = ap.parse_args(argv)

    tag = f"{args.instrument}_{args.timeframe}"
    matrix_csv = _ROOT / "results" / "research" / "bar_matrix" / tag / "bar_matrix.csv"
    labels_csv = _ROOT / "results" / "research" / "oracle_labels" / tag / "labels.csv"
    harness_json = _ROOT / "results" / "research" / "oracle_harness" / tag / "harness_report.json"
    out_dir = Path(args.out_dir) if args.out_dir else (
        _ROOT / "results" / "research" / "oracle_scan" / tag)
    out_dir.mkdir(parents=True, exist_ok=True)

    for p in (matrix_csv, labels_csv):
        if not p.exists():
            print(f"[FATAL] missing {p}")
            return 2

    # ── Stage 0.5 precondition ───────────────────────────────────────────────
    harness = None
    if harness_json.exists():
        harness = json.loads(harness_json.read_text(encoding="utf-8"))
    if not args.allow_unproven_harness:
        if harness is None:
            print("[FATAL] no harness report. Run validate_oracle_harness.py first;\n"
                  "        without it a null here is 'harness unproven', not 'no information'.")
            return 2
        if harness.get("gate") != "PASS":
            print(f"[FATAL] harness gate is {harness.get('gate')}, not PASS. Refusing to "
                  "emit numbers that would be read as a negative result.")
            return 2

    matrix = pd.read_csv(matrix_csv, parse_dates=["timestamp"])
    labels = pd.read_csv(labels_csv, parse_dates=["timestamp"])
    arm = labels[(labels["sl_geom"] == args.sl_geom)
                 & (labels["tie_break"] == args.tie_break)]
    if arm.empty:
        print("[FATAL] arm selection is empty")
        return 2

    drop = [c for c in matrix.columns if c in arm.columns and c != "_pos"]
    joined = arm.merge(matrix.drop(columns=drop), on="_pos", how="inner")
    if len(joined) != len(arm):
        print(f"[FATAL] join lost rows: {len(arm)} -> {len(joined)}")
        return 2

    part = partition(joined, embargo_bars=96, horizon=args.horizon)
    work = part.train if args.split == "train" else part.test_stride
    if work.empty:
        print("[FATAL] selected split is empty")
        return 2

    feature_cols = [c for c in CANONICAL_FEATURES if c in work.columns]
    if "atr_abs" in work.columns:
        feature_cols.append("atr_abs")
    state_cols = state_columns(work)

    report: dict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "instrument": args.instrument,
        "arm": {"sl_geom": args.sl_geom, "tie_break": args.tie_break},
        "split": args.split,
        "y_value": args.y_value,
        "y_binary": args.y_binary,
        "partition": part.meta,
        "harness_gate": (harness or {}).get("gate", "ABSENT"),
        "authority": "research_diagnostic_only",
        "economic_claims_allowed": False,
        "multiplicity": {
            "features_scanned": len(feature_cols),
            "state_families_scanned": len(state_cols),
            "arms_declared": 4,
            "primary_arm": "disp_bar|production",
            "note": ("The other three arms are declared robustness checks, not three "
                     "extra opportunities for significance. Any candidate must hold on "
                     "the primary arm."),
        },
        "contamination_notes": _CONTAMINATION_NOTES,
        "price_level_slots": list(_PRICE_LEVEL_SLOTS),
        "per_direction": {},
    }

    print(f"\n  ARM {args.sl_geom}|{args.tie_break}  SPLIT={args.split}  "
          f"y={args.y_value}  harness={report['harness_gate']}")
    print(f"  partition: train {part.meta['train_bars']} bars | "
          f"test_stride {part.meta['test_bars_stride']} bars "
          f"(dense {part.meta['test_bars_dense']}, embargo {part.meta['embargo_bars']})")

    # Controls are computed on the FULL arm, both directions together. Computed inside a
    # single-direction slice, `long_only` is trivially identical to that slice's own base
    # rate and benchmarks nothing — the point of the control is that a long-side pattern
    # must beat passive LONG exposure, which only exists as a comparison across the arm.
    arm_controls = controls(work, y_value=args.y_value, horizon=args.horizon,
                            n_boot=args.n_boot, seed=args.seed)
    report["arm_controls"] = arm_controls
    long_only_R = arm_controls.get("long_only", {}).get("mean_R")
    print(f"  arm controls: long_only {long_only_R}  "
          f"short_only {arm_controls.get('short_only', {}).get('mean_R')}  "
          f"random {arm_controls['random_entry']['mean_R']}  "
          f"shuffled {arm_controls['shuffled_label']['mean_R']}")

    for direction in ("long", "short"):
        d = work[work["direction"] == direction].reset_index(drop=True)
        if d.empty:
            continue
        eff = effective_n(d, horizon=args.horizon)
        ctl = arm_controls
        kw = dict(y_binary=args.y_binary, y_value=args.y_value,
                  horizon=args.horizon, n_boot=args.n_boot, seed=args.seed)
        l1 = l1_marginal(d, feature_cols, **kw)
        l2 = l2_state_cells(d, state_cols, min_eff_n=args.min_eff_n, **kw)
        l3 = l3_conjunctions(d, state_cols, y_value=args.y_value, y_binary=args.y_binary,
                             horizon=args.horizon, min_eff_n=args.min_eff_n,
                             n_boot=max(200, args.n_boot // 2), seed=args.seed)

        base = float(l1.attrs["base_mean_R"])
        l1.to_csv(out_dir / f"l1_marginal_{direction}_{args.split}.csv", index=False)
        l2.to_csv(out_dir / f"l2_states_{direction}_{args.split}.csv", index=False)
        if len(l3):
            l3.to_csv(out_dir / f"l3_conjunctions_{direction}_{args.split}.csv", index=False)

        l2_ok = l2[l2["status"] == "OK"]
        survivors_l2 = l2_ok[l2_ok["beats_base"]]
        # The economically meaningful bar. The base rate is cost-dominated and deeply
        # negative, so "beats base" can mean "loses less"; only "beats zero" is an edge.
        profitable_l2 = l2_ok[l2_ok["beats_zero"]]
        beat_long_only_l2 = l2_ok[l2_ok["ci_lo"] > (long_only_R or 0.0)]
        survivors_l3 = l3[l3["beats_base"]] if len(l3) else l3
        l3_total = int(l3.attrs.get("total_scored", len(l3)))
        l3_beat_zero = int(l3.attrs.get("total_beating_zero", 0))
        l3_beat_base = int(l3.attrs.get("total_beating_base", 0))
        l3_expected = l3.attrs.get("expected_beating_base_by_chance", 0.0)

        report["per_direction"][direction] = {
            "rows": int(len(d)),
            "effective_n": eff,
            "base_mean_R": round(base, 5),
            "base_win_rate": round(float(d[args.y_binary].mean()), 5),
            "controls": ctl,
            "l1_top": l1.head(8).to_dict("records"),
            "l1_features_beating_base": int(l1["top_beats_base"].sum())
            if "top_beats_base" in l1 else 0,
            "l2_cells_total": int(len(l2)),
            "l2_cells_sufficient": int(len(l2_ok)),
            "l2_cells_beating_base": int(len(survivors_l2)),
            "l2_cells_beating_zero": int(len(profitable_l2)),
            "l2_cells_beating_long_only": int(len(beat_long_only_l2)),
            "l2_top": l2_ok.head(8).to_dict("records"),
            "l3_patterns_scored_total": l3_total,
            "l3_patterns_reported": int(len(l3)),
            "l3_patterns_beating_base": int(len(survivors_l3)),
            "l3_patterns_beating_zero": l3_beat_zero,
            "l3_patterns_beating_base": l3_beat_base,
            "l3_expected_beating_base_by_chance": l3_expected,
            "l3_selection_note": (
                f"{l3_total} conjunctions were scored and the top {len(l3)} by lift are "
                f"reported; the leaderboard is a selection artifact, the counts are the "
                f"result. {l3_beat_base} clear the BASE rate against roughly {l3_expected} "
                f"expected by chance at a 95% interval. {l3_beat_zero} clear ZERO, which "
                f"is the economically meaningful bar — but note the base is far below "
                f"zero, so a low count there reflects the cost-dominated base rate and is "
                f"not by itself evidence of a strong null."),
            "l3_top": l3.head(8).to_dict("records") if len(l3) else [],
        }

        if args.permutation_null > 0:
            pn = l3_permutation_null(
                d, state_cols, y_value=args.y_value, y_binary=args.y_binary,
                horizon=args.horizon, min_eff_n=args.min_eff_n,
                n_perm=args.permutation_null, n_boot=max(200, args.n_boot // 5),
                seed=args.seed)
            report["per_direction"][direction]["l3_permutation_null"] = pn
            print(f"   L3 permutation null ({pn['n_perm']} perms): real "
                  f"{pn['real_beating_base']} beat base vs permuted "
                  f"{pn['perm_beating_base']} (mean {pn['perm_beating_base_mean']}), "
                  f"excess x{pn['excess_ratio_base']}")
            print(f"      beats ZERO: real {pn['real_beating_zero']} vs permuted "
                  f"{pn['perm_beating_zero']}")

        print(f"\n  --- {direction.upper()} | rows {len(d)} | effective n {eff} ---")
        print(f"   base   E={base:+.4f}R  win={d[args.y_binary].mean():.3f}")
        print("   L1 strongest by |AUC-0.5|:")
        for r in l1.head(5).to_dict("records"):
            note = _CONTAMINATION_NOTES.get(r["feature"], "")
            flag = " [PRICE-LEVEL]" if r["feature"] in _PRICE_LEVEL_SLOTS else ""
            note = f"  <{note}>" if note else ""
            print(f"     {r['feature']:26s} AUC={r.get('auc')}  "
                  f"top-decile {r.get('top_decile_mean_R')}R "
                  f"[{r.get('top_decile_lo')},{r.get('top_decile_hi')}]"
                  f"{flag}{note}")
        print(f"   L2 cells: {len(l2_ok)} sufficient of {len(l2)}; "
              f"{len(survivors_l2)} beat base; {len(profitable_l2)} beat ZERO; "
              f"{len(beat_long_only_l2)} beat long_only")
        for r in survivors_l2.head(5).to_dict("records"):
            print(f"     {r['family']}={r['cell']:22s} n={r['n']:5d} eff={r['eff_n']:4d} "
                  f"E={r['mean_R']:+.4f}R lift={r['lift_R']:+.4f} "
                  f"CI[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}]")
        print(f"   L3: {l3_total} conjunctions scored | {l3_beat_base} clear BASE "
              f"vs ~{l3_expected:.0f} expected by chance | {l3_beat_zero} clear ZERO "
              f"(top {len(l3)} shown; leaderboard is selection, counts are the result)")
        for r in survivors_l3.head(5).to_dict("records"):
            print(f"     {r['pattern'][:70]:70s} n={r['n']:5d} eff={r['eff_n']:4d} "
                  f"E={r['mean_R']:+.4f}R CI[{r['ci_lo']:+.4f},{r['ci_hi']:+.4f}]")

    (out_dir / f"scan_report_{args.split}.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\n  report -> {out_dir / f'scan_report_{args.split}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

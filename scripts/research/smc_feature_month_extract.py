"""smc_feature_month_extract.py — SMC (smart-money-concepts) feature spot-validation
for the Monthly TradingView <-> Active Production Semantic Comparison Report.

WHAT THIS CLOSES
-----------------
Schema v5.0 (`src/features/feature_schema.py`) added 9 SMC primitives at vector
indices 39-47: order_block_distance, fvg_distance, breaker_distance,
mitigation_block_distance, pdh_distance, pdl_distance, eqh_distance, eql_distance,
change_of_character. F-076 already establishes they are computed but decision-
UNREACHABLE (every consuming model family is stale). No existing tooling maps
their VALUES back to a chart a human could look at — this script is that
first cross-reference, deliberately scoped to only the windows already
captured by tools/tv_forensic (no new browser capture — see the report this
feeds for that scoping decision).

METHOD
------
Run `FeaturePipeline(df).run()` end-to-end over the one-month CSV (the same
call path production/backtest code uses, `compute_smc_features()` included —
`feature_pipeline.py` `run()` already calls it after `compute_canonical_session()`).
Filter to rows where at least one of the 9 columns is nonzero ("active" — the
columns default to 0.0 via `np.zeros` init, not NaN, so this is a real signal,
not a warmup artifact). Intersect those active rows against the exact windows
of the tv_forensic shots that actually have a captured PNG+JSON on disk (read
from the sidecars themselves, not from shot_plan.json's aspirational full
list — two of shot_plan.json's nine defined shots, h4_july_macro and
h4_july_setup, were never actually captured; this script does not claim
coverage that doesn't exist).

A feature with ZERO active instances inside the reused windows is reported as
"not observed in the reused sample window" — an honest null, not omitted and
not stretched into "verified absent."

WHAT THIS IS NOT
-----------------
Not a decision-path change — nothing here wires SMC features into any gate
(F-076 covers why they're unused; out of scope to change). Not a new capture.
Never writes to configs/production/ or ACTIVE_VERSION.

USAGE
-----
    venv\\Scripts\\python.exe scripts/research/smc_feature_month_extract.py \\
        --csv data/XAUUSD_M15.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

DEFAULT_CSV = "data/XAUUSD_M15.csv"
DEFAULT_OUT = "results/monthly_tv_semantic_report/smc_feature_month.json"
SHOTS_DIR = _ROOT / "tools" / "tv_forensic" / "shots"

SMC_COLUMNS = [
    "order_block_distance", "fvg_distance", "breaker_distance",
    "mitigation_block_distance", "pdh_distance", "pdl_distance",
    "eqh_distance", "eql_distance", "change_of_character",
]


def _captured_shot_windows() -> dict:
    """Windows for shots that actually have a sidecar JSON on disk (ground truth,
    not shot_plan.json's aspirational list — see module docstring)."""
    windows = {}
    for p in sorted(SHOTS_DIR.glob("*.json")):
        if p.stem.endswith("_ANNOTATED"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        shot = d.get("shot", {})
        windows[shot["name"]] = {
            "start": shot["start"], "end": shot["end"],
            "symbol": shot.get("symbol"), "interval_min": shot.get("interval"),
        }
    return windows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", default=DEFAULT_CSV)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    from features.feature_pipeline import FeaturePipeline

    df = pd.read_csv(args.csv)
    total_bars = len(df)

    pipeline = FeaturePipeline(df)
    enriched_df, _vectors = pipeline.run()
    bars_after_warmup_trim = len(enriched_df)

    missing = [c for c in SMC_COLUMNS if c not in enriched_df.columns]
    if missing:
        raise RuntimeError(
            f"SMC columns missing from FeaturePipeline output: {missing}. "
            "Schema v5.0 / compute_smc_features() may not be wired — stop, this "
            "invalidates every downstream row in this extraction."
        )

    active_mask = (enriched_df[SMC_COLUMNS] != 0).any(axis=1)
    active = enriched_df.loc[active_mask, ["timestamp"] + SMC_COLUMNS]

    windows = _captured_shot_windows()

    per_feature = {}
    for col in SMC_COLUMNS:
        col_active = enriched_df.loc[enriched_df[col] != 0, ["timestamp", col]]
        hits_by_shot = {}
        n_in_windows = 0
        for shot_name, w in windows.items():
            in_window = col_active[
                (col_active["timestamp"] >= w["start"]) & (col_active["timestamp"] <= w["end"])
            ]
            hits = [
                {"timestamp": str(row["timestamp"]), "value": float(row[col])}
                for _, row in in_window.iterrows()
            ]
            hits_by_shot[shot_name] = hits
            n_in_windows += len(hits)
        per_feature[col] = {
            "n_active_total_month": int(len(col_active)),
            "n_active_in_reused_shot_windows": n_in_windows,
            "status": (
                "observed_in_reused_window" if n_in_windows > 0
                else "not_observed_in_reused_sample_window"
            ),
            "hits_by_shot": hits_by_shot,
        }

    out = {
        "schema_version": "5.0",
        "csv": args.csv,
        "total_bars": total_bars,
        "bars_after_warmup_trim": bars_after_warmup_trim,
        "n_bars_any_smc_active": int(active_mask.sum()),
        "shot_windows_used": windows,
        "shot_windows_note": (
            f"{len(windows)} windows read from actually-captured sidecars under "
            f"tools/tv_forensic/shots/*.json — NOT shot_plan.json's full definition list "
            f"(2 of its 9 defined shots, h4_july_macro and h4_july_setup, were never "
            f"captured and are excluded here rather than falsely claimed as coverage)."
        ),
        "per_feature": per_feature,
        "scope": (
            "Read-only spot-validation only. Does not wire any SMC feature into a "
            "decision path (see F-076). Never writes configs/production/ or "
            "ACTIVE_VERSION."
        ),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"[OK] wrote {out_path}")
    print(f"[NON-VACUITY] all 9 SMC columns present: {'PASS' if not missing else 'FAIL'}")
    print(f"[SUMMARY] total_bars={total_bars} after_warmup={bars_after_warmup_trim} "
          f"any_smc_active_bars={int(active_mask.sum())}")
    for col in SMC_COLUMNS:
        pf = per_feature[col]
        print(f"  {col}: month_active={pf['n_active_total_month']} "
              f"in_reused_windows={pf['n_active_in_reused_shot_windows']} ({pf['status']})")
    print("[SCOPE] Read-only. No configs/production/ file or ACTIVE_VERSION was touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

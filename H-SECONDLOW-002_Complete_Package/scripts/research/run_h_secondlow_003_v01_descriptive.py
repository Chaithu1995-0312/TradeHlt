#!/usr/bin/env python3
"""H-SECONDLOW-003 v0.1 — pre-registered descriptive analysis on sealed PRE pool."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
if str(_REPO / "src") not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from research.secondlow_v1.corpus import CANONICAL_XAUUSD_M15
from research.secondlow_v1.detector import detect_independent_events, load_ohlcv, sha256_prefix

PRE_A = -1.5
PRE_B = 1.0
N_BOOT = 5000
SEED = 42

MANIFEST = _REPO / "H-SECONDLOW-002_Complete_Package/data/sealed_evaluation_set_v1.json"
OUTPUT = _REPO / "H-SECONDLOW-002_Complete_Package/results/h_secondlow_003_v01"


def is_exposed(pre_2h: float, depth: float) -> bool:
    return pre_2h <= PRE_A and depth >= PRE_B


def bootstrap_median_diff(exposed: np.ndarray, reference: np.ndarray, n_boot: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    obs = float(np.median(exposed) - np.median(reference))
    if len(exposed) == 0 or len(reference) == 0:
        return {"observed": obs, "ci_low": None, "ci_high": None, "n_boot": 0}
    stats = np.empty(n_boot)
    for i in range(n_boot):
        e = rng.choice(exposed, size=len(exposed), replace=True)
        r = rng.choice(reference, size=len(reference), replace=True)
        stats[i] = np.median(e) - np.median(r)
    return {
        "observed": obs,
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
        "n_boot": n_boot,
    }


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("preregistration_status") != "APPROVED":
        raise SystemExit("Manifest not approved for analysis.")

    sealed_times = {pd.Timestamp(t) for t in manifest["purge_times"]}
    dev_times = {pd.Timestamp(t) for t in manifest["internal_split"]["development"]}
    holdout_times = {pd.Timestamp(t) for t in manifest["internal_split"]["holdout"]}

    corpus = _REPO / CANONICAL_XAUUSD_M15
    df = load_ohlcv(corpus)
    _, events = detect_independent_events(df, require_post_window=True)

    rows = []
    for e in events:
        if e.purge_time not in sealed_times:
            continue
        if e.close_disp_atr is None:
            raise SystemExit(f"Missing post window for sealed event {e.purge_time}")
        group = "EXPOSED" if is_exposed(e.pre_2h_return_atr, e.purge_depth_atr) else "REFERENCE"
        split = "holdout" if e.purge_time in holdout_times else "development"
        rows.append(
            {
                "purge_time": e.purge_time,
                "split": split,
                "group": group,
                "pre_2h_return_atr": round(e.pre_2h_return_atr, 4),
                "purge_depth_atr": round(e.purge_depth_atr, 4),
                "close_disp_atr": round(e.close_disp_atr, 4),
            }
        )

    if len(rows) != len(sealed_times):
        raise SystemExit(f"Expected {len(sealed_times)} sealed events, got {len(rows)}")

    ev = pd.DataFrame(rows)
    exposed = ev[ev["group"] == "EXPOSED"]
    reference = ev[ev["group"] == "REFERENCE"]

    boot = bootstrap_median_diff(
        exposed["close_disp_atr"].to_numpy(),
        reference["close_disp_atr"].to_numpy(),
        N_BOOT,
        SEED,
    )

    def split_effect(sub: pd.DataFrame) -> float | None:
        e = sub[sub["group"] == "EXPOSED"]["close_disp_atr"]
        r = sub[sub["group"] == "REFERENCE"]["close_disp_atr"]
        if len(e) == 0 or len(r) == 0:
            return None
        return float(e.median() - r.median())

    dev_effect = split_effect(ev[ev["split"] == "development"])
    hold_effect = split_effect(ev[ev["split"] == "holdout"])
    direction_consistent = (
        dev_effect is not None
        and hold_effect is not None
        and np.sign(dev_effect) == np.sign(hold_effect)
    )

    rule1 = len(exposed) >= 12
    rule2 = boot["ci_low"] is not None and boot["ci_low"] > 0.3
    rule3 = direction_consistent
    rule4 = False  # prospective ledger empty
    worth_investment = rule1 and rule2 and rule3 and rule4

    report = {
        "hypothesis_id": "H-SECONDLOW-003",
        "version": "0.1",
        "corpus_sha256_prefix": sha256_prefix(corpus),
        "n_sealed_pre": len(ev),
        "exposed_n": int(len(exposed)),
        "reference_n": int(len(reference)),
        "exposed_median_close_disp_atr": float(exposed["close_disp_atr"].median()) if len(exposed) else None,
        "reference_median_close_disp_atr": float(reference["close_disp_atr"].median()) if len(reference) else None,
        "exposed_positive_frac": float((exposed["close_disp_atr"] > 0).mean()) if len(exposed) else None,
        "reference_positive_frac": float((reference["close_disp_atr"] > 0).mean()) if len(reference) else None,
        "primary_effect_median_diff": boot["observed"],
        "bootstrap_percentile_95ci": [boot["ci_low"], boot["ci_high"]],
        "development_effect_median_diff": dev_effect,
        "holdout_effect_median_diff": hold_effect,
        "decision_rules": {
            "rule1_exposed_n_ge_12": rule1,
            "rule2_ci_low_gt_0.3": rule2,
            "rule3_holdout_direction_consistent": rule3,
            "rule4_prospective_events_ge_15": rule4,
        },
        "verdict": "WORTH_FURTHER_INVESTMENT" if worth_investment else "ARCHIVE_OR_MODIFY",
        "rule1_expected_fail_note": "Rule #1 failure is pre-specified stop, not threshold-tuning signal",
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    ev.to_csv(OUTPUT / "descriptive_event_table.csv", index=False)
    (OUTPUT / "descriptive_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 72)
    print("H-SECONDLOW-003 v0.1 — DESCRIPTIVE ANALYSIS (APPROVED PREREG)")
    print("=" * 72)
    print(f"EXPOSED n: {report['exposed_n']}  REFERENCE n: {report['reference_n']}")
    print(f"Median EXPOSED close_disp_atr: {report['exposed_median_close_disp_atr']}")
    print(f"Median REFERENCE close_disp_atr: {report['reference_median_close_disp_atr']}")
    print(f"Primary effect (median diff): {report['primary_effect_median_diff']:.4f}")
    print(f"Bootstrap 95% CI: [{boot['ci_low']:.4f}, {boot['ci_high']:.4f}]")
    print(f"Development effect: {dev_effect}")
    print(f"Holdout effect: {hold_effect}")
    print(f"Decision rules: {report['decision_rules']}")
    print(f"VERDICT: {report['verdict']}")
    print(f"Wrote: {OUTPUT}")


if __name__ == "__main__":
    main()
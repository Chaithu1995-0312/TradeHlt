#!/usr/bin/env python3
"""
blind_label_score.py
======================
Read-only SCORER for the blind-labeling descriptive-fidelity test.

Pre-registration: docs/research/preregistration-blind-label-descriptive-fidelity.md
(the interpretation rule below is frozen there -- this script computes the numbers, it does not
decide what they mean).

Joins the user's exported CSV to sample_manifest.json (the answer key) by item_id, computes
Cohen's kappa (linear-weighted for the ordinal volatility question) per pre-registered cell:
  * Arm A only -- the population-rate-representative estimate, per question.
  * Arm B, per stratum -- conditional kappa, NEVER blended into a marginal/population estimate.
  * Arm C -- intra-rater reliability ceiling (same bar, two presentations).
  * Q4 (break_of_structure) split by whether the relevant reference level was on/off screen.

Any cell with fewer than MIN_CELL_N instances is reported INSUFFICIENT, never as a null
(E-001 discipline: underpowered is not evidence of no agreement).

Usage:
    PYTHONPATH=src python scripts/analysis/blind_label_score.py \\
        --labels results/blind_label/blind_label_answers.csv \\
        --manifest results/blind_label/sample_manifest.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sklearn.metrics import cohen_kappa_score

MIN_CELL_N = 15

# Label-string -> code, matching each question's answer domain.
Q1_MAP = {"up": 1.0, "down": -1.0, "neither": 0.0}
Q2_MAP = {"low": 0, "normal": 1, "high": 2}
Q3_MAP = {"above": 1, "below": -1, "neither": 0}
Q4_MAP = {"up": 1, "down": -1, "none": 0}

QUESTIONS = [
    ("q1_trend", "trend_bias", Q1_MAP, "nominal"),
    ("q2_vol", "volatility_regime", Q2_MAP, "linear"),
    ("q3_sweep", "liquidity_sweep", Q3_MAP, "nominal"),
    ("q4_bos", "break_of_structure", Q4_MAP, "nominal"),
]


def _load_labels(path: Path) -> dict[str, dict]:
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["item_id"]] = row
    return out


def _kappa(y_true: list, y_pred: list, weights: str | None) -> dict:
    n = len(y_true)
    if n < MIN_CELL_N:
        return {"n": n, "status": "INSUFFICIENT", "kappa": None}
    kw = None if weights == "nominal" else weights
    k = cohen_kappa_score(y_true, y_pred, weights=kw)
    agreement = sum(1 for a, b in zip(y_true, y_pred) if a == b) / n
    return {"n": n, "status": "SCORED", "kappa": float(k), "raw_agreement_pct": 100.0 * agreement}


def score(manifest: dict, labels: dict[str, dict]) -> dict:
    items_by_id = {it["item_id"]: it for it in manifest["items"]}
    report: dict = {
        "n_labeled": len(labels),
        "n_manifest_items": len(items_by_id),
        "per_question": {},
        "arm_c_intra_rater": {},
        "q4_reference_split": {},
    }

    for qkey, feature, vmap, weight_mode in QUESTIONS:
        arm_a_true, arm_a_pred = [], []
        by_stratum: dict[str, tuple[list, list]] = {}

        for item_id, item in items_by_id.items():
            lbl = labels.get(item_id)
            if lbl is None or not lbl.get(qkey):
                continue
            raw_label = lbl[qkey]
            if raw_label not in vmap:
                continue
            pred = vmap[raw_label]
            true = item["answers"][feature]
            # normalize true (may be float e.g. 1.0/-1.0/0.0 from trend_bias)
            true = float(true) if isinstance(true, (int, float)) else true
            arm = item["arm"]
            if arm == "A":
                arm_a_true.append(true)
                arm_a_pred.append(pred)
            elif arm == "B":
                for stratum in item.get("strata", []):
                    by_stratum.setdefault(stratum, ([], []))
                    by_stratum[stratum][0].append(true)
                    by_stratum[stratum][1].append(pred)

        report["per_question"][qkey] = {
            "arm_a_population_estimate": _kappa(arm_a_true, arm_a_pred, weight_mode),
            "arm_b_by_stratum": {
                s: _kappa(t, p, weight_mode) for s, (t, p) in by_stratum.items()
            },
        }

    # --- Arm C intra-rater reliability: pair each repeat with its original --------------
    for qkey, feature, vmap, weight_mode in QUESTIONS:
        first, second = [], []
        for item_id, item in items_by_id.items():
            if item["arm"] != "C":
                continue
            orig_id = item["repeat_of"]
            lbl_repeat = labels.get(item_id)
            lbl_orig = labels.get(orig_id)
            if not lbl_repeat or not lbl_orig:
                continue
            r1, r2 = lbl_orig.get(qkey), lbl_repeat.get(qkey)
            if r1 not in vmap or r2 not in vmap:
                continue
            first.append(vmap[r1])
            second.append(vmap[r2])
        report["arm_c_intra_rater"][qkey] = _kappa(first, second, weight_mode)

    # --- Q4 on/off-screen reference split (Arm A + Arm B pooled, conditional only) ------
    for onscreen_flag in (True, False):
        true_list, pred_list = [], []
        for item_id, item in items_by_id.items():
            if item["arm"] not in ("A", "B"):
                continue
            if item.get("primary_ref_onscreen") is None:
                continue  # NoBreak bars have no single relevant reference
            if bool(item["primary_ref_onscreen"]) != onscreen_flag:
                continue
            lbl = labels.get(item_id)
            if not lbl or not lbl.get("q4_bos") or lbl["q4_bos"] not in Q4_MAP:
                continue
            true_list.append(float(item["answers"]["break_of_structure"]))
            pred_list.append(Q4_MAP[lbl["q4_bos"]])
        key = "reference_onscreen" if onscreen_flag else "reference_offscreen"
        report["q4_reference_split"][key] = _kappa(true_list, pred_list, "nominal")

    return report


def _to_markdown(report: dict) -> str:
    lines = ["# Blind Label Score Report", "",
             f"Labeled items: {report['n_labeled']} / {report['n_manifest_items']}", ""]
    lines.append("## Per-question (Arm A = population estimate; Arm B = conditional only)")
    lines.append("| Question | Arm A n | Arm A kappa | Arm A raw agreement |")
    lines.append("|---|---|---|---|")
    for qkey, pq in report["per_question"].items():
        a = pq["arm_a_population_estimate"]
        kappa_s = f"{a['kappa']:.3f}" if a["kappa"] is not None else "—"
        agree_s = f"{a['raw_agreement_pct']:.1f}%" if a.get("raw_agreement_pct") is not None else "—"
        lines.append(f"| {qkey} | {a['n']} | {kappa_s} ({a['status']}) | {agree_s} |")
    lines.append("")
    lines.append("### Arm B conditional (within-stratum only, never a population estimate)")
    for qkey, pq in report["per_question"].items():
        for stratum, s in pq["arm_b_by_stratum"].items():
            kappa_s = f"{s['kappa']:.3f}" if s["kappa"] is not None else "—"
            lines.append(f"- {qkey} / {stratum}: n={s['n']}, kappa={kappa_s} ({s['status']})")
    lines.append("")
    lines.append("## Intra-rater reliability ceiling (Arm C)")
    for qkey, s in report["arm_c_intra_rater"].items():
        kappa_s = f"{s['kappa']:.3f}" if s["kappa"] is not None else "—"
        lines.append(f"- {qkey}: n={s['n']}, kappa={kappa_s} ({s['status']})")
    lines.append("")
    lines.append("## Q4 break_of_structure -- reference-level on/off screen split")
    for key, s in report["q4_reference_split"].items():
        kappa_s = f"{s['kappa']:.3f}" if s["kappa"] is not None else "—"
        lines.append(f"- {key}: n={s['n']}, kappa={kappa_s} ({s['status']})")
    lines.append("")
    lines.append("_Interpretation is governed by the pre-registered rule in "
                  "docs/research/preregistration-blind-label-descriptive-fidelity.md -- "
                  "this report states numbers only._")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--output-dir", default=None,
                    help="Defaults to the manifest's own directory.")
    args = ap.parse_args()

    labels_path = Path(args.labels)
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    labels = _load_labels(labels_path)

    report = score(manifest, labels)

    out_dir = Path(args.output_dir) if args.output_dir else manifest_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "score_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "score_report.md").write_text(_to_markdown(report), encoding="utf-8")

    print(_to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

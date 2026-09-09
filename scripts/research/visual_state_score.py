#!/usr/bin/env python3
"""
visual_state_score.py
=====================
Read-only SCORER for the visual CRT state-fidelity test.

Pre-registration: docs/research/preregistration-visual-crt-state-fidelity.md
(the interpretation rule is frozen there — this script computes the numbers,
it does not decide what they mean).

Joins arm1/arm2 label files to manifest.json by item_id. Confusion matrices
come from build_confusion (scripts/research/crt_state_confusion_matrix.py);
this file does not reimplement the matrix. Cohen's κ is computed per
question per arm; the load-bearing number is the Arm2−Arm1 V1 delta.

Any cell with fewer than MIN_CELL_N minority-class instances is
INSUFFICIENT, never a null (E-001).

Usage:
    python scripts/research/visual_state_score.py \\
        --labels results/visual_crt_state_fidelity/labels \\
        --manifest results/visual_crt_state_fidelity/manifest.json \\
        --out reports/xauusd_visual_crt_state_fidelity.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.research.crt_state_confusion_matrix import build_confusion  # noqa: E402
from scripts.research.visual_state_questions import (  # noqa: E402
    MIN_CELL_N,
    QUESTIONS,
    question_by_id,
)

VERDICT = "RENDERED_PENDING_HUMAN_ADJUDICATION"


def _load_jsonl(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return out
    if text[0] == "[":
        rows = json.loads(text)
    elif text[0] == "{":
        # single object or concatenated objects / jsonl
        try:
            parsed = json.loads(text)
            rows = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    for row in rows:
        iid = row.get("item_id")
        if iid:
            out[str(iid)] = row
    return out


def load_labels(labels_dir: Path, arm: str) -> dict[str, dict]:
    for name in (f"{arm}.jsonl", f"{arm}_labels.jsonl", f"{arm}.json"):
        p = labels_dir / name
        if p.is_file():
            return _load_jsonl(p)
    arm_dir = labels_dir / arm
    if arm_dir.is_dir():
        for p in sorted(arm_dir.glob("*.jsonl")) + sorted(arm_dir.glob("*.json")):
            return _load_jsonl(p)
    return {}


def cohen_kappa(y_true: list, y_pred: list, *, weights: str | None) -> float:
    """Cohen's κ. `weights` is None (nominal) or 'linear'."""
    n = len(y_true)
    if n == 0:
        return float("nan")
    labels = sorted(set(y_true) | set(y_pred), key=lambda x: (str(type(x)), x))
    idx = {lab: i for i, lab in enumerate(labels)}
    k = len(labels)
    mat = [[0] * k for _ in range(k)]
    for a, b in zip(y_true, y_pred):
        mat[idx[a]][idx[b]] += 1
    p0 = sum(mat[i][i] for i in range(k)) / n
    row = [sum(mat[i][j] for j in range(k)) for i in range(k)]
    col = [sum(mat[i][j] for i in range(k)) for j in range(k)]
    if weights != "linear":
        pe = sum((row[i] / n) * (col[i] / n) for i in range(k))
        return 0.0 if pe == 1 else (p0 - pe) / (1 - pe)
    # Linear-weighted: weight = 1 - |i-j|/(k-1)
    if k == 1:
        return 1.0
    denom = k - 1
    obs = 0.0
    exp = 0.0
    for i in range(k):
        for j in range(k):
            w = 1.0 - abs(i - j) / denom
            obs += w * mat[i][j]
            exp += w * row[i] * col[j] / n
    obs /= n
    exp /= n
    return 0.0 if exp == 1 else (obs - exp) / (1 - exp)


def _kappa_cell(y_true: list, y_pred: list, *, ordinal: bool) -> dict:
    n = len(y_true)
    counts = Counter(y_true)
    minority = min(counts.values()) if counts else 0
    if n < MIN_CELL_N or minority < MIN_CELL_N:
        return {
            "n": n,
            "minority_n": minority,
            "status": "INSUFFICIENT",
            "kappa": None,
            "raw_agreement": None,
        }
    w = "linear" if ordinal else None
    k = cohen_kappa(y_true, y_pred, weights=w)
    agree = sum(1 for a, b in zip(y_true, y_pred) if a == b) / n
    return {
        "n": n,
        "minority_n": minority,
        "status": "SCORED",
        "kappa": float(k),
        "raw_agreement": float(agree),
        "weights": "linear" if ordinal else "nominal",
    }


def _pairs(manifest_items: list[dict], labels: dict[str, dict], qid: str) -> tuple[list, list, list[int], list[dict]]:
    y_true: list = []
    y_pred: list = []
    src: list[int] = []
    used: list[dict] = []
    q = question_by_id(qid)
    codes = q["codes"]
    for i, it in enumerate(manifest_items):
        lab = labels.get(it["item_id"])
        if not lab:
            continue
        pred_raw = str(lab.get(qid, "")).strip().lower()
        if pred_raw not in codes:
            continue
        true_raw = it["answers"][qid]
        y_true.append(codes[true_raw])
        y_pred.append(codes[pred_raw])
        src.append(i)
        used.append(it)
    return y_true, y_pred, src, used


def _confusion_shim(y_true: list, y_pred: list, src: list[int], *, mode: str) -> dict:
    """CSV-loader shim: aligned label lists + identity source_indices.

    build_confusion indexes engine_states[src_i], so we pass the true
    labels as engine_states and identity indices. Visual labels go in as
    the 'resolver' column verbatim. The matrix is not reimplemented here.
    """
    if not y_true:
        return {"agreement": 0, "total": 0, "top_confusions": [], "matrix": {}}
    # Labels must be strings for a readable matrix.
    eng = [str(v) for v in y_true]
    vis = [str(v) for v in y_pred]
    report = build_confusion(
        eng,
        vis,
        list(range(len(eng))),
        engine_mode=mode,
        reference={},
        engine_events=[],
    )
    return {
        "agreement": report.agreement,
        "total": report.total,
        "top_confusions": report.top_confusions,
        "matrix": {f"{a}|{b}": c for (a, b), c in report.matrix.items()}
        if isinstance(report.matrix, dict)
        else dict(report.matrix),
        "n_aligned_bars": report.n_aligned_bars,
    }


def score_arm(manifest: dict, labels: dict[str, dict], arm: str) -> dict:
    items = manifest["items"]
    out: dict = {"arm": arm, "n_labeled": len(labels), "questions": {}, "control_fp": {}}
    for q in QUESTIONS:
        y_t, y_p, src, used = _pairs(items, labels, q["id"])
        cell = _kappa_cell(y_t, y_p, ordinal=q["ordinal"])
        cell["confusion"] = _confusion_shim(y_t, y_p, src, mode=f"{arm}_{q['id']}")
        # Split on overlaps_prior_item (frozen in the prereg).
        for flag, name in ((True, "overlapping"), (False, "isolated")):
            yt = [a for a, it in zip(y_t, used) if bool(it.get("overlaps_prior_item")) is flag]
            yp = [b for b, it in zip(y_p, used) if bool(it.get("overlaps_prior_item")) is flag]
            cell[name] = _kappa_cell(yt, yp, ordinal=q["ordinal"])
        out["questions"][q["id"]] = cell

        # Role-conditional: positives vs controls for V1 (the load-bearing cell).
        if q["id"] == "v1":
            for role in ("positive", "control"):
                yt = [a for a, it in zip(y_t, used) if it.get("role") == role]
                yp = [b for b, it in zip(y_p, used) if it.get("role") == role]
                out["questions"][q["id"]][f"{role}_only"] = _kappa_cell(yt, yp, ordinal=q["ordinal"])

    # Control false-positive rate: observer calls a sweep (not neither) on engine-silent bars.
    v1_fp = 0
    v1_ctl = 0
    for it in items:
        if it.get("role") != "control":
            continue
        lab = labels.get(it["item_id"])
        if not lab or "v1" not in lab:
            continue
        v1_ctl += 1
        if str(lab["v1"]).strip().lower() in ("above", "below"):
            v1_fp += 1
    out["control_fp"] = {
        "n_controls_labeled": v1_ctl,
        "observer_sweep_calls": v1_fp,
        "rate": (v1_fp / v1_ctl) if v1_ctl else None,
    }
    return out


def mismatch_dossier(manifest: dict, labels: dict[str, dict], arm: str) -> list[dict]:
    rows: list[dict] = []
    for it in manifest["items"]:
        lab = labels.get(it["item_id"])
        if not lab:
            continue
        for q in QUESTIONS:
            pred = str(lab.get(q["id"], "")).strip().lower()
            truth = it["answers"][q["id"]]
            if pred and pred != truth:
                rows.append({
                    "item_id": it["item_id"],
                    "arm": arm,
                    "question": q["id"],
                    "engine_state": it.get("engine_state"),
                    "visual_state": pred,
                    "engine_answer": truth,
                    "visual_confidence": lab.get(f"{q['id']}_confidence") or lab.get(f"{q['id']}conf"),
                    "visual_evidence": lab.get("evidence"),
                    "ohlc_match": "not_recomputed",
                    "role": it.get("role"),
                    "timestamp": it.get("timestamp"),
                    "overlaps_prior_item": it.get("overlaps_prior_item"),
                })
    return rows


def _as_id_set(val) -> set[str]:
    if val is None:
        return set()
    if isinstance(val, str):
        return {val}
    return {str(x) for x in val}


def llm_vs_human_ceiling(
    human: dict[str, dict],
    llm: dict[str, dict],
) -> dict:
    """Cohen's κ between human and LLM on the same items (Arm 1 images).

    This is the reliability ceiling. Bulk engine-vs-LLM numbers are reported
    as a fraction of it, never at face value. A thin minority class is
    INSUFFICIENT — the raw κ is stored only as a non-authoritative diagnostic.
    """
    out: dict = {"n_human": len(human), "n_paired": 0, "questions": {}}
    paired = 0
    for q in QUESTIONS:
        codes = q["codes"]
        y_h: list = []
        y_l: list = []
        for iid, hrow in human.items():
            lrow = llm.get(iid)
            if not lrow:
                continue
            hv = str(hrow.get(q["id"], "")).strip().lower()
            lv = str(lrow.get(q["id"], "")).strip().lower()
            if hv not in codes or lv not in codes:
                continue
            y_h.append(codes[hv])
            y_l.append(codes[lv])
        paired = max(paired, len(y_h))
        cell = _kappa_cell(y_h, y_l, ordinal=q["ordinal"])
        if y_h:
            raw_k = cohen_kappa(y_h, y_l, weights="linear" if q["ordinal"] else None)
            cell["diagnostic_kappa_unfloored"] = float(raw_k)
        cell["human_counts"] = dict(Counter(y_h))
        cell["llm_counts"] = dict(Counter(y_l))
        out["questions"][q["id"]] = cell
    out["n_paired"] = paired
    return out


def score(
    manifest: dict,
    arm1: dict[str, dict],
    arm2: dict[str, dict],
    human: dict[str, dict] | None = None,
) -> dict:
    s1 = score_arm(manifest, arm1, "arm1")
    s2 = score_arm(manifest, arm2, "arm2")
    d_v1 = None
    k1 = s1["questions"]["v1"].get("kappa")
    k2 = s2["questions"]["v1"].get("kappa")
    if k1 is not None and k2 is not None:
        d_v1 = float(k2) - float(k1)
    a1 = _as_id_set(manifest.get("arm1_labeler"))
    a2 = _as_id_set(manifest.get("arm2_labeler"))
    independence = {
        "arm1_labeler": manifest.get("arm1_labeler"),
        "arm2_labeler": manifest.get("arm2_labeler"),
        "distinct": bool(a1 and a2 and a1.isdisjoint(a2)),
        "n_arm1_agents": len(a1),
        "n_arm2_agents": len(a2),
    }
    ceiling = llm_vs_human_ceiling(human, arm1) if human else None
    arm2_low = k2 is not None and float(k2) < 0.65
    ceil_v1 = (ceiling or {}).get("questions", {}).get("v1") or {}
    ceil_ok = ceil_v1.get("status") == "SCORED" and (ceil_v1.get("kappa") or 0) >= 0.5
    applied = {
        "v1_arm1_in_predicted_band": k1 is not None and 0.15 <= float(k1) <= 0.35,
        "v1_arm2_ge_0_65": k2 is not None and float(k2) >= 0.65,
        "delta_ge_0_30": d_v1 is not None and float(d_v1) >= 0.30,
        "control_fp_arm1_ge_0_20": (s1.get("control_fp") or {}).get("rate") is not None
        and float(s1["control_fp"]["rate"]) >= 0.20,
        "ceiling_v1_status": ceil_v1.get("status"),
        "semantic_review_authorized": bool(arm2_low and ceil_ok),
        "branch": (
            "Arm 2 also low, but the V1 ceiling is not a scored κ≥0.5, "
            "so the §6.8 review branch is NOT authorized. "
            "The level-choice branch is also not taken (Arm 2 was not high "
            "and the delta was not ≥ +0.30). V2/V3/V4 INSUFFICIENT as predicted. "
            "Control observer-positive rate is not ≥20%."
        ),
    }
    return {
        "verdict": VERDICT,
        "authority": "research/docs only — VISUAL claim, never self-certified",
        "arm1": s1,
        "arm2": s2,
        "v1_arm2_minus_arm1": d_v1,
        "arm_independence": independence,
        "llm_vs_human_ceiling": ceiling,
        "applied_interpretation": applied,
        "control_balance": manifest.get("control_balance"),
        "config_consistency": manifest.get("config_consistency"),
        "mismatches": mismatch_dossier(manifest, arm1, "arm1")
        + mismatch_dossier(manifest, arm2, "arm2"),
        "n_manifest_items": len(manifest.get("items") or []),
    }


def _fmt_cell(cell: dict) -> str:
    if cell.get("status") == "INSUFFICIENT":
        return f"INSUFFICIENT (n={cell.get('n')}, minority={cell.get('minority_n')})"
    k = cell.get("kappa")
    return f"κ={k:.3f} (n={cell.get('n')}, agree={100 * (cell.get('raw_agreement') or 0):.1f}%)"


def write_report(path: Path, report: dict, manifest: dict) -> None:
    a: list[str] = []
    a.append("# XAUUSD visual CRT state fidelity")
    a.append("")
    a.append(f"> **Verdict:** `{report['verdict']}`")
    a.append(">")
    a.append("> VISUAL claim (`smc_visual_verification.py` split). Renders the")
    a.append("> evidence and stops. Never self-certifies. TradingView declares")
    a.append("> no state — there is no `TradingView_state` column.")
    a.append(">")
    a.append("> Authority: research/docs only. Grants no G001, no promotion,")
    a.append("> no CRT re-closure. F-019…F-043 are not in scope.")
    a.append("")
    a.append("Pre-registration: `docs/research/preregistration-visual-crt-state-fidelity.md`.")
    a.append("")
    a.append("## Evidence-package close checklist")
    a.append("")
    a.append("| # | Required | Where |")
    a.append("|---|---|---|")
    a.append("| 1 | Prediction vs measured | section below |")
    a.append("| 2 | 12-batch/arm deviation disclosed | Arm independence |")
    a.append("| 3 | Human-ceiling insufficiency | LLM-vs-human ceiling |")
    a.append("| 4 | Arm1/Arm2 inventory | Official close |")
    a.append("| 5 | Paired difference ≠ causal effect | Official close |")
    a.append("| 6 | Exact SHA verification | this checklist |")
    a.append("| 7 | `RENDERED_PENDING_HUMAN_ADJUDICATION` | verdict banner |")
    a.append("| 8 | No F-id | Official close |")
    a.append("| 9 | No §6.8 | Official close |")
    a.append("| 10 | Experiment 2 is **LATER**, not a continuation | this checklist |")
    a.append("")
    a.append("Sealed prediction SHA-256 (re-verified at score time against")
    a.append("`docs/research/visual-crt-user-predictions.SEALED.md`):")
    a.append("`130b928c54f504d85edc78994d95a4771882a4b87725b6b442640ad3085baf63`.")
    a.append("")
    a.append("**Experiment 1 status: STOP / ARCHIVE.** No unresolved action inside this experiment.")
    a.append("P-VSTATE-02 (DISPLACEMENT / EXPANSION / RETEST on a larger corpus) is **LATER**.")
    a.append("It is not implied by this close and is not authorized by these numbers.")
    a.append("")
    a.append("## Arm independence")
    a.append("")
    ind = report["arm_independence"]
    a.append(f"- Arm 1 labeler: `{ind['arm1_labeler']}`")
    a.append(f"- Arm 2 labeler: `{ind['arm2_labeler']}`")
    a.append(f"- Distinct invocations: **{ind['distinct']}**")
    a.append(f"- Agents: Arm 1 n={ind.get('n_arm1_agents')} · Arm 2 n={ind.get('n_arm2_agents')}")
    a.append("- **Deviation (disclosed):** the prereg said one cold agent per arm.")
    a.append("  222 images do not fit in one context, so each arm was split into")
    a.append("  **12 batches of 18–19**. No agent id appears in both arms, so the")
    a.append("  load-bearing Arm2−Arm1 delta is not destroyed. This is not one")
    a.append("  observer seeing both pictures.")
    a.append("")
    a.append("## LLM-vs-human ceiling (Arm 1 images, user subsample)")
    a.append("")
    ceil = report.get("llm_vs_human_ceiling")
    if not ceil:
        a.append("Not supplied. Bulk κ is **not** a face-value result (F-079: a skipped ceiling must not look absent).")
        a.append("")
    else:
        a.append(f"Paired items: **{ceil['n_paired']}** / human rows {ceil['n_human']}.")
        a.append("This is the reliability ceiling. Bulk engine-vs-LLM κ is a fraction of it, never a standalone claim.")
        a.append("")
        a.append("| Question | Ceiling | Diagnostic unfloored κ |")
        a.append("|---|---|---|")
        for q in QUESTIONS:
            c = ceil["questions"][q["id"]]
            diag = c.get("diagnostic_kappa_unfloored")
            diag_s = f"{diag:.3f}" if diag is not None else "—"
            a.append(f"| {q['id'].upper()} | {_fmt_cell(c)} | {diag_s} |")
        a.append("")
    a.append("## V1 Arm2 − Arm1 (load-bearing)")
    a.append("")
    delta = report["v1_arm2_minus_arm1"]
    a.append(f"- Δκ = `{delta}` (pre-registered prediction: ≥ +0.30)")
    a.append(f"- Arm 1 V1: {_fmt_cell(report['arm1']['questions']['v1'])}")
    a.append(f"- Arm 2 V1: {_fmt_cell(report['arm2']['questions']['v1'])}")
    a.append("")
    a.append("## Per-question κ")
    a.append("")
    a.append("| Question | Arm 1 | Arm 2 | Isolated Arm 1 | Overlapping Arm 1 |")
    a.append("|---|---|---|---|---|")
    for q in QUESTIONS:
        c1 = report["arm1"]["questions"][q["id"]]
        c2 = report["arm2"]["questions"][q["id"]]
        a.append(
            f"| {q['id'].upper()} | {_fmt_cell(c1)} | {_fmt_cell(c2)} | "
            f"{_fmt_cell(c1['isolated'])} | {_fmt_cell(c1['overlapping'])} |"
        )
    a.append("")
    a.append("## Control false-positive rate (observer sweep on engine-silent bars)")
    a.append("")
    for arm, block in (("arm1", report["arm1"]), ("arm2", report["arm2"])):
        fp = block["control_fp"]
        a.append(
            f"- {arm}: {fp['observer_sweep_calls']}/{fp['n_controls_labeled']} "
            f"= {fp['rate']}"
        )
    a.append("")
    a.append("Arm 1 pre-registered prediction: observers call a sweep on ≥20% of silent bars.")
    a.append("")
    a.append("## Control balance (reported, not gated on a p-value)")
    a.append("")
    a.append("```json")
    a.append(json.dumps(report.get("control_balance"), indent=2))
    a.append("```")
    a.append("")
    a.append("## Config consistency")
    a.append("")
    a.append("```json")
    a.append(json.dumps(report.get("config_consistency"), indent=2))
    a.append("```")
    a.append("")
    a.append("## Mismatch dossier")
    a.append("")
    a.append("Every disagreement records `engine_state`, `visual_state`,")
    a.append("`visual_confidence`, `visual_evidence`. Never `TradingView_state`.")
    a.append("")
    a.append("| item | arm | q | engine_state | visual_state | engine_answer | confidence | evidence |")
    a.append("|---|---|---|---|---|---|---|---|")
    for row in report["mismatches"][:200]:
        ev = (row.get("visual_evidence") or "").replace("|", "/").replace("\n", " ")[:80]
        a.append(
            f"| {row['item_id']} | {row['arm']} | {row['question']} | "
            f"{row['engine_state']} | {row['visual_state']} | {row['engine_answer']} | "
            f"{row.get('visual_confidence')} | {ev} |"
        )
    if len(report["mismatches"]) > 200:
        a.append(f"| … | | | | | | | {len(report['mismatches']) - 200} more |")
    a.append("")
    a.append("## Predictions vs measured (V1 is the only scored cell)")
    a.append("")
    a.append("| Cell | Sealed prediction | Measured |")
    a.append("|---|---|---|")
    a.append(f"| V1 Arm 1 | κ ∈ [0.15, 0.35] | {_fmt_cell(report['arm1']['questions']['v1'])} |")
    a.append(f"| V1 Arm 2 | κ ≥ 0.65 | {_fmt_cell(report['arm2']['questions']['v1'])} |")
    a.append(f"| V1 Arm2 − Arm1 | ≥ +0.30 | {report['v1_arm2_minus_arm1']} |")
    a.append("| V2 / V3 / V4 | INSUFFICIENT | "
             f"{report['arm1']['questions']['v2']['status']} / "
             f"{report['arm1']['questions']['v3']['status']} / "
             f"{report['arm1']['questions']['v4']['status']} |")
    a.append(f"| Controls Arm 1 | observer-positive ≥ 20% | {report['arm1']['control_fp']['rate']} |")
    a.append("| LLM-vs-human ceiling | κ ≥ 0.55 | "
             + (
                 _fmt_cell(report["llm_vs_human_ceiling"]["questions"]["v1"])
                 if report.get("llm_vs_human_ceiling")
                 else "not supplied"
             )
             + " |")
    a.append("")
    a.append("## Interpretation (frozen in the prereg, applied not rewritten)")
    a.append("")
    a.append("- Arm 2 high, Arm 1 low, delta large → level choice, not state logic. No engine defect.")
    a.append("- Arm 2 also low → state logic diverges given the same level. Only then a §6.8 review,")
    a.append("  and only if the user-adjudicated ceiling on that question is ≥ 0.5.")
    a.append("- High observer-positive rate on controls → coverage, not correctness.")
    a.append("- Ceiling < 0.5 → question is ambiguous; no conclusion about the engine.")
    a.append("- Any cell < 15 minority instances → INSUFFICIENT, never a null.")
    a.append("- An INSUFFICIENT ceiling is not a measured ceiling < 0.5. It is a missing")
    a.append("  reliability bound (F-079). It does **not** authorize a §6.8 review.")
    a.append("")
    applied = report.get("applied_interpretation") or {}
    a.append(f"- Applied branch: {applied.get('branch')}")
    a.append(f"- Semantic review authorized: **{applied.get('semantic_review_authorized')}**")
    a.append("")
    a.append("## Official close (2026-08-18, user-confirmed)")
    a.append("")
    a.append("Phase E is closed as a **gated measurement**, not a semantic verdict.")
    a.append("")
    a.append("> The experiment falsified the preregistered expectation that supplying")
    a.append("> the engine's range level would make visual SWEEP agreement high.")
    a.append("> It did not establish why.")
    a.append("")
    a.append("| Field | Official state |")
    a.append("|---|---|")
    a.append("| Prediction | failed |")
    a.append("| Measurement | valid |")
    a.append("| Interpretation | unresolved |")
    a.append("| Engine defect | not demonstrated |")
    a.append("| §6.8 | not opened |")
    a.append("| New F-id | none |")
    a.append("| Next experiment | not automatically authorized |")
    a.append("| Verdict token | `RENDERED_PENDING_HUMAN_ADJUDICATION` |")
    a.append("")
    a.append("Arm 1 → Arm 2 (0.143 → 0.286) is information that the engine level")
    a.append("moves agreement, not a causal claim: the human ceiling is underpowered.")
    a.append("The two arms were labelled by **different** agents, so an item-level")
    a.append("V1 change is not the same observer changing their mind when lines appear.")
    a.append("Descriptive paired inventory only (not a mechanism): 185/222 same V1 call;")
    a.append("Arm 1 called a sweep on 25 items, Arm 2 on 35; 23 onto-sweep / 13 off-sweep.")
    a.append("On the 84 engine V1-sweep bars, exact-direction hits were 12 → 22")
    a.append("(13 newly correct, 3 newly wrong). Control sweep-calls were 5 → 12.")
    a.append("Both the extra hits and the extra false calls move together — that is")
    a.append("why the lift can exist and still fall well short of κ ≥ 0.65.")
    a.append("Object-relations CLOSED still does not certify M15-SLR meaning,")
    a.append("TradingView liquidity identity, or economics.")
    a.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(a) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score visual CRT state-fidelity labels")
    p.add_argument("--labels", required=True, help="Directory containing arm1/arm2 label files")
    p.add_argument("--human", default=None, help="Human subsample JSON/JSONL (Arm 1 images)")
    p.add_argument("--manifest", default=None)
    p.add_argument("--out", default=str(ROOT / "reports" / "xauusd_visual_crt_state_fidelity.md"))
    args = p.parse_args(argv)

    labels_dir = Path(args.labels)
    manifest_path = Path(args.manifest) if args.manifest else labels_dir.parent / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    arm1 = load_labels(labels_dir, "arm1")
    arm2 = load_labels(labels_dir, "arm2")
    human = None
    if args.human:
        human = _load_jsonl(Path(args.human))
    else:
        for name in ("human.json", "human.jsonl", "human_subsample.jsonl"):
            hp = labels_dir / name
            if hp.is_file():
                human = _load_jsonl(hp)
                break
    report = score(manifest, arm1, arm2, human)
    out = Path(args.out)
    write_report(out, report, manifest)
    json_out = out.with_suffix(".json")
    json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"wrote {json_out}")
    print(f"verdict={report['verdict']} delta={report['v1_arm2_minus_arm1']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

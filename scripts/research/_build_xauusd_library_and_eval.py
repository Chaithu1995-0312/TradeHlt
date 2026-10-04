"""
_build_xauusd_library_and_eval.py — Phase 3+4: Representative Trace Library + Engine Evaluation.

DESCRIPTIVE - information not authority (sec6.5); no edge/profit claim; failure structure only.

Phase 3: Build a curated ~50-exemplar Representative Trace Library for human/LLM inspection.
Phase 4: Produce a descriptive Engine Evaluation report (agreement, calibration, coverage).

Usage:
    python scripts/research/_build_xauusd_library_and_eval.py

Outputs:
    results/research/trace_corpus/xauusd/REPRESENTATIVE_LIBRARY.md
    results/research/trace_corpus/xauusd/representative_exemplars.jsonl
    results/research/trace_corpus/xauusd/ENGINE_EVALUATION.md
"""
import json
import sys
import logging
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
from features.feature_schema import CANONICAL_FEATURES

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("build_library")

CORPUS_PATH = "results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl"
LIBRARY_MD_PATH = "results/research/trace_corpus/xauusd/REPRESENTATIVE_LIBRARY.md"
EXEMPLARS_PATH = "results/research/trace_corpus/xauusd/representative_exemplars.jsonl"
EVAL_MD_PATH = "results/research/trace_corpus/xauusd/ENGINE_EVALUATION.md"

BANNER = "> DESCRIPTIVE - information not authority (sec6.5); no edge/profit claim; failure structure only."


def load_corpus(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def get_feature_dict(trace: dict) -> dict:
    d = {}
    for feat in CANONICAL_FEATURES:
        val = trace.get(f"feature_{feat}")
        if val is not None:
            try:
                d[feat] = float(val)
            except (TypeError, ValueError):
                d[feat] = 0.0
        else:
            d[feat] = 0.0
    return d


def has_engines(trace: dict) -> bool:
    return trace.get("engine_crt_score") is not None


# ── Phase 3: Representative Library ──────────────────────────────────────

def select_exemplars(traces: list[dict]) -> list[dict]:
    exemplars = []
    seen_ids = set()

    def add(t):
        if t["trade_id"] not in seen_ids:
            seen_ids.add(t["trade_id"])
            exemplars.append(t)

    # 1. Best TP_HIT per family
    for family in ["expansion_breakout", "mean_reversion"]:
        candidates = [t for t in traces if t["family"] == family and t["outcome"] == "TP_HIT" and has_engines(t)]
        if candidates:
            add(max(candidates, key=lambda t: t["rr_achieved"]))

    # 2. Worst SL_HIT per family
    for family in ["expansion_breakout", "mean_reversion"]:
        candidates = [t for t in traces if t["family"] == family and t["outcome"] == "SL_HIT" and has_engines(t)]
        if candidates:
            add(min(candidates, key=lambda t: t["rr_achieved"]))

    # 3. Near-miss losers (SL_HIT with MFE >= p75)
    sl_traces = [t for t in traces if t["outcome"] == "SL_HIT" and has_engines(t)]
    if sl_traces:
        mfe_vals = [t["mfe"] for t in sl_traces if t["mfe"] is not None]
        if mfe_vals:
            p75 = float(np.percentile(mfe_vals, 75))
            near_misses = [t for t in sl_traces if t["mfe"] is not None and t["mfe"] >= p75]
            for t in near_misses[:3]:
                add(t)

    # 4. Typical TIMEOUT per family
    for family in ["expansion_breakout", "mean_reversion"]:
        candidates = [t for t in traces if t["family"] == family and t["outcome"] == "TIMEOUT" and has_engines(t)]
        if candidates:
            median_dur = float(np.median([t["duration_candles"] for t in candidates]))
            add(min(candidates, key=lambda t: abs(t["duration_candles"] - median_dur)))

    # 5. High-confidence correct (engines agree)
    for outcome in ["TP_HIT", "SL_HIT"]:
        candidates = [t for t in traces if t["outcome"] == outcome and has_engines(t)]
        scored = []
        for t in candidates:
            scores = [t["engine_crt_score"], t["engine_gaussian_score"],
                      t["engine_zone_score"], t["engine_rr_score"]]
            if all(s >= 0.6 for s in scores) or all(s < 0.4 for s in scores):
                scored.append((t["engine_disagreement"], t))
        scored.sort(key=lambda x: x[0])
        for _, t in scored[:2]:
            add(t)

    # 6. High-disagreement cases
    all_with_engines = [t for t in traces if has_engines(t)]
    by_disagreement = sorted(all_with_engines, key=lambda t: t["engine_disagreement"], reverse=True)
    for t in by_disagreement[:5]:
        add(t)

    # 7. Boundary cases (fusion near 0.5)
    boundary = [t for t in all_with_engines if abs(t.get("fusion_composite", 0) - 0.5) < 0.05]
    for t in boundary[:5]:
        add(t)

    # 8. Spine trace
    for t in traces:
        if t["family"] == "spine" and t["trade_id"] not in seen_ids:
            add(t)

    # 9. Longest/shortest duration per outcome
    for outcome in ["TP_HIT", "SL_HIT", "TIMEOUT"]:
        candidates = [t for t in traces if t["outcome"] == outcome and has_engines(t)]
        if candidates:
            add(max(candidates, key=lambda t: t["duration_candles"]))
            add(min(candidates, key=lambda t: t["duration_candles"]))

    # 10. Per-family per-direction median
    for family in ["expansion_breakout", "mean_reversion"]:
        for direction in ["long", "short"]:
            candidates = [t for t in traces if t["family"] == family and t["direction"] == direction and has_engines(t)]
            if candidates:
                add(candidates[len(candidates) // 2])

    log.info("Selected %d exemplars", len(exemplars))
    return exemplars


def format_exemplar_narrative(t: dict) -> str:
    features = get_feature_dict(t)
    parts = [
        f"**{t['trade_id']}** - {t['family']} / {t['direction']} / {t['outcome']}",
        f"Entry at {t['entry_timestamp']} (index {t['entry_index']}), price {t['entry']:.2f}.",
        f"Duration: {t['duration_candles']} candles. R achieved: {t['rr_achieved']:.2f}.",
        f"MFE={t['mfe']:.2f}, MAE={t['mae']:.2f}.",
    ]
    if has_engines(t):
        parts.append(
            f"Engine scores: CRT={t['engine_crt_score']:.3f}, "
            f"Gaussian={t['engine_gaussian_score']:.3f}, "
            f"Zone={t['engine_zone_score']:.3f}, "
            f"RR={t['engine_rr_score']:.3f}. "
            f"Fusion={t['fusion_composite']:.3f} ({t['fusion_decision']}), "
            f"disagreement={t['engine_disagreement']:.3f}."
        )
    key_feats = ["body_ratio", "disp_strength", "retest_depth", "atr",
                 "rsi_14", "volume_ratio", "sweep_detected", "trend_bias"]
    feat_strs = [f"{k}={features.get(k, 0):.4f}" for k in key_feats]
    parts.append("Key features: " + ", ".join(feat_strs))
    return "\n\n".join(parts)


def write_library_md(exemplars: list[dict], path: str):
    lines = [
        "# XAUUSD Representative Trace Library",
        "",
        BANNER,
        "",
        f"Curated exemplar set: **{len(exemplars)}** traces selected from the full corpus of 23,447.",
        "Each exemplar represents a distinct category for human/LLM inspection.",
        "",
        "---",
        "## Exemplar Index",
        "",
        "| # | Trade ID | Family | Direction | Outcome | R | Duration | Fusion | Disagreement |",
        "|---|----------|--------|-----------|---------|---|----------|--------|--------------|",
    ]
    for i, t in enumerate(exemplars):
        fusion = f"{t.get('fusion_composite', 0):.3f}/{t.get('fusion_decision', 'N/A')}"
        lines.append(
            f"| {i+1} | {t['trade_id']} | {t['family']} | {t['direction']} | "
            f"{t['outcome']} | {t['rr_achieved']:.2f} | {t['duration_candles']} | "
            f"{fusion} | {t.get('engine_disagreement', 0):.3f} |"
        )
    lines.extend(["", "---", "## Exemplar Narratives", ""])
    for i, t in enumerate(exemplars):
        lines.extend([f"### Exemplar {i+1}: {t['trade_id']}", "", format_exemplar_narrative(t), "", "---", ""])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Wrote library to %s", path)


def write_exemplars_jsonl(exemplars: list[dict], path: str):
    with open(path, "w", encoding="utf-8") as f:
        for t in exemplars:
            f.write(json.dumps(t, default=str) + "\n")
    log.info("Wrote exemplars JSONL to %s", path)


# ── Phase 4: Engine Evaluation ──────────────────────────────────────────

def compute_calibration(traces: list[dict], engine_key: str, n_bins: int = 10) -> list[dict]:
    scored = [(t[engine_key], t["outcome"] == "TP_HIT")
              for t in traces if has_engines(t) and t[engine_key] is not None]
    if not scored:
        return []
    scores, outcomes = zip(*scored)
    bins = np.linspace(0, 1, n_bins + 1)
    results = []
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = [(s >= lo if i == 0 else s > lo) and s <= hi for s in scores]
        n = sum(mask)
        win_rate = sum(o for o, m in zip(outcomes, mask) if m) / n if n >= 5 else None
        results.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": n, "win_rate": win_rate})
    return results


def compute_ic(traces: list[dict], engine_key: str) -> float:
    pairs = [(t[engine_key], 1 if t["outcome"] == "TP_HIT" else 0)
             for t in traces if has_engines(t) and t[engine_key] is not None]
    if len(pairs) < 10:
        return 0.0
    from scipy.stats import spearmanr
    r, _ = spearmanr(*zip(*pairs))
    return float(r) if not np.isnan(r) else 0.0


def compute_auc(traces: list[dict], engine_key: str) -> float:
    pairs = [(t[engine_key], 1 if t["outcome"] == "TP_HIT" else 0)
             for t in traces if has_engines(t) and t[engine_key] is not None]
    if len(pairs) < 10:
        return 0.0
    from sklearn.metrics import roc_auc_score
    try:
        return float(roc_auc_score(*zip(*pairs)))
    except Exception:
        return 0.0


def write_evaluation_md(traces: list[dict], path: str):
    all_eng = [t for t in traces if has_engines(t)]
    n = len(all_eng)

    lines = [
        "# XAUUSD Engine Descriptive Evaluation",
        "",
        BANNER,
        "",
        f"Evaluated on **{n}** traces with engine scores (out of {len(traces)} total).",
        "",
        "---",
        "## 1. Score Distributions",
        "",
        "| Engine | Mean | Std | Min | P25 | P50 | P75 | Max |",
        "|--------|-----|-----|-----|-----|-----|-----|-----|",
    ]
    for name, key in [("CRT", "engine_crt_score"), ("Gaussian", "engine_gaussian_score"),
                       ("Zone", "engine_zone_score"), ("RR", "engine_rr_score"),
                       ("Fusion", "fusion_composite")]:
        vals = [t[key] for t in all_eng if t.get(key) is not None]
        if vals:
            arr = np.array(vals)
            lines.append(
                f"| {name} | {np.mean(arr):.4f} | {np.std(arr):.4f} | {np.min(arr):.4f} | "
                f"{np.percentile(arr, 25):.4f} | {np.percentile(arr, 50):.4f} | "
                f"{np.percentile(arr, 75):.4f} | {np.max(arr):.4f} |"
            )

    lines.extend(["", "---", "## 2. Pairwise Agreement (Pearson r)", "", "| Engine A | Engine B | r |", "|---|---|---|"])
    eng_pairs = [("CRT", "engine_crt_score"), ("Gaussian", "engine_gaussian_score"),
                 ("Zone", "engine_zone_score"), ("RR", "engine_rr_score")]
    for i, (n1, k1) in enumerate(eng_pairs):
        for n2, k2 in eng_pairs[i+1:]:
            a1, a2 = np.array([t[k1] for t in all_eng]), np.array([t[k2] for t in all_eng])
            if np.std(a1) > 0 and np.std(a2) > 0:
                lines.append(f"| {n1} | {n2} | {float(np.corrcoef(a1, a2)[0, 1]):.4f} |")

    lines.extend(["", "---", "## 3. Direction Agreement", "", "| Configuration | Count | Pct |", "|---|---|---|"])
    crt_dir = np.array([t["engine_crt_score"] >= 0.5 for t in all_eng])
    gauss_dir = np.array([t["engine_gaussian_score"] >= 0.5 for t in all_eng])
    zone_dir = np.array([t["engine_zone_score"] >= 0.5 for t in all_eng])
    rr_dir = np.array([t["engine_rr_score"] >= 0.5 for t in all_eng])
    all4 = int(np.sum(crt_dir & gauss_dir & zone_dir & rr_dir))
    any3 = int(np.sum((crt_dir.astype(int) + gauss_dir.astype(int) + zone_dir.astype(int) + rr_dir.astype(int)) >= 3))
    any2 = int(np.sum((crt_dir.astype(int) + gauss_dir.astype(int) + zone_dir.astype(int) + rr_dir.astype(int)) >= 2))
    lines.append(f"| All 4 agree | {all4} | {100*all4/n:.1f}% |")
    lines.append(f"| >=3 agree | {any3} | {100*any3/n:.1f}% |")
    lines.append(f"| >=2 agree | {any2} | {100*any2/n:.1f}% |")

    # 4. Calibration
    lines.extend(["", "---", "## 4. Calibration (binned score vs win rate)", ""])
    for name, key in [("CRT", "engine_crt_score"), ("Gaussian", "engine_gaussian_score"),
                       ("Zone", "engine_zone_score"), ("RR", "engine_rr_score"),
                       ("Fusion", "fusion_composite")]:
        cal = compute_calibration(all_eng, key)
        lines.append(f"### {name}\n| Score bin | N | Win rate |\n|---|---|---|")
        for c in cal:
            wr = f"{c['win_rate']:.3f}" if c['win_rate'] is not None else "N/A"
            lines.append(f"| {c['bin']} | {c['n']} | {wr} |")
        lines.append("")

    # 5. Discrimination
    lines.extend(["---", "## 5. Discrimination Metrics", "", "| Engine | AUC | IC (Spearman) |", "|---|---|---|"])
    for name, key in [("CRT", "engine_crt_score"), ("Gaussian", "engine_gaussian_score"),
                       ("Zone", "engine_zone_score"), ("RR", "engine_rr_score"),
                       ("Fusion", "fusion_composite")]:
        lines.append(f"| {name} | {compute_auc(all_eng, key):.4f} | {compute_ic(all_eng, key):.4f} |")

    # 6. Coverage
    lines.extend(["", "---", "## 6. Coverage (fraction above gate threshold)", "",
                  "| Engine | Threshold | Above | Pct |", "|---|---|---|"])
    for name, key, thresh in [("CRT", "engine_crt_score", 0.5),
                               ("Gaussian", "engine_gaussian_score", 0.5),
                               ("Zone", "engine_zone_score", 0.5),
                               ("RR", "engine_rr_score", 0.5),
                               ("Fusion", "fusion_composite", 0.5)]:
        vals = [t[key] for t in all_eng if t.get(key) is not None]
        above = sum(1 for v in vals if v >= thresh)
        lines.append(f"| {name} | {thresh} | {above} | {100*above/len(vals):.1f}% |")

    # 7. Disagreement profiling
    lines.extend(["", "---", "## 7. Disagreement Profile", "",
                  "High-disagreement traces (engine_disagreement > 0.35):"])
    high_d = [t for t in all_eng if t.get("engine_disagreement", 0) > 0.35]
    lines.append(f"Count: {len(high_d)} / {n} ({100*len(high_d)/n:.1f}%)")
    if high_d:
        lines.append("\n### Feature comparison: high-disagreement vs all traces")
        lines.append("| Feature | High-Disagreement Mean | All Traces Mean | Diff |")
        lines.append("|---|---|---|---|")
        for feat in ["body_ratio", "disp_strength", "retest_depth", "atr", "rsi_14",
                      "volume_ratio", "sweep_detected", "trend_bias", "momentum_score"]:
            hd_vals = [get_feature_dict(t).get(feat, 0) for t in high_d]
            all_vals = [get_feature_dict(t).get(feat, 0) for t in all_eng]
            hd_mean, all_mean = float(np.mean(hd_vals)), float(np.mean(all_vals))
            lines.append(f"| {feat} | {hd_mean:.4f} | {all_mean:.4f} | {hd_mean - all_mean:+.4f} |")

    # 8. Pre-existing finding alignment
    lines.extend(["", "---", "## 8. Alignment with Pre-existing Findings", "",
                  "### F-036 (Zone non-pivotal)", "",
                  f"Zone AUC vs outcome: {compute_auc(all_eng, 'engine_zone_score'):.4f} (F-036 predicts non-pivotal)",
                  "",
                  "### F-037 (CRT-only spine)",
                  f"CRT AUC vs outcome: {compute_auc(all_eng, 'engine_crt_score'):.4f} (F-037: CRT-only spine in backtest)",
                  "",
                  "### F-044 (RR confidence gate mis-scaled)",
                  f"RR AUC vs outcome: {compute_auc(all_eng, 'engine_rr_score'):.4f} (F-044: gate mis-scaled, not model)",
                  "",
                  "### F-019...F-042 (cross-asset null)",
                  f"Fusion AUC vs outcome: {compute_auc(all_eng, 'fusion_composite'):.4f} (cross-asset null predicts AUC~0.5)",
                  ""])

    # 9. Engine by family
    lines.extend(["---", "## 9. Engine Performance by Family", "",
                  "| Family | N | CRT AUC | Gaussian AUC | Zone AUC | RR AUC | Fusion AUC |", "|---|---|---|---|---|---|---|"])
    for family in ["expansion_breakout", "mean_reversion"]:
        fam_traces = [t for t in all_eng if t["family"] == family]
        if fam_traces:
            lines.append(f"| {family} | {len(fam_traces)} | "
                         f"{compute_auc(fam_traces, 'engine_crt_score'):.4f} | "
                         f"{compute_auc(fam_traces, 'engine_gaussian_score'):.4f} | "
                         f"{compute_auc(fam_traces, 'engine_zone_score'):.4f} | "
                         f"{compute_auc(fam_traces, 'engine_rr_score'):.4f} | "
                         f"{compute_auc(fam_traces, 'fusion_composite'):.4f} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Wrote evaluation to %s", path)


def main():
    log.info("=" * 60)
    log.info("Phase 3+4: Representative Library + Engine Evaluation")
    log.info("=" * 60)

    traces = load_corpus(CORPUS_PATH)
    log.info("Loaded %d traces", len(traces))

    log.info("\n--- Phase 3: Building Representative Library ---")
    exemplars = select_exemplars(traces)
    write_library_md(exemplars, LIBRARY_MD_PATH)
    write_exemplars_jsonl(exemplars, EXEMPLARS_PATH)

    log.info("\n--- Phase 4: Engine Descriptive Evaluation ---")
    write_evaluation_md(traces, EVAL_MD_PATH)

    log.info("\nAll done.")


if __name__ == "__main__":
    main()
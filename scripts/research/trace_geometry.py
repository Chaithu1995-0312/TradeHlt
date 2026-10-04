# -*- coding: utf-8 -*-
"""trace_geometry.py — DESCRIPTIVE geometry over the Mathematical Trace Corpus (ERP).

Organizes the 23k-trace population into mathematically-similar regions BEFORE any interpretation:
normalize -> KMeans (k chosen by subsampled silhouette) -> cluster library (centroid / outcome
distribution / feature signature / representative traces). Extends the F-023 morphology pattern
(scripts/analysis/bnbusdt_trade_anatomy.py::cluster_morphology).

GOVERNANCE — clusters are NOT edges. F-023 established that morphology separates SHAPE, not expectancy.
A cluster's outcome distribution is DESCRIPTIVE population structure, never a promotable signal; a cluster
only becomes a hypothesis via the full M4 gate + OOS + costs (a separate step). Information not authority
(§6.5). No edge/profit claim; UNTRUSTED_RAW; corpus stays FROZEN_CANDIDATE.

Usage:
  python scripts/research/trace_geometry.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from sklearn.metrics import silhouette_score  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from utils.console_safe import safe_print  # noqa: E402
from utils.run_manifest import build_manifest, write_run  # noqa: E402

CORPUS_DIR = _ROOT / "results" / "research" / "trace_corpus" / "xauusd"
CORPUS = CORPUS_DIR / "trace_corpus.jsonl"
GEO_DIR = CORPUS_DIR / "geometry"
RUNS_DIR = _ROOT / "results" / "test_runs"
K_SWEEP = [4, 6, 8, 10, 12]
N_REP = 5  # representative traces per cluster

# Absolute price-LEVEL features: their variance over gold's 2400->4500 trajectory dominates a z-scored
# clustering, so it splits on price REGIME, not MORPHOLOGY. Excluded by default (matches F-023's curated
# shape subset + the "mathematical fingerprint" intent). Use --include-levels to cluster on all 38.
_LEVEL_FEATURES = [
    "open", "high", "low", "close", "volume",
    "ema_fast", "ema_slow", "ema_spread",
    "macd_line", "macd_signal", "macd_hist",
    "swing_high", "swing_low", "body_size", "wick_size",
]
MORPHOLOGY_FEATURES = [f for f in CANONICAL_FEATURES if f not in _LEVEL_FEATURES]
BANNER = ("DESCRIPTIVE — clusters are NOT edges (F-023: morphology separates SHAPE, not expectancy); "
          "outcome distributions are population structure, NOT promotable signals; §6.5 information not authority.")


def _load() -> pd.DataFrame:
    return pd.read_json(CORPUS, lines=True)


def _matrix(df: pd.DataFrame, feature_names: list[str]):
    """Return (kept_df, X original, feat_names_used, n_dropped_rows, dropped_zero_var)."""
    feat_cols = [f"feature_{n}" for n in feature_names]
    kept = df.dropna(subset=feat_cols).reset_index(drop=True)
    n_dropped = int(len(df) - len(kept))
    X = kept[feat_cols].astype(float)
    stds = X.std(axis=0)
    zero_var = [c for c in feat_cols if stds[c] == 0.0]
    used = [c for c in feat_cols if c not in zero_var]
    return kept, X[used], used, n_dropped, [c.replace("feature_", "") for c in zero_var]


def _sweep(Xs: np.ndarray) -> tuple[int, list[dict], dict]:
    results, models = [], {}
    for k in K_SWEEP:
        if k >= len(Xs):
            continue
        km = KMeans(n_clusters=k, random_state=0, n_init=10).fit(Xs)
        sil = float(silhouette_score(Xs, km.labels_, sample_size=min(2000, len(Xs)), random_state=0))
        results.append({"k": k, "silhouette": round(sil, 6), "inertia": round(float(km.inertia_), 4)})
        models[k] = km
    best = max(results, key=lambda r: r["silhouette"])["k"]
    return best, results, models


def build(df: pd.DataFrame, feature_names: list[str], feature_set: str) -> dict:
    kept, Xdf, used, n_dropped, zero_var = _matrix(df, feature_names)
    names = [c.replace("feature_", "") for c in used]
    scaler = StandardScaler().fit(Xdf.values)
    Xs = scaler.transform(Xdf.values)

    k_sel, sweep, models = _sweep(Xs)
    km = models[k_sel]
    labels = km.labels_
    # distance of each point to its own centroid (standardized space)
    dists = np.linalg.norm(Xs - km.cluster_centers_[labels], axis=1)

    clusters: dict[str, dict] = {}
    for c in range(k_sel):
        idx = np.where(labels == c)[0]
        if idx.size == 0:
            continue
        members = kept.iloc[idx]
        oc = members["outcome"].value_counts()
        total = int(idx.size)
        # feature signature: standardized centroid components, largest |z| first
        z = km.cluster_centers_[c]
        sig = sorted(({"feature": names[j], "z": round(float(z[j]), 4)} for j in range(len(names))),
                     key=lambda d: abs(d["z"]), reverse=True)[:8]
        reps = members.assign(_d=dists[idx]).nsmallest(N_REP, "_d")["trade_id"].tolist()
        clusters[str(c)] = {
            "size": total,
            "family_composition": {k: int(v) for k, v in members["family"].value_counts().items()},
            "outcome_distribution": {
                "counts": {k: int(v) for k, v in oc.items()},
                "fractions": {k: round(int(v) / total, 4) for k, v in oc.items()},
            },
            "median_mfe": round(float(members["mfe"].median()), 6),
            "median_mae": round(float(members["mae"].median()), 6),
            "median_duration": round(float(members["duration_candles"].median()), 2),
            "mean_rr_achieved": round(float(members["rr_achieved"].mean()), 4),  # DESCRIPTIVE, not a signal
            "centroid_original_units": {names[j]: round(float(Xdf[used[j]].iloc[idx].mean()), 6)
                                        for j in range(len(names))},
            "feature_signature": sig,
            "representative_trade_ids": reps,
        }

    return {
        "banner": BANNER, "n_traces": int(len(df)), "n_kept": int(len(kept)), "n_dropped_rows": n_dropped,
        "feature_set": feature_set,
        "level_features_excluded": ([] if feature_set == "all" else _LEVEL_FEATURES),
        "dropped_zero_variance_features": zero_var, "features_used": names,
        "k_selected": k_sel, "k_sweep": sweep,
        "clusters": clusters,
        "_labels": labels, "_Xs": Xs, "_centroids": km.cluster_centers_,
        "_assignments": [{"trade_id": t, "cluster": int(l), "dist_to_centroid": round(float(d), 6)}
                         for t, l, d in zip(kept["trade_id"], labels, dists)],
    }


def _markdown(rep: dict) -> str:
    L = ["# XAUUSD Trace Geometry — Descriptive Cluster Library", "",
         f"> {rep['banner']}", "",
         f"Traces: **{rep['n_traces']}** (kept {rep['n_kept']}, dropped {rep['n_dropped_rows']} NaN-feature rows) · "
         f"feature_set: **{rep['feature_set']}** ({len(rep['features_used'])} features) · "
         f"dropped zero-variance: {rep['dropped_zero_variance_features']}",
         "", f"> Clustered on dimensionless SHAPE features; absolute price-LEVEL features excluded "
         f"({rep['level_features_excluded'] or 'none'}) — their trajectory variance would split on price "
         f"regime, not morphology (descriptive note).",
         "", f"**k selected = {rep['k_selected']}** by subsampled silhouette. Sweep:",
         "", "| k | silhouette | inertia |", "|--:|--:|--:|"]
    for s in rep["k_sweep"]:
        L.append(f"| {s['k']} | {s['silhouette']:.4f} | {s['inertia']:.1f} |")
    L += ["", "## Clusters (descriptive population structure — NOT edges)", ""]
    for c, d in sorted(rep["clusters"].items(), key=lambda kv: -kv[1]["size"]):
        fr = d["outcome_distribution"]["fractions"]
        sig = ", ".join(f"{s['feature']}({s['z']:+.2f})" for s in d["feature_signature"][:6])
        L += [f"### Cluster {c} — n={d['size']}",
              f"- family: {d['family_composition']}",
              f"- outcome: SL {fr.get('SL_HIT', 0):.0%} · TP {fr.get('TP_HIT', 0):.0%} · TIMEOUT {fr.get('TIMEOUT', 0):.0%}",
              f"- median MFE {d['median_mfe']:.4f} · median MAE {d['median_mae']:.4f} · median dur {d['median_duration']} · mean R {d['mean_rr_achieved']:+.3f} (descriptive)",
              f"- feature signature (|z| top): {sig}",
              f"- representatives: {d['representative_trade_ids']}", ""]
    L += [f"> {rep['banner']}", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="trace_geometry",
                                 description="Descriptive KMeans geometry over the XAUUSD trace corpus")
    ap.add_argument("--features", choices=["morphology", "all"], default="morphology",
                    help="'morphology' = dimensionless shape features (default); 'all' = 38 incl. price levels")
    args = ap.parse_args(argv)
    if not CORPUS.exists():
        safe_print(f"No corpus at {CORPUS} — run build_trace_corpus.py first.")
        return 1
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    feature_names = list(CANONICAL_FEATURES) if args.features == "all" else MORPHOLOGY_FEATURES
    rep = build(_load(), feature_names, args.features)

    # numpy artifact (centroids + standardized matrix + labels) — no pyarrow needed
    np.savez(GEO_DIR / "geometry.npz", Xs=rep.pop("_Xs"), centroids=rep.pop("_centroids"),
             labels=rep.pop("_labels"), features=np.array(rep["features_used"]))
    assignments = rep.pop("_assignments")
    (GEO_DIR / "cluster_assignments.jsonl").write_text(
        "\n".join(json.dumps(a) for a in assignments) + "\n", encoding="utf-8")
    (GEO_DIR / "cluster_library.json").write_text(json.dumps(rep, indent=2, sort_keys=True), encoding="utf-8")
    (GEO_DIR / "CLUSTERS.md").write_text(_markdown(rep), encoding="utf-8")

    manifest = build_manifest(
        command="python scripts/research/trace_geometry.py", argv=sys.argv,
        validation_lens="trace_geometry_descriptive", exit_model="intrabar_fixed", cost_model_bps=0,
        label_source="forward_walk_intrabar_fixed", instruments=["XAUUSD"], timeframe="M15",
        data_source="local_csv_mt5", network="none", dry_run=True, intended_work_item_id="WI-006")
    write_run(RUNS_DIR / manifest["run_id"], manifest,
              {"descriptive_only": True, "non_promotable": True, "k_selected": rep["k_selected"],
               "n_kept": rep["n_kept"], "note": BANNER})

    safe_print(f"k={rep['k_selected']} over {rep['n_kept']} traces -> {GEO_DIR / 'CLUSTERS.md'}")
    safe_print(BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

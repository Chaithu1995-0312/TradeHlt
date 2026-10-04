# -*- coding: utf-8 -*-
"""trace_knn.py — DESCRIPTIVE k-NN similarity graph over the Trace Geometry (ERP).

Builds a per-trace nearest-neighbour graph in the SAME standardized morphology space as the clusters
(reuses geometry.npz), then asks the sharper LOCAL question the clusters can't: do a trace's nearest
neighbours share its outcome? If neighbourhood outcome-concordance ≈ the random baseline, morphology
gives NO local outcome structure — a finer-resolution re-confirmation of F-023.

GOVERNANCE — neighbourhoods are NOT edges. A neighbourhood with a high TP-rate is descriptive population
structure, never a signal; it becomes a hypothesis only via the full M4 gate + OOS + costs. Information
not authority (§6.5). No edge/profit claim; UNTRUSTED_RAW; corpus stays FROZEN_CANDIDATE.

Reuse: geometry.npz (Xs) + cluster_assignments.jsonl (aligned), the corpus (outcome/rr), and
ReplaySimilarityIndex.aggregate_top_k_stats (similarity-weighted neighbourhood win_rate/mean_rr). The
batch graph uses sklearn NearestNeighbors (the replay index's per-query scan does not scale to 23k²).

Usage:
  python scripts/research/trace_geometry.py   # produces geometry.npz first
  python scripts/research/trace_knn.py --k 10 --metric cosine
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.neighbors import NearestNeighbors  # noqa: E402

from replay.replay_similarity_index import ReplaySimilarityIndex  # noqa: E402  (reuse aggregation)
from utils.console_safe import safe_print  # noqa: E402
from utils.run_manifest import build_manifest, write_run  # noqa: E402

CORPUS_DIR = _ROOT / "results" / "research" / "trace_corpus" / "xauusd"
GEO_DIR = CORPUS_DIR / "geometry"
KNN_DIR = CORPUS_DIR / "knn"
RUNS_DIR = _ROOT / "results" / "test_runs"
BANNER = ("DESCRIPTIVE — neighbourhoods are NOT edges (F-023: morphology separates SHAPE, not "
          "expectancy); neighbourhood outcome stats are population structure, NOT signals; §6.5 "
          "information not authority.")


def _load():
    Xs = np.load(GEO_DIR / "geometry.npz", allow_pickle=True)["Xs"]
    assign = [json.loads(ln) for ln in (GEO_DIR / "cluster_assignments.jsonl")
              .read_text(encoding="utf-8").splitlines() if ln.strip()]
    if len(assign) != len(Xs):
        raise SystemExit(f"alignment error: {len(assign)} assignments != {len(Xs)} Xs rows")
    corpus = pd.read_json(CORPUS_DIR / "trace_corpus.jsonl", lines=True)
    meta = corpus.set_index("trade_id")[["outcome", "rr_achieved"]].to_dict("index")
    trade_ids = [a["trade_id"] for a in assign]
    clusters = [int(a["cluster"]) for a in assign]
    outcomes = [meta[t]["outcome"] for t in trade_ids]
    rrs = [float(meta[t]["rr_achieved"]) for t in trade_ids]
    return Xs, trade_ids, clusters, outcomes, rrs


def _quantiles(a: np.ndarray) -> dict:
    return {"mean": round(float(a.mean()), 4), "std": round(float(a.std()), 4),
            "p10": round(float(np.quantile(a, 0.10)), 4), "p50": round(float(np.quantile(a, 0.50)), 4),
            "p90": round(float(np.quantile(a, 0.90)), 4)}


def build(k: int, metric: str) -> tuple[dict, list]:
    Xs, trade_ids, clusters, outcomes, rrs = _load()
    n = len(Xs)
    nn = NearestNeighbors(n_neighbors=min(k + 1, n), metric=metric).fit(Xs)
    dist, idx = nn.kneighbors(Xs)  # includes self at col 0

    agg = ReplaySimilarityIndex(n_features=Xs.shape[1], top_k=k, use_faiss=False)
    # similarity: cosine distance in [0,2] -> sim=1-d; euclidean -> sim=1/(1+d) (monotone, descriptive)
    def _sim(d):
        return (1.0 - d) if metric == "cosine" else (1.0 / (1.0 + d))

    counts = Counter(outcomes)
    base_same = sum((v / n) ** 2 for v in counts.values())      # random same-outcome concordance
    base_tp = counts.get("TP_HIT", 0) / n                        # global TP rate

    graph: list[dict] = []
    conc = np.zeros(n); tprate = np.zeros(n); dens = np.zeros(n); xclu = np.zeros(n)
    nb_win = np.zeros(n)
    for i in range(n):
        nbr = [j for j in idx[i] if j != i][:k]
        sims = [_sim(float(d)) for d, j in zip(dist[i], idx[i]) if j != i][:k]
        nb_out = [outcomes[j] for j in nbr]
        conc[i] = sum(1 for o in nb_out if o == outcomes[i]) / max(len(nbr), 1)
        tprate[i] = sum(1 for o in nb_out if o == "TP_HIT") / max(len(nbr), 1)
        dens[i] = float(np.mean([d for d, j in zip(dist[i], idx[i]) if j != i][:k]))
        xclu[i] = sum(1 for j in nbr if clusters[j] != clusters[i]) / max(len(nbr), 1)
        stats = agg.aggregate_top_k_stats([(s, {"rr": rrs[j], "outcome": outcomes[j]})
                                           for s, j in zip(sims, nbr)])
        nb_win[i] = stats["win_rate"]
        graph.append({"trade_id": trade_ids[i], "cluster": clusters[i], "outcome": outcomes[i],
                      "neighbours": [{"trade_id": trade_ids[j], "similarity": round(s, 4),
                                      "cluster": clusters[j], "outcome": outcomes[j]}
                                     for s, j in zip(sims, nbr)]})

    summary = {
        "banner": BANNER, "n_traces": n, "k": k, "metric": metric,
        "outcome_base_rates": {o: round(c / n, 4) for o, c in counts.items()},
        "random_baseline": {"same_outcome_concordance": round(base_same, 4), "tp_rate": round(base_tp, 4)},
        "neighbourhood_outcome_concordance": _quantiles(conc),
        "neighbourhood_tp_rate": _quantiles(tprate),
        "neighbourhood_win_rate_replay_agg": _quantiles(nb_win),
        "local_density_dist_to_k": _quantiles(dens),
        "cross_cluster_edge_fraction": _quantiles(xclu),
        "read": ("concordance ≈ random baseline ⇒ static entry-state OHLCV morphology gives no LOCAL "
                 "outcome structure on this corpus (finer-resolution F-023). This is NOT a claim about "
                 "UNMEASURED information classes (temporal/HTF/execution/order-flow/macro/alt-data — see "
                 "docs/research-readiness/erp-information-class-boundary.md). Descriptive, no edge claim."),
    }
    return summary, graph


def _markdown(s: dict) -> str:
    c, b = s["neighbourhood_outcome_concordance"], s["random_baseline"]
    tp = s["neighbourhood_tp_rate"]
    return "\n".join([
        "# XAUUSD Trace k-NN Similarity Graph — Descriptive", "",
        f"> {s['banner']}", "",
        f"n={s['n_traces']} · k={s['k']} · metric={s['metric']}", "",
        "## Local outcome structure (the sharp question)", "",
        f"- neighbourhood same-outcome concordance: mean **{c['mean']}** "
        f"(p10 {c['p10']} / p50 {c['p50']} / p90 {c['p90']}) vs random baseline "
        f"**{b['same_outcome_concordance']}**",
        f"- neighbourhood TP-rate: mean **{tp['mean']}** vs global TP-rate **{b['tp_rate']}**",
        f"- replay-agg neighbourhood win_rate: mean {s['neighbourhood_win_rate_replay_agg']['mean']}",
        "", f"> {s['read']}", "",
        "## Graph geometry", "",
        f"- local density (mean dist to k): mean {s['local_density_dist_to_k']['mean']}",
        f"- cross-cluster edge fraction (bridges): mean {s['cross_cluster_edge_fraction']['mean']}",
        "", f"> {s['banner']}", "",
    ])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="trace_knn", description="Descriptive k-NN similarity graph")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--metric", choices=["cosine", "euclidean"], default="cosine")
    args = ap.parse_args(argv)
    if not (GEO_DIR / "geometry.npz").exists():
        safe_print("No geometry.npz — run scripts/research/trace_geometry.py first.")
        return 1

    KNN_DIR.mkdir(parents=True, exist_ok=True)
    summary, graph = build(args.k, args.metric)
    (KNN_DIR / "knn_graph.jsonl").write_text(
        "\n".join(json.dumps(g) for g in graph) + "\n", encoding="utf-8")
    (KNN_DIR / "knn_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (KNN_DIR / "KNN.md").write_text(_markdown(summary), encoding="utf-8")

    manifest = build_manifest(
        command="python scripts/research/trace_knn.py", argv=sys.argv,
        validation_lens="trace_knn_descriptive", exit_model="intrabar_fixed", cost_model_bps=0,
        label_source="forward_walk_intrabar_fixed", instruments=["XAUUSD"], timeframe="M15",
        data_source="local_csv_mt5", network="none", dry_run=True, intended_work_item_id="WI-007")
    write_run(RUNS_DIR / manifest["run_id"], manifest,
              {"descriptive_only": True, "non_promotable": True, "k": args.k, "metric": args.metric,
               "n_traces": summary["n_traces"], "note": BANNER})

    safe_print(f"k-NN (k={args.k}, {args.metric}) over {summary['n_traces']} traces -> {KNN_DIR / 'KNN.md'}")
    safe_print(f"  concordance mean={summary['neighbourhood_outcome_concordance']['mean']} "
               f"vs baseline={summary['random_baseline']['same_outcome_concordance']}")
    safe_print(BANNER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

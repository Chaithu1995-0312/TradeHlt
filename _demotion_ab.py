"""P3 — Governance demotion A/B (single variable).

H0: Governance (RECORDED / docs/governance) dominates ranking and suppresses
truth artifacts.

A = full corpus ranking (baseline weights)
B = same index, RECORDED truth_class_weight collapsed (query-time demotion only;
    no rebuild, no other weight changes)

Reports Recall@5/10, MRR, mean/median best-truth-rank, pct in top-500.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
sys.path.insert(0, str(ROOT / "src"))

from retrieval import RetrievalPipeline
from retrieval.config import build_default_config

GOLD = ROOT / "scripts/evaluation/benchmark_100.json"
OUT = ROOT / "results/evaluation/governance_demotion_ab_2026-09-11.json"
TOP_K_RANK = 500
TOP_K_EVAL = 10


def eval_variant(name: str, pipe: RetrievalPipeline, questions: list[dict], recorded_weight: float) -> dict:
    pipe.config.truth_class_weights["RECORDED"] = recorded_weight
    # keep everything else at defaults already on pipe.config

    ranks: list[int | None] = []
    best_ranks: list[int] = []
    recalls5 = []
    recalls10 = []
    mrrs = []
    n_q = 0

    for q in questions:
        if q.get("is_hallucination_test"):
            continue
        n_q += 1
        expected = list(q.get("expected_files") or [])
        hits = pipe.lexical.search(q["question"], top_k=TOP_K_RANK, include_historical=True)
        file_rank: dict[str, int] = {}
        for rank, h in enumerate(hits, 1):
            if h.filepath not in file_rank:
                file_rank[h.filepath] = rank

        # deep ranks
        per = [file_rank.get(ef) for ef in expected]
        ranks.extend(per)
        returned = [r for r in per if r is not None]
        if returned:
            best_ranks.append(min(returned))

        # recall metrics on unique filepath order
        fps = []
        seen = set()
        for h in hits:
            if h.filepath not in seen:
                seen.add(h.filepath)
                fps.append(h.filepath)
        top5 = fps[:5]
        top10 = fps[:10]
        if expected:
            r5 = sum(1 for ef in expected if ef in top5) / len(expected)
            r10 = sum(1 for ef in expected if ef in top10) / len(expected)
        else:
            r5 = r10 = 0.0
        recalls5.append(r5)
        recalls10.append(r10)
        mrr = 0.0
        for i, fp in enumerate(fps, 1):
            if fp in expected:
                mrr = 1.0 / i
                break
        mrrs.append(mrr)

    returned_ranks = [r for r in ranks if r is not None]
    return {
        "name": name,
        "recorded_weight": recorded_weight,
        "n_questions": n_q,
        "n_truth_refs": len(ranks),
        "avg_recall_at_5": round(sum(recalls5) / max(len(recalls5), 1), 4),
        "avg_recall_at_10": round(sum(recalls10) / max(len(recalls10), 1), 4),
        "avg_mrr": round(sum(mrrs) / max(len(mrrs), 1), 4),
        "pct_refs_in_top5": round(sum(1 for r in ranks if r is not None and r <= 5) / max(len(ranks), 1), 4),
        "pct_refs_in_top10": round(sum(1 for r in ranks if r is not None and r <= 10) / max(len(ranks), 1), 4),
        "pct_refs_in_top500": round(sum(1 for r in ranks if r is not None) / max(len(ranks), 1), 4),
        "pct_refs_not_returned": round(sum(1 for r in ranks if r is None) / max(len(ranks), 1), 4),
        "mean_truth_rank_when_returned": round(statistics.mean(returned_ranks), 2) if returned_ranks else None,
        "median_truth_rank_when_returned": round(statistics.median(returned_ranks), 2) if returned_ranks else None,
        "mean_best_truth_rank": round(statistics.mean(best_ranks), 2) if best_ranks else None,
        "median_best_truth_rank": round(statistics.median(best_ranks), 2) if best_ranks else None,
        "pct_questions_any_top5": round(sum(1 for r in recalls5 if r > 0) / max(len(recalls5), 1), 4),
    }


def main() -> None:
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    questions = gold["questions"]
    cfg = build_default_config()
    baseline_recorded = float(cfg.truth_class_weights.get("RECORDED", 1.2))
    pipe = RetrievalPipeline(cfg)
    t0 = time.time()
    pipe.lexical.ensure_loaded()
    print(f"loaded in {time.time()-t0:.1f}s")

    print("=== A: full (baseline RECORDED weight) ===")
    a = eval_variant("A_full", pipe, questions, recorded_weight=baseline_recorded)
    print(json.dumps(a, indent=2))

    print("=== B: RECORDED demoted to 0.05 ===")
    b = eval_variant("B_recorded_demoted", pipe, questions, recorded_weight=0.05)
    print(json.dumps(b, indent=2))

    # restore
    pipe.config.truth_class_weights["RECORDED"] = baseline_recorded

    delta = {
        "recall_at_5_delta": round(b["avg_recall_at_5"] - a["avg_recall_at_5"], 4),
        "recall_at_10_delta": round(b["avg_recall_at_10"] - a["avg_recall_at_10"], 4),
        "mrr_delta": round(b["avg_mrr"] - a["avg_mrr"], 4),
        "pct_top500_delta": round(b["pct_refs_in_top500"] - a["pct_refs_in_top500"], 4),
        "median_rank_delta": (
            None
            if a["median_truth_rank_when_returned"] is None or b["median_truth_rank_when_returned"] is None
            else round(b["median_truth_rank_when_returned"] - a["median_truth_rank_when_returned"], 2)
        ),
    }

    payload = {
        "meta": {
            "date": "2026-09-11",
            "hypothesis": "H0: Governance (RECORDED) dominates ranking and suppresses truth artifacts",
            "method": "single-variable query-time RECORDED weight demotion; same index; no rebuild",
            "A": f"RECORDED weight = {baseline_recorded}",
            "B": "RECORDED weight = 0.05",
            "held_constant": ["index", "BM25", "CURRENT/INTENDED/REFERENCE/HISTORICAL weights", "gold set"],
        },
        "A": a,
        "B": b,
        "delta_B_minus_A": delta,
        "verdict_notes": (
            "If B does not materially lift Recall@5/MRR/mean truth rank, H0 is weakened — "
            "CURRENT crowding (seen in P1) is a co-equal or dominant cause. "
            "If B lifts, governance demotion is a validated lever."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("DELTA", delta)
    print("wrote", OUT)


if __name__ == "__main__":
    main()

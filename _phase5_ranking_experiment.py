"""Phase-5 ranking-layer measurement (not whole-stack evaluation).

Populations (defined BEFORE measuring):
  A — at least one expected truth file appears in lexical top-N candidates
  B — no expected truth file in lexical top-N (dense cannot help)

H0: Dense reranking does not improve truth-file rank
    (tested on Population A only via rerank_lift = rank_before - rank_after).

candidate_reach_rate = fraction of truth-file refs present in lexical candidates
                     = |Population A refs| / |all truth refs|
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
OUT = ROOT / "results/evaluation/phase5_ranking_layer_2026-09-11.json"
CAND_N = 100  # lexical candidate depth; ranking layer only operates inside this set
MODEL_ID = "all-MiniLM-L6-v2"


def filepath_order(hits) -> list[str]:
    out, seen = [], set()
    for h in hits:
        if h.filepath not in seen:
            seen.add(h.filepath)
            out.append(h.filepath)
    return out


def ranks_for(expected: list[str], order: list[str]) -> list[int | None]:
    pos = {fp: i for i, fp in enumerate(order, 1)}
    return [pos.get(ef) for ef in expected]


def best_rank(ranks: list[int | None]) -> int | None:
    rs = [r for r in ranks if r is not None]
    return min(rs) if rs else None


def main() -> None:
    from sentence_transformers import SentenceTransformer
    import numpy as np

    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    questions = [q for q in gold["questions"] if not q.get("is_hallucination_test")]

    pipe = RetrievalPipeline(build_default_config())
    t0 = time.time()
    pipe.lexical.ensure_loaded()
    print(f"lexical loaded {time.time()-t0:.1f}s")

    print(f"loading {MODEL_ID}...")
    t0 = time.time()
    model = SentenceTransformer(MODEL_ID)
    print(f"model loaded {time.time()-t0:.1f}s")

    rows = []
    # per-ref tracking
    n_refs = 0
    n_refs_reached = 0
    lifts_A: list[float] = []  # only when before and after both defined
    pop_A_q = 0
    pop_B_q = 0

    # Population A head metrics
    A_r5_before, A_r5_after = [], []
    A_r10_before, A_r10_after = [], []
    A_mrr_before, A_mrr_after = [], []
    A_best_before, A_best_after = [], []

    for i, q in enumerate(questions, 1):
        expected = list(q.get("expected_files") or [])
        query = q["question"]
        hits = pipe.lexical.search(query, top_k=CAND_N, include_historical=True)

        lex_order = filepath_order(hits)
        before_ranks = ranks_for(expected, lex_order)
        before_best = best_rank(before_ranks)

        # reach: any expected file in candidates?
        reached_flags = [r is not None for r in before_ranks]
        n_refs += len(expected)
        n_refs_reached += sum(1 for x in reached_flags if x)
        in_pop_A = any(reached_flags)
        population = "A" if in_pop_A else "B"
        if in_pop_A:
            pop_A_q += 1
        else:
            pop_B_q += 1

        # dense rerank (chunk-level cosine → collapse to filepath by best score)
        if hits:
            texts = [h.text[:2000] for h in hits]
            q_emb = model.encode([query], normalize_embeddings=True)
            c_emb = model.encode(
                texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False
            )
            scores = (np.asarray(c_emb) @ np.asarray(q_emb).T).reshape(-1)
            order_idx = sorted(range(len(hits)), key=lambda j: float(scores[j]), reverse=True)
            dense_hits = [hits[j] for j in order_idx]
            dense_order = filepath_order(dense_hits)
        else:
            dense_order = []

        after_ranks = ranks_for(expected, dense_order)
        after_best = best_rank(after_ranks)

        # per-ref lift where both ranks exist (Population A refs)
        per_ref = []
        for ef, b, a in zip(expected, before_ranks, after_ranks):
            lift = None
            if b is not None and a is not None:
                lift = b - a  # positive => improved (moved toward rank 1)
                lifts_A.append(lift)
            per_ref.append(
                {
                    "file": ef,
                    "rank_before": b,
                    "rank_after": a,
                    "rerank_lift": lift,
                    "in_candidates": b is not None,
                }
            )

        def head_metrics(order: list[str], ranks: list[int | None]) -> dict:
            top5, top10 = order[:5], order[:10]
            r5 = sum(1 for ef in expected if ef in top5) / max(len(expected), 1) if expected else 0.0
            r10 = sum(1 for ef in expected if ef in top10) / max(len(expected), 1) if expected else 0.0
            mrr = 0.0
            for idx, fp in enumerate(order, 1):
                if fp in expected:
                    mrr = 1.0 / idx
                    break
            return {"r5": r5, "r10": r10, "mrr": mrr, "best": best_rank(ranks)}

        mb = head_metrics(lex_order, before_ranks)
        ma = head_metrics(dense_order, after_ranks)

        if in_pop_A:
            A_r5_before.append(mb["r5"])
            A_r5_after.append(ma["r5"])
            A_r10_before.append(mb["r10"])
            A_r10_after.append(ma["r10"])
            A_mrr_before.append(mb["mrr"])
            A_mrr_after.append(ma["mrr"])
            if mb["best"] is not None:
                A_best_before.append(mb["best"])
            if ma["best"] is not None:
                A_best_after.append(ma["best"])

        rows.append(
            {
                "question_id": q["id"],
                "category": q.get("category"),
                "question": query,
                "population": population,
                "candidate_reach": in_pop_A,
                "n_candidates": len(hits),
                "expected_files": expected,
                "per_ref": per_ref,
                "best_rank_before": before_best,
                "best_rank_after": after_best,
                "question_rerank_lift": (
                    None
                    if before_best is None or after_best is None
                    else before_best - after_best
                ),
                "lexical_head": mb,
                "dense_head": ma,
            }
        )
        print(
            f"[{i:3d}/{len(questions)}] Q{q['id']:3d} pop={population} "
            f"before={before_best} after={after_best} "
            f"lift={rows[-1]['question_rerank_lift']}"
        )

    # H0 test on Population A: mean lift <= 0?
    mean_lift = statistics.mean(lifts_A) if lifts_A else None
    median_lift = statistics.median(lifts_A) if lifts_A else None
    pct_positive_lift = (
        sum(1 for x in lifts_A if x > 0) / len(lifts_A) if lifts_A else None
    )

    summary = {
        "candidate_n": CAND_N,
        "n_questions": len(questions),
        "population_A_questions": pop_A_q,
        "population_B_questions": pop_B_q,
        "candidate_reach_rate_refs": round(n_refs_reached / max(n_refs, 1), 4),
        "candidate_reach_rate_questions": round(pop_A_q / max(len(questions), 1), 4),
        "n_refs": n_refs,
        "n_refs_reached": n_refs_reached,
        "population_A": {
            "avg_recall_at_5_before": round(sum(A_r5_before) / max(len(A_r5_before), 1), 4) if A_r5_before else None,
            "avg_recall_at_5_after": round(sum(A_r5_after) / max(len(A_r5_after), 1), 4) if A_r5_after else None,
            "avg_recall_at_10_before": round(sum(A_r10_before) / max(len(A_r10_before), 1), 4) if A_r10_before else None,
            "avg_recall_at_10_after": round(sum(A_r10_after) / max(len(A_r10_after), 1), 4) if A_r10_after else None,
            "avg_mrr_before": round(sum(A_mrr_before) / max(len(A_mrr_before), 1), 4) if A_mrr_before else None,
            "avg_mrr_after": round(sum(A_mrr_after) / max(len(A_mrr_after), 1), 4) if A_mrr_after else None,
            "median_best_rank_before": round(statistics.median(A_best_before), 2) if A_best_before else None,
            "median_best_rank_after": round(statistics.median(A_best_after), 2) if A_best_after else None,
            "mean_rerank_lift_per_ref": round(mean_lift, 4) if mean_lift is not None else None,
            "median_rerank_lift_per_ref": round(median_lift, 4) if median_lift is not None else None,
            "pct_refs_positive_lift": round(pct_positive_lift, 4) if pct_positive_lift is not None else None,
            "n_ref_lifts_measured": len(lifts_A),
        },
        "H0": "Dense reranking does not improve truth-file rank (Population A)",
        "H0_result": (
            "INCONCLUSIVE_NO_POP_A"
            if not lifts_A
            else (
                "FAIL_TO_REJECT_H0_NO_IMPROVEMENT"
                if mean_lift is not None and mean_lift <= 0
                else "REJECT_H0_POSITIVE_MEAN_LIFT"
            )
        ),
        "interpretation_constraint": (
            "Dense only acts on Population A. Whole-stack Recall@5 remains dominated by "
            "Population B (candidate generation failure). Do not promote dense as a "
            "whole-stack fix from this run alone."
        ),
    }

    payload = {
        "meta": {
            "date": "2026-09-11",
            "layer": "ranking_only",
            "model": MODEL_ID,
            "protocol": f"lexical top-{CAND_N} candidates → MiniLM cosine rerank → filepath collapse",
            "prior_finding": (
                "P1: 76.6% truth refs outside top-500; candidate generation failure > ranking failure"
            ),
        },
        "summary": summary,
        "questions": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n=== PHASE-5 RANKING LAYER SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()

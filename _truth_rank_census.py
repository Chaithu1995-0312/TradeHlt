"""P1 — Truth-file rank census for the gold set (observation, not pass/fail)."""
from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
sys.path.insert(0, str(ROOT / "src"))

from retrieval import RetrievalPipeline
from retrieval.config import build_default_config

GOLD = ROOT / "scripts/evaluation/benchmark_100.json"
OUT = ROOT / "results/evaluation/truth_file_rank_census_2026-09-11.json"
TOP_K = 500  # deep enough to distinguish rank=17 vs 53 vs not-in-top-500


def main() -> None:
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    questions = [q for q in gold["questions"] if not q.get("is_hallucination_test")]
    pipe = RetrievalPipeline(build_default_config())
    # preload
    t0 = time.time()
    pipe.lexical.ensure_loaded()
    print(f"index loaded in {time.time()-t0:.1f}s; chunks={len(pipe.lexical._chunks)}")

    rows = []
    ranks_all: list[int | None] = []
    crowd_classes: Counter[str] = Counter()
    crowd_paths: Counter[str] = Counter()

    for i, q in enumerate(questions, 1):
        qid = q["id"]
        query = q["question"]
        expected = list(q.get("expected_files") or [])
        t1 = time.time()
        hits = pipe.lexical.search(query, top_k=TOP_K, include_historical=True)
        latency = (time.time() - t1) * 1000

        # first occurrence rank per filepath (1-indexed)
        file_rank: dict[str, int] = {}
        for rank, h in enumerate(hits, 1):
            fp = h.filepath
            if fp not in file_rank:
                file_rank[fp] = rank

        # crowd: top-5 filepaths that are NOT expected
        top5 = []
        seen = set()
        for h in hits:
            if h.filepath in seen:
                continue
            seen.add(h.filepath)
            top5.append(h)
            if len(top5) >= 5:
                break
        for h in top5:
            if h.filepath not in expected:
                crowd_classes[h.truth_class] += 1
                crowd_paths[h.filepath] += 1

        truth_ranks = []
        for ef in expected:
            r = file_rank.get(ef)
            truth_ranks.append(
                {
                    "file": ef,
                    "rank": r,  # None => not in top TOP_K
                    "status": (
                        "not_returned"
                        if r is None
                        else ("top5" if r <= 5 else "top10" if r <= 10 else "top50" if r <= 50 else "top100" if r <= 100 else "top500")
                    ),
                }
            )
            ranks_all.append(r)

        best = None
        returned = [tr["rank"] for tr in truth_ranks if tr["rank"] is not None]
        if returned:
            best = min(returned)

        rows.append(
            {
                "question_id": qid,
                "category": q.get("category"),
                "question": query,
                "expected_files": expected,
                "truth_ranks": truth_ranks,
                "best_truth_rank": best,
                "any_in_top5": any((tr["rank"] or 10**9) <= 5 for tr in truth_ranks),
                "any_in_top10": any((tr["rank"] or 10**9) <= 10 for tr in truth_ranks),
                "any_in_top50": any((tr["rank"] or 10**9) <= 50 for tr in truth_ranks),
                "any_in_top100": any((tr["rank"] or 10**9) <= 100 for tr in truth_ranks),
                "any_in_top500": any(tr["rank"] is not None for tr in truth_ranks),
                "top5_filepaths": [h.filepath for h in top5],
                "top5_truth_classes": [h.truth_class for h in top5],
                "latency_ms": round(latency, 2),
            }
        )
        print(
            f"[{i:3d}/{len(questions)}] Q{qid:3d} best={best} "
            f"top5={rows[-1]['any_in_top5']} top50={rows[-1]['any_in_top50']} "
            f"top500={rows[-1]['any_in_top500']}  {query[:50]}"
        )

    returned_ranks = [r for r in ranks_all if r is not None]
    summary = {
        "n_questions_non_hallucination": len(questions),
        "n_truth_file_refs": len(ranks_all),
        "top_k_searched": TOP_K,
        "pct_refs_in_top5": round(sum(1 for r in ranks_all if r is not None and r <= 5) / max(len(ranks_all), 1), 4),
        "pct_refs_in_top10": round(sum(1 for r in ranks_all if r is not None and r <= 10) / max(len(ranks_all), 1), 4),
        "pct_refs_in_top50": round(sum(1 for r in ranks_all if r is not None and r <= 50) / max(len(ranks_all), 1), 4),
        "pct_refs_in_top100": round(sum(1 for r in ranks_all if r is not None and r <= 100) / max(len(ranks_all), 1), 4),
        "pct_refs_in_top500": round(sum(1 for r in ranks_all if r is not None) / max(len(ranks_all), 1), 4),
        "pct_refs_not_returned": round(sum(1 for r in ranks_all if r is None) / max(len(ranks_all), 1), 4),
        "pct_questions_any_top5": round(sum(1 for row in rows if row["any_in_top5"]) / max(len(rows), 1), 4),
        "pct_questions_any_top10": round(sum(1 for row in rows if row["any_in_top10"]) / max(len(rows), 1), 4),
        "pct_questions_any_top50": round(sum(1 for row in rows if row["any_in_top50"]) / max(len(rows), 1), 4),
        "pct_questions_any_top500": round(sum(1 for row in rows if row["any_in_top500"]) / max(len(rows), 1), 4),
        "mean_truth_rank_when_returned": (
            round(statistics.mean(returned_ranks), 2) if returned_ranks else None
        ),
        "median_truth_rank_when_returned": (
            round(statistics.median(returned_ranks), 2) if returned_ranks else None
        ),
        "crowd_truth_class_top5_non_expected": dict(crowd_classes.most_common()),
        "crowd_paths_top5_non_expected_top20": dict(crowd_paths.most_common(20)),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "date": "2026-09-11",
            "purpose": "P1 truth-file rank census — observation before action",
            "hypothesis_context": (
                "H0 missing-files falsified earlier; this measures WHERE truth files rank"
            ),
            "engine": "lexical BM25 truth-tier",
        },
        "summary": summary,
        "questions": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        if k.startswith("crowd_paths"):
            continue
        print(f"  {k}: {v}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

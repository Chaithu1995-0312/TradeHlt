#!/usr/bin/env python3
"""Measure file Recall@5 on ORIGINAL vs REMAPPED gold (no index rebuild).

Usage (Windows):
  $env:PYTHONPATH='D:\Tradelatest\src'
  venv\Scripts\python.exe scripts\_tmp_measure_rag_ranking.py
  venv\Scripts\python.exe scripts\_tmp_measure_rag_ranking.py --limit 95
  venv\Scripts\python.exe scripts\_tmp_measure_rag_ranking.py --gold remapped
  venv\Scripts\python.exe scripts\_tmp_measure_rag_ranking.py --compare
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\Tradelatest")
EVAL = ROOT / "scripts" / "evaluation"


def _load_gold(kind: str) -> tuple[Path, dict[str, Any]]:
    mapping = {
        "original": EVAL / "benchmark_100.original.json",
        "remapped": EVAL / "benchmark_100.remapped.json",
        "current": EVAL / "benchmark_100.json",
    }
    # Prefer explicit; fall back
    path = mapping.get(kind, EVAL / kind)
    if kind == "original" and not path.exists():
        path = EVAL / "benchmark_100.json"
    if kind == "remapped" and not path.exists():
        # active pointer
        ptr = EVAL / "benchmark_100.active"
        if ptr.exists():
            path = EVAL / ptr.read_text(encoding="utf-8").strip()
        else:
            path = EVAL / "benchmark_100.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return path, data


def _questions(data: dict[str, Any], limit: int | None) -> list[dict[str, Any]]:
    qs = [q for q in data.get("questions") or [] if not q.get("is_hallucination_test")]
    if limit is not None:
        qs = qs[:limit]
    return qs


def _norm(p: str) -> str:
    return p.replace("\\", "/").strip()


def measure(kind: str, limit: int | None, top_k: int = 5) -> dict[str, Any]:
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from retrieval import RetrievalPipeline
    from retrieval.config import build_default_config

    path, data = _load_gold(kind)
    questions = _questions(data, limit)
    cfg = build_default_config()
    pipe = RetrievalPipeline(cfg)
    t0 = time.time()
    pipe.lexical.ensure_loaded()
    load_s = time.time() - t0
    print(
        f"[{kind}] gold={path.name} N={len(questions)} "
        f"candidate_n={cfg.candidate_n} file_route_boost={getattr(cfg, 'file_route_boost', None)} "
        f"load={load_s:.2f}s backend={pipe.lexical._backend}"
    )

    recalls: list[float] = []
    any_hit = 0
    latencies: list[float] = []
    examples_flip: list[dict[str, Any]] = []  # filled by caller for compare

    details = []
    for q in questions:
        expected = [_norm(x) for x in (q.get("expected_files") or [])]
        t1 = time.time()
        ctx = pipe.retrieve_assembly(q["question"], top_k=top_k)
        latencies.append(time.time() - t1)
        seen: list[str] = []
        seen_set: set[str] = set()
        for h in ctx.chunks:
            fp = _norm(h.filepath)
            if fp not in seen_set:
                seen_set.add(fp)
                seen.append(fp)
        matched = [ef for ef in expected if ef in seen_set]
        # also basename match soft
        if not matched and expected:
            seen_bases = {s.rsplit("/", 1)[-1].lower() for s in seen_set}
            matched = [
                ef
                for ef in expected
                if ef.rsplit("/", 1)[-1].lower() in seen_bases
            ]
        r = (len(matched) / len(expected)) if expected else 0.0
        recalls.append(r)
        if matched:
            any_hit += 1
        details.append(
            {
                "id": q.get("id"),
                "question": q.get("question"),
                "expected": expected,
                "top_files": seen,
                "matched": matched,
                "recall": r,
            }
        )

    mean_r = sum(recalls) / max(len(recalls), 1)
    warm = sorted(latencies)[len(latencies) // 2] if latencies else 0.0
    out = {
        "kind": kind,
        "gold_path": str(path),
        "n": len(questions),
        "mean_file_recall_at_5": mean_r,
        "pct_questions_any_gold_in_top5": any_hit / max(len(questions), 1),
        "median_latency_s": warm,
        "p95_latency_s": sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else 0.0,
        "details": details,
    }
    print(
        f"[{kind}] mean_file_Recall@5={mean_r:.4f}  "
        f"any_hit={any_hit}/{len(questions)}  "
        f"median_s={warm:.3f} p95_s={out['p95_latency_s']:.3f}"
    )
    print(f"[{kind}] baselines: ranking-only=0.0385  pre-ranking=0.0211")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=95)
    ap.add_argument("--gold", choices=["original", "remapped", "current"], default=None)
    ap.add_argument("--compare", action="store_true", help="Measure original and remapped")
    ap.add_argument("--out", type=str, default=str(EVAL / "measure_file_route_report.json"))
    args = ap.parse_args()

    results = []
    if args.compare or args.gold is None:
        for kind in ("original", "remapped"):
            # remapped may not exist yet
            p = EVAL / f"benchmark_100.{kind}.json"
            if kind == "remapped" and not p.exists():
                print("remapped gold missing — run gold_remap.py first")
                continue
            results.append(measure(kind, args.limit))
    else:
        results.append(measure(args.gold, args.limit))

    # Flips: gold file newly in top-5 under remapped vs missing under original,
    # OR same gold but routing helped (present in remapped details matched).
    flips = []
    if len(results) == 2:
        by_id_a = {d["id"]: d for d in results[0]["details"]}
        by_id_b = {d["id"]: d for d in results[1]["details"]}
        for qid, db in by_id_b.items():
            da = by_id_a.get(qid)
            if not da:
                continue
            if da["recall"] == 0 and db["recall"] > 0:
                flips.append(
                    {
                        "id": qid,
                        "question": db["question"],
                        "matched_now": db["matched"],
                        "top_files": db["top_files"][:5],
                        "expected": db["expected"],
                    }
                )
        print("\n=== flips (0 -> >0 Recall) due to routing/remap ===")
        for ex in flips[:5]:
            print(f"  Q{ex['id']}: {ex['question'][:80]}")
            print(f"    matched={ex['matched_now']}")
            print(f"    top={ex['top_files']}")

    report = {
        "results": [
            {k: v for k, v in r.items() if k != "details"} | {"n_details": len(r["details"])}
            for r in results
        ],
        "flips_sample": flips[:10],
        "full": results,
    }
    out = Path(args.out)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

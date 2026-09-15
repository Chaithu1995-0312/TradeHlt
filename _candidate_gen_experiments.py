"""Candidate-generation experiments (observation before action).

Exp 1 — candidate_N sweep (single variable):
  For each N in {100, 500, 2000, 5000}, measure truth-file reach rates.
  H0: raising N does not materially increase reach (saturation).

Exp 2 — symbol/ID routing (single variable, N fixed at 500):
  A = lexical BM25 only (baseline)
  B = lexical + exact filepath/symbol/ID boost for governed ids AND
      basename/stem matches against query tokens
  Held constant: index, N=500, gold refs, weights except explicit routing boosts.

Also reports md-json twin awareness:
  if expected foo.md and foo.json (or sibling) is ranked, count as twin_hit.
"""
from __future__ import annotations

import json
import re
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
sys.path.insert(0, "src")
sys.path.insert(0, str(ROOT / "src"))

from retrieval import RetrievalPipeline
from retrieval.config import build_default_config
from retrieval.truth_tier import extract_ids

GOLD = ROOT / "scripts/evaluation/benchmark_100.json"
OUT = ROOT / "results/evaluation/candidate_gen_experiments_2026-09-11.json"

NS = [100, 500, 2000, 5000]
ID_RE = re.compile(
    r"\b(?:F-\d{3}|FM-\d{3}|SEM-\d{3}|L-003[A-Z]?|MC-[A-Z0-9-]+|Y_(?:scanner|oracle|joint)|Omega_\w+)\b"
)


def twin_paths(fp: str) -> set[str]:
    """md-json / md-yaml siblings sharing the same stem path."""
    p = Path(fp)
    stem = p.with_suffix("")
    out = {fp}
    for suf in (".md", ".json", ".yaml", ".yml"):
        out.add(str(stem) + suf)
    # also L003 style: FOO.md - foo-2026-09-07.json hard; keep simple stem twins only
    return out


def filepath_ranks(hits) -> dict[str, int]:
    ranks, seen = {}, set()
    for i, h in enumerate(hits, 1):
        if h.filepath not in seen:
            seen.add(h.filepath)
            ranks[h.filepath] = i
    return ranks


def best_rank_for_expected(expected: list[str], ranks: dict[str, int], twin: bool) -> tuple[int | None, str | None, bool]:
    """Return (best_rank, matched_path, used_twin)."""
    best, match, used_twin = None, None, False
    for ef in expected:
        cands = twin_paths(ef) if twin else {ef}
        for c in cands:
            r = ranks.get(c)
            if r is None:
                continue
            if best is None or r < best:
                best, match = r, c
                used_twin = c != ef
    return best, match, used_twin


def eval_reach(pipe, questions, N: int, twin: bool, label: str, search_fn) -> dict:
    n_refs = 0
    reached = 0
    twin_rescues = 0
    bests = []
    q_any = 0
    per_q = []
    t0 = time.time()
    for q in questions:
        expected = list(q.get("expected_files") or [])
        hits = search_fn(q["question"], N)
        ranks = filepath_ranks(hits)
        any_hit = False
        for ef in expected:
            n_refs += 1
            # exact
            r = ranks.get(ef)
            used_twin = False
            matched = ef if r is not None else None
            if r is None and twin:
                br, matched, used_twin = best_rank_for_expected([ef], ranks, twin=True)
                r = br
                if used_twin and r is not None:
                    twin_rescues += 1
            if r is not None:
                reached += 1
                bests.append(r)
                any_hit = True
        if any_hit:
            q_any += 1
        per_q.append({"id": q["id"], "reached": any_hit})
    elapsed = time.time() - t0
    return {
        "label": label,
        "N": N,
        "twin_aware": twin,
        "n_questions": len(questions),
        "n_refs": n_refs,
        "pct_refs_reached": round(reached / max(n_refs, 1), 4),
        "pct_questions_any_reach": round(q_any / max(len(questions), 1), 4),
        "twin_rescues_refs": twin_rescues,
        "median_rank_when_reached": round(statistics.median(bests), 2) if bests else None,
        "mean_rank_when_reached": round(statistics.mean(bests), 2) if bests else None,
        "elapsed_s": round(elapsed, 2),
    }


def symbol_id_search(pipe, query: str, N: int):
    """Baseline lexical, then boost chunks whose ids/symbols/filepath stem hit query tokens."""
    # Over-fetch then re-sort with routing boost
    hits = pipe.lexical.search(query, top_k=max(N * 3, N), include_historical=True)
    q_ids = set(extract_ids(query)) | set(ID_RE.findall(query))
    q_lower = query.lower()
    tokens = set(re.findall(r"[a-z0-9_]{3,}", q_lower))

    rescored = []
    for h in hits:
        score = float(h.score)
        # ID boost
        h_ids = {x.strip() for x in (h.ids or "").split(",") if x.strip()}
        if q_ids & h_ids:
            score += 8.0
        # filepath stem / basename token overlap
        fp = h.filepath.replace("\\", "/").lower()
        base = Path(fp).stem.lower()
        parts = set(re.findall(r"[a-z0-9_]{3,}", base.replace("-", "_")))
        overlap = tokens & parts
        if overlap:
            score += 3.0 * min(len(overlap), 3)
        # heading token overlap
        heading = (h.heading or "").lower()
        if heading and any(t in heading for t in tokens if len(t) > 4):
            score += 1.5
        rescored.append((score, h))
    rescored.sort(key=lambda x: -x[0])
    # reassign for consumer that expects hit objects in order
    out = []
    for score, h in rescored[:N]:
        # shallow copy score into metadata path — search consumer only uses filepath order
        out.append(h)
    return out


def main() -> None:
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    questions = [q for q in gold["questions"] if not q.get("is_hallucination_test")]

    pipe = RetrievalPipeline(build_default_config())
    t0 = time.time()
    pipe.lexical.ensure_loaded()
    print(f"loaded {time.time()-t0:.1f}s chunks={len(pipe.lexical._chunks)}")

    def lexical_search(query, N):
        return pipe.lexical.search(query, top_k=N, include_historical=True)

    print("\n=== Exp1: candidate_N sweep (exact paths) ===")
    sweep_exact = []
    for N in NS:
        r = eval_reach(pipe, questions, N, twin=False, label=f"lexical_N{N}_exact", search_fn=lexical_search)
        sweep_exact.append(r)
        print(r)

    print("\n=== Exp1b: candidate_N sweep (md-json twin-aware) ===")
    sweep_twin = []
    for N in NS:
        r = eval_reach(pipe, questions, N, twin=True, label=f"lexical_N{N}_twin", search_fn=lexical_search)
        sweep_twin.append(r)
        print(r)

    print("\n=== Exp2: symbol/ID routing vs lexical @ N=500 ===")
    a = eval_reach(pipe, questions, 500, twin=False, label="A_lexical_N500", search_fn=lexical_search)
    print("A", a)

    def routed(query, N):
        return symbol_id_search(pipe, query, N)

    b = eval_reach(pipe, questions, 500, twin=False, label="B_symbol_id_route_N500", search_fn=routed)
    print("B", b)

    a_t = eval_reach(pipe, questions, 500, twin=True, label="A_lexical_N500_twin", search_fn=lexical_search)
    b_t = eval_reach(pipe, questions, 500, twin=True, label="B_symbol_id_route_N500_twin", search_fn=routed)
    print("A_twin", a_t)
    print("B_twin", b_t)

    delta = {
        "exact": {
            "pct_refs_reached": round(b["pct_refs_reached"] - a["pct_refs_reached"], 4),
            "pct_questions_any_reach": round(b["pct_questions_any_reach"] - a["pct_questions_any_reach"], 4),
            "median_rank_delta": (
                None if a["median_rank_when_reached"] is None or b["median_rank_when_reached"] is None
                else round(b["median_rank_when_reached"] - a["median_rank_when_reached"], 2)
            ),
        },
        "twin": {
            "pct_refs_reached": round(b_t["pct_refs_reached"] - a_t["pct_refs_reached"], 4),
            "pct_questions_any_reach": round(b_t["pct_questions_any_reach"] - a_t["pct_questions_any_reach"], 4),
        },
    }

    # saturation signal from sweep
    reach_by_n = {r["N"]: r["pct_refs_reached"] for r in sweep_exact}
    twin_by_n = {r["N"]: r["pct_refs_reached"] for r in sweep_twin}

    payload = {
        "meta": {
            "date": "2026-09-11",
            "purpose": "Candidate-generation observation: N-sweep + symbol/ID routing",
            "held_constant_exp1": ["index", "BM25 weights", "gold refs", "no dense"],
            "held_constant_exp2": ["index", "N=500", "gold refs", "no dense"],
            "H0_N_sweep": "Raising candidate_N does not materially increase truth-file reach",
            "H0_routing": "Symbol/ID/filepath-stem routing does not increase truth-file reach vs lexical @ N=500",
        },
        "exp1_n_sweep_exact": sweep_exact,
        "exp1_n_sweep_twin": sweep_twin,
        "exp1_reach_by_n_exact": reach_by_n,
        "exp1_reach_by_n_twin": twin_by_n,
        "exp2_routing": {"A": a, "B": b, "A_twin": a_t, "B_twin": b_t, "delta_B_minus_A": delta},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\nDELTA routing", delta)
    print("wrote", OUT)


if __name__ == "__main__":
    main()

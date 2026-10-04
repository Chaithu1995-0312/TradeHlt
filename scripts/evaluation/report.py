"""
report.py — Generate a human-readable markdown report from a benchmark run JSON.

Usage:
    python scripts/evaluation/report.py results/evaluation/latest_run.json
    python scripts/evaluation/report.py results/evaluation/latest_run.json --output results/evaluation/baseline_report.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def load_run(path: Path) -> dict[str, Any]:
    """Load a benchmark run result."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_markdown(run: dict[str, Any]) -> str:
    """Generate a markdown report from a benchmark run."""
    meta = run["meta"]
    aggregate = run["aggregate"]
    criteria = run["criteria"]
    results = run["results"]
    categories = meta.get("benchmark_categories", None)
    if categories is None and results:
        # Infer categories from results
        cat_set = sorted(set(r["category"] for r in results))
        categories = {c: f"({sum(1 for r in results if r['category']==c)} questions)" for c in cat_set}

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────
    lines.append(f"# RAG Benchmark Report")
    lines.append("")
    lines.append(f"**Benchmark:** {meta.get('benchmark_name', 'Unknown')}")
    lines.append(f"**Timestamp:** {meta.get('evaluation_timestamp', 'Unknown')}")
    lines.append(f"**Top-K:** {meta.get('top_k', 10)}")
    lines.append(f"**Total evaluation time:** {meta.get('total_evaluation_time_s', 0):.1f}s")
    lines.append(f"**Rebuild index:** {meta.get('rebuild_index', False)}")
    lines.append("")

    # ── Overall Result ────────────────────────────────────────────────────
    lines.append("## Overall Result")
    lines.append("")
    overall = "✅ PASS" if aggregate.get("overall_pass") else "❌ FAIL"
    lines.append(f"**{overall}**")
    lines.append("")
    lines.append(f"| Metric | Value | Target | Status |")
    lines.append(f"|--------|-------|--------|--------|")

    for criterion, data in aggregate.get("criteria_results", {}).items():
        status = "✅" if data["passed"] else "❌"
        value_str = str(data["value"])
        target_str = str(data["target"])
        lines.append(f"| {criterion} | {value_str} | {target_str} | {status} |")

    lines.append("")
    lines.append(f"**Pass rate:** {aggregate['pass_rate']}% ({aggregate['passed']}/{aggregate['total_questions']} questions)")
    lines.append(f"**Failed:** {aggregate['failed']} questions")
    lines.append("")

    # ── Summary Metrics ────────────────────────────────────────────────────
    lines.append("## Summary Metrics")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Avg Recall@5 | {aggregate['avg_recall_at_5']:.4f} |")
    lines.append(f"| Avg Recall@10 | {aggregate['avg_recall_at_10']:.4f} |")
    lines.append(f"| Avg MRR | {aggregate['avg_mrr']:.4f} |")
    lines.append(f"| Avg Citation Accuracy | {aggregate['avg_citation_accuracy']:.4f} |")
    lines.append(f"| Avg Duplicate Ratio | {aggregate['avg_duplicate_ratio']:.4f} |")
    lines.append(f"| Avg Latency | {aggregate['avg_latency_ms']:.1f}ms |")
    lines.append(f"| Hallucination Correct | {aggregate['hallucination_handled_correctly']}/{aggregate['hallucination_questions']} |")
    lines.append(f"| Multi-hop Avg Recall@5 | {aggregate['multi_hop_avg_recall_at_5']:.4f} |")
    lines.append(f"| Multi-hop Avg Recall@10 | {aggregate['multi_hop_avg_recall_at_10']:.4f} |")
    lines.append("")

    # ── Per-Category Breakdown ────────────────────────────────────────────
    lines.append("## Per-Category Breakdown")
    lines.append("")
    lines.append(f"| Category | Pass Rate | Recall@5 | Recall@10 | Questions |")
    lines.append(f"|----------|-----------|----------|-----------|-----------|")
    for cat, data in sorted(aggregate.get("per_category", {}).items()):
        lines.append(f"| {cat} | {data['pass_rate']:.1f}% | {data['avg_recall_at_5']:.3f} | {data['avg_recall_at_10']:.3f} | {data['total']} |")
    lines.append("")

    # ── Failed Questions ──────────────────────────────────────────────────
    failed_qs = [r for r in results if not r["passed"]]
    if failed_qs:
        lines.append("## Failed Questions")
        lines.append("")
        lines.append(f"**{len(failed_qs)} questions failed:**")
        lines.append("")
        lines.append("| ID | Category | Question | R@5 | R@10 | MRR | Citation | Latency |")
        lines.append("|----|----------|----------|-----|------|-----|----------|---------|")
        for r in failed_qs:
            q = r["question"][:80]
            lat = f"{r['latency_ms']:.0f}ms"
            lines.append(f"| Q{r['question_id']} | {r['category']} | {q} | {r['recall_at_5']:.2f} | {r['recall_at_10']:.2f} | {r['mrr']:.2f} | {r['citation_accuracy']} | {lat} |")
        lines.append("")

        # Detail for each failed question
        lines.append("### Failure Details")
        lines.append("")
        for r in failed_qs:
            if r["is_hallucination_test"]:
                continue  # hallucination failures are handled separately
            lines.append(f"#### Q{r['question_id']}: {r['category']}")
            lines.append("")
            lines.append(f"**Question:** {r['question']}")
            lines.append("")
            lines.append(f"**Expected files:** `{'`, `'.join(r['expected_files']) if r['expected_files'] else '*none*'}`")
            lines.append("")
            lines.append("**Retrieved files (top 10):**")
            for i, fp in enumerate(r.get("retrieved_filepaths", [])[:10], 1):
                score = r["retrieved_scores"][i-1] if i-1 < len(r["retrieved_scores"]) else 0.0
                marker = " ✅" if fp in r["expected_files"] else ""
                lines.append(f"  {i}. `{fp}` (score={score:.3f}){marker}")
            lines.append("")
            lines.append(f"**Recall@5:** {r['recall_at_5']}  **Recall@10:** {r['recall_at_10']}  **MRR:** {r['mrr']}  **Citation:** {r['citation_accuracy']}")
            lines.append("")

    # ── Multi-hop Questions ───────────────────────────────────────────────
    multi_hop_qs = [r for r in results if r.get("multi_hop")]
    if multi_hop_qs:
        lines.append("## Multi-hop Reasoning")
        lines.append("")
        lines.append(f"**{len(multi_hop_qs)} multi-hop questions:**")
        lines.append("")
        lines.append("| ID | Question | R@5 | R@10 | MRR | Expected Files |")
        lines.append("|----|----------|-----|------|-----|---------------|")
        for r in multi_hop_qs:
            q = r["question"][:80]
            ef_count = len(r["expected_files"])
            lines.append(f"| Q{r['question_id']} | {q} | {r['recall_at_5']:.2f} | {r['recall_at_10']:.2f} | {r['mrr']:.2f} | {ef_count} |")
        lines.append("")

    # ── Hallucination Questions ───────────────────────────────────────────
    hall_qs = [r for r in results if r["is_hallucination_test"]]
    if hall_qs:
        lines.append("## Hallucination Resistance")
        lines.append("")
        correct = sum(1 for r in hall_qs if r.get("hallucination_handled_correctly"))
        lines.append(f"**{correct}/{len(hall_qs)} handled correctly**")
        lines.append("")
        lines.append("| ID | Question | Handled Correctly | Retrieved Files |")
        lines.append("|----|----------|-------------------|-----------------|")
        for r in hall_qs:
            q = r["question"][:80]
            handled = "✅" if r.get("hallucination_handled_correctly") else "❌"
            retrieved = ", ".join(r.get("retrieved_filepaths", [])[:3]) or "(none)"
            lines.append(f"| Q{r['question_id']} | {q} | {handled} | {retrieved} |")
        lines.append("")

    # ── Top Retrieval by Category ─────────────────────────────────────────
    lines.append("## Top Retrieval Quality by Category")
    lines.append("")
    for cat, data in sorted(aggregate.get("per_category", {}).items()):
        best_q = None
        best_r5 = 0.0
        worst_q = None
        worst_r5 = 1.0
        for r in results:
            if r["category"] == cat and not r["is_hallucination_test"]:
                if r["recall_at_5"] > best_r5:
                    best_r5 = r["recall_at_5"]
                    best_q = r
                if r["recall_at_5"] < worst_r5:
                    worst_r5 = r["recall_at_5"]
                    worst_q = r
        lines.append(f"### {cat}")
        lines.append(f"- **Pass rate:** {data['pass_rate']:.1f}%")
        lines.append(f"- **Avg Recall@5:** {data['avg_recall_at_5']:.3f}")
        lines.append(f"- **Best:** Q{best_q['question_id']} ({best_q['question'][:60]}) R@5={best_r5:.2f}" if best_q else "")
        lines.append(f"- **Worst:** Q{worst_q['question_id']} ({worst_q['question'][:60]}) R@5={worst_r5:.2f}" if worst_q else "")
        lines.append("")

    # ── Recommendations ───────────────────────────────────────────────────
    lines.append("## Recommendations")
    lines.append("")

    # Check for specific patterns that suggest improvements
    if aggregate.get("avg_citation_accuracy", 0) < 0.9:
        lines.append("- **Low citation accuracy.** Top-1 result rarely matches expected file. Consider: reranking, tightening domain filtering.")
    if aggregate.get("multi_hop_avg_recall_at_5", 0) < 0.5:
        lines.append(f"- **Multi-hop recall is weak ({aggregate['multi_hop_avg_recall_at_5']:.1%}).** The retriever struggles with questions requiring evidence from multiple documents. Consider: query decomposition, GraphRAG, or iterative retrieval.")
    if aggregate.get("hallucination_handled_correctly", 0) < aggregate.get("hallucination_questions", 0):
        lines.append("- **Hallucination handling needs improvement.** The retriever returns plausible-sounding but irrelevant results for non-existent concepts. Consider: confidence thresholding, refusal classifier.")
    if aggregate.get("avg_duplicate_ratio", 0) > 0.05:
        lines.append(f"- **High duplicate retrieval ({aggregate['avg_duplicate_ratio']:.1%}).** Many results come from the same file. Consider: MMR (Maximal Marginal Relevance) diversification.")
    if aggregate.get("avg_latency_ms", 0) > 500:
        lines.append(f"- **High latency ({aggregate['avg_latency_ms']:.0f}ms).** Consider: embedding caching, faster embedding model, approximate nearest neighbor index tuning.")

    if aggregate.get("overall_pass", False):
        lines.append("- **All criteria pass.** The RAG system meets the baseline benchmark targets. Future improvements should be evaluated against this baseline to measure regression.")
    else:
        lines.append("- **Baseline not yet passing.** Address the failed criteria above before making any other improvements. Every change must be measured against this baseline.")

    lines.append("")

    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate RAG benchmark report")
    parser.add_argument("input", type=str, help="Path to benchmark run JSON")
    parser.add_argument("--output", type=str, default=None, help="Output markdown path")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(1)

    run = load_run(input_path)
    report = generate_markdown(run)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report written to {output_path}")
    else:
        print(report)


if __name__ == "__main__":
    main()
# Analysis-only task — no code/repo changes

## Context
User pasted a broken Python snippet (tries `json.load()` on a file named
`semantic_layer_validation_7day_bars.csv`, which fails — CSV isn't JSON) plus a
hand-typed fallback reconstruction of "contradiction" percentages, followed by a
draft markdown report titled "Unexplained Semantic Mismatches in Market Behavior."
The ask: given the repo has three related files (csv / md / json) under
`results/feature_trace/`, determine which one actually suits the requirement, and
evaluate the correctness/completeness of the pasted script + report against it.

User confirmed: deliver the analysis only, no files to be created or edited.

## Findings (to report to user, no implementation needed)

1. **Three files, one lineage** — all in `results/feature_trace/`, produced by
   `scripts/analysis/semantic_layer_validation.py`:
   - `semantic_layer_validation_7day_stats.json` — the **source of truth**. Full
     machine-readable stats: geometry_verification, feature_statistics,
     non_canonical_evidence_statistics, and `contradiction_scan` (7 predicates
     with occurrences/pct/examples).
   - `semantic_layer_validation_7day.md` — human-readable narrative report,
     explicitly derived from the json ("Every statistic below is drawn from
     results/feature_trace/semantic_layer_validation_7day_stats.json"). Already
     contains a complete Part 3 contradiction table (all 7 predicates) plus
     co-occurrence stats, missing-semantics, redundancy analysis, and a final
     assessment.
   - `semantic_layer_validation_7day_bars.csv` — raw per-bar feature dump (635
     lines incl. header, one row per of the 634 finalized bars) — the "excel"
     file. This is tabular per-row data, not aggregated stats; it is NOT valid
     JSON (hence the pasted script's `JSONDecodeError`).

2. **Which file suits the requirement** — the pasted script wants
   `contradiction_scan["semantic_mismatch_predicates"]`, which only exists in the
   **`_stats.json`** file. The script's bug is simply pointing at the `.csv`
   filename while calling `json.load()`. Correct fix (if ever needed): open
   `semantic_layer_validation_7day_stats.json` instead.

3. **The pasted "manual fallback" numbers are correct but INCOMPLETE** — the 4
   hand-typed predicates (10/1.58%, 1/0.16%, 5/0.79%, 18/2.84%) match the real
   json exactly. But the json's `contradiction_scan.semantic_mismatch_predicates`
   has **7** predicates, not 4. Missing from the pasted report:
   - `trend_bias==Bearish while break_of_structure==BullishBreak` — **25
     occurrences, 3.94%** (the single largest predicate in the whole scan —
     bigger than the one the draft report emphasizes).
   - Doji (`body_ratio`<0.1) carrying `break_of_structure`≠0 — 14, 2.21%.
   - `liquidity_sweep`≠0 AND `break_of_structure`≠0 same bar — 2, 0.32%.
   - The repo's own `.md` explicitly combines predicates 4+5 into "43 bars
     (6.78%) — the most frequent recurring inconsistency in the study," which
     the draft report never states.

4. **Verdict to give the user**: use `semantic_layer_validation_7day_stats.json`
   as the data source (not the `.csv`, which isn't JSON, and not a re-typed
   subset). The repo's existing `semantic_layer_validation_7day.md` is already a
   complete, correct, cited analysis of that json — the pasted draft report is a
   partial re-derivation that undercounts contradictions and misses the largest
   one. Point the user at the existing `.md` rather than have them extend the
   partial draft.

## Verification
N/A — no code changes. Answer is delivered as plain-text analysis in the next
turn, citing `results/feature_trace/semantic_layer_validation_7day.md` and
`_stats.json` line numbers already read this session.

# Plan — epoch-scope F-069, restore `agree_scope`, then the feature map

## Context

Goal: a feature map at CRT states and Parent HTF for specific reconstructions, with
threshold ranges of features.

Querying what already exists answered most of it and surfaced two defects.

**The map already exists.** `results/research/bar_matrix/XAUUSD_M15/bar_matrix.parquet`
— 47,197 rows x 124 columns — already carries the canonical feature vector, 22 `state__*`
banding columns (the threshold ranges, point-in-time against a trailing window sized by
`feature_pipeline.volatility_percentile_window`), `crt_state_resolved`, and the parent/HTF
dimension (`parent_track_state`, `parent_bias`, `htf_state`, `objective_status`,
`htf_window_id`). Nothing needs building for the map itself.

**The join to the decision atlas is verified exact.** `bar_matrix._pos` and
`decision_atlas_full/envelope_bar.bar_index` are the *identical set* (78 -> 47274, 47,197
values; 78 is the warmup head), all 47,197 timestamps match, and `resolver_state ==
crt_state_resolved` at **1.000** — confirmed by a third column, not assumed.

**The 2,300-bar window cannot be joined.** `results/decision_atlas/`
(`run_20260906_010549`) spans 2026-07-06 -> 2026-08-07; `bar_matrix` spans 2024-05-22 ->
2026-05-21. Zero overlap. Scope is therefore `decision_atlas_full`
(`run_20260906_013609` — registered, carries `corpus_sha256`).

### Defect 1 — F-069 is epoch-scoped and does not say so

Engine<->resolver agreement reads **32,418/47,197 = 0.6869** on the atlas; F-069 records
**41,607/47,197 = 0.8816**. Same definition, same denominator, but **both constructions
changed**:

| state | F-069 engine | atlas engine | F-069 resolver | atlas resolver |
|---|---:|---:|---:|---:|
| RANGE | 35,130 | 22,127 | 37,343 | 21,745 |
| SWEEP | 7,004 | 15,587 | 7,571 | 15,186 |
| DISPLACEMENT | 373 | 779 | 466 | 3,127 |
| EXPANSION | 4,625 | 8,668 | 1,803 | 7,092 |
| SHADOW_PENDING | 43 | 6 | 14 | 47 |

Neither number is wrong. The agreement rate is a consequence. Atlas resolver RANGE 21,745
is exactly F-086's recorded figure while F-069's engine RANGE 35,130 sits beside F-086's
35,159 — the two findings straddle a resolver change.

Candidate drivers, **not isolated**: F-074 (directional displacement, 2026-08-13),
F-075 (12-state parent CRT), F-068 (shadow TTL — recorded 43->51, atlas says 6, a third
epoch).

### Defect 2 — `agree_scope` is dropped at the join

`src/runtime/crt_construction_trace.py:51` emits `agree_scope` explicitly *"so a reader
cannot mistake that feature-conditioned diagnostic for a verdict on engine truth."*
`scripts/analysis/build_decision_atlas.py` contains `agree_scope` **zero times**, so
`envelope_bar.parquet` has 20 columns and none of them is the guard. Same silent-gap class
as F-079 / F-083 / F-085.

## Scope

Two small corrections, then the map. No new atlas, no new emitter, no new record type, no
new run.

## Step 1 — epoch-scope F-069 (Documentation Drift Protocol)

Classify: `AMBIGUOUS` -> resolved to **scope correction, not reversal** (§6.2 rule 4 —
preserve, never delete). Precedent: F-058 epoch-scoped the gate-OFF corpus; F-070 recorded
non-reproduction of F-037 without reversing it.

- `docs/current-findings.md` — append to F-069's row: the 2026-09-06 re-measurement
  (`run_20260906_013609`), the two distribution tables, `0.6869`, and the statement that
  F-069's figures are valid for their epoch and do not reproduce on the current
  construction. Cite `results/decision_atlas_full/envelope_bar.parquet`.
- `CLAUDE.md` Repository Truths Index — F-069 conclusion line gains the epoch qualifier.
  Keep the row; `tests/test_current_findings.py` enforces both sides.
- `reports/crt_semantic_parity_report.md` — dated note under §1 pointing at the
  re-measurement. Do not edit the recorded numbers.

Do **not** claim which change caused it. The drivers stay hypotheses until ablated.

## Step 2 — restore `agree_scope` through the join

`scripts/analysis/build_decision_atlas.py` — carry `agree_scope` through to the
`envelope_bar` table beside `agree`, the same pass-through shape as the existing
`"agree": r.get("agree")` at `:304` / `:346`. One column, no recompute.

Rebuild `results/decision_atlas_full/` and confirm the 20 -> 21 column change and that
`agree` counts are unchanged (32,418 True / 14,779 False).

## Step 3 — the feature map

Join `bar_matrix.parquet` to `decision_atlas_full` on `_pos == bar_index`, verified above.
Read-only query, no new artifact unless the output is worth keeping.

Cross-tab the 22 `state__*` bands x CRT state x parent-HTF dimension. Two grain rules that
are already paid for and must be carried in the output, not remembered:

- **Report at DECISION grain, not occupancy.** `transition_decision.parquet` (5,269 rows)
  is the unit; a per-bar profile is a map of dwell. 673 EXPANSION bars were 4 entry
  decisions.
- **Print n and a power label per cell**; `n < 30` is INSUFFICIENT. Exclude
  `decision_class = CLOCK` and `is_self_transition`, which `query_decision_atlas.py`
  already does by default.

Use the registered banding vocabulary (`state__*`). Do not mint terciles — that is what
made this session's withdrawn `atr_tercile` claim inadmissible.

## Files

| File | Change |
|---|---|
| `docs/current-findings.md` | F-069 epoch scope + re-measurement evidence |
| `CLAUDE.md` | F-069 Truths Index row gains epoch qualifier |
| `reports/crt_semantic_parity_report.md` | dated pointer note under §1 |
| `scripts/analysis/build_decision_atlas.py` | carry `agree_scope` into `envelope_bar` |
| `docs/governance/build_manifests/CH-f069-epoch-scope.impact.json` | new |
| `assistant_project.md` | SESSION LOG (commit-msg hook needs a same-day entry) |

## Verification

```bash
venv/Scripts/python.exe -m pytest tests/test_current_findings.py tests/test_doc_citations.py -q
venv/Scripts/python.exe -m pytest tests/test_crt_construction_trace.py tests/test_resolver_metadata.py -q
venv/Scripts/python.exe scripts/governance/construction_protocol.py validate-impact docs/governance/build_manifests/CH-f069-epoch-scope.impact.json
```

Capture the GREEN_FLOOR baseline **before** editing — it stood at 12 failed / 554 passed /
1 skipped earlier this session, and a pre-existing red must not read as a regression.

## Out of scope

No finding minted for the feature map. No `F-*`, `MC-*`, `SEM-*`, `mx_id`. No authority,
no `economic_claims_allowed` flip. No ablation of F-074/F-075/F-068 — the drivers stay
hypotheses. No registry tracking (user: not yet). No AN/TR schema trim (deferred).

## Risks

- `docs/current-findings.md` and `CLAUDE.md` are both test-enforced and mutually pinned —
  edit them in the same turn or `tests/test_current_findings.py` goes red.
- Both files are already red at baseline for unrelated reasons; compare against the
  captured baseline, not against green.
- ~15 concurrent `claude.exe` sessions write to this repo. Stage explicit paths, never
  `git add -A`.
- Rebuilding `results/decision_atlas_full/` overwrites artifacts in place — the same
  `RECOMPUTE != RECOVER` gap that made `TR-SHADOWMEM-01`'s census sha `UNRECOVERABLE`.
  Hash the existing tables first.

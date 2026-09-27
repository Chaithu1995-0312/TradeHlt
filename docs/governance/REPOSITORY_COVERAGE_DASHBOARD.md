# Repository Semantic Coverage Dashboard

> **GENERATED** `2026-09-18T12:59:14Z` by `scripts/governance/coverage_dashboard.py`  
> Universe: `code` · Objects on disk: **1118**  
> Authority: **advisory** — documentation / Semantic OS hygiene only (§6.5).

## Overall answer

**Is the entire codebase covered?** → `NOT_YET`

NO — incomplete coverage

| Layer | Assessment |
|---|---|
| Documentation (Book + Encyclopedia) | **STRONG** |
| Semantic OS (Concept/Boundary/Journey) | **SKELETON** |

### What this dashboard distinguishes

| You can answer today | You cannot yet answer honestly |
|---|---|
| Is every package indexed in the Encyclopedia? | Is every executable behavior covered? |
| Is every chapter written? | Does every object have Concept + Boundary + Journey + Contract + Authority + Evidence? |
| Physical file documentation | End-to-end semantic coverage |

## Dimension scores

| Dimension | Metric | n | N | % | Status |
|---|---|---:|---:|---:|---|
| **physical_coverage** | Objects with encyclopedia enrichment / Objects on disk | 785 | 1118 | 70.2% | RED |
| **book_coverage** | Objects with encyclopedia phase OR book_status enrichment | 785 | 1118 | 70.2% | RED |
| **semantic_coverage** | Objects mapped to ≥1 Concept (CN-*) | 95 | 1118 | 8.5% | RED |
| **boundary_coverage** | Objects with owning Boundary (BD-*) | 95 | 1118 | 8.5% | RED |
| **journey_coverage** | Objects participating in ≥1 Journey step | 41 | 1118 | 3.7% | RED |
| **behavior_coverage** | ACTIVE journey steps with concept ∧ boundary resolved | 7 | 7 | 100.0% | GREEN |
| **contract_coverage** | Objects with config key / script registry / contract-path hint | 684 | 1118 | 61.2% | GREEN |
| **authority_coverage** | Objects with boundary/regime/relevance authority posture | 634 | 1118 | 56.7% | RED |
| **evidence_coverage** | Objects linked to findings/framework/tests/doc citations | 694 | 1118 | 62.1% | GREEN |
| **dependency_coverage** | Objects with ≥1 AST import edge (imports or imported_by) | 953 | 1118 | 85.2% | GREEN |
| **attribution_coverage** | src/ modules with owner_surface ≠ UNATTRIBUTED | 0 | 629 | 0.0% | RED |

### Dimension notes

- **physical_coverage** (RED): Encyclopedia is enrichment only; disk universe is denominator (848 code files today).
- **book_coverage** (RED): Canonical Book + Encyclopedia documentation layer — strong but ≠ semantic coverage.
- **semantic_coverage** (RED): PR-4/PR-5: CN-001..CN-015 + 10 BDs with expanded globs (~93 objects with concept). YELLOW at ~11%. Further CN (~50 target) and BD waves raise this; object join is member-driven, not concept-count-driven.
- **boundary_coverage** (RED): PR-5: 10 boundaries (BD-001..BD-010) with expanded globs (~94 claimed files). Spine floor still 11/11. Further seams (~30–40 target) remain for later waves.
- **journey_coverage** (RED): JN-001 full 7-step candle journey (PR-3/PR-5 BD rewiring). Object participation follows step member sets; JN-002..005 not yet authored.
- **behavior_coverage** (GREEN): Behavior coverage = can every declared journey step be explained by a concept and boundary? Object participation is journey_coverage on OBJs. GREEN also requires ≥7 declared steps (full candle journey depth); skeleton with 7 steps stays YELLOW even if fully resolved.
- **contract_coverage** (GREEN): Heuristic contract surface — not formal MC-* seals (still OPEN).
- **authority_coverage** (RED): owner_surface remains 100% UNATTRIBUTED; authority uses boundary+regime+encyclopedia relevance.
- **evidence_coverage** (GREEN): tests_importing is AST-proven; test_text_references are TEXT_REFERENCE only.
- **dependency_coverage** (GREEN): AST census covers src+scripts; graph.dot is corroboration only and src-scoped/stale.
- **attribution_coverage** (RED): Currently ~0% — attribution overlays not authored; use owner_boundary instead.

## Base Semantic OS coverage_report (raw)

- total_objects: 1118
- by_kind: `{"module": 629, "root_script": 30, "script": 459}`
- encyclopedia missing: 333
- module_attribution unattributed_owner_surface: 629
- graph_dot absent/stale: 3
- boundary_claimed: 95

## Blocking gaps (RED)

- `physical_coverage` — 70.2% (Objects with encyclopedia enrichment / Objects on disk)
- `semantic_coverage` — 8.5% (Objects mapped to ≥1 Concept (CN-*))
- `boundary_coverage` — 8.5% (Objects with owning Boundary (BD-*))
- `journey_coverage` — 3.7% (Objects participating in ≥1 Journey step)
- `authority_coverage` — 56.7% (Objects with boundary/regime/relevance authority posture)
- `attribution_coverage` — 0.0% (src/ modules with owner_surface ≠ UNATTRIBUTED)
- `book_coverage` — 70.2% (Objects with encyclopedia phase OR book_status enrichment)

## Next actions (Semantic OS close-the-gap)

1. PR-6: module_attribution overlays (DECISION_SPINE + FEATURE) so owner_surface leaves UNATTRIBUTED
1. Continue concepts toward ~50 (MeasurementContract, AuthorityLadder, sidecars)
1. Author JN-002 research / JN-003 governance / JN-004 config / JN-005 agent journeys
1. PR-7: semantic_impact.py + query "what breaks"
1. PR-8: behavior coverage GREEN_FLOOR hooks
1. Optional: further BD wave (~20–40 seams) without shrinking spine floor

## Related sources

| Source | Role |
|---|---|
| `src/governance/semantic_objects.py` | Disk universe + Object join + base `coverage_report()` |
| `docs/governance/semantic_os/{concepts,boundaries,journeys}.yaml` | Hand-authored semantic skeleton |
| `docs/book/encyclopedia/` | Documentation encyclopedia E0–E6 + E1b |
| `docs/book/encyclopedia/encyclopedia_rows.jsonl` | Enrichment twin (not denominator) |
| `scripts/governance/seed_semantic_os.py` | Compile YAML → data/semantic_os |
| `graph.dot` | Stale src-only corroboration — do not use as denominator |

---

_Regenerate: `python scripts/governance/coverage_dashboard.py`_

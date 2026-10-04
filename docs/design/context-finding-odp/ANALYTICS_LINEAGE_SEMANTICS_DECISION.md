# Analytics Lineage Semantics Decision (L-001 doctrines + evidence class + attribution eligibility)

**Status:** design-only, **provisional** — doctrine froze 2026-09-07. Definitional decisions only; NO registry row edits, NO column/schema changes, NO `src/` changes from this doc.
**Date:** 2026-09-07
**Companions:**
- `docs/governance/ANALYTICS_SCHEMA_REGISTRY.md` (symbol table; 268 rows)
- `docs/governance/ANALYTICS_LINEAGE_REGISTRY.md` (descriptive origin)
- `docs/governance/ANALYTICS_LINEAGE_ANOMALY_REVIEW.md` (12 UNKNOWN pocket)
- `docs/design/context-finding-odp/ANALYTICS_VOCABULARY_ALIGNMENT.md` (SAFE_ALIAS §5)
- `docs/design/context-finding-odp/DESIGN_DEFECTS_D1_D2_D3_L4.md` (identity/population defect classes)

**Not granted by this doc:** no new Ontology/ODP/Policy emitters; no attribution or causal-edge claim; no `analytics never becomes authority` reversal; no field promotion; no new Parquet family; no global lineage schema migration.

> **Ontology note (L-003J):** Outcome identity framing advances from rival `scanner_outcome` / `oracle_outcome` labels to primary **`JOINT_OUTCOME_STATE`** (`Y_joint`). This is docs measurement-object framing only — not registry promotion, not attribution unlock. See `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`.

---
## 1. What this decision freezes

Three **doctrines** (meanings), not schema. The 12 `opportunities.produced_by` UNKNOWN cells are UNKNOWN for a definitional reason: the single `produced_by` field cannot hold writer + computational producer + owner simultaneously. This doc resolves the *meaning*; the schema shape is decided separately by measurement (Phase B, §2).

## 2. Phase B measurement result — lineage variance is LOCALIZED, not systemic

Measured across the 268-row lineage registry (read-only, no schema change):

| Relationship | Count | Share of 256 filled | Family context |
|---|---|---|---|
| written_by == owner | 191 | 75% | bar_structure (122), crt_construction (34), clean_labels (35) |
| written_by != owner | 65 | 25% | events (9) + crt_telemetry (56) — single writer backtest_v2 into two umbrella owners |
| produced_by UNKNOWN | 12 | — | opportunities |

Per-family produced_by (computational) vs written_by:
- crt_construction, bar_structure, clean_labels, events: produced_by == written_by (same emitter).
- crt_telemetry: partial (backtest_v2 emits; components compute).
- **opportunities**: produced_by != written_by — FeaturePipeline (features) + ATR path (risk/SL-TP) + scanner (serialization) all participate. **Genuinely multi-producer.**

consumed_by: single uniform value (`research/diagnostics only`) across all 268 rows. Zero variance.

**Conclusion (the key finding):** the repository does NOT exhibit four independent lineage dimensions. Lineage variance is localized to exactly one family: `opportunities`. A global 4-column lineage schema is **falsified by measurement** — it would add mostly-duplicate columns. The correct model is a **default plus documented exception**: `single producer` default, `multi-producer` exception only where measured (opportunities).

*Method note:* the first measurement pass used a buggy owner-emitter string normalization and wrongly reported 221 writer!=owner rows; corrected family-level mapping stands. Re-measuring changed the conclusion — which is the point of Phase B.

## 3. L-001 definitions (frozen meanings)

| Term | Meaning |
|---|---|
| `written_by` | serializer / emitter that wrote the record to JSONL |
| `produced_by` | computational producer(s) of the field VALUE |
| `owner` | semantic owner of the fact + its meaning |
| `consumed_by` | downstream reader(s); research/diagnostics unless attribution path resolves |

Doctrine: `single producer` is the default; `multi-producer` (`list[str]`) is an explicitly documented exception, promoted only where measured (opportunities).

## 4. Evidence taxonomy (frozen)

| Evidence class | Meaning | Attribution input allowed? |
|---|---|---|
| `CORPUS_VERIFIED` | observed in an actual JSONL/Parquet row on disk | Yes (with resolved produced_by) |
| `CODE_VERIFIED` | reachable in emitter code, not corpus-observed | Only after exit/oracle contract proves materialization |
| `DECLARED_ONLY` | documented, neither code-reachable nor observed | No |

This makes `implemented ≠ observed` durable. A finding must never move to attribution on `CODE_VERIFIED` alone.

## 5. Attribution eligibility doctrine (frozen)

Attribution = link a feature/field to an outcome credibly. Gate = identity + population + lineage + measurement contract (resolved producer + exit/oracle path + outcome meaning) + evidence = CORPUS_VERIFIED.

| Field | Eligible? | Why |
|---|---|---|
| `opportunities.outcome` / `rr_achieved` (`scanner_outcome`) | **NOT eligible** | detection-stream `scanner_outcome`, NOT realized trade edge / `attribution_target`; `ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS` (L-003) |
| `opportunities.features` / `clean_labels.features` | Not until producer-set resolved | children collapsed under parent; per-field producer unenumerable (GT-4) |
| crt_construction / bar_structure / events / clean_labels.y_* | Pending | lineage resolved, evidence CORPUS_VERIFIED; needs outcome/exit contract |

**L-003 (2026-09-07):** NOT frozen — status **OBSERVED_PARTIAL**. **L-003J:** ontology lock — `JOINT_OUTCOME_STATE` primary measured object (docs framing only; NOT registry promotion). Phase A vocab: `docs/governance/ANALYTICS_OUTCOME_SEMANTICS_L003.md` + JSON. Phase B scanner_outcome × oracle_outcome population comparison: `ANALYTICS_OUTCOME_POPULATION_COMPARISON_L003B.md` + JSON (HOMONYM). Phases C–E: LABEL_MISMATCH_SL_TP characterization + path-shape metrics + early MAE timing (T_MAE). Terminology parity audit: `docs/governance/ANALYTICS_L003_TERMINOLOGY_PARITY_AUDIT.md` (`L-003-TERM.v1`). Attribution remains blocked under **`ATTRIBUTION_BLOCKER_OUTCOME_SEMANTICS`** (scanner_outcome ≠ oracle_outcome as RVs) — distinct from **`ATTRIBUTION_BLOCKER_IDENTITY`** (L-001 `produced_by` UNKNOWN). No registry column promoted; freeze deferred. Bare `outcome` is not an RV name in corrected prose (`scanner_outcome` / `oracle_outcome` / `live_outcome`).

## 6. Promote vs hold

**Promote now (doctrine only):** L-001 definitions (§3), evidence taxonomy (§4), attribution-eligibility doctrine (§5).
**Hold (measured, not promoted):** global 4-column lineage schema — falsified; family-scoped `opportunities.produced_by = list[str]` — correct exception, deferred as its own governed change.


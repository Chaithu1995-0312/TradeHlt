# Corpus Authority Doctrine

| Field | Value |
|---|---|
| Status | Active (R0–R2 substrate) |
| Freeze | [`ohlcv-corpus-mutation-freeze-2026-07-10.md`](ohlcv-corpus-mutation-freeze-2026-07-10.md) |
| Schema | [`corpus_authority_decision.schema.json`](corpus_authority_decision.schema.json) |
| Decisions | [`corpus_authority_decisions.jsonl`](corpus_authority_decisions.jsonl) |
| PASS-B | [`ohlcv-closure-report-2026-07-10.md`](ohlcv-closure-report-2026-07-10.md) |
| Contract | [`ohlcv-output-contract-2026-07-10.json`](ohlcv-output-contract-2026-07-10.json) |

---

## Purpose

Row-level OHLCV integrity (G-01…G-04) is strong. The layer fails on **identity,
semantics, and provenance**. Corpus authority is the upstream primitive:

```text
logical corpus
  → approved physical artifact
  → exact SHA-256
  → source family
  → transformation chain
  → authority decision
```

Until that chain exists, temporal proofs, volume semantics, crypto source choice,
adversarial detectors, and the OHLCV handoff gate have **no stable object**.

---

## Dependency graph (remediation order)

```text
                    CORPUS AUTHORITY DECISIONS
                              │
                              ↓
                 CORPUS BINDING MANIFEST          ← R3
                  logical id → exact bytes
                              │
                              ↓
                  LOAD-TIME ADMISSION GATE        ← R3
                              │
                ┌─────────────┼──────────────┐
                ↓             ↓              ↓
         PROVENANCE      FIELD SEMANTICS   TEMPORAL
                              │
                              ↓
                  ADVERSARIAL DETECTORS           ← R7
                              ↓
                    HANDOFF GATE TEST             ← R8
```

**R0–R2 (this slice):** freeze + decision schema + XAUUSD adjudication package.
**Not yet:** generalized binding, load-time gate, crypto/volume/temporal remediations.

---

## Decision statuses

| Status | Meaning |
|---|---|
| `APPROVED` | Exact bytes may enter a binding manifest (R3) for governed load |
| `REJECTED` | Explicitly not authoritative; do not bind or load as canonical |
| `QUARANTINED` | Held out of authority; may remain on disk for forensics |
| `UNRESOLVED` | **Default seed.** No binding. No governed load (once R3 exists). |
| `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` | **Scope freeze only.** Exact path+hash+range may be used for Phase-1 validation probes — **not** AUTHORITATIVE / VALIDATED / ECONOMICALLY_ADMISSIBLE / APPROVED |

Critical rules:

```text
UNRESOLVED
  → cannot enter binding manifest
  → cannot be loaded by governed research paths (R3)

FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION
  → Phase-1 work MUST target the frozen object only (fail-closed hash/range)
  → does NOT grant production authority or economic admissibility
  → promotion requires a later APPROVED decision on the SAME hash
```

### XAUUSD Phase-1 frozen candidate (active)

| Field | Value |
|---|---|
| Binding | [`xauusd_m15_phase1_frozen_candidate.json`](xauusd_m15_phase1_frozen_candidate.json) |
| Path | `data/mt5/XAUUSD_M15.csv` |
| SHA-256 | `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Range | `2024-05-22T01:00:00` → `2026-05-21T23:45:00` (47,275 rows) |
| Enforcer | `src/data_ingestion/xauusd_phase1_candidate.py` |
| Status | `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` |

**Out of scope for Phase-1 XAUUSD validation:** `data/XAUUSD_M15.csv` (extended root `486cf361…`), quarantine twin, yfinance short window.

Census `authority_class` (e.g. `AUTHORITATIVE_CANONICAL` by path convention) is
**inventory evidence**, not an authority decision. Seeding never auto-APPROVEs.

---

## G-10 synthetic corpora (design constraint)

Guarantee G-10 (`no undeclared substitution`) is CONTRADICTED under the current
system. Remediation must **not ban synthetic corpora**. It must require:

- declared derivation lineage (`transformation_chain` / parent ids), and
- field semantics (`volume_semantic`, `volume_meta.is_synthetic`, etc.)

bound to corpus identity. Undeclared synthesis is the defect; declared synthesis
with lineage is admissible under authority rules.

---

## XAUUSD golden vertical slice

See [`corpus_authority_XAUUSD_M15_adjudication-2026-07-10.md`](corpus_authority_XAUUSD_M15_adjudication-2026-07-10.md).

User must select Option A/B/C/D before any byte move or R3 admission work.

---

## Enforcement today

| Layer | Mechanism |
|---|---|
| Process freeze | freeze policy doc |
| Mechanical pin | `tests/test_ohlcv_corpus_freeze.py` |
| Decision integrity | `tests/test_corpus_authority_decisions.py` |
| Load-time admission | **none** (R3) |

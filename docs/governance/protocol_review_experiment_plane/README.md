# Protocol Review Experiment Plane (PREP)

**Status:** 🅿️ **PARKED_CONTINUE_LATER** (2026-07-14) — resume Wave A when owner un-parks  
**Task class:** EXPLORATORY_RESEARCH_DESIGN_ONLY  
**Created:** 2026-07-14  
**Claude memory:** `project_prep_msip_whole_prereg_parked.md` (MEMORY index)  
**Grants no RUN / IMPLEMENTATION / production authority**

---

## Purpose

Extend the Research Control Plane so **independent LLM technical reviews** of preregistration protocols become **registered, falsifiable review claims** — not automatic project truth and not automatic protocol amendments.

```text
LLM_REVIEW_FINDING  ≠  PROJECT_TRUTH
LLM_REVIEW_FINDING  ≠  AUTOMATIC_PROTOCOL_AMENDMENT

LLM_REVIEW_FINDING
        ↓
REGISTERED CLAIM (RF-id)
        ↓
EXPECTED EVIDENCE (pre-declared)
        ↓
VALIDATION (synthetic / mechanical first)
        ↓
DECISION LEDGER
        ↓
AMEND PROTOCOL | REJECT FINDING | HOLD FOR DESIGN HYPOTHESIS
```

---

## Key separation

| Layer | What it holds | Authority |
|-------|---------------|-----------|
| **Review claim** | Reviewer assertion about a protocol defect/ambiguity | Not truth until decided |
| **Design hypothesis** | Only when empirical discrimination among competing *protocol procedures* is required | Research design only |
| **Scientific hypothesis (H-id)** | Market/representation claim (e.g. M2−M1) | Assigned only after protocol freeze |
| **Market WHAT/HOW/WHO** | Quantities, thresholds, CRT lifecycle | Separate architecture authority |

**Rule:** A review finding does **not** automatically become a design hypothesis. Only findings that require empirical discrimination among competing protocol constructions (e.g. null generators) become design hypotheses.

---

## Finding type vocabulary

| Type | Typical path |
|------|----------------|
| `MECHANICAL_DEFECT` | Verify semantics → amend if confirmed → mechanical test → close |
| `STATISTICAL_DESIGN_UNCERTAINTY` | Pre-register candidate procedures → synthetic calibration → design hypothesis → select one |
| `SPECIFICATION_AMBIGUITY` | Resolve authority → freeze one rule → mechanical test → close |
| `AUTHORITY_GAP` | Trace executable surface → C0–C6 class → authorize or block |
| `NON_BLOCKING_RECOMMENDATION` | Optional amend list; not freeze-blocking |

---

## Change surface classes (mandatory before code)

| Class | Meaning | Default action |
|-------|---------|----------------|
| **C0** GOVERNANCE_ONLY | Wording / explicit rule in protocol | Protocol amend |
| **C1** CONFIG_ONLY | Existing generic capability; freeze values | Config variants |
| **C2** RESEARCH_INFRASTRUCTURE | New generic research Python; no market behavior authority | Authorize C2 only |
| **C3** MARKET_WHAT | Canonical quantity identity/formula | **BLOCK** — separate authority |
| **C4** MARKET_HOW | Thresholds / interpretation / model policy | **BLOCK** |
| **C5** MARKET_WHO | Lifecycle / state ownership | **BLOCK** |
| **C6** PRODUCTION_BEHAVIOR | Trading / execution consumers | **BLOCK** |

Invariant:

```text
REVIEW → CLAIM → TRACE → C0–C6
  C0/C1 → protocol/config path
  C2 → generic research capability + tests + synthetic validation
  C3–C6 → STOP; not PREP auto-remediation
```

**Config-only after harness exists:** “no code, only config” applies **after** the validation harness supports the experiment family. Do not force genuinely different algorithms into scalar config knobs.

---

## Artifact schema (this directory)

| Artifact | Role |
|----------|------|
| `review_claim_registry.jsonl` | One RF-id per finding (append-only) |
| `review_dedupe_map.json` | Overlap clusters across reviewers |
| `executable_authority_trace.json` | Capability exists? surface? class? |
| `review_validation_registry.jsonl` | Pre-declared validation recipes (when frozen) |
| `review_evidence_manifest.jsonl` | Pointers to immutable evidence (when run) |
| `review_decision_ledger.jsonl` | CLOSE / AMEND / REJECT per claim |
| `raw_reviews/` | Preserved reviewer artifacts |
| `REVIEW_VALIDATION_IMPLEMENTATION_PLAN_V1.md` | Ordered work plan (no code until authorized) |
| `configs/RF-*/` | Frozen validation config variants (when authorized) |

---

## Lifecycle (every reviewer)

```text
REVIEWER
  → RAW REVIEW ARTIFACT
  → NORMALIZE FINDINGS
  → DEDUPLICATE vs existing RF claims
  → CLASSIFY finding type
  → REGISTER RF-id
  → DEFINE EXPECTED EVIDENCE (before validation)
  → FREEZE VALIDATION CONFIG
  → IMPLEMENT GENERIC VALIDATOR IF REQUIRED (C2 only, authorized)
  → RUN ON SYNTHETIC / MECHANICAL EVIDENCE
  → EMIT EVIDENCE
  → INDEPENDENT CRITIQUE
  → DECISION LEDGER
  → AMEND PROTOCOL OR REJECT FINDING
  → RE-REVIEW (if required)
```

---

## Processing order (this package)

1. **Register** all Gemini + DeepSeek findings (done in V1 registry).  
2. **Validate / close Gemini blocking claims first** (`RF-GEM-001..003` + linked clusters).  
3. **Do not implement** DeepSeek-only amendments until Gemini cluster evidence is decided (or explicitly waived).  
4. Amended protocol → **independent re-review** (next reviewer sees hardened draft, not the same known defects only).  
5. Only after freeze + owner accept: H-id assignment and RUN (separate session).

---

## Non-authority stamp

```text
PROTOCOL_REVIEW_EXPERIMENT_PLANE = GOVERNANCE_ONLY
MARKET_WHAT_CHANGE = NO (by PREP alone)
MARKET_HOW_CHANGE = NO
MARKET_WHO_CHANGE = NO
PRODUCTION_BEHAVIOR_CHANGE = NO
HYPOTHESIS_ID_ASSIGNMENT = NOT_BY_PREP
RUN_AUTHORITY = NO
```

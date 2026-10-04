# Review-Validation Implementation Plan V1

**Protocol:** `MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1`  
**Plane:** Protocol Review Experiment Plane  
**Date:** 2026-07-14  
**Status:** 🅿️ **PARKED_CONTINUE_LATER** — un-park with owner “Continue PREP” / Wave A grant  
**Code changes in this plan phase:** **NONE** (plan + registry only)  
**RUN of MSIP whole experiment:** **NO**  
**H-id assignment:** **NO**

---

## 0. Goal of this plan

```text
INGEST Gemini + DeepSeek reviews
  → register RF claims (not auto-hypotheses)
  → dedupe
  → executable authority trace
  → C0–C6 classification
  → ordered validation / amendment plan
  → STOP before code unless owner authorizes C2 wave
```

---

## 1. Hard governance rules (frozen for PREP)

1. `LLM_REVIEW_FINDING ≠ PROJECT_TRUTH`  
2. `LLM_REVIEW_FINDING ≠ AUTOMATIC_PROTOCOL_AMENDMENT`  
3. Review claim → expected evidence → validation → decision ledger  
4. **Do not** turn every finding into a design hypothesis — only empirical protocol-procedure choices (null generators; possibly HP-selection estimand identity)  
5. **Do not** blindly adopt Gemini purge = h−1; derive from `R_h = close[t+h]/close[t]−1`  
6. **Do not** use real H-019 / MSIP-whole outcomes to select null or purge  
7. Process **Gemini wave completely** before implementing DeepSeek-only amendments  
8. C3–C6 market/production surfaces are **BLOCK** for PREP auto-remediation (none registered here)  
9. Config-only rule applies **after** generic harness exists for that experiment family  

---

## 2. Inventory summary

| Source | Blocking | Non-blocking | Unique freeze-blocking clusters |
|--------|----------|--------------|----------------------------------|
| Gemini | BF-01,02,03 | categorical; HP note | 3 primary (purge, null, M1 missingness) |
| DeepSeek | B1–B10 | N1–N5 | +8 clusters (HP, sign, tree, mult, GS2, M2 cov, episode, dedupe) |
| Dedupe | — | — | **11 freeze-blocking clusters** total |

Full IDs: `review_claim_registry.jsonl` · clusters: `review_dedupe_map.json` · traces: `executable_authority_trace.json`.

---

## 3. C0–C6 rollup (primary class per freeze-blocking cluster)

| Cluster | Primary RF | Primary class | Market WHAT/HOW/WHO | Prod |
|---------|------------|---------------|--------------------|------|
| TEMPORAL_PURGE | RF-GEM-001 | **C2** | NO | NO |
| GLOBAL_NULL | RF-GEM-002 (+ RF-DS-005 C0 spec) | **C2** + C0 | NO | NO |
| M1_BARS_SINCE | RF-GEM-003 (+ RF-DS-004) | **C0** (rule); optional C2 emitter later | NO (WHO read-only) | NO |
| HP_SELECTION | RF-DS-001 | **C2** (+ C0 estimand text) | NO | NO |
| METRIC_SIGN | RF-DS-002 | **C0** | NO | NO |
| FTREE_CAPACITY | RF-DS-003 | **C0** | NO | NO |
| MULTIPLICITY | RF-DS-006 | **C0** | NO | NO |
| GS2 | RF-DS-007 | **C0** | NO | NO |
| M2_COVERAGE | RF-DS-008 | **C0** (+ optional C2 auditor) | NO | NO |
| EPISODE_DEP | RF-DS-009 | **C2** | NO | NO |
| DEDUPE | RF-DS-010 | **C0** (+ optional C2 resolver) | NO | NO |

**Conclusion:** No registered finding requires C3–C6. Python may change only as **generic research infrastructure (C2)** after explicit authorization.

---

## 4. Executable reality (condensed)

| Need | Exists today? | Evidence |
|------|---------------|----------|
| R₈ definition | YES | Protocol §5; `run_h_msip_001.py` `closes[i+8]/closes[i]-1` |
| Nested purged CV | NO | H-MSIP folds = equal-count labels only, no train/test purge |
| Dependence-preserving null gens | NO | Only label/row perms in research modules |
| `bars_since_range_entry` | NO as field | Only prereg text; `Range.formed_at` exists for observational derive |
| Whole-rep harness M0/M1/M2 | NO | Prereg draft only; IMPLEMENTATION_AUTHORIZED=NO |
| MSV schema | YES (design) | `MARKET_STATE_VECTOR_SCHEMA_V1.json` + `src/msip/*` shadow |

**Derived purge math (pre-validation hypothesis, not decision):**

```text
R8(t) depends on close[t+8]
max train index L must satisfy L + 8 < F  (F = first eval index)
⇒ purge_gap_bars = F - L - 1 ≥ 8 = h
Gemini h-1 is INSUFFICIENT under this indexing.
```

Validation must still run the mechanical auditor on synthetic indices before protocol amend is closed.

---

## 5. Wave A — Gemini first (authorize before code)

### A1. RF-GEM-001 — temporal leakage (C2)

| Field | Value |
|-------|--------|
| Type | MECHANICAL_DEFECT |
| Design hypothesis? | NO |
| Expected evidence | Zero dependency overlaps on all inner/outer splits |
| Config variants | `current_protocol`, `purge_h_minus_1`, `purge_h` |
| Decision rule | Smallest purge that yields zero violations under exact R8 semantics |
| Implementation (when authorized) | `OutcomeOverlapAudit` + purged expanding split |
| Forbidden | Real outcome selection |

### A2. RF-GEM-002 — global null (C2 design hypothesis)

| Field | Value |
|-------|--------|
| Type | STATISTICAL_DESIGN_UNCERTAINTY |
| Design hypothesis? | **YES** |
| Candidates | N0 month row-perm · N1 circular shift · N2 contiguous block · N3 bootstrap iff justified |
| Validation data | Synthetic null processes only (+ optional label-destroyed design matrix) |
| Expected evidence | Type-I, uniformity, dependence, fold/episode compatibility, determinism, cost |
| Companion C0 | RF-DS-005 exact math after selection |
| Forbidden | Select on real MSIP-whole ΔMSE |

### A3. RF-GEM-003 / RF-DS-004 — M1 missingness (C0 first)

| Field | Value |
|-------|--------|
| Type | SPECIFICATION_AMBIGUITY |
| First action | Authority trace (done: field not emitted; `formed_at` derivable) |
| Freeze options | (1) drop field from M1 · (2) always-defined observational encode from `formed_at` · (3) sentinel + missingness indicator |
| Forbidden | Imputation chosen by predictive performance |
| Optional C2 later | Information-set enumerator identity tests |

**Wave A exit:** decision ledger entries for RF-GEM-001..003 (+ secondary RF-DS-004/005 as applicable); protocol draft amended for those clauses only; evidence artifacts hashed; **then** Wave B.

---

## 6. Wave B — DeepSeek remainder (after Wave A)

Process in this order (minimize interaction risk):

1. **RF-DS-002** metric sign identity (C0) — unblocks every formula reading  
2. **RF-DS-007** GS2 single rule (C0)  
3. **RF-DS-010** dedupe ownership (C0)  
4. **RF-DS-008** M2 coverage policy (C0; optional C2 auditor)  
5. **RF-DS-006** multiplicity enumeration (C0)  
6. **RF-DS-003** F-TREE capacity policy (C0: justify / expand / exploratory-only)  
7. **RF-DS-001** HP selection estimand (C0 text + C2 modes) — design hypothesis: shared-M1 vs independent-per-M  
8. **RF-DS-009** episode dependence (C2; couple to null choice from A2)  

Optional non-blocking: RF-GEM-NB-01 categorical encoding; RF-DS-NB-*.

**Wave B exit:** all freeze-blocking clusters decided; prereg MD+JSON identity updated; protocol hash candidate; technical re-review package prepared.

---

## 7. Proposed generic C2 module map (NOT implemented this turn)

Only if owner authorizes RESEARCH_INFRASTRUCTURE:

```text
src/research/protocol_validation/   # or equivalent package placement per CONVENTIONS
  temporal_validation.py     # PurgedExpandingSplit, OutcomeOverlapAudit
  null_generators.py         # interface + N0..N3 configs
  model_selection.py         # shared_M1 | independent_per_M
  information_sets.py        # M0/M1/M2 resolver, dedupe, missingness encode
  protocol_audit.py          # coverage, multiplicity checklist helpers
```

```text
configs/review_claims/
  RF-GEM-001/{current,purge_h_minus_1,purge_h}.yaml
  RF-GEM-002/{month_permute,circular_shift,contiguous_block}.yaml
  RF-GEM-003/authority_resolution.yaml
  RF-DS-001/{shared_hp_from_M1,independent_hp_per_M}.yaml
```

```text
results/research/protocol_review/
  RF-*/EVIDENCE.json
  RF-*/CRITIQUE.md
  review_decision_ledger.jsonl
```

Tests: synthetic-only unit + property tests; no MSIP-whole RUN; no production config rehash unless unrelated.

---

## 8. What is NOT in scope of PREP

- Assigning H-id for MSIP whole representation  
- RUN of M0/M1/M2 experiment  
- CRT transition / MSIP production authority  
- Threshold research / promotion  
- ChatGPT third-reviewer pass (after amended draft)  
- Blind acceptance of any reviewer’s preferred statistical fix  

---

## 9. Immediate next actions (owner-facing)

| # | Action | Auth needed |
|---|--------|-------------|
| 1 | Accept PREP registry + this plan as process of record | Owner stamp |
| 2 | Authorize **Wave A C2** for leakage auditor + null interface only | Explicit C2 grant |
| 3 | Run Wave A synthetic validations; write decision ledger | After #2 |
| 4 | Amend prereg for Wave A closes only | C0 after evidence |
| 5 | Wave B C0 amends + remaining C2 | Separate grants |
| 6 | Independent re-review of amended protocol | Reviewers |
| 7 | Owner FREEZE (still no RUN same session by default) | Owner |

**This session stop:**

```text
PREP_V1 REGISTERED
CODE_CHANGE = NO
RUN = NO
FREEZE = STILL_BLOCKED
NEXT = owner authorize Wave A C2 OR request C0-only protocol text amends that do not need code
```

---

## 10. Suggested owner decision prompts

1. **Wave A C2 authorization?** Build generic purged-split auditor + null-generator interface without touching CRT/MSIP authority?  
2. **M1 field policy preference?** Drop `bars_since_range_entry` vs observational `formed_at` encoding vs sentinel+indicator?  
3. **HP estimand identity?** Keep shared-M1 (conservative vs M2 peaking) vs independent-per-M (matches “incremental information” wording) — freeze as design choice after optional synthetic study?  

# MSIP-1 Verification Prompt (IDENTICAL for every LLM)

**Generated:** 2026-07-14T07:08:43Z  
**Role:** Independent verifier. You receive only the frozen `msip_1_verification_package/`.  
**You do not have the full repository.** Do not invent files outside the package.

---

## Mission

Verify the proposed Market-State Interpretation Program (MSIP-1) against repository evidence in this package.

Answer exactly these four questions:

1. **What is the proposed design?**
2. **What does the repository actually do?**
3. **Where do they contradict?**
4. **Is there enough evidence to declare the design verified and ready for implementation?**

Final verdict must be one of:

- `MSIP-1 VERIFIED`
- `MSIP-1 VERIFIED WITH BLOCKERS`
- `MSIP-1 REJECTED`

---

## Hard rules

1. **No majority voting.** Even if you know other models might agree, each claim needs evidence labels.
2. Every material claim must be labeled:
   - `PROVEN_BY_EXECUTABLE_EVIDENCE`
   - `PROVEN_BY_AUTHORITATIVE_ARTIFACT`
   - `CONTRADICTED`
   - `UNKNOWN`
   - `DESIGN_DECISION_REQUIRED`
3. **Non-transitive closure:**  
   - CRT CLOSED ≠ EngineRunner / DecisionEngine / live SM closed  
   - CANONICAL_FEATURE_CODE_SURFACE CLOSED ≠ model reuse authorized  
   - Feature Query Surface AUTHORITY_ACTIVE ≠ producer/consumer/model closed  
   Read `01_governance/closure_authority_index.json`.
4. **Freshness / supersession:**  
   Read `00_manifest/AUTHORITY_FRESHNESS.md` before trusting historical fc05 graphs or contracts.  
   When historical and later artifacts conflict, the later authority wins **only if** the freshness doc says so.
5. **feature_surface_query.py** is a join tool. Prefer underlying authoritative artifacts for conclusions.
6. **crt_feature_builder.py** is included to be classified — do not assume it is active production authority.
7. Do not use economic/backtest PnL as MSIP verification evidence.
8. Open questions in `06_design/MSIP-1_OPEN_QUESTIONS.json` are **not decided**. Label any use of them `DESIGN_DECISION_REQUIRED`.
9. Do not propose production code changes in the verification response (recommendations only).

---

## Required reading order

1. `00_manifest/MSIP-1_SOURCE_MANIFEST.json` (integrity)
2. `00_manifest/AUTHORITY_FRESHNESS.md`
3. `00_manifest/MSIP-1_DESIGN_CONTRACT.md` and `06_design/*`
4. `01_governance/closure_authority_index.json` + `CLAUDE.md` (doctrine sections)
5. Feature authority (`02_feature_authority/`)
6. Feature evidence (`03_feature_evidence/`) — note historical vs current
7. CRT runtime (`04_crt_runtime/`) + CRT baseline extract
8. Tests + `05_tests/TEST_EXECUTION_REPORT.json`

---

## Required output format

```markdown
# MSIP-1 Verification — <MODEL_NAME>

## 1. Proposed design (summary)
...

## 2. Repository actual behavior (summary)
...

## 3. Contradictions and frictions
| ID | Design claim | Repo evidence | Label | Notes |
|---|---|---|---|---|

## 4. Claim matrix (material)
| Claim | Label | Evidence paths |
|---|---|---|

## 5. Open questions used / remaining
...

## 6. Blockers (if any)
...

## 7. Verdict
MSIP-1 VERIFIED | MSIP-1 VERIFIED WITH BLOCKERS | MSIP-1 REJECTED

## 8. Confidence and unknowns
...
```

Store your full response unchanged under:

`07_llm_responses/<MODEL_NAME>_<UTC_DATE>.md`

---

## Integrity check before you start

Confirm you can see:

- design contract
- source manifest with SHA256 list
- feature_schema.py
- feature_38_lineage_census-2026-07-11.json (not only LATEST pointer)
- canonical_feature_code_surface_closure-2026-07-11.md
- feature_surface_closure_audit-2026-07-11.json
- crt_closure_report.md
- crt_config_reachability.json
- state_contract*.py / state_topology.py / active_models.yaml
- test execution report

If any required file is missing, verdict = `MSIP-1 REJECTED` with reason `INCOMPLETE_PACKAGE`.

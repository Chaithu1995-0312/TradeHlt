# Next Design Boundary — MSV as a Whole (Decision C)

**Status:** **PREREGISTRATION COMMISSIONED** (review → freeze → owner accept → STOP)  
**Execution authorized:** **NO**  
**Implementation authorized:** **NO**  
**Date:** 2026-07-14  

---

## Authoritative preregistration package

| Artifact | Path |
|----------|------|
| Protocol (human) | [`MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1.md`](MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1.md) |
| Protocol (machine) | [`MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1.json`](MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1.json) |
| Technical review | [`MSIP_WHOLE_REPRESENTATION_TECHNICAL_REVIEW_CHECKLIST_V1.md`](MSIP_WHOLE_REPRESENTATION_TECHNICAL_REVIEW_CHECKLIST_V1.md) |
| Owner freeze stub | [`MSIP_WHOLE_REPRESENTATION_OWNER_FREEZE_STUB_V1.json`](MSIP_WHOLE_REPRESENTATION_OWNER_FREEZE_STUB_V1.json) |

```text
TASK_CLASS = EXPLORATORY_RESEARCH_DESIGN_ONLY
PRIMARY_CONTRAST = M2 − M1
HYPOTHESIS_ID = NOT_ASSIGNED_UNTIL_PROTOCOL_IS_REVIEW_COMPLETE
EXECUTION_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZED = NO
```

---

## Why this boundary

H-017/H-018 closed partition-level residual testing as a general claim. The next question is
representation-level: whether governed continuous MSV adds reproducible information **beyond
CRT lifecycle + baseline market controls**.

---

## Forced nested sets

```text
M0 = baseline market controls
M1 = M0 + CRT lifecycle observations
M2 = M1 + governed MarketStateVector WHAT
PRIMARY TEST = M2 − M1
```

---

## Process stop

```text
Commission prereg V1
  → independent technical review (Gemini FAIL · DeepSeek FAIL)
  → Protocol Review Experiment Plane (PREP): register RF claims
  → validate Gemini wave → amend → DeepSeek wave → amend
  → re-review amended protocol
  → freeze protocol hash
  → owner acceptance of FREEZE only
  → STOP
  → (later session) H-id + RUN only if explicitly granted
```

**Current (2026-07-14):** 🅿️ **`FREEZE_BLOCKED_PARKED_CONTINUE_LATER`**.  
Claims + plan: [`docs/governance/protocol_review_experiment_plane/`](../governance/protocol_review_experiment_plane/README.md).  
Claude memory (Orient): `project_prep_msip_whole_prereg_parked.md`.  
**Resume later:** Wave A (RF-GEM-001..003) only — not DeepSeek implementation first.  
Code/RUN for the scientific experiment remain **unauthorized**.

Do **not** assign RUN authority in the freeze-acceptance session unless owner explicitly
separates and grants it (default: **never same session**).

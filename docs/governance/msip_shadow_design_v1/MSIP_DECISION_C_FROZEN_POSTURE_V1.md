# MSIP Decision C — Frozen Posture V1

**Frozen:** 2026-07-14  
**Implementation boundary:** **none open**  
**Migration:** **NOT_AUTHORIZED**

Machine authority: `MSIP_DECISION_C_FROZEN_POSTURE_V1.json`

---

## Frozen posture

```text
ARCHITECTURE_DECISION = C
MSIP_SHADOW_LAYER = IMPLEMENTED_AND_OBSERVATIONAL
G-SHADOW-01 = PASSED_FOR_DECLARED_XAUUSD_POPULATION
G-PARITY-01 = PARTIAL
G-MIG-01 = CLOSED

CRT_AUTHORITATIVE_LIFECYCLE = UNCHANGED

BODY_WICK_HYGIENE = DEFERRED
NEW_FM_IDENTITIES = DEFERRED_UNTIL_CONSUMER_NEED
THRESHOLD_RESEARCH = NOT_AUTHORIZED
CONCURRENT_CANDIDATES = NOT_AUTHORIZED
CRT_MIGRATION = NOT_AUTHORIZED
PRODUCTION_CUTOVER = NOT_AUTHORIZED

H-017/H-018 THREAD = SCOPE_CLOSED
H-017 = PRESERVED (ORIGINAL_±32_BAR_MATCHED_ESTIMAND_ONLY)
H-018 = ACCEPTED MATCHING_DEPENDENT
P-BOS+1 OCCUPANCY-WIDE = NOT_SUPPORTED
DECISION_C_PROGRAM = REMAINS_OPEN
NEXT_BOUNDARY = MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1
NEXT_STATUS = DRAFT_FOR_INDEPENDENT_TECHNICAL_REVIEW
EXECUTION_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZED = NO
HYPOTHESIS_ID = NOT_ASSIGNED_UNTIL_PROTOCOL_IS_REVIEW_COMPLETE
```

- Thread closure: `docs/research-readiness/h-msip-001-h018-thread-closure.md`  
- Whole-MSV prereg: `docs/research-readiness/MSIP_WHOLE_REPRESENTATION_PREREGISTRATION_V1.md`  
- Review checklist: `docs/research-readiness/MSIP_WHOLE_REPRESENTATION_TECHNICAL_REVIEW_CHECKLIST_V1.md`

---

## Why G-PARITY-01 stays PARTIAL

The “parity failure” is three different authority relationships:

| Surface | Relationship | Implication |
|---------|--------------|-------------|
| body_ratio / wick_size | EXACT CANONICAL IDENTITY | Possible hygiene later; little research value now |
| ATR | Same absolute SMA-TR(14) math; absolute CRT runtime ↔ relative FM-041 | Governed transform; migration would hit calibrated HOW |
| EMA 2 / 5 | DISTINCT GOVERNED QUANTITIES | Not substitutes for EMA 9 / 21 |

Forcing `G-PARITY-01 = PASS` would falsely imply every CRT-local quantity maps 1:1 onto an existing canonical feature.

---

## No new implementation boundary

- Body/wick hygiene → **DEFERRED**
- New FM ids (absolute ATR, EMA-2/5) → **DEFERRED_UNTIL_CONSUMER_NEED**
- Threshold research / concurrent candidates / CRT migration / cutover → **NOT_AUTHORIZED**

---

## Next high-value work (not more MSIP infrastructure)

Use what exists:

- deterministic shadow MarketStateVector + provenance  
- CRT funnel + fail-reason telemetry  
- resolved local-math authority  
- WHAT / HOW / WHO boundaries  

…to define the **first falsifiable market-state research hypothesis** and run it through the Research Control Plane:

```text
hypothesis_registry
  → experiment definition
  → frozen population
  → controls
  → shadow MarketStateVector observations
  → evidence
  → critique
  → decision ledger
```

### Entry points

| Piece | Path |
|-------|------|
| Hypothesis registry | `src/governance/hypothesis_registry.py` |
| Seed / artifact | `scripts/governance/seed_hypothesis_registry.py` → `data/hypothesis_registry.jsonl` |
| Validate | `python scripts/governance/query_hypotheses.py --validate` |
| M4 qualification (research only) | `src/research/qualification.py` |
| Shadow runner | `scripts/analysis/run_msip_shadow.py` |
| Findings | `docs/current-findings.md` |
| Task class policy | `docs/governance/TASK_CLASSIFICATION_BEHAVIOR_POLICY.md` |

### Constraints for any first hypothesis

- Authority remains **research** (§6.5)  
- Shadow outputs stay **observational only**  
- CRT lifecycle stays authoritative  
- Do not open G-MIG-01 or retune CRTConfig as the default next step  
- Do not build more MSIP architecture before testing research value  

---

## Related packages

- Design: `docs/governance/msip_shadow_design_v1/`
- Implementation evidence: `docs/governance/msip_shadow_implementation_plan_v1/G_IMPL_01_EVIDENCE_PACKAGE_V1.md`
- Math authority: `docs/governance/crt_local_math_authority_resolution_v1/`

# H-MSIP-002 / H-018 Run Findings (maintained)

**Date:** 2026-07-14  
**Owner verdict:** `MATCHING_DEPENDENT` (**ACCEPTED**)  
**Authority:** RESEARCH_ONLY  
**Thread:** H-017/H-018 **SCOPE_CLOSED** (with H-017 preserved under matched estimand only)

---

## Owner acceptance

```text
H-018_RESULT = ACCEPTED
H-018_VERDICT = MATCHING_DEPENDENT
P-BOS_PLUS_1_OCCUPANCY_WIDE_SIGNAL = NOT_SUPPORTED
FOLLOW_UP_EXECUTION_AUTHORIZED = NO
```

Artifact: `results/research/h_msip_002/H_018_OWNER_ACCEPTANCE_V1.json`

## Decisive evidence

```text
E0  ORIGINAL MATCHED ESTIMAND     −7.261e−5
E1  BROADER OVERLAP ESTIMAND      +2.57e−4
E2  TIME-BLOCKED STRATIFIED       +1.52e−4
```

E1 retained ~89.4%, ESS treatment ~3481, no severe overlap violation — reversal not dismissed as weight pathology. E2 independently reverses.

Composition: not selective under pre-registered SMD flags → problem is **estimand/question mismatch** (local match vs broader support), not obvious covariate imbalance.

## Implications

1. H-017 micro residual **preserved** under original frozen matched protocol.  
2. Occupancy-wide P-BOS=+1 claim **not supported**.  
3. No rescue experiments on P-BOS=+1.  
4. No economic / MSIP / CRT / threshold / migration / production authority.

## Artifacts

- `results/research/h_msip_002/H_018_EXPERIMENT_EVIDENCE_V1.json`
- `results/research/h_msip_002/H_018_CRITIQUE.md`
- Closure: `docs/research-readiness/h-msip-001-h018-thread-closure.md`

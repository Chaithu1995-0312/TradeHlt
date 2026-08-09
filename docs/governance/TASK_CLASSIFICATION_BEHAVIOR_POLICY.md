# Task Classification — Behavior-Preservation Policy

**Status:** ACTIVE (2026-07-14)  
**Supersedes (as general forward acceptance criterion):**  
`VERIFY ZERO BEHAVIORAL CHANGE AGAINST BASELINE TRANSITION / EVENT / TRADE HASHES`

---

## Decision

The general requirement that future work reproduce historical CRT/backtest **transition / event / trade hashes** is **SUPERSEDED**.

| Field | Value |
|---|---|
| `BASELINE_HASH_PARITY_GENERAL_REQUIREMENT` | **SUPERSEDED** |
| `HISTORICAL_BASELINE_ARTIFACTS` | **PRESERVED** (not deleted; comparison evidence only) |
| `OBSERVATION_ONLY_NEUTRALITY` | **REQUIRED** when task class is OBSERVATION_ONLY |
| `AUTHORIZED_BEHAVIOR_CHANGE` | **PERMITTED** when task class authorizes it |
| `FUTURE_ACCEPTANCE_POLICY` | **TASK_CLASSIFICATION_BASED** |

### Remove from active forward planning

```text
Future work must preserve baseline transition/event/trade hashes.
```

### Replace with

```text
Behavior-preservation requirements are determined by task classification.
Historical baseline hashes are comparison evidence, not immutable future acceptance criteria.
Authorized behavior changes must be evaluated by before/after evidence and preserved invariants,
not rejected solely because historical output hashes changed.
```

---

## Do not delete historical evidence

Preserve baseline traces, hashes, diagnostics, manifests, and run results as:

- historical executable evidence  
- before/after comparison references  
- regression-investigation inputs  
- causal attribution evidence  
- reproducibility anchors  

They are **not** permanent golden outputs that future system behavior must match.

Examples (preserved, non-golden):

- `docs/governance/xauusd_crt_baseline_trace/` (incl. freeze pointer)  
- `docs/governance/xauusd_crt_transition_trace/`  
- `docs/governance/crt_xauusd_funnel_diagnostic-2026-07-14.*`  
- `results/cert_xau_phase2/run_20260711_202626_XAUUSD/`  

---

## Task classes

### 1. `OBSERVATION_ONLY`

**Behavior preservation is required** against the *current* executable path under same inputs.

Applies to: instrumentation, telemetry, tracing, diagnostics, passive measurement.

Requirements:

- default-off where optional hooks exist  
- same-input ON/OFF parity (smallest sufficient deterministic corpus; full 47k rerun **not** mandatory solely for historical hash equality)  
- no alteration of authoritative outputs when disabled  
- no silent promotion of measurement into production authority  

### 2. `BEHAVIOR_CHANGE_AUTHORIZED`

**Historical output-hash equality is NOT required.**

Intentional change is expected when the governing plan authorizes it.

Require instead:

- explicit change hypothesis  
- declared affected boundary  
- frozen input population where comparison is intended  
- before/after measurements  
- invariant preservation (declared)  
- contract/schema compatibility checks  
- deterministic reproducibility where applicable  
- evidence of intended effects  
- measurement of unintended effects  
- updated artifacts and decision ledger  

### 3. `EXPLORATORY_RESEARCH`

**Historical parity is NOT required.**

Require:

- frozen experiment definition  
- reproducible inputs  
- explicit variables changed  
- controls where appropriate  
- evidence capture  
- no silent promotion to production authority  

---

## Classification before execution

Every engineering turn that touches CRT/runtime/feature consumers should state:

```text
TASK_CLASS = OBSERVATION_ONLY | BEHAVIOR_CHANGE_AUTHORIZED | EXPLORATORY_RESEARCH
```

If omitted for instrumentation/diagnostics, default = **OBSERVATION_ONLY**.

---

## Immediate application

| Task | Class |
|---|---|
| `try_*` fail-reason instrumentation | **OBSERVATION_ONLY** |
| MSIP shadow implementation | later: may start OBSERVATION_ONLY / EXPLORATORY; consumer cutover = BEHAVIOR_CHANGE_AUTHORIZED |
| Retest geometry / TTL / concurrent candidates | BEHAVIOR_CHANGE_AUTHORIZED (when planned) |

---

## Authority

Governance policy only. Does **not** authorize production cutover, CRT reopen, or economic claims.
Does **not** delete or invalidate historical baselines as evidence.

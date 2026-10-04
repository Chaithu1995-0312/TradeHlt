# Model Responsibility Matrix

> **What this is.** One table answering *"which model is allowed to do what?"* across every
> registered model at once. MIAR states each model's `authority_boundary` and
> `explicit_non_goals` as **per-model prose**; this document projects that prose onto a **shared
> taxonomy** so overlaps, gaps, and drift are visible in one screen instead of seventeen.
>
> **Created:** 2026-07-29 · **Authority: NONE — derived view.**
> [`MODEL_INTENT_AUTHORITY_REGISTER.md`](../governance/MODEL_INTENT_AUTHORITY_REGISTER.md) (MIAR)
> is authoritative for every cell. This file adds **no new intent claims**. On any conflict,
> MIAR wins and this file is the thing that gets fixed.
>
> **Companions:** [`intelligence-topology.md`](intelligence-topology.md) (how they connect) ·
> [`target-strategy-architecture.md`](target-strategy-architecture.md) §11 (stage table) ·
> [`crt_intent_contract.md`](../governance/crt_intent_contract.md) (the open CRT conflict)

---

## 1. The taxonomy

Seven responsibilities. They are deliberately **capabilities, not stages** — a stage says *when*
a model runs, a responsibility says *what it is permitted to change*.

| # | Responsibility | Means |
|---|---|---|
| R1 | **Emit score** | Produces an ordinal score that fusion consumes |
| R2 | **Veto** | Can hard-reject a candidate on its own |
| R3 | **Approve** | Can emit `execute` — the affirmative decision |
| R4 | **Size** | Determines position size / risk fraction |
| R5 | **Set SL/TP** | Determines execution geometry |
| R6 | **Mutate CRT state** | Can advance, reset, or otherwise change the state machine |
| R7 | **Write prod config** | Can change `ACTIVE_VERSION` or production JSON |

**Legend**

| Mark | Meaning |
|---|---|
| ✅ | **Owned** — this is the model's job |
| ➖ | **Forbidden** — MIAR `explicit_non_goals` names it, or the boundary excludes it |
| ⬜ | Not applicable — the responsibility is meaningless for this component |
| 📊 | Advisory only — produces the shape, carries no authority (sidecar / research) |
| 🟡 | **DRIFT** — contract and code disagree. See §3. |

---

## 2. The matrix

### 2.1 Spine (the 17 MIAR entries)

| Model | R1 score | R2 veto | R3 approve | R4 size | R5 SL/TP | R6 CRT state | R7 config |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `market_ontology` | ➖ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ➖ |
| `feature_pipeline` | ➖ | ⬜ | ➖ | ⬜ | ⬜ | ➖ | ⬜ |
| `crt` | ✅ | ✅ | **🟡** | **🟡** | **🟡** | ✅ | ⬜ |
| `gaussian` | ✅ | ➖ | ➖ | ⬜ | ➖ | ➖ | ⬜ |
| `zone_gate` | ✅ | ✅ | ➖ | ⬜ | ➖ | ➖ | ⬜ |
| `rr_engine` | ✅ | ➖ | ➖ | ⬜ | ➖ | ⬜ | ⬜ |
| `rr_trained` | 📊 | ➖ | ➖ | ⬜ | ➖ | ⬜ | ⬜ |
| `tradenet` | 📊 | ➖ | ➖ | ⬜ | ⬜ | ➖ | ⬜ |
| `bitnet` | ➖ | ✅ | ➖ | ⬜ | ➖ | **🟡** | ⬜ |
| `trap` | ✅ | ➖ | ➖ | ⬜ | ⬜ | ➖ | ⬜ |
| `breakout` | ✅ | ➖ | ➖ | ⬜ | ➖ | ➖ | ⬜ |
| `regime` | ⬜ | ➖ | ➖ | ⬜ | ⬜ | ➖ | ⬜ |
| `decision_fusion` | ✅ | ✅ | ✅ | ⬜ | ➖ | ➖ | ⬜ |
| `execution_intent` | ➖ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| `qualification_gate` | ➖ | 📊 | ➖ | ⬜ | ⬜ | ⬜ | 📊 |
| `backtest` | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ➖ |
| `research_runner` | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ➖ |

### 2.2 Risk / execution layer (not MIAR scoring engines)

MIAR §4 records these as owners of real questions while explicitly noting they are *"not a MIAR
scoring engine; risk layer."* They hold the authority the scoring engines are forbidden.

| Component | R1 | R2 | R3 | R4 | R5 | R6 | R7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `ExecutionPlannerV1_2` | ⬜ | ➖ | ➖ | ⬜ | ✅ | ⬜ | ⬜ |
| `UltronRiskGate` | ⬜ | ✅ | ➖ | ✅ | ➖ | ⬜ | ⬜ |
| `PromotionManager` | ⬜ | ✅ | ⬜ | ⬜ | ⬜ | ⬜ | ✅ |

`UltronRiskGate` is the **sole** owner of economic reward:risk (F-048) and of sizing.
`PromotionManager` is the **sole** writer of `ACTIVE_VERSION` (goal.md invariant #4).

### 2.3 Advisory sidecars (MIAR §3A — zero spine authority by contract)

| Model | R1 | R2 | R3 | R4 | R5 | R6 | R7 |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| `hierarchical_meta_fusion` | 📊 | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| `tradenet_meta` | 📊 | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| `replay_memory` | 📊 | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |
| `cognitive_bus` | ⬜ | ➖ | ➖ | ➖ | ➖ | ➖ | ➖ |

Enforced mechanically by `tests/test_miar_registry.py::test_sidecar_has_zero_spine_authority`.

---

## 3. Drift cells (🟡) — contract vs code

Four cells where the matrix cannot honestly say ✅ or ➖. **Each is an open item, not a decision
this document makes.**

### 3.1 `crt` × R3 approve / R4 size / R5 SL-TP

MIAR's `crt` non-goals include **"never decide whether to trade."** The runtime does exactly
that: `crt_engine_v2.CRTEngine` — via its internal `UltronRiskEngine.approve*` path — approves,
sizes, and opens trades directly. [`crt_intent_contract.md`](../governance/crt_intent_contract.md)
records this formally as a Stage 1+3+4+5 monolith and proposes three remediations
(relabel / physically extract / accept as documented drift) — **still awaiting a user ruling.**

MIAR's own rollup already carries `crt` at 🟡 for this reason. This matrix does not resolve it;
it makes the blast radius visible: **three** responsibilities, not one.

### 3.2 `bitnet` × R6 mutate CRT state

MIAR declares BitNet's boundary as *"veto on approve path only (when enabled)."* R6 is not
mentioned — but a BitNet reject **resets the CRT state machine**, because the gate fires *inside*
`crt_engine_v2`'s approve path rather than at the decision layer.

That is a state mutation, and it is the mechanism behind **F-055**: gate-ON is a *divergent
trajectory*, not a filtered subset of gate-OFF (BNB showed 50 `LOW_SCORE` rejects yet net trades
stayed 11 → 11 — removed ≠ added). A veto that only skipped the candidate would have been a
subset.

**Undeclared side effect, not a declared authority.** Resolving it is the substance of
[`bitnet-design-specification.md`](bitnet-design-specification.md): moving BitNet out of the state
machine turns 🟡 into ➖.

### 3.3 Known reinterpretation: `gaussian` score read as `p_win`

Not a cell — a *cross-model* violation. `decision_fusion`'s non-goals include **"never reinterpret
Gaussian score as probability,"** and `gaussian`'s include **"never claim probability without
calibration."** The DecisionEngine nonetheless consumes the Gaussian score as `p_win`.

MIAR §4 already flags this as a duplicate-ownership issue (🟡 on both). Recorded here because it
is the clearest example of the failure mode this taxonomy exists to catch: **no single model
misbehaved** — the violation lives in the *edge* between two correctly-specified models.

Note also **F-060**: the live Gaussian channel is effectively unparameterized and degenerates to a
near-constant ≈ 0.8825. So the misread quantity is additionally near-constant.

---

## 4. What the matrix shows

1. **Exactly one component owns each of R3–R5, R7.** Approve → `decision_fusion`. Size →
   `UltronRiskGate`. SL/TP → `ExecutionPlanner`. Config → `PromotionManager`. That is the
   architecture working: authority is scarce and named.
2. **R2 veto is deliberately plural** — `zone_gate`, `bitnet`, `UltronRiskGate`, and
   `decision_fusion` can each reject. Vetoes compose safely; approvals do not. This asymmetry is
   intentional and should survive any redesign.
3. **R6 has one legitimate owner and one accidental one.** `crt` owns its state machine; `bitnet`
   mutates it as an undeclared side effect of firing inside it.
4. **Every 🟡 traces to one root cause:** responsibilities that should live at the decision layer
   are physically executing inside `crt_engine_v2`. §3.1 and §3.2 are the same defect seen from
   two models.

---

## 5. Maintenance

- A new model gets a row **before** it is wired, not after.
- A ✅ appearing in a second row for R3, R4, R5, or R7 is a **governance error** — authority for
  those is singular by design.
- Changing a cell from ➖ to ✅ requires a MIAR `authority_boundary` edit first; this file follows.
- 🟡 cells are resolved by fixing code or amending MIAR — **never** by quietly re-marking the cell.

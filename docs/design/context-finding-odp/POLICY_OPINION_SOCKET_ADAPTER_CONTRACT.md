# PolicyOpinion + SocketAdapter Contract

**Status:** design-only (v1.2). No runtime. No `src/` changes.
**Companion:** `SOCKET_ADAPTER_MATRIX.md` (precedence + hardened DecisionEngine coupling).  
**Path (after copy):** `D:\\Tradelatest\\docs\\design\\context-finding-odp\\POLICY_OPINION_SOCKET_ADAPTER_CONTRACT.md`  
**Date:** 2026-09-06

## 0. Decision

Do **not** build: SemanticResolver, ExecutionOntology, TradeObjectGenerator, ExecutionProfile as primary runtime owners.

Build only (when Act is authorized later):

1. **PolicyOpinion** — user-chosen stances (not facts, not decisions)
2. **SocketAdapters** — translate stances into knobs already owned by DecisionEngine / ExecutionPlanner / UltronRiskGate

CRTEngine, DecisionEngine, ExecutionPlanner, UltronRiskGate remain the sole decision/execution authorities. Resolver + Trace remain observation-only.

## 1. Doctrine

| Rule | Meaning |
|------|---------|
| Observation ↛ Decision | Resolver / Trace / ODP / Findings never approve, reject, or size |
| ODP = measured; Policy = chosen; never mix | No quantiles on Policy; no size/participation on ODP |
| PolicyOpinion ≠ Decision | Stances are preferences; owners still `execute`/`approve` |
| PolicyOpinion does not know DecisionEngine | **SocketAdapters** know the sockets |
| Finding → Decision forbidden | Legal path: Finding → ODP → PolicyOpinion → Adapters → Owners |
| No second `S_t` | Adapters never write CRTEngine state / transitions / lifecycle |
| Producer match (D2) | PolicyOpinion may consume an ODP only when `ODP.condition.state_producer` matches the producer on the live decision path (CRTEngine → `engine`). Resolver-produced ODPs (`state_producer=resolver`) are observation-only — they may inform a Finding, never a live PolicyOpinion. Recording the producer makes Engine≠Resolver divergence (F-069, 88.16% agreement) visible; this rule makes acting across it illegal. |


## 1a. producer_actionability_rule (D2 — inlined)

Inline copy of `odp.schema.yaml` `producer_actionability_rule` (must stay aligned; do not rely on cross-ref alone):

```text
An ODP with state_producer=resolver is OBSERVATION-ONLY: it may inform a Finding
or research conclusion, but a PolicyOpinion that gates a LIVE decision path may only
consume an ODP whose state_producer matches the producer on that live path. The live
path is CRTEngine (state_producer=engine). Recording the producer makes Engine/Resolver
divergence visible; this rule is what makes acting across that divergence illegal
rather than merely visible.

Operational consequences for PolicyOpinion:
- Resolved or pinned odp_ref MUST have condition.state_producer=engine.
- A resolver-produced ODP never becomes a live stance: treat as on_odp_fallback (ABSTAIN).
- Never silently fall back from a missing engine-producer match to a resolver-produced row.
```

## 1b. Precedence (v1.1)

```
ABSTAIN > DEFENSIVE > NORMAL > AGGRESSIVE
```

Any gating `ABSTAIN` stops the execution path. Adapters share this table; they do not invent per-owner conflict logic.  
Example: `participation=AGGRESSIVE` + `risk=ABSTAIN` → ABSTAIN wins.

## 1c. DecisionEngine coupling (v1.1 harden)

DecisionEngine adapters may apply **`ABSTAIN` only** (pre-gate skip/reject).  
`AGGRESSIVE` / `DEFENSIVE` participation must **not** retune `p_win` / score / weak-component thresholds (keeps "what we believe" separate from "what we want").  
Participation bias lands on **Planner + Ultron** sockets instead. See `SOCKET_ADAPTER_MATRIX.md`.

## 2. Live owners (correct paths)

| Owner | Path | Owns |
|-------|------|------|
| CRTEngine | `src/config_layer/crt_engine_v2.py` | `S_t`, lifecycle, transitions, CRT SL/TP path |
| CRTStateResolver | `src/features/crt_state_resolver.py` | `F_t \| S_t` metadata — **not** `S_t` |
| Trace | `src/runtime/crt_construction_trace.py` | Observation join only |
| DecisionEngine | `src/core/decision_engine.py` | Semantic execute \| reject (no RR/size; F-048) |
| ExecutionPlanner | `src/config_layer/execution_planner.py` | Intent + entry + gate (not SL/TP/RR) |
| UltronRiskGate | `src/core/ultron_risk_gate.py` | Capital approve + `final_position_size` |

*(Caller paths like `src/execution/*` are not the live owners — do not invent parallel modules there.)*

Upstream (frozen for this contract): **Context** = identity key; **ODP** = measured distributions + `contract_ref`. This document does not redesign them.

## 3. PolicyOpinion (schema — conceptual)

Smallest object. Categorical. Channelized.

```text
PolicyOpinion
  id:                 POLICY-*
  status:             DRAFT | ACTIVE | SUPERSEDED | RETIRED
  owner:              user
  contract_ref:       MC-*          # may only act when ODP.contract_ref matches (prefer SEALED for ACTIVE)
  context_selector:   Context | null   # sparse; null selectors normal
  odp_ref:            ODP-* | null     # optional pin; else resolve via Context + contract_ref
                                        # any resolved/pinned ODP MUST have state_producer=engine (D2 producer-match rule) —
                                        # a resolver-produced ODP resolves to ABSTAIN via on_odp_fallback, never to a live stance
  on_odp_fallback:    ABSTAIN          # required default when ODP confidence is none / FALLBACK

  channels:
    participation_stance:  ABSTAIN | NORMAL | AGGRESSIVE | DEFENSIVE
    risk_stance:           ABSTAIN | NORMAL | AGGRESSIVE | DEFENSIVE
    intent_stance:         ABSTAIN | NORMAL | ALLOW_FILTERED

  optional_hints:                      # chosen numbers ONLY; never copied from ODP fields
    size_hint_mult:        float | null   # maps to Ultron position_size_hint path; bounds enforced by adapter
    risk_percent_override: float | null   # maps to Ultron trade.risk_percent when set

  measured_fields: {}                  # MUST be empty
```

### Stance meanings (chosen)

| Stance | Intent |
|--------|--------|
| ABSTAIN | Do not proceed through this channel’s owners |
| NORMAL | Pass-through — do not bias knobs |
| AGGRESSIVE | Bias toward more participation / size within Ultron floors |
| DEFENSIVE | Bias toward less participation / size / tighter semantic bars |
| ALLOW_FILTERED | Intent channel only: apply allowlist / unknown-intent reject |

### Coexistence

Channels are independent. Example legal: `participation=AGGRESSIVE` + `risk=DEFENSIVE`.  
If **any** channel that gates the path is `ABSTAIN`, adapters must pre-reject / skip — they do not become DecisionEngine.

### Forbidden on PolicyOpinion

- quantiles, `n`, sample confidence, corpus pins  
- `downside_tail_reduced`, `upside_convexity`, or other ODP/Finding vocabulary as native fields  
- `execute` / `approve` / `final_position_size` / CRT state labels  
- Writing Context, ODP, Findings, Trace, or `S_t`

## 4. SocketAdapters (the missing component)

Adapters are **pure functions / config overlays**. They consume `PolicyOpinion` (+ optional resolved ODP metadata for eligibility only: `confidence`, `contract_ref` match — **not** quantile arithmetic as hidden policy).

They emit **knob patches** for existing owners. They never call the broker. They never advance `S_t`.

### 4.1 DecisionEngineAdapter

**Target sockets:** constructor/`evaluate` **config** thresholds; optional pre-call veto.

| Stance | Adapter effect |
|--------|----------------|
| ABSTAIN | Pre-gate: do not call `evaluate`, or inject forced reject **before** owner (wrapper), without mutating fusion/score facts |
| NORMAL | No config overlay |
| AGGRESSIVE / DEFENSIVE | **No DecisionEngine overlay (v1.1).** Route participation bias to Planner + Ultron adapters only. |

**Must not:** retune belief thresholds; write `score`, `p_win`, `zone_gate`, `fusion` as if measured; add RR/size (F-048).

### 4.2 ExecutionPlannerAdapter

**Target sockets:** planner `config` (`reject_unknown_intent`, intent allowlist, `gate_approval_threshold` / weights).

| Stance (`intent_stance` / participation) | Adapter effect |
|------------------------------------------|----------------|
| ABSTAIN | Skip `plan()` or pass non-execute upstream |
| NORMAL | No overlay |
| ALLOW_FILTERED | Apply intent allowlist; keep `reject_unknown_intent=true` |
| AGGRESSIVE / DEFENSIVE (participation) | Bias `gate_approval_threshold` / weights as **chosen** constants |

**Must not:** overwrite feature vector with ODP; invent SL/TP/RR (CRT / `compute_crt_levels` path).

### 4.3 UltronRiskGateAdapter

**Target sockets:** `trade.risk_percent`, `trade.position_size_hint`; optional risk **config** floors (`min_rr_ratio`, max risk/day/trades) as chosen overlays.

| Stance (`risk_stance`) | Adapter effect |
|------------------------|----------------|
| ABSTAIN | Skip Ultron / do not submit trade |
| NORMAL | No overlay (hint null / risk_percent unchanged) |
| AGGRESSIVE | Raise `position_size_hint` and/or `risk_percent` within hard Ultron caps |
| DEFENSIVE | Lower hint / `risk_percent`; may raise effective caution via config overlay |

**Must not:** set `final_position_size` (Ultron owns it); treat ODP `p5`/`p95` as size; bypass kill switch / RR floor checks.

## 5. End-to-end flow

```
OHLC
  → CRTEngine                 (S_t)                 [IDENTITY / EXECUTION]
  → Resolver + Trace          (F_t|S_t, join)       [OBSERVATION]
  → Context                   (identity key)        [design / join]
  → ODP                       (measured)            [design / measurement]
  → PolicyOpinion             (stances)             [THIS ARTIFACT]
  → SocketAdapters            (knob patches)        [THIS ARTIFACT]
       ├─→ DecisionEngine
       ├─→ ExecutionPlanner
       └─→ UltronRiskGate
  → Trade / Broker
```

## 6. Worked example (illustrative)

**ODP (facts only):** Context = SWEEP + breaker_present + order_block_present; `p5` improved vs baseline; `confidence=survivor`; `contract_ref=MC-…`.

**PolicyOpinion (chosen):**

```text
participation_stance: AGGRESSIVE
risk_stance:          DEFENSIVE
intent_stance:        ALLOW_FILTERED
on_odp_fallback:      ABSTAIN
size_hint_mult:       0.8          # chosen, not p5→formula
```

**Adapters:**

- DecisionEngine: slightly loosened participation thresholds (policy constants)
- Planner: intent allowlist on; unknown intent rejected
- Ultron: `position_size_hint` / `risk_percent` reduced (DEFENSIVE), despite AGGRESSIVE participation upstream

Owners still emit `execute`/`approve`/`final_position_size`. Policy did not.

## 7. Illegal designs (refuse)

1. Semantic Resolver as second `S_t` or execution authority  
2. Finding → size / Finding → Trade Object  
3. ODP → `size_multiplier` as a fact field  
4. PolicyOpinion that stores quantiles or claims `execute`  
5. Adapter that mutates fusion scores or engine state  
6. New DecisionEngine / parallel Ultron inside adapters  
7. More Context/ODP YAML as a substitute for this contract  

## 8. Implementation gate (later — not now)

Act only when authorized, and only if:

- Adapters are pure overlays with golden tests: same owner inputs → same owner outputs when stance=NORMAL  
- ABSTAIN never reaches broker  
- Decision-neutrality of Trace/Resolver preserved  
- No ACTIVE_VERSION / G001 claim from Policy alone  

Until then: this document is the design freeze for PolicyOpinion + SocketAdapter.

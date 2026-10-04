# MSIP-1 Design Contract — Market-State Interpretation Program

**Status:** PROPOSED UNDER VERIFICATION (not implemented; not authorized)  
**Package generated:** 2026-07-14T07:08:43Z  
**Repository commit (at package build):** see `00_manifest/MSIP-1_SOURCE_MANIFEST.json`  
**Authority:** research/governance design under multi-LLM verification only  
**Does NOT grant:** production wiring, model enablement, economic claims, CRT reopen, feature formula changes

---

## 0. Purpose of this document

This contract freezes the **proposed** MSIP-1 design for independent verification. Verifiers must answer:

1. What is the proposed design?
2. What does the repository actually do?
3. Where do they contradict?
4. Is there enough evidence to declare the design verified and ready for implementation?

Evidence labels for every material claim:

| Label | Meaning |
|---|---|
| `PROVEN_BY_EXECUTABLE_EVIDENCE` | Demonstrated by code + tests |
| `PROVEN_BY_AUTHORITATIVE_ARTIFACT` | Demonstrated by named authority doc/config |
| `CONTRADICTED` | Design conflicts with executable or authority |
| `UNKNOWN` | Insufficient evidence in package |
| `DESIGN_DECISION_REQUIRED` | Open question; not silently fillable |

**Do not majority-vote.** Five LLMs agreeing on a false claim remains false.

---

## 1. Problem statement

The repository already has:

- a **feature math surface** (ontology → registry → pipeline/derived_math/candle_math) with identity certification progress and a CLOSED **canonical feature code surface** boundary;
- a **CRT interpretation state machine** (9 states) that is **CLOSED** for OHLCV → `TRADE_OPENED`;
- multiple **consumers** (EngineRunner, models, backtest, research, dashboards) with known encoding/name collisions.

Missing is a **governed, config-first interpretation layer** that composes certified market features into a stable **MarketStateVector** for observation/research/shadow use **without**:

- re-deriving feature math locally,
- forking CRT transitions,
- claiming model or economic authority from upstream closure.

MSIP-1 is that proposed layer.

---

## 2. Proposed architecture

```text
OHLCV
  → FeaturePipeline / candle_math / derived_math   (FEATURE AUTHORITY — existing)
  → (optional) CRTEngine state machine             (CRT AUTHORITY — existing, CLOSED)
  → MarketStateInterpreter (NEW, proposed)         (MSIP — compose, not invent math)
        → MarketStateVector
        → shadow telemetry / research consumers
        → (FUTURE, gated) production consumers
```

### 2.1 MarketStateVector

A structured, versioned interpretation object with named dimensions (see
`MSIP-1_STATE_DIMENSION_MATRIX.json`):

- `structure_state`
- `liquidity_state`
- `volatility_state`
- `session_state`
- `trend_state`
- optional `crt_phase` (OQ-002)
- optional `setup_quality` (event-gated composite)

Each dimension must declare:

- candidate features / FM IDs
- output type + domain
- config ownership
- consumers
- PIT / publication semantics
- whether it depends on CRT

### 2.2 Config boundaries

- New section: `msip` in production config (proposed).
- Strict load (`_require` / `from_prod_config`); no silent defaults for new knobs.
- CRT thresholds remain under `crt_engine` / `params` / `active_models` state_contracts.
- MSIP must not duplicate CRT knobs under new names.

See `MSIP-1_CONFIG_OWNERSHIP_MATRIX.json`.

### 2.3 CRT relationship

| Rule | Statement |
|---|---|
| R1 | CRT CLOSED remains authoritative for CRT transitions |
| R2 | MSIP may **read** CRT state as a dimension only if OQ-002 decides yes |
| R3 | MSIP must not implement a second state machine that redefines CRT edges |
| R4 | MSIP existence does **not** reopen CRT; CRT reopen conditions stay as in `closure_authority_index.json` |
| R5 | CH-002 emission names (`displacement_retrace`, `displacement_atr_ratio`) are CRT cache identities — MSIP must use those names for CRT-side quantities |

Baseline extract: `MSIP-1_CRT_STATE_BASELINE.json` (9 states, transitions, state_contracts).

### 2.4 Feature relationship

| Rule | Statement |
|---|---|
| F1 | Feature math remains ontology/registry/pipeline authority |
| F2 | MSIP composes features; does not re-implement FM math |
| F3 | `CANONICAL_FEATURE_CODE_SURFACE CLOSED` ≠ MSIP closed ≠ model authorization |
| F4 | Feature Query Surface is a **join tool**, not an authority that replaces lineage/closure artifacts |
| F5 | Historical fc05 dependency graph may mark structure features LEAKING; **FC1-A** is current production causal contract — freshness rules apply |

### 2.5 Visual validation (proposed gate, OQ-007)

If in-scope, visual validation means:

- overlays of MarketStateVector dimensions vs price
- encoding legends that match canonical codes (session 0/1/2, vol regime 0/1/2)
- no dashboard-only remapping without an adapter layer

---

## 3. Invariants (must hold if implemented)

1. **No local formula math** — new quantities registered first (construction protocol).
2. **Non-transitive closure** — CRT CLOSED / feature-code CLOSED do not authorize MSIP production authority.
3. **Config-first behavioral knobs** — no magic numbers in new MSIP code paths.
4. **PIT / no lookahead** — any multi-bar dimension must be prefix-invariant.
5. **Single encoding authority per dimension** — foreign encodings require explicit adapters.
6. **Shadow-first** — production consumers off until Authority Ladder evidence.
7. **Identity preservation** — FM-021 split identity, FM-027 role grounding, M14B vol regime deps, session pipeline identity remain.
8. **Logging** — SESSION LOG + no silent truth divergence.

---

## 4. Non-goals (MSIP-1)

- Economic edge discovery or promotion
- Retrain / re-enable Gaussian, BitNet, TradeNet, rr_fusion
- Replacing CRT as trade lifecycle authority
- Expanding the 38-dim vector without a migration program
- Resolving all M15 completion debts inside MSIP-1 (session encoding may be a **dependency**, not a free gift)
- Using backtest PnL as MSIP verification evidence

---

## 5. Gates before implementation

| Gate | Requirement |
|---|---|
| G0 | Multi-LLM verification package complete + identical across reviewers |
| G1 | No CONTRADICTED material design claims unresolved |
| G2 | All DESIGN_DECISION_REQUIRED items either decided by user or deferred with stop boundary |
| G3 | CRT baseline parity (code VALID_TRANSITIONS ↔ YAML) holds |
| G4 | Mechanical test subset green (see test report) |
| G5 | Construction protocol classification ready for first implementation slice |

---

## 6. Stop conditions

Stop and re-scope if:

- verification finds MSIP requires reopening CRT CLOSED without a valid reopen condition;
- design requires ungoverned formula math;
- design assumes feature-surface or query-surface closure authorizes model use;
- consumer encoding collisions are ignored while claiming activation readiness;
- LLMs disagree on material executable facts that repository recheck cannot resolve.

---

## 7. What the repository actually does today (summary for verifiers)

**Proven by package evidence (verifiers must re-check):**

- Feature production: `feature_pipeline.py` (+ candle_math/derived_math) builds the 38-dim vector and structural series.
- CRT: `crt_engine_v2.py` runs 9-state SM; closed for OHLCV→TRADE_OPENED (`crt_closure_report.md`).
- Orchestration: `engine_runner.py` fuses engines; research spine may run CRT-only (F-037 class).
- `crt_feature_builder.py` is a secondary surface — package includes it so verifiers do not confuse it with pipeline authority.
- Closures are boundary-scoped (`closure_authority_index.json`).

**Not present today:**

- No `MarketStateVector` type or `msip` config section (as of package build).
- No MSIP interpreter module under `src/`.

---

## 8. Known friction (pre-registered)

From M15 completion census and certification artifacts:

- session encoding multi-surface mismatch
- trend_strength name collision with dual_engine
- volatility_regime int8 vs s05 strings
- FM-025 provenance unresolved (does not auto-taint FM-026)
- SUPERSEDED ema_spread/momentum_score still in 38-vector; successors unbound

These are **not automatically MSIP blockers**, but activation claims that ignore them are invalid.

---

## 9. Success criteria for verification verdict

| Verdict | When |
|---|---|
| **MSIP-1 VERIFIED** | Design coherent with executable reality; no material CONTRADICTED claims; open questions either decided or explicitly non-blocking; ready for construction-protocol implementation planning |
| **MSIP-1 VERIFIED WITH BLOCKERS** | Design direction sound but listed blockers must clear before implementation |
| **MSIP-1 REJECTED** | Material contradictions with repository authority/executable behavior, or design violates non-transitive closure / construction protocol |

---

## 10. Package map

| Dir | Content |
|---|---|
| `00_manifest/` | Contract, prompt, source manifest, freshness rules |
| `01_governance/` | CLAUDE.md, assistant_project.md, closure index |
| `02_feature_authority/` | Ontology, schema, math, pipeline, FM resolve |
| `03_feature_evidence/` | Identity/deps/consumers/lineage/closure/query surface |
| `04_crt_runtime/` | CRT engine, runner, models, config, state contracts, CRT closure |
| `05_tests/` | Mechanical tests + execution report |
| `06_design/` | This contract + matrices + CRT baseline extract |
| `07_llm_responses/` | Empty; store each LLM response verbatim |

---

## 11. Explicit non-claims

- This contract is **not** a finding in `docs/current-findings.md`.
- This contract is **not** a closure of MSIP.
- Packaging is **not** implementation.

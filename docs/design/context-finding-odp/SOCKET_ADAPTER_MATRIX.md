# Socket Adapter Matrix

**Status:** design-only (v1.1 provisional). No runtime. No `src/` changes.
**D1:** OPEN — belief vs preference boundary; ABSTAIN-only for DecisionEngine is the working hypothesis until doctrine decides.  
**Companion:** `POLICY_OPINION_SOCKET_ADAPTER_CONTRACT.md`  
**Path:** `D:\Tradelatest\docs\design\context-finding-odp\SOCKET_ADAPTER_MATRIX.md`  
**Date:** 2026-09-06

## Doctrine (unchanged)

```
Context = identity
ODP = measurement
PolicyOpinion = choice
SocketAdapter = translation
Owners = decisions
```

Finding → Decision forbidden.  
ODP = measured; Policy = chosen; never mix.  
Observation ↛ Decision.

## Precedence (conflict resolution)

Across channels that affect whether a path may reach execution, resolve stances with:

```
ABSTAIN > DEFENSIVE > NORMAL > AGGRESSIVE
```

**Rules**

1. If **any** gating channel is `ABSTAIN` → path stops (pre-gate). No owner invents its own precedence.
2. When combining participation vs risk for sizing-related overlays, the **more restrictive** stance wins under the order above (e.g. `participation=AGGRESSIVE` + `risk=DEFENSIVE` → defensive risk overlay still applies; participation may still allow the path to Planner/Ultron).
3. `participation=AGGRESSIVE` + `risk=ABSTAIN` → **ABSTAIN wins** → no execution path.
4. Adapters must share this table; they do not each invent conflict logic.

## DecisionEngine coupling (hardened)

| Allowed | Forbidden |
|---------|-----------|
| `ABSTAIN` → pre-gate reject / skip `evaluate` | `AGGRESSIVE` / `DEFENSIVE` mutating `p_win_threshold`, score clamps, or weak-component bars |
| `NORMAL` → no overlay | Rewriting `score` / `p_win` / `fusion` |

**Rationale:** DecisionEngine stays closest to truth-estimation ("what do we believe?"). Participation bias belongs on Planner + Ultron ("what do we want to do with capital / intent?"), not on belief thresholds.

## Matrix

### DecisionEngine — `src/core/decision_engine.py`

| Policy channel | Adapter | Owner socket | Allowed mutation | Forbidden mutation |
|----------------|---------|--------------|------------------|--------------------|
| `participation_stance` / any | DecisionEngineAdapter | Pre-call gate only | `ABSTAIN` → skip call or forced reject wrapper; `NORMAL` → noop | Threshold overlays (`p_win_threshold`, score percentile/min/max, `weak_component_threshold`); writing fusion/score/p_win; RR/size |
| `risk_stance` | — | — | None (not a DecisionEngine concern) | Any |
| `intent_stance` | — | — | None | Any |
| `on_odp_fallback` | DecisionEngineAdapter | Pre-call gate | If fallback/none confidence → treat as `ABSTAIN` | Inventing scores when ODP missing |

### ExecutionPlanner — `src/config_layer/execution_planner.py`

| Policy channel | Adapter | Owner socket | Allowed mutation | Forbidden mutation |
|----------------|---------|--------------|------------------|--------------------|
| `participation_stance` | PlannerAdapter | `config` gate knobs; call/skip | `ABSTAIN` → skip `plan`; `NORMAL` → noop; `AGGRESSIVE`/`DEFENSIVE` → **chosen** `gate_approval_threshold` / weight overlays only (policy constants, not ODP formulas) | Overwriting feature vector; SL/TP/RR; treating ODP quantiles as features |
| `intent_stance` | PlannerAdapter | `reject_unknown_intent`, intent allowlist | `ALLOW_FILTERED` → allowlist + reject unknown; `ABSTAIN` → skip; `NORMAL` → noop | Inventing intents from Findings/ODP |
| `risk_stance` | — | — | None directly (risk → Ultron) | Sizing in planner |
| `on_odp_fallback` | PlannerAdapter | call/skip | Fallback → skip `plan` | Synthetic intent |

### UltronRiskGate — `src/core/ultron_risk_gate.py`

| Policy channel | Adapter | Owner socket | Allowed mutation | Forbidden mutation |
|----------------|---------|--------------|------------------|--------------------|
| `risk_stance` | UltronAdapter | `trade.risk_percent`, `trade.position_size_hint`; optional risk **config** overlays | `ABSTAIN` → skip submit; `NORMAL` → noop; `DEFENSIVE`/`AGGRESSIVE` → bias hint/risk_percent within Ultron hard caps; optional chosen config floors | Setting `final_position_size`; ODP `p5`→size as fact; bypassing kill switch / RR floor |
| `participation_stance` | UltronAdapter | same size/risk hint sockets (secondary) | Only if path reached Ultron and risk channel not ABSTAIN; still respect precedence (risk ABSTAIN/DEFENSIVE dominates aggressiveness) | Using participation to override ABSTAIN risk |
| `optional size_hint_mult` / `risk_percent_override` | UltronAdapter | `position_size_hint` / `risk_percent` | Apply as **chosen** numbers after stance resolution | Copying ODP fields into these sockets under measurement names |
| `on_odp_fallback` | UltronAdapter | call/skip | Fallback → skip | Guessed size |

## Ownership preservation check

| Owner | Still owns | Adapter may not own |
|-------|------------|---------------------|
| CRTEngine | `S_t`, lifecycle, CRT SL/TP path | State, transitions |
| Resolver | `F_t \| S_t` metadata | Rival `S_t` |
| Trace | Observation join | Approve/reject/size |
| DecisionEngine | execute \| reject (semantic) | Economics; policy-as-belief thresholds |
| ExecutionPlanner | intent + entry + gate | SL/TP/RR; final size |
| UltronRiskGate | capital approve + `final_position_size` | Truth-estimation; CRT state |

## Refuse to build

SemanticResolver runtime · ExecutionOntology runtime · TradeObjectGenerator · ExecutionProfile layer · ODP→size formulas · Findings→risk multipliers

## Freeze criterion

This matrix + precedence table + DecisionEngine ABSTAIN-only rule are frozen for review. Implementation (when authorized) is mechanical overlays + golden NORMAL-neutrality tests — not new authorities.

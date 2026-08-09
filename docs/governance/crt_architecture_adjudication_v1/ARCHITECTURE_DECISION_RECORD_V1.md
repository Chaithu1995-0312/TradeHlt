# CRT Architecture Decision Record V1

_Generated 2026-07-14T08:12:37.280834+00:00_

## DECISION: **C** — C. SEPARATE_CONTINUOUS_MARKET_STATE_OBSERVATION_FROM_CRT_OPPORTUNITY_LIFECYCLE

**Status:** DECIDED  
**Task class (this package):** OBSERVATION_ONLY  
**Threshold tuning authorized:** False  
**Implementation authorized:** False

## Decisive criteria

- Executable dual path: governed 38-vector parallel to CRT-local transition inputs (PROVEN)
- CRT is single-candidate opportunity lifecycle, not continuous market-state observer (PROVEN)
- Primary collapse is lifecycle/geometry/HTF ownership, not EngineRunner rejection (PROVEN)
- Threshold tuning alone cannot fix split WHAT authority or single-candidate monopolization (STRONG)
- Replacing 9-state CRT reopens CLOSED boundary without proof of necessity (PROVEN authority constraint)

## Rejected options

- **A:** Insufficient as sole next phase — collapses architectural split to threshold search
- **B:** Addresses concurrency only; leaves CRT-local WHAT duplication and continuous-state gap
- **D:** Unsupported by current evidence; requires explicit CRT-boundary reopen authority (not permanently forbidden by CLOSED)

## Next phase

- **Name:** MSIP_SHADOW_CONTINUOUS_STATE_LAYER_DESIGN
- **Task class:** OBSERVATION_ONLY / EXPLORATORY_RESEARCH
- **Behavior change authorized:** False

## Required invariants

- CRT CLOSED boundary (OHLCV→TRADE_OPENED) remains unreopened unless formal reopen conditions fire
- Canonical feature code surface CLOSED remains unreopened by this decision
- Non-transitive closure: continuous-state layer does not inherit production authority from feature CLOSED
- OBSERVATION_ONLY work remains behavior-neutral when hooks disabled
- Historical baselines preserved as comparison evidence
- No economic claims from architecture decision
- MarketStateVector must not silently become CRT transition authority without BEHAVIOR_CHANGE_AUTHORIZED plan

## Gates

- GATE_1_EVIDENCE_SUFFICIENCY: **PASS**
- GATE_2_EXECUTABLE_REALITY: **PASS**
- GATE_3_AUTHORITY_MAP: **PASS**
- GATE_4_WHAT_HOW_WHO_BOUNDARIES: **PASS**
- GATE_5_ALTERNATIVE_COMPARISON: **PASS**
- GATE_6_DECISION_REVERSIBILITY: **PASS**
- GATE_7_CLOSED_BOUNDARY_COMPATIBILITY: **PASS**
- GATE_8_IMPLEMENTATION_BOUNDARY: **PASS**

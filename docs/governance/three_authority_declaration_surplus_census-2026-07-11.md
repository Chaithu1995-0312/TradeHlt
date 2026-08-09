# Three-Authority Declaration Surplus Census (2026-07-11)

| Field | Value |
|---|---|
| Schema | `three_authority_declaration_surplus_census.v1` |
| Status | **CENSUS_ONLY** — observational only |
| ACTIVE_VERSION | `v2_multi_2026_04` |
| Authority | observational — grants no enablement, promotion, or topology change |
| Machine ledger | [`three_authority_declaration_surplus_census-2026-07-11.json`](three_authority_declaration_surplus_census-2026-07-11.json) |

## Authority model (frozen)

| Layer | Home | Owns | Must not own |
|---|---|---|---|
| **WHAT** | `configs/formulas/market_ontology.yaml` | FM identity, formulas, impl bindings | thresholds, state graph |
| **WHO** | `active_models.yaml` | models, states, transitions, required_fm, config *names* | numbers, formula text, eval |
| **HOW** | production JSON + `CRTConfig` | threshold values, TTLs, flags | FM math |
| **CODE** | `crt_engine_v2` + `features/*` | guards, enum, seed graph, callables | — |

**No fourth YAML.** Surplus cleanup = strip/mark/ref — not a new registry file.

## Summary counts

| Metric | Value |
|---|---|
| Detection numeric defaults (WHO) | 9 |
| Threshold block entries (WHO) | 48 |
| Active HOW ≠ WHO default drifts | 6 |
| Formula-like prose paths (WHO) | 17 |
| State contracts (clean WHO) | 9 |
| Contract field violations | 0 |
| Contract required_fm | FM-002, FM-010, FM-027, FM-028 |
| Ontology FMs not in contracts | 15 |
| Topology YAML≡code seed | True |
| Surplus records | 12 |
| Implementation candidates | 11 |
| P1 candidates | IC-001, IC-002, IC-008 |

## Surplus records

| ID | Class | Surplus | Owner | Runtime? | Risk | IC |
|---|---|---|---|---|---|---|
| SUR-001 | NUMERIC_DEFAULT_IN_WHO | WHO | HOW | N | HIGH_DOC_DRIFT | IC-001 |
| SUR-002 | NUMERIC_DEFAULT_IN_WHO | WHO | HOW | N | HIGH_DOC_DRIFT | IC-002 |
| SUR-003 | HOW_ACTIVE_VS_WHO_DEFAULT_DRIFT | WHO | HOW | N | HIGH_SESSION_MISREAD | IC-008 |
| SUR-004 | FORMULA_PROSE_IN_WHO | WHO | CODE_OR_WHAT | N | MEDIUM_DOC_DRIFT | IC-003 |
| SUR-005 | SCORING_WEIGHTS_IN_WHO | WHO | CODE | N | MEDIUM_DOC_DRIFT | IC-004 |
| SUR-006 | DUAL_TOPOLOGY_LOAD_BEARING | WHO+CODE | WHO_RUNTIME_GRAPH+CODE_SEED | Y | LOW_IF_PARITY_ENFORCED | IC-005 |
| SUR-007 | TRIPLE_TOPOLOGY_ARTIFACT | DOCS | CODE | N | LOW_TEST_PINNED | IC-006 |
| SUR-008 | HARDCODED_BEHAVIORAL_IN_CODE | CODE | SHOULD_BE_HOW | Y | MEDIUM_CONFIG_FIRST_GAP | IC-007 |
| SUR-009 | KEY_NAME_REDUNDANCY | WHO | WHO_STATE_CONTRACTS | N | LOW | IC-009 |
| SUR-010 | THRESHOLDS_NOT_IN_STATE_CONTRACTS | WHO_INDEX_GAP | HOW | N | LOW_NAVIGATION | IC-002 |
| SUR-011 | CLEAN_STATE_CONTRACTS | NONE | WHO | Y | NONE_POSITIVE_CONTROL | IC-KEEP |
| SUR-012 | ONTOLOGY_FM_NOT_IN_CONTRACTS | NONE | WHAT | N | NONE | IC-010 |

### Record detail (abridged)

#### SUR-001 — NUMERIC_DEFAULT_IN_WHO

- **Path:** `active_models.yaml crt.runtime.detection.*.defaults`
- **Evidence:** 9 numeric defaults under detection blocks (displacement/expansion/retest/expired). Restate CRTConfig/HOW seeds; not loaded by state_contract_loader or Phase-Topology.
- **Count:** 9
- **Candidate:** IC-001

#### SUR-002 — NUMERIC_DEFAULT_IN_WHO

- **Path:** `active_models.yaml crt.runtime.thresholds`
- **Evidence:** 48 threshold entries with embedded default values. Mirror CRTConfig dataclass defaults; session readers may treat as runtime HOW.
- **Count:** 48
- **Candidate:** IC-002

#### SUR-003 — HOW_ACTIVE_VS_WHO_DEFAULT_DRIFT

- **Path:** `params / crt_engine vs crt.runtime.thresholds|detection.defaults`
- **Evidence:** 6 keys where active production value ≠ WHO declared default (e.g. body_ratio_min params=0.65 vs WHO 0.70). Runtime follows HOW when loaded.
- **Count:** 6
- **Candidate:** IC-008

#### SUR-004 — FORMULA_PROSE_IN_WHO

- **Path:** `active_models.yaml crt.runtime.detection|scoring logic strings`
- **Evidence:** 17 formula-like prose strings in detection/scoring. Not executable; risk of dual-math narrative vs candle_math/derived_math/code.
- **Count:** 17
- **Candidate:** IC-003

#### SUR-005 — SCORING_WEIGHTS_IN_WHO

- **Path:** `active_models.yaml crt.runtime.scoring`
- **Evidence:** raw_formula embeds 0.35/0.25/0.20/0.20; soft_conf G^0.70×C^0.30; decay exp(-0.05×…). Parallel to code hardcodes; no FM ids.
- **Count:** 3
- **Candidate:** IC-004

#### SUR-006 — DUAL_TOPOLOGY_LOAD_BEARING

- **Path:** `valid_transitions ↔ VALID_TRANSITIONS`
- **Evidence:** YAML transitions parity with code seed: True. Phase-Topology injects WHO graph into StateMachine; module dict remains seed. state_list==CRTState: True.
- **Count:** 9
- **Candidate:** IC-005

#### SUR-007 — TRIPLE_TOPOLOGY_ARTIFACT

- **Path:** `docs/governance/crt_executable_state_graph.json`
- **Evidence:** Third topology home exists=True; states match state_list: True. Pinned by tests/test_crt_executable_state_graph.py.
- **Count:** 9
- **Candidate:** IC-006

#### SUR-008 — HARDCODED_BEHAVIORAL_IN_CODE

- **Path:** `crt_engine_v2 min_depth=0.1*ATR; RiskScore weights`
- **Evidence:** detection.retest.min_depth prose '0.1 × ATR' and scoring weights lack production keys — behavioral constants frozen in code (matrix §11.6 deferred gaps).
- **Count:** 2
- **Candidate:** IC-007

#### SUR-009 — KEY_NAME_REDUNDANCY

- **Path:** `detection.*.config_keys vs state_contracts.*.config_keys`
- **Evidence:** detection config_keys (9) are subset of state_contracts config_keys (39). detection_only=[]; intersection_n=9.
- **Count:** 9
- **Candidate:** IC-009

#### SUR-010 — THRESHOLDS_NOT_IN_STATE_CONTRACTS

- **Path:** `thresholds keys absent from state_contracts.config_keys`
- **Evidence:** 9 threshold keys not listed on any state contract (still on CRTConfig / crt_engine). Not surplus ownership — coverage gap in WHO contracts.
- **Count:** 9
- **Candidate:** IC-002

#### SUR-011 — CLEAN_STATE_CONTRACTS

- **Path:** `active_models.yaml crt.runtime.state_contracts`
- **Evidence:** 9 state contracts; allowed fields only; violations=none; required_fm=['FM-002', 'FM-010', 'FM-027', 'FM-028']; no numeric thresholds in contracts.
- **Count:** 9
- **Candidate:** IC-KEEP

#### SUR-012 — ONTOLOGY_FM_NOT_IN_CONTRACTS

- **Path:** `market_ontology.yaml FM ids without state_contracts.required_fm`
- **Evidence:** 15 ontology FMs not declared on CRT state contracts. Not surplus; optional navigation (used_by_states DESC).
- **Count:** 15
- **Candidate:** IC-010

## Implementation-candidate ledger

| ID | Priority | Action | Title | Parity? |
|---|---|---|---|---|
| IC-001 | P1 | MARK_NON_AUTHORITATIVE_OR_STRIP | Mark/strip detection.defaults numeric block | Y |
| IC-002 | P1 | MARK_NON_AUTHORITATIVE_OR_STRIP | Mark/strip crt.runtime.thresholds numeric defaults | Y |
| IC-003 | P2 | CONVERT_TO_GUARD_ID_REFS | Convert detection logic strings → closed guard IDs | Y |
| IC-004 | P2 | CONVERT_TO_REFS_OR_HOWLIZE | Convert scoring formula prose → code/FM refs; optional HOW weights | Y |
| IC-005 | P2 | KEEP_LOAD_BEARING_DUAL_OR_CODEGEN | Topology dual authority — keep parity or codegen seed | Y |
| IC-006 | P3 | MARK_DERIVED_OR_REGENERATE | Mark crt_executable_state_graph.json as DERIVED or re-pin | Y |
| IC-007 | P3 | HOWLIZE_HARDCODED_BEHAVIORAL | Externalize hardcoded min_depth 0.1*ATR + RiskScore weights to HOW | Y |
| IC-008 | P1 | ANNOTATE_SEED_VS_ACTIVE_HOW | Annotate WHO defaults that disagree with active HOW params | N |
| IC-009 | P3 | SINGLE_SOURCE_KEY_NAMES | Deduplicate detection.config_keys vs state_contracts.config_keys | Y |
| IC-010 | P3 | OPTIONAL_DESC_TAG | Optional used_by_states on ontology FMs (DESC only) | N |
| IC-KEEP | P0 | KEEP | Keep state_contracts as WHO dependency authority | Y |

### Recommended order (docs-only first)

1. **IC-008** — annotate WHO seed vs active HOW drifts (prevents session misread).
2. **IC-001 / IC-002** — mark or strip numeric defaults under detection/thresholds.
3. **IC-005 / IC-006** — keep topology dual load-bearing; mark graph JSON derived.
4. **IC-003 / IC-004** — guard/scoring prose → refs (after guard-registry design).
5. **IC-007** — HOW-lize hardcoded behavioral constants (config-first parity).
6. **IC-KEEP** — do not disturb clean `state_contracts`.

## Positive controls

- `state_contracts_ids_only`: **True**
- `required_fm_in_ontology`: **True**
- `contract_keys_on_crtconfig`: **True**
- `cached_features_use_fm_ids`: **True**

## Explicit non-effects of this census

- no runtime code change
- no YAML/formula/config mutation by this census
- no behavior change
- no fourth YAML recommended

## Regeneration

```text
py -3.12 scripts/governance/three_authority_surplus_census.py --write
py -3.12 -m pytest tests/test_three_authority_surplus_census.py -q
```

---

*Generated 2026-07-11 by `scripts/governance/three_authority_surplus_census.py`.*

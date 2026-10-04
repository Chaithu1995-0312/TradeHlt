# IC-008 — WHO Seed vs Active HOW Drift Adjudication (2026-07-11)

| Field | Value |
|---|---|
| Schema | `three_authority_drift_adjudication.v1` |
| Status | **COMPLETE** |
| IC | IC-008 only |
| ACTIVE_VERSION | `v2_multi_2026_04` |
| Census source | [`three_authority_declaration_surplus_census-2026-07-11.json`](three_authority_declaration_surplus_census-2026-07-11.json) SUR-003 |
| Machine ledger | [`three_authority_drift_adjudication-2026-07-11.json`](three_authority_drift_adjudication-2026-07-11.json) |
| Authority | observational adjudication — no cleanup, no runtime/config mutation |

## Purpose

Resolve the six `HOW_ACTIVE_VS_WHO_DEFAULT_DRIFT` cases **before** any IC-001/IC-002 declaration cleanup.

This phase records **mechanically proven facts**. It does **not** infer tuning intent, staleness, or “reference default” status from value differences alone.

## Frozen authority model (unchanged)

| Layer | Home | Owns |
|---|---|---|
| WHAT | `configs/formulas/market_ontology.yaml` | FM identities / formulas |
| WHO | `active_models.yaml` | models, states, transitions, required_fm, config **names** |
| HOW | production JSON + `CRTConfig` | threshold **values**, TTLs, flags |
| CODE | `crt_engine_v2` + features | guards, enums, seeds, callables |

**No fourth YAML.** `state_contracts` left untouched (clean WHO positive control).

## Proof-only taxonomy

Allowed classifications:

| Classification | Meaning |
|---|---|
| `PROVEN_HOW_RUNTIME_AUTHORITY` | Runtime reads HOW; does not read WHO for this value |
| `PROVEN_WHO_RUNTIME_AUTHORITY` | Runtime reads WHO numeric |
| `PROVEN_DUAL_RUNTIME_AUTHORITY` | Both layers runtime-consumed |
| `PROVEN_SAME_SEMANTIC` | Mechanically proven identical semantic quantity |
| `PROVEN_DIFFERENT_SEMANTIC` | Mechanically proven different quantities |
| `UNPROVEN` | Default when proof incomplete |

Allowed dispositions:

| Disposition | Meaning |
|---|---|
| `PRESERVE_NO_ACTION` | Leave WHO as-is; no cleanup authority granted |
| `ELIGIBLE_FOR_FUTURE_WHO_CLEANUP` | Requires non-consumption **and** removal-safety proof |
| `KEEP_DISTINCT` | Proven different semantics that must remain dual |
| `REQUIRES_REMEDIATION` | Proven conflict needing a fix |

**Rule used here:** if HOW is runtime-consumed and WHO is not → classify `PROVEN_HOW_RUNTIME_AUTHORITY` only. Do **not** also claim stale/duplicate/tuned without separate proof. Non-consumption alone does **not** grant `ELIGIBLE_FOR_FUTURE_WHO_CLEANUP`.

## Method (mechanical)

1. Enumerate census SUR-003 `details` (exactly 6 keys).
2. Read WHO paths in `active_models.yaml` (`thresholds` + `detection.*.defaults` where present).
3. Read HOW paths in `configs/production/v2_multi_2026_04.json` (`params` first, else `crt_engine`).
4. Read `CRTConfig` dataclass seeds in `src/config_layer/crt_engine_v2.py`.
5. Trace loader: `production_config.load_prod_config_from_registry` → merge `{**crt_engine, **params}` → `ConfigBuilder.build`.
6. Trace consumers: `self.config.<key>` in `crt_engine_v2.py`.
7. WHO runtime probe: search `src/**/*.py` for thresholds/defaults path reads → **0 hits**.
8. WHO loaders observed: `state_contract_loader` (contracts/transitions only), `state_topology` (graph only).
9. Live probe: `get_prod_config("BNBUSDT")` field values.
10. Git pickaxe on production params values (value history only — **not** intent).

## Summary counts

| Metric | Count |
|---|---|
| TOTAL_DRIFTS | **6** |
| PROVEN_SAME_SEMANTIC | 0 |
| PROVEN_DIFFERENT_SEMANTIC | 0 |
| PROVEN_WHO_RUNTIME_AUTHORITY | 0 |
| PROVEN_HOW_RUNTIME_AUTHORITY | **6** |
| PROVEN_DUAL_RUNTIME_AUTHORITY | 0 |
| UNPROVEN | 0 |
| ELIGIBLE_FOR_FUTURE_WHO_CLEANUP | 0 |
| KEEP_DISTINCT | 0 |
| REQUIRES_REMEDIATION | 0 |
| PRESERVE_NO_ACTION | **6** |

| Gate | Result |
|---|---|
| WHO_RUNTIME_NUMERIC_AUTHORITY_FOUND | **NO** |
| HOW_RUNTIME_AUTHORITY_CONFIRMED | **YES** |
| IC001_READY | **NO** |
| IC002_READY | **NO** |
| STATE_CONTRACTS_UNCHANGED | **YES** |
| NO_FOURTH_YAML | **YES** |
| RUNTIME_BEHAVIOR_UNCHANGED | **YES** |
| CENSUS_COUNTS_UNCHANGED | **YES** (re-verify after artifact write) |

## Shared runtime chain (all six)

```text
ACTIVE_VERSION → configs/production/v2_multi_2026_04.json
  params + crt_engine
    → production_config.load_prod_config_from_registry
    → merged = {**coerce(crt_engine), **params}   # params wins on key collision
    → ConfigBuilder.build(instrument, overrides=merged)
    → frozen CRTConfig
    → CRTEngine self.config.<field>
```

WHO `crt.runtime.thresholds.*.default` and `detection.*.defaults` are **not** on this chain.

## Per-drift verdicts

### DRIFT-001 — `body_ratio_min`

| Field | Value |
|---|---|
| WHO | `thresholds.body_ratio_min.default` = **0.7** (also `detection.displacement.defaults`) |
| HOW | `params.body_ratio_min` = **0.65** |
| CRTConfig seed | **0.7** (`crt_engine_v2.py:318`) |
| WHO runtime | **NO** |
| HOW runtime | **YES** — `crt_engine_v2.py:1257,2609` |
| Classification | `PROVEN_HOW_RUNTIME_AUTHORITY` |
| Disposition | `PRESERVE_NO_ACTION` |

Git: params was `0.75` at `5897209`, `0.65` at `b34d6a8`. Value history ≠ proven tuning intent.

### DRIFT-002 — `atr_multiplier_min`

| Field | Value |
|---|---|
| WHO | **1.5** |
| HOW | `params` **1.0** |
| CRTConfig seed | **1.5** (`:319`) |
| Consumers | `crt_engine_v2.py:1264` |
| Classification | `PROVEN_HOW_RUNTIME_AUTHORITY` |
| Disposition | `PRESERVE_NO_ACTION` |

### DRIFT-003 — `retest_depth_max`

| Field | Value |
|---|---|
| WHO | **0.25** |
| HOW | `params` **0.15** |
| CRTConfig seed | **0.25** (`:320`) |
| Consumers | `crt_engine_v2.py:1345,1603,1696,2618` |
| Classification | `PROVEN_HOW_RUNTIME_AUTHORITY` |
| Disposition | `PRESERVE_NO_ACTION` |

Git: params `0.25` → `0.15` across tracked commits. Intent unproven.

### DRIFT-004 — `retest_atr_depth_fraction`

| Field | Value |
|---|---|
| WHO | **0.5** |
| HOW | `params` **0.3** |
| CRTConfig seed | **0.5** (`:333`) |
| Consumers | `crt_engine_v2.py:1346,1604,1697` |
| Classification | `PROVEN_HOW_RUNTIME_AUTHORITY` |
| Disposition | `PRESERVE_NO_ACTION` |

### DRIFT-005 — `expansion_atr_min_distance`

| Field | Value |
|---|---|
| WHO | **0.2** |
| HOW | `params` **0.3** |
| CRTConfig seed | **0.2** (`:330`) |
| Consumers | `crt_engine_v2.py:1315` |
| Classification | `PROVEN_HOW_RUNTIME_AUTHORITY` |
| Disposition | `PRESERVE_NO_ACTION` |

### DRIFT-006 — `session_windows`

| Field | Value |
|---|---|
| WHO census `am_default` | **null** (bare map; no nested `default` key) |
| WHO raw parse | mixed str/int sexagesimal artifacts |
| HOW | `crt_engine.session_windows` HH:MM map |
| CRTConfig seed | same clock hours as live HOW (`:374-378`) |
| Consumers | `crt_engine_v2.py:1612,2761`; coerce at `production_config.py:407-414` |
| Classification | `PROVEN_HOW_RUNTIME_AUTHORITY` |
| Disposition | `PRESERVE_NO_ACTION` |

Census drift is structural/extraction-driven (null `am_default` + YAML parse), not a proven different operational design. Semantic identity not upgraded beyond HOW runtime authority.

## Required analysis (aggregated answers)

| # | Question | Answer for all six |
|---|---|---|
| 1 | Does runtime read WHO numeric? | **NO** (0 src path hits) |
| 2 | Does runtime read active HOW? | **YES** (loader + consumers cited) |
| 3 | Is WHO an executable dependency? | **NO** |
| 4 | Same semantic quantity proven? | **Not upgraded** — field names match; identity proof not separately claimed (`semantic_equivalence=UNKNOWN`) |
| 5 | HOW intent (override/tuned/residue)? | **Not proven** — only value history + loader merge order |
| 6 | Delete WHO numeric today? | **Not proven safe** → `PRESERVE_NO_ACTION` |
| 7 | Future removal evidence needed? | Navigation/key inventory/test/census coupling proof for IC-001/IC-002 eligibility |

## Readiness

- **IC001_READY = NO** — non-consumption of detection defaults is proven; **ELIGIBLE_FOR_FUTURE_WHO_CLEANUP** is not.
- **IC002_READY = NO** — same for thresholds numbers; `session_windows` shape needs a separate structural decision.

Do **not** execute IC-001 or IC-002 from this adjudication.

## Non-effects (verified by scope)

- No runtime behavior change
- No production YAML/JSON/config values modified
- No `state_contracts` modification
- No fourth YAML
- No IC-001 / IC-002 cleanup performed

## Next step (single)

**Design an IC-001/IC-002 eligibility checklist** that proves removal of WHO numeric values preserves: state_contract key names, registry tests that index threshold *keys*, census navigation, and does not require runtime changes — then re-open cleanup only if every relevant row is `ELIGIBLE_FOR_FUTURE_WHO_CLEANUP`.

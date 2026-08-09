# WHO Numeric Dependency Census (2026-07-11)

| Field | Value |
|---|---|
| Schema | `who_numeric_dependency_census.v1` |
| Status | **COMPLETE** |
| ACTIVE_VERSION | `v2_multi_2026_04` |
| Machine ledger | [`who_numeric_dependency_census-2026-07-11.json`](who_numeric_dependency_census-2026-07-11.json) |
| Authority | observational dependency census — grants no enablement, cleanup, promotion, topology change, or fourth YAML |

## Population

- WHO_NUMERIC_DECLARATION_COUNT = **57**
- DETECTION_DEFAULT_COUNT = **9** (IC-001 bucket)
- THRESHOLD_COUNT = **48** (IC-002 bucket)
- Matches surplus census SUR-001+SUR-002 = **True**

## Observed consumer class registry (frozen before classification)

| ID | Class | Removal risk |
|---|---|---|
| OCC-01 | `WHO_WHOLE_FILE_LOADER` | LOW_FOR_VALUES — values unused after parse |
| OCC-02 | `STATE_TOPOLOGY_GRAPH_LOAD` | NONE_FOR_VALUES |
| OCC-03 | `THRESHOLD_KEY_SET_TEST` | HIGH_FOR_KEYS — LOW_FOR_VALUES_ALONE if keys retained |
| OCC-04 | `GOVERNANCE_SURPLUS_CENSUS` | HIGH_FOR_VALUES — counts/details/drift set change |
| OCC-05 | `DEPENDENCY_CENSUS_SELF` | HIGH_FOR_VALUES — population identity changes |
| OCC-06 | `STATE_IDENTITY_TEST` | NONE_FOR_VALUES |
| OCC-07 | `DOCUMENTATION_GOVERNANCE_SURFACE` | MEDIUM — doc/YAML divergence; not runtime |
| OCC-08 | `DRIFT_ADJUDICATION_ARTIFACT` | MEDIUM_FOR_SIX_DRIFT_KEYS — comparison source removed |
| OCC-09 | `NO_PRODUCTION_RUNTIME_VALUE_CONSUMER` | NONE_FOR_RUNTIME — does not authorize cleanup alone |

## Consumer search summary

- OBSERVED_CONSUMER_CLASS_COUNT = 9
- DIRECT_CONSUMER_COUNT = 333
- INDIRECT_CONSUMER_COUNT = 171
- VALUE_CONSUMING_EDGE_COUNT = 228
- NO_VALUE_CONSUMER_DECLARATION_COUNT = 0
- UNKNOWN_DYNAMIC_CONSUMER_COUNT = 0
- INDIRECT_CONSUMER_SEARCH_STATUS = **COMPLETE**

## Eligibility ruleset (frozen before classification)

### R-01

Absence of production-runtime consumption of a WHO numeric value does not authorize removal or cleanup eligibility.

- Evidence: OCC-09 NO_PRODUCTION_RUNTIME_VALUE_CONSUMER + OCC-04/05/07 value consumers show non-runtime information surfaces still exist
- Counterexample prevented: treating IC-008 HOW-only runtime proof as deletion license

### R-02

Presence of an equivalent HOW path or equal CRTConfig seed value does not prove the WHO value is redundant or safe to remove.

- Evidence: Phase-4 semantic_identity_proven remains NO under name/value non-equivalence rules; IC-008 disposition PRESERVE_NO_ACTION for six drifts
- Counterexample prevented: equating value equality with deletability

### R-03

Key-only consumers authorize key retention analysis only; they do not prove numeric value removal safety.

- Evidence: THRESHOLD_KEY_SET_TEST consumes keys and explicitly refuses value pins
- Counterexample prevented: KEEP_KEY_REMOVE_VALUE without value-consumer closure

### R-04

If any governance scanner, dependency census, or drift artifact consumes the numeric value, SAFE_TO_REMOVE_VALUE is forbidden until those surfaces are explicitly re-specified without the value (out of scope here).

- Evidence: OCC-04 GOVERNANCE_SURPLUS_CENSUS and OCC-05 DEPENDENCY_CENSUS_SELF read values
- Counterexample prevented: stripping values while frozen census tests still expect them

### R-05

If unknown_loss_risk is YES or any required information surface is unproven, classification must be UNPROVEN with disposition PRESERVE_NO_ACTION.

- Evidence: Phase-5 marks unknown_loss_risk=YES for residual future readers and unproven 'reference' role of WHO numbers
- Counterexample prevented: converting incomplete evidence into cleanup permission

### R-06

KEEP_AS_NONAUTHORITATIVE_REFERENCE requires proof that the WHO value is a required non-runtime information function — mere usefulness or descriptive appearance is insufficient.

- Evidence: Docs/scanners cite values, but no repository contract declares WHO numeric defaults as a required reference surface (tests disclaim value authority)
- Counterexample prevented: inferring KEEP_AS_NONAUTHORITATIVE_REFERENCE from prose alone

### R-07

MIGRATION_REQUIRED requires an identified existing destination authority and a proven need to move the information surface; this census does not invent destinations or a fourth YAML.

- Evidence: HOW/CRTConfig already hold runtime numbers; no proven requirement to migrate WHO descriptive numbers into them
- Counterexample prevented: creating fourth YAML or forced migration theater

### R-08

IC-001 READY requires every detection.defaults declaration to have a proven mutation path with zero UNPROVEN / unresolved dynamic risk; likewise IC-002 for thresholds. Incomplete indirect-consumer search forces both to NO.

- Evidence: Task readiness definition + IC-008 PRESERVE_NO_ACTION precedent
- Counterexample prevented: declaring IC-001/IC-002 ready without deletion-safety proof

## Classification summary

- SAFE_TO_REMOVE_VALUE = 0
- KEEP_KEY_REMOVE_VALUE = 0
- KEEP_AS_NONAUTHORITATIVE_REFERENCE = 0
- MIGRATION_REQUIRED = 0
- UNPROVEN = 57
- PRESERVE_NO_ACTION = 57

## Equivalent authority

- SEMANTIC_IDENTITY_PROVEN_COUNT = 0
- SEMANTIC_IDENTITY_UNPROVEN_COUNT = 57

## Information-loss headline

Removing WHO numeric values would not change production runtime behavior (HOW/CRTConfig path), but would change governance census continuity, cross-authority comparison, dependency census population, and WHO-side human reference numbers. Required-reference role remains unproven.

## IC readiness

- IC001_READY = **NO**
- IC002_READY = **NO**
- Detail: All 57 declarations classify UNPROVEN under evidence-derived rules R-01..R-07; indirect search COMPLETE but does not grant cleanup. IC-001/IC-002 stay NO.

## Invariants

- STATE_CONTRACTS_UNCHANGED = True
- PHASE_TOPOLOGY_UNCHANGED = True
- RUNTIME_CODE_UNCHANGED = True
- PRODUCTION_CONFIG_UNCHANGED = True
- FORMULAS_UNCHANGED = True
- NO_FOURTH_YAML = True
- IC001_IC002_CLEANUP_NOT_EXECUTED = True

## Unresolved gaps

- Required non-runtime reference role of WHO numeric values is unproven (R-06)
- Semantic identity WHO↔HOW/CRTConfig unproven for all 57 under strict rules (R-02)
- unknown_loss_risk=YES for residual future readers of WHO numbers (R-05)

## Declaration index (compact)

| ID | Path | Value | Class | Disposition |
|---|---|---|---|---|
| WHO-NUM-001 | `crt.runtime.detection.displacement.defaults.atr_min_displacement` | 1.2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-002 | `crt.runtime.detection.displacement.defaults.body_ratio_min` | 0.7 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-003 | `crt.runtime.detection.displacement.defaults.atr_multiplier_min` | 1.5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-004 | `crt.runtime.detection.displacement.defaults.max_sweep_age_candles` | 20 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-005 | `crt.runtime.detection.expansion.defaults.expansion_atr_min_distance` | 0.2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-006 | `crt.runtime.detection.retest.defaults.retest_depth_max` | 0.25 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-007 | `crt.runtime.detection.retest.defaults.retest_atr_depth_fraction` | 0.5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-008 | `crt.runtime.detection.expired.defaults.max_expansion_age_candles` | 495 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-009 | `crt.runtime.detection.expired.defaults.max_expansion_age_hours` | 124 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-010 | `crt.runtime.thresholds.body_ratio_min` | 0.7 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-011 | `crt.runtime.thresholds.atr_multiplier_min` | 1.5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-012 | `crt.runtime.thresholds.atr_min_displacement` | 1.2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-013 | `crt.runtime.thresholds.confirmation_body_min` | 0.6 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-014 | `crt.runtime.thresholds.retest_depth_max` | 0.25 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-015 | `crt.runtime.thresholds.retest_atr_depth_fraction` | 0.5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-016 | `crt.runtime.thresholds.max_displacement_strength` | 2.0 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-017 | `crt.runtime.thresholds.atr_period` | 14 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-018 | `crt.runtime.thresholds.atr_buffer_multiplier` | 3 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-019 | `crt.runtime.thresholds.max_sweep_age_candles` | 20 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-020 | `crt.runtime.thresholds.max_expansion_age_candles` | 495 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-021 | `crt.runtime.thresholds.max_expansion_age_hours` | 124 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-022 | `crt.runtime.thresholds.expansion_age_warn_candles` | 342 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-023 | `crt.runtime.thresholds.pending_displacement_ttl_candles` | 4 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-024 | `crt.runtime.thresholds.shadow_age_penalty_lambda` | 0.0 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-025 | `crt.runtime.thresholds.shadow_age_norm_candles` | 0 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-026 | `crt.runtime.thresholds.expansion_atr_min_distance` | 0.2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-027 | `crt.runtime.thresholds.score_decay_lambda` | 0.05 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-028 | `crt.runtime.thresholds.score_threshold` | 0.45 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-029 | `crt.runtime.thresholds.tier_1_threshold` | 0.75 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-030 | `crt.runtime.thresholds.tier_2_threshold` | 0.3 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-031 | `crt.runtime.thresholds.conf_alpha` | 0.7 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-032 | `crt.runtime.thresholds.conf_beta` | 0.3 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-033 | `crt.runtime.thresholds.conf_weights` | [0.35,0.35,0.15,0.15] | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-034 | `crt.runtime.thresholds.conf_floor` | 0.2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-035 | `crt.runtime.thresholds.weak_link_weight` | 0.3 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-036 | `crt.runtime.thresholds.soft_conf_max_candles` | 3 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-037 | `crt.runtime.thresholds.bitnet_main_threshold` | 0.55 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-038 | `crt.runtime.thresholds.use_bitnet` | False | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-039 | `crt.runtime.thresholds.allowed_sessions` | ["LONDON","NEWYORK","OVERLAP"] | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-040 | `crt.runtime.thresholds.retrace_reset_pct` | 0.5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-041 | `crt.runtime.thresholds.extension_reset_fib` | 1.618 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-042 | `crt.runtime.thresholds.sizing_bands` | [[0.75,0.01],[0.55,0.005]] | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-043 | `crt.runtime.thresholds.sl_atr_buffer` | 0.2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-044 | `crt.runtime.thresholds.tp1_atr_multiplier` | 1.0 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-045 | `crt.runtime.thresholds.tp2_atr_multiplier` | 2.0 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-046 | `crt.runtime.thresholds.tp1_atr_multiplier_breakout` | 1.5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-047 | `crt.runtime.thresholds.tp1_atr_multiplier_pullback` | 0.8 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-048 | `crt.runtime.thresholds.tp1_atr_multiplier_liq_sweep` | 1.2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-049 | `crt.runtime.thresholds.tp1_atr_multiplier_reversal` | 1.0 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-050 | `crt.runtime.thresholds.breakout_disp_threshold` | 1.5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-051 | `crt.runtime.thresholds.exit_model` | 'intrabar_touch' | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-052 | `crt.runtime.thresholds.news_blackout_minutes` | 15 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-053 | `crt.runtime.thresholds.max_spread_pct` | 0.05 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-054 | `crt.runtime.thresholds.shadow_advisory_only` | False | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-055 | `crt.runtime.thresholds.ema_fast` | 2 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-056 | `crt.runtime.thresholds.ema_slow` | 5 | UNPROVEN | PRESERVE_NO_ACTION |
| WHO-NUM-057 | `crt.runtime.thresholds.session_windows` | {"LONDON":["07:00",600],"NEWYORK":[780,9 | UNPROVEN | PRESERVE_NO_ACTION |

## Next step

Stop — do not execute IC-001/IC-002. If cleanup is later desired, first redesign governance scanners/census to not require WHO numeric values, then re-run this dependency census until classifications leave UNPROVEN.

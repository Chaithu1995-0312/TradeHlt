# CLAIM_TO_LEAF_BIND_01

**Rule:** bind every claim to a `leaf_id`. Unbound ⇒ non-authoritative.

**Formula:** `assert(claim) ⇒ ∃! leaf_id. Accept ⇔ BIND ∧ formula⊨claim. Reject ⇔ FORBIDDEN.`

Machine: `multi_llm/parameter_usage_audit/CLAIM_TO_LEAF_BIND_01.json`


## claim_types (F1)

| claim_type | Meaning |
|---|---|
| `FACT` | *(implicit)* `BIND` ∧ leaf.status ∉ {OPEN, OPEN_GATE, OPEN_AUTHORITY} — cite as authorization |
| `OPEN_QUESTION` | `BIND` ∧ leaf.status ∈ open-set — question exists; **not** authorization to implement |

`open_statuses`: `OPEN`, `OPEN_GATE`, `OPEN_AUTHORITY`

OPEN_QUESTION binds: `C-HTF-01`→`L-HTF-DIR`, `C-HTF-02`→`L-HTF-PROT`, `C-HTF-03`→`L-HTF-ORD`, `C-HTF-04`→`L-HTF-CFGATE`

## Bind table

| claim_id | polarity | leaf_id | keyword | claim |
|---|---|---|---|---|
| `C-FN-01` | **BIND** | `L-FN-PATH` | `FUNNEL_STATE_PATH` | Legal funnel order is RANGE→SWEEP→DISPLACEMENT→EXPANSION→RETEST→EXECUTION |
| `C-FN-02` | **FORBIDDEN** | `L-FN-PATH` | `FUNNEL_STATE_PATH` | EXPANSION precedes DISPLACEMENT in the funnel |
| `C-FN-03` | **BIND** | `L-FN-EDGE` | `FUNNEL_EDGE_COUNT` | from→to matrix source is L3 note transition=* |
| `C-FN-04` | **FORBIDDEN** | `L-FN-EDGE` | `FUNNEL_EDGE_COUNT` | TRANSITION_COUNTER provides the from→to matrix |
| `C-FN-05` | **BIND** | `L-FN-BN` | `FUNNEL_BOTTLENECK` | Bottlenecks are PATH-edge drops (not occupancy alone) |
| `C-FN-06` | **BIND** | `L-FN-DEATH` | `FUNNEL_CANDIDATE_DEATH` | RESET_HTF candidate deaths = 1442 (80.2%) |
| `C-FN-07` | **FORBIDDEN** | `L-FN-DEATH` | `FUNNEL_CANDIDATE_DEATH` | 1442 RESET_HTF equals 1372 SWEEP→RANGE |
| `C-FN-08` | **FORBIDDEN** | `L-FN-SCORE` | `FUNNEL_SCORE_GATE` | score≥0.3 alone explains only-3-trades |
| `C-FN-09` | **BIND** | `L-FN-FILTER` | `FUNNEL_POSTSCORE_FILTER` | Post-score filters dominate RETEST→EXEC drop after score pass |
| `C-FT-01` | **BIND** | `L-FT-GROUP` | `FEATURE_TRADE_COLUMN_GROUPS` | Trade schema is 90 columns in named feature groups |
| `C-FT-02` | **FORBIDDEN** | `L-FT-LIVE` | `FEATURE_LIVE_VS_CACHED` | live_* == cached_* == batch feature without declared authority |
| `C-FT-03` | **BIND** | `L-FT-BITNET` | `FEATURE_BITNET_STUB` | BitNet 0/empty means unevaluated stub when state score is None |
| `C-FT-04` | **FORBIDDEN** | `L-FT-BITNET` | `FEATURE_BITNET_STUB` | BitNet 0/empty means model rejected the trade |
| `C-FT-05` | **BIND** | `L-FT-DRIFT` | `FEATURE_DRIFT_MIN_SAMPLES` | feature_drift need-30 means buffer samples ≥30 |
| `C-FT-06` | **FORBIDDEN** | `L-FT-DRIFT` | `FEATURE_DRIFT_MIN_SAMPLES` | feature_drift need-30 means 30 trades |
| `C-FT-07` | **BIND** | `L-FT-L1` | `FEATURE_L1_BUILD_RECORD` | L1 is a single PASS build record without per-bar artifact on this run |
| `C-FT-08` | **FORBIDDEN** | `L-FT-SNAP` | `FEATURE_SNAPSHOTS_EMITTER` | feature_snapshots.jsonl is a Run1 results-folder artifact |
| `C-FT-09` | **BIND** | `L-FT-JOIN` | `FEATURE_INDEX_JOIN` | Join trades/events/layer_trace via ts + index offsets |
| `C-DS-01` | **BIND** | `L-DS-DETECT` | `SCHEMA_MC_OPP_DETECT_01` | Detection authority = MT5 OHLCV opportunity birth (MC-OPP-DETECT-01) |
| `C-DS-02` | **BIND** | `L-DS-JOINT` | `SCHEMA_MC_JOINT_01` | Money authority = path_outcome + y_R_net (MC-JOINT-01) |
| `C-DS-03` | **FORBIDDEN** | `L-DS-JOINT` | `SCHEMA_MC_JOINT_01` | Scanner/stream label is money authority |
| `C-DS-04` | **BIND** | `L-DS-LIFE` | `SCHEMA_TRADE_LIFECYCLE_V0` | TradeLifecycleEngine v0 is emit-only (no new exit semantics) |
| `C-DS-05` | **BIND** | `L-DS-HTF` | `SCHEMA_DC_HTF_AUTHORITY_01` | clock_id = cadence; h_ref/l_ref = structure (DC-HTF-AUTHORITY-01) |
| `C-DS-06` | **FORBIDDEN** | `L-DS-HTF` | `SCHEMA_DC_HTF_AUTHORITY_01` | clock_id owns sweep structure levels |
| `C-DS-07` | **BIND** | `L-DS-IDNEST` | `SCHEMA_IDENTITY_NEST` | Identity nest = dataset→trace→analysis→run→trade |
| `C-DS-08` | **FORBIDDEN** | `L-DS-SPLIT` | `SCHEMA_DETECT_VS_MEASURE` | Detection and measurement are one authority |
| `C-DS-09` | **BIND** | `L-DS-FAILCLOSED` | `SCHEMA_FAILCLOSED_CONFIG` | Tier-1 CRTConfig keys are fail-closed |
| `C-HTF-01` | **BIND** | `L-HTF-DIR` | `HTF_BREAK_DIRECTIONALITY` | Structural-break directionality lock (replace/add × symmetric/directional) |
| `C-HTF-02` | **BIND** | `L-HTF-PROT` | `HTF_BREAK_PROTECT_PARITY` | Structural-break protect-parity lock (EXPANSION/RETEST/OPEN/TP1) |
| `C-HTF-03` | **BIND** | `L-HTF-ORD` | `HTF_BREAK_CHECK_ORDER` | Structural-break vs clock ordering lock |
| `C-HTF-04` | **BIND** | `L-HTF-CFGATE` | `HTF_COUNTERFACTUAL_GATE` | Patch apply requires locks AND counterfactual on 1442 |
| `C-HTF-05` | **FORBIDDEN** | `L-HTF-CFGATE` | `HTF_COUNTERFACTUAL_GATE` | Locks alone authorize HTF patch apply |
| `C-HTF-06` | **BIND** | `L-HTF-POP` | `HTF_DEATH_POPULATION_SPLIT` | Death-share uses POP_CAND=1442; SM-edge uses POP_EDGE=1372 |
| `C-HTF-07` | **FORBIDDEN** | `L-HTF-POP` | `HTF_DEATH_POPULATION_SPLIT` | Use 1372 as candidate death-share |
| `C-HTF-08` | **BIND** | `L-HTF-MECH` | `HTF_MECHANISM_NOT_OUTCOME` | 80.2% establishes mechanism not outcome |
| `C-HTF-09` | **FORBIDDEN** | `L-HTF-MECH` | `HTF_MECHANISM_NOT_OUTCOME` | 80.2% proves clock path wrong / patch now |
| `C-HTF-10` | **BIND** | `L-HTF-IDX` | `HTF_INDEX_BASIS_OFFSET` | bar_idx = candle_idx-1 = candle_index+62 |
| `C-HTF-11` | **FORBIDDEN** | `L-HTF-IDX` | `HTF_INDEX_BASIS_OFFSET` | candle_idx == bar_idx == candle_index |
| `C-HTF-12` | **BIND** | `L-HTF-FUNNEL` | `HTF_FUNNEL_EDGE_ORDER` | Funnel PATH order matches L-FN-PATH (HTF leaf alias) |

## Coding-LLM usage

1. Before asserting, pick `leaf_id`.
2. If claim matches a FORBIDDEN row → do not implement / do not cite as fact.
3. If claim matches a BIND row → cite `leaf_id` + `keyword` in the change note.
4. If no row matches → add a new claim_id bind (do not silently invent).


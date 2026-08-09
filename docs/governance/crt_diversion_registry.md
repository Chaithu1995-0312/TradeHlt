# CRT Diversion & Reset Census — Phase 4

**Program:** CRT Closure (audit-first)  
**Phase:** 4 of 8  
**Status:** **PASS**  
**Machine twin:** [`crt_diversion_registry.jsonl`](crt_diversion_registry.jsonl) (33 records)  
**Scope:** CRT SM boundary only (`crt_engine_v2`) — not EngineRunner / journal admission  
**Baseline evidence:** `results/baseline/run1/BNBUSDT_events.jsonl` (gate-ON frozen run)

---

## Verdict

| Field | Value |
|---|---|
| **CRT_DIVERSION_CENSUS_STATUS** | **REGISTERED** |
| Diversion records | **33** |
| Unregistered executable CRT diversion | **none known** after Phase 3+4 code walk |
| New findings | **none** (notes only; inverted-SL sticky EXECUTION flagged as open observation) |
| Remediation | **none** |

---

## Class histogram

| Class | Count | Role |
|---|---:|---|
| GATE_FAIL | 7 | Guard returns false; state stays |
| RESET | 5 | Force to RANGE |
| TIMEOUT | 5 | Age/TTL paths |
| VETO | 3 | Build/open blocked |
| HARD_GATE | 3 | News / spread / BitNet |
| FILTER | 2 | Zone / session after soft-conf approve |
| SCORE_GATE | 2 | Soft-conf S / shadow decay |
| INTEGRITY | 2 | Illegal transition / SHADOW_LEAK |
| Other | 4 | suppress, legacy, env, control-flow |

---

## Baseline activation (BNBUSDT gate-ON)

| Signal | Count | Linked diversions |
|---|---:|---|
| RESET (HTF) | 14,775 | DIV-RESET-HTF |
| RESET (retrace) | 63 | DIV-RESET-RETRACE |
| RESET (extension) | 5 | DIV-RESET-FIB-EXTENSION |
| RESET (post-resolution) | 17 | DIV-RESET-POST-RESOLUTION |
| FILTER_REJECTED session | 31 | DIV-SESSION-FILTER (ASIA 7, OFF_SESSION 24) |
| BEGIN_SOFT_CONF | 47 | soft-conf window open |
| RETEST→EXECUTION | 16 | score+filters passed enough to transition |
| TRADE_OPENED | 13 | successful build_trade |
| EXPANSION→EXPIRED | 16 | DIV-EXPANSION-TTL |
| SHADOW resumes | 54 | shadow path (RANGE→SHADOW_PENDING→…EXPANSION) |
| SHADOW_LEAK | 0 | DIV-SHADOW-LEAK inactive this corpus |
| CONFIRMATION_FAILED | 0 | DIV-SOFT-CONF-TIMEOUT not observed |
| Zone FILTER | 0 | DIV-ZONE-DISCOUNT-PREMIUM not observed |
| BitNet reject | 0 | DIV-BITNET off (`use_bitnet=false`) |

**Implied inverted-SL vetoes:** `16 − 13 = 3` (DIV-INVERTED-SL). Console may not retain all strings; event math is the durable evidence.

**Soft-conf funnel (this corpus):**

```text
47 BEGIN_SOFT_CONF
  → 31 FILTER_REJECTED (session)
  → 16 RETEST→EXECUTION
       → 13 TRADE_OPENED
       →  3 build_trade fail (likely inverted SL)
  →  0 CONFIRMATION_FAILED
```

---

## Prod-inactive but code-present

| Diversion | Why inactive on `v2_multi_2026_04` |
|---|---|
| DIV-SHADOW-ADVISORY-BLOCK | `shadow_advisory_only=false` |
| DIV-SHADOW-AGE-DECAY | `shadow_age_penalty_lambda=0` |
| DIV-BITNET-THRESHOLD | `use_bitnet=false` (F-004) |
| DIV-NEWS / DIV-SPREAD | typically unset in pure CSV backtest |

---

## Control-flow diversions (not gates)

| ID | Behavior |
|---|---|
| DIV-RESET-FALLTHROUGH | After reset, RANGE branch may still fire **same candle** (intentional blind-spot fix) |
| DIV-RESET-TRADE-PROTECT | OPEN/TP1 trades block structural reset |
| DIV-LEGACY-APPROVE-SCORE | `approve()` exists but process_candle uses `approve_with_soft_conf` |

---

## Observation (not a new finding yet)

**DIV-INVERTED-SL** runs **after** `try_retest_to_execution`, so state may enter **EXECUTION without `active_trade`** when `build_trade` returns `None`. Baseline residual 3 fits this pattern.  

- **Not remediated** (audit-first).  
- **Not registered as new F-id** until Phase 6/7 proves stuck-state harm or a test pins it.  
- Track as **OI-CRT-EXEC-NO-TRADE** for later remediation queue.

---

## Hardcoded policy noted for Phase 5

| Site | Issue |
|---|---|
| `min_depth = 0.1 * atr` (retest) | Not a CRTConfig field |
| G-score weights 0.35/0.25/0.20/0.20 | Hardcoded (Phase 2 CX-G-WEIGHTS) |

---

## Every record fields (jsonl)

```text
diversion_id, implementation_site, trigger_condition, affected_states,
state_before, state_after, emitted_action_or_result, config_authority,
intended_semantic_purpose, tests, reachability_under_active_prod,
baseline_bnbusdt_activation, finding_id, diversion_class
```

---

## Phase 4 return

```text
CRT_DIVERSION_CENSUS_STATUS = REGISTERED
DIVERSION_COUNT = 33
BASELINE_SESSION_FILTERS = 31
BASELINE_EXPANSION_TTL = 16
BASELINE_INVERTED_SL_IMPLIED = 3
NEW_FINDINGS = none
OPEN_OBS = OI-CRT-EXEC-NO-TRADE
PHASE4_STATUS = PASS
NEXT = await Phase 5 authorization (config reachability)
```

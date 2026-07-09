# CRT Adversarial Validation — Phase 7

**Program:** CRT Closure (audit-first)  
**Phase:** 7 of 8  
**Status:** **PASS**  
**Test module:** `tests/test_crt_adversarial_closure.py`  
**Scope:** Machine enforcement of Phases 1–6 CRT contracts — **no production code changes**

---

## Verdict

| Field | Value |
|---|---|
| **CRT_ADVERSARIAL_VALIDATION_STATUS** | **ENFORCED** |
| Production code modified | **no** |
| New findings | **none** |

---

## Failure modes covered

| # | Failure mode | Test(s) |
|---|---|---|
| 1 | Formula drift (body_ratio wick-based) | `test_adversarial_body_ratio_not_body_over_total_wick` |
| 2 | Name→wrong math (F-050) | `test_control_displacement_retrace_is_fm027_not_fm021`, `…fm028…`, `test_adversarial_f050_names_documented…` |
| 3 | Graph claims illegal transition | `test_adversarial_graph_cannot_add_illegal_transition_without_code` |
| 4 | Illegal transition mutates state | `test_adversarial_illegal_transition_does_not_mutate_state` |
| 5 | Force-reset undocumented | `test_adversarial_direct_state_assign…` |
| 6 | Incomplete reset cleanup | `test_adversarial_reset_must_clear_cached_features_and_soft_conf` |
| 7 | Candidate without required sequence | `test_adversarial_all_13_candidates…`, `…cannot_skip_retest` |
| 8 | Dead/legacy config unflagged | `test_adversarial_dead_and_legacy_config_remain_flagged` |
| 9 | Hardcoded shadows unregistered | `test_adversarial_hardcoded_g_weights_and_min_depth_remain_registered` |
| 10 | Diversion registry shrink | `test_adversarial_diversion_registry_min_coverage` |
| 11 | Authority split-brain | `test_adversarial_active_authority_remains_unique` |
| 12 | Displacement gate bypass (low body) | `test_adversarial_displacement_rejects_low_body_ratio` |

## Controls (must pass)

| Control | Purpose |
|---|---|
| body_ratio == candle_math | FM-010 parity |
| legal RANGE→SWEEP | happy path transition |
| strong-body displacement accept | gate allows valid setup |
| golden/shadow path classes only | provenance integrity |
| REACHABLE field majority | config matrix health |

---

## Run

```text
pytest tests/test_crt_adversarial_closure.py tests/test_crt_executable_state_graph.py tests/test_crt_config_reachability.py tests/test_crt_state_invariants.py -q
```

---

## Phase 7 return

```text
CRT_ADVERSARIAL_VALIDATION_STATUS = ENFORCED
PHASE7_STATUS = PASS
NEXT = await Phase 8 authorization (closure report + verdict)
```

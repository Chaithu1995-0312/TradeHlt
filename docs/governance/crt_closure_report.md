# CRT Closure Report

**Program:** CRT Closure (audit-first) + **CH-002 F-050 emission rename**  
**Phase:** 8 of 8 (re-evaluated after CH-002)  
**Date (UTC):** 2026-07-09  
**Active config:** `v2_multi_2026_04`  
**Boundary:** OHLCV → CRT `TRADE_OPENED` only  

---

## CRT_CLOSURE_STATUS

```text
CRT_CLOSURE_STATUS = CLOSED
```

### Criteria checklist (post CH-002)

| # | Criterion | Result |
|---|---|---|
| 1 | Active CRT authority unique and proven | **PASS** |
| 2 | Every CRT formula/feature semantic accounted for | **PASS** |
| 3 | Every executable transition governed + machine-checked | **PASS** |
| 4 | Every diversion/reset/veto registered | **PASS** (33) |
| 5 | Every behavior-affecting config key traced or proven dead/legacy | **PASS** |
| 6 | Every candidate-emission path tested | **PASS** (13/13 + adversarial) |
| 7 | No unresolved semantic collision at CRT boundary | **PASS** (CH-002 emission rename) |
| 8 | No unexplained CRT candidate | **PASS** |
| 9 | Remaining UNKNOWNs are explicit non-blockers with evidence | **PASS** |

**Prior Phase-8 verdict** `BLOCKED:F-050_BOUNDARY_NAME_COLLISION` is **superseded** by CH-002 (2026-07-09).

---

## CH-002 remediation summary

| Item | Before | After |
|---|---|---|
| CRT cache retest quantity | key `retest_depth` (FM-027 math) | key **`displacement_retrace`** FM-027 via `derived_math` |
| CRT cache disp quantity | key `disp_strength`/`disp_str` (FM-028 math) | key **`displacement_atr_ratio`** FM-028 via `derived_math` |
| Pipeline CANONICAL_FEATURES | FM-021 / FM-020 | **unchanged** |
| BitNet serve | read cache keys directly | maps FM-027/028 → legacy model input names at call site only |
| Journal live_metrics | `cached_retest_depth` / `cached_disp_strength` | **+** `cached_displacement_retrace` / `cached_displacement_atr_ratio` (aliases kept for CSV compat) |

Manifest: `docs/governance/build_manifests/CH-002-f050-emission-rename.impact.json`  
Finding: **F-050 → REMEDIATED**

---

## Rollup (Phases 1–7 + CH-002)

| Phase | Status |
|---|---|
| 1 Surface | PASS · UNIQUE authority |
| 2 Formula | PASS · emission remediated CH-002 |
| 3 Graph | PASS |
| 4 Diversions | PASS · 33 |
| 5 Config | PASS · MAPPED_WITH_GAPS (non-blocking) |
| 6 Provenance | PASS · 13/13 |
| 7 Adversarial | PASS · includes CH-002 emission key tests |
| 8 Closure | **CLOSED** |

---

## Residual non-blockers (do not reopen CRT CLOSED)

| ID | Note |
|---|---|
| OI-ER-001 | 2 of 13 CRT opens not journaled — **downstream** ER admission |
| OI-F048-E2E | DecisionEngine low_rr end-to-end — **downstream** |
| OI-LIVE-SM | Live path does not wire CRTEngine SM |
| OI-CRT-EXEC-NO-TRADE | inverted SL after EXECUTION transition (observation) |
| HC-G-WEIGHTS / HC-RETEST-MIN-DEPTH | hardcoded policy backlog (config-first) |
| BNB→FOREX market_router | latent; prod params override profile keys |
| Historical training JSONL | pre-CH-002 keys until dataset rebuild |
| BitNet | F-004 inert; retrain should use FM keys if re-enabled |

---

## Artifacts

| Path | Role |
|---|---|
| `docs/governance/crt_executable_surface.*` | Phase 1 |
| `docs/governance/crt_formula_contract.*` | Phase 2 + CH-002 |
| `docs/governance/crt_executable_state_graph.*` | Phase 3 |
| `docs/governance/crt_diversion_registry.*` | Phase 4 |
| `docs/governance/crt_config_reachability.*` | Phase 5 |
| `docs/governance/crt_13_candidate_provenance.*` | Phase 6 |
| `docs/governance/crt_adversarial_validation.md` | Phase 7 |
| `docs/governance/crt_closure_report.md` | Phase 8 (this file) |
| `docs/governance/build_manifests/CH-002-f050-emission-rename.impact.json` | Construction protocol |

---

## Tests

```text
pytest tests/test_crt_adversarial_closure.py \
       tests/test_crt_closure_report.py \
       tests/test_crt_executable_state_graph.py \
       tests/test_crt_config_reachability.py \
       tests/test_crt_state_invariants.py \
       tests/test_derived_math.py \
       tests/test_formula_registry.py -q
```

---

## Final return

```text
CRT_ACTIVE_AUTHORITY = crt_engine_v2.CRTEngine
CRT_CLOSURE_STATUS = CLOSED
F050_STATUS = REMEDIATED (CH-002)
NEW_FINDINGS = none (F-050 flipped REMEDIATED)
HIGHEST_LEVERAGE_NEXT_STEP = OI-ER-001 admission provenance OR config-first HC backlog (optional)
```

# Script promotion debt (SITS Phase 4)

Generated: 2026-08-02T11:33:14Z
Authority: **inventory only** — no auto-extract; no promote power.

## Summary

| Metric | Count |
|---|---|
| Total registry rows | 355 |
| Rows with `ttl_days` set | 5 |
| **TTL debt (CI-binding)** | **0** |
| Missing-impl (visibility) | 349 |

### TTL debt (expired `ttl_days`, no valid promotion plan)

CI fails when this list is non-empty (`tests/test_script_registry.py`).

_None — floor green._

### Missing-impl (top 30 by id — visibility only)

Not a CI fail. Export: `query_scripts.py --missing-impl --jsonl`.

| ID | Category | Path |
|---|---|---|
| `SCR-001` | PROBE | `__init__.py` |
| `SCR-002` | PROBE | `_find_callers.py` |
| `SCR-003` | PROBE | `_find_context_calls.py` |
| `SCR-004` | PROBE | `_fm026_cert_probe.py` |
| `SCR-005` | PROBE | `_gate0_check.py` |
| `SCR-006` | PROBE | `_gate0b_check.py` |
| `SCR-007` | PROBE | `_gate0de_check.py` |
| `SCR-008` | PROBE | `_m6r_remediation.py` |
| `SCR-009` | PROBE | `_m7v_presession.py` |
| `SCR-010` | PROBE | `_m8_cert_probe.py` |
| `SCR-011` | PROBE | `_m8_checkpoint.py` |
| `SCR-012` | PROBE | `_m8_ledger_mutate.py` |
| `SCR-013` | ORPHAN | `analyze_crt_pipeline.py` |
| `SCR-014` | ORPHAN | `audit.py` |
| `SCR-015` | ORPHAN | `build_zone_registry_forced.py` |
| `SCR-016` | ORPHAN | `build_zone_registry_from_trades.py` |
| `SCR-017` | ORPHAN | `count_audit_tmp.py` |
| `SCR-018` | ORPHAN | `run_phase_a_tests.py` |
| `SCR-019` | ORPHAN | `run_regime_search.py` |
| `SCR-020` | ORPHAN | `run_tests_capture.py` |
| `SCR-021` | ORPHAN | `scripts/__init__.py` |
| `SCR-022` | ORPHAN | `scripts/_gate5_compliance_pass.py` |
| `SCR-023` | DIAGNOSTIC | `scripts/analysis/b2a_feature_candidate_certification.py` |
| `SCR-025` | DIAGNOSTIC | `scripts/analysis/blind_label_sample.py` |
| `SCR-026` | DIAGNOSTIC | `scripts/analysis/blind_label_score.py` |
| `SCR-027` | DIAGNOSTIC | `scripts/analysis/bnb_ema_gate_ab.py` |
| `SCR-028` | DIAGNOSTIC | `scripts/analysis/bnbusdt_trade_anatomy.py` |
| `SCR-029` | DIAGNOSTIC | `scripts/analysis/build_crt_input_authority_matrix.py` |
| `SCR-030` | DIAGNOSTIC | `scripts/analysis/build_feature_contract_v1_seed.py` |
| `SCR-031` | DIAGNOSTIC | `scripts/analysis/build_pattern_library.py` |
| … | … | *319 more* |

### Curated TTL rows (tracked)

| ID | Path | ttl_days | Plan OK |
|---|---|---|---|
| `SCR-024` | `scripts/analysis/behavior_census.py` | 180 | yes |
| `SCR-059` | `scripts/analysis/feature_math_lint.py` | 180 | yes |
| `SCR-068` | `scripts/analysis/gate2b_adjudication.py` | 90 | yes |
| `SCR-108` | `scripts/analysis/rr_confidence_probe.py` | 90 | yes |
| `SCR-130` | `scripts/analysis/zone_assignment_parity_probe.py` | 90 | yes |

*Generator: `ScriptRegistry.debt_report_markdown` · schema §9.8 · design SITS PR-5*

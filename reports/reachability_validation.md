# Reachability Validation — Evidence (L2, observational)

> Generated `2026-07-04T13:00:08+00:00` · ACTIVE_VERSION = `v2_multi_2026_04` · branch-scoped (§4.0). Regenerate: `python scripts/analysis/reachability_validation_report.py`.
> **Authority: OBSERVATIONAL.** Pass/fail is NOT stored here — run `guard_suite` in CI.

## Verdict counts

| Verdict | Count |
|---|---|
| METADATA | 8 |
| READ_AND_USED | 265 |
| READ_BUT_INERT | 11 |
| TOOLING_ONLY | 4 |
| SHADOW_ONLY | 15 |

**DEAD count:** 0 (must be 0 — gated by `tests/test_config_reachability.py`).

## Runtime flags verified (vs ACTIVE_VERSION config)

| Flag | Value |
|---|---|
| `bitnet_enabled` | `False` |
| `zone_mode` | `hard` |
| `registry_file` | `models/zone_registry.json` |
| `gaussian_impl` | `heuristic` |
| `rr_fusion_active` | `False` |

## Certifying guard suite (observation)

- `tests/test_config_reachability.py`
- `tests/test_reachability_golden.py`
- `tests/test_active_models_registry.py`
- `tests/test_crt_state_invariants.py`

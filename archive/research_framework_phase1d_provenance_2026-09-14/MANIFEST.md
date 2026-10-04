# research_framework_phase1d_provenance_2026-09-14

- Plan: research-framework consolidation, Phase 1 (provenance helpers), batch 1d
- Policy: **no deletes** — every edited file copied here byte-exact first; SHA-256 before/after in `MANIFEST.csv`
- Change: Phase 1d dedup: private _sha256_file / _sha (streaming 1MiB SHA-256, variants 58ea5a0042/88dc0288cd/5b64ee474a/6ac2da0004) -> research.provenance.sha256_file; private _utc (variant c87b462e43) -> research.provenance.utc_stamp_compact; same-named imports, call sites unchanged

| File | Removed def | Now imported as same name from | `--help` stdout before/after |
|---|---|---|---|
| scripts/analysis/run_rr_xauusd_2m.py | `_sha256_file` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/analysis/run_zonegate_xauusd_2m.py | `_sha256_file` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/analysis/shadow_cross_range_restoration_probe.py | `_sha256_file` | `research.provenance.sha256_file` | identical `a32475f728e6b891` |
| scripts/analysis/soft_conf_ema_double_update_probe.py | `_sha256_file` | `research.provenance.sha256_file` | identical `169a012c11a8a05a` |
| scripts/research/h_rr_threshold_001.py | `_sha256_file` | `research.provenance.sha256_file` | not executed (no argparse) |
| scripts/research/visual_state_sample.py | `_sha256_file` | `research.provenance.sha256_file` | identical `364c94ecd0a9fa43` |
| scripts/analysis/phase1_shadow_create_economic_census.py | `_sha256_file` | `research.provenance.sha256_file` | identical `c80cabaa077bf2d0` |
| scripts/research/run_xau_metals_protocol_v1.py | `_sha256_file` | `research.provenance.sha256_file` | identical `f014d6d64483a85a` |
| scripts/research/run_xau_metals_protocol_v1.py | `_utc` | `research.provenance.utc_stamp_compact` | identical `f014d6d64483a85a` |
| scripts/research/xauusd_gaussian_econ_ledger.py | `_sha256_file` | `research.provenance.sha256_file` | identical `fb8ad5487f18fdb0` |
| scripts/research/xauusd_gaussian_econ_ledger.py | `_utc` | `research.provenance.utc_stamp_compact` | identical `fb8ad5487f18fdb0` |
| scripts/research/xauusd_gaussian_econ_units.py | `_sha256_file` | `research.provenance.sha256_file` | identical `e79a0bea39ef4b68` |
| scripts/research/xauusd_gaussian_econ_units.py | `_utc` | `research.provenance.utc_stamp_compact` | identical `e79a0bea39ef4b68` |
| scripts/research/xauusd_gaussian_m4_qualify.py | `_sha256_file` | `research.provenance.sha256_file` | identical `aeb653a681559570` |
| scripts/research/xauusd_gaussian_m4_qualify.py | `_utc` | `research.provenance.utc_stamp_compact` | identical `aeb653a681559570` |
| scripts/analysis/run_crt_local_math_parity_audit.py | `_sha256_file` | `research.provenance.sha256_file` | identical `17751fc19ce0b4a6` |
| scripts/analysis/run_msip_shadow.py | `_sha256_file` | `research.provenance.sha256_file` | identical `1e48bde71fdd2b0c` |
| scripts/research/run_h_msip_001.py | `_sha256_file` | `research.provenance.sha256_file` | not executed (no argparse) |

## Parity evidence

- Edit tool refuses any def whose AST-normalized body is not an approved variant of the shared function.
- Identity: in every edited module the private name `is` the shared `research.provenance` function (module imports).
- Shared functions pinned against verbatim copies of every replaced variant: `tests/research/test_provenance_helpers.py`.
- File line endings / BOM preserved; `py_compile` clean.

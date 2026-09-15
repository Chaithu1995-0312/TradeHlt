# Probes extraction audit — 2026-09-14

## Purpose
Record migrations that extract shared probe helpers into `src/research/probes/` so later audits can see **what moved, what was archived, and what was not deleted**.

## Policy
- **No deletes** of existing files.
- Before in-place edits: copy originals into `archive/<batch>/` preserving relative paths.
- Track every action in `MANIFEST.csv` + `MANIFEST.md`.
- Append batch to `archive/ARCHIVE_INDEX.md`.

## Batch 1 — Phase-1 / sep / p001 (`probes_extraction_phase1_2026-09-14`)

| Item | Detail |
|------|--------|
| Change id | `CH-probes-extract-phase1-2026-09-14` |
| Created | `src/research/probes/` (corpus, governance, horizon, scoreboard, costs_path, shadow_collapse placeholder) |
| Edited | `p001_excursion_probe.py`, `sweep_structure_economic_probe.py`, `phase1_resolver_replay_evidence.py` |
| Archived | pre-edit copies of those three + `shadow_cross_range_restoration_probe.py` |
| Removed pattern | `importlib` file-load of sep/p001 from Phase-1 and sep→p001 |
| Manifest | `archive/probes_extraction_phase1_2026-09-14/MANIFEST.csv` |
| Governance | `docs/governance/build_manifests/CH-probes-extract-phase1-2026-09-14.{impact,completion}.json` |

## Batch 2 — all_states_economic (this apply)

See section below / `CH-probes-extract-all-states-economic-2026-09-14`.

## How to verify later
1. Diff live file vs `archive/<batch>/scripts/...` for intended shim-only changes.
2. Confirm SHA256 rows in `MANIFEST.csv`.
3. `PYTHONPATH=src` → `from research.probes import ...`
4. Re-run probe CLI; compare artifact schema (no claim keys).

---
Generated UTC: 2026-09-14T10:38:13Z

## Batch 2 — all_states_economic (`probes_extraction_all_states_economic_2026-09-14`)

| Item | Detail |
|------|--------|
| Change id | `CH-probes-extract-all-states-economic-2026-09-14` |
| Edited | `all_states_economic_probe.py` (no importlib); `costs_path.load_cost_model`; sep wrapper |
| Archived | pre-edit copies under `archive/probes_extraction_all_states_economic_2026-09-14/` |
| Manifest | `archive/probes_extraction_all_states_economic_2026-09-14/MANIFEST.csv` |

### Remaining importlib sibling loaders (queue)
See live `Select-String importlib.util` under `scripts/` — next likely: `phase1_shadow_create_economic_census.py`, `sweep_conditional_magnitude_probe.py`, `all_states_persistence_probe.py`, `build_decision_atlas.py`.

## Batch 3 (probes_extraction_batch3_2026-09-14)
Full: all_states_persistence, sweep_conditional. Partial (excursion importlib): shadow census, build_decision_atlas.

## Batch 4 — sample_acquisition (probes_extraction_sample_acquisition_2026-09-14)

| Item | Detail |
|------|--------|
| Change id | CH-probes-extract-sample-acquisition-2026-09-14 |
| Fix | Replaced broken ev.sep.p001.load_corpus / ssert_no_claim_keys with 
esearch.probes |
| Residual | importlib still loads phase1_resolver_replay_evidence for Phase-1-local helpers |
| Manifest | rchive/probes_extraction_sample_acquisition_2026-09-14/MANIFEST.csv |

## Batch 5 — replay helpers + excursion (`probes_extraction_replay_excursion_2026-09-14`)
Created excursion + phase1_replay; dropped importlib from sample_acquisition, atlas, shadow census.

### Batch 6b — finish remaining 8 + scriptmod register-before-exec
UTC 2026-09-14T11:04:02Z

- Upgraded `src/research/probes/scriptmod.py`: `sys.modules` register before `exec_module`, return cached module.
- Migrated: feature_certification_state.py, feature_dag_certify.py, g1_build_v4_crt_sot_config.py, g2_v4_crt_sot_parity.py, crt_range_rebuild_probe.py, crt_state_window_trace.py, crt_variant_surface.py, rerun_xau_metals_m4.py
- Goal: `spec_from_file_location` only remains inside `scriptmod.py` under scripts/src research probes.

### Batch 6c — src loaders → load_py
UTC 2026-09-14T11:06:27Z

- `src/governance/semantic_query.py` `_load_feature_surface`
- `src/validation_access/ladder.py` live I-rung + F-rung feature_surface
- After this, `spec_from_file_location` under repo should only live in `src/research/probes/scriptmod.py`

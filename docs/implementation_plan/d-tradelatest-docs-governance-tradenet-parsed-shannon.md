# Plan — Phase 1: align authoritative facts (RR 35→38) + defer federation

## Context

Scope reduced on the governing principle: **don't optimize governance faster than you can validate
models.** The federation refactor is governance optimization; the bottleneck is trustworthy models.
So: execute Phase 1 now, record the federation as a deferred proposal, and leave Phases 2–3 for
later decisions.

## What Phase 1 changes

**One verifiable misalignment exists.** The dim cross-check across all families found exactly one
registry-vs-artifact contradiction:

| Family | YAML | Registry | Artifact | Action |
|---|---|---|---|---|
| gaussian ETH / BNB | 35 / 38 | 35 / 38 | 35 / 38 | consistent — no change |
| zone_gate | 38 | *(no dim field)* | 38 | consistent — no change |
| **rr_model** | **35** | **35** | **38** | **fix registry, mirror follows** |
| tradenet | 35 | *(no dim field)* | binary `.pth` | **unverifiable — leave untouched** |
| bitnet | n/a | `{}` | — | n/a |

Four independent confirmations that 38 is correct: the artifact (`n_features: 38`,
`feature_schema: "canonical_38"`, `scale_mu`/`ridge_w` both length 38, `zero_indices` 11 → rank 27);
the trainer constant `rr_pattern_miner.py:22` `N_FEATURES = CANONICAL_FEATURE_DIM` = **38**; the
pipeline; and sibling entry `202605_v1`, which already declares 38.

### Edits

1. **`models/rr_registry.json`** — active entry `202605_bnb_v2_bnbusdt`: `n_features: 35 → 38`.
   No hash field on entries ⇒ no rehash. **Artifact untouched.**
2. **`active_models.yaml`** — mirror follows *because the registry changed*:
   `rr_model.identity.selection.feature_schema_dim` and
   `runtime_binding.compatibility.feature_schema_dim`, both `35 → 38`.
3. **`docs/governance/build_manifests/CH-rr-registry-dim-38.impact.json`** (+ `.completion.json`)
   — matching the existing manifest shape (`change_id`, `objective`, `change_classes`,
   `affected_files`). Class: `MODEL_ARTIFACT_CHANGE`, which claims `"models/ registry manifests"`
   as its surface; guard `tests/test_active_models_registry.py`.
4. **`docs/governance/model_lineage_rollup.md`** — §4.3a marked RESOLVED (finding text preserved,
   resolution appended per §6.2 rule 4); §10.7 candidate (c) marked DONE.

### Deliberately left alone

- Six other RR entries also declare 35; four are dangling and unverifiable against any artifact.
  Changing unverifiable metadata would be inventing data.
- The same entry's `n_samples: 0` vs `metrics.n_train: 49000` — `0` is certainly wrong, but the
  true total is unknown and will not be guessed. Recorded as an open item.
- TradeNet's declared 35 — binary `.pth`, no registry dim field, unverifiable without torch.

### Behavioural impact: none on the decision path

The only runtime reader is `src/control_plane/dashboard_api.py:492` (`entry.get("n_features", 35)`)
— a *display* consumer. `rr_fusion.enabled=false`, so no inference path reads it either way. The
edit corrects what the dashboard shows.

## Federation — recorded as deferred, not built

A short block appended to `model_lineage_rollup.md` §10.7 (the existing home for recorded,
unauthorized candidates — no new file, §6.2 rule 5):

```text
MRF_V1 — Model Registry Federation
Status:  Proposed
State:   Not Implemented
Reason:  Deferred until research stabilization
```

With three lines of why it was deferred and the load-bearing constraint discovered while scoping it
(`active_models.yaml` is a runtime input — `state_contract_loader.py:38` hardcodes the root path,
parses `state_contracts`, and enumerates top-level keys as the model-ID set; 27 coupled files,
22 registry tests), so a future decision starts from evidence rather than re-deriving it.

## Files

| File | Change |
|---|---|
| `models/rr_registry.json` | active entry `n_features: 35 → 38` |
| `active_models.yaml` | mirror: two `feature_schema_dim` 35 → 38 |
| `docs/governance/build_manifests/CH-rr-registry-dim-38.*.json` | NEW manifest pair |
| `docs/governance/model_lineage_rollup.md` | §4.3a RESOLVED · §10.7 (c) DONE · MRF_V1 deferred note |
| `assistant_project.md` | §6 SESSION LOG |

Not touched: any model artifact, loader, config, or runtime wiring. No new YAML authorities.

## Verification

```
venv/Scripts/python.exe -m pytest tests/test_active_models_registry.py tests/test_state_contracts.py tests/test_doc_citations.py tests/test_session_log.py -q
```

Explicit checks: registry `n_features` == artifact `n_features` (38); artifact sha256 **unchanged**
at `6ed92d26…` (proves metadata-only); `active_models.yaml` mirrors the updated registry (R1 green);
`test_state_contracts.py` green (the index's runtime contract untouched).

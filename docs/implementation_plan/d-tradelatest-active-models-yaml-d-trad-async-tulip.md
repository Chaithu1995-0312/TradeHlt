# Add flags + key-existence checks linking active_models.yaml ↔ ACTIVE_VERSION config

## Context
"Link both files" evolved (via a multi-LLM design pass) into a model coverage registry. The
decisive finding: **that registry already exists** — `active_models.yaml` is schema **v2.1** with
per-model `reachability`/`optimization` blocks, and `tests/test_active_models_registry.py` already
links it to the config named by `configs/production/ACTIVE_VERSION` **by pointer resolution, not
value equality**, with a §6.5 guard that already forbids `threshold|min_delta|promotion` keys in
`optimization` (the exact "don't assert yaml==config" failure the chain warned about).

(E-001 note: my first read this session showed v2.0 — a stale working-tree snapshot; the file is now
committed at v2.1. Verified via `git show HEAD:` + clean `git status --porcelain`.)

The one genuine gap, which the user pre-approved: the config link is at **section** granularity
today (`crt_engine`, `params` exist as top-level keys). It does not yet assert (1) binary runtime
**flags** match the live values, nor (2) individual **config_key existence**. This plan adds both —
additive, hash-neutral, grants no authority.

## Change 1 — one additive yaml field (make rr_fusion machine-readable)
`rr_model.runtime` states "rr_fusion disabled" only in prose (`notes` + status comment). Add a
structured twin so the flag test can compare directly:
```yaml
rr_model:
  runtime:
    rr_fusion_active: false   # machine-readable twin of the F-038 prose; config engine_runner.rr_fusion.enabled
```
(yaml is not hashed — only the config `params` block feeds `config_hash` — so this is hash-neutral.)

## Change 2 — semantic-flag consistency test (high-confidence, green on arrival)
Add `test_runtime_flags_match_active_config` to `tests/test_active_models_registry.py`. Resolve the
active config via the existing `test_config_sections_are_active_config_keys` loader (ACTIVE_VERSION →
JSON). Assert this fixed flag map (FLAGS ONLY — never thresholds; yaml documents code defaults,
config holds tuned overrides like retest_depth_max 0.25 vs 0.15):

| yaml path | config path (ACTIVE_VERSION) |
|---|---|
| `bitnet.runtime.enabled` | `crt_engine.use_bitnet` |
| `zone_gate.runtime.zone_mode` | `engine_runner.zone_mode` |
| `zone_gate.runtime.registry_file` | `engine_runner.zone_registry_path` |
| `gaussian.runtime.engine` via `{HeuristicGaussianEngine: "heuristic"}` | `engine_runner.gaussian_impl` |
| `rr_model.runtime.rr_fusion_active` (Change 1) | `engine_runner.rr_fusion.enabled` |

## Change 3 — individual config_key existence test (verify-first, then pin)
Add `test_yaml_config_keys_exist_in_schema`. Build the key set from the CRT `detection.*.config_keys`
+ `thresholds` block; assert each resolves into `{f.name for f in dataclasses.fields(CRTConfig)}` ∪
the `params`/`crt_engine` section keys. Reuse the `CRTConfig` import pattern from
`scripts/analysis/config_reachability.py:57`.

**Discipline (§6.5 — don't pin a biased instrument):** run it first as a report (print unresolved
keys) to confirm 0 *benign* naming mismatches (e.g. `session_windows`, `sizing_bands`). If any
surface, classify each as real drift (fix yaml/code + doc decision per §6.2) vs. a naming-convention
gap (adjust the comparison) BEFORE turning it into a hard assertion. Do not ship it red.

## Critical files
- `active_models.yaml` — Change 1 (one field).
- `tests/test_active_models_registry.py` — Changes 2 & 3 (two functions; reuses its own config loader
  + `CRTConfig` via `dataclasses.fields`).
- Do NOT touch `tests/test_crt_state_invariants.py` (semantic YAML↔code invariant stays there).

## Out of scope (parked per §6.5 — separate axis / premature)
MT5 signal→position evidence bridge; coverage-% dashboards; a new CLAUDE.md governance section.

## Verification
`python -m pytest tests/test_active_models_registry.py tests/test_crt_state_invariants.py` green.
Red-check: flip `use_bitnet` or `rr_fusion.enabled` in a scratch config copy → flag test red;
rename a yaml `config_key` → existence test red. Then §6/§6.2 SESSION LOG + doc-impact entry
(governed-config-adjacent turn).

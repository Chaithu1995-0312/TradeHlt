# Reachability Validation — Confidence Hardening + Evidence-Driven Testing

## Context

The reachability full-sweep (prior turn) came back GREEN (0 DEAD, 14 guard tests pass), but a
confidence audit — reading `scripts/analysis/config_reachability.py`, `tests/test_active_models_registry.py`,
and `tests/test_config_reachability.py` directly — found the instrument is prone to **false
"inert/dead" readings** and its **confidence limits don't travel with the report**. The user further
directed that tests be elevated from pass/fail gates into a **three-layer evidence system**:
`L1 unit/invariant → L2 regenerated evidence artifact → L3 semantic golden (regression detection)`.

Confirmed root causes (this session):
1. **Scope blind spot.** Analyzer scans `src/` only. Tooling-consumed keys read as INERT — **verified**:
   `tuner.{trade_count_floor,consistency_alpha,phase2_min_iter}`, `rr_model.dataset_min_samples` all
   appear in `scripts/training/auto_tuner_multi.py` & `auto_tuner_gemini_gate.py`.
2. **`strict_fetch` false-INERT.** `dataset_integrity.strict_fetch` occurs in `src/` only inside a
   docstring (`src/data_ingestion/dataset_integrity.py:277`, backticks — not a quoted literal), so
   `_string_literal_refs` misses it; its real consumer must be verified at implement time.
3. **Confidence not encoded**; the committed `docs/` report is stale (2026-06-12).

**Reuse-first alignment (important):** the repo already has the exact "executable truth" pattern the
user wants — `scripts/governance/export_findings.py` generates a deterministic artifact and offers a
`--check` mode that fails on drift-from-source, guarded by `tests/test_findings_export.py`; and
`scripts/update_config_hash.py` is the in-repo "regenerate the committed truth" accept-script idiom.
Golden fixtures exist too (`tests/analytics/test_golden_ledgers.py`). This plan realizes L2/L3 on
those patterns instead of inventing a new golden framework.

Scope guard: this is a **precision + evidence upgrade to a Level-1 instrument** (§6.5), NOT a
conclusion change. No registered finding depends on the counts; INERT→TOOLING_ONLY reclassification
flips no F-finding. Economic findings, CRT invariants, and the config/`params` (hash) are untouched.

## Approach

### Change 1 — `TOOLING_ONLY` verdict + scan `scripts/` (`config_reachability.py`)
Keep `READ_AND_USED` = **live-spine (`src/`) consumption**; add a distinct tier for tooling.
- Extend corpus to walk `src/` **and** `scripts/` (exclude `tests/`); rel-paths already tag origin.
- Add `_is_tooling(rel) = rel.startswith("scripts/")`.
- Rewrite `_classify_refs` with documented precedence:
  `live src/ non-dormant → READ_AND_USED` > `scripts/ → TOOLING_ONLY` > `dormant src/ only →
  SHADOW_ONLY` > none → `READ_BUT_INERT`.
- Register `TOOLING_ONLY` in the module-docstring Classification list, `render_md` verdict order +
  Legend + Flagged section (summary loop picks it up automatically).

### Change 2 — Curated indirect-consumer note for verified false-INERTs
Add `_INDIRECT_CONSUMERS: dict[str, str]` (sibling of existing `_HARDCODED_OVERRIDES`, lines 82–87),
keyed `section.key → note`, wired through `add()`. Candidate: `strict_fetch`. **Verify the real
consumer first** (grep the `validate_dataset` cfg_override / strict-profile path in `src/`+`scripts/`);
reclassify only with a cited `file:line`, else leave INERT with an explanatory note — never flip on
assumption (E-001).

### Change 3 — Confidence & limitations block in the report (`render_md` only)
Append "## Confidence & limitations": per-verdict confidence (`DEAD`=Certain/structural;
`READ_AND_USED`=referenced Likely / consumed Possible; `INERT/SHADOW/TOOLING`=advisory, confirm via
evidence column); scope = `src/`+`scripts/` not `tests/`; §6.5 caveat "GREEN certifies plumbing, not
behavioral correctness or economic authority." JSON stays data-shaped (no schema change).

### Change 4 — L1 guard-test update (`tests/test_config_reachability.py`)
Add `"TOOLING_ONLY"` to the allowed-verdict set (lines 39–42); keep `test_no_dead_config_keys`.

### Change 5 — L2 regenerated evidence artifact (`reports/`)
Thin driver (new `scripts/analysis/reachability_validation_report.py`, or a `--evidence` flag on the
existing tool) emits a consolidated, stable-named `reports/reachability_validation.{json,md}`:
```
{ generated_at, active_version, verdict_counts, dead_count,
  runtime_flags_verified: {bitnet, zone_mode, registry_file, gaussian_impl, rr_fusion},
  guard_suite: [test files], guards_passed: bool }   # guards_passed via pytest.main() rc
```
Stable filename (timestamp lives *inside*, so `git diff reports/` is meaningful — mirrors
`reports/framework_registry_report.md`). Confirm `reports/` tracking at implement time; if gitignored,
this stays session evidence (the committed regression truth is the L3 golden below).

### Change 6 — L3 semantic golden / drift detection (reuse `export_findings --check` idiom)
Compare **semantic subsets only** (never full markdown / timestamps / paths / ordering — the user's
brittleness caution, adopted as a hard rule).
- **Config golden = the committed report itself.** Add `build_summary(report)` returning the stable
  subset `{active_version, verdict_counts, dead_keys[], tooling_only_keys[](sorted)}`. New
  `tests/test_reachability_golden.py::test_config_summary_matches_committed_report` compares a fresh
  `build_report()` subset to the committed `docs/research-readiness/config-reachability-report.json`
  subset; on drift it fails with "re-run config_reachability.py and commit." **Accept = regenerate**
  (Change 8) — same flow as `export_findings`.
- **Registry golden = one new small fixture** (`tests/golden/registry_summary.json`, the single
  justified new file — `active_models.yaml` has no generator artifact to diff against). Pin
  `{model_count, model_names[](sorted), runtime_flags:{5 resolved values}}`.
  `test_registry_summary_matches_golden` compares a derived summary of `active_models.yaml` +
  ACTIVE_VERSION config to the fixture. Accept via a `--update` flag on the accept-script (Change 8).

### Change 7 — Refresh the stale committed report + doc sync
Regenerate via the sanctioned generator (never hand-edit a GENERATED file):
`python scripts/analysis/config_reachability.py` → overwrites
`docs/research-readiness/config-reachability-report.{json,md}` (this also seeds the Change-6 config
golden). §6.2: if `docs/research-readiness/README.md` enumerates verdicts, add `TOOLING_ONLY` (grep
first).

### Change 8 — Accept-changes script (mirror `scripts/update_config_hash.py`)
`scripts/analysis/update_reachability_golden.py`: regenerates the config report (reseeds the config
golden) and rewrites `tests/golden/registry_summary.json`. Makes verdict-count/model changes an
**explicit accepted truth change**, never silent drift. (Config side can also just re-run Change-7's
generator; the script bundles both for one-command accept.)

## Critical files
- `scripts/analysis/config_reachability.py` — corpus roots, `_classify_refs`, `TOOLING_ONLY`,
  `_INDIRECT_CONSUMERS`, `build_summary`, `render_md` legend + confidence block, optional `--evidence`.
- `tests/test_config_reachability.py` — allowed-verdict set (+`TOOLING_ONLY`).
- `tests/test_reachability_golden.py` — **new**, L3 semantic golden (config + registry).
- `tests/golden/registry_summary.json` — **new** committed fixture (only justified new data file).
- `scripts/analysis/update_reachability_golden.py` — **new**, accept-changes.
- `scripts/analysis/reachability_validation_report.py` (or `--evidence` flag) — **new**, L2 artifact.
- `docs/research-readiness/config-reachability-report.{json,md}` — regenerated (generated artifact).
- `docs/research-readiness/README.md` — verdict enumeration sync (if it lists them).

## Reused existing patterns (do not invent)
- `_HARDCODED_OVERRIDES` curated-map + `add()` hook (lines 82–87, 225–234) → mirror for `_INDIRECT_CONSUMERS`.
- `_is_dormant`/`_DORMANT_FRAGMENTS` → sibling `_is_tooling`.
- `export_findings.py --check` + `test_findings_export.py` → the drift-golden idiom.
- `scripts/update_config_hash.py` → the accept-script idiom.
- `tests/analytics/test_golden_ledgers.py` → committed-golden test style (semantic, not byte-snapshot).

## Verification (the L1→L2→L3 pipeline)
1. `python scripts/analysis/config_reachability.py --check` → **exit 0** (0 DEAD preserved).
2. Inspect fresh summary: `tuner.*`/`rr_model.dataset_*` now `TOOLING_ONLY`; `strict_fetch` flips with
   a cited note *or* stays INERT with a note (never silently flipped).
3. `venv/Scripts/python.exe -m pytest tests/test_config_reachability.py tests/test_reachability_golden.py tests/test_active_models_registry.py tests/test_crt_state_invariants.py -q`
   → all green (use `venv/` py3.12; default py3.14 lacks PyYAML).
4. Regression check: manually bump a verdict in the committed report (or add a model) → the L3 golden
   test **fails** with a clear regenerate message; run Change-8 accept script → green again.
5. L2 artifact present at `reports/reachability_validation.{json,md}` with verdict_counts + 5 verified
   flags + `guards_passed: true`.
6. Report markdown carries the "Confidence & limitations" section; Legend lists `TOOLING_ONLY`.
7. `git diff --stat`: only the files above; **no `src/` spine or config edits**.

## Guardrails / doctrine
- Semantic golden only — never pin `generated_at`, evidence paths, key ordering, or full markdown.
- No config/`params` edits → no rehash. Reachability + evidence artifacts are generated.
- Deviation flagged: the repo's native golden style is inline hand-verified fixtures; a stored
  `tests/golden/registry_summary.json` snapshot + accept-script is a **user-directed** extension
  (justified: the registry has no generator to `--check` against). Confined to one fixture.
- No finding changes; if reclassification reveals a genuinely DEAD or economically-relevant key,
  STOP and surface a §6.2 TruthConflict rather than absorb it.
- Append the §6 `📝 SESSION LOG ENTRY` to `assistant_project.md` at the end of the implementation turn.

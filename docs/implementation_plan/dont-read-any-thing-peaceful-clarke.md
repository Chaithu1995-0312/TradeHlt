# Research SSOT framework — round 2 fixes (review of firstreview/ hardened zip)

## Context
Round 1 (A–H design, producer = kind+config) was implemented by another model and delivered as
`researcharctitecuredocs/firstreview/research_ssot_framework_hardened_v0.1.zip`. Review (2026-10-10)
confirmed by in-memory probes that invariants 3/4/6 are still bypassable. Scope remains the
standalone experiment under `researcharctitecuredocs/` only.

## Step 0 — adopt the zip as the base
Extract the zip's `research_ssot_framework_v0.1/` over the in-tree package after moving the current
package to `researcharctitecuredocs/_archive/pre_hardening_v0.1/` (never delete). Run its 16 tests
first to verify the "16 pass" claim before changing anything.

## Fixes (core.py unless noted), each with a test that fails pre-fix
1. **H7 evidence-bearing results** — `COMPLETED`/`REUSED` results must carry
   `{artifacts:[{path, sha256}], run_identity_ref}`; `REUSED` must also name the matched identity.
   Missing → `ValueError`. Results for node ids not in the plan → `ValueError`.
2. **H1 no `none` laundering** — a node with any state-bearing input may not emit `state_producer:
   "none"` (ERROR `PRODUCER_DROPPED`). Example: `population_counts` inherits the engine producer.
3. **H2 comparison taint propagates** — any output descended from a compare output (unless through a
   `bridge`) stays comparison-tainted; `measurement` on tainted input → error.
4. **H3 sources must declare** — `artifact_resolve` nodes (and any node with no producer-bearing
   inputs that emits outputs) must set `state_producer` explicitly (`none` or `{kind, config_ref}`);
   `inherit` there → ERROR `STATE_PRODUCER_UNDECLARED`.
5. **H4 externals can carry producers** — `external_inputs` of kind `dataset` may declare
   `state_producer`; undeclared dataset externals are `unknown` producer → pooling with anything
   tagged → `PRODUCER_POOLING`.
6. **H5** — `config_ref` pointing at an `UNRESOLVED` config external → node `BLOCKED`.
7. **H6 + FAILED relabel** — non-required failure keeps status `FAILED`; only dependents become
   `SKIPPED`. Report status: any unsupported claim after execution with no PLANNED/BLOCKED nodes →
   `INCOMPLETE`; add `PARTIAL` when some nodes ran and others still `PLANNED`.
8. **CLI** — `--include` default reads from `core` (single source); add `apply` command
   (`--plan --results --out`) so results flow through the validated path.
9. **Inventory hash** — exclude `repository_root` from `content_sha256` (keep it in the record).
10. **G docs** — archive top-level `ARCHITECTURE.md`, `example_final_report.md` and
    `firstreview/* (2).md` into `_archive/`; correct the false `_archive/README.md` note. One
    canonical ARCHITECTURE.md (package `docs/`) updated for 1–9.

## Verification
```
cd researcharctitecuredocs/research_ssot_framework_v0.1/research_ssot_framework
PYTHONPATH=src D:/Tradelatest/venv/Scripts/python.exe -m unittest -v
```
- Re-run the H1–H7 probe script (kept in scratchpad) → every probe now yields an ERROR / correct status.
- Mutation check: disable each new guard → its test fails → restore.
- CLI validate/plan/report on example → still `BLOCKED`, claims `UNSUPPORTED`.

## After
Read-only overlap map vs repo registries (SITS, MEASUREMENT_CONTRACT/MC-*, research_family_registry,
Corpus SSOT F-119, MPA v1) before binding any `ref`. SESSION LOG entry to `assistant_project.md`.

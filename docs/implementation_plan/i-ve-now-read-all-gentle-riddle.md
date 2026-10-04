# Plan: Framework Registry (001) — Full Build

## Context

Three **untracked, LLM-recent** framework docs (`TRADING_SYSTEM_FRAMEWORK.md`,
`EXISTING_TO_FRAMEWORK_MAP.md`, `001_FRAMEWORK_REGISTRY.md`) propose a 6-level architecture
(L0 Kernel → L6 Execution) and a JSONL-backed `FrameworkRegistry` to map every existing module
to that hierarchy with evidence links, parent/child edges, and finding links.

**Why build it:** the registry is the §6.2 "compress truth, reduce fragmentation" tool — a single
queryable source of "what exists, where, with what status." It is purely **additive** (new files
only, zero runtime/spine impact, no config-hash change, no rehash), test-gated, and reuses existing
infra. Crucially, its first real job is to **catch and correct the framework docs' own drift** —
validation already proved the map is wrong in places (below). The registry replaces the map's prose
assertions with code-verified, mechanically-validated status.

**Scope chosen by user:** the *complete* File Inventory from 001 (all milestones M0–M4 deliverables),
not a trimmed core.

## Truth corrections to bake in (verified against code this session — §6.2: code wins → fix the doc)

The 001 gap-audit template and the map contain false claims. The seed + gap-audit MUST emit
**code-verified** status, not the docs' assertions:

| Doc claim | Verified reality | Registry status to record |
|---|---|---|
| "UltronRiskGate disabled (`gated_enabled=false`)" — 001:314,335 | `disabled: false` in active config ([v2_multi_2026_04.json:86](configs/production/v2_multi_2026_04.json:86)); wired at [live_engine_hook.py:805](src/runtime/live_engine_hook.py:805) | `extant` + wired; gap-audit P1 row **retracted/corrected**, not "disabled" |
| Schema example cites `v2_multi_2026_04 - deepdeektry.json` (001:37) | Canonical active = `v2_multi_2026_04` (deepdeektry was the experimental dup, reverted — see `project_truth_audit_2026_06_11`) | Seed evidence cites the **canonical** config, never deepdeektry |
| config_integrity gates runtime | Orphaned, CLI-only ([config_integrity.py](src/governance/config_integrity.py)) (F-006) | `orphaned` |
| portfolio / capital_management wired | Exist, zero callers ([src/portfolio/](src/portfolio/allocator.py)) (F-013) | `orphaned` |
| CRT mandatory engine; s01–s10 exist | Confirmed ([engine_runner.py:52](src/core/engine_runner.py:52)) | `extant` |

These corrections are the registry's first compounding payoff — record them in `last_validated`
notes so the divergence is preserved (§6.2 rule 4: never silently delete truth).

## Deliverables (the full 001 File Inventory)

**M0 — Schema + Module + Tests**
1. `docs/reference/framework_registry_schema.md` — JSONL line schema (id/type/level/name/parent/
   children/evidence[]/findings[]/tests[]/status/created/last_validated/notes) + the 4 enums
   (type, level, status, evidence-type). Mirror 001 §M0 Deliverable 1 verbatim, but fix the
   deepdeektry example path.
2. `src/governance/framework_registry.py` — `FrameworkRegistry` class. Public API exactly per
   001:96–108: `load · filter · get · get_tree · find_by_finding · get_orphaned ·
   validate_evidence · validate_findings · append · to_dataframe · summary`.
3. `tests/test_framework_registry.py` — the 8 tests at 001:114–124.

**M1 — Seed**
4. `scripts/governance/seed_framework_registry.py` — emits the initial lines from the
   classification table (001:133–166), with **corrected statuses** (above). Thin wrapper; writes
   via the registry's `append`.
5. `data/framework_registry.jsonl` — generated artifact.

**M2 — Query + Report**
6. `scripts/governance/query_registry.py` — CLI: `--summary --type --level --status --tree
   --finding --orphaned --missing-evidence --validate` (001:193–215).
7. `scripts/governance/framework_registry_report.py` — generates report #8.
8. `reports/framework_registry_report.md` — generated (summary/gap/orphan/finding-coverage/
   evidence-health/ASCII-tree).

**M3 — Gap Audit**
9. `scripts/governance/framework_gap_audit.py` — emits the L0–L6 gap tables + priority list
   (001:256–342), **with the UltronRiskGate "disabled" P1 row corrected**.
10. `reports/framework_gap_audit.md` — generated.

**M4 — Update + (doc) CI**
11. `scripts/governance/update_registry.py` — `--component <id> --status <new>` appends a new
    timestamped line (append-only; never mutates prior lines).
12. `docs/architecture/TRADING_SYSTEM_FRAMEWORK.md` — MOD: append the JSONL schema section.
    (CI wiring is doc-only/optional — note it; do not silently add a CI yaml gate.)

## Design — reuse, don't reinvent (key constraint)

- **Persistence:** use [src/utils/jsonl_writer.py](src/utils/jsonl_writer.py) — `read_jsonl` /
  `append_jsonl` / `iter_jsonl`. Do **not** hand-roll JSON line I/O. `load()` keeps latest-per-id
  (append-only ledger semantics, like the model registries).
- **`validate_findings()`:** parse `docs/current-findings.md` the **same way**
  [test_current_findings.py](tests/test_current_findings.py) does (`### F-NNN` block regex). Every
  `findings[]` id must resolve to a non-terminal finding there. Reuse, don't duplicate, the parser
  shape.
- **`validate_evidence()`:** mirror [test_doc_citations.py](tests/test_doc_citations.py) — resolve
  `path`, confirm file exists, and confirm `symbol` appears within a **±30-line drift window** of
  `line` (symbol is authoritative, line is a hint). Config/doc evidence: existence check only.
- **Test-pinning pattern:** `test_framework_registry.py` loads the registry + runs the validators,
  exactly like [test_config_reachability.py](tests/test_config_reachability.py) imports the audit
  script and asserts no failures. The validate-suite IS the CI gate (M4 D1 = run `--validate`).
- **`to_dataframe()`:** optional-import-guard pandas (raise a clear message if absent) per the
  repo's optional-import convention — pandas must not be a hard dependency of the module.
- **Determinism:** seed/report/gap-audit outputs must be stable (sorted ids, fixed timestamp source
  or pinned `created`); generated `.md`/`.jsonl` should be byte-stable across reruns so they can be
  committed and diffed.

## Seed taxonomy (from 001:133–166, statuses corrected)

L0 Kernel (`extant`): engine_runner, fusion_engine, decision_engine, feature_pipeline,
backtest_v2, collector. — L1 Domain: CryptoSpot (`implicit`, no Domain class), Forex
(`implicit`/dormant). — L2 Style (`extant`, no style class yet): ReactionBased(3),
MeanReversion, Breakout, StatArb, Grid, Momentum, Pattern, ML/Hybrid. — L3 Strategy
(`extant`): s01–s10. — L4 Impl/AI (`extant`): crt/gaussian×2/zone/rr engines, agent, bitnet;
RegimeClassifier `dormant` (F-012), DriftDetector `extant`-not-acted (F-008). — L5 Risk:
UltronRiskGate `extant`+wired (**corrected**), portfolio `orphaned` (F-013). — L6 Execution:
execution_planner `extant`, executor `stub` (F-010). — Governance (meta): promotion_manager,
config_integrity `orphaned` (F-006).

## Verification

1. `pytest tests/test_framework_registry.py -v` — all 8 green.
2. `python scripts/governance/seed_framework_registry.py` then
   `python scripts/governance/query_registry.py --validate` — zero evidence/finding/dangling/dup
   errors (this is the M4 CI gate).
3. `python scripts/governance/query_registry.py --summary` and `--tree DOMAIN-001` — sane output.
4. Regenerate report + gap-audit; re-run the generators a 2nd time → **byte-identical** outputs
   (determinism).
5. Confirm gap-audit P1 row shows UltronRiskGate **enabled/wired**, not "disabled."
6. `pytest -q` smoke — no existing test regressions (additive-only expectation).
7. No config-hash change (no `params` edits) → no `_compute_hash.py` rehash needed.

## Notes / risks

- **Scope is large** (12 items). Recommend implementing in milestone order M0→M4, validating after
  each, so a failure is localized.
- **§6 SESSION LOG**: not writable in plan mode; append to `assistant_project.md` at implementation
  time (codebase log — this is tooling/governance code per §6 tie-breaker).
- **Open Qs from 001 resolved by this plan:** (1) seed CryptoSpot + dormant Forex only; (2)
  complement, not replace, existing intent maps; (3) seed is manual-classification-driven (script
  emits the curated table), AST auto-detection deferred.
- **Authority caveat (§6.5):** this registry is a *discovery/organizational* tool. It records and
  surfaces gaps; it grants **no** production authority and changes **no** behavior. Acting on any
  gap it surfaces (e.g. de-privileging CRT, wiring portfolio) is a separate, evidence-gated decision.

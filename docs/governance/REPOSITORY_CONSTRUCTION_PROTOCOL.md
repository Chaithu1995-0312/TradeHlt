# Repository Construction Protocol (Gate 6 — non-optional)

> **The governed architecture is the mandatory path for ALL repository changes.** This doc is thin;
> the machine-readable authorities rule: [`change_contracts.json`](change_contracts.json) (per-class
> obligations) and `scripts/governance/construction_protocol.py` (the validator). Enforcement is
> mechanical: the census FRESHNESS floor (`tests/test_geometry_census.py::test_geometry_census_is_fresh`)
> + the extended GREEN_FLOOR (`scripts/maintenance/check_governance_invariants.py`, run by CI
> `.github/workflows/governance.yml`) fail on ungoverned feature math regardless of whether anyone
> read this document.

## The lifecycle (every change)

```
1  CLASSIFY the change      → change_contracts.json classes (one or more)
2  PRE-BUILD SEARCH         → market ontology → formula registry → canonical impls →
                              geometry census → active_models.yaml → production config →
                              lineage/consumers (adjudication artifact)
3  BUILD_IMPACT_MANIFEST    → docs/governance/build_manifests/<change_id>.impact.json
                              (validator: `construction_protocol.py validate-impact <file>`)
                              ANY blocking UNKNOWN ⇒ STOP — resolve before implementing.
4  IMPLEMENT                → through the canonical authorities only (no local formula math;
                              new quantities are REGISTERED first: ontology + registry + FM-id)
5  POST-BUILD VALIDATE      → `construction_protocol.py validate-completion <file>`:
                              declared-vs-actual git diff (undeclared governed surfaces FAIL),
                              REQUIRED checks are EXECUTED (never log-trusted), repo-state hash bound
6  BUILD_COMPLETION_MANIFEST→ <change_id>.completion.json; COMPLETE only if mechanically green
7  SYNC                     → findings/topics/citations/session log per CLAUDE.md §6.x
```

One-command floor for agents: `python scripts/governance/construction_protocol.py check`.

## What the machine already prevents (do not rely on memory)

| Attempt | Caught by |
|---|---|
| local geometry formula anywhere in the universe | census FRESHNESS floor (repo-wide re-derivation diff) |
| new feature without ontology/registry registration | census-fresh + `test_feature_lineage` exhaustiveness |
| re-derivation of a governed name in the live spine | ownership lint (`test_feature_math_lint`) |
| formula change without parity | `test_candle_math` / `test_derived_math` / `test_formula_registry` |
| model outside the registry / stale pointers | `test_active_models_registry`, zone manifest parity |
| config outside authority | `test_config_reachability` + golden |
| changed governed file not declared in the manifest | `validate-completion` git-diff check |
| COMPLETE claimed with failing/stale/skipped checks | `validate-completion` executes checks + repo-hash binding |
| grandfathered-debt resurrection | GD set-monotonic ratchet + retirement manifest |

## Honest residuals (disclosed, not hidden)
- No local git hook is installed in this clone — CI-on-push (`governance.yml`) is the backstop;
  in-session edits are caught at the next floor run, not mid-edit.
- The census is static analysis (declared limits in its universe manifest); dynamically-dispatched
  math beyond the admitted registry executors would need census extension.
- Census price-token recall is alias-table bound: `_PRICE_LOOKUP` resolves `close`/`c`/`cls` but not
  prefixed parameter names (`disp_close`, `retest_close`), so `abs(disp_close - disp_open)` in
  `derived_math.displacement_retrace` (FM-027) is invisible to the census. Recall-only, and confined
  to a REGISTERED canonical impl — it cannot conceal an ungoverned re-derivation. Disclosed
  2026-07-22; tracked as FU-CENSUS-PARAM-ALIAS with the adjudication rows preserved (commented) in
  `scripts/analysis/gate2b_adjudication.py`.
- The full pytest suite retains known F-018 reds; the GREEN_FLOOR is the curated enforcement set and
  grows monotonically.

### Script inventory (SITS) — thin pointer

Adding/moving/classifying scripts is change class **`SCRIPT_LIFECYCLE_CHANGE`**
([`change_contracts.json`](change_contracts.json)). Required checks include
`tests/test_script_registry.py` (disk coverage + grandfather ratchet) and
`tests/test_script_matrix_sync.py`. New paths outside the grandfather pin must get a
**seed overlay** with a real purpose — auto-stub `GRANDFATHER_UNCLASSIFIED` fails the floor.
Day-to-day steps: [`docs/reference/conventions.md`](../reference/conventions.md) §2.1.
Design: [`docs/implementation_plan/script-implementation-traceability-sits-design.md`](../implementation_plan/script-implementation-traceability-sits-design.md).

Created 2026-07-08 (Gate 6). Phase-1 audit: [`construction_protocol_reachability_audit.md`](construction_protocol_reachability_audit.md).

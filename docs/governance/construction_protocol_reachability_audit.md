# Construction-Protocol Reachability Audit (Gate 6, Phase 1 — point-in-time, 2026-07-08)

_What was actually ENFORCED vs documentation-only before the Construction Contract, with the bypasses
that motivated it. Point-in-time forensic (§6.2 rule 5); the living contract is
[`REPOSITORY_CONSTRUCTION_PROTOCOL.md`](REPOSITORY_CONSTRUCTION_PROTOCOL.md)._

## Enforcement spine (pre-existing)
- **CI**: `.github/workflows/governance.yml` → `scripts/maintenance/check_governance_invariants.py
  --all` = curated **GREEN_FLOOR** (deliberately NOT full pytest — ~66 known F-018 reds would make the
  gate permanently red = decorative, E-001F). Policy constants pinned by
  `tests/test_governance_invariant_check.py`; monotonic-growth rule.
- **Local hooks**: none active in this clone (`.git/hooks` samples only) — CI-on-push is the backstop.
- **AGENTS.md**: pointer to CLAUDE.md (deliberate non-duplication).
- **Manifest machinery**: none existed.

## Component audit (pre-Gate-6 state)

| Component | Authoritative artifact | Enforcement | Fresh? | In GREEN_FLOOR/CI? | Bypassable? |
|---|---|---|---|---|---|
| Market ontology + registry parity | market_ontology.yaml + registry/ | test_formula_registry (parity battery) | fresh | **NO** | yes — skip pytest, CI green |
| Canonical math parity | candle_math/derived_math | test_candle_math/test_derived_math | fresh | NO | yes |
| Ownership lint | feature_math_lint.py + GD ledger | test_feature_math_lint (build_report fresh) | fresh, **5-dir scope** | NO | yes + scope gap (B5) |
| Geometry census | geometry_census.jsonl | test_geometry_census | **STALE** (validated committed artifact shape only) | NO | **B1: new derivation anywhere passed silently** |
| Gate-2B adjudication | geometry_semantic_adjudication.jsonl | test_gate2b_closure (artifact↔artifact) | stale-pair | NO | with B1 |
| Feature lineage | ontology↔registry↔vector | test_feature_lineage | fresh (static parity-set) | NO | yes |
| Active models | active_models.yaml | test_active_models_registry | fresh | NO | yes |
| Production config | configs/production/* | test_config_reachability + golden | fresh | NO | yes |
| Findings/citations/topics/session | docs | 4 doc floors | fresh | **YES** | — |
| GOVERNED paths | invariant gate | requires_run() | — | src/research, docs/governance, tests/governance, findings only | **B3: src/features + configs/formulas ungoverned** |

**Bypass set:** B1 census staleness (keystone) · B2 feature-math floors absent from GREEN_FLOOR ·
B3 governed-path gaps · B4 no manifest/change-contract machinery · B5 lint 5-dir scope ·
B6 local hook uninstalled (residual, disclosed).

## Gate-6 closures (implemented 2026-07-08)
- **B1** → `test_geometry_census_is_fresh` + `test_adjudication_closed_against_fresh_census`
  (re-derive census in-test, diff vs committed; registration/adjudication becomes mandatory-by-test).
- **B2** → GREEN_FLOOR += 9 floors (formula/candle/derived/lint/lineage/census/gate2b/active-models/
  construction-protocol); pinned policy test extended in the same change.
- **B3** → GOVERNED_PREFIXES += `src/features/`, `configs/formulas/`, `scripts/analysis/`;
  GOVERNED_FILES += `active_models.yaml`.
- **B4** → `change_contracts.json` (12 classes) + `construction_protocol.py`
  (validate-impact / validate-completion / check) + `build_manifests/` + adversarial floor
  `tests/test_construction_protocol.py` (14 tests: UNKNOWN-blocks, unacked checks, undeclared
  surfaces, DOCUMENTATION_ONLY behavior guard, stale repo-hash, executed-not-log-trusted checks,
  rogue-formula census catch; valid controls pass).
- **B5** → mitigated repo-wide by B1 (census freshness covers all universes; the 5-dir lint remains
  the fast in-spine floor).
- **B6** → residual: CI-on-push only; disclosed in the protocol doc.

## Can an agent still modify governed surfaces and get green completion without the protocol?
- Via pytest/CI: **NO** for geometry/feature-math surfaces (census-fresh + extended GREEN_FLOOR);
  **NO** for undeclared-surface completion claims (validator).
- Residuals: an agent that neither runs pytest nor pushes sees no gate mid-edit (B6); non-geometry
  behavioral code outside governed prefixes (e.g. src/core engine logic) is gated by the invariant
  gate only when governed files are co-touched — extending GOVERNED to the full spine is a future,
  deliberate monotonic step once its floors are green (F-018 burn-down).

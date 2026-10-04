# Model-Layer Rewrite — Tracker

**Living file.** Updated turn-over-turn as the Model-Layer Rewrite + Registry plan
(`docs/implementation_plan/dont-read-codebase-yet-lovely-clarke.md` — the approved plan; also
saved as `C:\Users\Hi\.claude\plans\dont-read-codebase-yet-lovely-clarke.md`) advances. Status
here is re-verified against source at write time, not carried forward from a prior turn's own
report (that gap is exactly what triggered the 2026-09-23 correction below — see the Process
Notes section).

**Mode:** no economic claim, no authority change. `use_bitnet` stays `false` everywhere.
`rr_fusion.enabled` stays `false`. Nothing in this tracker grants production weight to anything
(§6.5 Authority Ladder).

---

## Closure table

| ID | Item | Status | Evidence |
|---|---|---|---|
| K1 | BitNet enable path broken (Gap 1) | ✅ CLOSED | `apply_crt_serve_aliases()` gained the missing 4th alias (`candles_since_retest_state`→`candles_since_sweep`) in `src/bitnet/encoders.py`. Fix landed entirely there — `crt_engine_v2.py` never touched. 3 tests in `tests/test_bitnet_composition.py`. Probe reproduces clean. `active_models.yaml` corrected. |
| K2 | `enc_canonical38_v1` 38/48 mismatch (Gap 2) | ✅ CLOSED | `DEFAULT_INPUT_DIM` (defaults.py) documented as a synthetic/bootstrap backbone-build default, decoupled from the live schema — value unchanged (still correctly 38 for that scope). `Canonical38Encoder` id pinned, docstring corrected, dead no-op branch removed. Guard test (`dim() == len(CANONICAL_FEATURES)`). R2.5-style 38-dim bundle still binds at 38 and still fails closed on a backbone-width mismatch (built by hand — the synthetic-envelope test helper silently auto-corrects a mismatched `feature_names` length, so it can't exercise the real check). 3 new tests, 16/16 in the file, 54/54 across the full bitnet test set. |
| K3 | `CRTGaussianScorer` print() ×2 (Gap 3) | ✅ CLOSED | `src/config_layer/crt_gaussian_scorer.py`: 0 `print(` calls remain, both route through `self._log.debug`. Smoke-verified `compute()` returns identical `score`/`decision`. |
| K4 | Stale v5.0/38-dim schema labels (Gap 4) | ✅ CLOSED | `feature_pipeline.py` (5 refs), `docs/reference/schemas.md` §4.1 (rewritten from live 48-name v6.0 tuple — was worse than scoped, a full stale 39-name/v4.0 table), `docs/topics/feature-schema.md`, `CLAUDE.md` `schemas.md` row. Two remaining "38-dim" strings in `CLAUDE.md` (lines 690/697, 192) checked and confirmed historically/artifact-scoped, not drift (§6.2 rule 4) — left untouched. |
| K5 | Naming collision `L{n}` ×3 (feature-DAG / `layer_trace` / model-id) | ✅ CLOSED | Resolved in plan design: model id uses a distinct `M{tier}_...` prefix, never `L{n}`; `L*_` survives only as a declared `input_dag_layer` field on a registry row. |
| K6 | 14:45 orphan (`RETEST→EXECUTION`, `build_trade` returned `None` on inverted SHORT stop) explainability | open | `BuildAttempt`/`last_build_attempt` patch shipped in a prior session (per the pasted intake summary §2) — recorded, not yet re-observed against a fresh run this session. |
| K7 | Telemetry has no `bar_ts`; keyed by engine index only | open | unchanged |
| K8 | Engine-runtime state surface (`EngineState`) ungoverned — no version, no hash | open | unchanged; blocks Phase 0's `input_schema_hash` field for any model reading raw `EngineState` rather than `cached_features`/canonical vector |
| K9 | Cost model has 4 rulers that don't string-match (`flat_12bps`, `sem015_component_xauusd`, `CM-XAUUSD-COMPONENT-MEASURED-V1`, `component_measured.v1`, …) | open | Note: the pasted intake summary's §5 predates the concurrent session's `CH-measurement-basis-declaration` work (`src/governance/measurement_basis.py`, canonicalises 5 spellings via an alias table) — re-check whether K9 is now narrower or closed once that work lands cleanly (currently mid-flight, not yet re-verified this session). |
| K10 | No Semantic OS noun for any model except partial Gaussian/BitNet | open | unchanged |
| K11 | Governance baseline (`check_governance_invariants.py --all`) | open (tracked, not a blocker) | **Re-run post-Phase-0, confirmed:** 13 failed / 587 passed / 1 skipped — same 13 named failing tests as the original baseline (zero regression); passed count rose by exactly +13, matching `test_model_registry_join.py`'s 13 new tests added to `GREEN_FLOOR`. Exit-code-0-on-FAILED still reproduces (flagged, not asserted as a defect). |
| K12 | JSONL claim catalog needs a `CC-*` class before the Phase 2 shadow stream can assert anything | open | blocks Phase 2, not Phase 0 |
| K13 | RR polarity engine ("candle_structure_quality") vs the naive expectation of "forward reward:risk" — three objects share the name "RR" | open | design-documented in `cozy-pie.md`, not yet re-founded (Phase 5) |
| K14 | Codebase access depth (can Claude actually read/cite real line numbers, real constants, real test files) | ✅ CLOSED | Demonstrated across Gaps 1 and 2: exact line citations, tracing the real call path (`bitnet_score`→`get_default_composition`→`predict`→`apply_crt_serve_aliases`) rather than assuming the plan's framing, catching a test-helper auto-correction that would have produced a false-positive regression test. |
| K15 | "All 4 gaps complete" claim (2026-09-23, Gap-1-focused turn) | ✅ RESOLVED | Was true at 3-of-4 (Gaps 3/4 done in an earlier turn, Gap 1 done that turn) but Gap 2 was still open — the summary line overclaimed. Corrected same session; Gap 2 subsequently closed (K2). |
| K16 | Concurrent-session disjoint-region confirmation before editing `src/config_layer/crt_engine_v2.py` (never needed in the end — Gap 1's fix avoided that file entirely) | ✅ CLOSED | Hunk-boundary analysis: old-file 667-737 / 2287-2517 / 2700-2926 / 3337-3565 vs BitNet call site 2176-2195 — disjoint, confirmed not assumed. |
| K17 | Phase 0 — model registry join (23 models, 3 previously-disjoint surfaces) | ✅ CLOSED | `MODEL_CATALOG` is now the hub (19 rows, code-bound). MIAR (17 entries) + `active_models.yaml` (9 sections) carry `semantic_ids` back-refs. 21 Phase-3 specialist/arbiter rows seeded as `DESIGN_ONLY` with the plan's own `M{tier}_` prefix (not the original `L{n}_` naming, per K5). New floor `tests/test_model_registry_join.py` (13 checks, on `GREEN_FLOOR`) — caught a real bug pre-ship (a one-level-too-shallow `active_models_key` for `gaussian_ml`). Declarative only, grants no authority (§6.5). |

---

## Checklist

### ✅ DONE

| # | Item |
|---|---|
| D1 | Merged 3 precedent design docs (BitNet/Gaussian/RR) into one Model-Layer Rewrite + Registry plan; user approved |
| D2 | User decisions: registry joins existing surfaces (no 5th registry file); model-id prefix is `M{tier}_...`, distinct from `L{n}` |
| D3 | Gap 1 shipped (K1) |
| D4 | Gap 3 shipped (K3) |
| D5 | Gap 4 shipped (K4) |
| D6 | Gap 2 shipped (K2) |
| D7 | Tracker written as a living file (this file) |
| D8 | SESSION LOG entries appended to `assistant_project.md` for every code-touching turn |
| D9 | Governance-floor baseline confirmed byte-identical post-Gap-2 (13/574/1, same 13 named tests, zero regression) |
| D10 | Phase 0 — model registry shipped: `MODEL_CATALOG` (19 rows) gained 7 join fields (`semantic_id`/`tier`/`miar_id`/`active_models_key`/`serve_domain`/`scale_type`/`authority`/`trained_on_schema`); MIAR's 17 entries + 21 new `design_only_concepts` rows (Phase 3 ensemble, not yet built) gained `semantic_ids` back-refs; `active_models.yaml`'s 9 model sections gained `semantic_ids`; new floor `tests/test_model_registry_join.py` (13 checks) added to `GREEN_FLOOR`; docs updated (MIAR §7, the owning topic doc). Caught one real bug pre-ship: `gaussian.trained_registry.v4_mirrored` was one level too shallow (`...entries.v4_mirrored`). |

### ⏳ PENDING

| # | Item |
|---|---|
| P2 | Phase 1 — one model contract (`score(bar_ctx) -> ModelOutput \| Abstain`) |
| P3 | Phase 2 — shadow harness (H1 `layer_trace` evidence-plane rows, H2 per-bar runner) — blocked on K12 (JSONL claim catalog `CC-*` class) for any claim-bearing assertion |
| P4 | Phase 3 — 19 block specialists + L5 temporal tracker + L6 arbiter |
| P5 | Phase 4 — conditional-expectancy table (19 blocks × quartiles = 76 cells, pre-registered, walk-forward, Bonferroni) |
| P6 | Phase 5 — RR/Gaussian/BitNet family re-founds, each gated on its own precedent's Gates/Options |

---

## Process notes

**2026-09-23 — the reporting-gap lesson (from the user's Drift E alert and its resolution).** A
"Slice complete" or "all N items done" claim needs **per-item evidence in the same report**, not
a summary line trusting an earlier turn's work. When a status line covers multiple items, cite
the file/test/probe for each one, every time it's restated — otherwise a reporting gap (evidence
existed, just wasn't re-cited) is indistinguishable from a real overclaim (work never happened).
Applied from this point forward in this tracker: every closure-table row carries its own
evidence column, re-verified against source at write time, not copied from the prior row.

**2026-09-23 — two class-level lessons from Gap 2 specifically:**
1. A "fix the constant" instruction can be wrong about *which* value is wrong. `DEFAULT_INPUT_DIM
   = 38` looked like the same defect as the live-schema staleness fixed in Gap 4, but tracing its
   only 2 call sites (`build_default_backbone_envelope`/`build_default_bitlinear_stages`,
   `TrainerConfig.input_dim`) showed it is a synthetic/bootstrap backbone-build default, never a
   claim about the live canonical schema — the correct fix was documentation, not a value change
   to 48. Verify usage before assuming a numeric mismatch is the same bug twice.
2. A test-helper function can silently defeat the exact regression test it's meant to enable —
   `build_synthetic_bitlinear_envelope()`'s own convenience auto-correction
   (`if len(names) != input_dim: names = [...]`) would have made the first draft of the
   R2.5-bundle-refusal test pass for the wrong reason (never reaching the real fail-closed check
   at all). Caught by actually reading the failure message rather than accepting a green run.

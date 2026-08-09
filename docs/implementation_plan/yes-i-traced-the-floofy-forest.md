# Plan — Restore the repository, then close the real hole map

## Context

You traced the architecture through the semantic documents and produced a 27-hole map,
concluding the implementation spine is more complete than the semantic spine, with the
missing cross-layer **AGREEMENT** object as the deepest hole.

I verified the map against the repository rather than against the prose describing it.
Three things changed:

1. **The map omits the hole that outranks all 27.** The committed repository is not the
   system: half of `src/` was never committed, the entire Semantic OS is untracked, there
   is no CI and no pre-commit hook in the repo, and a clean clone cannot import the
   canonical feature pipeline.
2. **The runtime-authority holes (#14/#15) are largely already fixed.** F-057 and F-058
   were both remediated. Two *different* defects are live in their place.
3. **The semantic-layer holes (#6, #10, #11, #12) are accurate**; #8 is wrong in a way that
   points at a worse defect beside it.

**Decisions taken:** fix the tree first; register the map's corrections as findings.

Intended outcome of this plan: a repository where a clean clone runs, enforcement actually
enforces, and the semantic work of the last weeks exists in git — so that steps 2–6 of the
sequence are worth doing at all.

---

## Part 1 — Verified findings (the corrected hole map)

### HOLE #0 — The committed repository is not the system

| Measure | Value |
|---|---|
| `src/**/*.py` tracked in git | **237** |
| `src/**/*.py` on disk | **476** |
| Never committed | **239 (50.2%)** |
| Untracked paths (expanded) | **1,872** — `docs` 609 · `tests` 282 · `scripts` 268 · `src` 239 · `reports` 122 · `configs` 39 |
| Uncommitted Python | **159,157 lines** |
| Modified tracked files | **160** (+31,336 / −10,131; only ~87 lines are CRLF noise — genuine work) |

Nothing is `.gitignore`d — `git check-ignore` returns nothing for these paths. Confirms and
worsens `project_untracked_tree_divergence.md` (836 untracked / 68 in `src/` on 2026-07-19).

**A clean clone cannot import the feature pipeline.** `src/features/feature_pipeline.py:53`,
committed and unguarded:
```python
from data_ingestion.ohlcv_schema import require_ohlcv_columns, validate_ohlcv_frame
```
`src/data_ingestion/ohlcv_schema.py` is on disk, not tracked. **16 committed files import
never-committed modules** — also `dataset_integrity.py`, `config_validator.py`
(→ `goal_schema`/`goal_validator`), `hypothesis_registry.py`. Sharpest: HEAD's own last
commit (`03c3dbf`, F-069) shipped `src/features/crt_state_resolver.py`, which imports
`features.feature_states` at line 85 — not included in that commit. Active regression.

**No enforcement exists in the repo.** `.github/` is entirely untracked (`git ls-files
.github/` → empty). `scripts/maintenance/check_governance_invariants.py` — untracked.
`.git/hooks/pre-commit` — not installed. **13 of 19 `GREEN_FLOOR` pytest targets do not
exist in the committed tree.** Every "enforced by `tests/…`" claim in CLAUDE.md is currently
an assertion about files a clean checkout does not contain.

**The bootloader documents a tree that isn't in the repo.** CLAUDE.md cites
`state_identity.py:69` as the `VALID_TRANSITIONS` authority; that file is untracked, and
`git show HEAD:src/config_layer/crt_engine_v2.py` still defines `VALID_TRANSITIONS` inline
at line 1076. HEAD and the working tree are two coherent but *different* systems.

**Map holes #1–#4 are mis-stated:** the Semantic OS is not partially built — all five YAMLs,
all four `src/governance/semantic_*.py`, the seed script, and all 182 tests are **100%
untracked**. The "SHIPPED 2026-08-08" markers on PR-2…PR-5 are backed by no commit, and
`CH-semantic-os-v2.completion.json` was never produced.

### Runtime authority — corrected

| Map claim | Verified |
|---|---|
| #15 / F-057 split-brain | **FIXED** — `backtest_v2.py:1739-1748` routes through `load_prod_config_from_registry`; fail-closed provenance gate `:1750-1759`; regression test exists |
| 0.08 vs 0.30 | Values still differ but both in `v2_multi_2026_04.json` (`:980` vs `:11`); merge order resolves 0.30 |
| F-058 `engine_gate_enabled` | **FIXED** — strictly required at `backtest_v2.py:2065-2067` |
| #14 ATR units | **REAL, UNFIXED** |
| #18 live ≠ backtest | **WORSE — there is no live rail** |

**(a) ATR dimensional mismatch, 3 sites.** `compute_crt_levels`
(`src/core/gate_intelligence.py:24-84`) needs price units (`sl = low - sl_atr_buffer * atr`,
`:70`), but canonical `atr` is close-relative (`feature_pipeline.py:906-910`). Fed the ratio
at `live_engine_hook.py:916`, `research/model_runners/adapters/execution_plan.py:279-287`,
`config_layer/execution_planner.py:390,403,406`. On XAUUSD the SL buffer becomes
`0.2 × 0.0025 = 0.0005` instead of `1.0` (~2000× off), inflating `position_size_hint`
identically. Backtest is correct (`crt_engine_v2.py:2201` uses `state.atr_abs`).
*Map correction:* `src/core/execution_planner.py` does not exist; `default_sl_atr_mult` is
absent from `src/` and the active config.

**(b) No live runner exists.** `HookedLiveEngine` (`live_engine_hook.py:688`) is **never
instantiated** — zero constructor calls repo-wide. Its one would-be entry point,
`agent/modes/pipeline_mode.py:160`, imports a class name that does not exist
(`LiveEngineHook` vs `HookedLiveEngine`); the `ImportError` is swallowed at `:167-169`.
So the ATR defect is **latent, not producing loss**. Two structural divergences separate the
paths: ATR semantics, and SL anchor (backtest → displacement candle,
`crt_engine_v2.py:2215/2222`; hook → current candle, `live_engine_hook.py:914-915`).

**Residual on the F-057 fix:** `MultiInstrumentRunner.run_all` (`backtest_v2.py:2932`) copies
a EURUSD-resolved `crt_config` (`:3040-3045`) and only overwrites `cfg.instrument` (`:2937`),
skipping the per-instrument governed load. Masked today because `params` overrides all five
router keys and `instrument_overrides` is absent — one override away from silent breakage.

### Semantic market chain — corrected

| Map claim | Verified |
|---|---|
| #6 — 39 features, 27 without states | **EXACTLY CORRECT.** `feature_schema.py:114`; 12 of 39 vector-bound stateful; remainder already exposed as `FeatureStateEncoder.continuous_features` (`feature_states.py:119-124`) |
| #10 — AGREEMENT missing | **CORRECT.** Six of seven layers are real modules; no AGREEMENT object in `src/` or the ontology. Every `agreement`/`coherence` hit in `src/` is a different concept |
| #9 — shape vocabulary gaps | Vocabulary is **larger than implied**: 8 shapes / 5 families / 4 explicit `blocked_shapes` / an `UNNAMED` identity. The 1/10 unnamed episode is the designed bucket |
| #8 — participation | **PARTLY WRONG.** `volume_spike` is `VolumeSpike` in 5 of 10 census episodes, fed by real MT5 tick volume. The dead channel is **`volume_ma20`** — `gate_intelligence.py:278,284` reads a key no production builder emits, so the documented "Volume spike (50%)" half of `_liquidity_score` is a constant 0.0 |
| F-065 | **CONFIRMED and undercounted** — `volatility_regime` is equally unreferenced across all 9 CRT `when:` blocks; the H8 comment omits it |
| CandleStateEncoder in this ladder | **FALSE** — separate research-only vocabulary, declared as such |

STATE/CONTEXT/SHAPE/TESTIMONY are genuinely shadow-only: no importer in `src/core`,
`src/engines`, `src/runtime`, `src/execution`.

### The map's strongest number — three caveats

"10 episodes / 10 AGREEMENT BREAK" is verbatim correct
(`results/research/xauusd_episode_semantic_reconstruction/phase2_chain_coherence.json:21-52`).
But: (1) **AGREEMENT=BREAK is definitional, not measured** — the same file records
`O14_cross_layer_agreement_object: NOT_IMPLEMENTED`; it is a statement about the ontology,
not the market. (2) **No generator exists** — no `.py` emits `layerwise_describable` /
`integrated_coherent`; hand-authored ad hoc. (3) **It can never be committed** —
`.gitignore:5` ignores `results/`.

The sibling `coverage_census.json` *is* script-generated
(`scripts/research/xauusd_episode_coverage_census.py`, itself untracked) and its O-priority
list is sound. Build on that one; state its n=10 power limit whenever it is cited.

### Semantic OS — measured state

| Registry | Records | Note |
|---|---|---|
| concepts | **15** CN (target ~50) | 9 of 15 on no journey |
| boundaries | **10** BD (target 30–40) | 94 files = 11.0% of the 854-file universe |
| journeys | **1** JN (7 steps, 7/7 resolved) | JN-002…005 do not exist |
| contracts | **7** CT | — |
| file_identities | 98 curated → **854** | **756 (88.5%) `UNKNOWN`** |

PR-6 outstanding (`module_attribution_stubs.jsonl` `UNATTRIBUTED` on **463/463**;
attribution coverage **0/475**). PR-7 outstanding — `semantic_impact.py` does not exist
("Impact is declared, never computed"). PR-8 outstanding — no `test_semantic_*` in
`GREEN_FLOOR`. `semantic_query.py` (611 lines) has **zero tests and no CLI**.
The "behavior_coverage 100% GREEN" headline is a **fake denominator** — 7/7 declared steps
of one journey, with the object-join half hard-coded to `+= 0`
(`coverage_dashboard.py:149`); real `journey_coverage` is **41/849 = 4.8% RED**.

---

## Part 2 — Execution: restore the tree

**Safety preconditions (verified, must hold):**
- HEAD is **clean of the compromised Groq key** (`git merge-base --is-ancestor 278d993 HEAD`
  → false; no `.env` tracked). The two contaminated branches
  (`backup/pre-env-scrub-20260702`, `claude/elegant-dubinsky-a2b441`) stay untouched per
  `project_pending_secret_ref_cleanup.md`.
- Work on the current branch `feature/truth-registry-v2` (6 ahead of its upstream).
- **Never `git add -A`** — `core.autocrlf=true`. Stage explicit path lists per batch.
- **Commit only. Do not push.** Push is outward-facing and needs separate approval.

### Batch order (dependency-ordered; tree stays importable after each)

**B1 — `src/` modules (239 files).** Additive only, no tracked file modified. Resolves
HEAD's 16 broken imports. Includes the 20 collapsed dirs (`src/interpreters/`, `src/msip/`,
`src/research/{adapters,clean_labels,model_runners,episodes,…}`, `src/retrieval/`,
`src/validation_access/`) and the spine modules CLAUDE.md already cites:
`config_layer/state_identity.py`, `state_topology.py`, `state_contract*.py`,
`crt_config_provenance.py`, `model_paths.py`, `model_resolver.py`,
`data_ingestion/ohlcv_schema.py`, `features/feature_states.py`, `features/broker_clock.py`,
`governance/semantic_{os,objects,identity,query}.py`.
*Gate:* import smoke test (below) passes for `features.feature_pipeline`.

**B2 — the 160 modified tracked files.** Their worktree copies import 35 untracked modules,
all landed in B1. Includes `crt_engine_v2.py`, `config_builder.py`, `production_config.py`,
`market_router.py`, `engine_runner.py`, `CLAUDE.md`, `active_models.yaml`, the configs.
*Gate:* import smoke test still passes; `git diff --stat` reconciles to 0 modified.

**B3 — `tests/` (282) + `scripts/` (268).** Brings the 13 missing `GREEN_FLOOR` targets and
the 182 semantic-OS tests into the repo.
*Gate:* `pytest` collects without import errors on the GREEN_FLOOR set.

**B4 — enforcement.** `.github/workflows/{governance,erp-test-harness}.yml`,
`scripts/maintenance/check_governance_invariants.py`, then install `.git/hooks/pre-commit`
calling the same script (hook/CI parity is the script's stated design constraint).
*Gate:* `python scripts/maintenance/check_governance_invariants.py --all` runs green **from
a clean worktree checkout**, not from this directory.

**B5 — `docs/` (609) + `configs/` (39).** Includes `docs/governance/semantic_os/*.yaml`, the
design + contract docs, and the coverage dashboard.
*Gate:* `seed_semantic_os.py --check` valid; `test_doc_citations.py` green.

**Excluded by `.gitignore`, intentionally:** `results/` (122 reports incl. the episode
artifacts), `data/`, `context/`, `logs/`. The Semantic OS projection under
`data/semantic_os/` is GENERATED and correctly stays out — the YAMLs in B5 are its source.

### Verification (end-to-end, must run from a clean checkout)

```bash
git worktree add /tmp/tl-verify HEAD && cd /tmp/tl-verify && pip install -e . && python -c "import features.feature_pipeline, config_layer.crt_engine_v2, governance.semantic_os; print('IMPORT OK')"
```

```bash
python scripts/maintenance/check_governance_invariants.py --all
```

```bash
python scripts/governance/seed_semantic_os.py --check
```

Additionally: re-run the AST import-integrity check (scratchpad `imp2.py`) — it must report
**0 HEAD blobs importing an untracked module** (currently 16).

### Findings to register (same turn as the commits, per §6.2 Findings Mandate)

Add to `docs/current-findings.md` + the CLAUDE.md Repository Truths Index:

- **F-071 GOV** — committed tree ≠ system; 239 uncommitted `src` modules, 16 committed files
  with unresolvable imports, zero active enforcement. Evidence: counts above.
- **F-072 ARCH** — no live rail: `HookedLiveEngine` never instantiated; sole entry point
  imports a nonexistent class name. Supersedes the "live vs backtest equivalence" framing.
- **Correct F-065** — add `volatility_regime` as a second unreferenced declared state.
- **Correct the participation claim** — `volume_spike` is live and nonzero; `volume_ma20` is
  the structurally-dead channel (`gate_intelligence.py:278,284`).
- **Annotate F-057/F-058 as RESOLVED** with the residual `MultiInstrumentRunner` bleed named
  as a separate open item.
- ATR unit mismatch stays open and unfixed — a behavior-change decision, out of scope here.

Then update memory: `project_untracked_tree_divergence.md` (new counts + resolution) and
`project_atr_dimensional_mix_sltp.md` (add: latent, no live caller).

---

## Part 3 — Sequence after the tree is fixed

The map's step 1 is done and its step 7 is not reachable. Corrected:

```
0. Commit the tree + restore enforcement      <- this plan
1. Live-rail decision: ATR units + dead entry point
2. VALUE -> STATE bands   (O6 body, O7 atr, O18 momentum)
3. Episode semantics      (O11 dir-vs-context, O16 temporal)
4. AGREEMENT object       (O14, O12)
5. Semantic OS PR-6/7/8   (attribution, semantic_impact, GREEN_FLOOR hooks)
6. Research seal          (Measurement Contract probes)
```

Step 1 is a genuine fork, not a bug fix: with no live caller, the choice is *repair the live
rail* or *formally retire it and make backtest the only rail*. That decision should be made
explicitly rather than inherited.

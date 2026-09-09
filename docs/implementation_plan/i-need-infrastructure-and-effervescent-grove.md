# Plan — Tradelatest Infrastructure & Architecture Map

**Deliverable:** one published HTML Artifact — full technical map, rendered flow diagrams.
**Repo writes:** none, except the mandated SESSION LOG entry after your approval.

---

## Context

You asked for the infrastructure and architecture of the entire codebase, with flow diagrams.

The repo has ~35 architecture docs, so the first thing I checked was whether this already exists.
It does not, and the gap is structural:

- **The two "master reference" docs have no diagrams.** `docs/architecture/three-layer-codebase-atlas.md`
  (654 lines, self-declared "Master Reference") and `codebase-wiring-guide.md` (380 lines) are
  ASCII-only. The real Mermaid lives in a 2,312-line machine-generated file (`code-map.generated.md`,
  39 diagrams — not readable as narrative) and a 584-line HTML page needing a network CDN.
- **Three mutually inconsistent module counts are live in the docs right now**: 206/31, 351/36,
  504/38. Measured actual: **596 `.py` files across 40 code packages**.
- **15 architecture docs are anchored to `v2_multi_2026_04`**; this branch's `ACTIVE_VERSION` is
  **`v2_htfcrt_2026_08`**. Both are true — truth is branch-scoped (§6.2 rule 7), and `patch` really
  does hold `v2_multi_2026_04` (`git show patch:configs/production/ACTIVE_VERSION`) — but no doc
  states which branch it describes, so a reader cannot tell.
- **Infrastructure proper has no home**: process topology, the control plane, storage layout, the
  JSONL/Parquet artifact tree, CI, and the tracked-vs-local boundary are nowhere consolidated.

So this is the missing top-level entry point. It does not replace any existing doc; it routes into
them.

---

## Measured baseline (verified this session, from source — not from docs)

| Fact | Value |
|---|---|
| `src/` Python / LOC | **596 files · 148,294 LOC** across **40 code packages** |
| Largest packages | `research` 200f/41k · `config_layer` 34f/13k · `governance` 29f/12k · `features` 42f/11k · `runtime` 15f/8.4k |
| scripts / tests | 409 script files · 535 test files (363 at `tests/` root + 27 subdirs) |
| Active config | `v2_htfcrt_2026_08`, 46 top-level sections |
| Registered, not promoted | `v3_unified_market_structure_2026_09` (49 sections), `v4_crt_sot_2026_08` |
| Production configs on disk | 25 JSON (incl. archived + shadow) |
| Feature schema | **v5.0, 48 canonical dims** (`CANONICAL_FEATURES` imported and counted) |
| Control-plane commands | **44** `CommandSpec` · HTTP on `127.0.0.1:8787` |
| Agent surface | **36** registered tools · **22** `PLAN_REGISTRY` intents (docstring says 14 — stale) |
| Data footprint | `logs/` 26 GB · `results/` 16 GB · `data/` 1.6 GB · `models/` 459 MB · **3,549 `.jsonl`** |
| Git boundary | 3,133 tracked · **60 of 596 `src/*.py` untracked** · 779 untracked overall |
| CI / gates | 2 workflows · 2 hooks · **25 GREEN_FLOOR targets** (`check_governance_invariants.py:78`) |
| Dependencies | **zero base deps**; 5 optional extras; 10 pytest markers; `requires-python >=3.10` |
| Interpreters | `venv/` = 3.12.10 (intended) · `.venv/` = 3.14 (stray) · CI pins 3.10 |

Every number in the artifact comes from this table or from source. Nothing from the older docs.

---

## Spine trace (verified from source)

The trace corrected several locations the existing docs get wrong — worth recording:

| Thing | Actually at | Docs said |
|---|---|---|
| Live hook | `src/runtime/live_engine_hook.py:817` (`HookedLiveEngine.process`) | `src/inout/` |
| Live orchestrator | `src/runtime/live_rail_orchestrator.py:65` | `src/live/` |
| `CandleLoader` | `src/runtime/backtest_v2.py:723` | `src/data_ingestion/` |
| `ExecutionPlannerV1_2` | `src/config_layer/execution_planner.py:132` | `src/execution/` |
| `CRTState` | **12 members**, generated into `config_layer/_crt_state_generated.py:27` from `active_models.yaml` | 9, hand-authored |

**Shared decision core, both rails:** `EngineRunner.run` (`src/core/engine_runner.py:640`) — 9 steps:
adapter → 4 engines → completeness (`EXPECTED_ENGINES`, `:827`) → fusion (`:856`) → score floor →
belief gate → regime gate → `DecisionEngine.evaluate` (`:1049`, sole emitter of execute/reject) →
telemetry. Backtest reaches it at `backtest_v2.py:2824` (optional, `backtest.engine_gate_enabled`);
live at `live_engine_hook.py:993` (always).

**`src/execution/` is imported only by tests** — a parallel, never-constructed execution
architecture. The real live path is `HookedLiveEngine.process` + `LiveRailOrchestrator`.

**Three feature-construction paths bind to one 48-dim schema**: `FeaturePipeline.run` (backtest,
pandas), `FeatureStore.process` (live hook), `LiveRailFeeder._ensure_features` (re-runs the full
pipeline per bar, then the hook re-validates through `FeatureStore`). Only
`feature_schema.CANONICAL_FEATURES` holds them together. This gets its own diagram.

**Reachability** (static AST closure from 4 entrypoint roots): **178 of 596 modules (30%)**.
Caveat that must appear in the artifact: the control plane launches commands as *subprocesses*, so
governance/training/analysis modules reachable only via `CommandSpec.script` are **"sidecar,
invoked"**, not dead. Genuinely dead: `src/ui/` (0 LOC), `src/execution/`, `src/portfolio/`,
`src/feedback/`, `src/search/`.

---

## Artifact structure

Single page, `<title>Tradelatest Architecture</title>`, section nav, theme-aware, Mermaid rendered
natively. ~6 diagrams at three zoom levels.

1. **System at a glance** — what it is, the measured baseline, and pointers into existing docs.
2. **Runtime spine: candle → order** — the primary swim-lane diagram over the real call chain,
   annotated *live* / *config-gated off* / *built but unwired*, with `path:line` per lane.
3. **Backtest vs live: two entry paths** — side-by-side, showing that the spine forks after
   `DecisionEngine` (planner + risk gate live in the caller), the fail-open backtest gate
   (`backtest_v2.py:2856`) vs fail-closed live (`live_engine_hook.py:857`), and that there is no
   production live rail (F-073 — paper/TickDB only, and `live_rail` is absent from the active config).
4. **Feature construction** — the three paths into one 48-dim schema.
5. **Infrastructure & process topology** — what actually runs: control plane (stdlib
   `ThreadingHTTPServer`, 8787, 44 commands, `JobManager` subprocess supervisor), health checker
   (8788, the Docker CMD), agent REPL, live-rail asyncio loop, Streamlit sidecar. Plus every
   external integration and its import guard.
6. **`src/` module inventory** — all 40 packages: files, LOC, role, and a **status column**
   (live / sidecar-invoked / sidecar-by-design / dead). No existing doc has this correctly.
7. **Configuration & promotion flow** — Tier-0 → validator → `PromotionManager` → `ACTIVE_VERSION`,
   the 46-section anatomy, hash rules.
8. **Data & persistence** — JSONL as system of record, the Parquet projection contract, `models/`
   registries, the `src/identity/` 7-layer store, and the tracked-vs-local boundary.
9. **Build, test, CI** — 2 workflows, 2 hooks, 25-target GREEN_FLOOR vs the full suite (known reds,
   explicitly not the gate), markers, the three-way interpreter split.
10. **Known drift & open observations** — everything below, stated with evidence.

---

## Two findings to surface (report, don't fix)

### A. 60 `src/` modules are untracked, including load-bearing ones — F-071 has recurred

Verified first-hand:

- `src/config_layer/state_identity.py:71` does `from config_layer._crt_state_generated import (...)`
- `git ls-files src/config_layer/_crt_state_generated.py` → **0 rows** (and `git check-ignore` says
  it is **not** ignored — it is simply missing from the commit)
- Also untracked: `src/data_ingestion/corpus_gate.py` (called by `_preflight_dataset`),
  `src/governance/semantic_grounding.py` (the §6.7 grounding tool CLAUDE.md mandates), and the
  **entire `src/identity/` package** (Phase 3/4 physical storage)

A fresh clone of this branch cannot import `state_identity` → no `CRTState` / `VALID_TRANSITIONS` →
the CRT spine will not load. This is the exact F-071 failure mode ("the committed repository was not
the running system"), marked RESOLVED 2026-08-09 and now recurred at 60 modules.

I am **not** committing anything — memory notes ~15 concurrent Claude sessions on this repo and
`git add -A` is explicitly banned. This is yours to decide; the artifact states it as an observation.

### B. Config-declared fusion weights never reach behavior

- `EngineRunner.__init__` strictly reads `weight_crt/gaussian/zone_gate/rr` into `FusionConfig`
  (`src/core/engine_runner.py:423-427`); active config declares `0.40/0.20/0.20/0.20`
- It does **not** pass `regime_fusion_weights`, so the hardcoded `default_factory` table stands
  (`src/core/fusion_engine.py:161-169`)
- `EngineRunner.run` **always** calls `compute(..., regime=current_regime)` (`:856`)
- `compute()` prefers the regime table whenever `regime=` is passed (`fusion_engine.py:324-329`)
- `grep -c regime_fusion_weights configs/production/v2_htfcrt_2026_08.json` → **0**

Per §6.8 I am **not** calling this a defect — the `compute()` docstring documents this priority
order, so the mechanism is intentional. What is notable is config declaring tunable weights that
never reach behavior: the exact F-056 lesson. Candidate verdicts `CONFIRMED DEFECT` (config-illusion
class) or `DOCUMENTATION GAP`. Adjudication is a separate authorized turn.

---

## Explicitly out of scope

- **No repo files modified.** Artifact only — so no new `docs/architecture/` file and no new
  `tests/test_doc_citations.py` surface.
- **Not fixing the stale docs.** Reported in §10 and in my closing message. Correcting
  `code-map.md` / `codebase-wiring-guide.md` / the version anchors touches registered conclusions,
  so it is a gated decision (§6.2 Drift Protocol), not an auto-fix.
- **Not regenerating `code-map.generated.md`.** `python scripts/analysis/gen_code_map.py` would
  refresh the 39 Mermaid slices and `module-roles.generated.md`, currently ~92 modules behind — the
  cheapest correctness win available, but it writes to the repo. Offered, not done.
- **Not touching the untracked-file situation** (finding A).

---

## Verification

1. **Numbers** — re-run the measured-baseline commands; every figure in the artifact must be
   reproducible from that table.
2. **Citations** — for each `path:line`, confirm the symbol is at that line (`sed -n 'N,+3p'`);
   spot-check the spine chain end to end.
3. **Rendering** — open the published URL; confirm every Mermaid diagram renders, the page reads in
   both light and dark, and the body does not scroll horizontally.
4. **Honesty pass** — anything not confirmed by an actual trace is marked `UNVERIFIED` rather than
   guessed (§1.1). The §6 status column is the highest-risk content and gets this treatment.
5. **Session log** — append the `📝 SESSION LOG ENTRY` block to `assistant_project.md` (§6). The one
   repo write, after approval.

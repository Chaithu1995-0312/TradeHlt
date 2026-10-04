# Concatenated implementation plans — part 5 of 10

Source directory: `docs/implementation_plan/`
Files in this part: 16

## Contents

1. `here-s-a-tabular-summary-jaunty-mountain.md` (5112 bytes)
2. `historical-zone-mapping-pipeline-design-2026-07-20.md` (9829 bytes)
3. `i-have-an-llm-jiggly-torvalds.md` (10022 bytes)
4. `i-remember-e-have-silly-forest.md` (5819 bytes)
5. `i-studied-the-materials-recursive-phoenix.md` (16983 bytes)
6. `i-ve-now-read-all-gentle-riddle.md` (8678 bytes)
7. `i-want-to-check-graceful-fog.md` (15150 bytes)
8. `i-zoomed-into-the-soft-whale.md` (13119 bytes)
9. `ignore-governance-no-defaults-compiled-music.md` (8298 bytes)
10. `ill-share-two-prompts-moonlit-key.md` (10277 bytes)
11. `in-the-tradelatest-repo-piped-gem.md` (2878 bytes)
12. `intelligence-compounding-doctrine-core-crystalline-walrus.md` (9328 bytes)
13. `is-codebase-dirty-elegant-planet.md` (15512 bytes)
14. `label-back-to-spine-research-descriptio-serene-conway.md` (8045 bytes)
15. `label-repo-maintenance-description-pay-validated-summit.md` (6758 bytes)
16. `lets-generate-pyan-dot-streamed-hare.md` (5383 bytes)


================================================================================
SOURCE_FILE: docs/implementation_plan/here-s-a-tabular-summary-jaunty-mountain.md
SOURCE_BYTES: 5112
PART: 5/10 FILE 1/16
================================================================================

# Close the two residual gaps in the feature-pipeline config migration

## Context

The Phase-A/Phase-B `feature_pipeline` config migration (2026-07-18/19) is
substantially complete: 40 keys in `configs/production/v2_multi_2026_04.json`
under a three-tier risk taxonomy, strict `_require_fp_cfg()` enforcement (no
silent defaults), ontology formula strings synced with `<feature_pipeline.X>`
placeholders + `config_key`/`config_keys` fields, and `swing_window` made
config-derived via a PEP 562 lazy module attribute that preserves the nine
existing `from features.feature_pipeline import SWING_WINDOW` call sites
without creating a `features -> config_layer` import cycle.

A source walkthrough found two residuals. Neither causes divergence *today*
(both current values happen to equal the config values), but both are latent
split-brains of exactly the class §6.5's hard rule exists to eliminate.

## Gap 1 — `double_sweep_window` is not threaded to the live path (T-7)

`src/core/feature_store.py:141` calls `causal_structure_at_bar(...)` with only
`liquidity_sweep_history`, so live falls back to the module default
`_DOUBLE_SWEEP_WINDOW_DEFAULT = 5`. Batch uses
`self._fp_cfg["double_sweep_window"]` (`feature_pipeline.py:800`). The pipeline
already carries a comment admitting this (lines 793-800).

Config is currently `5`, so batch == live. Changing the config moves batch only.

**Fix:** resolve the value from config at the `feature_store.py` call site and
pass it through, mirroring how `causal_structure._resolve_k` handles
`swing_window` — a deferred function-local import, `None` meaning "resolve from
config". Prefer adding a `_resolve_double_sweep_window(w: int | None) -> int`
helper in `causal_structure.py` and defaulting the parameter to `None`, so the
resolution rule lives in one module rather than being duplicated at each caller.
Keep the explicit-arg-wins semantics.

Then delete the now-stale `feature_pipeline.py:793-800` comment.

## Gap 2 — hardcoded `swing_window` provenance literal in the census

`resolve_swing_window()`'s docstring states the provenance rule: every
governance/certification script recording a `swing_window` fact MUST resolve it
through that function, never re-declare the literal — so an artifact can never
assert a value the pipeline did not use.

`scripts/analysis/feature_38_lineage_census.py` violates it in the `swing_high`
and `swing_low` entries (lines ~275, ~278, ~286, ~289):
- `"formula": "... k=SWING_WINDOW=2"`
- `"impl_refs": [..., "SWING_WINDOW=2"]`

**Fix:** import `SWING_WINDOW` from `features.feature_pipeline` (the PEP 562
attribute already returns the config value) and interpolate it, matching the
pattern the other 8 script call sites already use — e.g.
`scripts/analysis/phase1_run1_feature_truth.py:480` builds its formula string
with an f-string over the imported symbol. The remaining 8 call sites are
already correct and need no change.

## Files to modify

- `src/core/feature_store.py` (call site, ~line 141)
- `src/features/causal_structure.py` (add `_resolve_double_sweep_window`, change
  `double_sweep_window` default to `None` on both public functions)
- `src/features/feature_pipeline.py` (remove stale comment, lines 793-800)
- `scripts/analysis/feature_38_lineage_census.py` (4 literal sites)

## Verification

1. **Parity floor (the decisive check):** `pytest tests/test_fc1a_swing_causal.py`
   — `test_fc1a_swing_causal.py:296-302` already compares the live
   `causal_structure_at_bar` output against the batch binding. This is the test
   that would catch a bad thread-through.
2. `pytest tests/test_feature_pipeline.py tests/test_candle_math.py tests/test_formula_registry.py tests/test_feature_dag_structural_certification.py`
   — the last one contains `test_double_sweep_window_boundary_semantics`.
3. `pytest tests/test_behavior_census.py` — pins per-module config maturity so a
   knob cannot drift back into code.
4. **Divergence proof (the point of the exercise):** temporarily set
   `feature_pipeline.double_sweep_window` to `3` in a scratch config copy,
   confirm batch AND live both move together, then revert. Before the fix only
   batch moves. Do not commit the scratch config.
5. Re-run the census: `python scripts/analysis/feature_38_lineage_census.py` and
   confirm the emitted artifact reports `k=2` sourced from config rather than a
   baked literal.

## Notes / non-goals

- **`src/features/causal_structure.py` is currently untracked (`??` in git
  status)** despite carrying the FC1-A contract that both the parity tests and
  the live `FeatureStore` depend on. Worth committing before any branch
  operation. Flagging, not acting on it, without your say-so.
- Hash-neutral: no `params`-block edit, so no `_compute_hash.py` re-run needed.
- `PRODUCTION_BEHAVIOR_CHANGED = NO` — config values equal current effective
  values byte-for-byte; this closes a latent divergence, it does not change
  today's output. Ledger must stay byte-identical.
- Grants no authority (§6.5): threading a knob to live is tunability, not
  evidence. No promotion, no re-certification implied.


================================================================================
SOURCE_FILE: docs/implementation_plan/historical-zone-mapping-pipeline-design-2026-07-20.md
SOURCE_BYTES: 9829
PART: 5/10 FILE 2/16
================================================================================

# Design: Historical Zone Mapping Pipeline

**Date:** 2026-07-20  
**Status:** **P1a + P1a.5 + full-corpus census IMPLEMENTED**. Baseline geometry: `results/zone_maps/xauusd_phase1_zone_census.{json,md}`. Join / ER precomputed source still pending. Grants no production admission authority.  
**Depends on:** ZoneGate audit (§6 model-integration), semantic rename `zone_cluster_threshold`  
**Authority:** architecture / research tooling  
**Code:** `src/research/zone_mapping/historical_zone_mapper.py` · `collect_trade_opened_features.py` · `src/engines/zone_cluster_score.py` · floors `tests/test_historical_zone_mapper.py` + `tests/test_historical_zone_mapper_corpus_parity.py`

---

## 1. Problem

Today zone scoring is **entangled** with Spine B admission:

```text
CRT TRADE_OPENED → Feature snapshot → EngineRunner → run_zone_gate_engine → …
```

Consequences:

| Pain | Why |
|---|---|
| Cadence mismatch | Zone runs only on candidates, not every bar |
| Hard to attribute | Cannot ask “was this bar in zone Z before CRT fired?” without replaying ER |
| Tests couple CRT + fusion | Any zone unit test needs TRADE_OPENED path or synthetic ER |
| Naming confusion | Zone cluster score lived next to BitNet branding (now `zone_cluster_threshold`) |
| F-036 inertness opaque | Weight ablations cannot separate pre-mapping from fusion blend |

**Goal:** compute **zone assignment for every bar** as a pure, pre-CRT artifact, then let CRT / fusion **join** (not re-discover) that map.

---

## 2. Separation of concerns

```text
┌─────────────────────────────────────────────────────────────┐
│  HISTORICAL ZONE MAPPING PIPELINE (new; offline / pre-pass) │
│  FeaturePipeline vectors × zone_registry                    │
│       → per-bar zone assignment series                      │
│  NO CRT · NO Fusion · NO DecisionEngine                     │
└───────────────────────────┬─────────────────────────────────┘
                            │ artifact (JSONL / parquet / memmap)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  CRT candidate generation (unchanged Spine A)               │
│  OHLCV → CRTEngine → TRADE_OPENED                           │
└───────────────────────────┬─────────────────────────────────┘
                            │ join on timestamp
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Admission / research consumers                             │
│  EngineRunner (optional: read precomputed score)            │
│  Attribution / ablations / RB benchmarks                    │
└─────────────────────────────────────────────────────────────┘
```

**Invariant:** Mapping pipeline must be runnable with `CRTEngine` and `EngineRunner` **imported zero times**.

---

## 3. Semantic objects

### 3.1 Inputs

| Input | Authority |
|---|---|
| OHLCV CSV / candle frame | same corpus as backtest |
| `FeaturePipeline.run()` → 38-dim vectors + timestamps | freeze pin / schema v3 |
| `models/zone_registry.json` | runtime registry (manifest parity) |
| Config knobs | `zone_gate.top_k`, `cluster_min_n`, `cluster_spread_max`, **`zone_cluster_threshold`** |

### 3.2 Per-bar output record (proposed)

```json
{
  "timestamp": "2025-01-15 10:30:00",
  "instrument": "XAUUSD",
  "bar_index": 12345,
  "best_zone_id": "zone_3",
  "best_zone_score": 0.612,
  "top_zone_ids": ["zone_3", "zone_1", "zone_0"],
  "top_scores": [0.612, 0.58, 0.55],
  "cluster_score": 0.591,
  "passed_cluster_threshold": true,
  "zone_cluster_threshold": 0.25,
  "registry_sha256": "e73e0893…",
  "feature_schema_dim": 38,
  "schema_version": "zone_map_v1"
}
```

| Field | Meaning |
|---|---|
| `best_zone_*` | argmax similarity (BitNetZoneGate.check best) |
| `top_*` | top_k for cluster aggregation |
| `cluster_score` | `compute_weighted_cluster_score(top_scores, spread_max)` — **same math as ER** |
| `passed_cluster_threshold` | `cluster_score >= zone_cluster_threshold` |
| `registry_sha256` | bind artifact to registry file |

**Not stored as economic label:** zone `meta.mean_rr` / SL rates (F-041B contaminated). Geometry only.

### 3.3 Artifact layout (proposed)

```text
results/zone_maps/
  {instrument}_{tf}_{start}_{end}_zone_map_v1.jsonl
  {instrument}_{tf}_{start}_{end}_zone_map_v1.meta.json
```

Meta: registry path + sha, feature schema hash, config knobs, row count, pipeline git/code pin.

---

## 4. Module placement (when implemented)

| Piece | Path | Notes |
|---|---|---|
| Pure scorer reuse | `engines/zone_gate_engine.py` + `live_engine.BitNetZoneGate` | **no formula fork** — call existing functions |
| Batch driver | `src/research/zone_mapping/historical_zone_mapper.py` | research package; not spine |
| CLI | `scripts/research/build_historical_zone_map.py` | thin wrapper |
| Join helper | `src/research/zone_mapping/join_candidates.py` | ts-align TRADE_OPENED → map row |
| Tests | `tests/test_historical_zone_mapper.py` | synthetic vectors + golden 3 bars |

**Do not** put production admission logic under `scripts/` only; research driver OK if pure batch.

---

## 5. Algorithm (byte-parity target with EngineRunner zone stage)

For each bar `i` with feature dict `F_i` (canonical 38 keys):

```text
1. filter_canonical_inputs(F_i)
2. vector = _extract_vector(F_i)
3. check = BitNetZoneGate.check(vector)   # top_scores, best score/id
4. if len(top_scores) >= cluster_min_n:
       cluster = compute_weighted_cluster_score(top_scores, spread_max)
   else:
       cluster = check["score"]
5. passed = cluster >= zone_cluster_threshold
6. emit record
```

**Parity proof (required before any ER wire):**  
On a fixed TRADE_OPENED set, `cluster_score` and `passed` from the map must match `engine_results["zone_gate"]` score / hard pass under identical registry + knobs (hash-equal floats within 1e-9).

---

## 6. Consumers (phased)

| Phase | Consumer | Behavior change? |
|---|---|---|
| **P0 Design** | this doc | no |
| **P1 Build map** | CLI batch on XAU/BNB windows | research artifact only |
| **P2 Attribution** | join CRT candidates → zone_id distribution, confusion with RETEST | research |
| **P3 Ablation** | counterfactual “would pass threshold?” without ER | research |
| **P4 Optional ER read** | EngineRunner loads map by ts instead of recompute | **behavior-neutral only if parity-proven**; config flag `zone_gate.source = live|precomputed` |

Default production remains **live recompute** until P4 parity + user approval.

---

## 7. Testing strategy (why separation helps)

| Test class | Without map | With map |
|---|---|---|
| Registry geometry unit | needs ER or hand vectors | mapper on synthetic 38-vecs |
| Threshold sweep | full backtest | map once, re-threshold offline |
| CRT funnel × zone | coupled | CRT ledger ⨝ map on ts |
| Feature freeze pin | unrelated | map rebuild when registry or schema changes |

**Determinism:** same CSV + registry sha + knobs → byte-identical JSONL (sort stable).

---

## 8. Explicit non-goals

- Not a new zone training / KMeans pipeline (uses existing registry).  
- Not fixing DE `zone.valid` wiring (MI-ZG-01) — orthogonal.  
- Not claiming ΔG001 or economic edge (F-036 / F-041B stand).  
- Not replacing FeaturePipeline.  
- Not writing zone scores into the 38-dim canonical vector (would be a schema program).

---

## 9. Config surface (future)

```json
"historical_zone_mapping": {
  "enabled": false,
  "registry_path": "models/zone_registry.json",
  "output_dir": "results/zone_maps",
  "zone_cluster_threshold": 0.25,
  "zone_gate": { "top_k": 3, "cluster_min_n": 2, "cluster_spread_max": 0.15 }
}
```

Until P1, knobs can be CLI flags mirroring `engine_runner` (no silent defaults: strict require).

**Naming:** always `zone_cluster_threshold` — never reintroduce BitNet for this quantity.

---

## 10. Implementation plan (next steps when authorized)

1. **P1a** — `HistoricalZoneMapper.map_frame(df_features) -> list[dict]` pure function.  
2. **P1b** — CLI + meta sha binding.  
3. **P1c** — parity test vs EngineRunner zone stage on ≥1 TRADE_OPENED fixture.  
4. **P2** — join script for existing runtime benchmark / CRT funnel artifacts.  
5. **Stop** — user decides P3/P4.

---

## 11. Success criteria

| Criterion | Measure |
|---|---|
| Decoupling | mapper import graph excludes `crt_engine_v2`, `decision_engine` |
| Parity | max |score_map − score_ER| < 1e-9 on fixture set |
| Attribution | can tabulate zone_id × CRT state without re-running fusion |
| Naming | only `zone_cluster_threshold` in new code |

---

## 12. Related artifacts

| Doc | Role |
|---|---|
| `docs/analysis/model-integration-audit-2026-07-20.md` §6 | ZoneGate ER path |
| `docs/analysis/backtest-runner-runtime-call-graph-2026-07-20.md` | when zone runs today |
| `docs/governance/zonegate_lineage_audit.md` | registry lineage |
| Rename floor | `tests/test_zone_cluster_threshold_rename.py` |

---

*End of design. Implementation requires explicit user go-ahead for P1.*


================================================================================
SOURCE_FILE: docs/implementation_plan/i-have-an-llm-jiggly-torvalds.md
SOURCE_BYTES: 10022
PART: 5/10 FILE 3/16
================================================================================

# Trade-Mining System Prompt for the CRT Episode Trace

## Context

The user has an external LLM (a separate chat surface, not Claude Code) that can be handed the
files in `results/crt_episode_trace/20260813T124158Z/` as attachments. They want a **system
prompt** to paste into that LLM so it performs "trade mining" over those sources.

The problem this solves: that folder is ~1.3 MB across 12 files, four of which are 260–314 KB
per-bar walkthroughs with heavily repeated 39-feature ledgers. Dropped into an LLM cold, the
model will linearly chew the biggest files, blow its context on repeated feature tables, and
produce vague narration. It also has no way to know what A0/A3 mean, that the two arms are
confounded, or which numbers are engine-emitted vs recomputed. The system prompt has to carry
that map.

**User decisions (from clarification):** all four analysis jobs in scope (diagnose the no-trade
chain, mine setup patterns, audit the trace, explain the mechanism in plain language);
**no governance rails** (no E-001 / Authority Ladder / evidence-class jargon, no repo governance
vocabulary); **markdown report only** (no §3 handoff block, no JSON).

> One flag, then proceeding as specified: with no rails, this prompt's output is not safe to
> paste back into findings/docs unvetted — an LLM handed 47 bars will readily produce
> confident-sounding edge claims from n=2. The prompt keeps a single plain-analyst line ("every
> number you cite must appear in one of the attached files") because a prompt without it yields
> unusable output, but that is hygiene, not governance framing. Vetting the output stays manual.

## Deliverable

One new file: `multi_llm/research_lane/prompts/TRADE_MINING_SYSTEM_PROMPT.md`

Chosen over `ChatGpt  workflow/Agents Prompts/` (that dir holds only `.docx` role cards, and its
literal name has a double space that breaks paths). `multi_llm/research_lane/prompts/` already
holds exactly this kind of artifact — a hand-carried prompt template — see the existing
[PLAN_DESIGN_PROMPT.md](multi_llm/research_lane/prompts/PLAN_DESIGN_PROMPT.md), whose format
(H1 title → blockquote provenance line → `---`-separated sections → tables for structure) this
file matches.

The prompt is written **generic over any `results/crt_episode_trace/<RUN_ID>/` folder**, with the
`20260813T124158Z` run's values as the worked example, so it stays reusable when the trace is
regenerated.

## Structure of the prompt file

| Section | Content |
|---|---|
| Role | Analyst reading a read-only forensic trace of one trading engine's decisions. States that the engine is not modifiable from this seat and nothing here is a live order. |
| What you were given | The 12-file map + **reading order** (see below). This is the highest-value section. |
| How to read the domain | CRT state machine vocabulary, the gate chain, the two arms, the SL formula. |
| Four jobs | The four analyses, each with its own output contract. |
| Traps in this data | Six concrete gotchas that will otherwise produce wrong conclusions. |
| Output format | A fixed markdown skeleton. |

## Content the prompt must encode

### Reading order (routing — prevents context burn)

1. `journeys.md` (6.5 KB) — the whole story; read first, completely.
2. `proof_*.md` (1–2 KB × 4) — the SL arithmetic with engine-parity check.
3. `operands.csv` (2.5 KB) — every SL input with its source.
4. `bars.csv` (23 KB, 47 rows, 74 cols) — the tabular spine; use this for anything comparative.
5. `episodes.json` (95 KB) — machine mirror of the above; use only to resolve a disagreement.
6. `episode_*_{A0,A3}.md` (260–314 KB × 4) — **sample, never read linearly.** Per-bar sections
   are `## BAR nn <ts> [state_before → state_after] action=X`; the 39-feature ledgers appear only
   on decision bars, inside `<details>` blocks. Jump to `## BAR` headers with `***DECISION BAR***`
   and to the tail sections `### SL operands` / `### Execution geometry` / `### Engine-parity proof`.

### Domain facts

- **Instrument/scope:** XAUUSD M15, broker-local timestamps, source
  `data\XAUUSD_M15_20260807_203705.xlsx` (sha256 `74f04a43…`), `active_version v2_multi_2026_04`,
  feature schema v4.0 (39 canonical features).
- **Two episodes only:** `2026-07-22 19:15:00 SHORT`, `2026-07-28 05:45:00 LONG`. Bars 60–73
  rendered per episode.
- **CRT sequence:** `RANGE → SWEEP → DISPLACEMENT → (EXPANSION) → RETEST → EXECUTION`. The trace
  starts at the SWEEP that opened each episode.
- **Gate chain** (this is the diagnostic backbone):
  `RETEST_CONFIRMED → soft-conf score → shadow age-decay → zone → SESSION → shadow advisory → build_trade → SL guard`.
- **Arms:** `A0` = production config as-is; terminal `FILTER_REJECTED` at SESSION
  (`off_session:OFF_SESSION`) — so `build_trade` is never reached and the SL geometry is
  invisible. `A3` = `session_windows` overridden open; reaches `build_trade`, terminal
  `TRADE_BUILD_FAILED` at the SL guard. Both arms, both episodes, zero trades.
- **SL geometry:** SHORT `sl = disp_high + sl_atr_buffer*atr`; LONG `sl = disp_low − sl_atr_buffer*atr`;
  `sl_atr_buffer = 0.2`; `atr = state.atr_abs` **on the soft-confirmation bar, not the RETEST bar**.
  Guard: SHORT needs `sl > entry`, LONG needs `sl < entry`; failure → `build_trade` returns None,
  TP1/TP2/risk_dist never computed.
- **The two numeric outcomes** (so the model can check its own arithmetic):
  - 07-22 SHORT: entry 4154.55, disp_high 4146.75, atr 9.562143 → sl 4148.6624 — below entry, guard FALSE.
  - 07-28 LONG: entry 4044.31, disp_low 4046.38, atr 6.571429 → sl 4045.0657 — above entry, guard FALSE.
  - Shape in both: the retest close sits *past* the displacement extreme, so the protective buffer
    lands on the wrong side. Give this to the model as the observation, and make finding *why the
    retest closes there* one of the mining targets.

### Traps to name explicitly

1. **The arms are confounded.** A3's `session_windows` override also feeds the risk engine's
   time score, so A3 raises `final_S` too (0.4957→0.5980 on 07-22; 0.4670→0.5628 on 07-28). A3 is
   not "A0 with only the session gate opened." Any A0-vs-A3 delta attributed purely to session is wrong.
2. **A session *rejection* is emitted; a session *pass* is not.** In A3 the pass is known only
   because `build_trade` was subsequently called. Don't read the two as equally observed.
3. **Two different ATRs exist per episode** — on the RETEST bar and on the soft-conf bar. Only the
   soft-conf one reproduces the engine's SL. `operands.csv` labels both.
4. **`momentum_score` and `ema_spread` are price-scaled, not normalized ratios** — values in the
   thousands are expected in this dump. Do not interpret them as z-scores or read magnitude as strength.
5. **Warmup holes are real data**, e.g. `trend_strength = NOT_YET_AVAILABLE (needs 79 bars, have 62)`.
   Not a bug to report, and not a value to impute.
6. **`session` feature = 2 while the engine reports `OFF_SESSION`, and `active_range.session = UNKNOWN`.**
   Flag as an audit target rather than silently picking one.
7. **n = 2 episodes.** The pattern-mining job produces *candidate* signatures and the test that
   would confirm them — never a rate, hit-rate, or edge estimate.

### The four jobs, with output contracts

- **J1 — No-trade chain.** For each episode×arm: the ordered gate list, which gate bound, the
  operands that made it bind, and what would have to be true numerically for it not to bind.
  Then: rank gates by how many of the 4 episode×arm cells they kill.
- **J2 — Setup signatures.** From `bars.csv`, the per-bar feature/state values at SWEEP,
  DISPLACEMENT and RETEST for both episodes; note what the two share and where they diverge;
  emit each as a named candidate signature with the measurement that would test it on a full corpus.
- **J3 — Trace audit.** Recheck every arithmetic line in the `proof_*.md` files; check the parity
  deltas; check that each claim in `journeys.md` is supported by a value in `operands.csv` /
  `bars.csv`; list anything asserted more strongly than its source supports.
- **J4 — Plain-language mechanism.** Bar-by-bar narration of both episodes: what price did, what
  the state machine saw, why it moved state, why it ended without a trade. No hypotheses, no jargon
  the report hasn't defined.

### Output skeleton the prompt fixes

```
# Trade Mining — <RUN_ID>
## 1. What this run contains        (instrument, window, episodes, arms, terminal outcomes)
## 2. Why no trade                  (J1 — gate table + binding-gate ranking)
## 3. Setup signatures               (J2 — candidate table + the test for each)
## 4. Trace audit                    (J3 — arithmetic recheck + overstated claims)
## 5. The story, bar by bar          (J4 — one subsection per episode)
## 6. What I could not determine     (explicit; anything the files don't answer)
```

Plus one standing instruction: every number cited must appear in one of the attached files, with
the filename beside it; if a value isn't there, write what's missing instead of estimating.

## Verification

1. Read the written file end to end — it must be self-contained (an LLM with only these
   attachments and this prompt needs no repo access).
2. Cross-check every embedded fact against source:
   `results/crt_episode_trace/20260813T124158Z/journeys.md`, `operands.csv`, `proof_*.md`,
   `episodes.json` (header block), and `bars.csv` (header row).
3. Confirm no governance vocabulary leaked in (no F-ids, FM-ids, "Authority Ladder", "E-001",
   OBSERVED/DERIVED/INFERRED_BY_ORDER as *taxonomy* — the words may appear only where quoting
   what the files literally contain).
4. Confirm generality: the prompt reads correctly if `<RUN_ID>` is a different trace folder.
5. Live test (user-run): paste as system prompt, attach the 12 files, send "mine this run" —
   the report should follow the 6-section skeleton and should not claim a win rate or edge.


================================================================================
SOURCE_FILE: docs/implementation_plan/i-remember-e-have-silly-forest.md
SOURCE_BYTES: 5819
PART: 5/10 FILE 4/16
================================================================================

# Generate the XAUUSD oracle parquet artifacts

## Context

The user remembered a `labels.parquet` / `bar_matrix.parquet` in the repo. Investigation showed
**neither ever existed**:

- `pyarrow` is declared only as an *optional* extra under `mt5_analytics`
  (`pyproject.toml:22`) and is installed in **neither** venv (`venv/` py3.12, `.venv/` py3.14).
- `scripts/research/build_bar_matrix.py:333` attempts `to_parquet` inside a `try`, fails, and
  honestly records `parquet_written: false` + `parquet_skipped_reason` in its manifest. Console
  output correctly prints the **CSV** path.
- `src/research/oracle/labeler.py:330` has **no** `to_parquet` call at all — structurally
  incapable of producing `labels.parquet`.
- Git history contains zero parquet adds or deletes; F-086's evidence line correctly cites
  `labels.csv … sha256 3027ea97…`.

The `.parquet` filename existed only in the prose of a prior chat summary. Every authoritative
surface (code, console, manifest, finding) said CSV and was right.

**Goal:** honor the already-declared `pyarrow` dependency so both parquet artifacts actually
exist as convenience siblings — **without disturbing the CSVs that F-086/F-087/F-088 cite by
hash**. CSV stays canonical.

## Non-negotiable constraint

These two hashes are cited evidence and must be **byte-identical** when this is done:

| artifact | sha256 |
|---|---|
| `results/research/oracle_labels/XAUUSD_M15/labels.csv` | `3027ea973b4a7a2bd71c2ed615a23cb837ff9e319e44af3d1e6d2b33f11b9282` |
| `results/research/bar_matrix/XAUUSD_M15/bar_matrix.csv` | `e409d8333aec585633cf8ebab107eaceeeb0b65b21455ea782efd4e426de394c` |

`labels.csv`'s hash matches the `3027ea97…` cited in F-086 and F-088 exactly. The design below
regenerates into a **scratch dir** and promotes only the `.parquet` files, so the canonical CSVs
are never overwritten — byte-identity holds by construction, not by luck.

## Steps

### 1. Environment
Install the already-declared optional dep into the canonical venv (`venv/`, py3.12 — the one
`project_feature_lineage_candle_math.md` flags; `.venv/` py3.14 is also in use, install there too
if the user runs it):

```bash
venv/Scripts/python.exe -m pip install pyarrow
```

No `pyproject.toml` change — `pyarrow` is already declared. It stays optional; the `try/except`
guards mean nothing breaks if it's absent.

### 2. Add the parquet write to `labeler.py` (additive)
In `src/research/oracle/labeler.py`, immediately after `labels.to_csv(...)` (`:330`), mirror the
existing block at `scripts/research/build_bar_matrix.py:332-337` **verbatim in shape** — same
`try/except`, same `parquet_written` / `parquet_skipped_reason` manifest keys, same "CSV is
canonical" comment rationale. Add the two keys to the `manifest` dict built at `:335+`.

CSV write stays first and unconditional; parquet cannot affect it.

### 3. Regenerate into scratch, then verify
Scratch dir: `C:\Users\Hi\AppData\Local\Temp\claude\D--Tradelatest\<session>\scratchpad\parquet_run\`

```bash
venv/Scripts/python.exe scripts/research/build_bar_matrix.py --instrument XAUUSD --timeframe M15 --out-dir <scratch>/bar_matrix
venv/Scripts/python.exe -m research.oracle.labeler --instrument XAUUSD --timeframe M15 --matrix-dir <scratch>/bar_matrix --out-dir <scratch>/labels
```

`build_bar_matrix` takes ~339s; the labeler ~11s.

Then `sha256sum` both scratch CSVs against the table above.

- **Both match** → proceed to step 4. This also *proves determinism* of the pipeline, a
  worthwhile side-result.
- **Either differs** → **STOP. Do not touch the canonical dir.** A non-reproducing CSV is a far
  more serious result than a missing parquet (it would mean cited evidence can't be regenerated),
  and it gets reported, not worked around. Fallback for delivering the parquet anyway: convert
  the *existing canonical* CSV directly (`pd.read_csv(...).to_parquet(...)`), which guarantees the
  parquet matches the cited artifact.

### 4. Promote parquet only
Copy `bar_matrix.parquet` and `labels.parquet` from scratch into their canonical dirs. Update the
two canonical `manifest.json` files to set `parquet_written: true` and drop
`parquet_skipped_reason`. **Canonical CSVs are not touched.**

### 5. Fix the now-stale comment (§6.2, same turn)
`scripts/research/build_bar_matrix.py:326` asserts *"no parquet engine is installed in this
environment"* — false once step 1 lands. Rewrite to state that parquet is an optional convenience
and CSV remains canonical. Unambiguous `DOC_DRIFT`, auto-fix tier.

## Verification

1. **Byte-identity (the load-bearing check)** — re-`sha256sum` both canonical CSVs after
   promotion; must still equal the table above.
2. **Round-trip** — read each parquet back and compare against its CSV: identical shape, column
   names, and values (dtype-aware; parquet preserves types the CSV round-trip widens).
3. **Floors** — `venv/Scripts/python.exe -m pytest tests/research/test_oracle_labeler.py tests/research/test_multi_tp_walk_parity.py` (31 tests, expect all green).
4. **Manifests** — both report `parquet_written: true` with no `parquet_skipped_reason`.

## Governance notes

- **No finding is created or changed.** No conclusion moves; F-086's `labels.csv` citation stays
  true. Adding a sibling artifact grants no authority (§6.5).
- **No SITS re-registration.** `labeler.py` lives under `src/`, not `scripts/**`; the three
  scripts (`SCR-418/419/420`) are already registered at `EXTRACTED_TO_SRC`.
- **Untracked output.** `results/` is gitignored (`.gitignore:5`), so the parquet artifacts are
  local-only. Only `labeler.py` and the `build_bar_matrix.py` comment are tracked changes.
- **Hash-neutral.** No `configs/production/*` edit, no `params` change, no rehash.
- §6 SESSION LOG entry appended to `assistant_project.md` on completion.


================================================================================
SOURCE_FILE: docs/implementation_plan/i-studied-the-materials-recursive-phoenix.md
SOURCE_BYTES: 16983
PART: 5/10 FILE 5/16
================================================================================

# Truth-Layer Registry v2.0 → v2.1 — Reachability + Machine-Readable Truth Sources

## Context

`active_models.yaml` v2.0 (commit 0c378a9, 2026-07-02) established the 4-layer truth schema (intent/runtime/evidence/status) per model. A multi-LLM handoff analysis identified the next gap: the registry knows *what* each model is, but the machine-readable truth artifacts (findings, hypotheses, telemetry streams) are not reachable from it or from CLAUDE.md — "dark knowledge." The user approved the **full proposal** with two constraints from doctrine review:

- **Drift/conflicts stay as F-id references** — `docs/current-findings.md` remains the single conflict-truth store; no structured drift blocks, no new drift store (`logs/drift_audit.jsonl` stays the runtime stream).
- Anywhere the proposal would duplicate an authoritative store, the artifact is **GENERATED/seeded, never hand-edited** (§6.2), and the `optimization` metadata is **descriptive only** — no promotion thresholds in any registry (§6.5 Authority Ladder).

User-confirmed decisions:
1. Scope = full proposal (reachability pointers + generated findings export + hypothesis registry + optimization metadata + CLAUDE.md table).
2. Hypothesis registry uses the **seed-script pattern** (committed truth = seed script; `data/hypothesis_registry.jsonl` is its deterministic projection — exact `framework_registry` precedent).
3. New guard test is classified **citation-class reference-resolution** and the Executable-Invariant Scope Policy (conventions.md §9) is amended to record it.

## Grounding facts (verified)

- `data/` and `context/` are gitignored; `data/framework_registry.jsonl`'s committed truth is `scripts/governance/seed_framework_registry.py` (pinned timestamps, byte-stable dump); `tests/test_framework_registry.py` reseeds via autouse fixture.
- Finding-block grammar codified in `tests/test_current_findings.py` (`### F-\d{3}` headers, `- Field:` lines) and `src/governance/framework_registry.py::valid_finding_ids()` — the new parser reuses this grammar, never invents a third.
- Telemetry stream paths are module constants (`src/utils/engine_telemetry.py:35-36`, `src/replay/replay_drift_governor.py:55`, `src/utils/trade_logger.py:82`); `EventType` enum at `src/events/event_fabric.py:56`. JSONL schemas doc home = `docs/reference/schemas.md §9`.
- In-memory `HYPOTHESIS_REGISTRY` (`src/research/registry.py`) populated by importing `research.hypotheses` + `research.controls`; M4 gate = `src/research/qualification.py`.
- `tests/test_crt_state_invariants.py` reads only `crt.runtime.{states,state_list,valid_transitions}` — all changes are additive, so it stays green untouched.
- `active_models.yaml` is NOT the production config — no rehash needed.
- Working tree is dirty with many untracked files — every commit must be surgical (`git add <explicit paths>` only).

## Version semantics (avoid split-brain)

`meta.schema_version: 2.0 → 2.1` (file format, additive). `meta.truth_schema.version` **stays 2.0** — canonical layer set `[intent, runtime, evidence, status]` unchanged; new blocks are sub-blocks inside existing entries. This distinction is written into conventions.md §9.

---

## Step 1 — Findings export (generated derived view)

**Create `src/governance/findings_export.py`** (docstring cites §6.2 DERIVED-VIEW rule):
- `parse_findings(doc=Path("docs/current-findings.md")) -> list[dict]` — reuses `test_current_findings.py` grammar exactly. Pure, deterministic, stdlib+`re`.
- `render(records) -> str` — first line = self-describing meta record (no timestamp → deterministic), then one line per finding in doc order, `json.dumps(..., ensure_ascii=False, sort_keys=True)`.

Line shapes:
```python
# line 0: {"kind":"meta","schema":"findings_export/1","source":"docs/current-findings.md","generated_by":"scripts/governance/export_findings.py"}
# per finding: {"kind":"finding","id":"F-NNN","title","type","status","confidence","validated","revalidate_by",
#               "evidence","evidence_paths":[...],"supersedes","superseded_by","reversal","owner","note","terminal":bool}
```

**Create `scripts/governance/export_findings.py`** — thin argparse CLI; default writes `data/findings.jsonl` (gitignored-generated, per D1: committing it would put a second copy of findings truth in every diff); `--check` prints without writing.

**Create `tests/test_findings_export.py`** (mirrors `test_context_compiler.py`): (1) render twice → byte-identical; (2) every `### F-NNN` in doc appears exactly once, counts match; (3) meta line present; (4) non-terminal records have non-empty evidence; (5) autouse fixture regenerates `data/findings.jsonl` if absent + asserts on-disk == fresh render (hand-edit guard).

**Doc sync:** `schemas.md` new **§9.5 `data/findings.jsonl` (GENERATED)** — key set + "never hand-edit; regenerate via the script; truth stays `docs/current-findings.md`".

## Step 2 — Hypothesis registry (seed-script pattern)

**Create `src/governance/hypothesis_registry.py`** — mirrors `FrameworkRegistry` (load/validate_record/append/dump via `utils.jsonl_writer`); reuse `framework_registry.valid_finding_ids` (do not re-implement). Record shape:

```python
{"id":"H-NNN", "statement":str, "family":str|None,
 "status":"open"|"validated"|"falsified"|"frozen"|"superseded",
 "authority":"research",                 # PINNED literal — validator rejects anything else (§6.5)
 "findings":["F-019",...],               # must resolve via valid_finding_ids()
 "models":["crt",...],                   # top-level keys of active_models.yaml (minus meta/philosophy)
 "code_hypotheses":["expansion_breakout",...],  # names in research HYPOTHESIS_REGISTRY (may be [])
 "programs":[...], "evidence":[{path,line,symbol,type}],
 "created":ts, "last_validated":ts, "notes":str}
```
No `promotion_requirements` / `min_delta_g001` style keys exist; validator rejects unknown keys. Promotion standard stated once in docstring + §9.6 doc: "`validated` is a research verdict; the only promotion path remains M4 `QualificationGate` → `ConfigValidator`/`PromotionManager`; this registry defines no thresholds."

**Create `scripts/governance/seed_hypothesis_registry.py`** (clone seed_framework_registry shape: pinned `_TS`, `_rec()`, dump → `data/hypothesis_registry.jsonl`). Seed ~16 records harvested from the falsification programs (statements written with the finding text open at implementation):

| H-id | gist | status | findings |
|---|---|---|---|
| H-001 | CRT structural completion has standalone directional edge | falsified | F-019, F-021, F-026 |
| H-002 | Candle-conditional directional pockets exist | falsified | F-020 |
| H-003 | Exit/SL-TP structure is an expectancy lever | falsified | F-025 |
| H-004 | HTF (H1/H4) rescues the edge | falsified | F-027 |
| H-005 | P&F interpreter carries standalone edge | frozen | F-028 |
| H-006 | Vol-regime LEVEL conditioning consumable | falsified | F-030 |
| H-007 | Markov P^H forecast adds beyond vol level | falsified | F-043 |
| H-008 | MTF compression→expansion directionally consumable | falsified | F-040 |
| H-009 | Cross-sectional dispersion monetizable | falsified | F-032 |
| H-010/011 | Carry/basis signal · carry harvest | falsified | F-033 / F-034 |
| H-012 | Entry-info null generalizes to FX | validated | F-035 |
| H-013 | Weekly liquidity-sweep ontology clears M4 | falsified | F-042 |
| H-014 | Feature-pipeline lookahead is fatal contamination | falsified (benign) | F-029 |
| H-015 | ZoneGate neighborhood quality is pivotal | falsified | F-036, F-041 |
| H-016 | Program 9: M5 multi-TF OCO straddle | open | — (pre-reg only) |

`code_hypotheses` filled where twins exist (`expansion_breakout`, `mean_reversion`, `compression_breakout`→H-008, `weekly_sweep_reversal`→H-013, `spine_hypothesis`→H-001).

**Create `scripts/governance/query_hypotheses.py`** — sibling of `query_registry.py`: `--summary`, `--finding`, `--model`, `--status`, `--validate` (exit 1 on error).

**Create `tests/test_hypothesis_registry.py`** — mirror the 8 framework contract tests: loads-valid · findings-exist · models-exist (keys of active_models.yaml excl. meta/philosophy) · code-hypotheses ⊆ HYPOTHESIS_REGISTRY (after importing research.hypotheses+controls) · programs/evidence paths resolve · unique-ids · authority-pinned + status-enum · append-only-immutable. Autouse reseed fixture.

**Doc sync:** `schemas.md` **§9.6** (key set + authority note + regenerate command); one cross-link line in `docs/reference/framework_registry_schema.md`.

## Step 3 — `schemas.md §9.4`: event-fabric stream table (prereq for Step 4 pointers)

Add **§9.4 "Event-fabric streams (uniform envelope)"**: the `make_event_envelope` key set once + thin table `EventType → stream file → emitter module` covering at least: ENGINE_TELEMETRY, DECISION_LINEAGE, DRIFT_AUDIT, TRADE_LIFECYCLE, STATE_TRANSITION, LLM_TURN (paths/emitters per grounding facts above).

Also scope the §9 preamble rule: "`timestamp`+`kind` applies to **audit/event streams**; registry-class JSONL (§9.5–9.6, framework_registry) uses `created`/`last_validated`" — auto-fixable DOC_DRIFT (framework_registry.jsonl already deviates undocumented).

## Step 4 — `active_models.yaml` v2.1 (additive) + guard test

**Modify `active_models.yaml`** — additions only, no renames/removals:

1. `meta.schema_version: 2.1`; extend `meta.migration` (`breaking_changes: false`); add `meta.machine_readable_sources` block mapping each of {findings_export, hypothesis_registry, framework_registry} → `{path, generator, guard}`.
2. Per model (crt, gaussian, bitnet, zone_gate, rr_model, strategies, engine_runner) a `reachability` block:
```yaml
reachability:
  config_sections: [crt_engine]      # top-level keys in configs/production/<ACTIVE_VERSION>.json
  telemetry:
    - {event_type: STATE_TRANSITION, stream: <path>, emitter: src/config_layer/crt_engine_v2.py}
  tests: [tests/test_crt_state_invariants.py]
  topics: [docs/topics/model-intent-and-feature-ownership.md]
  framework_ids: [IMPL-00X]          # optional link into framework_registry
```
Every path verified by grep before writing.
3. Per model `evidence.conflicts:` — plain F-id list (zone_gate: `[F-041]`; others `[]`/omitted). **No structured drift blocks** (fixed decision).
4. Per model `evidence.hypotheses:` — H-id lists (crt: `[H-001, H-002, H-004, H-012, H-013]`, zone_gate: `[H-015]`, gaussian: `[H-014]`, …).
5. Per model `optimization` block — **descriptive only**:
```yaml
optimization:
  authority: "none — descriptive; see CLAUDE.md §6.5 (tunability ≠ authority; promotion only via M4 QualificationGate + PromotionManager)"
  tunable_class: BEHAVIORAL
  config_sections: [crt_engine]      # caveat: CRTConfig params split-brain, §6.5
  frozen_structural: "CRTState members, VALID_TRANSITIONS, feature dims — code-frozen"
  census: docs/research-readiness/behavior-census-report.md
  promotion_standard:
    research:   src/research/qualification.py
    production: src/governance/promotion_manager.py
```
No numeric thresholds anywhere in the block; no per-knob inventories (census's job; `crt.runtime.thresholds` stays as-is).

**Create `tests/test_active_models_registry.py`** — docstring classifies it as *citation-class reference-resolution* (sibling of `test_doc_citations.py`), NOT a semantic YAML↔code invariant. Reseed fixture for both `data/*.jsonl`. Checks:
1. YAML parses; `meta.schema_version == 2.1`; canonical_layers unchanged.
2. Every F-id in `evidence.findings`/`evidence.conflicts`/`philosophy.authority.findings` ∈ `valid_finding_ids()`.
3. Every H-id resolves in the reseeded hypothesis registry.
4. Every reachability path + `machine_readable_sources.{path,generator,guard}` resolves from repo root.
5. Every `telemetry.event_type` ∈ `EventType`; stream basename appears in emitter module source text.
6. Every `config_sections` entry is a top-level key of the JSON named by `configs/production/ACTIVE_VERSION` (branch-scoped §4.0).
7. `optimization.authority` startswith "none" + mentions §6.5; **negative guard**: no key matching `promotion_requirements|min_delta|threshold` inside `optimization` (authority-creep regression).
8. `framework_ids` resolve in the reseeded framework registry.

**Doc sync (§6.3/§6.4):**
- `conventions.md §9`: (a) v2.1 note under Truth-Layer Standard (sub-blocks; truth_schema.version stays 2.0; meta.schema_version tracks file format); (b) Executable-Invariant Scope Policy amendment: add the new test as "reference-resolution (citation-class), no semantic pinning", drift evidence = F-041. **[User approved this amendment.]**
- `docs/topics/model-intent-and-feature-ownership.md`: pointer to per-model optimization/reachability blocks + dated Discussion entry + bump `Updated:`.
- No finding changes (nothing validated/overturned) — state explicitly in SESSION LOG.

## Step 5 — CLAUDE.md thin reachability table + SESSION LOG

Under the §2 companion table add (~9 lines):

```markdown
**Machine-readable truth sources** (artifacts are GENERATED/seeded — edit the source/seed, never the artifact):
| Artifact | Source of truth | Regenerate | Guard |
|---|---|---|---|
| data/findings.jsonl | docs/current-findings.md | scripts/governance/export_findings.py | tests/test_findings_export.py |
| data/hypothesis_registry.jsonl | scripts/governance/seed_hypothesis_registry.py | run the seed | tests/test_hypothesis_registry.py |
| data/framework_registry.jsonl | scripts/governance/seed_framework_registry.py | run the seed | tests/test_framework_registry.py |
| active_models.yaml (v2.1) | hand-maintained, source-verified | — | tests/test_active_models_registry.py + test_crt_state_invariants.py |
| context/*.md | canonical docs (Compile) | scripts/context/build_context.py | tests/test_context_compiler.py |
```

In passing (unambiguous DOC_DRIFT, auto-fix): the `active_models.yaml` row in the §2 table has a malformed leading `| |` and says "10 states" (stale vs corrected 9).

Then append the mandated `📝 SESSION LOG ENTRY` to `assistant_project.md` (§6), including the Executable-Invariant amendment justification.

## What is explicitly NOT built (doctrine)

- No new telemetry emitters (`crt_candidates.jsonl` etc.) — 15 streams exist; the gap was discoverability.
- No hand-maintained `evidence/findings.jsonl` second truth store — generated export only.
- No drift-registry JSONL / structured drift blocks — findings + `logs/drift_audit.jsonl` already own this.
- No auto-tune promotion thresholds in any registry — §6.5 Authority Ladder; the negative-guard test enforces it.

## Files summary

**Create:** `src/governance/findings_export.py`, `src/governance/hypothesis_registry.py`, `scripts/governance/export_findings.py`, `scripts/governance/seed_hypothesis_registry.py`, `scripts/governance/query_hypotheses.py`, `tests/test_findings_export.py`, `tests/test_hypothesis_registry.py`, `tests/test_active_models_registry.py`.
**Modify:** `active_models.yaml`, `docs/reference/schemas.md` (§9 preamble + §9.4–9.6), `docs/reference/conventions.md` (§9), `docs/reference/framework_registry_schema.md` (1 line), `docs/topics/model-intent-and-feature-ownership.md`, `CLAUDE.md` (§2 table), `assistant_project.md` (SESSION LOG).
**Reuse:** `FrameworkRegistry` pattern + `valid_finding_ids` (`src/governance/framework_registry.py`), `utils/jsonl_writer.py`, `test_current_findings.py` grammar, seed/reseed-fixture pattern (`scripts/governance/seed_framework_registry.py`, `tests/test_framework_registry.py`).

## Verification

```bash
# baseline
python -m pytest tests/test_crt_state_invariants.py tests/test_current_findings.py tests/test_framework_registry.py tests/test_context_compiler.py -q
# step 1
python scripts/governance/export_findings.py
python -m pytest tests/test_findings_export.py tests/test_current_findings.py -q
# step 2
python scripts/governance/seed_hypothesis_registry.py
python scripts/governance/query_hypotheses.py --validate
python -m pytest tests/test_hypothesis_registry.py tests/research/test_registry.py -q
# step 3
python -m pytest tests/test_doc_citations.py -q
# step 4
python -c "import yaml; yaml.safe_load(open('active_models.yaml', encoding='utf-8'))"
python -m pytest tests/test_active_models_registry.py tests/test_crt_state_invariants.py tests/test_topic_docs.py -q
# step 5 + regression sweep
python scripts/governance/query_registry.py --validate
python -m pytest tests/test_current_findings.py tests/test_doc_citations.py tests/test_topic_docs.py tests/test_context_compiler.py tests/test_framework_registry.py tests/test_findings_export.py tests/test_hypothesis_registry.py tests/test_active_models_registry.py tests/test_crt_state_invariants.py -q
```

Each step is independently green-able; Step 4's H-id checks depend on Step 2, its stream-table pointer on Step 3 — hence the ordering. Commits: surgical `git add <explicit paths>` only (dirty tree).


================================================================================
SOURCE_FILE: docs/implementation_plan/i-ve-now-read-all-gentle-riddle.md
SOURCE_BYTES: 8678
PART: 5/10 FILE 6/16
================================================================================

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


================================================================================
SOURCE_FILE: docs/implementation_plan/i-want-to-check-graceful-fog.md
SOURCE_BYTES: 15150
PART: 5/10 FILE 7/16
================================================================================

# Report: OHLCV→feature tracing (both flows) + blast radius of the two XAUUSD warnings

## Context

Follows the XAUUSD run on active config `v2_multi_2026_04` (1 trade, net −0.04R). Two questions:
(1) do the `normalization_basis` / `session_timestamp_basis` warnings explain or cause bugs in
upper layers? (2) trace OHLCV→feature formation in `BacktestRunner` vs `CRTStateResolver`.

Everything below marked ✅ was verified by me against source or by running read-only probes.
Items marked ⚠️ are unverified and flagged as such. Three sub-agent claims were **corrected**
during verification — noted inline.

---

# PART A — OHLCV → feature formation, both flows

## A1. BacktestRunner: TWO independent passes over the same CSV ✅

The single most important structural fact: `backtest_v2` reads the CSV **twice**, by two different
readers, producing two parallel derivations that are only reconciled at trade time.

```
data/mt5/XAUUSD_M15.csv
   │
   ├─ PASS 1 (vectorized, pandas) ─────────────────────────────────────────
   │   backtest_v2.py:1790  raw_df = pd.read_csv(self.csv_path)
   │   :1792                columns → lowercase
   │   :1794-1800           synthesize `timestamp` from date+time if absent
   │   :1803                require_ohlcv_columns(...)
   │   :1804-1805           FeaturePipeline(raw_df).run()
   │        └─ feature_pipeline.py:1316 run() — ordered steps:
   │             :1329 compute_price_features   :1330 compute_volume_features
   │             :1331 compute_indicators       :1332 compute_trend_features
   │             :1333 compute_volatility_regime:1334 compute_context
   │             :1335 compute_structure_liquidity :1336 compute_normalization
   │             :1339 canonical_price :1340 volatility :1341 ema :1342 trend
   │             :1343 structure :1344 temporal :1345 liquidity_distance
   │             :1346 promote_volume_spike :1347 canonical_session
   │             :1350 finalize()  ← WARMUP DROP + INDEX RESET (single stmt, :1198)
   │                                 df.dropna(subset=CANONICAL_FEATURES).reset_index(drop=True)
   │             :1352 build_feature_vector() (:1276) → 39-dim vectors
   │   → enriched_df (47,197 rows) + self.feature_vectors
   │   :1810-1814  feature_ts_to_idx = {ts.strftime("%Y-%m-%d %H:%M:%S"): i}
   │
   └─ PASS 2 (row-by-row, csv.reader) ─────────────────────────────────────
       backtest_v2.py:700   class CandleLoader   (same file)
       :752-754             stream() re-opens the file with csv.reader
       :840-841             yields crt_engine_v2.Candle(..., index=_candle_pos)
       NO warmup skip, NO dropna — every raw row is yielded (47,275)
            └─ Candle geometry is its OWN, ontology-routed:
               crt_engine_v2.py:86/92/97 → _cm.body_size / FM-002 / FM-010
```

**The join** ✅ — `engine.process_candle(candle, ...)` runs for **every** candle (`:2202`), but the
39-dim vector is pulled **only inside** `if "TRADE_OPENED" in action` (`:2224` → `:2235-2236`
lookup → `:2268` `.tolist()`). So on 47,274 of 47,275 candles this run, the pipeline vector was
never consulted at all — the CRT state machine ran purely on its own ontology-routed geometry.

**Consequence worth internalizing:** the pipeline's 39-dim vector does **not** drive trade
*generation*. It drives scoring/fusion/monitoring **after** a setup exists. That bounds how much
damage the saturation defects (Part B) can do in this flow.

## A2. CRTStateResolver flow ✅

```
data/mt5/XAUUSD_M15.csv
   └─ run_crt_state_on_mt5_xauusd.py  (OHLCV_PATH :35 hardcoded)
        └─ FeaturePipeline(...).run()          ← SAME pipeline as pass 1
             └─ per-bar: CRTStateResolver.resolve(feat_dict, timestamp=...)   :118
                  crt_state_resolver.py:194-283 resolve():
                    normalize → encode feature states → candle_index += 1 (:244)
                    → _advance_htf (:247) → _apply_lifecycle_resets (:253)
                    → _tick_shadow_ttl (:268) → _resolve_from_features (:271)
                    → _apply_transition_validity (:274) → _update_memory (:277)
        → state counts / funnel → reports/crt_state_fresh_run_xauusd.md
```

## A3. Why the two funnels disagree — and the correction I had to make ✅

I initially framed this as "stateless resolver vs stateful engine." **That was wrong**, and I'm
flagging it rather than quietly dropping it. Both are **stateful sequential machines running the
identical transition graph** — `state_identity.py:69-79` `VALID_TRANSITIONS` ≡
`market_crt_states.yaml:237-246`; the resolver carries `CRTStateMemory` (:100-128) and enforces
`_apply_transition_validity` (:882-931) exactly as `crt_engine_v2._transition()` (:980-990) does.
Totals match exactly (47,197 both) → pure redistribution.

| State | BacktestRunner | CRTStateResolver | Mechanism |
|---|---|---|---|
| SHADOW_PENDING | 51 | **271** | `_force_range_reset(kind="htf")` (:429-440) arms `pending_displacement_active` on every DISPLACEMENT; `htf_candles_per_range:4` < `max_displacement_age_candles:3`+1 ⇒ ~every DISPLACEMENT dies on an HTF boundary → 1:1 with DISPLACEMENT (271 = 271 exactly). Engine gates shadow on a real confirming sweep → 51. |
| EXECUTION | 5 | **0** | `_continuous_gates_pass` (:690-694) requires `raw["score"\|"risk_score"\|"crt_score"]`; `feature_schema` has none of those ⇒ `score is None` → fail-closed. **Documented as expected** at `market_crt_states.yaml:33-36`. |
| RANGE / EXPANSION | 35,159 / 4,605 | **39,705 / 698** | ⚠️ **Genuine defect in the runner:** `run_crt_state_on_mt5_xauusd.py:118` calls `resolve()` **without `htf_id`**, so the internal HTF counter restarts at 0 on the post-warmup slice and drifts out of phase. `build_htf_id_timeline()` (:1082-1126) exists precisely to prevent this and is never called. Unmatched bars fall to RANGE (:651). |

**Not a production bug** ✅ — `grep -rn crt_state_resolver src/` returns only the module itself.
Consumers: 4 research scripts, 2 tests, docs. No live or backtest decision path consumes it. My
earlier "TruthConflict between two authorities" framing was too strong: this is a fidelity gap in
an intentionally-shadow research tool, plus one fixable runner defect.

## A4. NEW defect found — warmup off-by-one, verified empirically ✅

| | |
|---|---|
| Pipeline | `required_warmup_rows()` = 78 → drops raw rows **0–77**; first enriched ts = `2024-05-22 20:30:00` (raw row 78) |
| Replay loop | `candle_idx` is **1-based** (`=0` at :1990, `+=1` at :2117 *before* use); skips while `candle_idx < 78` (:2140) → drops raw rows **0–76** |
| Result | raw row **77** (`2024-05-22 20:15:00`) enters the CRT state machine with **no feature row**. Probe confirmed: `'2024-05-22 20:15:00' in feature_ts_to_idx` → **False** |
| Guard | `:1828` tests `warmup_candles < _pipeline_warmup` → `78 < 78` → False → **does not fire** |
| Arithmetic | loop drops `W−1` rows vs pipeline's `P` ⇒ alignment needs `W = P+1 = 79`, or the loop needs `<=` |

**Severity: low, fails closed.** A `TRADE_OPENED` on that one bar raises `FeatureAlignmentError`
(:2255-2267) — it can crash a run, never silently corrupt a ledger. Did not fire on this run.

---

# PART B — Do the two warnings cause bugs upstairs?

## B1. `normalization_basis=atr_relative` (F-061/F-064) — YES, kills channels ✅

Live-measured, this run: `momentum_score` = **1155.82** on the single trade (`tanh` = **exactly
1.0**); `ema_spread` = **−474.22**. Corpus: momentum −26,421→+25,226, ema_spread −9,370→+12,110.
`atr` = 0.00093 (correct ratio) — proving these two are the dimensional outliers, not the norm.

| Consumer | Code | Effect at live scale | Reached in **this backtest**? |
|---|---|---|---|
| `engine_runner.py:160-164` `detect_regime` | `ema_spread_abs >= 0.15 and momentum >= 0.3` | **constant `"trend"`** | ✅ YES (gate was ON) |
| `engine_runner.py:176-179` `breakout_engine` | `score = min(1.0,(spread+momentum)/2)`; `if score < 0.3: direction = 0` | **score pinned 1.0**, min-score veto unreachable | ✅ YES |
| `fusion_engine.py:115,164-168` | regime → `_REGIME_NORM["trend"]="TRENDING"` | **TRENDING weight profile permanently selected**; RANGING/VOLATILE unreachable | ✅ YES |
| `heuristic_gaussian_engine.py:358-360` | `tanh(momentum)`; `x=(ema_diff+momentum_norm)/2` | tanh=±1 swamps ema_diff (~1e-3) → gaussian ≈ 2-valued on `sign(momentum)` | ✅ YES |
| `gate_intelligence.py:235-237` REVERSAL | `1.0 - min(1.0, abs(mom))` | **exactly 0.0, always** | ❌ live-only |
| `s08_ml_ensemble.py:207,213` | `w_mom(0.25) × min(abs(mom),1.0)` | constant **+0.25 offset**, not signal | ❌ strategies |
| `s03/s04/s06/s07/s09` thresholds | `>0.3`, `0.6`, `0.5`, `−0.2` | degenerate to **pure sign tests** | ❌ strategies |
| `crt_gaussian_scorer.py` | — | does **not** consume either | n/a |

**Scoping correction I had to make** ✅ — `ExecutionPlannerV1_2` is constructed **only** at
`live_engine_hook.py:877`; `backtest_v2` never builds it (it only reads `execution_planner` config
values for exit simulation). So the whole `GateIntelligence` column is **live-path only** and was
**not** exercised by the run I did. A sub-agent presented these as one undifferentiated blast
radius; they are two different surfaces.

### The REVERSAL knife-edge — a sub-agent claim I corrected ✅

An agent concluded REVERSAL is "systematically rejected," citing max `0.20+0.20+0.25 = 0.65`
against threshold `0.55`. That arithmetic **refutes** its own conclusion (0.65 ≥ 0.55 → *passes*).
Verified weights from config (`gate_intelligence`): intent 0.35 / vol 0.20 / liq 0.20 / struct
0.25, threshold 0.55, `approved = final >= threshold` (:176).

The real result comes from **two defects compounding**:
- F-061 saturation ⇒ `s_i = 0.0` (kills the 0.35 intent weight)
- F-065 ⇒ `vol_score` structurally 0.0 (`volume_ma20` never emitted, :272-284) ⇒ `_liquidity_score
  = 0.5*sweep_score`, **capped at 0.5**

⇒ REVERSAL ceiling `= 0.35(0) + 0.20(1.0) + 0.20(0.5) + 0.25(1.0) = ` **exactly 0.55** = the
threshold. So REVERSAL is not impossible — it is a **measure-zero knife-edge** requiring perfect
vol AND perfect sweep AND perfect structure simultaneously. Neither defect alone does this
(without F-065 the ceiling is 0.65, comfortably passable). **This interaction is in neither
finding** — it is new.

⚠️ **Unverified, potentially decisive:** `_vol_score` (:250-257) computes `r = (high−low)/atr`. If
the live features dict carries `atr` as the **relative** value (0.00093) while `high`/`low` are raw
prices, then `r ≈ 2269` → `score = 1−(r−1)/2` → clamped **0.0**, dropping the REVERSAL ceiling to
0.35 and making it genuinely **impossible**. The trades.csv carries *both* `atr`=0.00093 and
`live_atr`=2.167, so both are plausible. **I did not verify which dict `live_engine_hook` passes.**
This is the same dimensional-mix class as the known SL/TP ATR issue. Resolving it is the single
highest-value follow-up in this report.

## B2. `session_timestamp_basis=broker_local` (F-066) — YES, and the advertised fix is incomplete ✅

**New finding: two different session-window sets exist and disagree** ✅

| Surface | Config key | Windows | Format |
|---|---|---|---|
| **Trade filter** (gating) | `crt_engine.session_windows` | LONDON 07:00–10:00, NEWYORK 13:00–16:00, ASIA 00:00–03:00 | strings |
| **Feature labeler** | `feature_pipeline.session_windows_utc` | ASIA [0,9], LONDON [7,16], NEWYORK [12,21] | int hours |

The labeler's windows **overlap** (LONDON [7,16] ∩ NEWYORK [12,21] = 12–16), so the emitted label
depends on iteration order — a defect independent of any timezone question. The filter
(`crt_engine_v2.py:3095-3098`) also `break`s on first match, same order-sensitivity.

**The decisive point** ✅ — the trade-gating filter at `crt_engine_v2.py:3093` reads
`candle.timestamp.time()`, i.e. the **raw candle timestamp**, *not* the FM-052 `session` feature.
Therefore **flipping `session_timestamp_basis` to `utc_corrected` fixes the feature and leaves the
gating filter untouched.** The warning text advertises `utc_corrected` as "the correction path"
without noting it does not reach the surface that actually blocks trades.

Evidence from this run: the sole trade opened at broker `15:00` 2024-06-17 (June ⇒ EEST ⇒ true UTC
≈ 12:00), labeled `session=3.0`/NEWYORK, and the summary reports `best_hour_utc: 15` — a field
named UTC holding broker time. On the same row `cached_session` = **UNKNOWN** while the pipeline
says NEWYORK — the engine's own cached session never resolved.

⚠️ **Deliberately not claimed:** whether this *mis-gates*. F-066 records that
`crt_engine.session_windows` was **empirically tuned on broker time**, so filter-and-data may be
self-consistent and the defect purely semantic (the window named "NEWYORK" denotes ≈10:00–13:00
UTC, which is London afternoon). Determining whether the windows were fit to broker or UTC time is
an economic question, not a code question — it needs your call, not a grep.

### Verdicts

| Defect | Kills a channel? | Changes which trades are taken? | Reached in this backtest? |
|---|---|---|---|
| F-061/F-064 saturation | **Yes** — regime discrimination, breakout veto, REVERSAL intent, gaussian reduced to sign | **Yes on the live path** (REVERSAL knife-edge); on the backtest path it freezes fusion into the TRENDING profile | ✅ partially (engine_runner/fusion yes; gate_intelligence no) |
| F-066 session basis | Feature is model-contaminating | ⚠️ filter reads raw timestamp — self-consistency undetermined | filter ✅ active; feature ✅ emitted |

### Silent fusion-weight losses ✅
`fusion_engine` weight profile frozen to TRENDING · `gate_intelligence` `w_intent=0.35 × 0.0` for
REVERSAL · `s08` `w_mom=0.25 × 1.0` = constant offset · `_liquidity_score` permanently halved.
Each is a weight applied to a constant — arithmetically a bias term, not a signal.

---

# Recommended next actions (none taken — read-only report)

1. **Resolve the `_vol_score` ATR dimension** (⚠️ above). Decides whether REVERSAL is knife-edge or
   structurally dead. One probe of the live features dict settles it.
2. **Fix the warmup off-by-one** — `:1828` guard `<` → `<=`, or loop `<` → `<=`. One line, testable.
3. **Fix the `htf_id` phase-lock** in `run_crt_state_on_mt5_xauusd.py:118` — call the existing
   `build_htf_id_timeline()`. Makes the research census trustworthy.
4. **Decide the session question** (yours): were `crt_engine.session_windows` fit to broker or UTC
   time? Then either relabel or re-tune. Also de-overlap `session_windows_utc`.
5. **Correct the F-066 warning text** to state that `utc_corrected` does not reach the trade filter.

None of this grants promotion authority (§6.5) — all descriptive.


================================================================================
SOURCE_FILE: docs/implementation_plan/i-zoomed-into-the-soft-whale.md
SOURCE_BYTES: 13119
PART: 5/10 FILE 8/16
================================================================================

# Trace Sujan's CRT method → mimic it on XAUUSD

## Context

Two source docs sit at repo root: `SujanTraderCRTExp.txt` (1,415 lines) and
`SujanTraderCrtExpPart2.txt` (1,324). They are the **same conversation** — doc 1 is a superset;
`CRT 2.0` appears at `CRTExp:685` and `Part2:602`, and the tails are identical. Treat them as one
corpus, not two sources.

They are **dialogue transcripts between Sujan and an AI**, not a written-up method. That matters
for provenance (below) and it is the same trap F-077 exists to prevent.

Separately, this session reverse-engineered five FX setups Sujan posted as screenshots
(NZDCAD/AUDUSD/AUDCHF/NZDUSD/USDCHF). Those turn out to be **the last three phases of the
documented protocol executed**, which lets the two sources validate each other.

**The synthesis that makes this worth building.** From the screenshots alone I concluded the only
undocumented input was "what makes a sweep count," and that it looked like a hindsight filter. That
was wrong — it is written down as an 8-phase checklist explicitly designed so *"90% of charts get
rejected before you even think about entering"* (`Part2:1122`). What the docs *also* reveal is
something Sujan does not appear to have noticed:

> `Part2:1266-1270` — **`Reward ≥ 1:5` · `Target = HTF CRT objective` · `Stop = CRT invalidation`**

Target and stop are both fixed by structure, so RR is fully determined — nothing is chosen. The
`≥1:5` rule therefore cannot select better trades; it can only select **trades whose invalidation
happens to sit close to entry**. It is a thin-buffer selector wearing the costume of a quality
filter. That predicts the exact pattern measured in the five screenshots: sort by stop distance and
RR falls monotonically, 5 of 5 (86→8.5, 101→5.5, 151→5.0, 175→4.9, 338→4.5), while sorting by
reward gives no order at all (5.5, 8.5, 5.0, 4.9, 4.5).

**Testing that one rule is the highest-value experiment in this program**, and it is original — it
is not a restatement of any existing finding.

---

## Part 1 — The extracted pattern

### Provenance chain (record it; do not repeat F-077's error)

`Romeo CRT Time-Based Model` (the "1-3-5-9 framework", `CRTExp:121`) → Sujan's own HTF-candle-state
practice → co-developed **with the AI** into `CRT Execution Protocol v1.0`, `CRT 2.0`, and
`CRT High-Probability Checklist v1.0`.

Both the four-state model (`Part2:869-872`) and the 8-phase checklist (`Part2:1124+`) are prefaced
by the AI as *"One refinement I'd like us to add"* / *"I think we should add"*. **They are the
interlocutor's proposals, not Sujan's authored method.** F-077 already corrected one Sujan
over-attribution; this plan must not create a second.

### The governing principle

> `Part2:851-857` — *"You're not really trading price. You're trading the state of higher-timeframe
> candles."* Every lower timeframe exists to answer: **"What is the current HTF candle trying to
> accomplish?"**

### The timeframe ladder

`6M` macro objective → `3M` decision zone → `Monthly` → `Weekly` → `Daily` execution environment →
`4H` active candle / execution engine → `1H` microscope for timing → `15M` refinement.

### The 8-phase checklist (`Part2:1124-1305`)

| Phase | Gate | Fail action |
|---|---|---|
| 1 | Macro alignment — 6M/3M/Monthly/Weekly each classified into 4 states | no clear answer → no trade |
| 2 | Alignment score — **all four must agree** | one disagrees → skip |
| 3 | Daily objective — "what is today's objective?" (sweep BSL/SSL, reach OB, fill imbalance) | can't answer → skip |
| 4 | 4H CRT — fresh? inside HTF objective? expanding? accumulating? liquidity taken? | — |
| 5 | Trade location — only Monthly/3M/Weekly/Daily OB, CRT midpoint, CRT high/low. **"Never chase."** | middle of nowhere → reject |
| 6 | Liquidity — external/internal taken? equal highs/lows? | no sweep → no trade |
| 7 | Activation — Rejection → Displacement → Structure shift → Return → Entry | without displacement the CRT is *"sleeping"* |
| 8 | Risk — **Reward ≥ 1:5**, Target = HTF objective, Stop = invalidation | — |

### The 100-point rubric (`Part2:569-580`)

Monthly +15 · Weekly +15 · Daily objective +20 · HTF location +15 · liquidity sweep +10 · rejection
block +10 · displacement +10 · BOS/CHoCH +5. **Sums to exactly 100; trade only at ≥90** — so at most
one 10-point component may be missing. Extremely strict.

### The four HTF states — two conflicting definitions in the same doc

- **A** (`Part2:869-872`): Expansion / Accumulation / Distribution *(reversal-warning)* / Reversal
- **B** (`Part2:991-994`): Accumulation ⭐⭐⭐⭐⭐ / Expansion ⭐⭐ / Exhaustion ⭐⭐⭐ / Redistribution-Reaccumulation ⭐⭐⭐⭐⭐
- Plus a "traffic light" overlay (`Part2:1319-1323`): 🟢 accumulation complete · 🟡 don't chase · 🔴 stand aside

**Adopt A and declare it** — `src/config_layer/htf_state.py:42` already implements exactly those four
members. B is recorded as an unimplemented variant, not silently merged.

### The one rule

> `Part2:1311` — **"Never trade an Expansion CRT. Trade the Accumulation before the next Expansion."**

### The 3-candle CRT profile (`CRTExp:787-791`)

expansion → small accumulation/base → recovery, i.e. **move → pause → move**. Note this is *not*
range→sweep→impulse, which is what shipped as `RANGE_C1`/`MANIPULATION_C2`/`DISTRIBUTION_C3` — the
divergence F-077 already records. Do not re-conflate them.

### Screenshot ↔ doc correspondence (the two sources validating each other)

| Screenshot behaviour | Checklist phase |
|---|---|
| Sweep of prior swing extreme | Phase 6 |
| Entry on reclaim at the level | Phase 7 (rejection → return → entry) |
| Stop just past the sweep wick | Phase 8 "Stop = CRT invalidation" |
| Target = opposite end of prior range | Phase 8 "Target = HTF CRT objective" |
| Every posted RR in 4.5–8.5 | Phase 8 "Reward ≥ 1:5" |
| HTF Open line on all five charts | the parent-candle ladder itself |

---

## Part 2 — XAUUSD design

XAUUSD is the docs' own worked example (6M equilibrium 3825, 3M OB 4325, ~500-point objective,
`Part2:1006-1015`) and the repo's standing research instrument
(`memory/feedback_xauusd_only_and_distrust_evidence.md`).

### Scope boundaries — declare these before building, not after

1. **6M/3M are unmeasurable on this corpus.** `data/mt5/XAUUSD_M15.csv` spans 2024-05-22 →
   2026-05-21 — exactly 2 years, 47,275 bars = **4 six-month candles and 8 three-month candles**.
   Phase 1's mandatory 6M/3M gate cannot be evaluated at that count, and a 6M gate partitions the
   whole corpus into four blocks. Build the ladder **Monthly-down**; carry 6M/3M as a declared,
   explicitly-unmeasured tier. (Same call the earlier `study-sujantrader-docs` plan already took.)
2. **The five screenshots are not a fidelity test set.** The corpus ends 2026-05-21, his posts are
   ~Aug 2026, and three of his five pairs (NZDCAD, AUDCHF, USDCHF) have no data in the repo at all.
   Using them would require an MT5 fetch extension — out of scope here, worth noting as the only
   route to a true fidelity check.
3. **No G001 authority.** Research only (§6.5). Nothing touches an active config.

### New package `src/research/sujan_crt/`

Follows the sanctioned **reimplement-locally** precedent of `weekly_sweep/` and `visual_crt/`;
production must never import `src/research/`.

| Module | Job | Reuses (do not re-derive) |
|---|---|---|
| `ladder.py` | calendar-true M/W/D/4H parent candles from M15 | `ParentCandleBuilder` via `src/features/htf_bars.py` (F-080 already proved the grid phase) |
| `state.py` | per-TF state + objective | **`src/config_layer/htf_state.py`** — `classify_htf_state`, `resolve_objective`, `HTFState`, `ObjectiveStatus`. Already Sujan's four states; wrap per-TF, do not rewrite |
| `location.py` | Phase 5 location gate | the 9 SMC canonical features from F-076 (order block / breaker / mitigation / PDH-PDL / EQH-EQL) + parent midpoint/high/low |
| `liquidity.py` | Phase 6 sweep | `visual_crt/pools.py` + `geometry.py` (built, tested, F-074-compliant) |
| `activation.py` | Phase 7 chain | `visual_crt/retest.py` for the return leg; F-074 directional displacement |
| `score.py` | the 100-point rubric + ≥90 gate | weights are BEHAVIORAL → config, strict `_require()`, no silent defaults (§6.5) |
| `driver.py` | funnel orchestration + per-phase telemetry | `visual_crt/driver.py` shape |

**Ontology first (§6.6):** register the objective ladder, alignment score, trade-location gate and
the 1:5 rule as canonical nodes in `market_ontology.yaml` **non-frozen sibling sections** before any
production use. `validate_registry() == []` is a gate, not a nicety.

### The measurement design

The 8-phase gate is *built* to reject ~90% of charts, so a faithful implementation lands directly in
the F-026 trap (n=47, INSUFFICIENT_POWER, ~1% funnel completion). The answer is to measure the
**funnel**, not just the final ledger — every rung reported with its own n:

| Rung | Gate | Expected n |
|---|---|---|
| 0 | Phase 6+7 only (sweep + activation) | ≈ F-081's object, n≈944 known |
| 1 | + Phase 5 location | — |
| 2 | + Phase 3/4 daily & 4H objective | — |
| 3 | + Phase 1/2 macro alignment (Monthly/Weekly only) | — |
| 4 | + Phase 8 `≥1:5` | — |
| 5 | full ≥90 rubric | likely single digits — claim nothing |

**The funnel is itself the finding.** It answers "does each phase add or destroy value?" with real
power at the loose end, and makes a small n at Rung 5 legible instead of fatal.

**The headline experiment — Rung 4 with and without the `≥1:5` filter.** Pre-register the
prediction: *the 1:5 gate reduces expectancy, because with target and stop both structurally fixed
it selects thin buffers rather than good trades.* This is the one test that could genuinely surprise,
in either direction.

### Measurement contract — sealed before the detector exists

`MC-SUJAN-XAUUSD-M15-V1` under `configs/research/measurement_contracts/instances/`, floor-green
**before** any detector code (F-081 did this right; F-083 caught what it did wrong — declared but
never executed). Every declared artifact must actually be produced.

- **Cost:** SEM-015 `ComponentCostModel` **ON** — flat 12bps is ~11× too punitive on XAU (F-082).
- **Fills:** SEM-016 `AdverseFill` **ON** — `forward_walk` otherwise books every stop at exactly
  −1.000R.
- **Kernel:** `forward_walk(intrabar_fixed)`. This is **correct here and must be justified in
  writing** against F-088: Sujan's Phase 8 is genuinely one-target, no partial, no trail, so
  `forward_walk` models *his* trade object exactly. Using `multi_tp_walk` would measure a trade he
  does not take. State it so it does not read as a regression.
- **Controls, declared and executed** (`src/research/controls/`): `random_entry`, `long_only`
  (mandatory — gold drift beat 156 of 156 long cells in F-087), plus a **funnel-matched control**:
  same n drawn at random from bars passing Phases 1–2 only. That last one isolates the marginal
  value of Phases 5–8 and is the control F-081 lacked.
- **OOS** split with embargo + purge, actually run, both partitions reported.
- **Null:** block-permutation (F-086's method) for the alignment score, with measured
  autocorrelation → effective n, not raw bar count.

### Build order — cheapest decisive test first

1. **Contract + ontology nodes + controls.** No detector. Floor green.
2. **`ladder.py` + `state.py`** on XAUUSD; assert calendar-true grid and per-TF state series.
   Cheap and independently verifiable.
3. **Rung 0** — reproduce F-081's n≈944 as a calibration check. *If Rung 0 does not roughly
   reproduce, the harness is wrong and everything downstream is noise.*
4. **Rungs 1→5** with per-phase telemetry.
5. **The 1:5 experiment.**
6. Finding + topic sync + session log + `construction_protocol.py validate-completion`.

Stop after step 3 if calibration fails. Steps 1–3 are the afternoon's work and carry most of the
information.

---

## Verification

- `validate_registry() == []`; new ontology nodes present in non-frozen sections only.
- **Byte-identical XAUUSD ledger with the new package absent from the import graph** — this is
  research-side only; nothing in `src/` production may change. `SCHEMA_HASH`, `FEATURE_ORDER_HASH`,
  freeze-pin vector SHA all unchanged.
- Rung 0 n within a stated tolerance of F-081's 944 (calibration gate).
- Every `evidence_artifacts` path in the sealed contract exists on disk **and is git-tracked**
  (the findings gate reads `git ls-files`, not the filesystem).
- `pytest tests/test_current_findings.py tests/test_findings_export.py tests/test_measurement_contract.py tests/test_topic_docs.py tests/test_doc_citations.py`
- Provenance check: `grep -rn "Sujan" src/ configs/` returns **no authority claim** — the docs are
  the *trigger*, and the four-state model and checklist are the AI interlocutor's proposals.
- Determinism: run the driver twice, assert byte-identical funnel counts and ledger.


================================================================================
SOURCE_FILE: docs/implementation_plan/ignore-governance-no-defaults-compiled-music.md
SOURCE_BYTES: 8298
PART: 5/10 FILE 9/16
================================================================================

# CRT Contract Freeze + Code-Grounded Audit (MIAR workflow steps 1–3)

## Context

You froze the MIAR stage-family law (understanding-vs-decision separation) and set the
alignment workflow to **start with CRT**, one model at a time:
`1. Freeze contract → 2. Agree → 3. Audit code → 4. Fix drift → 5. Lock`.
This unit of work executes **steps 1–3 for CRT only**. Steps 4 (fix drift) and 5 (lock →
flip `alignment` to `ALIGNED`) are explicitly **out of scope** here.

Standing rules for this work: **ignore the governance ceremony** (no SESSION LOG mandate, no
`docs/current-findings.md` F-registration, no drift-protocol approval gate, no rehash — this is
intent/documentation only, zero production scoring behavior changes); **no defaults, no
fallbacks, no deletion of any intent**; **on any conflict/ambiguity, ask** (already done — see
Decisions).

What the exploration established:
- CRT's intent contract **already exists** as the MIAR `crt` entry (16 fields) +
  `locked_vocabulary`. "Freeze line-by-line" = ratify those clauses verbatim, plus the new
  stage-family row. There is **no** machine-readable freeze slot beyond `alignment`.
- **Two CRT surfaces.** `src/engines/crt_engine.py::compute` (fusion-slot scorer, delegating to
  `scoring_engine.compute_scores`) is **clean** — emits a bounded `score`, never a probability,
  never approves. The runtime **spine** `src/config_layer/crt_engine_v2.py::CRTEngine` (driven by
  `runtime/backtest_v2.py`) **approves + executes + vetoes** trades via the embedded
  `UltronRiskEngine.approve → open_trade → action=TRADE_OPENED`.
- The spine behavior **contradicts** the Stage-1 law ("CRT — may approve a trade? **Never**") and
  the charter's mandatory Stage-1 non-goal "never decide whether to trade" — which CRT's
  `explicit_non_goals` list currently **omits**. This is the core drift the audit surfaces.
- Three JSON↔MD wording mismatches block a byte-consistent freeze: `hypothesis`, `dependencies`,
  `authority_boundary`.

## Decisions (from user)

1. **Deliverable = single `.md`** — one freeze+audit doc; no `.json` twin.
2. **Reconcile now** — additively fix the JSON↔MD mismatches and add the missing mandatory
   Stage-1 non-goal to CRT's entry (additive only, no deletion).
3. **Document + propose fix** — include a step-4 unbundling proposal, clearly marked
   proposal-not-action.

`alignment` **stays `SEMANTIC_DRIFT`** (🟡): the audit finds unresolved drift (spine approval),
so it cannot flip to `ALIGNED` — that is step 5, out of scope.

## Approach

### Deliverable 1 (NEW): `docs/governance/crt_intent_contract.md`

Single doc, sections in this order (header + Verdict + Key-file-map mirror the existing
`*_lineage_audit.md` template so it reads as a repo-native governance artifact):

- **Header block** — `Program:` MIAR CRT freeze steps 1–3 · `Date (UTC):` 2026-07-28 ·
  `Authority:` intent-only, no scoring behavior changed · `Prerequisite:` CRT closure CLOSED
  (`crt_closure_report.md`) + `crt_formula_contract.md` Phase 2 (cite, do not reopen/duplicate).
- **Verdict** (fenced `text` block): `CRT_INTENT_CONTRACT = FROZEN (steps 1–3)`,
  `ALIGNMENT = SEMANTIC_DRIFT (unresolved)`, `PRIMARY_DRIFT = spine approves/executes trades`,
  `STEPS_4_5 = out of scope`.
- **§A — Frozen contract, line by line.** Table: `clause | verbatim text | source file:line |
  agreed`. Clauses = the 16 MIAR `crt` fields + the stage-family row (locked question +
  "may approve a trade? Never") + the four `locked_vocabulary` terms the contract leans on
  (Structure / Score / Probability / Confidence, verbatim from
  `MODEL_INTENT_AUTHORITY_REGISTER.md §0.3` / `miar_registry.json:748-761`) + the mandatory
  Stage-1 non-goal.
- **§B — Reconciliations applied** (additive; before→after, so nothing is silently changed):
  `hypothesis` (JSON "Sweep to retest…" → MD's fuller "Sweep→displacement→expansion→retest…",
  which matches the actual golden path); `dependencies` (MD "ontology geometries" → name
  `market_ontology` as in JSON); `authority_boundary` (JSON bare → MD "; may open structural path
  to risk"); and **added** non-goal `"never decide whether to trade"` (charter §46 mandate).
- **§C — Code audit (step 3).** Two-surface table: each contract clause → code evidence
  (file:line) → `ALIGNED` / `DRIFT`. Fusion-slot scorer = ALIGNED. Spine = DRIFT on
  "never approve" / "never decide whether to trade". Also record the pre-existing dual-math-path
  drift (FSM `RiskScore.final` vs `compute_scores` retest) that is the current 🟡 reason.
- **§D — TruthConflict (primary).** `Source A` (Stage-1 law / added non-goal) vs `Source B`
  (spine code: `crt_engine_v2.py` `UltronRiskEngine.approve` ~2016–2094 /
  `approve_with_soft_conf` ~1930–2012 / `open_trade`+`TRADE_OPENED` ~3096–3121) · evidence ·
  impact · recommendation (→ step 4).
- **§E — Proposed step-4 remediation (PROPOSAL, NOT ACTION).** Unbundle the Stage-1 structure-FSM
  from the embedded Stage-3/4 `UltronRiskEngine` **without deleting any intent** — the approval
  logic is relocated/owned by the correct stage, not removed. Sketch options only; no code.
- **§F — Key file map** (Role / Path table) and **§G — Final return** block
  (`FROZEN` / `STILL_DRIFTED` / `DO_NOT` reopen closure / `NEXT = step 4`).

### Deliverable 2 (EDIT, additive): `docs/governance/miar_registry.json` — `crt` entry (:116-154)

- `hypothesis` (:119) → `"Sweep to displacement to expansion to retest sequences mark actionable structure."`
- `authority_boundary` (:134) → append `; may open structural path to risk` (match MD).
- `explicit_non_goals` (:135-139) → **append** `"never decide whether to trade"` (additive).
- Bump top-level `updated` (:5). Leave `alignment: "SEMANTIC_DRIFT"` unchanged. `dependencies`
  already lists `market_ontology` — no JSON change there.

### Deliverable 3 (EDIT, additive): `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` §3.3 (:239-258)

- `dependencies` (:253) → name `market_ontology` (align to JSON).
- `explicit_non_goals` (:252) → add "**never** decide whether to trade".
- Optionally add a `notes` line pointing to `crt_intent_contract.md` (freeze audit trail).
  Update the §-rollup alignment table only if it currently mis-states CRT (keep 🟡).

## Critical files

- **Create:** `docs/governance/crt_intent_contract.md`
- **Edit (additive):** `docs/governance/miar_registry.json` (crt entry), `docs/governance/MODEL_INTENT_AUTHORITY_REGISTER.md` (§3.3)
- **Cite, do not modify:** `src/config_layer/crt_engine_v2.py` (spine: `UltronRiskEngine.approve`,
  `approve_with_soft_conf`, `open_trade`/`TRADE_OPENED`, `RiskScore.final`),
  `src/engines/crt_engine.py::compute`, `src/engines/scoring_engine.py::compute_scores`
  (weights `(0.35,0.25,0.20,0.20)`), `src/config_layer/state_identity.py` (9 states,
  VALID_TRANSITIONS, the "never alias" weight-identity note), `src/core/engine_runner.py`
  (fusion-slot wiring, DecisionEngine = sole EXECUTE/REJECT authority),
  `docs/governance/crt_closure_report.md`, `docs/governance/crt_formula_contract.md`,
  `docs/topics/crt-spine.md`.

## Verification

- `python -m pytest tests/test_miar_registry.py -q` → **must stay 9 passed** after the additive
  registry edits (adding a non-goal keeps `explicit_non_goals` non-empty; 17-entry order, intent
  uniqueness, single-owner matrix, locked-vocab keys all unaffected).
- Manual: confirm `miar_registry.json` `crt` entry and MD §3.3 are now byte-consistent on
  `hypothesis` / `dependencies` / `authority_boundary` / `explicit_non_goals`.
- Manual: confirm the freeze doc's §A clauses each carry a real `file:line` source and the §C
  audit rows each carry a real code `file:line`; spot-check 3–4 citations against source.
- No code changes → no behavior/parity tests needed (intent-only, per Authority line).

## Out of scope (do not do)

- Step 4 (fix drift) — no edits to `crt_engine_v2.py` / `UltronRiskEngine`; the §E remediation is
  a written proposal only.
- Step 5 (lock) — do **not** flip `alignment` to `ALIGNED`.
- Do not reopen CRT closure phases (`crt_closure_report.md` is frozen).
- No governance ceremony (SESSION LOG, F-registration, rehash) per the standing instruction.


================================================================================
SOURCE_FILE: docs/implementation_plan/ill-share-two-prompts-moonlit-key.md
SOURCE_BYTES: 10277
PART: 5/10 FILE 10/16
================================================================================

# PHASE 1 — OHLCV Truth Closure — PASS B (Blocked-State Adjudication) execution plan

> **Rev 3.** PASS A is complete and frozen (evidence: 9 governance artifacts + census generator +
> manifest + validator test; see layer-audit-manifest.json). The user's adjudication authorizes
> **PASS B as BLOCKED-STATE adjudication**: the expected outcome is
> `OHLCV_CLOSURE_STATUS = BLOCKED:<minimal blocker set>`, derived honestly — not forced either way.
> User adjudication of BC-1…6 (all BLOCKER variants) is a **recommendation to verify, not a
> conclusion to copy** (§13.8: advice is non-binding; evidence decides). Dissent with evidence is
> allowed and must be explicit.

## Context

PASS A proved row-level integrity is clean (0/224 violations) but corpus **identity + semantics +
provenance** are not closed: 9 logical corpora resolve to different bytes under one name; canonical
root crypto descends from the ungated yfinance family; `volume` = 5 quantities under one column;
open-time labeling + yfinance tz + forming-bar protection unproven; canonical XAUUSD ≡ quarantined
bytes. PASS B must adjudicate every BC/CX against the frozen artifacts, derive a fail-closed
machine-readable output contract **from PROVEN guarantees only**, and emit the closure verdict +
remediation prerequisites. **No remediation, no doc edits to PASS-A artifacts, no economic claims,
no Phase 2.**

## Governing rules (from the user's adjudication — mandatory)

1. **Independent verification first**: every BC-1…6 and CX-001…010 re-verified against the frozen
   PASS-A artifacts (+ targeted read-only probes) BEFORE classification. Concur/dissent recorded
   per item with evidence.
2. **C1 verdict grammar**: only `CLOSED` or `BLOCKED:<reason>`; every unresolved item classified
   `BLOCKER` or `PROVEN_NON_BLOCKER` (positive evidence required for the latter); UNKNOWN affecting
   active-path semantics/identity/provenance/reproducibility = BLOCKER.
3. **Contract = current enforcement, not aspiration** (the stated Most Likely Failure Mode): every
   guarantee binds `authoritative_producer` + `runtime_enforcer` + `evidence` (executable/static/
   reproducible refs) + `contradiction_status`, and carries
   `guarantee_status ∈ {PROVEN, UNPROVEN, CONTRADICTED}`. A guarantee with no runtime enforcer is
   at best UNPROVEN even if the data is currently clean. Any handoff-required guarantee UNPROVEN or
   CONTRADICTED ⇒ BLOCKED.
4. **Corpus-family scoped admissibility**: BC-2 adjudicated per family (active acquisition vs
   immutable historical), BC-6 yfinance-scoped; the contract carries a per-family admissibility
   table, not a global verdict.
5. **BC-3 discipline**: do NOT resolve by declaring Binance authoritative — record that current
   canonical-crypto authority is unproven. Adjudication ≠ remediation.
6. **Matrix metrics split**: mutation registration ≠ detection coverage. Closure report + contract
   carry explicit `failure_classes_registered=29 / canonical_seeds_defined=29 /
   detectors_implemented=21 / clean_path_probes_green=NOT_MEASURED /
   mutants_killed=NOT_MEASURED / mutation_score=NOT_MEASURED`. Never allow "29/29 seeds" to read
   as E-MT-01 COMPLETE. (PASS-A matrix JSON stays frozen; metrics live in the new PASS-B
   artifacts.)

## Independent-verification probes (read-only; step 1 of execution)

- **BC-5 lineage probe (the one item that may flip):**
  (a) `reports/dataset_integrity/XAUUSD_M15.json` (+ any XAUUSD entries) — recorded `decision`,
  `hard_failures`, `file_hash` vs census sha for `data/XAUUSD_M15.csv` and
  `data/mt5/_rejected/XAUUSD_M15.csv`;
  (b) `HANDOFF.md` `standing_rules.canonical_corpus` sha `4d73f5ce…` vs census hash — if it matches
  the current bytes, HANDOFF *knowingly* pinned these bytes as canonical (promotion-by-decision
  evidence);
  (c) session-log archives (`docs/analysis/session-log-archive/`) + `assistant_project.md` for the
  H-SECONDLOW XAUUSD quarantine/promotion narrative;
  (d) file mtimes (weak, corroborating only).
  Outcome: BLOCKER (lineage unproven) or PROVEN_NON_BLOCKER (documented known-gap acceptance).
- **CX-006 positive-evidence probe**: grep configs + `.env`-adjacent config surfaces (NOT `.env`
  itself) for `db_url`/timescale wiring; confirm `correlation_engine.py:77` activation condition is
  unreachable on this branch (who calls it, with what config). Target: PROVEN_NON_BLOCKER.
- **CX-005 positive-evidence probe**: re-confirm zero readers of `_rejected/`/`_archive_5wk/`
  (grep already run in PASS A; re-cite) + confirm gate verdict is config-contextual
  (strict_fetch override) → PROVEN_NON_BLOCKER with evidence.
- **BC-1/3/4 spot re-verification**: recompute 2–3 census hashes independently (`sha256sum`) to
  confirm the manifest is faithful; re-cite fetch-script lines.
- **BC-2/6**: verify the NARRATIVE-ONLY tags are still the strongest available repo evidence (no
  overlooked executable proof, e.g. parity tests between mt5 and binance overlapping instruments —
  there are none: families don't overlap instruments except via root copies).

## Deliverables (all NEW files; PASS-A artifacts untouched)

| # | Artifact | Content |
|---|---|---|
| 1 | `docs/governance/ohlcv-output-contract-2026-07-10.json` | Machine-readable contract: (a) `guarantees[]` — each with id, statement, scope (global or family), authoritative_producer, runtime_enforcer (or `none`), evidence[{type: executable/static/reproducible/narrative, ref}], contradiction_refs, `guarantee_status`; (b) `corpus_families{}` — per family: identity binding requirements (`logical_corpus_id + physical_path + sha256 + authority_class + source_family + transformation_chain`), volume_semantic, timestamp_semantic (+status), admissibility (`ADMISSIBLE_WITH_BINDING / NOT_ADMISSIBLE_AS_AUTHORITATIVE / EXCLUDED`); (c) `handoff_required_guarantees[]` (the set whose non-PROVEN status blocks closure); (d) `forbidden_substitutions[]` (from Prompt-2 §7 + T-003/T-006); (e) `trust_status` with the 6-metric matrix split; (f) verdict echo. Fail-closed: consumers must reject a corpus lacking a binding entry |
| 2 | `docs/governance/ohlcv-closure-report-2026-07-10.md` | CRT closure grammar: header (pinned commit, twins); **BC/CX adjudication table** — per item: user classification, independent verification result, final `BLOCKER / PROVEN_NON_BLOCKER`, concur/dissent + evidence; 12-criteria closure-gate walk (each PASS/FAIL with refs); matrix metrics split; guarantee rollup (n PROVEN / UNPROVEN / CONTRADICTED); **remediation prerequisites** — per final BLOCKER, the minimal proof/mechanism that would flip it (design-level only, no changes); return block ending with the literal verdict token |
| 3 | `docs/governance/layer-audit-manifest.json` (UPDATE — the one intentionally-stable mutable manifest) | phase_status → `PASS_B_ADJUDICATED`; `closure_verdict = "BLOCKED:<minimal blocker set>"` (exact composition decided by the verification, e.g. `BLOCKED:BC-1,BC-2[acquisition-families],BC-3,BC-4,BC-5?,BC-6[yfinance]`); closure_report + output_contract paths; refreshed artifact hash list incl. the two new artifacts |
| 4 | `tests/test_ohlcv_output_contract.py` | Validator: schema shape; **no guarantee may be PROVEN with only narrative evidence**; no guarantee PROVEN with `runtime_enforcer: none` unless evidence type is executable; every handoff-required guarantee non-PROVEN ⇒ manifest verdict MUST be BLOCKED (fail-closed consistency); matrix metrics keys present and mutation_score ≠ implied-complete |
| 5 | SESSION LOG entry in `assistant_project.md` (+ finding decision: file a new F-05x GOV finding for the identity-unbound conclusion in `docs/current-findings.md`? — **only with user approval per §6.2 gate**; the plan DEFERS the finding registration and lists it as a follow-up question in the closure report) |

## Execution order

1. Run the independent-verification probes (read-only) → record concur/dissent per BC/CX.
2. Derive the guarantee inventory from the frozen temporal/transformation/census artifacts →
   assign guarantee_status (expect: STATIC/EXECUTABLE-backed rows PROVEN; NARRATIVE-ONLY rows
   UNPROVEN; CX-003/CX-008-touched rows CONTRADICTED or UNPROVEN as evidence dictates).
3. Build the per-family admissibility table (mt5 / binance / yfinance / data_root FX / data_root
   crypto / resampled / archive / quarantine / perp-excluded).
4. Write the output contract JSON (#1), then the closure report (#2) with the 12-criteria walk and
   the final minimal blocker set.
5. Update the layer manifest (#3), write the contract validator test (#4).
6. Verify: `venv/Scripts/python.exe -m pytest tests/test_layer_audit_manifest.py
   tests/test_ohlcv_output_contract.py -q` green; census `--check` still PASS (PASS-A artifacts
   unmodified); `git status` = new files + manifest + session log only.
7. SESSION LOG append; final report with the verdict token; **STOP** — remediation design is a
   separate follow-up authorization.

## Hard constraints

- No modification of PASS-A artifacts, production code, configs, findings, or existing docs
  (the layer manifest is the sole designed-mutable file; its hash-guard test is regenerated with it).
- No remediation of any kind (no re-fetching, no re-pointing canonical paths, no declaring Binance
  authoritative, no volume metadata implementation).
- Verdict grammar strict: final line is exactly `OHLCV_CLOSURE_STATUS = BLOCKED:<reason>` (or
  `CLOSED` in the unlikely event verification dissolves every blocker — do not force either way).
- `.env` never read. No economic claims. Do not begin Phase 2.

## Verification

1. Both validator tests green; existing `tests/data_ingestion/` still green.
2. `ohlcv_census.py --check` = PASS (proves PASS-A evidence untouched).
3. `grep "OHLCV_CLOSURE_STATUS" docs/governance/ohlcv-closure-report-2026-07-10.md` returns exactly
   one verdict line matching the C1 grammar; the manifest's `closure_verdict` matches it.
4. Contract JSON: every PROVEN guarantee has ≥1 non-narrative evidence ref (enforced by test #4).
5. Final response: adjudication table (concur/dissent per BC/CX), guarantee rollup, minimal blocker
   set, remediation prerequisites summary, SESSION LOG — and stops before any remediation.


================================================================================
SOURCE_FILE: docs/implementation_plan/in-the-tradelatest-repo-piped-gem.md
SOURCE_BYTES: 2878
PART: 5/10 FILE 11/16
================================================================================

# Fix 6 stale doc citations (CLAUDE.md §6.3 Citation Sync)

## Context
`tests/test_doc_citations.py::test_every_code_citation_resolves` is RED. The test
(`tests/test_doc_citations.py`) scans mapped docs for dual-form `path:line · Symbol`
citations and asserts the symbol sits within ±30 lines of the cited line. Six citations
drifted because code moved underneath them. The fix is purely mechanical "code moved,
docs didn't" — update each cited line number to the symbol's current location (and
normalize/qualify two ambiguous paths). **Doc-only; no code changes.** `docs/` is
gitignored on `patch`, so edits live on disk only — expected.

Live locations confirmed via grep + the test's own DRIFT report.

## Edits

**1. `docs/current-findings.md:98`** (F-004 Evidence) — keep conclusion, fix line only.
- `crt_engine_v2.py:1805 · bitnet_main_score` → `:1756` (the `if bitnet_main_score < 0.55:`
  line the prose quotes; symbol cluster is 1749–1757).
- Leave the same line's `:363 · bitnet_main_threshold` untouched (not regex-matched, not flagged).

**2. `docs/architecture/entry-exit-map.md:29`** (Live tick row)
- `src/runtime/live_engine_hook.py:590 · process` → `:523` (`def process(` is at line 523).

**3. `docs/architecture/entry-exit-map.md:46`** (Config promotion row)
- `src/governance/promotion_manager.py:583 · _write_to_registry` → `:499` (`def _write_to_registry` at 499).
- Leave the same line's `:723 · _log_event` untouched (not flagged).

**4. `docs/architecture/entry-exit-map.md:62`** (load-bearing caveat prose)
- `live_engine_hook.py:590 · process` → `src/runtime/live_engine_hook.py:523 · process`
  (fix line AND add the `src/runtime/` prefix to normalize the bare basename).

**5. `docs/topics/ai-automation-agent.md:21`** (AMBIGUOUS — two `cli.py` exist)
- `cli.py:49 · main` → `src/agent/cli.py:49 · main` (line 49 is already correct; just qualify
  the path to the agent CLI, disambiguating from `src/research/cli.py`).

**6. `docs/topics/crt-spine.md:20`** (two citations on this line)
- `crt_engine_v2.py:1099 · VALID_TRANSITIONS` (enforcement) → `:1050` — this is the RED one.
- `crt_engine_v2.py:1074 · VALID_TRANSITIONS` (the def) → `:1025` — currently passes the
  window but is inaccurate; refresh while here (def is at 1025).

## Optional accuracy fix (not test-enforced)
**`CLAUDE.md §4`** CRTState bullet cites `VALID_TRANSITIONS` (`crt_engine_v2.py:981`). This is
the symbol-before-path form, so the test regex does NOT match it (not RED). The line is stale
(def now at 1025). Refresh `:981` → `:1025` for accuracy. Doc-only, low risk.

## Verification
```
python -m pytest tests/test_doc_citations.py -q
```
Expect `2 passed`. (`test_mapped_docs_exist` + `test_every_code_citation_resolves`.)

## Per CLAUDE.md §6: append the SESSION LOG ENTRY block to `assistant_project.md` on completion.


================================================================================
SOURCE_FILE: docs/implementation_plan/intelligence-compounding-doctrine-core-crystalline-walrus.md
SOURCE_BYTES: 9328
PART: 5/10 FILE 12/16
================================================================================

# Audit — Pasted Intelligence Compounding Doctrine vs. Canonical Repo

## Context

The user pasted a clean restatement of the **Intelligence Compounding Doctrine**. The doctrine
is already frozen in three coordinated locations:

- **`CLAUDE.md` §6.1** (condensed, always-loaded) + **§7.4** (the `Belief Update / ROI / Goal`
  SESSION LOG field that operationalizes it)
- **`docs/architecture/intelligence-compounding.md`** — the long-form (utility function,
  goal-first chain, modules-as-frozen-thoughts table, 7-level ladder, Memory Rule, entropy
  principle, Stage 1→7 evolution path)
- **Memory** `project_intelligence_compounding_doctrine.md` (frozen 2026-06-11)

The user selected **"Audit faithfulness"**: a line-by-line comparison of the pasted text against
those canonical locations, flag any drift or gaps, **report findings, make no edits until the
user decides.** This file IS the audit deliverable. No code or doc changes are proposed for
execution yet — only findings + optional reconciliations for the user to approve.

---

## Verdict

The pasted doctrine is a **faithful, leaner subset** of the canonical doctrine. Same north star
("zero intelligence loss + continuous compounding"), same forbidden `Tool output → Memory`
shortcut, same "modules are frozen thoughts," same "enemy is fragmented meaning." The canonical
docs are a **superset** — they add the operational machinery (utility function, SESSION LOG
hook, three checklists, Stage 1→7 path) that the pasted version omits.

**One genuine semantic conflict** and **two chain-anchoring drifts** are worth the user's
attention. Everything else is cosmetic/labeling.

---

## Findings

### 🔴 F1 — Memory Rule recoverability line CONTRADICTS the immutable canonical line
- **Pasted:** "Meaning without artifacts is recoverable. Artifacts without meaning are noise."
- **Canonical** (`intelligence-compounding.md:215`, marked *immutable doctrine — do not soften*;
  echoed in CLAUDE.md §6.1 and the memory file): **"Artifacts are recoverable. Meaning is not."**
- **Conflict:** the pasted line asserts *meaning IS recoverable*; the canonical immutable line
  asserts *meaning is NOT recoverable*. These are logically opposite on the recoverability of
  meaning. Canonical is explicitly flagged immutable.
- **Recommendation:** keep the canonical immutable line as authoritative. The pasted phrasing is
  a looser paraphrase whose intended point ("meaning > artifacts") is already carried by the
  canonical line. **Do not adopt the pasted wording.** If the user wants the "artifacts without
  meaning are noise" flavor, it can be added as a *non-conflicting* second sentence without
  touching the immutable line.

### 🟠 F2 — Pasted "Meaning Over Data" chain is artifact-first; canonical is goal-first
- **Pasted:** `Artifact → Purpose → User Intent → Goal Contribution → Economic Value → ROI →
  Belief Update → Future Decisions` (starts at Artifact, Goal sits mid-chain).
- **Canonical** (`intelligence-compounding.md:76-94`): `User Goal → Economic Objective → Tool →
  Output → ROI Evaluation → Belief Update → Memory → Future Decisions → Goal Probability`, with
  the explicit doctrine "ROI is undefined without a goal, so the chain is anchored to the user's
  objective end-to-end — never to 'belief update' in the abstract."
- **Drift:** the pasted chain is a *softening* — it leads with the artifact rather than the
  goal. Not a contradiction (Goal Contribution appears), but it weakens the canonical
  "goal-FIRST" insistence.
- **Recommendation:** canonical goal-first ordering stays authoritative. No change needed.

### 🟠 F3 — Pasted ROI-interpretation chain omits the explicit goal/purpose node
- **Pasted** (§"Tool Outputs Require ROI Interpretation"): `Tool → Output → ROI Evaluation →
  Belief Update → Memory → Future Decisions`.
- **Canonical** (CLAUDE.md §6.1 forbidden path): `Tool → Output → Purpose → User Intent →
  Economic Objective → ROI → Belief Update → Memory`.
- **Drift:** pasted jumps Output → ROI without naming Purpose/Economic Objective. Since the
  canonical principle is "ROI without a goal is undefined," the goal node is load-bearing.
- **Recommendation:** canonical (with the explicit Purpose/Objective node) stays authoritative.

### 🟡 F4 — Intelligence *definition* drops "ROI-weighted" / "probability"
- **Pasted:** "A persistent change in beliefs that improves future decisions toward the user's
  long-term goals."
- **Canonical:** "an ROI-weighted belief change that increases the *probability* of achieving
  the user's long-term objectives — not accumulated data."
- **Assessment:** compatible; pasted is a plain-language gloss. Canonical keeps the quantitative
  framing (`Intelligence = ROI-weighted belief change × effect on goal probability`,
  `intelligence-compounding.md:44`). Cosmetic — no action.

### 🟡 F5 — "Intelligence Checklist" (flat) vs "7-level ladder" (climb)
- Same seven questions (What is this → How should future decisions change), reframed as a flat
  checklist instead of a ladder you "climb." Cosmetic — no action.

### 🟡 F6 — Pasted version omits the operational machinery (this is expected, not a gap)
- Pasted has **no**: utility function, SESSION LOG `Belief Update / ROI / Goal` hook, the three
  permanent checklists, artifact metadata/governance schema, entropy principle (by name), or the
  Stage 1→7 evolution path with the "no premature framework" guardrail.
- **Assessment:** the pasted text is a statement of *principle*; canonical is principle +
  operationalization. This is the correct relationship (CLAUDE.md §6.1 condensed ↔ long-form
  doc). **Not a faithfulness defect.** No action — canonical is intentionally richer.

---

## Summary table

| ID | Type | Item | Canonical authority | Action |
| --- | --- | --- | --- | --- |
| F1 | 🔴 Conflict | "Meaning... is recoverable" | `intelligence-compounding.md:215` (immutable) | Keep canonical; reject pasted wording |
| F2 | 🟠 Drift | Artifact-first chain | `:76-94` goal-first | Keep canonical |
| F3 | 🟠 Drift | ROI chain skips goal node | CLAUDE.md §6.1 | Keep canonical |
| F4 | 🟡 Cosmetic | Definition gloss | `:44` | None |
| F5 | 🟡 Cosmetic | Checklist vs ladder | `:194-204` | None |
| F6 | 🟡 Expected | Pasted omits machinery | long-form doc | None |

---

## Recommended outcome (no edits made; user decides)

**Net: the canonical doctrine already captures the pasted text faithfully and is the stronger,
richer version. No edits are required to stay faithful.** The single thing worth a decision is
**F1** — the pasted "meaning is recoverable" line directly contradicts the immutable canonical
"Meaning is not [recoverable]" line. My recommendation is to keep canonical as-is and not adopt
the pasted wording.

If, after reading this audit, the user wants any reconciliation, the **only** doc-only edit I'd
propose is optional and additive:
- Append a non-conflicting sentence to the Memory Rule capturing the pasted "artifacts without
  meaning are noise" emphasis — **without** touching the immutable "Artifacts are recoverable.
  Meaning is not." line — in `docs/architecture/intelligence-compounding.md` (and mirror one
  clause into CLAUDE.md §6.1 if desired).

No other edits recommended. Everything else in the pasted text is already present, equal, or
weaker than canonical.

---

## Verification

This is a read-only doc audit; verification = re-reading the cited lines:
- `docs/architecture/intelligence-compounding.md` lines 11-13 (frozen sentence), 44 (utility
  function), 76-100 (goal-first + forbidden path), 215 (immutable Memory Rule line),
  194-204 (7-level ladder).
- `CLAUDE.md` §6.1 (forbidden `Tool → … → Memory` path) and §7.4 (SESSION LOG field).
- Memory `project_intelligence_compounding_doctrine.md` (frozen-sentence + "immutable doctrine
  line" echo).
If the user approves the optional F1-adjacent additive sentence, re-read the Memory Rule block
after editing to confirm the immutable line is untouched.

---
📝 SESSION LOG ENTRY
Date: 2026-06-11
Topic: Audit of user-pasted Intelligence Compounding Doctrine vs. canonical repo (CLAUDE.md §6.1/§7.4, long-form doc, memory).
Decision/Output: Pasted text is a faithful leaner subset of canonical (which is the superset). 6 findings: F1 = genuine conflict (pasted "meaning is recoverable" vs canonical immutable "Meaning is not"); F2/F3 = goal-first vs artifact-first chain drift; F4-F6 cosmetic/expected. Recommend keep canonical; no edits required; optional additive non-conflicting Memory-Rule sentence only if user wants.
Belief Update / ROI / Goal: Goal: zero intelligence loss / doctrine coherence. Belief: canonical doctrine already dominates the pasted restatement; the only real risk is the F1 wording contradicting the immutable line. Knowledge ROI: medium (confirms no drift to repair except one paraphrase conflict). Action: hold for user decision on F1; do not soften the immutable line.
Open Questions: Does the user want the optional additive Memory-Rule sentence (F1-adjacent), or leave canonical untouched?
Next Step: Await user decision via ExitPlanMode approval; if approved with "leave as-is," no changes — audit stands as the deliverable.
---


================================================================================
SOURCE_FILE: docs/implementation_plan/is-codebase-dirty-elegant-planet.md
SOURCE_BYTES: 15512
PART: 5/10 FILE 13/16
================================================================================

# Commit Plan — snapshot working tree onto a new branch (no switch, Grok untouched)

## Context

`feature/truth-registry-v2` is 23 commits ahead of origin with **122 modified + 212 untracked**
paths (real content: +7,568 / −2,081 ignoring whitespace; `core.autocrlf=true` is *not* what's
inflating it). Nothing is staged.

This is the F-071 failure mode re-accumulating: 19 untracked modules under `src/` means the
committed repository is again not the running system. Several closed findings (F-074…F-084) cite
files that exist only on disk — `src/features/smc/`, `src/research/visual_crt/`,
`tools/tv_forensic/`, `src/config_layer/parent_crt.py`. Their evidence is unresolvable from a
clean checkout today.

**Two hard constraints from the user:**

1. A **Grok session is running in parallel** — do not touch its changes.
2. Commit to a **new branch without switching to it** — 12 other Claude worktrees share this
   `.git`, and this working tree is live.

Intended outcome: every non-Grok, non-junk change lands as a dependency-ordered commit series on a
new branch ref, while the working tree and `HEAD` remain **bit-for-bit unchanged**.

---

## Mechanism — commit without switching

`git checkout -b` / `git switch -c` move `HEAD` and are rejected here. Use plumbing against a
**temporary index file**, which never touches `.git/index`, `HEAD`, or a single file on disk:

```bash
export TMPIDX="$SCRATCH/commitplan.idx"
export GIT_INDEX_FILE="$TMPIDX"
PARENT=$(git rev-parse HEAD)          # 84fff51

# --- repeat per commit N ---
rm -f "$TMPIDX"
git read-tree "$PARENT"               # seed temp index from the parent commit's tree
git add -- <paths for commit N>       # honors GIT_INDEX_FILE, recurses dirs, respects .gitignore
TREE=$(git write-tree)
PARENT=$(git commit-tree "$TREE" -p "$PARENT" -F <msgfile>)
# --- end repeat ---

git branch snapshot/tree-restore-2026-08-19 "$PARENT"   # create ref; does NOT switch
unset GIT_INDEX_FILE
```

Safety properties:

- `HEAD` stays at `84fff51` on `feature/truth-registry-v2`; `git status` in the main tree is
  identical before and after.
- Other worktrees keep their own `.git/worktrees/<name>/index` — untouched.
- Object writes are concurrency-safe; `git branch` creates one new ref.
- `git add` applies the same `core.autocrlf` clean filter as a normal `git add`, so blobs are
  byte-identical to what a normal commit would produce.

**Hook caveat (must be handled manually).** `core.hooksPath=D:\Tradelatest\hooks`, and
`commit-tree` bypasses `pre-commit` / `commit-msg`. Run both gates by hand instead:

```bash
python scripts/maintenance/check_governance_invariants.py
```

and satisfy the §6 commit-linkage rule (`scripts/maintenance/check_session_log_commit.py`) — every
commit touching `src/**` or `configs/production/**` needs a same-day SESSION LOG entry in
`assistant_project.md`, which is already modified in this tree and lands in commit 15.

**Not doing:** no push, no `--force`, no rewriting `feature/truth-registry-v2`, no deletions, no
`git add -A`.

---

## Exclusion set 1 — Grok (DO NOT TOUCH)

Verified as a self-contained workspace, last written 2026-08-18 16:31:

```
.grok/                                                    # incl. rules/GROK.md, PENDING.md, run_mc_crt_sb*.py
GROK.md
grokclosure.txt
groksessionauto.txt
tests/Grok/
tests/test_grok_intent_workbook.py
docs/analysis/grok_test_intent.xlsx
docs/implementation_plan/analyse-last-grok-code-humming-leaf.md
docs/implementation_plan/topic-ladder-and-grok-test-intent-excel.md
configs/research/research_config_mc_crt_sb_xauusd.json    # referenced ONLY from .grok/run_mc_crt_sb*.py
```

## Exclusion set 2 — test-intent workbook effort (user decision: exclude entirely)

Both twins plus the shared generator, since the generator was written one minute before Grok's
workbook and may still be in flight:

```
tests/Claude/                                             # untracked
tests/test_claude_intent_workbook.py                      # untracked
docs/analysis/claude_test_intent.xlsx                     # untracked
docs/analysis/feature-identity-state-inventory-2026-08-19.xlsx   # untracked, Excel lock file present
docs/analysis/~$feature-identity-state-inventory-2026-08-19.xlsx # Excel lock — never commit
claudeclosure.txt                                         # untracked, pairs with grokclosure.txt
scripts/analysis/test_functionality_excel.py              # MODIFIED — leave dirty
docs/analysis/tests_functionality_inventory.xlsx          # MODIFIED — leave dirty
scripts_business_functionality.xlsx                       # MODIFIED — leave dirty
```

## Exclusion set 3 — bulk / junk (gitignored in commit 1, never committed)

```
tools/oss_lab/            283 MB  vendored third-party Codebase-Memory repo
tools/tv_forensic/shots/   12 MB  TV screenshots
xauusd_backtest_run/        9 MB  run output (same class as the already-ignored results/)
ui_kits/crt_dashboard/    4.5 MB
docs (2).zip, docs (3).zip, scripts (2).zip   6.3 MB stale archives
bundles/who_how_what_bundle.zip
agent-tools/<uuid>.txt    session scratch
```

`__pycache__/` is already covered by `.gitignore:1`, so `git add` skips it automatically.

> **One assumption to confirm at execution time:** the user wrote "oos_lab" — read as
> `tools/oss_lab/` (the 283 MB vendored tree). Repo-root **`oss_lab/`** is different: it is already
> tracked, contains real governance work, and **is** committed (commit 13). Gitignoring a tracked
> path has no effect on tracked files but would hide the 5 legitimate untracked files under it.

---

## Commit sequence

Dependency-ordered (F-071 lesson: each commit must import cleanly on its own). Paths are prefixes
— `git add` recurses.

| # | Message (subject) | Paths |
|---|---|---|
| 1 | `chore(gitignore): exclude vendored OSS, TV shots, run output, stale archives` | `.gitignore` (edit), `.cbmignore` |
| 2 | `feat(features): SMC primitives + canonical schema v4.0→v5.0 (F-076)` | `src/features/smc/`, `src/features/feature_schema.py`, `feature_pipeline.py`, `crt_feature_builder.py`, `tests/test_smc_primitives.py`, `docs/governance/feature-layer-freeze-pin-2026-07-20.json`, `configs/market_reality/market_reality_v1.yaml` |
| 3 | `feat(crt): directional displacement contract (F-074)` | `src/config_layer/crt_engine_v2.py`, `state_identity.py`, `configs/formulas/market_crt_states.yaml`, `tests/test_directional_displacement.py`, `test_retrace_reset_direction.py`, `test_crt_states_yaml_transition_parity.py`, `docs/governance/build_manifests/CH-directional-displacement-contract.*` |
| 4 | `feat(htf): parent CRT + HTFState/ObjectiveStatus (F-075, F-078)` | `src/config_layer/parent_crt.py`, `htf_state.py`, `src/features/parent_candle.py`, `src/runtime/parent_crt_feed.py`, `configs/production/v2_htfcrt_2026_08.json`, `v2_htfcrt_objgate_shadow_2026_08.json`, `tests/test_parent_*`, `tests/test_htf_*`, `scripts/research/htf_*`, manifests `CH-htf*`, `CH-parent-crt-caller-wire.*` |
| 5 | `feat(structure): M15 structural range + structure predicate registry` | `src/config_layer/m15_structural_range.py`, `src/structure/`, `src/features/registry/predicate_registry.py`, `src/features/registry/__init__.py`, `derived_registry.py`, `configs/formulas/structure_profiles.yaml`, `tests/test_m15_structural_range.py`, `test_structur*`, `test_predicate_definition_binding.py`, manifests `CH-PSTRUCT-*`, `CH-p-struct-*`, `CH-m15-structural-liquidity-range.impact.json`, `CH-structure-dimension-inventory.impact.json` |
| 6 | `feat(governance): Semantic OS grounding + adversarial review protocol (§6.7/§6.8, F-079)` | `src/governance/semantic_grounding.py`, `semantic_os.py`, `docs/governance/semantic_os/`, `SEMANTIC_OS_CONTRACT.md`, `SEMANTIC_OS_V1_DESIGN.md`, `SEMANTIC_REVIEW_PROTOCOL.md`, `scripts/governance/query_semantic_os.py`, `src/agent/modes/truth_mode.py`, `plan_compiler.py`, `tests/test_semantic_grounding.py`, `test_semantic_query.py`, `tests/governance/test_semantic_review_protocol.py`, manifests `CH-closed-semantic-environment.*` |
| 7 | `feat(ingestion): OHLCV clock detection + provenance registry (F-066 follow-on)` | `src/data_ingestion/clock_detector.py`, `clock_registry.py`, `ohlcv_schema.py`, `dataset_integrity.py`, `historical_fetcher.py`, `src/features/calendar_periods.py`, `configs/data_provenance/`, `docs/governance/clock_evidence/`, `scripts/governance/review_ohlcv_clocks.py`, `tests/test_ohlcv_clock_provenance.py`, `test_calendar_periods.py` |
| 8 | `feat(research): measured broker cost model + adverse stop fill (F-082)` | `src/research/costs.py`, `config.py`, `provenance.py`, `measurement/forward_walk.py`, `measurement/metrics.py`, `configs/research/measurement_contracts/metals_mt5.v1.json`, `src/core/ultron_risk_gate.py`, `tests/test_component_cost_model.py`, `test_cost_model_parity.py`, `test_forward_walk_adverse_fill.py`, `test_measurement_profile_calibration.py`, `test_measurement_contract.py`, manifest `CH-cost-model-broker-truth.*` |
| 9 | `feat(research): Visual CRT trade object + MC-VCRT V2 remeasure (F-081, F-083, F-084)` | `src/research/visual_crt/`, `configs/research/measurement_contracts/instances/`, `scripts/research/vcrt_remeasure_v2.py`, `visual_state_*.py`, `tests/research/test_vcrt_v2_contract.py`, `test_visual_crt_trade_object.py`, `tests/test_visual_state_harness.py`, `docs/research/visual-crt-*`, `visual_crt_trade_object.md`, `reports/xauusd_visual_*`, manifests `CH-vcrt-remeasure-v2.*`, `CH-visual-crt-*` |
| 10 | `feat(tools): TradingView forensic capture + H4 grid reconciliation (F-080)` | `tools/tv_forensic/` **excluding `shots/`**, `scripts/research/tv_engine_odds.py`, `tests/test_tv_forensic_smoke.py`, `reports/monthly_tv_vs_*`, `reports/xauusd_month_tv_engine_odds.md`, manifests `CH-monthly-tv-coverage-h4-recon.*`, `CH-xauusd-tv-odds.impact.json` |
| 11 | `feat(live): live rail scaffolding — feeder, orchestrator, order manager (F-072/F-073)` | `src/inout/live_rail/`, `src/runtime/live_rail_feeder.py`, `live_rail_orchestrator.py`, `live_engine_hook.py`, `src/live/order_manager.py`, `src/core/ultron_live_adapter.py`, `src/agent/modes/pipeline_mode.py`, `src/engines/live_engine.py`, `configs/experimental/spec/live_rail_tickdb_paper.json`, `tests/test_live_rail_*`, `tests/fixtures/ticks/`, `docs/implementation_plan/live-rail-repair-path.md`, manifests `CH-live-rail-pr*` |
| 12 | `docs(governance): CRT object-relations closure CT-009` | `docs/governance/crt_object_relations.yaml`, `crt_object_relations_closure.md`, `crt_closure_report.md`, `crt_executable_state_graph.json`, `tests/test_crt_object_relations.py`, `tests/test_crt_*` (closure/adversarial/baseline/resolver), manifests `CH-crt-object-relations*` |
| 13 | `feat(oss_lab): RI-SOS compatibility runner + QA milestone verdict` | `oss_lab/` (all, tracked + untracked), `tests/test_oss_lab.py` |
| 14 | `chore(registry): feature-math lint, script registry, generated architecture artifacts` | `scripts/analysis/feature_math_lint.py`, `feature_dag_layers.py`, `scripts/governance/seed_script_registry.py`, `scripts/maintenance/check_governance_invariants.py`, `scripts/analysis/CRT_TRACE_WORKFLOW.md`, `crt_episode_number_trace.py`, `run_crt_trace_workflow.py`, `session_filter_funnel_probe.py`, `xauusd_excel_feature_state_trace.py`, `scripts/research/{p_struct_01_displacement_evidence,smc_feature_month_extract,smc_visual_verification,crt_range_rebuild_probe}.py`, `docs/governance/script_registry_*`, `docs/reference/script-matrix.md`, `cli-matrix.md`, `docs/architecture/*.generated.md`, `graph.dot`, `docs/research-readiness/feature-math-lint-report.*`, `src/control_plane/registry.py`, remaining `src/**` + `tests/**` singletons (`bitnet_registry.py`, `sl_tp_comparator.py`, `timing_reconstructor.py`, `resample.py`, `weekly_range.py`, `clean_labels/builder.py`, `model_runners/schema_resolver.py`, `logging_config.py`, `crt_state_resolver.py`, `tests/conftest.py`, …) |
| 15 | `docs: findings F-074…F-084, closure index, topics, memory, session log` | `CLAUDE.md`, `AGENTS.md`, `active_models.yaml`, `assistant_project.md`, `docs/current-findings.md`, `docs/governance/closure_authority_index.json`, `change_contracts.json`, `research_family_registry.json`, `model_paths_literal_debt.json`, `feature_dag_layers*.json/.md`, `ANALYSIS_COVERAGE_AUDIT.md`, `docs/reference/{agent-reference,config-reference,schemas}.md`, `docs/topics/`, `docs/memory/`, `docs/book/A1-testing.md`, `docs/analysis/readme.md`, `docs/analysis/session-log-archive/`, `docs/implementation_plan/` (minus the 2 Grok docs), `docs/research/p_struct_01_*`, `structure-dimension-inventory-displacement.md`, `reports/p_struct_01_*`, `reports/semantic_and_screenshot_layer_review.md`, `tests/test_p_struct_01_*`, `test_fm058_boundary_is_not_sp001.py`, `mt5_analytics/evaluate_bar_features_outcome.py`, `multi_llm/research_lane/prompts/`, `terminals/`, `ui_kits/control_plane/`, `configs/formulas/market_ontology.yaml` |
| 16 | `gov(runtime): ACTIVE_VERSION v2_multi_2026_04 → v2_htfcrt_2026_08` | `configs/production/ACTIVE_VERSION`, `configs/production/v2_multi_2026_04.json`, `configs/promotion_log.jsonl` |

### Why commit 16 is last and alone

`ACTIVE_VERSION` is §4.0 **Tier 0** — the only runtime truth — and §6.2 requires explicit user
approval for edits to it. It has already flipped on disk to `v2_htfcrt_2026_08`, backed by a
matching `PROMOTED` line in `promotion_log.jsonl` (2026-08-15, hash
`7de09f62…`), so this is a governed promotion rather than a stray edit. It nonetheless
**supersedes F-016** ("active config is `v2_multi_2026_04`") on this branch. Isolated so it can be
dropped or deferred with `git branch <name> <commit-15-sha>` without disturbing commits 1–15.

---

## Verification

Run after the branch ref exists — all read-only with respect to the working tree.

1. **Working tree provably untouched** (the load-bearing check):
   ```bash
   git status --porcelain | md5sum
   ```
   Capture before and after; the digests must match. `git rev-parse HEAD` must still be `84fff51`.

2. **Grok surface provably absent from the branch:**
   ```bash
   git diff --name-only 84fff51 snapshot/tree-restore-2026-08-19 | grep -Ei '(^|/)\.?grok|GROK\.md|tests/Grok/|_test_intent|test_functionality_excel'
   ```
   Must return nothing.

3. **Import-resolvability from a clean checkout** (the F-071 gate that caught the last divergence):
   ```bash
   git worktree add --detach ../Tradelatest-commitplan-verify snapshot/tree-restore-2026-08-19
   ```
   Then from that worktree, compile-check every committed module and confirm 0 unresolvable
   imports. Remove the worktree afterward.

4. **Governance floor** (replaces the bypassed `pre-commit` hook):
   ```bash
   python scripts/maintenance/check_governance_invariants.py
   ```
   Expect the 9 pre-existing GREEN_FLOOR failures recorded under F-071 and no new ones.

5. **No bulk blobs leaked in:**
   ```bash
   git diff --name-only 84fff51 snapshot/tree-restore-2026-08-19 | grep -E 'oss_lab/codebase-memory|tv_forensic/shots|xauusd_backtest_run|\.zip$|~\$'
   ```
   Must return nothing.

6. **Residual dirt is only the intended exclusions** — after the run, `git status --porcelain`
   should show exactly the Grok set, the workbook set, and the newly-gitignored bulk paths.

## Rollback

Single command, no history rewrite, working tree unaffected:

```bash
git branch -D snapshot/tree-restore-2026-08-19
```

Orphaned objects are reclaimed by `git gc` on its own schedule.


================================================================================
SOURCE_FILE: docs/implementation_plan/label-back-to-spine-research-descriptio-serene-conway.md
SOURCE_BYTES: 8045
PART: 5/10 FILE 14/16
================================================================================

# Fix F-038 — RR Fusion Gaussian-Duplicate Defect

## Context

The spine's fusion stack nominally runs 4 independent engines (CRT/Gaussian/ZoneGate/RR), but
F-038 (confirmed, CLAUDE.md repository-truths index) established that the RR slot has been
silently degrading to a **Gaussian duplicate**: the `RRFusionLayer`'s confidence gate almost
always fails, so it discards its own model and returns the Gaussian score verbatim. This means
fusion has effectively run with ≤2.5 independent signals since the layer was shipped, with
Gaussian double-weighted (once directly, once via the RR bypass) — silently biasing every fused
decision toward whatever Gaussian says, undetected until this audit.

Programs 1–2 of the spine edge-discovery effort (F-019…F-028) already concluded the upstream
entry signal carries ~0 standalone edge — so this is **not** a new edge-discovery program. It's
a fusion-integrity defect fix: restore an honest, correctly-weighted fusion before any further
spine work builds on top of a quietly-doubled Gaussian signal. Per CLAUDE.md §6.5 Authority
Ladder, RR fusion never demonstrated ΔG001 improvement — it has no claim to production authority
as-is, so removing it (Option A) is strictly evidence-aligned, not a downgrade.

**Root cause (confirmed via code read):**
- `engine_runner.py:698-709` (legacy path, active by default) calls `RRFusionLayer.score_dict()`,
  which only populates 3 of 38 canonical features (`rr_fusion.py:176-179`) → Mahalanobis
  confidence collapses to ~1e-88.
- The shipped mitigation (`engine_runner.rr_fusion.full_feature_vector`, default `false`) routes
  to `score()` with the full feature vector instead — but confidence is *still* ~5e-5, five
  orders below the `confidence_bypass_threshold=0.3` gate (`rr_pattern_miner.py:299-350`,
  `configs/production/v2_multi_2026_04.json` → `rr_model.confidence_bypass_threshold` /
  `mahal_clip`).
- Whenever confidence < threshold, `_passthrough()` (`rr_fusion.py:35-42`) fires: discards the
  model, returns `final_score = gaussian_score`, `confidence = 0.0`. This is the "duplicate."
- The underlying model (`models/rr_model.json`, trained 2026-05-24, filename hint
  `rr_model_202605_bnb_v2.json` suggests BNB-specific, LedoitWolf covariance with very tight
  precision ~2363) is out-of-distribution for live multi-instrument data even when fed correctly
  — feeding more features does not fix a miscalibrated/overfit covariance.

## Plan

### Phase 1 — Disable rr_fusion (ship now, low ceremony, zero blast radius)

A pure BEHAVIORAL config flip, already supported by existing short-circuit logic — **no engine
code changes required**.

1. **`configs/production/v2_multi_2026_04.json`** (the file `ACTIVE_VERSION` points to — verified
   via `configs/production/ACTIVE_VERSION` = `v2_multi_2026_04`): flip `rr_fusion.enabled` from
   `true` → `false`. Leave `model_path`/`threshold`/`full_feature_vector` untouched — minimizes
   diff and preserves the forensic trail of what Fix A attempted. This is hash-neutral if
   `rr_fusion` is a top-level section (not inside `params`) — confirm with
   `python scripts/maintenance/_compute_hash.py` after the edit; rehash only if required.
   - Only the active file needs this change. `v1_multi_2026_03*.json`, the `_archived_*` files,
     and `v3_multi_2026_06.json`/`v4_multi_2026_06.json` are out of scope: archived configs are
     preserved history (§6.2 rule 4 — never edit), and v3/v4 belong to a different code line
     (F-016: v4 loads only on the post-TP3 line; not active on `patch`).
   - Do **not** touch the `"... - deepdeektry.json"` variant — historical/non-canonical per
     existing truth-audit findings.

2. **Verify the disable path is already idempotent** (read-only check, no code change expected):
   confirm in `engine_runner.py` that `RRFusionLayer(enabled=...)` is constructed from this exact
   config key, and that when `enabled=False` → `is_loaded` stays `False` → the guard at
   `engine_runner.py:682` (`if self.rr_fusion and self.rr_fusion.is_loaded:`) never enters either
   branch, so `rr_result` (the genuine base `RREngine.compute()` output, line 678) flows through
   unmodified into fusion.

3. **Add a regression test** (extend `tests/test_engine_runner_rr_fusion.py`):
   - Build the runner with `rr_fusion.enabled=false`.
   - Assert `rr_result["score"]` equals the base `RREngine` output and that no `"rr_fusion"` key
     is injected (per `engine_runner.py:713-717`, only present inside the loaded-fusion branch).
   - Assert `self.rr_fusion is None` or `self.rr_fusion.is_loaded is False` per however the
     runner short-circuits construction.

4. **Parity/determinism proof** (follow the existing pattern in
   `tests/runtime/test_replay_determinism.py` / `tests/test_bitnet_parity.py`): run a fixed
   replay set through `EngineRunner` pre- and post-config-change and assert every output field
   *except* the RR slot (and anything causally downstream of the RR score, e.g. fused decision
   fields) is byte-identical. This is the parity-proof CLAUDE.md §6.5 requires for any migration.

5. **Findings update (same turn, per §6.2 Findings Mandate):** flip F-038's status in
   `docs/current-findings.md` — `Reversal:` line noting the fix shipped (disable, not retrain),
   and the table-row `Conf` stays `Likely`→ re-evaluate to `Certain` once the regression test +
   parity proof pass. Add a `📝 SESSION LOG ENTRY` per CLAUDE.md §7.4.

### Phase 2 — Optional follow-on: retrain/recalibrate (separate, gated, not blocking)

Only pursue if there's appetite to restore RR as a genuine 4th signal later. This is gated by
`promotion_manager` — no retrained model reaches production without an `APPROVE`d
`ValidationReport`.

1. New read-only script `scripts/validation/validate_rr_model_calibration.py`:
   - Loads the current model + a current multi-instrument eval dataset (via
     `config_layer/rr/rr_dataset_builder.load_dataset()`).
   - **Coverage check:** fraction of eval rows whose Mahalanobis `d_sq` (same formula,
     `rr_pattern_miner.py:322-337`) lands below `mahal_clip` pre-clip — quantifies how little of
     real data the trained covariance recognizes.
   - **Confidence distribution check:** histogram + assert ≥X% of in-distribution rows exceed
     `confidence_bypass_threshold` (X itself config-declared, not a magic number).
   - **Per-instrument breakdown:** same checks grouped by symbol, to confirm/deny the
     BNB-specific-overfit hypothesis.
   - **ΔG001 comparison:** run old vs. candidate model through the existing Goal Layer
     (`goal_report`) harness — no promotion without demonstrated ΔG001 improvement
     (Authority Ladder).
2. **Independent small fix** (ship regardless of whether retraining happens):
   `rr_pattern_miner.py:309-310` currently silently truncates an oversized feature vector
   (`features[:n]`). Replace with a hard `feature_schema`/version check that fails closed on
   mismatch instead of silently truncating — this is a latent correctness bug independent of the
   retraining question.
3. Any new `models/rr_model_{version}.json` goes through `ConfigValidator` →
   `PromotionManager.promote_*` before being copied to canonical `models/rr_model.json` — never
   hand-copied.

## Verification

- `pytest tests/test_engine_runner_rr_fusion.py -v` — new disable-path test green, existing
  fallback tests still green.
- Run the determinism/parity harness (`tests/runtime/test_replay_determinism.py` or equivalent)
  pre/post config change on a fixed replay set; diff must be empty outside the RR-derived fields.
- `python scripts/maintenance/_compute_hash.py` — confirm hash-neutral or correctly rehashed.
- Full `pytest` per `docs/reference/testing.md` pre-promotion regression command — confirm no
  unrelated breakage.
- Manually inspect one live-equivalent fusion run's log output to confirm `rr_fusion` no longer
  appears / RR score now differs from Gaussian score (proving real `RREngine` is back in play).


================================================================================
SOURCE_FILE: docs/implementation_plan/label-repo-maintenance-description-pay-validated-summit.md
SOURCE_BYTES: 6758
PART: 5/10 FILE 15/16
================================================================================

# Repo Maintenance — Session Log Rotation, Findings Consolidation, Memory Consolidation

## Context

Three advisory hygiene signals have accumulated past their thresholds and need paying down before
any new research track starts: the SESSION LOG (`assistant_project.md`, 31 entries vs the 25-keep
norm), `docs/current-findings.md` (39 findings, 2 of them already-SUPERSEDED but mis-filed in the
"non-terminal" section, leaving 37 genuinely-tracked findings vs a ~30 target), and the memory
index (51 files vs a 45 target). None of this is a code change — it's pure doc/memory bookkeeping
governed by CLAUDE.md §6 (session log), §6.2 (truth maintenance, "never delete, mark
SUPERSEDED/RETIRED, append-discipline"), and the repo's own `consolidate-memory` skill. The goal is
to clear these signals without inventing new conclusions or silently overclaiming closure — every
move is either purely mechanical (rotation, re-filing already-decided statuses) or a citation-based
supersession of findings that are *already* documented as closed/killed in memory (Program 1,
Program 5/6/6b).

## 1. Session log rotation (mechanical, scripted)

Run the existing tool, nothing new to build:

```
python scripts/maintenance/rotate_session_log.py --keep 25 --dry-run   # verify split first
python scripts/maintenance/rotate_session_log.py --keep 25             # apply
```

This spills the oldest 6 entries from [assistant_project.md](assistant_project.md) into
`docs/analysis/session-log-archive/session-log-<oldest-date>_to_<newest-spilled-date>.md` (the
existing archive folder — [scripts/maintenance/rotate_session_log.py](scripts/maintenance/rotate_session_log.py) already names files by
date range, so no new naming scheme is needed; this **is** the "single folder + timestamp
differentiation" pattern the task asks for, already in place). Conservation guard in the script
aborts before writing if entry count doesn't match markers — trust it.

## 2. Findings consolidation in `docs/current-findings.md`

**Step A — re-file already-decided statuses (no new judgment).** F-003 and F-007 are already
marked `Status: SUPERSEDED` but sit in the `## Findings (non-terminal)` section instead of
`## Terminal (SUPERSEDED / RETIRED) — kept for replay` (currently a placeholder, "_(none yet...)_").
Cut their blocks and paste them under Terminal, replacing the placeholder line. No status or
content changes — purely fixing a stale section placement.

**Step B — consolidate the two closed-program clusters into superseding findings**, per
§6.2 rule 4 (preserve history, mark SUPERSEDED, never delete) and rule 5 (minimize doc count):

- **New finding `F-040 · Program 1 (next-bar directional ontology) closed after four
  falsifications`** — consolidates F-019 (qualify-majors null), F-020 (conditional entropy null),
  F-021 (selection-is-session-only), F-025 (exit/cost grid null), F-026 (structural asymmetry
  null/underpowered). Cite [docs/analysis/program-1-closure-2026-06-13.md](docs/analysis/program-1-closure-2026-06-13.md) (already exists per
  memory `project_program1_closure.md`) as the evidence anchor. Status: `VALIDATED`.
- Flip F-019, F-020, F-021, F-025, F-026 to `Status: SUPERSEDED` with a one-line
  `Superseded-by: F-040` note, and move all five blocks to the Terminal section (content
  untouched otherwise — this is re-filing + a status flip, not a rewrite of their evidence).
- **New finding `F-041 · Cross-sectional / carry program (5, 6, 6b) closed — no monetizable
  signal on crypto-major dispersion or carry`** — consolidates F-032 (panel dispersion null),
  F-033 (carry/basis signal null), F-034 (carry harvest null). Cite the three existing memory
  files (`project_cross_sectional_program5.md`, `project_carry_basis_program6.md`,
  `project_carry_harvest_program6b.md`) as evidence anchors. Status: `VALIDATED`.
- Flip F-032, F-033, F-034 to `Status: SUPERSEDED` (`Superseded-by: F-041`), move to Terminal.

**Net effect:** non-terminal findings 39 → 39 (no deletions) but *tracked-as-open* count
37 → 31 (37 minus the 6 superseded, plus the 2 new consolidated rows F-040/F-041 = 31). This is the
"Recommended" option the user selected — close to the 30 target without forcing artificial RETIRED
verdicts on findings whose null results are durable knowledge, not failures.

**Step C — sync the Repository Truths Index table** in [CLAUDE.md](CLAUDE.md) §6.2: add rows for
F-040/F-041, and either remove or mark the now-superseded F-019/020/021/025/026/032/033/034 rows
(the table is enforced 1:1 against non-terminal findings by `tests/test_current_findings.py` — run
it after the edit to confirm sync, per the Findings Mandate).

**Step D — run the test floor:** `pytest tests/test_current_findings.py -q` must pass before
calling this step done (it enforces the index↔doc 1:1 invariant).

## 3. Memory consolidation (51 → 45 files)

Invoke the existing skill rather than hand-rolling logic:

```
/consolidate-memory   (anthropic-skills:consolidate-memory)
```

This is the purpose-built tool for "merge duplicates, fix stale facts, prune the index" — point it
at `C:\Users\Hi\.claude\projects\D--Tradelatest\memory\`. Likely merge candidates based on the
current `MEMORY.md` index: the Program-1 family (`project_program1_closure.md`,
`project_qualify_majors_findings.md`, `project_phase_b_conditional_entropy.md`,
`project_phase_s_selection_effect.md`, `project_phase_d_exit_grid.md`,
`project_phase_e_structural_asymmetry.md` — 6 files describing one closed program) and the
cross-sectional/carry family (`project_cross_sectional_program5.md`,
`project_carry_basis_program6.md`, `project_carry_harvest_program6b.md` — 3 files, same program
that's now also being consolidated in `current-findings.md` Step B). Merging each family into one
memory file (mirroring the F-040/F-041 consolidation above so doc and memory tell the same
compressed story) would bring 51 → ~43, past the 45 target. Let the skill decide exact grouping —
this list is a steer for it, not a hard prescription.

## Verification

- `git diff --stat` shows only `assistant_project.md`, `docs/current-findings.md`, `CLAUDE.md`,
  new file under `docs/analysis/session-log-archive/`, and memory files under
  `C:\Users\Hi\.claude\projects\D--Tradelatest\memory\` — no `src/` changes.
- `pytest tests/test_current_findings.py tests/test_session_log.py -q` green.
- `grep -c "^### F-" docs/current-findings.md` and a manual scan of `## Findings (non-terminal)`
  confirm 31 tracked + the rest under Terminal.
- Session log entry count in `assistant_project.md` == 25 + this response's own new entry (§6
  mandate — this maintenance turn itself still ends with a SESSION LOG block, appended after
  rotation).


================================================================================
SOURCE_FILE: docs/implementation_plan/lets-generate-pyan-dot-streamed-hare.md
SOURCE_BYTES: 5383
PART: 5/10 FILE 16/16
================================================================================

# Plan: Generate Pyan Dot File & Understand Codebase Wiring

## Context

The Tradelatest codebase uses a three-tier dependency visualization system:
1. **graph.dot** (module-level imports via AST): ~515 edges, structural
2. **pyan_call_flow.dot** (function/class calls via pyan3): tens of thousands of edges, runtime
3. **flow_graphs/*.dot** (domain-scoped slices): 7 flows (agent, runtime, governance, research, training, control_plane, telemetry)

Current status:
- All generation scripts exist (`gen_code_map.py`, `gen_pyan.py`, `gen_flow_graphs.py`)
- graph.dot exists and is up-to-date
- pyan_call_flow.dot exists but may be stale (last run unclear)
- flow_graphs/*.dot all exist
- flow_context/*.json manifests all exist (7 flows defined)

## Goals

1. **Regenerate all artifacts** to ensure they reflect the current codebase
2. **Analyze the wiring** to understand:
   - Module-level dependency structure
   - Critical paths and bottlenecks
   - Per-domain flow isolation
3. **Provide interactive exploration tools** to query the graph

## Implementation Plan

### Phase 1: Regenerate Core Artifacts (read-only, inspection only)
- [ ] **gen_code_map.py** → regenerate graph.dot (modules + imports via AST)
- [ ] **gen_pyan.py** → regenerate pyan_call_flow.dot (function/class calls via pyan3)
- [ ] **gen_flow_graphs.py** → regenerate all flow_graphs/*.dot slices

Success criteria:
- All three artifact types regenerated without errors
- Byte-identical check (deterministic generation confirmed)
- graph.dot validates against pyan for consistency

### Phase 2: Analyze Module-Level Structure
- [ ] Load graph.dot and extract statistics:
  - Node count per package
  - Edge count (dependencies between packages)
  - Cyclic dependency detection
  - Depth from entry points (runtime, governance, training, agent)
  - Betweenness centrality (critical intermediate modules)

- [ ] Per-flow analysis (flow_graphs/*.dot):
  - Module count per flow
  - Internal edges (within-flow dependencies)
  - Boundary edges (imports from outside flow)
  - Flow isolation score (low boundary edges = good)

Success criteria:
- Generate a structured report (`codebase_wiring_analysis.json`)
- Identify 3-5 critical paths and junction points
- Flag any circular dependencies

### Phase 3: Analyze Call-Graph Structure (pyan_call_flow.dot)
- [ ] Sample the pyan call graph (too large to fully analyze):
  - Total node/edge count
  - Top 10 most-called functions
  - Longest call chains (depth)
  - Hot spots (high in-degree)

Success criteria:
- Generate a summary (`call_graph_hotspots.txt`)
- Identify which modules are "hub" functions

### Phase 4: Interactive Exploration Tools
- [ ] **Graph query script** (read-only):
  - `--module <name>` → show all dependencies of a module
  - `--flow <name>` → show the flow's induced subgraph
  - `--path <from> <to>` → find shortest import path
  - `--downstream <module>` → modules that depend on this

- [ ] **Visualization preparation**:
  - Convert graph.dot to a Graphviz PNG/SVG for visual inspection
  - Generate a per-flow visual (7 small PNGs for each flow)

### Phase 5: Document & Summarize
- [ ] Create `docs/architecture/codebase-wiring-guide.md`:
  - Module hierarchy diagram (text-based ASCII tree)
  - Per-package role summary (from graph.dot clusters)
  - Critical dependencies (high fan-in/fan-out modules)
  - Per-flow topology (module count, boundary structure)
  - How to navigate: using graph.dot, query tools, flow_graphs

- [ ] Update `docs/reference/architecture.md` §3 with wiring section reference

## Critical Files to Touch

### Generation Scripts (read-only, just run them)
- `scripts/analysis/gen_code_map.py` — AST module parser
- `scripts/analysis/gen_pyan.py` — pyan3 call-graph runner
- `scripts/analysis/gen_flow_graphs.py` — flow-scoped slicer

### Artifacts (regenerated, never hand-edited)
- `graph.dot` — module import graph (Graphviz format)
- `pyan_call_flow.dot` — function call graph (Graphviz format)
- `flow_graphs/*.dot` — 7 domain slices

### Flow Manifests (hand-authored, stable)
- `flow_context/*.json` — 7 flow definitions (agent, runtime, governance, research, training, control_plane, telemetry)

### New Analysis Tools (to create)
- `scripts/analysis/codebase_wiring_analysis.py` — Phase 2 analysis
- `scripts/analysis/graph_query.py` — Phase 4 interactive tool

### Documentation (to update)
- `docs/architecture/codebase-wiring-guide.md` — new, comprehensive guide
- `docs/reference/architecture.md` — link to wiring guide

## Verification

✅ All generation scripts can run without errors
✅ Artifacts are deterministic (byte-identical on re-run)
✅ graph.dot nodes match pyan modules (no drift)
✅ flow_graphs/*.dot all validate against graph.dot
✅ No circular dependencies detected
✅ Query tools work against graph.dot and pyan_call_flow.dot

## Open Questions for User

1. **Visualization preference**: Would you like PNG/SVG renders of the graphs, or Graphviz interactive HTML, or both?
2. **Query tool interface**: Preference for CLI script (`python graph_query.py --module x`) or a simple REPL?
3. **Documentation depth**: Comprehensive (~50 pages) or executive summary (~5 pages)?
4. **Focus areas**: Any specific packages/flows you'd like deep-dive analysis on?

## Next Step

→ User approval, then execute Phase 1 (regenerate artifacts).

# Opportunity Episode Platform — Audit + Implementation Plan

## Context

`docs/architecture/opportunity-episode-platform-design.md` (rev 2) and its authoritative sibling
`docs/architecture/opportunity-episode-research-substrate.md` propose a research substrate that
preserves the **post-entry observation timeline** for every opportunity, so that labels, events,
queries and tensors become *derived* artifacts instead of being re-simulated by ~10 independent
forward-walkers.

Today the path exists only inside walk loops and is thrown away on return. `TradePathStats`,
`Outcome`, and the opportunities stream all keep scalars. `src/research/ic002_entry_evolution/`
is the only module that persists a sequence (15 features × N bars, npz).

**Nothing is built.** `src/research/episodes/` does not exist. This plan takes the design from
zero to the full P0–P8 program, DETECTION_STREAM-first, on a stdlib storage substrate.

Authority: **NONE** (§6.5). Research infrastructure. `PRODUCTION_BEHAVIOR_CHANGED = NO` throughout.

---

## Part 1 — Audit of the design documents

### Verified-correct claims

| Claim | Verification |
|---|---|
| `forward_walk` is the single governing exit kernel | `src/research/measurement/forward_walk.py:27` — already supports all three v1 policies: `intrabar_fixed`, `trailing`, `close_only` |
| Batch feature pipeline makes per-step features free | `FeaturePipeline.run()` enriches the full frame; IC-002 slices it by `_src_idx` |
| `clean_labels/` is the freeze-pattern precedent | `protocol.py` (frozen consts + `freeze_block()` + `compute_protocol_hash()`) + `builder.py` + sidecar artifacts |
| IC-002 is the tensor precedent, not the canonical store | `ic002_entry_evolution/schema.py:43` `TrajectoryBatch` |
| Downstream consumers already wrap the same kernel | `exit_grid.py:53`, `forensics.py:55-59`, `clean_labels/builder.py:199` all call `forward_walk` with a synthesized `Signal` |
| Production spine needs no change | `TradeJournal`/`TradeRecord`/`TradePathStats` in `backtest_v2.py:237,281` already carry entry, exit, and MFE/MAE — a SpineProjector reads them offline |

### Defects found (platform-design.md; substrate.md is right in each case)

1. **Provenance contradicts its own Principle 3.** `EpisodeProvenance.exit_policy_hash`
   (platform-design §5.1) bakes exit policy into the canonical episode. Substrate §12 is explicit:
   *"exit_policy_hash does NOT live on Episode — it lives on LabelSet."* **Substrate wins; drop the field.**

2. **`EpisodeDerived.stop` / `.tp` are policy state, not derived state.** A trailing stop is a
   function of the exit policy, so storing it makes canonical steps policy-coupled — the exact
   anti-pattern substrate §10 names. **Drop `stop`/`tp` from canonical v1**; keep only quantities
   that depend on `entry_snapshot` + observation prefix.

3. **Feature dim is 39, not 38.** `feature_schema.py:114` `CANONICAL_FEATURE_DIM = 39` (hard-asserted
   at import). platform-design §4/§15 says 38-dim. Substrate §7 already flags this. *Separate
   pre-existing conflict, out of scope:* `clean_labels/protocol.py:35` `FEATURE_DIM = 38` is stale
   metadata inside a frozen hash while `builder.py:101` validates against 39 — reported, not touched.

4. **Phase ordering is inverted.** platform-design makes the ledger-based Episode Projector Phase 2
   (its only "High"), before any builder exists. Substrate correctly builds the timeline first (P1)
   and defers SpineProjector to P6 because ledger completeness is the risk. **Follow substrate.**

5. **The "five duplicated simulators" list (§1) is stale.** Substrate §5 enumerates ten and is the
   accurate map. Also, RR labels do not re-simulate forward — per F-045 they derive from the trade
   `outcome`/`rr_achieved` field (`rr_dataset_builder.py:125-206`), which is *why* they are
   F-022-contaminated. Use substrate §5 as the migration inventory.

6. **Sizing assumes the wrong population.** platform-design §13 budgets 10K episodes × 30 steps
   ≈ 25 MB. The chosen DETECTION_STREAM population is ~139,942 detections (F-022) × T=40 ≈ **5.6M
   steps**. Substrate §7 flags "multi-GB raw if naively stored." Observation-minimal Tier 1 +
   join-by-index for features is mandatory, not a default.

### Blockers neither document addresses

**B1 — Parquet/DuckDB are not installed.** `pyproject.toml` lists them only under the
`mt5_analytics` extra; `import pyarrow` and `import duckdb` both fail in this environment. The
entire three-tier storage design assumes them. *Resolved by decision:* stdlib gzipped JSONL + npz
for v1, behind a format-agnostic store API.

**B2 — `forward_walk` cannot express multi-level exits.** `Signal` is `frozen` and expresses
geometry as ATR multiples with a **single** TP. The spine has TP1/TP2 + `partial_tp_fraction`
(F-056). So substrate §10's proposed `partial_tp_be` policy is **not implementable without a
second exit kernel** — which substrate §18 itself rates a *Critical* risk ("second exit kernel
drift"). **Resolution: v1 policy set is exactly `{intrabar_fixed, trailing, close_only}` — the
three modes the audited kernel already has. Partial-TP is declared a non-goal for this program**
and requires its own pre-registration.

**B3 — `episode_id` determinism is unspecified.** Reuse the `clean_labels/builder.py:82`
`_unit_id` pattern: SHA over `instrument|timestamp|direction|entry|sl`.

**B4 — No change-class covers a new research package.** Verified precedent: `CH-tn-env-gate-l`
built `src/research/clean_labels/` under `["MODEL_TRAINING_CHANGE","DOCUMENTATION_ONLY"]`. Use the
same classification; no new class needed, no `UNKNOWN` to block on.

### Open decisions (substrate §23) — resolved by this plan

| # | Decision | Resolution |
|---|---|---|
| 1 | Root name | `OpportunityEpisode` |
| 2 | `t` convention | **`t=0` = entry bar observation; PolicyEvaluator walks `t≥1` only** — matches `forward_walk`'s `index > entry_index` assertion |
| 3 | ATR placement | Entry ATR in `entry_snapshot` pinned by FM-041 formula hash; per-step ATR is opt-in Tier-2, **not** Observation |
| 4 | v1 Observation | `t, bar_index, timestamp, o/h/l/c, volume` — nothing else |
| 5 | v1 policy set | `intrabar_fixed` (governing) + `trailing` + `close_only` (see B2) |
| 6 | Query v1 | Library API first; no string DSL |
| 7 | First population | `DETECTION_STREAM` (user decision) |
| 8 | Artifact root | `results/research/episodes/…` (gitignored) |

---

## Part 2 — Implementation Plan (P0–P8)

New package: **`src/research/episodes/`**. CLIs under `scripts/research/`. Tests under
`tests/research/episodes/`. Artifacts under `results/research/` (gitignored).

### P0 — Contract freeze *(no code paths; design-heavy)*

- `src/research/episodes/protocol.py` — modelled directly on `src/research/clean_labels/protocol.py`:
  `EPISODE_PROTOCOL_ID = "OE_L1"`, observation schema version, `t`-convention constant, population
  enum, v1 policy set, `pit_status`, `freeze_block()`, `compute_protocol_hash()`.
- `docs/research-readiness/opportunity-episode-prereg.md` — pre-registration; records the eight
  §23 resolutions and the B2 partial-TP non-goal.
- `docs/governance/build_manifests/CH-opportunity-episodes.impact.json` — classes
  `["MODEL_TRAINING_CHANGE","DOCUMENTATION_ONLY"]`, `unknowns: []`, copying `CH-tn-env-gate-l.impact.json`.
- **Doc-drift fixes the same turn (§6.2/§6.3):** correct 38→39 in platform-design §4/§15; strike
  `exit_policy_hash` from its §5.1 dataclass; strike `stop`/`tp` from `EpisodeDerived`; annotate §1's
  walker list as superseded by substrate §5. Add a `TruthConflict` note for the `protocol.py:35`
  FEATURE_DIM=38-vs-39 discrepancy (report only — the hash is frozen).
- **Gate:** `python scripts/governance/construction_protocol.py validate-impact <manifest>`

### P1 — Schema + EpisodeBuilder + Detection projector

- `episodes/schema.py` — `Observation`, `Derived`, `Annotations`, `EpisodeStep`, `EntrySnapshot`,
  `EpisodeProvenance` (**no** `exit_policy_hash`), `OpportunityEpisode`, `Population` enum.
  `episode_id` per B3.
- `episodes/builder.py` — candles + entry geometry → observation timeline. Owns *no* exit policy.
  Enforces the no-lookahead contract by construction (slice `[entry : entry+1+max_forward]`,
  `t=0` = entry bar).
- `episodes/projectors/detection.py` — `opportunities.jsonl` → episodes. Reuses
  `clean_labels/builder.py`'s `_geometry()` / `_norm_ts()` / `ts_to_idx` conventions verbatim so the
  two builders select the identical unit population. **F-022 discipline: the stream's
  `outcome`/`rr`/`mfe`/`mae` are copied to `metadata.diagnostics` and never to canonical fields.**
- `scripts/research/build_episodes.py` — thin CLI (`--instrument --population --max-units`).
- **Tests:** determinism (same inputs → same content hash), lookahead rejection, `t=0` identity,
  `episode_id` stability.

### P2 — PolicyEvaluator + LabelSet *(the load-bearing phase)*

- `episodes/policy.py` — `PolicyEvaluator.evaluate(episode, policy_id) -> LabelSet`. **Wraps
  `forward_walk` only.** Synthesizes the frozen `Signal` exactly as `clean_labels/builder.py:188-197`
  does (`atr=risk_distance`, `sl_atr_mult=1.0`, `tp_atr_mult=|tp-entry|/risk`) and feeds it
  `steps[1:]`. `LabelSet` carries `exit_policy_id`, `exit_policy_hash`, `cost_model_hash`,
  `evaluator_hash`.
- **Parity floor (the acceptance criterion for the whole program):** for the same detection units,
  `PolicyEvaluator(episode, "intrabar_fixed")` must produce a `LabelSet` **field-identical** to the
  `Outcome` that `clean_labels/builder.py` produces today. Any divergence is a build defect.
- Multi-policy proof: `close_only` and `trailing` on the same episodes with no rebuild.

### P3 — EventEngine

- `episodes/events.py` — one pure detector per kind, dispatched by rulepack id. Seed rulepack v1:
  `ENTRY`, `REACHED_R` (0.5/1/1.5/2/3R), `NEW_MFE`, `NEW_MAE`, `BE_ELIGIBLE`, `SL_THREAT`, `TP_TOUCH`.
- Cross-check: `REACHED_R@1R` must agree with `horizon_excursion()["bars_to_first_1r"]`.
- Regenerability test: a v2 rulepack produces a new EventSet with the episode file byte-unchanged.

### P4 — Query Engine v1

- `episodes/query.py` — library API (no string DSL): `filter_population`, `filter_time_range`,
  `where_derived(fn)`, `join_labels(policy_id)`, `join_events(rulepack_id)`.
- Reference query, per substrate §14: *reached 1R within 6 bars without exceeding −0.4R adverse.*

### P5 — Store + flat projection + tensors

- `episodes/store.py` — **format-agnostic writer/reader interface**; v1 backend = gzipped JSONL
  (one episode per line) + `.npz` for step arrays, partitioned `…/{population}/{instrument}/`.
  A Parquet backend is a drop-in later with no schema change.
- `episodes/flat.py` — `(episode_id, t, …)` flat table for pandas/SQL.
- `episodes/tensors.py` — `[N,T,D]` materializer generalizing IC-002's
  `path_relative_row`/`flatten_Z` (`ic002_entry_evolution/schema.py:62,73`); pad/mask policy explicit.
- **Sizing gate:** measure real bytes on one instrument before building the full DETECTION_STREAM
  corpus; abort and re-scope if observation-minimal Tier 1 exceeds budget.

### P6 — SpineProjector

- `episodes/projectors/spine.py` — `TradeRecord`/journal + candles → `population=SPINE_TRADE`.
  **Offline only; nothing writes episodes from `TradeJournal`.**
- **Parity floor:** episode-derived MFE/MAE must equal `TradePathStats.mfe_price`/`mae_price`
  (`backtest_v2.py:237`) for the same trades — the independent oracle substrate §18 demands.
- Ledger-completeness probe first; report gaps rather than inventing fields.

### P7 — Consumer migration *(dual-read, one at a time)*

Order chosen by parity-provability, each landing only after old ≡ new on real data:
1. `clean_labels/builder.py` → consume `LabelSet` (already the same kernel + same geometry helper)
2. `exit_grid.py` (`:53`) → evaluate SL×TP cells as LabelSets over cached episodes
3. `forensics.py` (`:55-59`) → its `intrabar`/`close_only`/`horizon` triple becomes two LabelSets + derived
4. IC-002 `build_trajectories` → a `tensors.py` view

Legacy `_simulate` in `scripts/research/opportunity_scanner.py:53` is **left byte-untouched**; it is
the historical corpus generator and its trailing convention is already reproducible as the
`trailing` policy.

### P8 — Opt-in sequence training

- `scripts/training/train_from_episodes.py`, reading Tier-3 tensors. Torch is **not installed** —
  gate behind an optional-import guard per `conventions.md`. Research models only; no promotion,
  no fusion, no spine wiring (§6.5).

---

## Files

**New:** `src/research/episodes/{protocol,schema,builder,policy,events,query,store,flat,tensors}.py`,
`src/research/episodes/projectors/{detection,spine,hypothesis}.py`,
`scripts/research/build_episodes.py`, `scripts/training/train_from_episodes.py`,
`tests/research/episodes/*`, `docs/research-readiness/opportunity-episode-prereg.md`,
`docs/governance/build_manifests/CH-opportunity-episodes.{impact,completion}.json`

**Modified (docs, P0):** `docs/architecture/opportunity-episode-platform-design.md`,
`docs/current-findings.md` (+ CLAUDE.md §6.2 truths index if a finding registers),
`assistant_project.md`

**Modified (code, P7 only, dual-read):** `src/research/clean_labels/builder.py`,
`src/research/exit_grid.py`, `src/research/forensics.py`,
`src/research/ic002_entry_evolution/build_trajectories.py`

**Untouched:** entire production spine — `EngineRunner`, fusion, `DecisionEngine`,
`ExecutionPlanner`, `UltronRiskGate`, `crt_engine_v2.py`, `backtest_v2.py`, `TradeJournal`,
`FeaturePipeline`, all `configs/`, `forward_walk.py` (read-only reuse),
`scripts/research/opportunity_scanner.py`

---

## Verification

```bash
python scripts/governance/construction_protocol.py validate-impact docs/governance/build_manifests/CH-opportunity-episodes.impact.json
```

```bash
python -m pytest tests/research/episodes/ tests/research/test_forward_walk.py tests/research/test_clean_labels_tn_env.py tests/research/test_exit_grid.py tests/research/test_forensics.py -q
```

```bash
python scripts/research/build_episodes.py --instrument BNBUSDT --population DETECTION_STREAM --max-units 500
```

Acceptance gates, in order:
1. **P1 determinism** — two builds of the same units produce identical episode content hashes.
2. **P2 parity (blocking)** — `intrabar_fixed` LabelSet ≡ today's `clean_labels` `Outcome` fields,
   unit-for-unit. This is the criterion that proves no second exit kernel was introduced.
3. **P2 multi-policy** — three LabelSets from one episode build, episode files byte-unchanged.
4. **P3 regenerability** — rulepack v2 EventSet written, episode bytes unchanged.
5. **P5 sizing** — measured corpus bytes recorded before the full build.
6. **P6 spine parity (blocking)** — episode MFE/MAE ≡ `TradePathStats` per trade.
7. **P7 dual-read** — each migrated consumer byte-identical to its pre-migration output before switch.
8. **Isolation** — `git diff --stat` shows zero changes outside `src/research/`, `scripts/research/`,
   `scripts/training/`, `tests/`, `docs/`.

```bash
python scripts/governance/construction_protocol.py validate-completion docs/governance/build_manifests/CH-opportunity-episodes.completion.json
```

---

## Risks carried forward

| Risk | Mitigation |
|---|---|
| Second exit kernel drift (**Critical**) | PolicyEvaluator wraps `forward_walk` only; P2 parity floor is blocking; partial-TP is a declared non-goal (B2) |
| Detection-stream size (5.6M steps) | Observation-minimal Tier 1; features joined by bar index; P5 sizing gate before full build |
| F-022 contamination re-entering as truth | Stream fields land in `metadata.diagnostics`; canonical labels come only from PolicyEvaluator |
| PIT-unclean stored features (F-051) | `pit_status` declared in provenance; no promotion authority on this status |
| Ledger incompleteness (P6) | Probe-and-report first; gaps documented, never synthesized |

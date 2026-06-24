# Topic: Replay Memory & the Probability Surface

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: 2026-06-02 · Updated: 2026-06-16 (re-applied the `_assign_cluster` `center`/`feature_weights` repair on `patch`; STORY-1.5: `_build_cluster_stats` zone-id schema dispatch) · Status: living

## In plain language
`ReplayMemoryEngine` is the system's **institutional memory**: it loads historical opportunity
outcomes (`opportunities.jsonl`), buckets each record into a **zone** (a cluster of similar
candle-geometry contexts), and reports cluster-conditioned stats — historical win rate, mean RR,
failure modes, trap frequency, staleness. The clusters come from `discover_zones` (research
K-Means). The long-term ambition is a **Probability Surface**: an advisory "we've seen this
context before, here's how it usually resolves" tie-break. Today it is **monitoring-only** — it
runs in a fire-and-forget `CognitiveBus` worker thread *after* the decision is finalized and
**never gates a trade** (frozen *Schema-Consistency-Before-Fusion* invariant).

## Code covered
- [`replay_memory_engine.py:394`](src/replay/replay_memory_engine.py) — `ReplayMemoryEngine._assign_cluster` — nearest-zone assignment. **2026-06-02 repair:** reads `center` (legacy `centroid` alias) and applies the registry's `feature_weights` so the query vector lands in the *same weighted space* as the producer's centers. The prior unweighted-vs-weighted mismatch (plus the `centroid` key typo) collapsed every record to cluster 0.
- [`replay_memory_engine.py:419`](src/replay/replay_memory_engine.py) — `_build_cluster_stats` — same `center`/`centroid` back-compat read. **2026-06-16 (STORY-1.5):** the per-zone id key is now dispatched by `schema_version` via `_zone_cluster_id` (`zone_v1`→`zone_id` int; `v2_gaussian`→`id` `"zone_N"`-string→trailing int; unknown→`ValueError`, caught by the `_load` fail-open). Fixes the `KeyError: 'zone_id'` that wiped all records when the default `v2_gaussian` `models/zone_registry.json` was loaded. No silent default (§6.5).
- [`replay_memory_engine.py:161`](src/replay/replay_memory_engine.py) — `query` / `get_replay_features` — cluster-conditioned intelligence summary (advisory output).
- [`discover_zones.py:49`](scripts/research/discover_zones.py) — `_inv_std_weights` (shared) + `_vector_from_record` + `discover` — producer; writes `zone_v1` registries with `center` in weighted space + top-level `feature_order` / `feature_weights`. `--normalize` computes inverse-std weights.
- [`feature_region_oos_study.py`](scripts/research/feature_region_oos_study.py) — Part 4A OOS harness; delegates to `discover_zones._inv_std_weights` (single source of truth).
- [`cognitive_bus.py:217`](src/cognitive/cognitive_bus.py) — instantiates `ReplayMemoryEngine` from the `cognitive_layer` config; fire-and-forget worker, writes `logs/replay_queries.jsonl`.
- `models/replay/zone_registry_{BNB,SOL,ETH,BTC}USDT.json` — canonical normalized `zone_v1` replay registries (8 zones each, inverse-std weights, per instrument). All validate + assign non-collapsing (6–8 distinct clusters on each instrument's own opps).

## Ins / Outs
- **Ins:** `opportunities.jsonl` records (`features` dict, `outcome`, `rr_achieved`, `timestamp`); a `zone_v1` registry (`feature_order`, `feature_weights`, `zones[].center`). Config: `cognitive_layer` section (`zone_registry_path`, `opportunities_dir`, `max_replay_records`, decay/staleness).
- **Outs:** `query()` dict (`historical_winrate`, `historical_rr`, `failure_modes`, `replay_density`, `cluster_stability`, …); `REPLAY_QUERY` envelopes appended to `logs/replay_queries.jsonl`. **No** decision/fusion/execution output.

## Entry points & validations
- **Reached via:** `CognitiveBus.emit()` from `EngineRunner.run()` *after* the decision is finalized (async daemon thread). Producer registry via `python scripts/research/discover_zones.py --normalize --no-promote …`.
- **Validated by:** `tests/replay/` (assignment + engine). Invariant check: `fusion_engine.py` / `decision_engine.py` / `execution_planner.py` import nothing from `replay`/`cognitive` (dead-end sidecar). Part 4A OOS persistence study ([feature-region-oos-persistence-2026-06-01.md](docs/analysis/feature-region-oos-persistence-2026-06-01.md)).

## Tests
- [`tests/replay/test_assign_cluster.py`](tests/replay/test_assign_cluster.py) — non-collapse regression, weighting-consumed proof, legacy `centroid` back-compat, empty-registry fallback, determinism, generated-registry guard.
- [`tests/replay/test_replay_memory_engine.py`](tests/replay/test_replay_memory_engine.py) — load/query/decay/determinism/caps.
- [`tests/cognitive/test_cognitive_bus.py`](tests/cognitive/test_cognitive_bus.py) — non-blocking emit, drop telemetry, daemon lifecycle.

## Fits in architecture
A **kitchen feeder** that joins the spine off the decision path, not on it — see
[`docs/architecture/signal-flow.md`](docs/architecture/signal-flow.md) (AI/telemetry feeders) and
the `cognitive` package in [`docs/architecture/code-map.md`](docs/architecture/code-map.md).
The Probability-Surface→Fusion branch is gated behind the frozen
*Schema-Consistency-Before-Fusion* invariant.

## Discussion (filled in-session)
> Standing parallel-discussion surface. Append dated entries; never delete — supersede.

- **Risks:** 2026-06-02 — `_centroid_similarity` (advisory `similarity_score` only) compares the *raw* query vector against the now-weighted `stats.centroid`; and the `_build_cluster_stats` fallback centroid (computed from raw record features) is in raw space while a registry `center` is in weighted space. Mixed spaces — acceptable for advisory telemetry, but inconsistent. **Documented in code 2026-06-02** (`_centroid_similarity` docstring); proper fix (canonical-ordered weighted stored features both sides) deferred — monitoring-only and the main caller passes `[]` → neutral 0.5.
- **Per-instrument registry selection (design / bridge to advisory):** 2026-06-02 — `CognitiveBus` today loads ONE `ReplayMemoryEngine` with a single `zone_registry_path`, but a `DecisionSnapshot` carries its `instrument` and the registries are now per-instrument (`models/replay/zone_registry_<INST>.json`). **Recommended design:** route per instrument — either (a) a dict of lazily-loaded engines keyed by instrument (one registry + that instrument's opps each), or (b) extend `ReplayMemoryEngine` to hold an instrument→registry map and assign each record by `ReplayRecord.instrument`. Option (a) is simpler and matches the per-instrument advisory at query time. Implement under #6 wiring; keep monitoring-only.
- **Challenges:** 2026-06-02 — replay registries are built on full per-instrument data (no train/test split). The *OOS* validation is the separate harness ([feature-region-oos-persistence-multi-2026-06-02.md](docs/analysis/feature-region-oos-persistence-multi-2026-06-02.md)); these registries are the production assignment surface, not themselves an OOS test.
- **Blockers:** 2026-06-02 — **two hard preconditions before any Fusion wiring — BOTH NOW MET:** (1) ✅ per-instrument OOS confirmation (BNB/SOL/ETH/BTC all persist, persist_share 1.0 — see the multi-instrument OOS doc); (2) ✅ RME schema/weighting repair + assignment tests + 4 per-instrument registries. The *Schema-Consistency-Before-Fusion* invariant is therefore satisfied; advisory wiring is now permitted (see #6).
- **Ambiguities:** 2026-06-02 — active config (`ACTIVE_VERSION` → `v2_multi_2026_04 - deepdeektry`) has **no** `cognitive_layer` section; the corrected `zone_registry_path` lives in `v1_multi_2026_03.json` (source-of-truth). Live-config wiring deferred until the cognitive layer is enabled.
- **DECISION (#6, 2026-06-02): YES — ReplayMemory earns advisory status.** Both preconditions met (4-instrument OOS persistence; schema/weighting repair + 4 per-instrument registries). Five-Questions scoring: (2) comparable ✅ additive telemetry; (3) auditable ✅; (4) LLM-reasonable ✅ interpretable cluster stats; (5) authority isolated ✅ advisory never triggers/approves, 0.0 weight = zero authority; **(1) determinism ⚠️ the binding constraint** — the signal is currently computed in the **async daemon worker** (non-replay-comparable). **Therefore the grant is conditional:** before any non-zero weight it must (a) be **re-homed to the synchronous deterministic decision path** (a reviewed FusionEngine change — crosses the now-satisfied *Schema-Consistency-Before-Fusion* invariant), (b) enter at **weight 0.0, measured additively** (Phase-6 ROI pattern — telemetry already exists via `replay_queries.jsonl`/`cognitive_telemetry.jsonl`), (c) ship with full determinism/replay tests. Because this is a decision-spine change, the implementation is scoped to a **focused sub-plan**, not done inline. Per-instrument registry selection (design above) is its first step.
- **Enhancements:** 2026-06-02 — if/when wired, enter as a low-weight advisory (`weight_*` small, 0.0 default), measured additively (Phase-6 ROI pattern), never a primary gate.
- **Need more info:** 2026-06-02 — is `ACTIVE_VERSION` intentionally pointing at the `deepdeektry` experimental config, or is that drift?
- **REGRESSION FLAG (out of scope, 2026-06-16):** the 2026-06-02 `_assign_cluster` repair (read `center`, apply `feature_weights`) is **MISSING on the `patch` branch** — the on-disk code reads only `centroid` and does not weight, so `tests/replay/test_assign_cluster.py` has **8 pre-existing failures** (collapse-to-0 + the 4 generated-registry parametrizations). Confirmed pre-existing via `git stash` (independent of the STORY-1.5 `_build_cluster_stats` fix). NOT fixed here — it is a separate decision-spine-adjacent repair (sidecar, monitoring-only) outside Epic-1's "green the failing spine-trust tests" scope. Spun off as its own task; re-apply the `center`/weighting logic + re-validate against the 4 `models/replay/zone_registry_*.json` registries.
- **RESOLVED (2026-06-16):** the regression flag above is fixed. `_assign_cluster` now reads `center` (legacy `centroid` alias) and builds the query vector in **weighted** space (`feature_weights[i]`, default 1.0 when absent) before the nearest-center distance — matching the `discover_zones` producer. Cluster-id read stays `int(zone.get("zone_id", 0))` (tolerates the bare-int/no-schema test registries; NOT routed through `_zone_cluster_id`'s schema dispatch). `tests/replay/test_assign_cluster.py` + `test_replay_memory_engine.py` 20/20 green; broad golden/determinism/oracle/parity gate 55 passed (byte-identical — sidecar path is spine-neutral, F-012).

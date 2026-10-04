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

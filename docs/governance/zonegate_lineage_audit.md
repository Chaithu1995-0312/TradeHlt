# ZoneGate Lineage Audit

**Program:** Post-CH-002 model/training lineage (subsystem priority 2 — user-requested)  
**Date (UTC):** 2026-07-09  
**Active config:** `v2_multi_2026_04`  
**Prerequisite:** `POST_CH002_BASELINE_DIFFERENTIAL = PASS` · CRT CLOSED  
**Authority:** observational — no retrain, no promote, no weight/threshold flip

---

## Verdict

```text
ZONEGATE_LINEAGE_VERDICT = ACTIVE_GEOMETRIC + NO_MARGINAL_VALUE
  LIVE_RUNTIME           = ACTIVE (EXPECTED_ENGINES; HARD gate; models/zone_registry.json)
  TRAINING               = UNSUPERVISED KMeans on opportunities features
  LABEL_META             = CONTAMINATED (stored meta) / HONEST_NO_EDGE (F-041B)
  CH002_IMPACT           = INERT (pipeline 38-vector; not CRT FM-027/028 cache)
  REBUILD_REQUIRED       = NO for current production
  MARGINAL_OOS           = NO_MARGINAL_VALUE (F-036 ΔG001≡0 gate-ON; F-041B 0/8 zones E>0)
```

---

## Naming hygiene (do not conflate)

| Name | What it is | This audit? |
|---|---|---|
| **ZoneGate / BitNetZoneGate** | Geometric zone similarity scorer on 38-dim pipeline vector | **YES** |
| **BitNet 6-feature hard-reject** | `bitnet_score` inside CRT | **NO** — BitNet lineage |
| **zone_gate_registry.json** | Version **manifest** (not the scorer) | Documented only |
| **zone_registry.json** | **Runtime scoring** centroids | **YES** |

---

## Lineage chain (11 slots)

### 1. Training population

| Item | Detail |
|---|---|
| Primary research path | `scripts/research/discover_zones.py` — KMeans on `logs/opportunities_*.jsonl` feature dicts |
| Legacy | `scripts/analysis/zone_registry_builder.py` (profitable trades + FeaturePipeline + KMeans) |
| Other | `build_zone_registry_from_trades.py`, `build_zone_registry_forced.py` |
| Runtime artifact provenance | `source: discover_zones_v1_converted_to_gaussian` |
| Sample mass | Sum of zone `weight` fields ≈ **139,942** (≫ `zone_min_samples=50` underpowered floor) |

**Not** CRT `TRADE_OPENED` only. Population = opportunity/detection stream (F-022 class for **labels**, not for geometric μ/σ themselves).

### 2. Feature identities

| Item | Detail |
|---|---|
| Contract | Full **38** keys — `CANONICAL_FEATURE_ORDER` (`zone_gate_engine.py:29`, `filter_canonical_inputs:163-167`) |
| Registry `feature_order` | 38 names including pipeline `disp_strength`, `retest_depth` (FM-020/021) |
| Per-zone mask | ~**25** non-zero weights / ~13 near-zero (learned, not design mask) |
| CRT FM-027/028 | **Not used** — scores pipeline FeaturePipeline vector only |

### 3. Target / label

| Kind | Role at score time |
|---|---|
| **Training** | **Unsupervised** clustering — no supervised y |
| **Stored `meta`** (`mean_rr`, `sl_hit_rate`, n) | **Descriptive only** — **never read** by `compute_gaussian_score` / `check()` |
| F-041B re-derive | Stored SL≈0.96–0.99 vs honest SL≈0.65–0.66; **0/8 zones honest E>0** → meta CONTAMINATED + HONEST_NO_EDGE |

Runtime is purely geometric: weighted Gaussian similarity to zone (μ, σ, w).

### 4. Dataset builder

| Step | Implementation |
|---|---|
| Vectorize | `_vector_from_record` over `CANONICAL_FEATURE_ORDER` (`discover_zones.py`) |
| Cluster | Pure-stdlib / numpy KMeans (`--n-clusters` default 8, `--min-samples`) |
| Emit | JSON registry `{schema_version, feature_order, zones:[{id,mu,sigma,weights,threshold,meta,weight}]}` |
| Convert | discover_zones → v2_gaussian form consumed by BitNetZoneGate |

Label audit (research only): `src/research/zone_label_audit.py` / `scripts/research/zone_label_audit.py`.

### 5. Artifact

| Path | Role | SHA-256 (pin) |
|---|---|---|
| **`models/zone_registry.json`** | **Runtime scorer** (config `zone_registry_path`) | `e73e08934add02c9…eda3` |
| `models/zone_gate_registry.json` | Version manifest | `e6d36474…87c09` |
| Manifest active | `v2_gaussian_runtime_2026_07` → `models/zone_registry.json` | **F-041A reconciled 2026-07-05** |

**Runtime registry facts:**
- `schema_version=v2_gaussian`
- **8 zones** (`zone_0`…`zone_7`)
- Each ~25 active weight dims
- Stored meta still shows contaminated SL≈0.96–0.99 (research display only)

Invariant: `tests/test_zone_manifest_runtime_parity.py` — manifest active SHA == runtime file.

Matches pre-remediation baseline pin (`PRE_REMEDIATION_BASELINE.md` zone_registry `e73e0893…`).

**Provenance: RECONSTRUCTED 2026-07-21 (was: producer absent).** The artifact declares
`source: discover_zones_v1_converted_to_gaussian` / `weight_strategy: scale_free_v1`, but no
script in the repository emitted the `v2_gaussian` schema — the converter had been run ad hoc
and lost, so a live gating artifact was not reproducible. Recovered by
`scripts/analysis/zone_registry_provenance_probe.py` (READ-ONLY) against the original corpus
(`logs/BNBUSDT/bnbusdt_training_20260524/opportunities.jsonl`, 139,942 records):

| Component | Rule | Verification |
|---|---|---|
| membership | `discover_zones._kmeans`, k=8, seed=1337 | 8/8 cluster sizes exact, identity order |
| `mu` | per-cluster centroid, round 6dp | max abs delta **0.0** (38 dims × 8 zones) |
| `sigma` | `round(max(GLOBAL per-dim std ddof=0, 0.01), 6)` | **38/38 dims exact** |
| `weights` | `scale_free_v1` — 0.0 on the 13 absolute price/volume dims, uniform 1/25 elsewhere | 8/8 zones exact |
| `threshold` | constant 0.3 | value reproduced; **derivation still unknown** (inert — the spine reads only `top_scores`) |

Two non-obvious facts the reconstruction pinned: **`sigma` is a single GLOBAL vector replicated
onto every zone**, not a per-cluster dispersion (the per-cluster hypothesis was tested and
refuted), and the **0.01 floor is load-bearing** — `atr`'s true std is 0.00237 and the artifact
stores exactly `0.010000` for it. Because `sigma` is a whole-corpus statistic, the conversion
was never a pure JSON→JSON transform; it needed the source stream, which is the likely reason
it was run ad hoc.

Converter committed as `scripts/research/convert_zones_v1_to_gaussian.py`; `--compare` against
the live artifact reports IDENTICAL. **The artifact was NOT regenerated** — byte-identity is
the proof, and rewriting a live gating file carries risk for no gain. This closes a provenance
gap only; it grants no authority (§6.5) and changes no behavior.

### 6. Loader

| API | Behavior |
|---|---|
| `get_zone_gate(path, …)` / `BitNetZoneGate` | Loads via `load_zone_registry` (`live_engine.py`) |
| **Empty/unloadable registry → fail-CLOSED** | Missing/malformed registry → empty zones → `check()` returns score **0.0** and omits `top_scores` ⇒ `zone_cluster_score._model_fn` falls through to 0.0, which fails `zone_cluster_threshold` (0.25) ⇒ **every candle BLOCKS**. Schema error inside `run_zone_gate_engine` is a *different* path and does fail open (score 0.5, passed=True). |
| Underpowered guard | Total `weight` &lt; `zone_min_samples` (50) → auto-bypass `underpowered_zone_registry` (score 1.0 ⇒ **passes**) |
| Disabled gate | `enabled=False` → `gate_disabled`, score 1.0 ⇒ **passes** |
| Hot-reload | `RegistryWatcher` on path mtime |

EngineRunner: `zone_registry_path` + nested `zone_gate.top_k` → `get_zone_gate(..., top_n=_zone_top_k)`.

### 7. Inference inputs

```text
pipeline feature dict (38 CANONICAL keys)
  → filter_canonical_inputs
  → _extract_vector  (float list, len=38; may truncate older 35-dim models)
  → BitNetZoneGate.check(vector)
       for each zone: compute_gaussian_score(features, zone)
         score = Σ w_k · exp(−½ ((x_k−μ_k)/σ_k)²) / Σ w_k
       top_scores (top_k)
  → compute_weighted_cluster_score(top_scores, spread_max)
       <2 neighbors → max; spread > spread_max → 0; else weighted sum of squares / total
```

### 8. Output semantics

| Output | Meaning |
|---|---|
| Per-zone score | Similarity ∈[0,1] to historical cluster centroid |
| Cluster score | Aggregated top-k neighborhood quality |
| HARD mode | Compare to `zone_cluster_threshold` (0.25) — pass/fail vote into fusion context |
| Fusion contribution | `engine_results["zone_gate"]` → weight `weight_zone_gate=0.2` |
| **Not** | True RR, p(win), or expectancy — geometric neighbourhood only |

Per-zone `allowed` / threshold path inside `check()` is **not** the live spine authority; spine uses **top_scores + cluster aggregation** then fusion (`active_models` / engine_runner comments).

### 9. Active config

| Key | Value |
|---|---|
| `engine_runner.zone_registry_path` | `models/zone_registry.json` |
| `zone_mode` | `hard` |
| `zone_gate_execution_mode` | `normal` |
| `zone_gate.top_k` | `3` |
| `zone_gate.cluster_min_n` | `2` |
| `zone_gate.cluster_spread_max` | `0.15` |
| `zone_cluster_threshold` | `0.25` |
| `zone_min_samples` | `50` |
| `fusion_engine.weight_zone_gate` | `0.2` |

`EXPECTED_ENGINES` includes `"zone_gate"`.

### 10. Runtime consumption

```text
EngineRunner.run
  → _zone_model_fn(vector)
       → BitNetZoneGate.check → top_scores
       → compute_weighted_cluster_score
  → run_zone_gate_engine(..., threshold=zone_cluster_threshold)
  → engine_results["zone_gate"]
  → FusionEngine.compute (weight 0.2)
  → DecisionEngine
```

**Active on spine** (unlike BitNet / TradeNet).  
**Gate-ON baseline:** zone loads 8 zones (log: `BitNetZoneGate: loaded 8 zones from models/zone_registry.json`).

Backtest research default often `BACKTEST_ENGINE_GATE=0` (F-037) → zone never runs in CRT-only research corpus; **live-equivalent** needs gate ON (as post-CH-002 baseline).

### 11. Marginal OOS value

| Evidence | Result |
|---|---|
| **F-036** gate-ON ablation | `weight_zone_gate` ∈{0,0.2,0.4,0.6} × threshold ∈{0,0.25,0.5} → **byte-identical entries** ⇒ ΔG001≡0 |
| Mechanism (F-036) | Zone **not weak** (mean≈0.61, often above 0.25) and **not under-weighted** → **redundant / decision-dominated** |
| **F-041B** | 0/8 zones honest E>0 under `forward_walk` |
| Config knobs | TUNABLE (CONFIG_DRIVEN) but **no authority** (§6.5) |

**Verdict slot:** `NO_MARGINAL_VALUE` — rebuild/retrain does not earn production weight without a new ontology + ΔG001 proof.

---

## CH-002 impact assessment

| Question | Answer |
|---|---|
| Does ZoneGate read CRT `displacement_retrace` / `displacement_atr_ratio`? | **No** |
| Feature names in registry | Pipeline `retest_depth` / `disp_strength` (unchanged by CH-002) |
| Live score delta from CH-002 rename? | **None expected** — confirmed indirectly by full BNB economic parity (PASS) |
| Rebuild required for CH-002? | **NO** |

Historical opportunities used for KMeans still use pipeline feature keys; CRT emission rename does not shift the zone vector.

---

## Rebuild / retrain matrix

| Action | Allowed now? | Condition |
|---|---|---|
| Retrain zones because of CH-002 | **NO** | Pipeline identities unchanged; live non-pivotal |
| Re-label meta for research docs | Optional hygiene | Does not change runtime scores |
| Change top_k / weight_zone_gate | Config-legal | **No authority** without ΔG001 (F-036) |
| Promote alternate zone file | Via registry + config path | Must keep manifest parity test green |
| Drop ZoneGate from EXPECTED_ENGINES | Architecture program | Not this audit |

---

## Known gaps / non-blockers

1. **Name collision** BitNetZoneGate ≠ BitNet model.  
2. **Per-zone `allowed` threshold** computed but **bypassed** on live spine aggregation path.  
3. **Stored meta contamination** (F-041B) — research/docs only.  
4. **Soft zone mode** exists (`_compute_soft_zone_score`) — not the active hard path.  
5. **Docstring drift** in `check()` (“11-dim”) vs 38-dim contract.  
6. **Research gate-OFF** still confuses zone-inert measurements unless gate forced ON (F-037).  
7. Manifest was historically split-brain — **reconciled F-041A**; do not re-point active away from runtime without protocol.
8. **`no_zones_fail_open` mislabel — CORRECTED 2026-07-21 → `no_zones_fail_closed`.** The
   branch has always blocked (score 0.0, `top_scores` omitted), but its reason string,
   `allowed: True` field, CRITICAL log ("All trades are passing unfiltered"), and code comment
   all asserted the opposite. The false belief had propagated into two test surfaces that
   *encoded* it — `src/bitnet/_smoke_test.py` ("Missing registry must fail-open") and a test
   literally named `test_no_zones_underpowered_is_false_but_fails_open`. All five surfaces
   corrected; behavior deliberately unchanged (blocking is the safer failure for an unloadable
   registry — the alternative admits unfiltered trades). Regression-pinned by
   `tests/test_zone_gate.py::test_empty_registry_reason_string_matches_its_behaviour`, which
   asserts the reason string cannot advertise fail-open while the score blocks.
   `PRODUCTION_BEHAVIOR_CHANGED = NO`.
9. **Assignment parity (0.414) — RESOLVED 2026-07-22.** The recorded sub-finding is closed,
   and the framing behind it corrected: **the runtime SCORES, it never PARTITIONS.** The live
   decision is `top_scores` → `compute_weighted_cluster_score` → `>= zone_cluster_threshold`;
   no record is assigned to a zone (`best_zone_id` is telemetry, no consumer). So "assignment
   parity" measured a partitioning the runtime does not perform. Mechanically low because the
   13 runtime-zeroed dims carry **99.9983%** of the variance driving the KMeans objective
   (`volume` 97.58%) — KMeans partitioned by volume/price level, the runtime scores candle
   shape. Correct null is the majority baseline 0.3264 (not 1/8); κ=0.238; all 8 zones show
   positive lift over their runtime marginal. Runtime argmax concentrates 77.7% on zones 2+7
   (51.8% label share); ~95% of records have top1−top2 margin < 0.05, and the per-zone margin
   gradient is BIMODAL (attractors agree more when confident; disfavoured zones fall to ≈0 —
   two mechanisms, so no single scalar describes it). Probe
   `scripts/analysis/zone_assignment_parity_probe.py`; artifact
   `docs/analysis/zone-assignment-parity.LATEST.json` (recorded 0.4140 reproduced exactly,
   delta 0.0). Information only — grants no authority (§6.5).

---

## Key file map

| Role | Path |
|---|---|
| Engine wrapper | `src/engines/zone_gate_engine.py` |
| Gate loader/check | `src/engines/live_engine.py` — `BitNetZoneGate` |
| Similarity | `src/bitnet/zone_cosine_searcher.py` — `compute_gaussian_score` |
| Orchestration | `src/core/engine_runner.py` — `_zone_model_fn`, zone_gate knobs |
| Train | `scripts/research/discover_zones.py` |
| Runtime artifact | `models/zone_registry.json` |
| Manifest | `models/zone_gate_registry.json` |
| Label audit | `src/research/zone_label_audit.py` |
| Findings | F-036, F-037, F-041 / F-041A / F-041B |
| Config | `v2_multi_2026_04.json` engine_runner + fusion weights |
| Intent | `docs/topics/model-intent-and-feature-ownership.md` |
| active_models | `active_models.yaml` → `zone_gate:` |
| Parity test | `tests/test_zone_manifest_runtime_parity.py` |

---

## Comparison to other audits

| | Gaussian | ZoneGate | BitNet | TradeNet |
|---|---|---|---|---|
| On spine | YES (heuristic) | **YES (trained geometric)** | NO | NO |
| Trained artifact used live | mu/sigma only | **Full 8-zone registry** | unused | unused |
| CH-002 impact | INERT | **INERT** | SKEW if enable | INERT |
| Marginal value | unmeasured heuristic | **NO (F-036/F-041B)** | N/A | N/A |
| Rebuild now | NO | **NO** | NO | NO |

ZoneGate is the **only** fused engine that scores a full trained multi-dim artifact on the live path — and it is still **non-pivotal**.

---

## Comparison to the IC-003B shape library (same prototype-cluster design, honest re-run)

ZoneGate and the research **IC-003B sequence-geometry shape library** are the **same design pattern**:
*cluster engineered-feature space into a few prototypes via KMeans → attach historical outcome labels →
assign by nearest prototype.* ZoneGate is the **static-entry, production-wired, HARD-gate** incarnation;
IC-003B is the **sequence/trajectory, research-only, descriptive** one. Both reached the **same null** —
which is the point of recording this here.

| Dimension | **ZoneGate** (this audit) | **IC-003B shape library** (`results/research/ic_003b/`) |
|---|---|---|
| Object clustered | one **static** 38-dim entry vector | a **trajectory** (t-15…t+20 path summary), 105-dim (Arm S) / DTW-3ch (Arm T) |
| Algorithm | `KMeans` (`discover_zones`) → Gaussian μ/σ scorer | `MiniBatchKMeans` (Arm S) / DTW k-medoids (Arm T) |
| K | **8 zones, fixed** | k∈{4,6,8,12} **gate-selected** (6 for the OK unit) |
| Label source | opportunities **stream** — F-022 contaminated (registry shows **~98% SL** on every zone) | **`forward_walk`** (honest exit model) |
| Quality gate | `min_samples≥10` + fixed `threshold 0.3` — **cannot fail to be a library** | **G1 compactness ≤0.85, G2 silhouette ≥0.05, G3 OOS robust-z, G4 min-n** — a gate that *can* FAIL (and did → PARTIAL) |
| Authority | **production HARD gate** (`zone_mode=hard`, wired) | **NONE** — PL-0, descriptive (§6.5) |
| Verdict | **INERT** (F-036 ΔG001≡0) + **0/8 zones honest E>0** (F-041B) | **`IC003B_PARTIAL`** — near-noise, seed-unstable k\*, weak continuum |

**Four design flaws of ZoneGate that IC-003B fixes by construction:** (1) **honest labels** —
`forward_walk` vs the F-022 stream whose 98%-SL meta was never trustworthy (F-041B); (2) **a gate that can
fail** — silhouette/compactness/OOS vs bare `min_samples`, so IC-003B can *conclude "no library"* where
ZoneGate always emits 8 zones; (3) **authority discipline** — IC-003B stays unwired until it earns ΔG001,
whereas ZoneGate was wired to production **before** proving edge (existence→authority); (4) **robustness** —
IC-003B swept seeds (k\* unstable) where ZoneGate's 8 zones were taken as given.

**Convergent verdict.** Both expose the same wall: **KMeans on engineered features finds structure (blobs)
that is orthogonal to expectancy** — prototypes differ in *anatomy/shape*, not *win-rate*. That is **F-023**
("morphology separates SHAPE, not expectancy") as a design principle, and it is *why* ZoneGate is inert
(F-036/F-041B) and IC-003B is near-noise. IC-003B therefore **independently re-confirms the ZoneGate null**
on a different representation (sequence vs static) with an honest label source and a real statistical gate —
strengthening, not reopening, this audit's `NO_MARGINAL_VALUE` verdict.

**Cross-refs:** IC-003B registry `docs/research-readiness/erp-information-class-boundary.json`
(`IC-003B.robustness` / `program_verdict`), `docs/research-readiness/shape_explanations.md`; findings
**F-023 / F-036 / F-041B**. Authority: observational/synthesis — **no new finding**, no retrain, no weight
flip; grants no authority to either model.

---

## Final return

```text
ZONEGATE_ACTIVE_ON_PATCH = true (geometric HARD gate)
ZONEGATE_LINEAGE_STATUS  = ACTIVE_GEOMETRIC + NO_MARGINAL_VALUE
REBUILD_REQUIRED_NOW     = NO
CH002_IMPACT             = INERT
NEW_FINDINGS             = none (F-036 / F-041 already cover)
DO_NOT                   = retrain zones for rename; grant fusion authority; reopen CRT
NEXT_SUBSYSTEM           = RR Engine lineage audit (priority 3 remaining)
```

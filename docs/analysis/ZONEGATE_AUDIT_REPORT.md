# ZoneGate Audit Report
**Date:** 2026-07-26
**Scope:** Source-based audit of all ZoneGate-related implementations
**Precedent:** CRT_AUDIT_REPORT.md, GAUSSIAN_AUDIT_REPORT.md (same methodology)

---

## Architecture Overview

The ZoneGate subsystem spans **four layers** with an external black-box dependency:

| Layer | File | Role | Execution Authority |
|---|---|---|---|
| **Orchestration (hard path)** | `src/engines/zone_cluster_score.py` (90 lines) | Cluster-weighted score + pass/fail via zone_gate_engine | **PRIMARY** — what FusionEngine sees |
| **Core gate logic** | `src/engines/zone_gate_engine.py` (309 lines) | Vector extraction, schema validation, pass/fail, cluster score | **CORE** |
| **Registry loader + per-zone scorer** | `src/engines/live_engine.py` class `BitNetZoneGate` (:185-406) | Loads registry, delegates to bitnet module | **LOADER** |
| **External similarity** | `bitnet.zone_cosine_searcher` (not in repo `src/`) | Per-zone Gaussian cosine similarity (`compute_gaussian_score`) | **BLACK BOX** |
| **Soft score helper** | `zone_gate_engine.py:89-103` `_compute_soft_zone_score()` | Soft mode (distance+freshness+strength) | **NOT active** (zone_mode="hard") |
| **Legacy ghost** | `scoring_engine.py:64-93` | Import-guarded zone cosine + fallback kernel | **ZERO call sites** |

**Naming hazard:** The `BitNetZoneGate` class (ZoneGate engine) is distinct from the `bitnet` model (6-feature hard-reject gate inside `UltronRiskEngine.approve()`, `use_bitnet=false`). These occupy DIFFERENT architectural slots — ZoneGate is an `EXPECTED_ENGINES` producer; bitnet gates inside CRT's approval chain with `engine_key=null`.

---

## 1. Input Contract Verification

### 1A. Production path (EngineRunner → zone_cluster_score → run_zone_gate_engine)

| Component | Inputs | Outputs | Status |
|---|---|---|---|
| `run_zone_gate_engine(raw_features, model_fn, threshold, zone_registry, ...)` | Full 39-key canonical feature dict + callable model_fn + threshold | `{"score": float [0,1], "passed": bool, "vector": list[float], "valid": bool}` | ✅ |
| `score_zone_cluster(raw_features, zone_gate, ...)` | Full 39-key canonical features + BitNetZoneGate instance | `{score, cluster_score, passed, vector, best_zone_id, best_zone_score, top_scores, meta}` | ✅ |
| `filter_canonical_inputs(raw)` | Raw feature dict | Validated dict with all 39 `CANONICAL_KEYS` | ✅ — fail-fast if missing keys |
| `_extract_vector(features, feature_order)` | Feature dict + optional `feature_order` list | `list[float]` in trained name order | ✅ — name-anchored, never ambient truncation |

**Key observations:**
- The vector is built in **trained name order** from `feature_order` (supplied by the registry), never by ambient canonical position.
- `filter_canonical_inputs` requires ALL 39 canonical keys, but `_extract_vector` only extracts the 38 that are in the registry's `feature_order` (deliberately excludes `macd_hist_raw`).
- Schema v4.0 alignment: the active registry uses `macd_hist_z` and `candle_range` (renames from v3.0's `macd_hist`/`wick_size`) — `_validate_feature_order()` checks that all trained names exist in the live schema and **fail-closes at load** if they don't (raised as `ZoneFeatureOrderError`).
- The v2 registry entry (`v2_gaussian_runtime_2026_07`, `active:false`) would now FAIL CLOSED because its `feature_order` names `macd_hist`/`wick_size` which no longer exist in the v4 live schema.

### 1B. Inputs consumed vs not consumed

| Consumed | Not Consumed |
|---|---|
| 38 canonical features via name-anchored extraction | CRT-specific state (RANGE/SWEEP/DISPLACEMENT/...) |
| `feature_order` from registry for alignment | CRT-specific outputs (`retest_depth` as separate concept — it IS in the 38 features) |
| `zone_cluster_threshold` (0.25 default) | Gaussian score (`gaussian_result`) |
| `execution_mode` ("normal") | Risk score or trade decision |
| `zone_debug_config` (debug mode only) | OHLCV raw prices (only via normalized features) |

**Verdict: Input contract is correct.** ZoneGate consumes the canonical feature vector through the name-anchored contract, never by position. It does NOT recompute CRT state or Gaussian similarity.

---

## 2. Similarity Computation — Zone Representation and Matching

### 2A. Zone Representation

The active artifact (`models/zone_registry_v4_2026_07.json`) contains **8 Gaussian zones**:

| Property | Value |
|---|---|
| Schema | `v4_gaussian` |
| Feature dimension | 38 (excluding `macd_hist_raw`) |
| Zones | 8 (zone_0 through zone_7) |
| Total training samples | ~140,942 (across all zones) |

Each zone stores:
- **mu** (38-dim mean vector)
- **sigma** (38-dim radius vector) — **IDENTICAL across ALL 8 zones** (global batch sigma, not per-zone estimated)
- **weights** (38-dim importance) — **IDENTICAL mask across ALL 8 zones**: 24 active dims at 0.04 each, 14 zeroed dims (price levels: open/high/low/close/volume, EMA values, macd_line/macd_signal, body_size/wick_size). In v4, `session` is also zeroed (→ 24 active dims).
- **threshold** (all 0.3)
- **meta**: n_samples, mean_rr, tp_hit_rate, sl_hit_rate per zone

**Finding 1 (AUTHORITATIVE): The weights are NOT learned.** All 8 zones carry an IDENTICAL weight vector with a hand-specified zero-set. This is confirmed in `active_models.yaml`: "every zone carries exactly 25 weights of 0.04 with an IDENTICAL zero-set across all 8 zones — a hand-specified mask dropping the 13 price-level dims, not a trained importance vector." In v4, session is also zeroed (→ 24 active dims at ≈0.04167 each).

**Finding 2 (INFORMATIONAL): Sigma is global, not per-zone.** All 8 zones share the SAME sigma vector. This means the zone radius is not individually parameterized — the "zones" differ only in their center positions (mu) and sample counts.

### 2B. Similarity Computation (hard path)

```
BitNetZoneGate.check(vector) → per-zone Gaussian cosine similarity scores
    ↓
top_scores extracted (configurable via zone_gate.top_k, default 3)
    ↓
if len(top_scores) >= cluster_min_n (default 2):
    compute_weighted_cluster_score(top_scores, spread_max=0.15)
        - Reject cluster if max-min spread > 0.15
        - Self-weighted sum: Σ(s_i / Σs) × s_i
else:
    fallback to max(top_scores)
    ↓
run_zone_gate_engine: passed = cluster_score >= zone_cluster_threshold (default 0.25)
```

**Key properties:**
- The weighted cluster score is nearest-neighbour interpolation, not a proper density estimate.
- The spread filter (reject if max-min > 0.15) prevents unstable clusters.
- With only 2 neighbours and spread ≤ 0.15, the self-weighted formula reduces to `(s1² + s2²) / (s1 + s2)`.
- The underlying per-zone scoring is delegated to `bitnet.zone_cosine_searcher.compute_gaussian_score()` — a **black-box external dependency** not in this repo's source tree.

### 2C. Soft path (NOT active)

`_compute_soft_zone_score(raw_features, w1=0.5, w2=0.3, w3=0.2)` returns `w1×exp(-distance) + w2×freshness + w3×strength` using raw feature fields `zone_distance`, `zone_freshness`, `zone_strength`. This path is gated behind `zone_mode="soft"` in config; the active config uses `"hard"` so the soft score only overrides the score value while the pass/fail decision still comes from the hard gate.

### 2D. Per-zone historical quality (from zone registry meta)

| Zone | n_samples | mean_rr | tp_hit_rate | sl_hit_rate |
|---|---|---|---|---|
| zone_0 | 20,708 | -0.0292 | 1.3% | 98.6% |
| zone_1 | 10,100 | -0.0180 | 1.7% | 98.3% |
| zone_2 | 45,674 | -0.0519 | 1.3% | 98.7% |
| zone_3 | 31,540 | -0.0448 | 1.1% | 98.9% |
| zone_4 | 3,872 | +0.0124 | 1.9% | 98.0% |
| zone_5 | 172 | +0.1163 | 4.1% | 95.9% |
| zone_6 | 1,162 | +0.0897 | 3.1% | 96.6% |
| zone_7 | 26,714 | -0.0500 | 1.3% | 98.7% |

**Finding 3 (CRITICAL): 6 of 8 zones have NEGATIVE mean RR.** Only zones 4/5/6 have positive mean_rr, and zone_5 has only 172 samples (likely noise). The three "profitable" zones represent only ~5,206 of ~140,942 total samples (3.7%).

**Finding 4 (CRITICAL): Labels are F-022 contaminated.** The zone discovery used raw `rr_achieved` labels from the contaminated stream, not forward_walk-derived labels. The audit in `active_models.yaml` confirms: "stored ~98% SL-hit labels are an F-022 ARTIFACT (honest intrabar_fixed SL≈0.66 on VERIFIED-identical KMeans membership) AND 0/8 zones clear honest E>0."

---

## 3. Historical Authority

### Zone Origin

The zones were produced by `discover_zones_v1_converted` — a discovery algorithm that ran on historical OHLCV data. The representation is a **Gaussian mixture model over feature space**, with zones capturing high-density regions of historically observed feature vectors associated with trade entries.

### Key authority questions

| Question | Answer |
|---|---|
| Are zones derived from actual historical trades? | ✅ Yes — 140,942 training samples across 8 zones. |
| Are labels economically validated? | ❌ No — F-022 contaminated (98% SL-hit labels from raw rr_achieved). |
| Does any zone show positive expectation? | ❌ 0/8 zones clear "honest E>0" under forward_walk assessment. |
| Is the gate pivotal in fusion? | ❌ No — ΔG001≡0 (F-036): zone is non-pivotal, redundant/decision-dominated. |
| Was retraining causal or contaminated? | ❌ Labels are intrabar-fixed without forward walk. |

**Finding 5 (AUTHORITATIVE): The zones are historically derived but NOT economically validated.** The discovery process produced zones from real data, but the labels that defined "profitable" regions are F-022 contaminated. Under honest forward_walk assessment, 0/8 zones show positive expectancy. Furthermore, the gate itself has ΔG001≡0 — switching it on or off does not change fusion outcomes, making the question of historical quality largely moot operationally.

---

## 4. Output Contract

### Current Outputs

```
run_zone_gate_engine:
{
    "score":  float [0,1],    # cluster score
    "passed": bool,           # score >= threshold
    "vector": list[float],    # 38-dim extracted vector
    "valid":  bool,           # = passed in normal mode
}

score_zone_cluster (enriched):
{
    "score":          float,
    "cluster_score":  float,       # same as score
    "passed":         bool,
    "vector":         list[float],
    "valid":          bool,
    "best_zone_id":   str | None,
    "best_zone_score": float | None,
    "top_scores":     [float],     # top-k scores for debugging
    "meta":           dict,        # full run_zone_gate_engine result
}

EngineRunner wraps as engine_results["zone_gate"]:
{
    "engine":    "zone_gate",
    "score":     float,           # [0, 1]
    "direction": int,             # 1 if passed, 0 if blocked (NEVER -1)
    "meta":      dict,            # full score_zone_cluster result
}
```

| Output | Produced? | Purpose |
|---|---|---|
| Similarity score (0-1) | ✅ | Primary — enters fusion weighted at 0.20-0.25 |
| Pass/fail | ✅ | Used for direction (1=pass, 0=fail) |
| Nearest matching zone | ✅ | `best_zone_id` in meta |
| Cluster scores | ✅ | `top_scores` and cluster aggregation |
| Confidence interval | ❌ | Not produced |
| Per-zone breakdown | ✅ | Via `best_zone_id` + `best_zone_score` |
| Likelihood / density | ❌ | Not produced — score is a cluster similarity, not a density |

**Finding 6 (MINOR): ZoneGate's direction is binary 1/0, not ternary -1/0/1.** It always votes LONG when passing, never SHORT. This is architecturally correct — ZoneGate is a quality gate, not a directional predictor — but means the conflict detection in FusionEngine will never detect a conflict from ZoneGate since it only votes 1 or 0.

---

## 5. Ownership Boundaries

| Boundary | Code Evidence | Status |
|---|---|---|
| ZoneGate should NOT recompute CRT state | Consumes canonical features only (via `filter_canonical_inputs` + `_extract_vector`); no CRT state machine import | ✅ |
| ZoneGate should NOT recompute Gaussian independently | Delegates per-zone scoring to `bitnet.zone_cosine_searcher.compute_gaussian_score()`; `compute_weighted_cluster_score()` is aggregation only, not a re-scoring | ✅ |
| ZoneGate should NOT produce trade decisions | Outputs score+pass to FusionEngine; only the DecisionEngine applies final threshold | ✅ |
| ZoneGate should NOT redefine OHLCV | Uses only pre-computed canonical features; no raw price reinterpretation | ✅ |
| ZoneGate should NOT estimate profit | `compute_weighted_cluster_score()` evaluates similarity only; no RR or expected return term | ✅ |
| ZoneGate should NOT know about CRT state names | No import from `crt_engine_v2.py` or `state_identity.py` | ✅ |
| ZoneGate should fail-closed on vector misalignment | ✅ — `ZoneFeatureOrderError` prevents construction at load, not a silent fallback | ✅ |

**Verdict: Ownership boundaries are correct.** Each component stays within its documented responsibility. The most important boundary is the **fail-closed on vector misalignment** — the gate refuses to start rather than scoring against a wrong-dimension vector.

---

## 6. Causal Correctness

| Check | Evidence | Status |
|---|---|---|
| Temporal accumulation | Stateless per-bar computation — `BitNetZoneGate.check()` scores each vector independently | ✅ |
| Future data in features | Consumes pipeline features at current bar (passed from EngineRunner) | ✅ |
| Lookahead in model loading | Registry loaded at init (static artifact); hot-reload re-reads same static file on disk | ✅ |
| Online retraining | None — registry is static; no online adaptation | ✅ |
| Feature extraction | Name-anchored via `_extract_vector()` — never by ambient position | ✅ |
| Schema validation at load | `_validate_feature_order()` checks trained names exist in live schema — fail-CLOSED | ✅ |
| Cluster spread filter | `compute_weighted_cluster_score()` rejects clusters with max-min > 0.15 — prevents unstable decisions | ✅ |
| Underpowered registry bypass | `BitNetZoneGate._underpowered` check (default 50 samples) — passes with score=1.0 when registry is too small to be meaningful | ✅ |

**Verdict: No causal leakage detected.** All scoring consumes current-bar features only. The registry is a static artifact. The name-anchored extraction prevents positional misalignment.

---

## 7. Production Authority — Implementation Identification

### Implementation Inventory

| Component | Status |
|---|---|
| `src/engines/zone_cluster_score.py` (score_zone_cluster) | **AUTHORITATIVE** — orchestrates the hard path, called by EngineRunner |
| `src/engines/zone_gate_engine.py` (run_zone_gate_engine, _extract_vector, compute_weighted_cluster_score) | **CORE** — vector extraction + schema validation + pass/fail + cluster weighting |
| `src/engines/live_engine.py` BitNetZoneGate class + `get_zone_gate()` | **LOADER** — registry I/O + per-zone scoring via black-box module |
| `bitnet.zone_cosine_searcher.compute_gaussian_score()` | **BLACK BOX** — external module, per-zone similarity computation |
| `zone_gate_engine.py:_compute_soft_zone_score()` | **DORMANT** — zone_mode="hard" in active config; soft mode shadows score only |
| `scoring_engine.py:64-93` compute_gaussian_score (zone import guard) | **GHOST** — zero call sites, identical to GAUSSIAN_AUDIT Finding 1 |
| `models/zone_registry_v4_2026_07.json` | **ACTIVE ARTIFACT** — 8 Gaussian zones, v4 schema |
| `models/zone_gate_registry.json` | **VERSION REGISTRY** — version selection (active: `v4_gaussian_runtime_2026_07`) |

### Production Config Authority

| Setting | Active Config Value |
|---|---|
| `zone_registry_path` | `models/zone_registry_v4_2026_07.json` (via ModelResolver) |
| `zone_mode` | `"hard"` |
| `zone_min_samples` | `50` |
| `zone_gate.top_k` | `3` |
| `zone_gate.cluster_min_n` | `2` |
| `zone_gate.cluster_spread_max` | `0.15` |
| `zone_cluster_threshold` | `0.25` |
| Fusion weight: zone_gate | `0.20` (`v2_multi_2026_04` config) |

**Production path:** `EngineRunner.run()` → `score_zone_cluster()` → `run_zone_gate_engine()` with `_model_fn` wrapper → `BitNetZoneGate.check()` → external `bitnet.zone_cosine_searcher.compute_gaussian_score()` per zone → `compute_weighted_cluster_score()` aggregation → pass/fail vs `zone_cluster_threshold` (0.25).

### Flow of the Black Box

The most important architectural fact: **the per-zone similarity is computed by `bitnet.zone_cosine_searcher.compute_gaussian_score()`, which is not in this repository's `src/` directory.** This is an external dependency. The repo's ZoneGate code handles:
1. Schema validation (v4 alignment, name-anchored extraction)
2. Registry loading (file I/O, version selection)
3. Cluster aggregation (nearest-neighbour interpolation)
4. Pass/fail thresholding

But the core mathematical operation — "how similar is this feature vector to zone N?" — is delegated outside.

### Fusion Integration

ZoneGate score enters FusionEngine at configurable weight (`weight_zone_gate`: 0.20 in active `v2_multi_2026_04` config, 0.25 in FusionConfig defaults). FusionEngine also has a dead-engine health tracker for ZoneGate (`EngineHealthTracker _health_zonegate`) that excludes a permanently-zero zone_gate from fusion weights — though zone_gate fails to `score=0.5` not `0.0` on registry errors, so this dead-engine detection would only fire if the gate consistently produces zero (which it doesn't in normal operation).

---

## 8. Detailed Findings

### Finding 1 (AUTHORITATIVE) — Hand-Specified Weight Mask, Not Learned
- **Severity:** INFORMATIONAL (architectural, not a bug)
- **Location:** All 8 zones in `models/zone_registry_v4_2026_07.json`
- **Impact:** The zone importance weights are IDENTICAL across all 8 zones — a hand-specified mask zeroing 14 of 38 dims (price levels, EMAs, macd components, body/wick size). This is NOT a learned feature importance vector. The zones differ only in center positions (mu) and sample counts.
- **Recommendation:** Document explicitly that zone weights are a hand-specified structural mask, not a trained parameter. If feature importance learning is desired, it must be implemented separately.

### Finding 2 (INFORMATIONAL) — Global Sigma, Not Per-Zone
- **Severity:** INFORMATIONAL
- **Location:** `models/zone_registry_v4_2026_07.json`
- **Impact:** All 8 zones share the SAME sigma vector. Zone radius is not individually parameterized.
- **Recommendation:** If per-zone radius estimation would improve discrimination, the discovery process should be updated to estimate per-zone covariance.

### Finding 3 (CRITICAL) — 6 of 8 Zones Have Negative Mean RR
- **Severity:** HIGH (research impact, not operational)
- **Location:** Zone meta in `zone_registry_v4_2026_07.json`
- **Impact:** 6 of 8 zones show negative mean RR on their own training labels. The 2 positive zones (4 and 6) are barely so (+0.0124, +0.0897). Zone 5's positive value (+0.1163) comes from only 172 samples. Under honest re-assessment (forward_walk), 0/8 zones clear E>0.
- **Recommendation:** This confirms the F-036 finding (ΔG001≡0) — the zone gate is non-pivotal. No economic case exists for retraining or tuning the zone registry without first resolving the F-022 label contamination.

### Finding 4 (CRITICAL) — Labels Are F-022 Contaminated
- **Severity:** HIGH
- **Location:** Zone discovery pipeline (historical, not in current code)
- **Impact:** The zones were discovered using raw `rr_achieved` labels from the F-022 contaminated stream (no forward_walk, intrabar_fixed SL≈0.66 vs reported ~0.02). The ~98% SL-hit rate across most zones is an artifact of label contamination, not market reality.
- **Recommendation:** Zone re-discovery is not warranted (ΔG001≡0), but if attempted in the future, MUST use forward_walk-derived labels from the clean label pipeline.

### Finding 5 (AUTHORITATIVE) — Black-Box External Similarity Module
- **Severity:** MEDIUM (governance)
- **Location:** `src/engines/live_engine.py:352` imports `bitnet.zone_cosine_searcher.compute_gaussian_score`
- **Impact:** The core per-zone similarity computation is delegated to `bitnet.zone_cosine_searcher.compute_gaussian_score()`, an external module not in this repository's source tree. The ZoneGate code handles schema validation, vector extraction, cluster aggregation, and thresholding, but the actual Gaussian similarity formula is opaque.
- **Recommendation:** Either (a) vendor the bitnet module into the repo so the similarity formula is auditable, or (b) document the exact formula contract expected from `compute_gaussian_score()` so the dependency is pinned to a known mathematical interface.

### Finding 6 (MINOR) — Direction Is Binary (1/0), Never -1
- **Severity:** LOW
- **Location:** `engine_runner.py:711` — `"direction": 1 if zone_raw.get("passed") else 0`
- **Impact:** ZoneGate never expresses a SHORT direction. It's a quality gate that votes LONG or stays neutral. FusionEngine's conflict detection will never register a directional conflict from ZoneGate.
- **Recommendation:** No change needed — this is architecturally correct for a quality gate. Documented for clarity.

### Finding 7 (GHOST) — `scoring_engine.py` Zone Import Guard is Dead Code
- **Severity:** LOW
- **Location:** `src/engines/scoring_engine.py:64-93` (also identified in GAUSSIAN_AUDIT Finding 1)
- **Impact:** Identified in the Gaussian audit as the `compute_gaussian_score` ghost. This function has an import guard against `bitnet.zone_cosine_searcher` and would use it if importable. Zero call sites anywhere in the codebase.
- **Recommendation:** Remove or archive. This is the same dead function identified in the Gaussian audit.

### Finding 8 (AUTHORITATIVE) — ΔG001≡0 Confirmed: Gate Is Non-Pivotal
- **Severity:** INFORMATIONAL (finding, not a bug)
- **Location:** `active_models.yaml` F-036 evidence
- **Impact:** The zone gate, whether passing or blocking, does not change fusion outcomes (ΔG001≡0). It is "redundant/decision-dominated, not weak/underweighted" — meaning FusionEngine's other three engines already dominate the fused score to the extent that ZoneGate's contribution is non-binding. This is consistent with the 0.20 fusion weight and the fact that all 4 engines typically produce scores in similar ranges.
- **Recommendation:** The gate is architecturally "correct" (it executes and passes valid data) but economically inert. No retuning or retraining is warranted. If fusion weights change in the future, re-evaluate ΔG001.

---

## 9. Summary

| Category | Status |
|---|---|
| **Input Contract** | ✅ Consumes 38-dim canonical vector via name-anchored contract. Does NOT consume CRT state, Gaussian score, or OHLCV directly. |
| **Similarity Computation** | ⚠️ 8 Gaussian zones with hand-specified weight masks (not learned). Identical sigma across all zones. Core per-zone similarity is a black-box external dependency (`bitnet.zone_cosine_searcher`). |
| **Historical Authority** | ❌ Zones are historically derived (140K samples) but labels are F-022 contaminated. 0/8 zones clear honest E>0. Gate has ΔG001≡0 — non-pivotal. |
| **Output Contract** | ✅ Score [0,1] + pass/fail + best zone metadata. Direction is binary (1/0), never -1. |
| **Ownership Boundaries** | ✅ All boundaries respected. Fail-closed on vector misalignment is the most important boundary. |
| **Causal Correctness** | ✅ No future leakage. Static artifact, name-anchored extraction, spread filter prevents unstable clusters. |
| **Production Authority** | ✅ Single authoritative path: `EngineRunner.run()` → `score_zone_cluster()` → `run_zone_gate_engine()` → `BitNetZoneGate.check()` → external `bitnet.zone_cosine_searcher` |
| **Implementation Drift** | See below |

### Drift Classifications

| Component | Classification |
|---|---|
| `zone_gate_engine.py` (run_zone_gate_engine, _extract_vector) | **MATCH** |
| `zone_cluster_score.py` (score_zone_cluster) | **MATCH** |
| `live_engine.py` BitNetZoneGate | **MATCH** |
| `zone_gate_engine.py:_compute_soft_zone_score` | **DORMANT** — not active in production (zone_mode="hard") |
| `scoring_engine.py` compute_gaussian_score ghost path | **GHOST** — zero call sites, same dead function as GAUSSIAN audit Finding 1 |
| Zone registry weights | **ARCHITECTURAL NOTE** — hand-specified mask, not learned importance |

### Key Recommendations

1. **Document the black-box dependency** on `bitnet.zone_cosine_searcher.compute_gaussian_score()`. The per-zone similarity formula is not auditable from this repo alone.
2. **No re-training warranted.** ΔG001≡0 means the gate is non-pivotal. Even if it were pivotal, 0/8 zones have positive expectation under honest labels (F-022 contamination).
3. **Remove the ghost path** in `scoring_engine.py:64-93` (already recommended in the Gaussian audit).
4. **Document the hand-specified weight mask** as intentional architecture, not a model output.
5. **No action needed on causal correctness or ownership boundaries** — both are clean.
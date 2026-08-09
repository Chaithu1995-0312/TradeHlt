# Implementation Details — IC-001 Closure + IC-002… Roadmap

> Companion to [`erp-ic001-closure-and-ic-roadmap.md`](erp-ic001-closure-and-ic-roadmap.md).  
> This file is the **how**: files, schemas, functions, gates, and order of work.  
> **Authority:** research/docs only unless a step explicitly says otherwise.  
> **Date:** 2026-07-17

---

## 0. Repository surfaces you will touch

| Layer | Path | Role |
|-------|------|------|
| IC boundary (living) | `docs/research-readiness/erp-information-class-boundary.{md,json}` | COMPLETE / OPEN registry |
| Plan | `docs/implementation_plan/erp-ic001-closure-and-ic-roadmap.md` | Strategy |
| **This file** | `docs/implementation_plan/erp-ic001-implementation-details.md` | Build steps |
| XAUUSD corpus | `results/research/trace_corpus/xauusd/` | IC-001 evidence (gitignored) |
| Feature math | `src/features/feature_pipeline.py` · `feature_schema.py` · registry | OHLCV → 38-dim |
| Path geometry | `src/research/measurement/forward_walk.py` · `exit_grid.py` | MFE/MAE / R paths |
| H-RR study | `scripts/research/h_rr_threshold_001.py` · prereg under `docs/research-readiness/` | R thresholds (≠ IC-001) |
| RR contracts | `decision_engine.py` · `live_engine_hook.py` · `rr_engine.py` | A/B/C/D already split |

**Do not touch for IC work:** production fusion weights, `rr_fusion.enabled`, CRT `VALID_TRANSITIONS`, new engines under `src/engines/`.

---

## Phase 1 — IC-001 documentation fence (no research runner)

### 1.1 New file: IC-001 closure chapter

**Create:** `docs/research-readiness/ic-001-xauusd-static-entry-closure.md`

**Required sections (copy structure):**

```markdown
# IC-001 — XAUUSD Static Entry Mathematics (CLOSED)

> DESCRIPTIVE / RESEARCH_ONLY · Information Class COMPLETE on this corpus

## Canonical statement
[exact wording from plan §1.1]

## Corpus pin
- instrument, path, n traces, n scored, families, date range
- pointer: results/research/trace_corpus/xauusd/

## Attack matrix
| Attack | Artifact | Result summary |

## Permanent teaching example
→ link dual-read doc

## Engine characterization table
CRT / Gaussian / Zone / RR / Fusion

## Forbidden re-openings
(list models on same 38 static dims)

## Next chapter
IC-002 / RC-005 only
```

**Attack matrix rows (fill from existing artifacts):**

| Attack | File(s) under `results/research/trace_corpus/xauusd/` |
|--------|------------------------------------------------------|
| Distributions | `DISTRIBUTIONS.md`, `distributions.json` |
| Engines | `ENGINE_EVALUATION.md` |
| Family cal | `FAMILY_CALIBRATION.md` |
| Near-miss | `NEAR_MISS_PROFILE.md`, `near_miss_profile.json` |
| Clusters | `geometry/CLUSTERS.md` |
| Library | `REPRESENTATIVE_LIBRARY.md`, `representative_exemplars.jsonl` |
| Robustness X/V/R/P | `ROBUSTNESS_XVRP.md` |
| Time-series CV | `TIME_SERIES_CV_X.md` |
| Enriched corpus | `trace_corpus_enriched.jsonl` |

**Acceptance:** a cold LLM session that reads only this file + boundary JSON will state IC-001 COMPLETE and refuse “train another classifier on entry features.”

---

### 1.2 New file: Dual-Read Bar 78 teaching card

**Create:** `docs/research-readiness/erp-teaching-dual-read-bar78.md`

**Content skeleton:**

```markdown
# ERP Teaching Example — Dual-Read Bar 78

## One-line lesson
Entry-time mathematics restates morphology; it does not adjudicate direction/family forks.

## Table
| | expansion_breakout_000007 | mean_reversion_000012 |
| trade_id, entry_index=78, timestamp, price, features, engines, direction, outcome |

## How to use
- Opening slide for IC-001
- LLM eval: "explain why engines cannot separate these"
- Regression: exemplar pair must remain in representative library

## Links
REPRESENTATIVE_LIBRARY.md #1 #4
representative_exemplars.jsonl categories typical_tp + dual_read
```

**Code check (no change required if already present):**

```text
representative_exemplars.jsonl
  trade_id == expansion_breakout_000007 → tags include dual_read_bar_78
  trade_id == mean_reversion_000012     → category == dual_read
```

**Optional test** `tests/research/test_erp_teaching_dual_read.py` (lightweight):

```python
def test_dual_read_bar78_pair_present():
    rows = load_exemplars()
    a = by_id(rows, "expansion_breakout_000007")
    b = by_id(rows, "mean_reversion_000012")
    assert a["entry_index"] == b["entry_index"] == 78
    assert a["outcome"] == "TP_HIT" and b["outcome"] == "SL_HIT"
    assert a["direction"] != b["direction"]
    # same engine vector within float tol
    for k in ("engine_crt_score", "engine_gaussian_score", "engine_zone_score", "engine_rr_score"):
        assert abs(a[k] - b[k]) < 1e-6
```

---

### 1.3 Update boundary registry (MD + JSON together)

**Edit:** `docs/research-readiness/erp-information-class-boundary.md`  
**Edit:** `docs/research-readiness/erp-information-class-boundary.json`

**JSON additions (conceptual patch):**

```json
{
  "measured_boundary": {
    "ic_id": "IC-001",
    "status": "COMPLETE",
    "statement": "Within Information Class IC-001 ...",
    "teaching_example": "docs/research-readiness/erp-teaching-dual-read-bar78.md",
    "closure_doc": "docs/research-readiness/ic-001-xauusd-static-entry-closure.md",
    "measured_surfaces": [
      "...existing...",
      "engine descriptive evaluation + family calibration",
      "near-miss SL path profile",
      "non-linear OOF (GBT) + time-series CV",
      "continuous R calibration + permutation tests",
      "representative library (incl. dual-read bar 78)"
    ]
  },
  "ic_alias_map": {
    "IC-001": "measured_boundary",
    "IC-002": "RC-005",
    "IC-003": "RC-005_extension_shape_library",
    "IC-004": "IC-004_cross_instrument",
    "IC-005": "RC-007"
  },
  "hard_guardrail": "Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.",
  "open_information_classes": [
    { "id": "RC-005", "ic_alias": "IC-002", "next": true, "...": "..." }
  ]
}
```

**MD:** mirror the same under “Measured boundary” + “IC alias map” + guardrail quote box.

---

### 1.4 Library UX (small)

**Edit:** `results/research/trace_corpus/xauusd/REPRESENTATIVE_LIBRARY.md` (gitignored — regenerate via script if preferred)

Add at top after “How to use”:

```markdown
## Teaching openers (start here)
1. Dual-Read Bar 78 — #1 vs #4 (same vector, opposite outcome)
2. High-agreement block — #10–#13 (agreement ≠ skill)
```

If library is only in `results/`, also mirror a **short** dual-read section into the teaching doc under `docs/` (docs are versioned; results may not be).

---

### 1.5 Phase 1 definition of done

- [ ] Closure MD exists with canonical statement  
- [ ] Dual-read teaching MD exists  
- [ ] Boundary MD+JSON: `IC-001` COMPLETE + aliases + guardrail  
- [ ] Optional dual-read regression test green  
- [ ] SESSION LOG entry  

**Still no:** new Python research pipeline for trajectories.

---

## Phase 2 — IC-002 Entry Evolution (design + implement later)

### 2.1 What is new (information class)

| IC-001 | IC-002 |
|--------|--------|
| One 38-vector at **entry bar** | Sequence of vectors / derived path over **bars after entry** |
| “Does snapshot rank outcome?” | “Does **trajectory shape** separate outcomes?” |

If you only re-score t=0 with XGBoost → **you reopened IC-001**. Reject that PR.

---

### 2.2 Data contract

#### Input population

Reuse frozen XAUUSD trade entries from enriched corpus:

```text
source: results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl
keys:   trade_id, family, direction, entry_index, entry_timestamp,
        outcome, rr_achieved, mfe, mae, duration_candles,
        feature_* (t=0 snapshot, optional baseline)
OHLCV:  data/mt5/XAUUSD_M15.csv  OR  data/XAUUSD_M15.csv (pin which exists)
```

**Pin at run:** sha256 of OHLCV + entry list in `results/research/ic_002/manifest.json`.

#### Trajectory object (proposed)

```python
@dataclass(frozen=True)
class EntryTrajectory:
    trade_id: str
    family: str
    direction: str          # long | short
    entry_index: int
    outcome: str
    rr_achieved: float
    N: int                  # horizon bars
    # shape (N, D) — D = len(TRAJECTORY_FEATURE_IDS)
    X: tuple[tuple[float, ...], ...]
    # path economics (from forward_walk or bar path)
    mfe_r_path: tuple[float, ...]   # optional length N
    mae_r_path: tuple[float, ...]
    # provenance
    feature_ids: tuple[str, ...]
    pit_ok: bool
```

#### Frozen horizons (closed set — from plan)

```text
N ∈ {4, 8, 16}   # bars after entry; no other N without new prereg
```

#### Feature subset for trajectories (closed set)

Do **not** dump all 38 if some are non-PIT or level-dominated. Pre-register a **morphology-first** subset, e.g.:

```text
TRAJECTORY_FEATURE_IDS = [
  body_ratio, disp_strength, retest_depth, rsi_14,
  atr, volatility_ratio, volume_ratio,
  trend_bias, momentum_score,  # if PIT-safe on causal pipeline
  # exclude absolute OHLC levels open/high/low/close unless z-scored path-relative
]
```

**Path-relative transform (recommended):**

```text
For each dim d at lag k=1..N:
  z[k,d] = (x[entry+k,d] - x[entry,d]) / scale_d
  # or pure delta; freeze one definition in prereg
```

Absolute price levels must not dominate clusters (same lesson as geometry.md).

---

### 2.3 Computation pipeline (modules)

**New package (suggested):**

```text
src/research/ic002_entry_evolution/
  __init__.py
  schema.py          # EntryTrajectory, TRAJECTORY_FEATURE_IDS, N_GRID
  build_trajectories.py
  cluster_paths.py
  evaluate_separation.py
  io.py              # jsonl read/write
```

**New script (thin CLI):**

```text
scripts/research/ic002_build_trajectories.py
scripts/research/ic002_evaluate.py
```

#### Algorithm: `build_trajectories`

```text
1. Load OHLCV → DataFrame with chronological index
2. FeaturePipeline(df).run() → enriched_df aligned to bar index
   # MUST be causal / PIT; same rules as production research
3. For each trade in enriched corpus with valid entry_index:
     if entry_index + N >= len(df): skip
     X = []
     for k in 1..N:
        row = enriched_df.iloc[entry_index + k]
        X.append([row[f] for f in TRAJECTORY_FEATURE_IDS])
     apply path-relative transform vs entry bar row
     attach outcome labels from corpus
4. Write results/research/ic_002/trajectories_N{N}.jsonl
   + trajectories_N{N}.npz (optional, for clustering)
```

**Performance note:** Do **not** call `FeaturePipeline` per trade. Run **once** per instrument series, then slice rows — same lesson as H-RR harvest slowness (70k × detect).

#### Algorithm: path economics (optional joint object)

Reuse existing:

```python
from research.measurement.forward_walk import forward_walk, horizon_excursion
from research.exit_grid import Entry, net_rr
```

For each trade, can attach `mfe_r`, `mae_r` paths without inventing new exit math.

#### Algorithm: `cluster_paths` (descriptive)

```text
Flatten X → vector length N*D
  or use DTW / PCA-then-kmeans (freeze one in prereg)
k ∈ {4, 6, 8} closed silhouette pick (like geometry k=4)
Report:
  - cluster size
  - outcome mix (SL/TP/TIMEOUT %)  # expect ~uniform if null
  - mean path of body_ratio / MFE under each cluster
```

#### Algorithm: `evaluate_separation` (gates)

Pre-register metrics **before** run:

| Metric | Null expectation |
|--------|------------------|
| Cluster outcome entropy vs global | ≈ global if no path info |
| AUC of “path embedding → TP” with **time-series OOF** | ≈ 0.50 |
| Δ vs IC-001 static baseline embedding | path must beat static if claiming new IC value |

**Static baseline control (mandatory):**  
For each trade, repeat the model using only **repeated t=0 vector** N times (or single snapshot). If path model ≈ static model → **no new information class value**.

---

### 2.4 IC-002 preregistration (before any measure)

**Create (before code lands):**

```text
docs/research-readiness/h-ic002-entry-evolution-preregistration.md
docs/research-readiness/h-ic002-entry-evolution-experiment-definition.json
```

**Must freeze:**

- N grid, feature ids, path-relative formula  
- clustering method + k set  
- OOS scheme (time-ordered)  
- static baseline control  
- verdict vocabulary: INSUFFICIENT / REJECT / RESEARCH_SUPPORTIVE / …  
- **STOP after one primary run**  
- Authority: RESEARCH_ONLY  

**Forbidden in same prereg:** trailing exits, engine reweight, full 38-level features without justification.

---

### 2.5 IC-002 definition of done (measurement)

- [ ] Prereg frozen  
- [ ] One-pass FeaturePipeline build  
- [ ] `trajectories_N*.jsonl` + manifest sha  
- [ ] Cluster report + static baseline comparison  
- [ ] Time-series OOF discrimination table  
- [ ] REPORT.md with authority banner  
- [ ] Boundary RC-005 status update (MEASURED / still OPEN if null)  

---

## Phase 3 — IC-003 Shape library (after IC-002)

### 3.1 Object

```text
Shape = prototype trajectory (centroid or medoid path)
ShapeLibrary = { shape_id → prototype, membership, outcome mix, exemplars }
```

### 3.2 Implementation sketch

```text
src/research/ic003_shapes/
  library.py       # build from IC-002 trajectories
  representatives.py
scripts/research/ic003_build_shape_library.py
results/research/ic_003/
  SHAPE_LIBRARY.md
  shapes.json
  representative_shapes.jsonl
```

### 3.3 Stories

```text
docs only: shape_id → human narrative
NEVER: narrative → invent shape or filter without prereg
```

---

## Phase 4 — IC-004 Cross-instrument

### 4.1 Minimal replication battery (descriptive)

For each instrument in closed set `{EURUSD, BTCUSDT, …}`:

| Step | Reuse |
|------|--------|
| Trace corpus build | same scripts as XAUUSD enrichment |
| Distributions + engines | same probes |
| Dual-read style check | same-bar opposite family if data allows |
| Closure sentence | per-instrument IC-001 status |

**Do not** require IC-002 first.  
**Do** keep separate artifact roots:

```text
results/research/trace_corpus/{instrument}/
```

---

## Phase 5 — IC-005 / H-RR integration

### 5.1 H-RR-THRESHOLD-001 (already coded)

| Piece | Location |
|-------|----------|
| Prereg | `docs/research-readiness/h-rr-threshold-001-*.md/json` |
| Runner | `scripts/research/h_rr_threshold_001.py` |
| Output | `results/research/h_rr_threshold_001/` |

**Known implementation issue:** harvest loops every bar with hypothesis `detect` — **very slow** on 70k×4×2.  

**Lean restart options (if killed):**

1. Progress prints after each instrument/family (already partially there — move print earlier).  
2. Cache entries to `entries.jsonl` after first harvest; skip detect on re-run.  
3. Optional: subsample instruments for smoke test (requires prereg amendment if not primary).

### 5.2 How to read results into ERP

```text
if Arm B all E_oos < 0:
    → consistent F-025; IC-005 "fixed R exit" not alpha on this entry stream
if Arm A admit_rate(min_rr=1.5) << 1:
    → documents D-wiring honesty (planned TP1 vs Ultron floor)
NEVER:
    → "IC-001 failed so we found edge by changing TP"
```

### 5.3 Production config path (only if PROMOTE_RESEARCH + human)

```text
configs/production/v2_multi_2026_04.json
  ultron_risk_gate.min_rr_ratio
  crt_engine.tp1_atr_multiplier*
→ rehash + promote_manager  (governance)
NOT research scripts writing ACTIVE_VERSION
```

---

## Phase 0 — H-RR job (ops detail)

| Check | Command / path |
|-------|----------------|
| Process alive? | Task PID from runner / `Get-Process python` |
| Log | session `terminal/call-…h_rr_threshold_001….log` |
| Done? | `Test-Path results/research/h_rr_threshold_001/REPORT.md` |
| If stuck &gt; 2h in harvest | Kill; add entry cache; re-run |

---

## Shared engineering rules (all IC phases)

### Performance

| Bad | Good |
|-----|------|
| FeaturePipeline per trade | One pipeline run per series |
| Hypothesis detect every bar without progress | Log every instrument/family; cache entries |
| Shuffle CV for claims | Time-ordered OOS / expanding window |

### PIT / no lookahead

- Trajectory features at bar `t` may only use data ≤ `t`  
- Centered swings: obey FC1-A / F-051 policy already in pipeline  
- `forward_walk` future slice starts at `entry_index+1` only  

### Tests to add (by phase)

| Phase | Test |
|-------|------|
| 1 | Dual-read pair present + opposite outcomes |
| 2 | Trajectory builder: length N; no NaN; entry_index+N in bounds; static baseline runs |
| 2 | PIT smoke: last bar of trajectory doesn’t use future close (unit with synthetic series) |
| 5 | H-RR grid equals prereg JSON (no CLI override) — already intended |

### Authority banners (every artifact)

```text
> DESCRIPTIVE / RESEARCH_ONLY — information not authority (§6.5)
> IC-00X — not a production promote
```

---

## Suggested execution order (concrete checklist)

```text
[ ] Phase 1.1  ic-001-xauusd-static-entry-closure.md
[ ] Phase 1.2  erp-teaching-dual-read-bar78.md
[ ] Phase 1.3  erp-information-class-boundary.md + .json
[ ] Phase 1.4  library teaching openers (docs-side at minimum)
[ ] Phase 1.5  optional test_erp_teaching_dual_read.py
[ ] Phase 0    H-RR REPORT.md appears → 1-paragraph fold into IC-001 related / IC-005
[ ] Phase 2.0  h-ic002-*-preregistration.md + json  (STOP for user Run grant)
[ ] Phase 2.1  src/research/ic002_entry_evolution/* + scripts
[ ] Phase 2.2  run once → results/research/ic_002/
[ ] Phase 3+   only after IC-002 measured
```

---

## What “implement IC-002” means in PRs (when granted)

| PR | Contents | Behavior change? |
|----|----------|------------------|
| PR-A | Prereg MD+JSON only | No |
| PR-B | `ic002_entry_evolution` package + build script + tests | No prod |
| PR-C | Evaluation script + REPORT (results gitignored) | No prod |
| PR-D | Boundary RC-005 status update | Docs only |

Never combine “new engine” with IC-002 PRs.

---

## Quick reference — canonical statement

> Within Information Class IC-001 (static entry-time OHLCV-derived information), no practically useful outcome discrimination was observed on the certified XAUUSD corpus under the evaluated research conditions.

## Quick reference — guardrail

> Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.

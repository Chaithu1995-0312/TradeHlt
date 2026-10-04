# H-IC003 — Shape Library (trajectory prototypes)

> **PRE-REGISTERED before any outcome measurement on this protocol.**  
> Status: **ARCHIVED · MEASURED · RESEARCH_ONLY**  
> **Authoritative result: v1 LIBRARY_FAIL** (G1 max = **0.85**)  
> Date: 2026-07-17  
> See [`ic-003-lessons-learned.md`](ic-003-lessons-learned.md) — A1 demoted (not scientific authority)

| Field | Value |
|-------|--------|
| Program alias | **H-IC003-001** |
| Registry / IC | **IC-003** (depends on **RC-005 / IC-002**) |
| Title | TRAJECTORY_SHAPE_LIBRARY_FROM_IC002_PATHS |
| Task class | `EXPLORATORY_RESEARCH` |
| Authority | **RESEARCH_ONLY** (§6.5) |
| Production / CRT / fusion / engines | **NO / FORBIDDEN** |
| IC-001 static re-open | **FORBIDDEN** |
| Parent | IC-002 MEASURED — [`h-ic002-entry-evolution-preregistration.md`](h-ic002-entry-evolution-preregistration.md) · `results/research/ic_002/` |
| Boundary | [`erp-information-class-boundary.md`](erp-information-class-boundary.md) |

Machine twin: [`h-ic003-shape-library-experiment-definition.json`](h-ic003-shape-library-experiment-definition.json)

---

## 1. Why this study exists

**IC-001** closed static entry-time discrimination on XAUUSD.  
**IC-002** showed that **post-entry path embeddings** separate outcomes better than the static snapshot under pre-registered gates (N=4, N=16 RESEARCH_SUPPORTIVE), with the critical caveat that path features **co-evolve** with the realized trade path under fixed exits — **not** an entry-time tradable signal.

**IC-003** asks the next OHLCV-mathematical question:

> Can the continuum of post-entry trajectories be compressed into a **finite library of mathematical shapes** (prototypes) that are stable, inspectable, and useful as a **descriptive ontology** — with stories attached *after* shapes, never before?

```text
OHLCV → features → entry snapshot     [IC-001 COMPLETE]
                 → post-entry path    [IC-002 MEASURED]
                 → shape library      [IC-003 THIS]
                 → narratives (docs)  [documentation only]
```

### Hard rejection of fake “new research”

| Proposal | Verdict |
|----------|---------|
| Cluster **entry-bar** 38-vectors again | **REJECT** — IC-001 / F-023 class |
| Use shape IDs as live entry filters without new prereg + OOS expectancy gate | **REJECT** |
| New engines / fusion / rr_fusion | **REJECT** |
| KMeans/medoids on **IC-002 path tensors** + representative library | **IN SCOPE** |

---

## 2. Hypotheses (frozen)

### Primary (descriptive geometry)

**H_G:** On frozen IC-002 trajectories (primary N∈{4,16}), a pre-registered clustering procedure yields a **finite set of prototypes** such that:

1. Within-cluster path variance is materially lower than global (compact shapes), and  
2. Prototypes are **stable under IS→OOS assignment** (OOS points map to the same prototype set without re-fitting centroids on OOS), and  
3. A human/LLM-readable **representative set** (nearest-to-centroid exemplars) can be published.

**H_G0:** No compact/stable prototype set under the frozen k-grid and validation (shapes collapse to noise / unstable labels).

### Secondary (outcome mix — diagnostic only)

**H_O:** Some shapes show outcome mix **materially different** from the global base rate on OOS (descriptive purity).  

**H_O is never sufficient for production authority.** Even a pure shape is concurrent path description unless a **separate** prereg proves *ex-ante* shape membership from information available **at or before entry** (out of scope for IC-003).

### Explicit non-hypothesis

IC-003 does **not** claim: “trading the shape improves expectancy.” That would require a new program (IC-005-class or new entry IC) with admission-time features only.

---

## 3. Population & inputs (frozen)

| Item | Value |
|------|--------|
| Instrument | XAUUSD M15 (same as IC-002) |
| Trajectory source | `results/research/ic_002/trajectories_N{N}.npz` + `_meta.jsonl` |
| **Primary N** | **{4, 16}** (IC-002 RESEARCH_SUPPORTIVE cells) |
| **Diagnostic N** | **{8}** (IC-002 REJECT on shuffle-gap — report shapes but **not** primary library) |
| Feature path | Same `TRAJECTORY_FEATURE_IDS` (D=15), path-relative Z as built by IC-002 |
| Labels | From meta: outcome, family, direction, trade_id — for **description only** |
| Rebuild rule | If IC-002 artifacts missing, rebuild via `ic002_build_trajectories.py` then proceed — do not invent a new path formula |

**Pin at run:** sha256 of each `trajectories_N*.npz`, meta line count, git commit, this prereg path → `results/research/ic_003/manifest.json`.

---

## 4. Shape definition (frozen)

### 4.1 Vectorization

```text
Primary: M-FLAT — flatten Z ∈ R^{N×D} → R^{N·D}
Optional diagnostic: PCA to n_components = min(32, N·D) fit on IS only
  (if used, freeze n_components=32; report both FLAT and PCA libraries separately;
   primary claim uses FLAT only)
```

### 4.2 Clustering procedure

| Step | Spec |
|------|------|
| Scale | `StandardScaler` fit on **IS only** |
| Algorithm | **MiniBatchKMeans** (or KMeans if n fits memory), `random_state=42`, `n_init=10` |
| k grid (closed) | **{4, 6, 8, 12}** |
| k selection | Maximize **IS silhouette** on a random IS subsample of max **8,000** points (`seed=42`); lock k before any OOS purity read |
| Prototype | **Centroid** in scaled space; store also **medoid** (IS member nearest centroid) as human exemplar seed |
| Assignment | Each trade → nearest centroid (IS and OOS use **IS-fitted** scaler + centroids only) |

### 4.3 Shape record

```text
Shape:
  shape_id          # e.g. N16_k8_s03
  N, k, method
  centroid          # length N*D (unscale for report optional)
  medoid_trade_id
  n_is, n_oos
  outcome_mix_is / outcome_mix_oos   # diagnostic
  mean_path_key_dims  # mean Z[:,:,d] for d in {body_ratio, disp_strength, rsi_14, atr}
  representative_trade_ids  # top-5 nearest IS + top-3 nearest OOS
```

### 4.4 Library product

```text
results/research/ic_003/
  manifest.json
  shapes_N{N}_k{k}.json
  SHAPE_LIBRARY.md              # human index
  representative_shapes.jsonl   # LLM-consumable exemplars
  assignment_N{N}.jsonl         # trade_id → shape_id (IS/OOS flag)
  report.json / REPORT.md
```

**Stories:** optional `docs/research-readiness/ic-003-shape-narratives.md` written **after** shapes exist — mapping `shape_id → prose`. Narratives **must not** change membership or gates.

---

## 5. Validation & gates

### 5.1 Split

```text
Same time-ordered 70/30 by entry timestamp as IC-002 meta order
  (first 70% IS · last 30% OOS)
Centroids fit on IS only.
```

### 5.2 Geometry gates (primary H_G) — all required for LIBRARY_OK

| Gate | Rule |
|------|------|
| G1 Compactness | Mean IS within-cluster SSE / global SSE ≤ **0.85** (**authoritative v1 bar**; see §11) |
| G2 Separation | IS silhouette (full IS or 8k subsample) ≥ **0.05** (weak but non-zero; k chosen by max silhouette) |
| G3 Stability | Fraction of OOS points whose assigned shape’s **IS medoid path correlation** (Pearson on flat vector) with point path ≥ median IS self-correlation − **0.10** — report metric; require OOS mean centroid-distance z-score ≤ **2.0** vs IS distance distribution per shape (no explosion) |
| G4 Coverage | Every shape has **n_is ≥ 50** and **n_oos ≥ 20** (else merge not allowed — drop k or mark shape UNSTABLE and fail G4 if any shape fails) |
| G5 Inspectability | SHAPE_LIBRARY.md + ≥1 medoid narrative slot per shape (can be stub “TBD prose”) |

**Verdict:**

| Verdict | Meaning |
|---------|---------|
| `INSUFFICIENT` | Missing IC-002 artifacts or n too small |
| `LIBRARY_FAIL` | Fails G1–G5 |
| `LIBRARY_OK` | Passes G1–G5 — shapes are a valid descriptive library |
| `PURITY_NOTE` | Optional flag if any shape has OOS TP-rate outside global ± **10 pp** with n_oos≥50 (diagnostic only) |

**No expectancy / PF / promotion gates in IC-003.**  
`LIBRARY_OK` + `PURITY_NOTE` ≠ production authority.

### 5.3 Explicitly not gates

- AUC of shape_id → outcome (tempting; deferred — would re-litigate concurrent path skill)  
- Beating IC-002 path logistic (wrong object)  
- Silhouette maximization over free k outside {4,6,8,12}  

---

## 6. Priors (E-001 — before the run)

1. **F-023 / IC-001 geometry:** entry morphology clusters separate shape not expectancy — expect similar for **path** shapes unless purity appears.  
2. **IC-002:** path carries concurrent outcome association — pure shapes may appear; treat as **description of failure/success paths**, not entry signals.  
3. **Dual-read Bar 78:** direction/family still not resolved by candle snapshot; shapes after entry describe **what unfolded**, not which side to take at t=0.  

---

## 7. Out of scope

- Entry-time shape prediction (would need features ≤ entry only — new IC)  
- Trailing/partial/time exits as treatments  
- Cross-instrument shapes (→ IC-004 after library exists)  
- Free feature/N redesign  
- LLM stories that invent extra shapes not in the library  

---

## 8. Implementation map (when Implement/Run granted)

| Component | Location |
|-----------|----------|
| Package | `src/research/ic003_shapes/` |
| Build | `scripts/research/ic003_build_shape_library.py` |
| Inputs | `results/research/ic_002/trajectories_N{4,16}.npz` (+ optional N=8 diagnostic) |
| Outputs | `results/research/ic_003/` |
| Reuse | IC-002 `load_batch`, same seeds |

**Algorithm sketch:**

```text
for N in {4, 16}:
  load Z, meta
  time-split IS/OOS
  for k in {4,6,8,12}:
    fit scaler+KMeans on IS → silhouette
  lock k*
  fit final KMeans(k*) on IS
  assign all → build Shape records
  evaluate G1–G5
  write library + representatives
diagnostic: repeat for N=8, label DIAGNOSTIC
```

---

## 9. Status

| Item | State |
|------|--------|
| Design frozen | **YES** |
| Code | **YES** — `src/research/ic003_shapes/` |
| Run | **YES** — `results/research/ic_003/REPORT.md` |
| Finding | optional; **archive = LIBRARY_FAIL (v1)** |

**Authoritative archive:** v1 LIBRARY_FAIL (N=4 G1 0.873>0.85; N=16 G1+G2).  
**A1** (G1→0.90) executed then **SUPERSEDED as authority** — see lessons learned. Code defaults restored to G1=0.85.

---

## 11. Amendment A1 — executed then SUPERSEDED as scientific authority

**History:** User briefly authorized G1 0.85→0.90 and re-run after N=4 near-miss (0.873).

**ERP integrity decision (same day):** Post-hoc gate relaxation because a result was “close” is the failure mode preregistration exists to prevent. **Authoritative result remains v1 LIBRARY_FAIL.**

| Item | v1 (authoritative) | A1 (non-authoritative) |
|------|--------------------|-------------------------|
| G1 max | **0.85** | 0.90 (historical only) |
| Scientific archive | **LIBRARY_FAIL** | PARTIAL sensitivity — not success |

**Future work:** If representation changes (DTW, sequence kernels, multi-scale, etc.), open **IC-003B** as a **new prereg**, do not re-amend G1 on the same design.

**Still forbidden:** production filters on shape_id; expectancy promote from purity; silent gate moves.

**Lessons:** [`ic-003-lessons-learned.md`](ic-003-lessons-learned.md)

---

## 10. Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Initial open prereg after IC-002 measure |
| v1 first run | 2026-07-17 | **AUTHORITATIVE LIBRARY_FAIL** (N=4 G1 0.873; N=16 G1+G2) |
| A1 | 2026-07-17 | G1→0.90 re-run executed; **SUPERSEDED as authority** same day |
| archive | 2026-07-17 | Lessons learned; restore G1=0.85 as frozen bar |

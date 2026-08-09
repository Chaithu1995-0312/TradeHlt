# H-IC003B — Sequence Geometry Shape Library (new representation)

> **PRE-REGISTERED before any outcome measurement on this protocol.**  
> Status: **OPEN · EXPLORATORY_RESEARCH · RESEARCH_ONLY · NOT RUN**  
> Date: 2026-07-17  
> User grant: **design IC-003B**

| Field | Value |
|-------|--------|
| Program alias | **H-IC003B-001** |
| Registry / IC | **IC-003B** (successor design to archived **IC-003**, not an amendment) |
| Title | SEQUENCE_GEOMETRY_SHAPE_LIBRARY |
| Task class | `EXPLORATORY_RESEARCH` |
| Authority | **RESEARCH_ONLY** (§6.5) |
| Production / engines / fusion | **FORBIDDEN** |
| Parent archive | IC-003 v1 **LIBRARY_FAIL** — [`ic-003-lessons-learned.md`](ic-003-lessons-learned.md) |
| Depends on | IC-002 trajectories `results/research/ic_002/` |
| Boundary | [`erp-information-class-boundary.md`](erp-information-class-boundary.md) |

Machine twin: [`h-ic003b-sequence-geometry-experiment-definition.json`](h-ic003b-sequence-geometry-experiment-definition.json)

---

## 1. Why IC-003B exists (not “IC-003 with looser G1”)

**IC-003 (archived)** asked:

> Can trajectories form a stable prototype library under **M-FLAT + Euclidean KMeans + G1–G5 (G1≤0.85)**?

**Answer:** **LIBRARY_FAIL** — authoritative. N=4 failed G1 at sse_ratio 0.873; N=16 failed G2 (silhouette ≈0.02).

**IC-003B** does **not** move that gate. It asks a **different design question** from the lessons note:

> Under **sequence-preserving representations** (and an explicit continuum diagnostic), can paths form a compact, stable, inspectable prototype library — and/or is the manifold better described as continuous?

```text
IC-003  = Euclidean geometry on flattened paths     → FAIL (archived)
IC-003B = sequence summaries + DTW medoids + continuum diagnostic
```

### Explicit non-goals

| Forbidden | Why |
|-----------|-----|
| G1 0.85→0.90 (or any post-hoc gate move on IC-003 design) | Already rejected; A1 superseded |
| Re-run IC-003 M-FLAT only and declare success | Same experiment |
| Entry-time filters / production promote | ERP guardrail |
| Reinterpret IC-002 as false | Independent question |

---

## 2. Hypotheses (frozen)

### Arm S — Path summary Euclidean library (PRIMARY library claim)

**H_S:** On frozen IC-002 trajectories (primary N∈{4,16}), clustering **path-summary vectors** (per-dim temporal statistics, not full flatten) yields a library that passes the **same G1–G5 geometry gates as IC-003 v1** (G1 max **0.85**).

**H_S0:** LIBRARY_FAIL under those gates (summaries do not fix prototype collapse).

### Arm T — DTW sequence geometry (SECONDARY library claim)

**H_T:** On a **reduced 3-channel path** (body_ratio, disp_strength, rsi_14 only), **DTW distance + k-medoids** yields a library that passes G1–G5 adapted to DTW space (see §5.2), on N∈{4,16}.

**H_T0:** LIBRARY_FAIL under DTW geometry gates.

### Arm C — Continuum diagnostic (NOT a library verdict)

**H_C (diagnostic):** PCA on (i) M-FLAT and (ii) Arm-S vectors shows that the first **4** components explain **≥ 50%** of IS variance on at least one representation **and** silhouette of KMeans on those 4 PCs stays **&lt; 0.05** for all k∈{4,6,8,12} — supporting a **continuous / weak-prototype** manifold.

**H_C is never LIBRARY_OK.** It only classifies continuum evidence as `CONTINUUM_NOTE` / `DISCRETE_HINT`.

---

## 3. Population & inputs (frozen)

| Item | Value |
|------|--------|
| Source | `results/research/ic_002/trajectories_N{N}.npz` + meta (same pins as IC-003) |
| Primary N | **{4, 16}** |
| Diagnostic N | **{8}** (report only; not primary LIBRARY claim) |
| Features (full path) | IC-002 `TRAJECTORY_FEATURE_IDS` (D=15), path-relative Z |
| DTW channels (Arm T only) | **Exactly** `body_ratio`, `disp_strength`, `rsi_14` (indices in feature_ids) |
| Split | Time-ordered 70/30 IS/OOS by entry meta (identical rule to IC-002/003) |
| Seed | **42** |

If IC-002 artifacts missing → rebuild with `ic002_build_trajectories.py` (no new path formula).

---

## 4. Representations (frozen)

### 4.1 Arm S — path summary vector (PRIMARY)

For each dim \(d=1..D\) over steps \(k=1..N\), compute:

| Stat | Definition |
|------|------------|
| mean | \(\mathrm{mean}_k z_{k,d}\) |
| std | \(\mathrm{std}_k z_{k,d}\) (0 if N=1) |
| first | \(z_{1,d}\) |
| last | \(z_{N,d}\) |
| min | \(\min_k z_{k,d}\) |
| max | \(\max_k z_{k,d}\) |
| slope | \((z_{N,d} - z_{1,d}) / \max(N-1, 1)\) |

**Vector length = 7D = 105.**  
No free stats. No PCA for primary library claim (PCA only in Arm C).

### 4.2 Arm T — DTW on 3-channel path (SECONDARY)

```text
seq_i = Z[i, :, idx_channels]   # shape (N, 3)
distance(i,j) = DTW_euclidean(seq_i, seq_j)
  - window band: Sakoe-Chiba radius r = max(1, floor(0.2 * N))  # frozen
  - implementation: scipy or pure numpy; must be deterministic
```

**Prototype:** k-medoids (PAM) on IS with DTW distance; assign OOS by nearest medoid under DTW.  
**Subsample for k-selection:** if n_IS > 3000, random IS subsample of 3000 (seed=42) for silhouette-on-distance-matrix; final fit on full IS.

### 4.3 Arm C — continuum diagnostic

| Object | Spec |
|--------|------|
| C-FLAT | PCA on M-FLAT (N·D), fit IS only |
| C-SUM | PCA on Arm-S vectors, fit IS only |
| Report | cumulative variance of PCs 1–4; max silhouette of KMeans k∈{4,6,8,12} on PC1–4 scores (IS) |
| CONTINUUM_NOTE | if for **both** C-FLAT and C-SUM: cumvar_4 ≥ 0.50 **and** max_sil &lt; 0.05 |
| DISCRETE_HINT | if for **either**: max_sil ≥ 0.05 on PC1–4 |

---

## 5. Clustering & gates

### 5.1 Arm S — same geometry gates as IC-003 v1 (fair comparison of representation)

| Gate | Rule (identical spirit to IC-003 v1) |
|------|--------------------------------------|
| Algorithm | MiniBatchKMeans, k∈**{4,6,8,12}**, IS silhouette lock, seed=42, n_init=10 |
| Scaler | StandardScaler fit IS only |
| **G1** | within SSE / global SSE ≤ **0.85** |
| **G2** | IS silhouette ≥ **0.05** |
| **G3** | OOS vs IS centroid-distance: robust median/MAD scale; mean z ≤ **2.0** per shape |
| **G4** | every shape n_is≥50, n_oos≥20 |
| **G5** | SHAPE_LIBRARY docs + medoids |

**Verdict Arm S:** `LIBRARY_OK` / `LIBRARY_FAIL` / `INSUFFICIENT` (per N; primary needs both N=4 and N=16 for full multi-N OK; report PARTIAL if only one N OK).

### 5.2 Arm T — DTW-adapted gates

| Gate | Rule |
|------|------|
| **G1_T** | Mean IS within-medoid DTW cost / mean pairwise IS DTW (subsample 500 pairs) ≤ **0.85** |
| **G2_T** | Silhouette on IS using **precomputed DTW** distances ≥ **0.05** (subsample ≤2000 for cost) |
| **G3_T** | Mean OOS DTW-to-assigned-medoid ≤ mean IS DTW-to-medoid + **2** robust scales (MAD) |
| **G4** | same min n as Arm S |
| **G5** | docs + medoid trade_ids |

**Verdict Arm T:** independent `LIBRARY_OK` / `LIBRARY_FAIL` / `INSUFFICIENT`.

### 5.3 What is never a success criterion

- Beating IC-003 by relaxing G1  
- Outcome purity / AUC of shape→TP (diagnostic note only if |tp_oos−global|≥10pp and n_oos≥50)  
- Production filters  

---

## 6. Program-level verdict (frozen)

| Label | Rule |
|-------|------|
| `IC003B_LIBRARY_OK` | Arm S **LIBRARY_OK** on **both** primary N (4 and 16) |
| `IC003B_PARTIAL` | Arm S OK on exactly one primary N **or** Arm T OK on both N while Arm S fails |
| `IC003B_FAIL` | Neither arm delivers multi-N library under gates |
| `CONTINUUM_NOTE` / `DISCRETE_HINT` | From Arm C only (orthogonal flag) |

**IC003B_LIBRARY_OK / PARTIAL still ≠ production authority.**  
Optional narratives only for shapes that passed LIBRARY_OK on their N.

---

## 7. Priors (E-001 — before run)

1. **IC-003 lesson:** M-FLAT Euclidean prototypes failed — expect Arm S may help if flatten was the bug; may still fail if manifold is continuous.  
2. **IC-002:** path information exists; library is about **compression**, not “is there signal.”  
3. **DTW cost:** Arm T is expensive; secondary by design; subsample rules frozen to avoid fishing.  
4. **Continuum prior:** weak silhouettes on long paths suggest CONTINUUM_NOTE is plausible.  

---

## 8. Implementation map (when Implement granted)

| Component | Location |
|-----------|----------|
| Package | `src/research/ic003b_sequence_geometry/` |
| Script | `scripts/research/ic003b_build.py` |
| Outputs | `results/research/ic_003b/` |
| Reuse | `ic002` load_batch; do **not** mutate IC-003 archive paths |

**Suggested modules:**

```text
schema.py          # frozen constants
summarize.py       # Arm S vectorization
dtw.py             # deterministic DTW + sakoe-chiba
cluster_euclid.py  # Arm S library + G1–G5
cluster_dtw.py     # Arm T k-medoids + G*_T
continuum.py       # Arm C PCA diagnostic
report.py          # REPORT.md / SHAPE_LIBRARY.md
```

**Performance rules:**

- One load of Z per N  
- Arm T: distance matrix on IS subsample for k-select; full IS medoids optional if n_IS≤3000 else subsample medoid search  
- No free hyperparameter search beyond frozen grids  

---

## 9. Artifacts on run

```text
results/research/ic_003b/
  manifest.json
  report.json / REPORT.md
  arm_S_N{N}/shapes.json, assignment.jsonl
  arm_T_N{N}/shapes.json, assignment.jsonl
  arm_C_continuum.json
  SHAPE_LIBRARY.md          # only LIBRARY_OK shapes promoted to “library” section
```

IC-003 archive under `results/research/ic_003/` remains **read-only historical**.

---

## 10. Status

| Item | State |
|------|--------|
| Design frozen | **YES** (this document + JSON) |
| Code | **NO** |
| Run | **NO** |
| Finding | **NO** |

**Next step:** user authorizes **`Implement IC-003B`** and/or **`Run H-IC003B-001`**.

---

## 11. Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | New prereg from IC-003 lessons; not a G1 amendment |

# ERP Geometry Compute Doctrine

> **Status:** ACTIVE guidance (2026-07-17) · RESEARCH_ONLY · **not** a production mandate  
> **Trigger observation:** IC-003B Arm T ETA (~3–4h remaining at pause) is a **compute-wall signal**, not only a schedule fact.  
> **Linked run:** [`results/research/ic_003b/`](../../results/research/ic_003b/) · pause note [`NEXT_SESSION_PRIORITY.md`](../../results/research/ic_003b/NEXT_SESSION_PRIORITY.md)

---

## 1. What the ETA actually said

The long pole is **not**:

- feature engineering  
- engines / fusion / OHLCV load  
- LLMs  

It **is**:

```text
Trajectory corpus
        ↓
DTW pairwise distance   ← wall
        ↓
Prototype selection (k-medoids / assignment)
```

IC-003B pipeline shape:

```text
~23k traces
  → trajectory extraction (IC-002, already paid)
  → distance computation (Arm T)
  → geometry / continuum (Arm S, C)
  → representative library
  → (later) shape ontology — research authority only
```

This is closer to **large-scale similarity / pattern mining** than classical backtest loops.

---

## 2. Code-grounded cost model (IC-003B Arm T)

| Parameter | Value | Authority |
|-----------|--------|-----------|
| Full corpus size | ~23,428 trades | `arm_*_N4` assignment line count |
| IS DTW subsample cap | **3000** | `DTW_IS_SUBSAMPLE_MAX` in `schema.py` |
| Pair count (upper triangle) | \(n(n-1)/2 \approx\) **~4.5M** not 9M | `pairwise_dtw` only fills \(i < j\) |
| Sequence length | primary N ∈ {4, 16}; diagnostic 8 | `PRIMARY_N` / `DIAGNOSTIC_N` |
| Band | Sakoe–Chiba `radius = max(1, floor(0.2·N))` | `dtw.py` |
| Per-pair work | \(O(N \cdot radius \cdot C)\), C=3 channels | pure Python nested loops |
| Implementation | Python + NumPy scalar DP; ThreadPool ≤8 | **GIL-bound** — wall ≈ 1 core observed |

Scaling (pairs fixed at ≤3000):

| N | radius | relative per-pair work vs N=4 |
|---|--------|-------------------------------|
| 4 | 1 | 1× |
| 8 | 1 | ~2× |
| 16 | 3 | ~12× |

N=4 Arm T wall ≈ **12–15 min** (measured). N=16 Arm T estimate ≈ **2.5–3.5 h**.  
Partial DTW matrices are **not** checkpointed mid-run (only finished arm artifacts).

---

## 3. GPU: relevant later, not this week

GPU becomes interesting because this is **similarity search at scale**, not because “we are doing AI.”

**Do not rent NVIDIA this week.** Reasons:

1. Current DTW is **Python DP loops** — does not map cleanly to CUDA without a rewritten kernel/backend.  
2. Renting without a profile risks **cost with ~0 speedup**.  
3. Algorithmic reductions (pruning / approx / hierarchical) often beat hardware swaps for this class of problem.

---

## 4. Staged progression (measurement-first)

### Stage 1 — Profile (next compute investment after resume completes or aborts)

Attribute wall time, e.g. target shape:

```text
dtw_euclidean / pairwise_dtw   ??%
assignment to medoids          ??%
k-medoids PAM                  ??%
IO / JSON                      ??%
rest                           ??%
```

If DTW is **70–90%**, optimize **that** surface first.  
Instrument under `src/research/ic003b_sequence_geometry/` only — no production spine.

### Stage 2 — Algorithm before silicon

Prefer order-of-magnitude cuts without new hardware:

```text
Brute-force pairwise DTW
  → LB_Keogh / Keogh lower-bound pruning
  → FastDTW (or banded + constrained variants already partial)
  → approximate nearest neighbours / pivots
  → hierarchical / multi-resolution clustering
```

Any change that alters distances is a **representation / experiment-definition** decision — prereg or diagnostic arm; do **not** silently swap the authoritative Arm T backend mid-run without a labeled protocol.

### Stage 3 — GPU only with evidence

Justify rental when:

- Stage 1 profile shows distance still dominates after Stage 2, **and**  
- a concrete backend (e.g. CUDA DTW / soft-DTW package) has a **measured** speedup on a fixed pin of sequences.

Then: accelerate a **named bottleneck** in the ERP geometry layer — not “AI infra.”

---

## 5. Backend-swappable distance (design intent, not built)

Target shape for later IC-004+ geometry work:

```text
DistanceEngine
    ├── Euclidean          (Arm S path summaries — already cheap)
    ├── DTW (banded)       (current Arm T reference)
    ├── FastDTW
    ├── Soft-DTW
    └── GPU-DTW (future)
```

Rules:

- **Reference backend** stays the preregistered one for a given experiment ID.  
- Swaps require explicit experiment label + pin of IC-002 trajectories.  
- Speed ≠ economic authority (§6.5). Faster geometry still does not grant production filters.

---

## 6. Roadmap implication (IC-004+)

| Earlier ERP | Geometry phase |
|-------------|----------------|
| OHLCV → features → backtest | traces → millions of comparisons → prototypes |
| Throughput = candles / gates | Throughput = pairwise / ANN / library build |
| CPU fine | Must design for **scalable similarity** |

Investment priority remains aligned with ERP process integrity:

1. Finish / archive IC-003B under frozen gates (resume, no G1 loosen).  
2. Profile distance wall.  
3. Algorithmic DistanceEngine path.  
4. GPU only if still binding after (2)+(3).

---

## 7. Explicit non-actions

- No cloud GPU rental from this note alone  
- No production config / shape filters from geometry speedups  
- No silent replacement of Arm T DTW mid IC-003B  
- No claim that “GPU = edge”  

---

## 8. Resume link

Paused run + checkpoints: `results/research/ic_003b/checkpoint.json`  
Resume: `python scripts/research/ic003b_build.py --resume`

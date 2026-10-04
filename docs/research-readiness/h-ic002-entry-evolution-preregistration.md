# H-IC002 / RC-005 — Entry Evolution (post-entry trajectory)

> **PRE-REGISTERED before any outcome measurement on this protocol.**  
> Status: **MEASURED · RESEARCH_ONLY** (first run 2026-07-17)  
> Date: 2026-07-17  
> User grant: **Draft IC-002 prereg** then **Implement IC-002**

| Field | Value |
|-------|--------|
| Program alias | **H-IC002-001** |
| Registry / IC | **RC-005** / **IC-002** |
| Title | ENTRY_EVOLUTION_POST_ENTRY_OHLCV_TRAJECTORY |
| Task class | `EXPLORATORY_RESEARCH` |
| Authority | **RESEARCH_ONLY** (§6.5) |
| Production / CRT / fusion change | **NO** |
| New engines | **FORBIDDEN** |
| Threshold / feature optimization on t=0 | **FORBIDDEN** (IC-001 reopen) |
| Parent chapter | IC-001 COMPLETE — [`ic-001-xauusd-static-entry-closure.md`](ic-001-xauusd-static-entry-closure.md) |
| Boundary | [`erp-information-class-boundary.md`](erp-information-class-boundary.md) |
| Build detail | [`docs/implementation_plan/erp-ic001-implementation-details.md`](../implementation_plan/erp-ic001-implementation-details.md) §Phase 2 |

Machine twin: [`h-ic002-entry-evolution-experiment-definition.json`](h-ic002-entry-evolution-experiment-definition.json)

---

## 1. Why this study exists

**IC-001** established that **static entry-time** OHLCV-derived information (38-dim snapshot, engines, morphology clusters, non-linear OOF, TS-CV) does not practically rank outcomes on the certified XAUUSD corpus.

That does **not** measure whether **how the mathematical state evolves after entry** carries descriptive structure about outcomes. That is a **different information class** (trajectory vs snapshot).

OHLCV-first ERP path:

```text
OHLCV → features → entry snapshot [IC-001 DONE]
                 → post-entry path  [IC-002 THIS]
                 → shape library    [IC-003 later]
```

### Hard rejection of fake “new research”

| Proposal | Verdict |
|----------|---------|
| XGBoost / LSTM on **entry bar only** (same 38 dims) | **REJECT** — IC-001 reopen |
| New fusion weights / engine | **REJECT** — guardrail |
| Path of features over N bars after entry + static baseline control | **IN SCOPE** |

---

## 2. Hypotheses (frozen)

### Primary

**H:** On the frozen XAUUSD entry population, **post-entry OHLCV-derived feature trajectories** of length \(N\) identify structure associated with outcome (TP/SL/TIMEOUT or binary TP) that is **not** available from the static entry snapshot alone.

**H₀:** After time-ordered OOS validation and the pre-registered controls, trajectory-based separation is **not** better than the **static baseline** (and/or remains at chance). IC-002 is then measured-null (chapter may close or open IC-003 only as descriptive shape catalog without expectancy claim).

### Secondary (descriptive only — not primary promote)

**H_S:** Trajectory clusters form stable morphological path families (shape prototypes) with distinct *geometry*, even if outcome mix is near-global (F-023-style).  
Outcome purity is **not** required for H_S; H_S never grants trading authority.

---

## 3. Population (frozen)

| Item | Value |
|------|--------|
| Instrument | **XAUUSD** M15 |
| Entries | All scored rows from `results/research/trace_corpus/xauusd/trace_corpus_enriched.jsonl` with non-null `entry_index` and non-null features (exclude 19 warmup-null) |
| Families | expansion_breakout, mean_reversion, spine (spine n=1 diagnostic only) |
| OHLCV | Pin at run: path + sha256 of the series used to rebuild features (prefer `data/mt5/XAUUSD_M15.csv` if present else `data/XAUUSD_M15.csv`) |
| Eligibility | `entry_index + max(N) < len(series)`; causal FeaturePipeline available for bars ≤ `entry_index + N` |
| Label | Primary binary: `y = 1` if `outcome == TP_HIT` else `0` (TIMEOUT counts as 0). Diagnostic: 3-way outcome mix |

**Entry freeze rule:** trade list is **fixed** from the enriched corpus; no new entry detection inside this program.

**Pin at run start:** write `results/research/ic_002/manifest.json` with entry count, sha256 of entry id list, OHLCV sha256, git commit, this prereg path.

---

## 4. Treatment object — trajectory

### 4.1 Horizons (closed set)

```text
N ∈ {4, 8, 16}   # bars strictly AFTER entry_index
```

No other N without a **new** preregistration.

Bars used: `entry_index + 1, …, entry_index + N` (entry bar itself is **t=0 baseline**, not a trajectory step).

### 4.2 Feature IDs (closed set — morphology / rate, not absolute price)

**Included (`TRAJECTORY_FEATURE_IDS`, order frozen):**

| # | Feature | Rationale |
|---|---------|-----------|
| 1 | `body_ratio` | candle structure |
| 2 | `disp_strength` | displacement geometry |
| 3 | `retest_depth` | retest geometry |
| 4 | `rsi_14` | oscillator state |
| 5 | `atr` | scale (for path-relative norm) |
| 6 | `volatility_ratio` | vol state |
| 7 | `volume_ratio` | relative volume |
| 8 | `trend_bias` | directional bias |
| 9 | `momentum_score` | momentum state |
| 10 | `break_of_structure` | structure event |
| 11 | `higher_high` | structure |
| 12 | `lower_low` | structure |
| 13 | `sweep_detected` | liquidity event |
| 14 | `liquidity_distance` | geometry |
| 15 | `candles_since_retest` | timing state |

**D = 15.**  

**Excluded from path (level / price anchors):**  
`open`, `high`, `low`, `close`, `volume`, `ema_fast`, `ema_slow`, `ema_spread`, `macd_*`, raw `body_size`/`wick_size` (use ratios already).

### 4.3 Path-relative transform (frozen formula)

Let \(x_{0,d}\) = feature \(d\) on the **entry bar**, \(x_{k,d}\) = feature \(d\) on bar `entry_index + k`, \(k=1..N\).

```text
scale_d = max(|x_{0,d}|, ε) with ε = 1e-9
z_{k,d} = (x_{k,d} - x_{0,d}) / scale_d
```

For discrete flags in `{-1,0,1}` or `{0,1}` (`break_of_structure`, `higher_high`, `lower_low`, `sweep_detected`): use **raw delta** \(x_{k,d} - x_{0,d}\) without division (or same formula — division by max(|x0|,ε) is still fine).

**Trajectory tensor:** \(Z \in \mathbb{R}^{N \times D}\), row-major flatten for models: vector length \(N·D\).

### 4.4 Construction performance rule

```text
FeaturePipeline(df).run() ONCE on the full XAUUSD series
then slice rows by entry_index — never per-trade pipeline
```

PIT: features at bar \(t\) use only information available at \(t\) under the existing causal pipeline (FC1-A / F-051 policy as already in production research path).

---

## 5. Controls (mandatory)

| Id | Control | Purpose |
|----|---------|---------|
| **C-STATIC** | Static baseline: use **entry vector** \(x_0\) only — either repeated N times or single snapshot embedding | Shows path is not just t=0 |
| **C-SHUFFLE-PATH** | Randomly permute time order of the N rows within each trade (features permuted together) | Destroys temporal structure |
| **C-GLOBAL** | Outcome base rate / random classifier | Chance floor |

**Primary claim requires:** path method **strictly beats C-STATIC** on the primary OOS metric (see §7).  
If path ≈ C-STATIC → **H₀** (no new IC value).

---

## 6. Methods (frozen; pick implementations before run, no post-hoc swap)

### 6.1 Representation

| Method id | Definition |
|-----------|------------|
| **M-FLAT** | Flatten \(Z\) to length \(N·D\) |
| **M-SUMMARY** | Per-dim stats over k: mean, std, first, last, min, max → length \(6D\) (secondary; not primary unless M-FLAT underpowered) |

Primary representation: **M-FLAT**.

### 6.2 Discrimination model (closed)

| Model | Spec |
|-------|------|
| **Logistic regression** | L2, `C` frozen grid `{0.1, 1.0, 10.0}` chosen **only on IS** by mean OOF-IS logloss; single choice locked before OOS score |
| **Optional secondary** | Same GBT as H-RR robustness (max_depth=3, n_estimators=80) — **secondary only**, reported separately; cannot alone claim PROMOTE |

No architecture search, no deep nets in this prereg.

### 6.3 Clustering (secondary H_S only)

| Item | Value |
|------|--------|
| Input | M-FLAT vectors, z-scored on IS only |
| k | silhouette over `{4, 6, 8}` on IS subsample (max 5k points) |
| Report | outcome mix per cluster; **not** a promote gate |

---

## 7. Validation & gates

### 7.1 Split

```text
Time-ordered by entry_timestamp (fallback entry_index):
  first 70% IS · last 30% OOS
No shuffle CV for primary claims.
```

### 7.2 Primary metric

| Metric | Definition |
|--------|------------|
| **AUC_path** | ROC-AUC of model score vs binary TP on **OOS** |
| **AUC_static** | Same protocol on C-STATIC |
| **ΔAUC** | `AUC_path - AUC_static` |

### 7.3 Success criteria (all required for RESEARCH_SUPPORTIVE)

On **OOS**:

1. `n_oos ≥ 500` trajectories (else **INSUFFICIENT** for primary claim; still write descriptive report)  
2. `AUC_path ≥ 0.55` **and** `ΔAUC ≥ 0.03` (path beats static by pre-registered margin)  
3. IS retention: `AUC_path_IS > 0.52` and `AUC_path_OOS / AUC_path_IS ≥ 0.85` if both defined  
4. Permutation: label-shuffle of OOS outcomes, n_perm=**500**, seed frozen — two-sided p on AUC_path ≤ **0.05**  
5. C-SHUFFLE-PATH: AUC of path model on time-shuffled trajectories ≤ AUC_path − 0.02 (temporal order matters)

**No BH over many methods** — primary is single (M-FLAT + logistic with IS-chosen C). Secondary GBT cannot promote.

### 7.4 Verdict vocabulary

| Verdict | Meaning |
|---------|---------|
| `INSUFFICIENT` | n too small or pipeline pin failed |
| `REJECT` | fails §7.3 (expected under IC-001 prior extended to short paths) |
| `RESEARCH_SUPPORTIVE` | passes §7.3 — **descriptive IC value**; **no** production authority |
| `SHAPE_ONLY` | H_S clusters interesting geometry but H₀ on discrimination |

**RESEARCH_SUPPORTIVE does not:** enable engines, change fusion, or mint production config.

---

## 8. Priors (E-001 — before the run)

1. **IC-001 prior:** static entry null is strong; short post-entry paths may still be near-null.  
2. **Near-miss prior:** many losers run favorably first — path **geometry** may separate *path shape* without improving **expectancy ranking**. Prefer SHAPE_ONLY over false PROMOTE.  
3. **Dual-read prior:** direction assignment still not in the feature path unless encoded; paths are direction-aware only via signed features / trade direction as optional covariate — **direction as covariate is DIAGNOSTIC only**, not in primary feature vector (avoids leaking family policy).  

---

## 9. Explicitly out of scope

- Trailing stops, partials, time exits as **treatments** (→ IC-005 / H-RR)  
- Rebuilding entry detectors  
- Full 38-dim path including raw OHLC levels  
- Free N, free feature search, free k beyond §6.3  
- Order flow / HTF / macro  
- Claiming “entry research revived” if only t=0 models improve  

---

## 10. Artifacts on run

```text
results/research/ic_002/
  manifest.json
  trajectories_N4.jsonl   (or .npz + sidecars)
  trajectories_N8.jsonl
  trajectories_N16.jsonl
  report.json
  REPORT.md
  clusters_N*.md          (secondary)
```

Primary N for the §7.3 claim: evaluate **each N separately**; a cell is RESEARCH_SUPPORTIVE only if that N passes.  
**STOP** after one full pass over N∈{4,8,16} on XAUUSD — no iterative redesign.

---

## 11. Implementation map (when Run is granted)

| Component | Location |
|-----------|----------|
| Schema / IDs | `src/research/ic002_entry_evolution/schema.py` |
| Builder | `src/research/ic002_entry_evolution/build_trajectories.py` |
| Eval | `src/research/ic002_entry_evolution/evaluate_separation.py` |
| CLI | `scripts/research/ic002_build_trajectories.py`, `ic002_evaluate.py` |
| Tests | PIT slice, length N, static baseline, no future bars |

Reuse: `FeaturePipeline.run()`, corpus JSONL, not `detect()` harvest.

---

## 12. Status

| Item | State |
|------|--------|
| Design frozen | **YES** |
| Code | **YES** — `src/research/ic002_entry_evolution/` |
| Run | **YES** — `results/research/ic_002/REPORT.md` |
| Finding | optional; not auto-minted |

**First-run summary:** N=4 and N=16 **RESEARCH_SUPPORTIVE** (path AUC_OOS≈0.57–0.60 vs static≈0.51); N=8 **REJECT** (shuffle-path gap). Interpretation: concurrent path description under fixed exits — **not** entry-time tradable alpha. See REPORT.md.

---

## 13. Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Initial open preregistration (user: Draft IC-002 prereg) |

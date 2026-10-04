# Implementation Plan — IC-001 Closure + ERP Information-Class Roadmap

> **Status:** PLAN · **Phase 1 EXECUTED 2026-07-17** (IC-001 fence docs + test)  
> **Date:** 2026-07-17  
> **Authority:** Research / documentation / governance only (§6.5). **No** new engines, **no** threshold tuning, **no** production promote from this plan.  
> **Parents:** User handoff (IC taxonomy + Dual-Read Bar 78) · existing  
> [`docs/research-readiness/erp-information-class-boundary.md`](../research-readiness/erp-information-class-boundary.md) ·  
> XAUUSD descriptive enrichment · H-RR-THRESHOLD-001 (running / research-only) · RR contracts A/B/C/D wiring.

---

## 0. One-screen Orient

| Item | State |
|------|--------|
| **Chapter to close** | **IC-001** = Static entry-time OHLCV-derived information (XAUUSD certified corpus) |
| **Not closed** | “Entry research forever” — only this information class on this corpus |
| **Permanent teaching artifact** | Dual-Read Bar 78 (library #1 vs #4) |
| **Next research chapter** | **IC-002 / RC-005** Entry Evolution (post-entry trajectory) — OHLCV-only |
| **Hard guardrail** | No new engines · no threshold tuning · no re-analyzing IC-001 with a different model |
| **H-RR-THRESHOLD-001** | Orthogonal production R-threshold study (admission/exit knobs); **not** a reopening of IC-001 entry discrimination |

---

## 1. Canonical scientific statement (freeze this wording)

### 1.1 Measured boundary (authoritative)

> **Within Information Class IC-001 (static entry-time OHLCV-derived information), no practically useful outcome discrimination was observed on the certified XAUUSD corpus under the evaluated research conditions.**

### 1.2 Explicit non-claims

| Do **not** say | Correct |
|----------------|---------|
| “Entry research is dead forever” | IC-001 static entry math is **characterized** on this corpus |
| “Nothing beyond OHLCV can help” | Unmeasured classes remain **open**; not measured ≠ uninformative |
| “Order flow is required next” | Current ERP stays **OHLCV-centered** until that surface is exhausted |
| “AUC 0.51 is the main result” | Dual-read / agreement≠skill / path failure structure are the **teaching** results |

### 1.3 Independent attacks already on the record (IC-001 saturation)

| Attack | Artifact / surface |
|--------|-------------------|
| Static 38 features / distributions | `trace_corpus`, `DISTRIBUTIONS.md` |
| Engines + fusion + calibration | `ENGINE_EVALUATION.md`, `FAMILY_CALIBRATION.md` |
| Near-miss path structure | `NEAR_MISS_PROFILE.md` |
| Morphology clusters (F-023 class) | `geometry/CLUSTERS.md` |
| Representative library + dual-read | `REPRESENTATIVE_LIBRARY.md` (#1 vs #4) |
| Non-linear OOF (GBT) + **time-series CV** | `ROBUSTNESS_XVRP.md`, `TIME_SERIES_CV_X.md` |
| Continuous R + permutation | `ROBUSTNESS_XVRP.md` |
| Cross-asset entry null priors | F-019…F-042 (context; not XAU-only) |

**Verdict for plan:** IC-001 is **COMPLETE as a measured chapter** — documentation/archive work, not more static-entry models.

---

## 2. Taxonomy map (user IC-xxx ↔ existing RC-xxx)

Keep **both** IDs: user-facing **IC-*** for chapter language; machine **RC-*** already in the boundary JSON.

| User IC | Name | Maps to | Status after this plan | OHLCV-native? |
|---------|------|---------|------------------------|---------------|
| **IC-001** | Static Entry Mathematics | Measured boundary (no RC id) | **COMPLETE** (archive) | Yes |
| **IC-002** | Entry Evolution | **RC-005** Temporal Evolution | OPEN · **NEXT design** | Yes |
| **IC-003** | Trade Trajectory / Shape families | RC-005 extension + path geometry | OPEN (after IC-002) | Yes |
| **IC-004** | Cross-Instrument Generalization | *(new RC or IC-004 registry row)* | OPEN | Yes |
| **IC-005** | Execution Layer | **RC-007** Execution Effects | OPEN | Yes (policy); not microstructure |
| — | Higher-TF context | RC-006 | OPEN (later) | Yes |
| — | Order flow / macro / alt | RC-008…010 | OPEN · **data-gated** · not ERP focus now | No |

**OHLCV-first doctrine (user-aligned):**  
Research effort stays on  
`OHLCV → 38 features → trace → geometry → shape library → shape evolution → representative shapes → interpretation → prereg hypotheses`  
until that stack is exhausted. Order flow remains an honesty bound (“not measured”), not a pivot.

---

## 3. Permanent ERP teaching example — Dual-Read Bar 78

### 3.1 Facts (do not paraphrase away)

| | #1 | #4 |
|--|----|----|
| Trade ID | `expansion_breakout_000007` | `mean_reversion_000012` |
| Bar | **2024-05-22 20:30**, index **78**, price **2387.55** | **identical** |
| Features / engines | body 0.576 · CRT 0.45 · G 0.88 · Z 0.2 · RR 0.77 · Fusion 0.56 | **identical** |
| Direction / family | SHORT / expansion | LONG / mean_reversion |
| Outcome | **TP_HIT +2R** | **SL_HIT −1R** |

### 3.2 Lesson (one sentence)

> Entry-time mathematics restates candle morphology; it does **not** adjudicate direction/family forks on the same vector.

### 3.3 Implementation actions (documentation)

| # | Action | Deliverable |
|---|--------|-------------|
| T1 | Promote dual-read to a **named permanent example** | `docs/research-readiness/erp-teaching-dual-read-bar78.md` (1 page) |
| T2 | Cross-link from library, IC-001 closure, boundary doc | Links only |
| T3 | Ensure `representative_exemplars.jsonl` categories remain `typical_tp` + `dual_read` with tags `dual_read_bar_78` | Already mostly done (UX polish) |
| T4 | Optional: 1 slide-ready table in `REPRESENTATIVE_LIBRARY.md` “Teaching openers” section | Small MD edit |

---

## 4. Archive IC-001 (not “Entry Research”)

### 4.1 What “archive” means here

| Do | Don’t |
|----|-------|
| Mark IC-001 **COMPLETE** in boundary registry | Delete artifacts |
| Write a **closure chapter** with statement + attack matrix + links | Claim global entry null across all assets without IC-004 |
| Treat artifacts as a **conceptual fence** against re-work | Re-run XGBoost/LSTM on the same 38 static dims as “new research” |
| Keep H-RR-THRESHOLD-001 under **execution / config R** (RC-007-adjacent) | Fold H-RR into “IC-001 failed so change R to find edge” without prereg gates |

### 4.2 Deliverables

| # | Deliverable | Path (proposed) |
|---|-------------|-----------------|
| A1 | IC-001 closure chapter | `docs/research-readiness/ic-001-xauusd-static-entry-closure.md` |
| A2 | Update boundary MD+JSON | Add IC-001 COMPLETE; map IC-002…; dual-read pointer; list new attacks (GBT, TS-CV, near-miss, family cal) |
| A3 | Optional thin finding | F-xxx only if owner wants living-findings index row (research authority only) |
| A4 | Program tracker note | One row in edge-research-platform program if present |

### 4.3 Closure chapter outline (A1)

1. Canonical statement (§1.1)  
2. Corpus pin (path, n=23,447 / 23,428 scored, families)  
3. Attack matrix with artifact paths  
4. Dual-Read Bar 78  
5. Engine characterization table (CRT / G / Zone / RR / Fusion)  
6. What remains **forbidden** under IC-001  
7. Pointer to **IC-002** as next chapter  
8. Authority banner DESCRIPTIVE / RESEARCH_ONLY  

---

## 5. H-RR-THRESHOLD-001 — how it plugs in (running job)

### 5.1 Status at plan time

- Job: `scripts/research/h_rr_threshold_001.py`  
- Observed: still in harvest (~30+ min CPU, ~70k bars × 4 instruments × 2 families); no result artifacts yet  
- **When complete:** fold summary into RC-007 / config-governance evidence, **not** as IC-001 entry skill  

### 5.2 Interpretation rules (pre-committed)

| Outcome | Use |
|---------|-----|
| Arm B all E_oos &lt; 0 | Consistent with **F-025** — exit R is risk/cost, not alpha |
| Arm A admit_rate structure | Documents honest D-wiring (e.g. planned TP1 1.0 fails min_rr 1.5) |
| Any PROMOTE_RESEARCH | **Config proposal only** — human governance; not engine work |
| Runtime too long | Optional later: pin cached entries artifact to skip re-harvest (prereg-compatible if population unchanged) |

### 5.3 Plan step when results land

| # | Action |
|---|--------|
| H1 | Read `results/research/h_rr_threshold_001/REPORT.md` |
| H2 | Append 1 paragraph to IC-001 closure “Related but distinct: production R-threshold study” |
| H3 | If live reject spike + H-RR null → config hygiene only; if PROMOTE_RESEARCH → separate promote PR |

---

## 6. Implementation phases

### Phase 0 — Wait / capture H-RR (in flight)

| Step | Owner | Exit |
|------|-------|------|
| 0.1 | Let runner finish or kill+restart with progress logging | `REPORT.md` exists |
| 0.2 | Record program_verdict in SESSION LOG | Logged |

**Estimate:** remaining harvest-dominated; could be **~20–60+ min** total from start (already ~30+ min).

---

### Phase 1 — Documentation fence (IC-001 COMPLETE) — **no code engines**

| Step | Work | Est. |
|------|------|------|
| 1.1 | Write `ic-001-xauusd-static-entry-closure.md` | 0.5–1 h |
| 1.2 | Write `erp-teaching-dual-read-bar78.md` | 0.25 h |
| 1.3 | Update `erp-information-class-boundary.{md,json}`: IC aliases, COMPLETE IC-001, dual-read, attack list | 0.5 h |
| 1.4 | Library “Teaching openers” blurb + dual-read table | 0.25 h |
| 1.5 | SESSION LOG + optional F-id (owner call) | 0.25 h |

**Exit criteria:** A human/LLM reading only the closure + boundary docs cannot reasonably re-open “train another model on 38 static features for XAUUSD entry.”

**Guardrail sentence (paste into every future ERP prompt):**

> **Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.**

---

### Phase 2 — Design IC-002 / RC-005 only (pre-register, do not run until grant)

**Question:**  
How does the **mathematical state evolve** over the first **N** bars after entry (OHLCV-derived trajectory), and does that trajectory family separate outcomes better than the IC-001 snapshot?

| Step | Work | Est. |
|------|------|------|
| 2.1 | Define trajectory object: per-bar feature vector or reduced shape path for t=0…N | Design |
| 2.2 | Freeze N ∈ {4, 8, 16} (closed set — no free N search) | Design |
| 2.3 | Population: same frozen XAUUSD entries (or crypto majors if generalizing later) | Design |
| 2.4 | Controls: shuffled path, static snapshot-only, time-reversed path (diagnostic) | Design |
| 2.5 | Metrics: path-cluster purity vs outcome; OOS; **no** entry-score rehash | Design |
| 2.6 | Write `h-ic002-entry-evolution-preregistration.md` + JSON twin | 1–2 h |
| 2.7 | **STOP** until user says Run | — |

**Explicitly not IC-002:**

- New CRT states  
- rr_fusion enable  
- Feature formula changes  
- Same 38 dims at t=0 only with a new classifier  

**Data:** pure OHLCV + existing FeaturePipeline / causal rules — **no order flow.**

---

### Phase 3 — IC-003 Shape library (after IC-002 has a first measurement)

| Step | Work |
|------|------|
| 3.1 | Compress trajectories → canonical shapes (cluster / prototype paths) |
| 3.2 | Representative shape library (human + LLM), analogous to trade exemplars |
| 3.3 | Stories **only as documentation of shapes**, never as priors that invent shapes |
| 3.4 | Separate prereg before any expectancy claim |

---

### Phase 4 — IC-004 Cross-instrument (fence test)

| Step | Work |
|------|------|
| 4.1 | Replicate IC-001 **descriptive** battery on EURUSD / BTC / (optional NAS100) with same protocol |
| 4.2 | Ask: same null region vs different morphology |
| 4.3 | Does **not** require IC-002 success |

Can run **in parallel** with Phase 2 design if owner wants fence strength; still not “new engines.”

---

### Phase 5 — IC-005 / RC-007 Execution layer

| Step | Work |
|------|------|
| 5.1 | Incorporate H-RR-THRESHOLD-001 results as first R-admission/exit cell study |
| 5.2 | Optional later: path-aware exits **only** under new prereg (not near-miss post-hoc) |
| 5.3 | Keep separate from IC-001 entry skill claims |

---

## 7. Pipeline picture (target architecture)

```text
OHLCV
  → Canonical mathematics (38 features / ontology)
  → Mathematical Trace Corpus
  → Geometry / clusters          [IC-001: DONE on XAUUSD entry snapshot]
  → Shape evolution (paths)      [IC-002]
  → Shape library                [IC-003]
  → Representative shapes
  → LLM mathematical interpretation (descriptive)
  → Pre-registered hypotheses
  → ERP validation (M4 / OOS / costs) — authority ladder
```

Stories attach **after** shapes, not before.

---

## 8. Hard guardrails (non-negotiable for next coding LLM)

1. **No new engines** (no “EntryNet v3”, no re-enable rr_fusion without ΔG001 + F-044/F-045).  
2. **No threshold tuning** as research theater on IC-001.  
3. **No feature optimization** on the same static entry vector.  
4. **No claiming** order-flow necessity; also **no** claiming OHLCV is the only possible information in nature.  
5. **One IC at a time** for design+run (IC-002 next).  
6. **RR contracts stay split:** A polarity · B shadow · C no polarity-as-RR · D SL/TP true RR.  
7. Production config changes only via **governance promote**, never from descriptive AUC.

---

## 9. Work queue (recommended order)

| Priority | Item | Depends on |
|----------|------|------------|
| P0 | Finish or recover H-RR-THRESHOLD-001 results | Running job |
| P1 | Phase 1 docs (IC-001 closure + dual-read + boundary update) | None |
| P2 | Phase 2 IC-002 prereg only | P1 preferred |
| P3 | User grant → implement IC-002 measure pipeline | P2 |
| P4 | IC-003 / IC-004 as separate grants | P3 or parallel design |

---

## 10. Success criteria for *this plan*

| Criterion | Met when |
|-----------|----------|
| IC-001 fence | Closure doc + boundary say COMPLETE; dual-read is the default teaching opener |
| No IC-001 reopen | Future sessions cite guardrail sentence |
| Next chapter clear | IC-002 prereg exists before any trajectory code lands |
| H-RR integrated correctly | Results filed under execution/R-threshold, not “entry edge found” |
| OHLCV program intact | Roadmap does not pivot to order flow |

---

## 11. Immediate next user choices

| Say… | Effect |
|------|--------|
| **Execute Phase 1** | Write closure + dual-read + boundary updates now |
| **Continue waiting on H-RR** | Only monitor; fold when `REPORT.md` appears |
| **Kill H-RR / restart lean** | Progress logging + optional entry cache (if harvest too slow) |
| **Draft IC-002 prereg** | Phase 2 design only |
| **Implement IC-002** | Only after prereg frozen + explicit run grant |

---

## 12. Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Initial plan from user handoff + existing RC registry + live H-RR job |

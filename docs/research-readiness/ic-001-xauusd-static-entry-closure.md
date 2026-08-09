# IC-001 — XAUUSD Static Entry Mathematics (CLOSED)

> **DESCRIPTIVE / RESEARCH_ONLY** — information not authority (§6.5).  
> **Information Class status: COMPLETE** on the certified XAUUSD corpus under the evaluated conditions.  
> This archives **IC-001**, not “entry research forever.”  
> Machine boundary twin: [`erp-information-class-boundary.json`](erp-information-class-boundary.json)  
> Plan: [`docs/implementation_plan/erp-ic001-closure-and-ic-roadmap.md`](../implementation_plan/erp-ic001-closure-and-ic-roadmap.md)

---

## Canonical statement

> **Within Information Class IC-001 (static entry-time OHLCV-derived information), no practically useful outcome discrimination was observed on the certified XAUUSD corpus under the evaluated research conditions.**

### Explicit non-claims

| Do **not** say | Correct reading |
|----------------|-----------------|
| “Entry research is dead forever” | Only **static entry-time** math on **this** corpus is characterized |
| “Nothing beyond OHLCV can help” | Other information classes remain **UNMEASURED** |
| “Order flow is required next” | ERP stays **OHLCV-centered** until that surface is exhausted |
| “AUC≈0.51 is the whole story” | Dual-read / agreement≠skill / path structure are the teaching results |

---

## Corpus pin

| Field | Value |
|-------|--------|
| Instrument | XAUUSD M15 |
| Candidate corpus | ~23,447 traces (families: expansion_breakout, mean_reversion, spine n=1) |
| Scored / enriched | ~23,428 with features+engines (19 warmup-null) |
| Artifact root | `results/research/trace_corpus/xauusd/` (often gitignored — regenerate via research scripts if missing) |
| OHLCV source (typical) | `data/mt5/XAUUSD_M15.csv` or `data/XAUUSD_M15.csv` (pin sha at re-run) |
| Authority | Descriptive / research only |

---

## Attack matrix (IC-001 saturation)

Independent attacks on the **same information class** (static entry snapshot / static scores). Not the same experiment repeated under a new name.

| Attack | Artifact(s) under `results/research/trace_corpus/xauusd/` | Result (summary) |
|--------|-----------------------------------------------------------|------------------|
| Static 38 features / distributions | `DISTRIBUTIONS.md`, `distributions.json` | Outcome means close; morphology ≠ expectancy |
| Engine scores + fusion | `ENGINE_EVALUATION.md` | AUC ≈ 0.49–0.51; flat calibration |
| Family-specific calibration | `FAMILY_CALIBRATION.md`, `family_calibration.json` | Score *levels* differ by family; skill does not |
| Near-miss path structure | `NEAR_MISS_PROFILE.md`, `near_miss_profile.json` | ~25% of SL; 63% reached +1R then reversed — path, not entry alpha |
| Morphology clusters | `geometry/CLUSTERS.md` | Distinct shapes, ~same win rates (F-023 class) |
| Representative library | `REPRESENTATIVE_LIBRARY.md`, `representative_exemplars.jsonl` | Agreement ≠ skill; dual-read |
| Non-linear OOF (GBT) | `ROBUSTNESS_XVRP.md` | Shuffle OOF ~0.54 (feature-driven) |
| Time-series CV | `TIME_SERIES_CV_X.md` | TS-CV full OOF ~0.51–0.52; shuffle inflation confirmed |
| Continuous R + permutation | `ROBUSTNESS_XVRP.md` | Spearman(score,R)≈0; large-N p≠edge |
| Enriched full corpus | `trace_corpus_enriched.jsonl` | Features + engine fields for audit |

Related priors (cross-asset entry nulls): **F-019…F-042** (context; not XAU-only closure).

---

## Permanent teaching example

**Dual-Read Bar 78** — same candle vector and engine scores; opposite direction/family; opposite outcome.

→ Full card: [`erp-teaching-dual-read-bar78.md`](erp-teaching-dual-read-bar78.md)

| | #1 | #4 |
|--|----|----|
| Trade ID | `expansion_breakout_000007` | `mean_reversion_000012` |
| Entry | index **78**, 2024-05-22 20:30, **2387.55** | **identical** |
| Engines | CRT≈0.45 · G≈0.88 · Z=0.2 · RR≈0.77 · Fusion≈0.56 | **identical** |
| Direction | short | long |
| Outcome | TP_HIT (+2R) | SL_HIT (−1R) |

**Lesson:** entry-time mathematics restates morphology; it does **not** adjudicate direction/family forks.

Secondary teaching block: high-agreement exemplars **#10–#13** (aligned engines, split TP/SL).

---

## Engine characterization (descriptive)

| Component | On this corpus |
|-----------|----------------|
| CRT | Low/mid scores; non-discriminative (AUC~0.51) |
| Gaussian | Near-constant (~0.88); not a ranker |
| Zone | Wide; couples partly with CRT; non-discriminative |
| RR (A polarity) | High candle-polarity; not true reward/risk |
| Fusion | Reweights non-discriminative inputs; EXECUTE−VETO ΔWR noise-scale |
| Agreement | High agreement rare and not better than chance |
| Geometry | Organizes shape, not expectancy |

**RR contracts (architecture, not IC-001 reopen):** A polarity active · B rr_fusion shadow/inert · C must not treat polarity as economic RR · D true RR from SL/TP (Ultron). See `docs/governance/rr_lineage_audit.md`.

---

## Forbidden re-openings of IC-001

Without a **new information class** and new preregistration, do **not**:

- Train XGBoost / LSTM / RF / linear models on the **same static entry 38-vector** (or engine scores alone) and call it new research  
- Tune fusion weights / DecisionEngine thresholds to “fix entry AUC”  
- Re-enable `rr_fusion` as an entry edge claim  
- Mine post-hoc feature thresholds on the frozen XAUUSD entry snapshot  

**Hard guardrail:**

> Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.

---

## Related but distinct studies

| Study | Relation to IC-001 |
|-------|-------------------|
| **H-RR-THRESHOLD-001** | Production **admission/exit R** knobs (tp1 × min_rr) — **IC-005 / RC-007-adjacent**, not entry snapshot skill |
| F-025 exit grid | Exit geometry as risk/cost lever — not IC-001 reopen |

---

## Next chapter

| Id | Name | Status |
|----|------|--------|
| **IC-002 / RC-005** | Entry Evolution (post-entry trajectory) | **MEASURED** 2026-07-17 — path beats static on N=4/16 (RESEARCH_SUPPORTIVE); not entry-time tradable; [`ic_002/REPORT.md`](../../results/research/ic_002/REPORT.md) |
| IC-003 | Shape library from trajectories | **ARCHIVED LIBRARY_FAIL (v1)** — [`ic-003-lessons-learned.md`](ic-003-lessons-learned.md) · A1 not authoritative |
| IC-004 | Cross-instrument IC-001 fence test | OPEN |
| IC-005 / RC-007 | Execution / R policy | OPEN |

Implementation detail: [`docs/implementation_plan/erp-ic001-implementation-details.md`](../implementation_plan/erp-ic001-implementation-details.md).

---

## Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Phase 1 archive — IC-001 COMPLETE fence |

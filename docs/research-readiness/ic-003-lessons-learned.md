# IC-003 Lessons Learned — Shape Library under frozen gates

> **Authority:** governance / research integrity only (§6.5).  
> **Date:** 2026-07-17  
> **Parent prereg:** [`h-ic003-shape-library-preregistration.md`](h-ic003-shape-library-preregistration.md)  
> **Authoritative scientific result:** **v1 LIBRARY_FAIL** under G1 max = **0.85** (not A1).

---

## 1. Three measured boundaries (not “a chain of failures”)

| IC | Question | Authoritative result |
|----|----------|----------------------|
| **IC-001** | Does a static entry-time OHLCV snapshot discriminate TP vs SL? | **No** — boundary established |
| **IC-002** | Does post-entry trajectory contain additional measurable information vs static? | **Yes** (under prereg gates), concurrent with trade evolution — not entry prediction |
| **IC-003** | Can those trajectories be compressed into a stable, reusable shape ontology under preregistered geometry gates? | **No (LIBRARY_FAIL)** under v1 gates |

These are **independent** scientific questions. IC-003 fail does **not** reverse IC-002.

---

## 2. What IC-003 actually taught

### Correct conclusion

> **The trajectory manifold is not naturally compressible into a small, stable prototype library under this representation and these validation criteria.**

### Incorrect conclusions (do not draw)

| Wrong | Why |
|-------|-----|
| “KMeans failed, so try until it passes” | Turns prereg into a moving target |
| “IC-002 was wrong” | Different question (path info vs prototype library) |
| “0.873 is close to 0.85, so loosen G1” | “Close” is not a scientific reason to move a frozen gate |
| “Trajectory research is dead” | Trajectory info can exist without clean prototypes |

---

## 3. Why the library failed (v1 numbers)

| N | Role | Binding fails (v1, G1≤0.85) | Detail |
|---|------|------------------------------|--------|
| **4** | primary | **G1 only** | sse_ratio **0.873** > 0.85; G2–G5 passed |
| **16** | primary | **G1 + G2** | sse ~0.87; silhouette **0.020** ≪ 0.05 |
| **8** | diagnostic | G1 + G2 | not primary |

**Interpretation of G1 near-miss (N=4):** within-cluster SSE is only modestly below global SSE — clusters are **weak**, not tight prototypes. Being 2.3 pp over the bar is still a fail under prereg discipline.

**Interpretation of G2 (N=16):** longer flattened paths live in a high-dimensional space where Euclidean KMeans silhouette collapses — consistent with a **more continuous** manifold or a **representation mismatch**, not a license to retune k after the fact.

---

## 4. Process note: Amendment A1 (SUPERSEDED for scientific authority)

A1 (G1 0.85→0.90) was user-executed after the first fail. Under ERP integrity review, **post-hoc gate relaxation because a result was “close” is the failure mode preregistration exists to prevent.**

| Run | Status for decision-making |
|-----|----------------------------|
| **v1** (G1=0.85) | **AUTHORITATIVE** scientific result = **LIBRARY_FAIL** |
| **A1** (G1=0.90) | **NON-AUTHORITATIVE** post-hoc sensitivity / process experiment — N=4 would pass G1; does **not** replace the archive |

A1 code/docs remain in the record for transparency (`amendments.A1` marked **SUPERSEDED_AS_AUTHORITY**). Default code constants restored to **G1=0.85** so future runs match the frozen scientific bar unless a **new** prereg (e.g. **IC-003B**) is opened with a different *representation*, not a quieter gate.

---

## 5. Independent of IC-002

```text
IC-002: Is there path information beyond the static snapshot?
        → Yes (measured, concurrent-path caveat).

IC-003: Can paths be summarized by a finite prototype library
        under Euclidean M-FLAT + KMeans + G1–G5?
        → No (LIBRARY_FAIL).
```

Trajectory information **can** exist without clean prototype decomposition. Do not collapse these.

---

## 6. Hypotheses for a future **IC-003B** (not this amendment)

These are **new design questions** for a separate preregistration — not silent tweaks:

1. Does **flattening** destroy temporal structure that DTW / soft-DTW / alignment kernels would preserve?  
2. Would a **sequence distance** (rather than Euclidean on M-FLAT) change geometry?  
3. Are **multiple timescales** mixed (N=4 vs N=16 disagreement)?  
4. Is the manifold **genuinely continuous** (soft mixture / continuum) rather than prototype-based?  
5. Would **path summaries** (mean/std/first/last per dim) cluster more cleanly than full flatten?

Any of these → **IC-003B** (new prereg id), not “IC-003 with G1=0.90.”

**Designed 2026-07-17 (not run):**  
[`h-ic003b-sequence-geometry-preregistration.md`](h-ic003b-sequence-geometry-preregistration.md) — Arm S path-summaries · Arm T DTW medoids · Arm C continuum diagnostic. G1 remains **0.85** (no gate amend).

---

## 7. What not to do next

| Action | Verdict |
|--------|---------|
| Amend gates because 0.873 ≈ 0.85 | **Rejected** (this note) |
| Jump to IC-004 to “replicate” a failed library | **Low priority** until the *object of replication* is clear |
| Treat A1 PARTIAL as the archive result | **No** — v1 LIBRARY_FAIL is authoritative |
| Reinterpret IC-003 as killing IC-002 | **No** |

---

## 8. Recommended queue (ERP-healthy)

```text
IC-003 v1 LIBRARY_FAIL
  → Archive (this note + prereg + code + artifacts)
  → Analyze failure modes (§3–§6)
  → Design IC-003B (new representation) OR different IC
  → Preregister → Measure → Accept
```

Not:

```text
Fail → loosen gate → pass → declare success
```

---

## 9. Permanent ERP pattern

```text
Question → Preregister → Measure → Accept result
```

A preregistered experiment that fails honestly **narrows the search space without hindsight bias**. That is as valuable as a pass.

---

## Document control

| Version | Date | Note |
|---------|------|------|
| v1 | 2026-07-17 | Archive IC-003 as measured boundary; demote A1 authority |

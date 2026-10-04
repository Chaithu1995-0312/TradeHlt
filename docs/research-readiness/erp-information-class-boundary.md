# ERP — Information-Class Boundary & Open Questions

> **Authority:** descriptive / governance only — PL-0; grants **no** promotion or production authority
> (§6.5). Machine twin: [`erp-information-class-boundary.json`](erp-information-class-boundary.json)
> (edit both together). Refines unknown **U-008**; maps to phased-plan **P4 (New Information Family)**.

### Hard guardrail (every future ERP session)

> **Do not create new engines. Do not tune thresholds. Do not optimize features. Future work must introduce genuinely new information classes rather than re-analyzing IC-001.**

---

## IC alias map

| User-facing IC | Registry | Status |
|----------------|----------|--------|
| **IC-001** Static Entry Mathematics | `measured_boundary` | **COMPLETE** (this corpus) |
| **IC-002** Entry Evolution | **RC-005** | OPEN · **NEXT** |
| **IC-003** Trajectory / shape library | RC-005 extension | **ARCHIVED LIBRARY_FAIL (v1)** |
| **IC-003B** Sequence geometry library | IC-003B | **MEASURED PARTIAL** (2026-07-17) · `IC003B_PARTIAL` |
| **IC-004** Cross-instrument generalization | `IC-004` (planned row) | OPEN |
| **IC-005** Execution layer | **RC-007** | OPEN |
| Higher-TF context | RC-006 | OPEN |
| Order flow / macro / alt | RC-008…010 | OPEN · data-gated |

Closure chapter: [`ic-001-xauusd-static-entry-closure.md`](ic-001-xauusd-static-entry-closure.md)  
Teaching example: [`erp-teaching-dual-read-bar78.md`](erp-teaching-dual-read-bar78.md)

---

## The measured boundary — IC-001 COMPLETE

> **Within Information Class IC-001 (static entry-time OHLCV-derived information), no practically useful outcome discrimination was observed on the certified XAUUSD corpus under the evaluated research conditions.**

Scoped short form (legacy): *Static entry-state morphology derived from OHLCV did not discriminate outcomes on the XAUUSD frozen-candidate corpus* (`data/mt5/XAUUSD_M15.csv`, ~23,447 traces).

**Status:** **COMPLETE** as a measured research chapter on this corpus — **not** “entry research forever.”

### Measured surfaces (all: no practically useful outcome separation)

| Surface | Measured? | Result |
|---|---|---|
| Static 38 PIT features at entry | ✅ | no meaningful separation |
| Engine scores (CRT / RR / Gaussian / Zone / Fusion) | ✅ | AUC≈0.49–0.51; flat calibration |
| Feature distributions (by outcome / segment) | ✅ | no meaningful separation |
| Morphology clusters (KMeans on shape features) | ✅ | cluster outcomes ~uniform (SL 66–68% / TP 31–33%) |
| k-NN similarity (per-trace neighbours) | ✅ | concordance 0.5498 ≈ random baseline 0.5459 |
| Family-specific engine calibration | ✅ | levels differ; skill does not |
| Near-miss SL path profile | ✅ | path failure structure, not entry ranker |
| Representative library + dual-read | ✅ | agreement≠skill; bar-78 constructive counterexample |
| Non-linear OOF (GBT) + **time-series CV** | ✅ | shuffle OOF~0.54 inflated; TS-CV ~0.51–0.52 |
| Continuous R + permutation tests | ✅ | score–R association ~0; large-N p ≠ edge |

Evidence: findings **F-019 / F-023 / F-035** (+ XAUUSD descriptive pack 2026-07); work items **WI-005 / WI-006 / WI-007**; artifacts under
`results/research/trace_corpus/xauusd/` (see IC-001 closure attack matrix).

**Permanent teaching example:** Dual-Read Bar 78 — [`erp-teaching-dual-read-bar78.md`](erp-teaching-dual-read-bar78.md).

**What this does NOT say:** it does **not** show that other information classes are uninformative — those
are **UNMEASURED**. *"Not measured" ≠ "likely to work"* and ≠ *"shown to be uninformative."*  
ERP remains **OHLCV-first** for the next chapters; order flow is an honesty bound, not a required pivot.

### Correction (E-001)

> **Caught me overclaiming; I owe you a correction.**

An earlier statement — *"shape carries no outcome information at any resolution"* — over-generalized the
measured null. `CORRECTED -> ` the scoped boundary above (static entry-state OHLCV morphology, this
corpus). Fixed in: `assistant_project.md` SESSION LOG, the program-tracker twin (CL-024 / WI-007), the
memory note, and `scripts/research/trace_knn.py`. History preserved (append-discipline).

---

## Open information classes (UNMEASURED — questions, not leads)

Genuinely **different information classes** from IC-001 — each an **open research
question**, opened **one at a time** (RC-005 / IC-002 is NEXT), each a **pre-registered descriptive experiment
only on an explicit owner grant** (PL-0, measure-only, grants no authority). **Guard:** each is a
distinct class — **NOT** a reopening of static-entry morphology under a new name (including “new ML on the same 38 static dims”).

| Id | IC alias | Class | Question (descriptive) | Status | In corpus? |
|---|---|---|---|---|---|
| **RC-005** | **IC-002** | **Temporal Evolution** | Does post-entry feature **trajectory** improve separation vs entry-only morphology? | **MEASURED** (2026-07-17): N=4/16 RESEARCH_SUPPORTIVE vs static; N=8 REJECT shuffle-gap; **not** entry-time tradable authority — see [`results/research/ic_002/REPORT.md`](../../results/research/ic_002/REPORT.md) · prereg [`h-ic002-entry-evolution-preregistration.md`](h-ic002-entry-evolution-preregistration.md) | yes |
| — | **IC-003** | Shape library | Finite stable prototypes under G1–G5? | **ARCHIVED LIBRARY_FAIL (v1, G1=0.85)** · [`ic-003-lessons-learned.md`](ic-003-lessons-learned.md) · A1 not authoritative | yes |
| — | **IC-003B** | Sequence geometry library | Summaries + DTW + continuum? | **MEASURED PARTIAL** (2026-07-17): verdict `IC003B_PARTIAL` — Arm S OK at N=4 (marginal) but FAIL at N=16; Arm T FAIL; Arm C N=4 DISCRETE_HINT (dimensionality artifact). Robustly-weak, structurally under-determined library (independently re-derived; seed-robust; k\* unstable). See [`results/research/ic_003b/`](../../results/research/ic_003b/) · prereg [`h-ic003b-sequence-geometry-preregistration.md`](h-ic003b-sequence-geometry-preregistration.md) | yes |
| — | **IC-004** | Cross-instrument | Do the same null regions appear on EURUSD / BTC / …? | OPEN | yes (other files) |
| RC-006 | — | Higher-Timeframe Context | Does daily/H4/H1 state at entry improve separation vs M15 snapshot? | OPEN | yes |
| **RC-007** | **IC-005** | Execution Effects | Would a different execution/R policy change outcomes for the same entries? | OPEN | yes |
| RC-008 | — | Order Flow | Bid/ask / depth / aggressor? | OPEN | **no** |
| RC-009 | — | Macro Information | CB / CPI / employment / geopolitics? | OPEN | **no** |
| RC-010 | — | Alternative Data | Positioning / sentiment / on-chain? | OPEN | **no** |

Each carries the caveat **"not measured ≠ likely to work."** RC-008/009/010 require **data acquisition** first.

**Related running/adjacent study:** H-RR-THRESHOLD-001 (tp1 × min_rr) is **execution/R-threshold** research (IC-005-adjacent), **not** a reopening of IC-001 entry discrimination.

---

## Shape documentation hierarchy (read-order for coding LLMs)

A 4-level chain with a strict authority gradient — **math is authoritative; explanations and stories grant
no authority and never flow upward into a mathematical claim** (§6.5):

| Level | File | Role | Authority |
|---|---|---|---|
| 1 | `results/research/ic_003b/SHAPE_LIBRARY.md` (generated) | what mathematically exists | **AUTHORITATIVE** |
| 2 | [`shape_explanations.md`](shape_explanations.md) | LLM→human explanation of each shape | **NONE** |
| 3 | `configs/research/market_story_ontology.yaml` | closest story family (labels) | NONE · **mapped 2026-07-18** (nearest-family in `shape_explanations.md`; 2/6 active, 4/6 planned `trend_reversal`; weak) |
| 4 | `results/research/ic_003b/REPORT.md` (generated) | why it matters / governance | governance record |

Read **top-down**. Level 2 explains the only `LIBRARY_OK` unit (Arm S N=4, 6 shapes) and carries the
IC-003B robustness caveat (marginal / seed-fragile / near-noise) so a human gloss is never mistaken for a
stable archetype. Floor: `tests/research/test_shape_explanations.py`.

---

## Discipline

1. **One at a time** — IC-001/002/003 are **measured boundaries**. IC-003 **archived LIBRARY_FAIL (v1)**. **IC-003B** is now **MEASURED PARTIAL** (2026-07-17; verdict `IC003B_PARTIAL`, robustly-weak library — not a G1 amend). Next: an explicit **owner grant** picks the next information class (P4) — not IC-004 replicate-fail by default.
2. **Distinct class** — each opens a new information source, never re-runs static-entry morphology.
3. **Grant-gated** — a class is only *designed* (pre-registered) and *measured* on an explicit owner
   grant; every result stays PL-0 / UNTRUSTED_RAW / descriptive until it survives the full M4 gate + OOS
   + costs (a separate step, never a promotion from a descriptive artifact).
4. **OHLCV-first** — prefer trajectory/shape chapters on the existing mathematical surface before pivoting off-OHLCV.

---

## Document control

| Version | Date | Note |
|---------|------|------|
| 1.0 | 2026-07-16 | Initial boundary + RC-005…010 |
| 1.1 | 2026-07-17 | Phase 1: IC-001 COMPLETE, IC aliases, dual-read, guardrail, extended surfaces |
| 1.2 | 2026-07-17 | IC-003B MEASURED PARTIAL (`IC003B_PARTIAL`): robustly-weak / under-determined sequence library; validation (independent re-derivation) + robustness recorded; `discipline.next` → owner grant |
| 1.3 | 2026-07-18 | Shape documentation hierarchy (4-level read-order) + Level-2 `shape_explanations.md` (6 IC-003B Arm-S N=4 shapes, grounded in real medoid features; no authority; `stability: LOW`) |
| 1.4 | 2026-07-18 | Level-3 shape→story mapping (descriptive nearest-family; 2/6 active, 4/6 planned `trend_reversal`; weak, no authority); floor extended to validate family ids ⊆ ontology |

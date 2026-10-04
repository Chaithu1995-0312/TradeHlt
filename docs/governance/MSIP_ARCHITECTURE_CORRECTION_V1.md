# MSIP Architecture Correction V1

_Generated 2026-07-14T08:12:37.280834+00:00_  
**TASK_CLASS:** OBSERVATION_ONLY (this document)  
**Supersedes assumptions:** MSIP as mere dynamic config; CRT as 38-feature consumer for transitions

---

## 1. Corrected executable reality

```text
RAW MARKET DATA
        │
        ├──────────────► GOVERNED FEATURE PIPELINE
        │                       │
        │                       ▼
        │               38 CANONICAL FEATURES
        │                       │
        │                       ▼
        │               OTHER CONSUMER SURFACES
        │               (journal @ TRADE_OPENED, models when enabled)
        │
        └──────────────► CRT-LOCAL INTERPRETATION
                                +
                         CRT STATE MEMORY
                                +
                         CRTConfig / POLICY (HOW)
                                │
                                ▼
                         9-STATE CRT LIFECYCLE (single active candidate)
                                │
                                ▼
                         EVENTS / TRADE OUTPUT
```

**PROVEN:** CRT transition guards are not primarily driven by the 38-dim vector.

---

## 2. MSIP problem statement (corrected)

MSIP is the program to introduce a **continuous market-state interpretation layer**
from **governed WHAT** quantities, producing a **MarketStateVector** for observation
and research, **without** initially mutating CRT opportunity-lifecycle behavior.

MSIP is **not**:

- dynamic config loading alone  
- automatic CRT rewrite  
- mandatory concurrent candidates  
- claim that CRT already implements 38→HOW→decision  

---

## 3. Adjudicated design questions

| Question | Decision |
|---|---|
| MarketStateVector = continuous market state independent of opportunity ownership? | **YES** |
| Computed from governed WHAT quantities? | **YES** (primary); CRT-local math only after parity or new registration |
| CRT remains stateful opportunity-lifecycle consumer? | **YES** (near term; CLOSED boundary) |
| CRT private memory outside MarketStateVector? | **YES** |
| Policy produce dimensions without mutating CRT lifecycle? | **YES** (shadow HOW interpretation) |
| Migration begin in SHADOW mode? | **YES — REQUIRED** |
| Keep current CRT as comparison path? | **YES — REQUIRED** |
| Concurrent candidates separate from MarketStateVector introduction? | **YES — separate later decision (B), not phase-1 of C** |

---

## 4. Relation to architecture decision C

Adjudication V1 selects **Option C**: separate continuous market-state observation
from CRT opportunity lifecycle. MSIP shadow is the named next design phase under C.

**Not authorized now:** CRT cutover, threshold program as primary work, CRT replacement.

---

## 5. Authority

Design correction only. No production authority. No economic claims.

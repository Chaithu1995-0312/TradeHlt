# Mother-range inside-close holdout (MC-MRANGE-XAUUSD-M15-V1)

Point-in-time. Not a living finding. Contract sha256 `94d1ae03…`.

Geometry was frozen in [`docs/research/mother_range_trade_object.md`](../research/mother_range_trade_object.md) **before** this ledger existed. Single pass. No retune.

| Split | n | gross mean R | net mean R | win rate | PF |
|---|---|---|---|---|---|
| Train (not the gate) | 240 | −0.159 | −0.252 | 0.346 | 0.776 |
| **Holdout** | **59** | **+0.225** | **+0.204** | 0.373 | 1.386 |
| Holdout long_only | 59 | −0.093 | — | — | — |

Holdout start: `2025-12-24 19:15:00` (corpus idx 37820). F-086's 236-bar stride holdout was **not** used.

**Verdict:** `DIAGNOSTIC_PASS_NOT_ECONOMIC` (holdout n≥30, net>0, PF>1, beats long_only). `economic_claims_allowed` remains **false** (mt00/mt01 UNRUN).

**E-001:** Train is **negative**. Holdout is **positive**. That sign split is recorded, not explained away. It forbids treating the holdout print as a stable edge. No G001. No production. Does not reopen F-086. Does not rewrite identity L5.

Driver: `python -m research.mother_range`

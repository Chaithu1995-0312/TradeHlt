# XAUUSD Identity Certification (1-month shadow)

> **L3 occupancy meaning SUPERSEDED 2026-08-23.** This run called `process_candle(htf_id="")` without `HTFBuilder` / `initialise_range`, so occupancy was RANGE on every bar and L3 events were 0. Store round-trip numbers below remain true of *what was written*. Corrected 1-month HTF dry-run: `results/identity_cert/xauusd_m15_1m_htf.md`. 2-year corpus: [`xauusd_identity_certification_2y.md`](xauusd_identity_certification_2y.md).

**Gate:** `XAUUSD_IDENTITY_CERTIFICATION`
**Status:** **PASS** (written layers; L3 occupancy was RANGE-only — see banner)
**Production approved:** False
**Corpus:** `data/XAUUSD_M15.csv`
**corpus_sha256:** `478b075150935c950ccc749925709db783e337c55c886d6dda1e3ee8b9692c5b`
**Rows:** 2116

| Check | Required | Result |
|---|---|---|
| L0 identities written | Count | 2116 |
| L1 identities written | Count | 2038 |
| L2 identities written | Count | 26494 |
| L3 occupancies written | Count | 2116 |
| L3 events written | Count | 0 |
| RESET events present | YES/NO | NO |
| L4 geometries written | Count | 0 |
| L5 outcomes written | Count | 0 |
| UNIDENTIFIED records | Count | 0 |
| IDENTITY_INCOMPLETE records | Count | 0 |
| IDENTITY_MISMATCH records | Count | 0 |
| CRT process_candle errors (isolated) | Count | 0 |
| Query PRESERVED L0 | Count | 2116 |
| Query PRESERVED L1 | Count | 2038 |
| Query PRESERVED L2 | Count | 26494 |
| Query PRESERVED L3 occupancy | Count | 2116 |
| Query PRESERVED L3 events | Count | 0 |
| Query PRESERVED L4 | Count | 0 |
| Query PRESERVED L5 | Count | 0 |

## Gate (not production)

```text
L0–L5 recoverable via IdentityQuery  (of what was written)
No recompute path on QUERY
No HEAD dependency on QUERY
No identity mismatch
```

**Certification:** PASS
**Production Approved:** NO (gate requires this report; promotion is a separate authorization).

## Errors

- none

## Notes

- WRITE used FeaturePipeline / FeatureStateEncoder / CRTEngine as producers.
- QUERY used IdentityQuery / Identity Check only.
- L5 not produced (engine TRADE_OPENED has no outcome until close).
- 1-month corpus first; 2-year corpus is not this run.
- Not production. Not live-spine. Grants no G001.

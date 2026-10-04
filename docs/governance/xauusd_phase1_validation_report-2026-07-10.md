# XAUUSD Phase-1 Validation Report

Generated (UTC): `2026-07-10T15:13:47Z`

**Verdict:** `PASS_CONTENT_ADDRESSED`

Promotable to AUTHORITATIVE: **False**

Phase-1 content-addressed validation can PASS while remaining NOT AUTHORITATIVE / NOT VALIDATED / NOT ECONOMICALLY_ADMISSIBLE until independent open-time proof + broker calendar certification + full E-MT-01 mutation score. User promotion decision still required.

## Gate statuses

| Gate | Status |
|---|---|
| `G0_BINDING` | PASS |
| `G0b_L1_FULL_STREAM` | PASS |
| `G1_SOURCE_PROVENANCE` | PASS_WITH_RESIDUAL |
| `G2_TIMESTAMP_OPEN_TIME` | PASS_CONSISTENT_UNPROVEN_LABEL |
| `G3_BROKER_SESSION_HOLIDAY` | PASS_OBSERVED_PATTERN |
| `G4_VOLUME_SEMANTICS` | PASS_DECLARED |
| `G5_ADVERSARIAL_APPLICABLE` | PASS |

## Residuals

- G1: no per-fetch session log
- G2: open-time label not dual-fetch proven
- G3: independent broker calendar UNPROVEN; config session mismatch
- G5: 8 FC classes still detector-less (temporal/identity contract)

## Binding (unchanged)

```json
{
  "path": "data/mt5/XAUUSD_M15.csv",
  "sha256": "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56",
  "status_remains": "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION"
}
```

Machine twin: `docs/governance/xauusd_phase1_validation_report-2026-07-10.json`

Authority: research/governance only. Grants no economic claims.

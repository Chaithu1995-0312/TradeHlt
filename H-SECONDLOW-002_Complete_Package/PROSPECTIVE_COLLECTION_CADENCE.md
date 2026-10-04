# Prospective Collection Cadence (H-SECONDLOW-004)

**Status:** ACTIVE  
**Date:** 2026-07-07

## Standing mode

**Continue collecting** — no outcome re-runs or v0.2 changes until more ledger events accrue.

## Monthly (or after ~3 new POST events)

```powershell
# 1. Fetch — use end = today+1; if REJECT (future bar / gap), retry with end = last good UTC day
python scripts/data/fetch_and_verify_mt5.py --symbols XAUUSD --timeframes M15 --start 2024-05-22 --end YYYY-MM-DD --out data

# 2. Append new POST_DISCOVERY events (idempotent)
python H-SECONDLOW-002_Complete_Package/scripts/research/append_secondlow_prospective_ledger.py

# 3. Dual-track update ONLY when ledger grows (≥3 new events or monthly)
python H-SECONDLOW-002_Complete_Package/scripts/research/run_h_secondlow_004_prospective_update.py
```

## Current snapshot (2026-07-07)

| Field | Value |
|---|---|
| Ledger events | 14 |
| EXPOSED (depth ≥ 1.0) | 3 |
| Last dual-track update | `prospective_update_001` — WATCH / Tier 1 |
| Corpus end | 2026-07-06 23:45 UTC |
| Corpus hash | `486cf3616415ff86` |

## Fetch pitfalls (2026-07-07)

1. `--end 2026-07-08` can quarantine: future bar ahead of wall-clock + Jul-3 gaps.
2. Jul-4 2026 holiday gap (Jul-3 20:00 UTC → Jul-6 01:00 reopen) registered in `dataset_integrity.session_calendar` (`2026-07-04` holiday + XAUUSD `known_gaps` entry). Use `--end 2026-07-07` after that fix.
3. Do not use quarantined files without review.
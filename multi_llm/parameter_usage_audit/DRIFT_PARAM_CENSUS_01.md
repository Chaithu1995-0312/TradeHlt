# DRIFT-PARAM-CENSUS-01 — Completeness census floor stale

**Status:** OPEN (pre-existing) — filtered from fail-closed A diff
**Opened:** 2026-09-19

## Evidence

Floor pins `total=24` `complete=1`. HEAD corpus: `total=25` `complete=2`.
Delta: `configs/production/v4_crt_sot_2026_08.json` (at HEAD). Off-by-one, not off-by-four. Not caused by A.

## Resolution

Refresh the floor's `total` and `complete` counts to match HEAD, **or** pin the floor to a named corpus SHA so future additions do not silently invalidate it. **Preference: pin to SHA.**

A numeric floor that drifts whenever the corpus grows will go stale again on the next config add. Pinning to a SHA makes the floor a fact about a specific state, not an assertion about the whole corpus.

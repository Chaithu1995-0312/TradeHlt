# DRIFT-PARAM-REACHABILITY-01 — Reachability artifact missing kill fields

**Status:** OPEN (pre-existing) — filtered from fail-closed A diff
**Opened:** 2026-09-19

## Evidence

HEAD CRTConfig already has `displacement_origin_kill_enabled` and `displacement_origin_kill_precedence`; governance JSON matrix lacks both (51 vs 53). Baseline red with HEAD `state_identity`. Not a patch side effect.

## Pattern (not just the two fields)

Two fields is the observable delta; the underlying pattern is **matrix-vs-code drift** — same class as the `threshold_refs` dead / `crtconfig_duplicate_dead` annotations (two records of one fact, silently diverging). Governance matrix is not updated when code adds config fields.

## Resolution

Re-sync the current two fields **and** add a check that flags future divergence, not just a one-shot re-sync.

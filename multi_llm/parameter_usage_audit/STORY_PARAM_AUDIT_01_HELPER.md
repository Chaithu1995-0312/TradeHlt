# STORY-PARAM-AUDIT-01-HELPER — crt_config_for_test soft-fill residual

**Status:** OPEN — **does not block commit A**; residual after fail-closed A
**Parent:** STORY-PARAM-AUDIT-01 / sibling of STORY-PARAM-AUDIT-01-ADDENDUM
**Opened:** 2026-09-19

## Symptom

`tests/helpers/crt_config.py` → `crt_config_for_test(**overrides)` soft-fills `_AUTHORITY` for any of the four Tier-1 keys not passed by the caller. Missing keys never fail; they are silently filled.

## Scope

Test helper only — not production resolver / CRTConfig fields (those are already fail-closed under commit A).

## Class

Residual defect class (same family as silent defaults, one layer up in the test harness). Not a SIGNAL that blocks A unless the conditioned suite diff shows soft-fill-driven green→red on the four keys.

## Hardening options (deferred)

- **A** — require all four keys at every call site
- **B** — named presets only
- **C** — read prod authority JSON (preferred)

## Not blocking A

Log and leave open. Revisit after `FULL_SUITE_DIFF.md` lands.

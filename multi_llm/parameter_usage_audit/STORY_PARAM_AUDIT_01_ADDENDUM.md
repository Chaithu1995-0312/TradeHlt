# STORY-PARAM-AUDIT-01-ADDENDUM — Provenance bare CRTConfig()

**Status:** OPEN (design) — **out of scope for fail-closed commit A**
**Opened:** 2026-09-19
**Parent:** STORY-PARAM-AUDIT-01 / Path A fail-closed

## Finding

`src/config_layer/crt_config_provenance.py:235` (`schema_fingerprint`) and `:244` (`compare_surfaces`) construct `CRTConfig()` with no arguments.

- Pre fail-closed: soft defaults → fingerprint/compare saw the *default shape*, not a loaded config.
- Post fail-closed: both raise `TypeError`.

**Class:** pre-existing provenance defect **exposed** by fail-closed (expected-caused-by-A). Not a fail-closed regression.

## Design question (answer before any fix)

Read both function bodies, callers, and docstrings first. If docstrings already name the intended fingerprint target, that is the answer; if not, write the answer into the docstring first, then implement.

1. **Schema** (field names + types) — what `schema_fingerprint()` should do → class introspection; no instance.
2. **Loaded config** — what `compare_surfaces()` should do → pass the actual config in; signature change.
3. **Fresh canonical instance** — **REJECTED.** This is the current behavior and is almost certainly wrong. Kept only as the rejected alternative, not a live option.

## Blast radius

Governance-adjacent path was fingerprinting defaults rather than loaded config. Downstream consumers of those fingerprints may be affected.

## Not in commit A

No provenance code change in fail-closed patch.

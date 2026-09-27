# Schema Evolution & Preservation Workflow

> Charter for `docs/governance/schema_version_registry.json`. Enforced by
> `tests/governance/test_schema_version_registry.py`. Complements — does not restate —
> `CANONICAL_LAYER_IDENTITY_CONTRACT.md` and `STORAGE_PRESERVATION_CONTRACT.md`, which define
> *what* preservation means; this contract governs *how a version bump propagates*.

## Why this exists

The `v5.0 → v6.0` feature-schema bump (F-107, `CH-schema-v6-normalization-identity`, 2026-09)
changed `src/features/feature_schema.py`'s `SCHEMA_VERSION` but did not propagate to
`src/identity/tokens.py`'s closed vocabulary or `src/identity/certify.py`'s emitted label. Nothing
caught it — no floor existed that even knew those two facts were supposed to move together. That
is the same silent-gap class as F-056 / F-079 / F-083 / F-085: a skipped propagation is
indistinguishable from an unnecessary one until something declares the edge between them.
Discovered and fixed 2026-09-18 — the worked example below.

## The idea

Every versioned schema in this repository is a **declaration token** (one Python symbol that is
the single source of truth for "what version is this") plus a set of **downstream slots** — every
other place that must agree with, accumulate, or derive from that token. A slot is always exactly
one of four kinds, and the kind fixes its obligation on a bump:

| Kind | Obligation | Violated-by |
|---|---|---|
| `TRACKS_HEAD` | must **equal** `current_version` | a hardcoded literal that didn't move |
| `ACCUMULATES` | must **contain** every version ever declared (`history ∪ {current_version}`) | a closed vocabulary that forgot to add the new one |
| `FROZEN` | must **never change** — it records history | an archive value silently "corrected" to match HEAD |
| `DERIVED` | recomputed from the declaration; must match | a stale cached hash |

This taxonomy is schema-agnostic even though the schemas are not — it is what lets one registry
and one floor test cover the feature schema, identity tokens, and (once adjudicated) config
`schema_version`, without a bespoke check per schema.

**`ACCUMULATES` is not `TRACKS_HEAD` with extra steps.** Dropping an old version to add a new one
orphans every record already written under it — the exact truth-deletion `CLAUDE.md §6.2 rule 4`
forbids. Versions are added, never replaced.

**A `FROZEN` slot inside a closed/frozen contract doc is not edited in place.** Correcting it
follows the same append-only discipline as any other closed-artifact correction: a dated
`CORRECTED` marker is appended beside the original sentence, the original stays byte-identical, and
the floor reads the *last* such marker. See `STORAGE_PRESERVATION_CONTRACT.md`'s `schema_version`
row for the live example.

## The procedure

1. **Classify the change.** Is a `current_version` symbol moving? If the schema isn't yet in
   `schema_version_registry.json`, it's tracked in `unregistered_pinned` — register it properly
   before or as part of the bump (the completeness ratchet in the floor test will refuse a new
   `*SCHEMA_VERSION*` symbol that is neither registered nor pinned).
2. **Enumerate slots from the registry.** Do not rediscover them by grep each time — that is
   exactly the step that was skipped for v6.0. The registry is the list.
3. **Propagate by slot kind** — using the table above, not ad hoc judgment per site.
4. **Run the floor:**
   `pytest tests/governance/test_schema_version_registry.py -q`. Where possible, prefer making the
   `TRACKS_HEAD` obligation *structural* (import the canonical symbol instead of hardcoding a
   literal — see `identity/certify.py` below) over merely re-checkable: a check that must be
   re-run to stay true is weaker than one the language enforces.
5. **Record.** Queue story + `assistant_project.md` SESSION LOG, as for any governed change.

## Worked example — F-107's v6.0 propagation (2026-09-18)

| Slot | Kind | Before | After |
|---|---|---|---|
| `identity/tokens.py:SCHEMA_VERSIONS` | `ACCUMULATES` | `{2.0,3.0,4.0,5.0}` | `{2.0,3.0,4.0,5.0,6.0}` |
| `identity/certify.py`'s L1 `schema_version` | `TRACKS_HEAD` | hardcoded `"5.0"` | imports `SCHEMA_VERSION` from `features.feature_schema` — structural, not just re-checked |
| `STORAGE_PRESERVATION_CONTRACT.md`'s `schema_version` row | `FROZEN` + append | original `5.0 active` sentence, untouched | + an appended `CORRECTED 2026-09-18` marker naming `6.0` |
| `feature_schema.py`'s `TRADENET_SCHEMA`/`GAUSSIAN_SCHEMA` comments | `TRACKS_HEAD` | `# 48 (schema v5.0)` | `# 48 (schema v6.0)` |
| `test_identity_store.py`'s synthetic `"5.0"` fixtures | *(deliberately unchanged)* | — | a comment now says why: these test store mechanics against an arbitrary token, not "current HEAD" |

Demonstrated both directions, not just asserted: the floor test was run against the pre-fix tree
first (5 failures, matching exactly the 5 rows above) before any fix landed, then again after
(green). A check never shown to fire is the F-079/F-083 class.

**Explicitly out of scope for this pass:** `configs/production/*.json`'s `schema_version` key
(`1.3`×21 / `1.2`×1 / `1.0`×2 / absent×1, no code declaration site tying them together) — recorded
in the registry's `config_schema_version_note`, not adjudicated. Which value is authoritative, and
whether the split is intentional per-generation tiering or drift, is a `§6.2 rule 3` `TruthConflict`
for a future turn, not resolved here.

## Grants no new authority

Registering and propagating a schema-version token changes no feature value, no model weight, no
config, and no trading decision (`§6.5`). It makes drift *visible*, nothing more.

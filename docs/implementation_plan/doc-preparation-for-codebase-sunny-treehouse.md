# Schema Evolution & Preservation Workflow — one mechanism for every versioned schema

## Context

**The prompt:** design a workflow that preserves schema. **The evidence that it is needed:** the
`v5.0 → v6.0` feature-schema bump (F-107, `CH-schema-v6-normalization-identity`) did **not**
propagate into the preservation layer, and nothing detected that.

| Source | Says | Verified |
|---|---|---|
| `src/features/feature_schema.py:317` | `SCHEMA_VERSION = "6.0"` | read |
| `src/identity/tokens.py:16` | `SCHEMA_VERSIONS = frozenset({"2.0","3.0","4.0","5.0"})` | read — **no 6.0** |
| `src/identity/certify.py:194` | emits `"schema_version": "5.0"` beside a live `FEATURE_ORDER_HASH` | read |
| `docs/governance/STORAGE_PRESERVATION_CONTRACT.md:198` | ``5.0`` active | read |
| `tests/test_identity_store.py` | pins `"5.0"` at 6 sites | read |
| `src/features/feature_schema.py` (`TRADENET_SCHEMA`/`GAUSSIAN_SCHEMA`) | comments say `48 (schema v5.0)` | read |

Both hashes are computed **over the feature names** (`:237`, `:248`), and v6.0 renamed two names —
so `certify.py` writes an L1 record carrying a **v6.0 order-hash labelled family 5.0**. That is the
contract's own `Inferred PK` / `HEAD substitution` class (`STORAGE_PRESERVATION_CONTRACT.md:475`,
`:490`), and a genuinely-labelled v6.0 record would be rejected `UNIDENTIFIED` because the token is
not in the frozenset. The identity layer is live and tested (`tests/test_identity_store.py`,
`src/research/evidence/queries.py`) — this is not dead code, so `unreachable ≠ bug` does not apply.

**De-risking fact, verified not assumed:** no identity store exists on disk (`data/identity*`
absent; `IdentityStore.__init__` takes an explicit root). There are **no already-mislabelled
records to remediate** — the fix is forward-only.

**Scope decision (user):** one workflow covering **all** versioned schemas, not just the feature
schema. That is justified because the disease is repo-wide — 25+ independent `*SCHEMA_VERSION*`
declarations across `src/` with no registry tying any of them together, and the production configs
already carry **three** live `schema_version` values (`1.3`×21, `1.2`×1, `1.0`×2, absent×1).

---

## The design idea

Every versioned schema here is a **declaration token** plus a set of **downstream slots**. Every
slot is exactly one of four kinds, and the kind determines its obligation on a bump:

| Slot kind | Obligation | v6.0 instance |
|---|---|---|
| `TRACKS_HEAD` | must **equal** the current version | `certify.py:194` — **violated** (still `5.0`) |
| `ACCUMULATES` | must **contain** every version ever declared | `tokens.py:16` frozenset — **violated** (missing `6.0`) |
| `FROZEN` | must **not** change; it records history | archived records — correctly untouched |
| `DERIVED` | recomputed from the declaration; must match | `SCHEMA_HASH`, `FEATURE_ORDER_HASH` |

**This taxonomy is the whole workflow**, and it is what makes one mechanism cover feature, config
and JSONL/token schemas: the slot kinds are schema-agnostic even though the schemas are not.

It also explains the failure exactly: the v6.0 bump **treated a `TRACKS_HEAD` slot as `FROZEN`, and
an `ACCUMULATES` slot as complete**. To a reviewer those are indistinguishable from correct work —
the same silent-gap class as F-056 / F-079 / F-083 / F-085, where a skipped propagation looks
identical to an unnecessary one. Only a *declared edge* separates them.

**The repo already does this correctly when it remembers to.** The uncommitted `REM-COST-04` change
in your working tree adds `backtest_g1g2_v2` to **both** `tokens.py` `COST_MODEL_IDS` **and** the
`CANONICAL_LAYER_IDENTITY_CONTRACT.md` table, in one change. The discipline is practiced, just not
enforced. This plan makes it mechanical.

### Patterns reused (nothing invented)

- **`docs/governance/closure_authority_index.json` + `tests/test_closure_authority_index.py`** —
  the machine-readable-registry + floor-test twin. The new registry copies its field discipline
  (required fields, unique ids, referenced artifact must exist, prose index must not contradict,
  a `REQUIRED_*` set so entries cannot silently vanish). Read it before writing the new one.
- **Shrink-only ratchet** — `_MIGRATED_WIRED` (`scripts/analysis/behavior_census.py`),
  `_UNREGISTERED_VECTOR_SLOTS` (F-063). Pins existing debt, forbids growth.
- **`tests/governance/` is already a `GREEN_FLOOR` prefix** (`check_governance_invariants.py`
  `GREEN_FLOOR`, verified) — a test placed there is on the floor automatically, hook == CI by
  construction. No floor-list edit needed.
- **`FeatureSchemaRegistry.check_compatibility`** (`feature_schema.py`) already fails closed on an
  unregistered version — the new registry must not duplicate it, only register the schema it owns.

---

## Phases

### Phase 0 — declare what exists (no behaviour change)

Create **`docs/governance/schema_version_registry.json`**. One entry per versioned schema:

```
schema_id            e.g. FEATURE_CANONICAL, CONFIG_PRODUCTION, IDENTITY_TOKENS,
                     TRADE_IDENTITY, STATE_CONTRACT, ...
declaration          {path, symbol}                     the authoritative token
current_version      the value that declaration must yield
derived              [{path, symbol, over}]             DERIVED slots
slots                [{path, symbol_or_key, kind, note}]  kind ∈ TRACKS_HEAD | ACCUMULATES |
                                                          FROZEN | DERIVED
owning_contract      the doc that governs it (may be null)
history              versions ever declared (feeds ACCUMULATES)
```

Seed it with the schemas whose slots are *known* — `FEATURE_CANONICAL` first, since its slot set is
fully traced above. Every other `*SCHEMA_VERSION*` declaration found by the census goes into the
`unregistered_pinned` ratchet list, **not** silently omitted: the point is that absence is visible.

### Phase 1 — the mechanical floor

Create **`tests/governance/test_schema_version_registry.py`** (auto-on-floor via the prefix):

1. registry parses; ids unique; every declared path exists; `kind` ∈ the closed set.
2. each `declaration` actually yields `current_version` (import the module and read the symbol —
   do not regex the source; a stale comment must not be able to satisfy the check).
3. every `TRACKS_HEAD` slot **equals** `current_version`.
4. every `ACCUMULATES` slot **contains** every entry in `history` ∪ `{current_version}`.
5. every `DERIVED` value recomputes from the declaration and matches.
6. `FROZEN` slots are asserted present-and-unchanged against their recorded value (they are the
   §6.2 rule 4 history guard — the test must fail if someone "helpfully" bumps one).
7. **completeness ratchet:** AST-scan `src/` for module-level `*SCHEMA_VERSION*` assignments; every
   one must be registered **or** listed in `unregistered_pinned`; the pinned list may only shrink.

This is what converts the runbook from prose into enforcement. Land Phase 1 green **against the
un-fixed v6.0 state** by pinning the four known violations as expected-failures with issue notes,
then have Phase 2 remove the pins — so the test is proven to actually fail before it is trusted
(the F-079/F-083 lesson: a check that has never been shown to fire is not a check).

### Phase 2 — execute the workflow once, on v6.0

The first real use of the procedure, not a hypothetical:

| Slot | Action |
|---|---|
| `src/identity/tokens.py:16` | **add** `"6.0"` (ACCUMULATES — add, never replace `5.0`) |
| `src/identity/certify.py:194` | `"5.0"` → `"6.0"` (TRACKS_HEAD). Safe: no on-disk store exists |
| `docs/governance/STORAGE_PRESERVATION_CONTRACT.md:198`, `:200` | `6.0` active, `5.0` → archive |
| `tests/test_identity_store.py` (6 sites) | decide per-site: fixtures asserting *current* move to `6.0`; any asserting *archive-family* behaviour stay `5.0` and get a comment saying so |
| `feature_schema.py` `TRADENET_SCHEMA`/`GAUSSIAN_SCHEMA` comments | `v5.0` → `v6.0` |

**Gate — needs your ruling, not mine:** `STORAGE_PRESERVATION_CONTRACT.md` is **CLOSED / FROZEN
v1.0.0, user-accepted 2026-08-23**. Correcting `:198` is a factual sync, but editing a frozen
closed contract is a §6.2-gated act. I will prepare the edit and **not apply it** without your word;
the alternative is an append-only `CORRECTED` note that leaves the frozen text intact.

Also fix in passing (found, not sought): `src/identity/tokens.py` carries a **mojibake corruption**
in your working tree — `§9.4` became `Â§9.4`, a cp1252/UTF-8 round-trip. And
`FeatureSchemaRegistry.register`'s docstring shows `register(version=…, hash=…)` while the
signature is `feature_order_hash` — the documented call would `TypeError`.

### Phase 3 — the runbook

Create **`docs/governance/SCHEMA_EVOLUTION_CONTRACT.md`**: the slot taxonomy, the 5-step procedure
(classify the change → enumerate slots from the registry → propagate by slot kind → run the floor →
record), and the v6.0 worked example. A **new** doc rather than a §6.2-rule-1 extension because the
doc that would otherwise own it (`STORAGE_PRESERVATION_CONTRACT.md`) is frozen-closed and this is a
*process*, not a preservation requirement. Add one row to CLAUDE.md §2's companion table.

**Deliberately not done:** no new CLAUDE.md `§6.9`. `tests/governance/test_semantic_review_protocol.py`
asserts §6.8's position relative to §6.7/§7, and a numbered-section insertion is a needless risk for
a pointer that fits in the §2 table.

---

## Verification

Preflight per §1.5: `git status --porcelain`, `git stash list`, and
`venv/Scripts/python.exe -c "import sys; print(sys.prefix)"` → `D:\Tradelatest\venv`. **Capture the
floor baseline before touching anything** — last measured 14 failed / 565 passed / 1 skipped;
compare failure **name sets**, not counts.

1. `pytest tests/governance/test_schema_version_registry.py -q` — must FAIL on the un-fixed tree
   (Phase 1 acceptance), then PASS after Phase 2. Demonstrate both, don't assert one.
2. Negative probe per slot kind: remove `"6.0"` from the frozenset → ACCUMULATES check fails;
   revert `certify.py` → TRACKS_HEAD fails; rename a canonical feature in a scratch copy → DERIVED
   fails. A check that cannot be shown to fire is the F-079/F-083 class.
3. `pytest tests/test_identity_store.py tests/test_feature_layer_freeze.py
   tests/test_cost_model_ids_l5_rem_cost_04.py -q`.
4. **Schema-value neutrality:** `SCHEMA_HASH`, `FEATURE_ORDER_HASH`, `CANONICAL_FEATURES` order and
   `feature_dim` unchanged by this work — it relabels and registers, it does not touch the vector.
   Assert the XAUUSD vector SHA is identical before/after.
5. `python scripts/maintenance/check_governance_invariants.py --all` — identical failure-name set.
6. Bookkeeping same turn: queue story filed (append-only, never renumber — ~15 concurrent sessions
   write `build_queue.jsonl`), both `DOC_TRACKING_INDEX.xlsx` copies synced via `shutil.copyfile`
   (never re-run `_build_doc_tracking_index.py`), `assistant_project.md` SESSION LOG entry.

## Hazards

- **Config `schema_version` is out of scope for Phase 2.** Three live values across 21/1/2 configs
  with no code declaration site is a *separate* adjudication — the registry will **record** the
  split (that is the point) but Phase 2 fixes only `FEATURE_CANONICAL`. Do not silently pick a
  winner (§6.2 rule 3).
- **`ACCUMULATES` must never be "corrected" by replacement.** Dropping `5.0` to add `6.0` would
  orphan every archive record — the exact truth-deletion §6.2 rule 4 forbids.
- **No authority earned (§6.5).** This registers and labels schemas. It changes no feature value,
  no model, no config, and grants nothing production authority.
- **Two answers conflicted** ("Fix the v6.0 gap now" + "Design only, no code"). Read as: no changes
  during planning, v6.0 fix included in execution. Say so at approval if that is wrong — Phase 2
  is cleanly separable.

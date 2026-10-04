# CRT Resolver — Wiring Phase

## Context

The resolver expresses roughly half of what the CRT engine knows. Capability is built, indexed, and
consumed by nothing: FM-083 `change_of_character` (vector-bound idx 47, the only feature separating
reversal from continuation) is not declared in the resolver vocabulary; the magnitude banding layer
has an encoder and no importer; three of twelve `CRTState` members are never emitted; `HTFState` +
`ObjectiveStatus` are an orthogonal dimension with zero predicates; and a third of the state space
(`SHADOW_PENDING` / `EXPIRED` / `RESOLUTION`) is unreachable because the declarative language has no
memory-predicate vocabulary — not because the resolver lacks memory.

This phase **links what exists**. Committed output is zero by design; no variant is canonical; no
agreement figure is optimised. Acceptance is structural (§ Done), not statistical.

**Path note:** the brief scopes `src/config_layer/crt_state_resolver.py`; the file is at
`src/features/crt_state_resolver.py` (verified). `src/config_layer/state_identity.py` is a different,
real file. Using the verified paths.

---

## Resolved design questions

**Cause taxonomy — separate, not `RejectReason`.** `state_identity.py:71-78` holds *trade-signal*
rejection reasons. Four have a resolver analogue (`LOW_SCORE` → EXECUTION fail-closed-without-score at
`crt_state_resolver.py:1005-1011`; `OUTSIDE_SESSION` → `session` predicate; `NO_DOUBLE_SWEEP` →
`double_sweep` predicate; `INVALID_STATE` → funnel illegality); `NEWS_FILTER` and `HIGH_SPREAD` have
none; and the causes dominating residual divergence — predicate mismatch, continuous-gate failure,
memory/sticky-dwell divergence, geometry-construction divergence (F-069 Category C = 96.1%) — have no
member at all. Register `ResolverDivergenceCause` for the resolver domain, with a declared
`maps_to_reject_reason` field on corresponding members. Reuse preserved without collapsing two
quantities (§5, the FM-058/SP-001 class).

**Variant cap vs. ablation.** The 8-cap governs *declared live variants* — streams compared for
meaning. The inert-link ablation is a mechanical per-link sweep against a fixed base, linear in links,
not a cross product; §1.3 targets combinatorial search, not mechanical ablation.

**What the selection rule selects for.** Nothing is selected during wiring. Step 2 pre-registers the
**tuning phase's** rule, committed now precisely so the wiring phase cannot contaminate the judgment.
Write it as that, or an implementer produces an empty file.

**Criterion 1 is not reachable in Steps 1–6.** `SHADOW_PENDING`/`EXPIRED`/`RESOLUTION` need the memory
grammar; parent `C1/C2/C3` need the HTF axis. Steps 1–6 close criteria 2–6 and make 1 *measurable*;
1 closes in the Step 7 programs.

---

## Corrected facts carried (not re-derived)

Schema **v5.0 / 48 dims**; any "39-dim" comment is stale. Resolver has **9 states**, six with
non-empty `when:`. **13** `when:`-named features; **10 already strict** via
`FeatureStateEncoder.classify` (`feature_states.py:178-183`), **3 silent** (`retest_flag` FM-061,
`rsi_state` FM-068, `displacement_flag` FM-069). `lineage.vector_key: []` is the schema's declared
unbound marker — conformant, not a bug. The three Class-A features **are** materialised as
non-canonical DataFrame columns (`feature_pipeline.py:596-599 / :1009-1013 / :1030`); the loss is at
the `CANONICAL_FEATURES` filter boundary. `sweep_geometry=htf_range` skip is **entry-only**
(`:920-926`), so `SWEEP.when` **is** evaluated during sticky dwell. Resolver is research-shadow,
**zero production `src/` callers**.

Verified for this plan: `_predicates_match` has a **second call site**, `_check_resolution`
(`:1470-1479`), reading `RANGE.when`. FM-083 states are `BearishCHoCH=-1 / NoCHoCH=0 /
BullishCHoCH=+1`, `depends_on: [break_of_structure, trend_bias]` — both already in the vocabulary
(`market_ontology.yaml:2686-2698`).

**Known red, out of scope:** `test_crt_state_resolver_sweep_geometry.py::test_funnel_sweep_to_displacement_bypasses_pipeline_flag`.
Step 3d edits that file's shared `_base_features`, so verify the **same failure signature** — same
assertion text, same line — not merely "still one failure."

---

## Design: links, variants, comparison surface

Steps 1 and 2 are one design; the surface determines what the schema must carry.

### Link — declaration *and* binding mechanism

A **link** is a config-level switch, **default off**, with a stable `LINK-NNN` id, human name,
rationale, and the surfaces it touches (§1.4). Registered in a new sibling file
`configs/formulas/crt_resolver_links.yaml`, kept out of `market_crt_states.yaml` so the resolver's
consumed config shape stays clean.

**Binding — the piece the previous draft omitted.** Declaration alone does not make a link
disableable. All Step 5 links are predicate-only, so *disabled* must mean the clause is not evaluated:

- A `when:` clause entry may carry an optional `link: LINK-NNN` tag. **Untagged clauses are baseline**
  and always evaluate; **tagged clauses evaluate only when that link is enabled** in the resolved
  variant.
- `CRTStateResolver.__init__` accepts a variant (or an explicit link set), resolves it to an enabled
  link set, and **filters the `when:` blocks at load time**. This is the resolver-side change; it must
  land in Step 2 alongside the schema, not be assumed.
- **Validation runs on the UNFILTERED config.** `_validate_predicates` must see every clause across
  every link, or a typo inside a disabled link's clause stays hidden until someone enables it — which
  would reintroduce the exact silent-gap class this program exists to close.

### Requirement set — per variant, computed AFTER link filtering

The previous draft carried a static `frozenset` computed once at `__init__`, justified by *"a
requirement set that varies with a threshold is itself a silent-gap generator."* **That reasoning is
scoped to `sweep_geometry` and does not transfer to links, where variation is the entire point.** A
link that adds `change_of_character` to a `when:` block makes the set 13 features with the link off
and 14 with it on; a set computed before link resolution is wrong for some variants.

- Compute `_required_when_features` **per resolved variant, after link filtering**, then freeze it for
  that instance's lifetime (still one `frozenset - dict.keys()` per bar).
- Expose it as a read-only property, alongside the resolved link set, so a run's actual contract is
  readable rather than inferred.
- Restate the geometry-independence argument **scoped to geometry only**: within a fixed link set, the
  set does not vary with `sweep_geometry`, because every feature in `SWEEP.when` also appears in
  `RANGE.when`. Keep the entry-only comment — that fact is commonly gotten backwards.

### Variant

`variant_id`, `links: [LINK-NNN, …]`, and a **mandatory non-empty `rationale` stating what the
comparison tests** — §1.2 made mechanical. A rationale that cannot say what will be learned marks a
duplicate, not a variant. Hard cap **8 live variants**, test-enforced.

**Canonical, ratchet-style rather than a red test.** A `_CANONICAL_DECLARATIONS` allowance dict, empty
today. The test asserts every variant with `canonical: true` has an entry carrying a written
justification, and every entry corresponds to a live variant (stale entries go red). A passing test
that records *why* beats a red test that only records *that*.

### Comparison surface

Emits, per bar per variant, `(bar_index, variant_id, state, cause)` — never a scalar.

**Anchor, stated explicitly:** `cause` is always divergence **from the CRT engine**, which remains
execution authority and is the reference during this phase. "No canonical variant" means no variant is
authoritative *among the variants*; it does not mean there is no reference. Pairwise variant-vs-variant
comparison is **stream-identity only** (criterion 6) and carries **no cause attribution** — it answers
"identical or not," nothing more. The two comparisons produce different kinds of claim and must not be
reported in one column.

Derived views: per-CRT-state × per-cause × per-variant attribution against the engine; and pairwise
stream identity distinguishing *same rate, different bars* (genuinely different models) from *same
rate, bar-for-bar identical* (a link is inert — revert it).

### Holdout (§1.5)

Before the **first** comparison runs, cut and seal a holdout slice of the 47,197-bar XAUUSD frame and
commit the pre-registered tuning-phase selection rule. N parallel streams on one frame make max-of-N
optimistically biased — parallel comparison is a more efficient overfitting machine than sequential
tuning, not a safer one. One commit now; unrecoverable afterwards.

---

## Steps

### 1 — Cause taxonomy + comparison surface
Register `ResolverDivergenceCause` with `maps_to_reject_reason` on corresponding members. Build the
N-stream surface, the engine-anchored per-state × per-cause views, and the separate pairwise
stream-identity check. Lands before any link, since every link reports into it.

### 2 — Link/variant schema + resolver binding
`crt_resolver_links.yaml`, loader, **and the resolver-side `when:` filtering described above**
(variant → enabled link set → filtered blocks; validation on the unfiltered config; requirement set
computed post-filter). Tests: cap of 8, canonical ratchet, non-empty rationale per variant, every
referenced `LINK-NNN` exists, stale-link ratchet, and — specifically — that a disabled link's clause
is not evaluated while its vocabulary is still validated. Seal the holdout and commit the selection
rule here.

### 3 — Strict supply contract for the three silent features
Fix every call site **before** tightening, so the repo never goes red.

- 3a `run_crt_state_on_mt5_xauusd.py:100-104,131-136` — add `rsi_state`; replace `enriched[col] = 0`
  with a hard raise (§1.6); fix the misleading warning at `:93-97`.
  **Artifact consequence:** any prior run of this script that hit the 0-fill produced results under a
  different contract — those are **unsound, not superseded**. Record in the Findings entry, not only
  in the diff.
- 3b `validate_crt_state_resolver.py:118-124` — add `change_of_character`, `candle_range`. This is a
  **pre-existing red** (filler omits FM-083, fills v3.0 `wick_size`); reproduce at baseline first.
- 3c `test_crt_state_resolver_b1h_polish.py:74,99,124` — add the three at 0.0. All three assert
  `engine_state_to` injection, which overrides the predicate path, so zeros cannot move them.
- 3d `test_crt_state_resolver_sweep_geometry.py:40` — add `rsi_state: 0.0` to `_base_features`. Inert
  (`rsi_state` is named only by EXECUTION, which no test there asserts). **Verify the known red's
  signature is unchanged.**
- 3e The check itself, in `resolve()` after `feature_states.update(non_vector_features)` (`:378`),
  **not** in `_predicates_match`: the latter runs per-state behind ~10 early returns (`:828-902`) and
  the entry-skip, so a raise fires on an arbitrary bar; it has a second call site
  (`_check_resolution:1479`) the caller never invoked; `resolve()` sits adjacent to the `classify()`
  raise it generalises (`:363-368`) and fails on bar 0.
  Test `feat_dict.keys()`, not `feature_states.keys()` — `classify_value` returns `X_UNMAPPED(...)`
  for garbage (`feature_states.py:166-168`), a value failure, not a supply failure. Message names the
  feature, the states requiring it, and the producing file:line.
  Escape hatch per §1.6: `allow_missing_when_features` name-list, never `strict=False`;
  self-validating (waived ⊆ required, so a stale waiver goes red at construction); exposed as a
  property. Tests must not use it.
- 3f **Threshold-authority scan** (criterion 4 as an invariant, not one deletion). Enumerate every
  threshold the resolver reads and trace each to exactly one registered authority; the check fails on
  any threshold with zero or ≥2. The known instance: FM-068's registered authority is
  `feature_pipeline.rsi_overbought/rsi_oversold` (`market_ontology.yaml:2457`), while
  `market_crt_states.yaml:324-326` declares a second, unregistered pair the parity harness reads.
  Nobody chose to have two → **delete, do not promote to a variant** (§1.2). Same treatment for the
  harnesses' inline `rsi_state` re-derivation (`crt_state_confusion_matrix.py:443-450`,
  `crt_range_rebuild_probe.py:349-357`, `crt_resolver_economic_comparison.py:292-293`): read the
  pipeline column, raise if absent. Gate deletion on the scan showing zero remaining readers.
  **Guard:** these harnesses feed F-069. Before switching, prove the pipeline column ≡ the inline
  derivation bar-for-bar. The guard is pinned to the **underlying matched/total integers
  (41,607 / 47,197)**, never the rounded 88.16% — two different match counts round to that figure.
  If it differs, **stop and report**; do not move a registered finding as a side effect.
- 3g First tests for `_validate_predicates` (currently **zero** coverage) plus the supply-contract
  ratchet, in `tests/governance/test_crt_predicate_supply_contract.py` — auto-enrolled, since
  `GREEN_FLOOR` lists `tests/governance/` wholesale
  (`scripts/maintenance/check_governance_invariants.py:69`). Four negative tests mutating a `deepcopy`
  into `tmp_path` per `test_semantic_registry.py:96-171`, one per branch at `:762-766`, `:770-776`,
  `:783-787`, `:788-794`. Ratchet declares the three non-vector features with FM id, producer
  file:line, and requiring states, two-sided per `test_feature_lineage.py:140-166`.

### 4 — Visibility
`feature_surface_query.py:259` walks 3 of 6 sections — 30 of 65 entries, omitting all 14
`structural_states` (FM-061/068/069/060/083), 19 `rolling_indicators`, 2 `temporal_context`. Promote
`_ITERATED_SECTIONS` (`src/features/registry/__init__.py:40-41`) to public, alias the private name,
import it. **Same step (§6):** fix the co-located binding bug at `:268` — `item.get("vector_key")`
reads top level, but only 5 of 65 entries declare it there; the rest use `lineage.vector_key`.
Widening without this makes the surface delta unattributable. Emit `lifecycle` and vector-binding per
record so `research`-lifecycle identities are visible without reading as enforced.

### 5 — Cheap links, one landing each
All three targets are already vector-bound, so `classify()` already requires them — naming them in
predicates adds zero supply burden.
- **LINK: FM-083 `change_of_character`** — vocabulary entry (`BearishCHoCH/NoCHoCH/BullishCHoCH`) *and*
  ≥1 `when:` clause, since vocabulary alone leaves the dead-permission case criterion 2 kills. Which
  state it gates is a domain decision needing a written rationale (it separates reversal from
  continuation-BOS); propose at implementation, do not assume.
- **LINK: `volatility_regime` (idx 30)** and **LINK: `volume_spike` (idx 38)** — declared in the
  vocabulary, named by zero predicates. Cheapest inert-link probes: predicate-only wiring.

### 6 — Inert-link ablation
Per link, base vs base+link. Bit-identical stream → dead code → revert. Boolean; run before any
statistical framing.

### 7 — Architecture pieces (scoped here, designed separately)
Own design documents: **memory predicate grammar** (`since:` / `age:` / `pending:` — the missing
linkage layer costing a third of the state space); **HTF / Objective as a second predicate axis**
(`HTFState` 5 + `ObjectiveStatus` 4); then **magnitude banding** (FM-071/072/073), contingent on the
gate structure the former establishes. `EXECUTION` currently gates on `rsi_state=NeutralMomentum`, a
crude proxy for what `momentum_magnitude` measures properly — that substitution is the rationale when
banding lands.

Stale comments swept alongside whichever step touches the file: `crt_state_resolver.py:8, :65, :324,
:804` and `feature_states.py:187` say 39-dim; `feature_pipeline.py:594-595 / :1004-1005 / :1018-1019`
claim no FM id (FM-068/069/061); `:1033` calls `double_sweep` unregistered (it is **FM-060**,
vector-bound).

---

## Done (§4 — structural, all checkable at zero output)

1. All **12 `CRTState` members** emitted ≥1× — **closes in Step 7**, made measurable by 1–6.
2. Every vocabulary entry named by ≥1 predicate (kills `volatility_regime`, `volume_spike`).
3. Every `when:`-named feature strictly supplied; missing raises naming feature, states, producer.
4. Zero duplicate threshold declarations — enforced by the Step 3f scan, not one deletion.
5. Every link individually identified and individually disableable **through the Step 2 binding**.
6. Inert-link sweep passes: no link produces a bit-identical stream.

---

## Verification

Repo uses `venv/Scripts/python.exe`; `pyproject.toml:29-31` sets `pythonpath`, so bare `-m pytest`
from the root resolves imports.

```bash
venv/Scripts/python.exe -m pytest tests/test_crt_state_resolver_sweep_geometry.py tests/test_crt_state_resolver_b1h_polish.py tests/test_crt_state_resolver_gate_parity.py tests/test_crt_state_resolver_displacement_gate.py tests/test_crt_states_yaml_transition_parity.py -q
```

```bash
venv/Scripts/python.exe -m pytest tests/governance/test_crt_predicate_supply_contract.py tests/test_feature_lineage.py tests/test_semantic_registry.py -q
```

```bash
venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py
```

Baseline first, no edits: record the known red's exact assertion text and line, and F-069's
**matched/total integers**. After Step 3d the red's signature must be identical. After Step 3f the
integers must be identical. After Step 4, diff the emitted surface — the delta must be exactly the
newly-visible identities plus corrected bindings.

---

## Governance

Same turn: §6.2 Findings Mandate entry (ARCH, the F-079/F-056/F-083/F-085 silent-gap class),
**including that prior 0-fill runs of `run_crt_state_on_mt5_xauusd.py` are unsound, not superseded**;
a **`TruthConflict`** for the FM-068 duplicate thresholds (two authorities, one quantity); and a
separate **ARCH/identity** finding for the `RejectReason` taxonomy — *not* a TruthConflict, since it
is two different quantities nearly conflated (FM-058/SP-001 class). §6.4 topic sync; §6.3 citation
sync; §6 SESSION LOG. **Grants no new authority** (§6.5) — research-shadow surface, zero committed
output, no ΔG001, no variant canonical; F-069's figure and its `structurally config-unreachable`
determination stand unchanged by design.

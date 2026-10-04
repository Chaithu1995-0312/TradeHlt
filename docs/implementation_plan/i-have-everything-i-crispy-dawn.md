# Layered outcome ontology for the Pipeline-B opportunity scanner

## Context

`scripts/research/opportunity_scanner.py` emits `outcome ∈ {TP_HIT, SL_HIT, TIMEOUT}`. That
vocabulary answers *which exit mechanism terminated the simulation*, not *what the bracket
returned*. On run `20260913_130531` (XAUUSD M15, 94,332 rows) the conflation is severe and
measured:

| fact | count | consequence |
|---|---|---|
| `SL_HIT` total | 92,937 (98.52%) | one label covers 98.5% of the corpus |
| …of which exactly −1.0000R (trail never armed) | **30,797** (33.1%) | a true full stop-out |
| …of which rr > −1 (trail armed and ratcheted) | **62,140** (66.9%) | breakeven-or-better, mislabelled as a stop |
| `SL_HIT` with rr ∈ (−1, 0) | **0** | the split above is *exact*, not approximate |
| `TP_HIT` with rr ≠ 2.0 | **0** | all 1,344 sit on a single atom |

So `SL_HIT` spans two mechanisms of opposite economic sign. Splitting it is the single
highest-value change available, and it needs no re-scan.

**The governing constraint.** `docs/governance/jsonl_claim_catalog.yaml:30-43` registers
`STR-F022-OPPORTUNITIES` (`**/opportunities.jsonl`) as `catalog_stream_status: CONTAMINATED`,
`allowed_cc: [CC-ENVELOPE-SHAPE]`, `meaning_authority: INVENTORY_NOT_MARKET`, and
`CC-F022-CONTAMINATED` (`:284-291`) refuses *"This trade was profitable"* against this stream's
`outcome` / `rr_achieved`. Writing `ECON_MAJOR_WIN` onto these rows is that refused claim turned
into queryable data. The AN record (`run_linkage_registry.json`) also carries
`economic_claims_allowed: false`.

**Intended outcome.** A vocabulary boundary that delivers the mechanical and arithmetic layers
immediately from the existing artifact, while keeping economic word-labels on a substrate that
can actually support them.

---

## The one architectural rule

> **Number-words on anything scanner-derived. World-words only where a cost basis exists.**

`RR_1_TO_2` is a statement about a stored float and a versioned band table — recomputable,
falsifiable, closes nothing about the world. `MAJOR_WIN` is a statement about the world.

The blocker on world-words is **not the file path** — it is that this stream has no cost model.
SEM-018's economic label is `y_R_net = gross − cost_r(exit_kind)`; there is no `cost_r` here
(`cost_basis: NONE`). Renaming the path to a sidecar does not create one. So `ECON_*` labels are
deferred to the episodes substrate (Phase 3), not relocated to a differently-named file.

Two further reasons the gross number cannot carry an economic reading, both already registered:

- **The trail is non-causal.** `opportunity_scanner.py:84-89` arms the stop from bar *i*'s own
  `high`, then tests bar *i*'s own `low` against it. SEM-019's `mathematical_definition`
  (`market_ontology.yaml:3788`) forbids exactly this; F-087 measured that same-bar ambiguity band
  at **0.261R** against a policy spread of 0.021R (12–15×). All 62,140 armed rows sit at the
  optimistic edge of a band far wider than any effect worth banding for.
- **L-003J freeze.** `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md:21` makes
  `(Y_scanner, Y_oracle)` the primary measured object. A five-layer vocabulary on `Y_scanner`
  alone would promote a component to primary.

---

## Layers in scope

Layer 4 (opportunity quality) is **dropped this phase** — verified unbuildable, see Deferred.

### Layer 1 — Exit mechanics (`exit_mechanism`)

Additive field. Do **not** rename `TP_HIT`/`SL_HIT`/`TIMEOUT`: ~20 consumers read `outcome` by
name, `build_rr_dataset.py:97` pins the three literals in a docstring, and
`opportunity_scanner.py:246` increments `counts[result["outcome"]]` against a dict seeded with
exactly those three at `:188` — a fourth literal raises `KeyError`.

| value | derivation (Phase 1, from the existing file) |
|---|---|
| `TP_EXIT` | `outcome == "TP_HIT"` |
| `ORIGINAL_STOP_EXIT` | `outcome == "SL_HIT"` ∧ `abs(rr_achieved + 1.0) < 1e-9` |
| `TRAIL_STOP_EXIT` | `outcome == "SL_HIT"` ∧ `rr_achieved > −1.0` |
| `TIMEOUT_EXIT` | `outcome == "TIMEOUT"` |

Companion field `trail_state ∈ {TRAIL_NEVER_ARMED, TRAIL_ARMED}` — same predicate, stated as the
trail fact rather than the exit fact.

**Why the derivation is exact, and why it must still be tested.** The trail arms only at
mfe_r ≥ 0.5 (`:84-89`); once armed, `trail_stop` is strictly better than `sl`, so `rr > −1`;
never armed leaves `trail_stop == sl`, so `rr == −1` exactly. Verified: 0 rows in (−1, 0), and
0 of 30,797 `−1.0R` rows have mfe_r ≥ 0.5. **This holds only because the scanner has no adverse
fill** — under SEM-016 a gap-through stop books below −1R (F-084 measured −1.3425R). Encode as a
fail-closed invariant test, never an assumption.

**Phase-1 limitation.** `TP_EXIT` cannot be split into a clean target touch (`:124-135`) versus
the trail-guard path that honours TP when `trail_stop >= tp` (`:106-118`). Both emit rr = 2.0
exactly; the distinguishing state was discarded. Phase 2.

### Layer 2 — RR bands (`rr_band`)

Your four bands, completed to be exhaustive and mutually exclusive over ℝ ∪ {NaN}. Half-open
`[lo, hi)`, ordered, first match wins.

| band id | interval | n (this run) |
|---|---|---|
| `RR_UNDEFINED` | NaN / None | 0 |
| `RR_BELOW_NEG1` | (−∞, −1.0) | 0 — *structurally unreachable here, not under SEM-016* |
| `RR_EQ_NEG1` | [−1.0, −1.0] atom | 30,797 |
| `RR_NEG1_TO_0` | (−1.0, 0.0) | 0 — *structurally unreachable here* |
| `RR_0_TO_1` | [0.0, 1.0) | 60,774 |
| `RR_1_TO_2` | [1.0, 2.0) | 1,366 |
| `RR_GE_2` | [2.0, +∞) atom in practice | 1,344 |

Rules: every emission carries `band_table_id: BT-RR-ECON-V1`; a zero-population band prints as
`STRUCTURALLY_UNREACHABLE` and is **never omitted** (SEM-019 `:3829` makes exactly this point —
an absent row and an empty row are indistinguishable in a table and only one is evidence); atom
bands report a tie-count. Use exact equality ±1e-9, not the original `≤ −0.99` float-fudge.

Optional split of `RR_0_TO_1` at 0.05 (6,593 rows below) if a flat band is wanted — but call it
`RR_FLAT`, not `BREAKEVEN`: breakeven is a cost-net concept and there is no cost model here.

**Declared collision.** `src/training/stage1_dataset_builder.py:84-98` `RR_BUCKETS` already bands
this axis as `LOSS/SCRATCH/BASE/STRONG/OUTLIER`. Do **not** harmonize by renaming — that breaks a
training-dataset schema cosmetically. Subordinate both to a band-table registry:
`BT-RR-STAGE1-V1` (incumbent, frozen, described as-is) and `BT-RR-ECON-V1` (new). The collision
becomes a declared fact rather than a silent one.

### Layer 3 — Path capture

`capture = realized_r / mfe_r`, but the emitted `mfe` is **exit-truncated** — accumulated at
`opportunity_scanner.py:97-100` inside the forward loop, which returns from inside that loop. A
bar-2 stop-out measures mfe over 2 bars, not 40. The denominator is therefore biased small and
capture biased toward 1.0.

- **Name it `exit_bounded_capture`**, never `capture_ratio`. SEM-020's `mathematical_definition`
  (`market_ontology.yaml:3856`) fixes MFE_r as horizon-agnostic; reusing the name with a truncated
  denominator silently redefines a `MATHEMATICALLY_DEFINED` node and trivializes its own validation
  rule at `:3883`.
- **Always emit `mfe_basis: EXIT_TRUNCATED`** alongside. This is the highest-value single field in
  the design — it is what makes the number honest and what lets Phase 3 supersede it cleanly.

States before bands — the proposed `GIVEBACK (<20%)` band silently swallows a third of the corpus:

| state | condition | n |
|---|---|---|
| `CAPTURE_UNDEFINED` | `mfe_r ≤ 1e-9` | 1,491 |
| `CAPTURE_UNSTABLE` | `0 < mfe_r < 0.05` | 4,007 |
| `CAPTURE_NEGATIVE` | `mfe_r > 0 ∧ rr < 0` | **29,339** |
| `CAPTURE_VIOLATION` | `capture > 1` | defect — count, never average |
| banded | otherwise | EFFICIENT >0.8 / GOOD 0.5–0.8 / MODERATE 0.2–0.5 / GIVEBACK <0.2 |

Reuse rather than reimplement: `src/research/oracle/exit_analysis.py:165-175` `capture_ratios()`
(vectorized, NaN where `mfe_r <= 1e-9`) and its `capture_ratio_violations` counter (`:234`,
`:257-264`); `src/analytics/metrics_oracle.py:270-279` `capture_ratio()` / `giveback()`.
Summarize by **median (p50/p90), never mean** — `exit_analysis.py:231-232` already does.

**Unit trap to close.** `rr_achieved` is in R; `mfe`/`mae` are in price
(`opportunity_scanner.py:84-100`, no division). `capture_ratio(row["rr_achieved"], row["mfe"])`
is dimensionally wrong and will never raise — it just returns a plausible number off by
`risk_distance`. `risk_distance` is computed at `:211` and discarded; it equals
`abs(entry - sl)`. **Emit it.** Cheapest defect-closing change in the design.

### Layer 5 — Census

Counts alone reproduce the frequency illusion the catalog already names (`:39-41`). Every census
row must carry:

1. **Effective n, computed not asserted.** 47,166/direction ÷ horizon 40 ≈ 1,179; F-086's
   independently measured figure is ≈941/direction. Print raw and effective side by side.
2. **Direction split, always** — F-086 shows gold's drift makes long/short structurally different
   (`htf|long` flips sign entirely vs `htf|short`).
3. **The basis triple**: `exit_kernel` (SEM-037), `mfe_basis`, `cost_basis: NONE` — the last is by
   itself sufficient to forbid the word "profitable".
4. Per-band support: tie-count at atoms, min/max, `saturated` flag above 5% mass on one value.
5. Structurally-unreachable bands marked, not omitted.
6. **The refusal, printed in the header** (`CC-OPP-BAND-NOT-ECONOMIC`), so a reader quoting a row
   has already been handed it.

Reuse `scripts/analysis/phase1_shadow_create_economic_census.py:419` `bucket_table(rows, key,
dir_key, h=20)` → markdown with n/E/lift/power. **Caution on**
`src/research/forensics.py:200-220` `_loss_mechanisms`: it ranks by `r_lost_pct`, which here is
dominated by the 30,797 −1.0R atom and answers "the stop" — true and useless. Rank *within*
`exit_mechanism`.

---

## Governance registration (blocking, dependency-ordered)

Ordering is mechanically enforced, not merely doctrinal:
`tests/test_jsonl_claim_catalog.py:163` requires every `meaning_authority` id to ground as a NOUN,
and `semantic_grounding.py:470-487` grounds an ontology id only once it is declared in
`market_ontology.yaml`. **Ontology node first, catalog second.**

1. **SEM-037** `SCANNER_TRAILING_EXIT_KERNEL` in `market_ontology.yaml` →
   `execution_behaviours`. `semantic_category: ExecutionBehaviour`,
   `knowledge_status: MATHEMATICALLY_DEFINED`. All 25 `semantic_node_required_fields` present,
   `version` an `int`, list fields `[]` never null, `evidence`/`origin` non-empty. Its most
   important content is the two defects as `validation_rules`: non-causal arming (`:84-89`) and
   the same-bar SL-first tie-break with the TP-honouring guard (`:106-118`, which produces 1,366
   rows labelled `SL_HIT` whose path reached ≥2R). Put the measured support
   `{−1.0} ∪ [0, 1.5] ∪ {2.0}` in `epistemic.known_invariants`.
2. **Refine SEM-020 in place** (do not mint): add `mfe_basis` as a required input plus the
   degenerate-case rules. Bump `version`, not `knowledge_status`.
3. **Band-table registry** — `BT-RR-STAGE1-V1`, `BT-RR-ECON-V1`. Data, not ontology.
4. **Claim catalog** + regenerate `data/jsonl_claim_catalog.jsonl` in the **same commit**
   (`tests/test_jsonl_claim_catalog.py:265` byte-compares it):
   - `CC-OPP-BAND-RESTATEMENT` (**CAN**) — *"The stored `rr_achieved` on this row falls in
     half-open band B of band table `BT-RR-ECON-V1`."* Add to `allowed_cc`. The only new CAN this
     stream gets.
   - `CC-OPP-BAND-NOT-ECONOMIC` (**CANNOT**) — *"Therefore this detection won / lost / hit full
     target / captured its move / the win rate is X."*
   - A stream row for the Phase-1 sidecar carrying `catalog_stream_status: CONTAMINATED`,
     `primary_source` pointing at the opportunities path (the key exists — see
     `STR-FINDINGS-EXPORT:193`), and a `forbidden_joins` row. Without this the sidecar grounds
     `UNKNOWN`, which looks like a pass — contamination laundering by path rename.
5. Per-node pin in `tests/test_semantic_registry.py`, `test_sem_037_*` style (see
   `test_sem_032_*` at `:199-211`).

Registering SEM-037 before its consuming code exists is **normal** here — SEM-018 and SEM-019 both
landed that way. Do not let step 1 block on step 6.

---

## Build phases

**Phase 1 — derive only, no scanner change.** A read-only deriver over
`logs/XAUUSD/20260913_130531/opportunities.jsonl` producing the sidecar: `exit_mechanism`,
`trail_state`, `rr_band`, `risk_distance`, `mfe_r`/`mae_r` (tagged `EXIT_TRUNCATED`),
`exit_bounded_capture` + state, `band_table_id`. A1's sha256 binding and `TR-PIPEB-STRAT-01` are
untouched.

**Phase 2 — scanner emit + re-scan.** Add `exit_mechanism` (5 values, splitting `TP_EXIT` into
`TARGET_TOUCH` / `TARGET_VIA_TRAIL_GUARD`), `risk_distance`, `trail_armed_bar`, `ratchet_count`,
`activation_price`, `exit_level`.
- Top-level keys are additive-safe (no consumer asserts an exact key-set). Keys inside `features`
  are **not** — that is the 48-dim canonical contract.
- **Extend `src/research/episodes/projectors/detection.py:27`'s `_STREAM_DIAGNOSTIC_KEYS` in the
  same change**, or the new fields escape quarantine — precisely the failure mode this design
  exists to prevent.
- Add a **second** counter dict rather than widening `counts` at `:188`; the INFO log at
  `:248-253` hard-codes the three names and `compress_logs_for_llm.py` may parse that line.
- Re-scan writes to a new `run_id` directory (`:169`, `:212`), so the binding is safe — **unless**
  someone passes `--run-id 20260913_130531` and overwrites in place. There is precedent for that
  accident (TR-SHADOWMEM-01's census.json hash is recorded as UNRECOVERABLE). Make the scanner
  fail closed when the target run directory exists. Register as `TR-PIPEB-STRAT-02` against the
  same AN.

**Phase 3 — horizon substrate (deferred).** `horizon_mfe_r`, `horizon_mae_r`,
`reached_{0_5,1,2,3}R` via `horizon_excursion()` (`forward_walk.py:339-388`), which already
returns these R-normalized. Not a second exit kernel — it never exits, so it does not trip the
`policy.py:3-7` drift rule. This is what finally makes Layer 4 and the `ECON_*` vocabulary legal,
on the episodes `LabelSet` (`src/research/episodes/policy.py:58-93`), which carries
`exit_policy_hash` + `cost_model_hash` + `evaluator_hash` + `protocol_id`.

---

## Deferred, with reason

- **Layer 4 (opportunity quality).** Unbuildable on the emitted `mfe`. Verified: **0 of 30,797**
  full-loss rows have mfe_r ≥ 0.5R, because arming *requires* mfe_r ≥ 0.5 — so the
  `FULL_LOSS × TARGET_OPPORTUNITY` cell that motivates the layer is empty by construction. On the
  truncated basis it returns "bad market" on 100% of full losses regardless of the market.
  Rebuilding it on `horizon_excursion` is **RECOMPUTE, not RECOVER** (`goal.md` invariant 8): the
  un-truncated MFE was never computed and never stored. The corpus is hash-pinned
  (`4d73f5ce…`) so the recompute is reproducible, but `code_state: "UNIDENTIFIED"` on the trace
  means the producing code is unidentified. **The diagnostic is recoverable as a question, not as
  a value.**
- **`ECON_*` world-words.** Phase 3, on the episodes substrate. Not a path choice — a cost-basis
  requirement.
- **Refining SEM-018** to carry a `y_R_band` output: belongs with Phase 3.

---

## Verification

Read-only probes and mechanical floors. The invariant tests are the real deliverable — per E-001,
a test that cannot fail is not enforcement.

1. **Derivation-basis invariants** (fail-closed, over all 94,332 rows):
   - `exit_mechanism == ORIGINAL_STOP_EXIT` ⟺ `abs(rr + 1.0) < 1e-9` — expect 0 violations.
   - No `SL_HIT` row in rr ∈ (−1, 0) — expect 0. A violation means adverse fill is in play and the
     Layer-1 derivation is void.
   - `TRAIL_NEVER_ARMED ⟹ mfe_r < 0.5` — expect 0 violations.
2. **Band totality**: every row maps to exactly one `rr_band`; counts reproduce the table above
   (30,797 / 60,774 / 1,366 / 1,344); zero-population bands present and marked.
3. **Vocabulary lint**: no world-word (`WIN`, `LOSS`, `PROFIT`, `TARGET`, `BREAKEVEN`, `ECON_`)
   appears in any Phase-1 output key or value. This is the mechanical guard on the one
   architectural rule.
4. **Capture guards**: `CAPTURE_UNDEFINED` n = 1,491; `CAPTURE_UNSTABLE` n = 4,007;
   `CAPTURE_NEGATIVE` n = 29,339; `CAPTURE_VIOLATION` n = 0.
5. **Governance floors**, after each registration step:
   ```bash
   venv/Scripts/python.exe -m pytest -q tests/test_semantic_registry.py tests/test_jsonl_claim_catalog.py
   ```
   then the authoritative floor:
   ```bash
   venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all
   ```
   Capture the baseline failure count **before** changing anything — the green floor carries
   known pre-existing reds.
6. **Non-mutation check**: re-hash A1 after Phase 1 and confirm it matches the sha256 in
   `run_linkage_registry.json`.

---

## Critical files

| path | role |
|---|---|
| `scripts/research/opportunity_scanner.py` | emit site (`:229-243`), `_simulate` (`:53-149`), counter (`:188`, `:246`) — Phase 2 only |
| `configs/formulas/market_ontology.yaml` | SEM-037 new; SEM-020 refine in place |
| `docs/governance/jsonl_claim_catalog.yaml` | stream row + two CC classes; regenerate the projection |
| `src/research/measurement/forward_walk.py:339` | `horizon_excursion` — Phase 3 |
| `src/research/oracle/exit_analysis.py:165-175` | reuse for capture + violation counter |
| `src/analytics/metrics_oracle.py:270-279` | reuse `capture_ratio` / `giveback` |
| `src/research/episodes/policy.py:58-93` | `LabelSet` — the Phase-3 home for `ECON_*` |
| `src/research/episodes/projectors/detection.py:27` | quarantine tuple — extend with Phase 2 |
| `scripts/analysis/phase1_shadow_create_economic_census.py:419` | reuse `bucket_table` for Layer 5 |
| `src/training/stage1_dataset_builder.py:84-98` | incumbent `RR_BUCKETS` — declare, do not rename |

---

## One wording correction

*"Labels are ontology. Metrics are authority."* — the second half is load-bearing and wrong here.
Per §6.5 and `CC-PRESENCE-NOT-G001`, metrics are **not** authority; authority is earned only by
measured G001 improvement. A stored float has no more authority than a stored string — and
`rr_achieved` is exactly the stored float this whole design exists to stop treating as truth.

The formulation the episodes substrate already implements, and the one to adopt:

> **Observations are primary. Metrics are recomputable derivations. Labels are policy-bound
> interpretations. None of the three is authority.**

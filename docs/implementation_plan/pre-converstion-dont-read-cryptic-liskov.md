# Re-Research Architecture: Measurement Contract + Family Registry

## Context

~239 research scripts under `scripts/research` + `scripts/analysis` encode roughly 15 semantic
families asked repeatedly across instruments and axes. The blocking problem is not idea supply —
it is that **no research result records the measurement basis it was produced under**, so results
are not mechanically comparable and prior conclusions cannot be selectively invalidated.

Evidence that this is one defect, not several (all from the always-loaded findings index):

| Finding | Symptom | Class |
|---|---|---|
| F-037 / F-058 | Fusion gate OFF in `.env`, ON in code default, docs said OFF | Same question, two contracts, one label |
| F-022 → F-045 → F-041B | Label contamination rediscovered in three separate labs | No shared label derivation |
| F-025 / F-035 | 12bps cost applied where it is 1.8–2.5× the FX bar | Cost as constant, not instrument property |
| F-061 / F-066 | `normalization_basis`, `session_timestamp_basis` | Feature semantics as a *silent* contract term |

The repo already governs **production** config this way (`ACTIVE_VERSION` + SHA-256 +
`promotion_log.jsonl` + §4.0 precedence). The instrument that *judges* production has no equivalent.
Closing that asymmetry is the intended outcome.

Secondary outcome: make the user's stance — *"treat old PROMOTE/REJECT as historical noise until
re-proven"* — **mechanical instead of remembered**, by binding every claim to a contract hash and
letting a contract bump cascade claims to `PROVISIONAL`.

## Decisions locked (2026-08-06)

1. **Sequence:** Phase A (family atlas artifact) → Phase B (design doc + contract schema) → Phase C
   (return to discussion; build nothing further without approval).
2. **Ordering: strict L0 → L1 → L2 → L3 → L4 → L5 per family.** Pivotality-first for wired channels
   was considered and **rejected** — an ablation under an unverified contract carries no more
   authority than any other result. Consequence: the L0 sufficiency criterion is the only bound on
   hygiene spend and must be written explicitly (Phase B).
3. **Contract scope: per-asset-class profiles.** One schema, bound profiles (crypto majors / FX
   majors / metals-MT5). Cost model **derived from each instrument's own bar statistics**, not a
   fixed 12bps.
4. **Legacy scripts: freeze as historical.** Existing scripts become read-only artifacts (§6.2
   rule 4 — never deleted). New work runs through per-family runners. The runner is *specified* in
   Phase B and **not built** in this plan.

## Data model (the reconciliation)

The atlas contains two representations. The flat family list conflates three different kinds of
thing; the object × question matrix does not. **The matrix is the model.**

- **Rows = objects** (semantic things studied)
- **Columns = layers L0–L5** (questions asked of them) — the matrix's existing columns already map:
  Structure→L1, Selection→L2, Labels→L0, Discrimination→L3, Economic qualify→L4, Pivotality→L5
- **Cells = claim slots**, each carrying evidence mass, status, and bound claims
- **Instrument/asset-class is a separate dimension**, not a row — this is why the "XAUUSD/MT5
  campaign" read as a family: a cross-cutting scope masquerading as an object. It dissolves into a
  contract-profile binding.
- **System/governance research is a different domain**, not a market family — excluded from this
  registry (it is L0-of-the-instrument, already covered by the script-census / behavior-census line).

Normalized object list (16): `crt_structure`, `crt_parity`, `session_time`, `zone_geometry`,
`gaussian`, `rr`, `neural_consumers`, `shapes_trajectories`, `regime_dynamics`, `carry_basis`,
`cross_sectional_panel`, `htf`, `weekly_calendar`, `exit_cost_path`, `feature_ontology`,
`label_truth`.

---

## Phase A — Machine-readable family atlas

**Pre-flight (§6.2 rule 1, existing-doc-first).** Before creating anything, check whether
`docs/knowledge-map.md` or `docs/research-readiness/README.md` already owns this topic and extend
it instead. Create new only if neither does.

**Primary artifact:** `docs/governance/research_family_registry.json` (committed; precedent:
`geometry_family_registry.json`, `closure_authority_index.json`, `miar_registry.json`).

Record shape per object:

```json
{
  "family_id": "RF-ZONE-GEOMETRY",
  "object": "Zone geometry / local membership",
  "question": "one sentence — what this object is being asked",
  "canonical_instrument": null,
  "contract_profile": null,
  "runner": null,
  "cells": {
    "L0": { "evidence_mass": "high|med|low|none", "status": "...", "claims": [] },
    "L1": { ... }, "L2": { ... }, "L3": { ... }, "L4": { ... }, "L5": { ... }
  },
  "script_evidence": ["discover_zones", "zone_label_audit"],
  "provenance": {
    "source": "user_atlas_2026-08-06",
    "verified_against_filesystem": false
  }
}
```

**Cell status vocabulary (closed set):** `UNTESTED` · `UNVERIFIED_HISTORICAL` · `IN_PROGRESS` ·
`ANSWERED_UNDER_CONTRACT` · `GAP`.

**Every cell with existing mass seeds as `UNVERIFIED_HISTORICAL`** — this is the user's stance
expressed as initial state rather than as discipline.

**Provenance is mandatory and honest.** The atlas is a *claim about the filesystem* built from
approximate name-based buckets, by the user's own statement. Nothing in Phase A is verified against
disk. `verified_against_filesystem: false` on every record until a join against
`data/script_registry.jsonl` runs (deferred — that join requires reading, which this session
excludes).

**Floor:** `tests/test_research_family_registry.py` — schema validity; all 16 objects present; every
object carries all six L0–L5 cells; status tokens in the closed set; provenance block present; no
cell references a `contract_hash` that does not exist in the contract directory.

## Phase B — Design doc + contract schema

**Charter:** `docs/governance/MEASUREMENT_CONTRACT.md` (long-form; precedent shape:
`MARKET_ONTOLOGY_EVOLUTION_CONTRACT.md`, `REPOSITORY_CONSTRUCTION_PROTOCOL.md`). Must contain the
L0 sufficiency criterion in full, since decision 2 makes it the sole bound on hygiene spend:

> L0 is complete **for a family** when the contract's terms are declared, strictly read, and the
> family's result is provably invariant to the remaining unknowns — **not** when the feature layer
> is clean. Boundary-scoped and non-transitive, mirroring the closure index invariant.

**Machine artifacts:** `configs/research/measurement_contracts/{crypto_majors,fx_majors,metals_mt5}.v1.json`,
each SHA-256 hashed via the existing `scripts/maintenance/_compute_hash.py` pattern.

Contract terms (most already exist as declared config keys — this is assembly, not new machinery):

| Term | Source |
|---|---|
| corpus + integrity level (L1/L2/L3) | `dataset_integrity.validate_dataset` (F-039 scope caveat applies) |
| timestamp basis | existing `feature_pipeline.session_timestamp_basis` (F-066) |
| feature basis | existing `feature_pipeline.normalization_basis` (F-061) |
| label derivation | one definition — `forward_walk(intrabar_fixed)`; closes the F-022 class |
| cost model | **derived** per profile from instrument bar statistics (F-035) |
| decision-path mode | existing `BACKTEST_ENGINE_GATE` (F-058 — declare in config, not `.env`) |
| warmup / purge / OOS split | per profile |
| control + permutation protocol, power floor | research-only terms |

**Claims reuse the existing findings system — do not build a parallel store** (§6.2 rules 1 and 5).
`docs/current-findings.md` already has a living doc, a thin always-loaded CLAUDE.md index, and a
test floor. Extend it with two required fields per row: `family` and `contract`. All 69 existing
findings take `contract: UNKNOWN` in a bulk mechanical pass → `PROVISIONAL` by construction. Nothing
is deleted (§6.2 rule 4); nothing retains unearned authority.

**Invalidation rule (one rule, reusing F-054's proven engine).** A claim is comparable only to
claims sharing its `contract_hash`. A contract version bump cascades every claim bound to the old
hash to `PROVISIONAL` — the same transitive-invalidation / STALE-cascade pattern already built for
the feature DAG (`feature_dag_certify.py`), one level up over `contract → family → claim`.

**Runner: specified, not built.** Document the per-family runner contract — scope object in,
contract binding, claim record out — so the ~19 `qualify_*` variants have a single target shape to
collapse into later. Implementation is a separately approved turn.

**Floors:** `tests/test_measurement_contract.py` (schema, hash freshness, no undeclared terms,
strict-read discipline per §6.5's no-silent-defaults rule); extend `tests/test_current_findings.py`
for the two new required fields.

## Phase C — Discussion gate

Stop. Review the two artifacts together, then decide what gets built. No runner, no migration, no
re-research execution in this plan.

## Explicitly out of scope

Reading or modifying any script; the `data/script_registry.jsonl` join; building runners; migrating
any research script; re-running any family; any change to `configs/production/*` or `ACTIVE_VERSION`.

## Verification

1. `python -m pytest tests/test_research_family_registry.py tests/test_measurement_contract.py tests/test_current_findings.py`
2. Hand-check: every `○` cell in the source matrix appears in the registry as an explicit `GAP` or
   `UNTESTED` record — the point of the artifact is that gaps are addressable, not silent.
3. Hand-check: zero findings carry a contract hash after Phase B's bulk pass (all `UNKNOWN`), i.e.
   the stance is enforced, not asserted.
4. Hash-neutrality: Phases A and B add non-`params` artifacts only — the production config hash must
   be unchanged. Confirm no `configs/production/*` file is touched.
5. §6 SESSION LOG entry appended to `assistant_project.md` (deferred out of plan mode).

## Open items requiring filesystem verification (deferred, need reading)

- Whether `docs/knowledge-map.md` / `docs/research-readiness/README.md` already owns the family-map
  topic (decides create-vs-extend in Phase A).
- `data/script_registry.jsonl` schema, for the eventual family ↔ script join that would flip
  `verified_against_filesystem` to `true`.
- Exact current front-matter/row schema of `docs/current-findings.md`, before adding two required
  fields across 69 rows.

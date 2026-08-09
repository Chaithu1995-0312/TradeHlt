# Topic: Research Measurement Contract

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: 2026-08-06 · Updated: 2026-08-06 · Status: living

## In plain language
Production config is governed — `ACTIVE_VERSION` + SHA-256 + `promotion_log.jsonl` mean nobody can
*infer* what was live. The instrument that judges production — research — had no equivalent: which
label definition, cost model, gate mode, or clock basis a result used lived as an untracked `.env`
value or a per-script literal. Four separate findings (F-037/F-058 gate mode, F-022→F-045→F-041B→F-059
label contamination, F-025/F-035 cost-as-constant, F-061/F-064/F-066 feature/clock basis) turned out
to be one defect wearing four names. This topic is the fix: a frozen per-experiment
**MeasurementContract** schema (pre-existing, 2026-07-10) subordinating reusable per-asset-class
**profiles**, both binding into an atlas of **research families** so every claim can record — and be
selectively invalidated by — the measurement basis it was produced under.

**Honest current state:** the schema is frozen; the *layer* is not ready. Zero sealed `MC-*`
instances exist, zero of 27 declared adversarial probes are implemented, all 3 profiles are `DRAFT`,
every non-terminal finding carries `Contract: UNKNOWN`. `MEASUREMENT_LAYER_STATUS = OPEN` — see
`docs/governance/closure_authority_index.json` surface `RESEARCH_MEASUREMENT_CONTRACT`.

## Code covered
- [`docs/governance/MEASUREMENT_CONTRACT.md`](../governance/MEASUREMENT_CONTRACT.md) — the charter.
  §1–§8 FROZEN v1.0.0 (2026-07-10): the E0–E4 admissibility bar, the 7 declared surfaces
  (population/features/labels/costs/exits/splits/metrics), `pipeline_identity`. §9–§10 amended
  additively 2026-08-06: asset-class profiles, the L0 sufficiency criterion.
- [`docs/governance/measurement_contract.schema.json`](../governance/measurement_contract.schema.json) — the frozen JSON Schema for a sealed `MC-*` instance.
- [`docs/governance/e_mt_01_adversarial_mutation_matrix.json`](../governance/e_mt_01_adversarial_mutation_matrix.json) — 27 declared failure classes (`FC-*`), each needing ≥1 seeded defect; **0 implemented**.
- [`docs/governance/research_family_registry.json`](../governance/research_family_registry.json) — 16 objects (research families, `RF-*`) × 6 layers (`L0` hygiene → `L5` pivotality) = 96 claim-slot cells, seeded from a user-authored atlas of ~239 research scripts. Excludes instrument/asset-class (a scope dimension, not an object) and system/governance research (a different domain).
- [`configs/research/measurement_contracts/crypto_majors.v1.json`](../../configs/research/measurement_contracts/crypto_majors.v1.json), `fx_majors.v1.json`, `metals_mt5.v1.json` — `MP-*` profiles, `DRAFT` lifecycle, per-asset-class defaults an `MC-*` instance always overrides on experiment-scoped fields (`engine_gate_mode`, `dataset_integrity_level`, `splits`, `metrics.multiplicity`).
- [`scripts/research/gate_measurement_m_gate_01.py`](../../scripts/research/gate_measurement_m_gate_01.py) — the one runner built so far; a SCOPE measurement (authority NONE), reuses `ProductionSpineSource` unmodified with a hard non-vacuity guard on `EngineRunner.run()` call count.
- [`docs/current-findings.md`](../current-findings.md) — every non-terminal finding carries `Family:` (an `RF-*` id or an explicit exclusion) and `Contract:` (a resolved identity or `UNKNOWN`).

## Ins / Outs
- **Ins:** the frozen schema's 7 surfaces per experiment; a profile's `surface_defaults` per asset
  class; a family registry cell's `evidence_mass`/`status`/`claims`; a finding's `Family:`/`Contract:`
  fields.
- **Outs:** a sealed `MC-*` instance (none exist yet); a profile `profile_hash` once `FROZEN` (none
  are); a family-registry claim binding; `results/research/gate_measurement_2026_08_06/summary.json`
  (M-GATE-01's one measurement artifact so far, per-instrument+arm entry sets and resolved
  `engine_gate_mode`).

## Entry points & validations
- **Reached via:** no runner exists yet for the general case (§6 of the charter specifies the
  per-family runner contract — scope object in, contract binding, claim record out — but it is not
  built). `scripts/research/gate_measurement_m_gate_01.py` is the one concrete, hand-written
  measurement run so far.
- **Validated by:** `tests/test_measurement_contract.py` (profile schema, mechanical subordination
  to the frozen schema's own enums, lifecycle gating, hash recomputation, MC-* override-precedence
  wording), `tests/test_research_family_registry.py` (registry schema, full finding coverage — every
  non-terminal finding bound or explicitly excluded, zero silent drops), `tests/test_current_findings.py`
  (every non-terminal finding carries Family+Contract, Contract resolves to a real identity or
  `UNKNOWN`), `tests/test_closure_authority_index.py` (the `RESEARCH_MEASUREMENT_CONTRACT` surface
  entry is schema-valid and its status token is literally present in the charter). All 7 of the new
  assertions across these files were seeded-defect-mutation tested (RED on mutant, green on clean)
  before being trusted.

## Tests
- [`tests/test_measurement_contract.py`](../../tests/test_measurement_contract.py) — 13 tests: profile shape/namespace, mechanical subordination to the frozen schema's enums, lifecycle gating, hash recomputation, label-surface identity across profiles, derived-cost enforcement, MC-* override precedence.
- [`tests/test_research_family_registry.py`](../../tests/test_research_family_registry.py) — 16 tests: schema, all 6 layers per family, closed status/mass vocabularies, mass/status coherence, full finding coverage (no unaccounted, no phantom, no double-bound claims), unpartitioned-bundle honesty, reachability from `docs/knowledge-map.md`.
- [`tests/test_current_findings.py`](../../tests/test_current_findings.py) — extended with `test_nonterminal_findings_declare_family_and_contract` + `test_contract_bound_findings_name_a_real_measurement_identity`.
- [`tests/test_closure_authority_index.py`](../../tests/test_closure_authority_index.py) — generic surface floors (schema, status vocab, artifact existence, status-token presence, CLAUDE.md table row consistency) apply automatically to the new `RESEARCH_MEASUREMENT_CONTRACT` surface; no test-file edits were needed to add it.

## Fits in architecture
Sits *above* the research scripts it governs, *beside* production's `ACTIVE_VERSION`/SHA-256
governance (the pattern this topic mirrors one level up), and *below* the §6.5 Authority Ladder (a
contract grants comparability, never authority — exactly as `CONFIG_DRIVEN` grants tunability, never
authority). See `docs/governance/closure_authority_index.json` surface `RESEARCH_MEASUREMENT_CONTRACT`
for the machine-checked navigational status, and `docs/knowledge-map.md`'s "Research families" row
for the traversal recipe.

## Discussion (filled in-session)
> Standing parallel-discussion surface. Append dated entries; never delete — supersede.

- **Risks:** 2026-08-06 — a frozen-but-unimplemented spec (`MEASUREMENT_CONTRACT.md` §1–§8) already
  existed when this topic's registry/profile layer was designed; nearly rebuilt in parallel before
  the read-before-write guard caught it. Subordination is now mechanical (enum-membership test), but
  the risk of a future session not noticing the frozen spec again is real — this topic doc + the
  Closure & Authority Index entry are the mitigation.
- **Challenges:** 2026-08-06 — deciding whether `engine_gate_mode` belongs on the profile (asset-class
  default) or the claim (per-experiment pipeline identity). Resolved empirically, not just by
  argument: M-GATE-01 measured F-037 (gate-OFF epoch) vs F-070 (gate-ON epoch, current config) on the
  identical historical corpus and found byte-identical entry sets under F-070 vs F-037's recorded 14%
  reduction — both findings stay true because they're epoch-scoped, which only makes sense if gate
  mode is claim-scoped pipeline identity, not a profile default.
- **Blockers:** none structural. The real blocker is throughput: 27 declared `E-MT-01` probes, 0
  built; 3 profiles, all `DRAFT`, none with a calibrated cost model.
- **Ambiguities:** whether `RF-HTF` (timeframe) is a genuine object or another scope dimension like
  instrument — flagged, not resolved, in the family registry's own notes for that row.
  Whether `RF-CARRY-BASIS` should split into its signal vs harvest payoffs — same status.
- **Enhancements:** implement the E-MT-01 probes (highest leverage — the frozen spec's own stated
  next step, 4 weeks undone); seal a first `MC-*` instance against one profile; calibrate one
  profile's cost model to move it toward `FROZEN`; disambiguate F-070's driver (F-038 vs F-048) with
  a third arm.
- **Need more info:** none currently blocking.

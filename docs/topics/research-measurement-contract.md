# Topic: Research Measurement Contract

> **Topic-visibility unit.** One concept, narrated in human language, kept in sync with the
> code on every working response (`CLAUDE.md §6.1`). Read this to understand the topic — what
> code it covers, how it's reached, what tests it, what's still open — **without loading the
> rest of the codebase**. Link, don't inline.
>
> Created: 2026-08-06 · Updated: 2026-09-03 · Status: living

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
- [`docs/research/parquet_evidence_layer.md`](../research/parquet_evidence_layer.md) + [`src/research/evidence/`](../../src/research/evidence/) — the four XAUUSD parquet projections queried as an evidence layer (not a training dataset). JSONL remains system of record. LLM/parquet-bot paste-pack: [`.grok/PARQUET_BOT_BRIEF.md`](../../.grok/PARQUET_BOT_BRIEF.md) (findings that bind per surface; not a second authority).
- [`docs/current-findings.md`](../current-findings.md) — every non-terminal finding carries `Family:` (an `RF-*` id or an explicit exclusion) and `Contract:` (a resolved identity or `UNKNOWN`).

- **Spine inventory (2026-09-03 citation pass — path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.:**
- [`src/identity/__init__.py`](../../src/identity/__init__.py)
- [`src/identity/certify.py`](../../src/identity/certify.py)
- [`src/identity/check.py`](../../src/identity/check.py)
- [`src/identity/hashes.py`](../../src/identity/hashes.py)
- [`src/identity/outcome.py`](../../src/identity/outcome.py)
- [`src/identity/query.py`](../../src/identity/query.py)
- [`src/identity/store.py`](../../src/identity/store.py)
- [`src/identity/tokens.py`](../../src/identity/tokens.py)

## Ins / Outs
- **Ins:** the frozen schema's 7 surfaces per experiment; a profile's `surface_defaults` per asset
  class; a family registry cell's `evidence_mass`/`status`/`claims`; a finding's `Family:`/`Contract:`
  fields.
- **Outs:** a sealed `MC-*` instance (none exist yet); a profile `profile_hash` once `FROZEN` (none
  are); a family-registry claim binding; `results/research/gate_measurement_2026_08_06/summary.json`
  (M-GATE-01's one measurement artifact so far, per-instrument+arm entry sets and resolved
  `engine_gate_mode`); `results/research/parquet_evidence_layer/report.json` (evidence records:
  n / effect / confidence / candidate finding — not F-ids).

## Entry points & validations
- **Reached via:** no runner exists yet for the general MC-* family case (§6 of the charter specifies the
  per-family runner contract — scope object in, contract binding, claim record out — but it is not
  built). `scripts/research/gate_measurement_m_gate_01.py` is the one concrete, hand-written
  measurement run so far. `python -m research.evidence` queries the parquet projections as
  measurements, not as a sealed contract.
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
- [`tests/test_measurement_contract.py`](../../tests/test_measurement_contract.py) — 16 tests: profile shape/namespace, mechanical subordination to the frozen schema's enums, lifecycle gating, hash recomputation, label-surface identity across profiles, derived-cost enforcement, MC-* override precedence.
- [`tests/test_research_family_registry.py`](../../tests/test_research_family_registry.py) — 16 tests: schema, all 6 layers per family, closed status/mass vocabularies, mass/status coherence, full finding coverage (no unaccounted, no phantom, no double-bound claims), unpartitioned-bundle honesty, reachability from `docs/knowledge-map.md`.
- [`tests/test_current_findings.py`](../../tests/test_current_findings.py) — extended with `test_nonterminal_findings_declare_family_and_contract` + `test_contract_bound_findings_name_a_real_measurement_identity`.
- [`tests/test_closure_authority_index.py`](../../tests/test_closure_authority_index.py) — generic surface floors (schema, status vocab, artifact existence, status-token presence, CLAUDE.md table row consistency) apply automatically to the new `RESEARCH_MEASUREMENT_CONTRACT` surface; no test-file edits were needed to add it.
- [`tests/research/test_evidence_layer.py`](../../tests/research/test_evidence_layer.py) — parquet evidence layer: illegal join refused, y_tp1 not stream outcome, quality ≠ TP, no engine/trainer imports.

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
  built; 3 profiles, all `DRAFT`. **[UPDATED 2026-08-19]** `MP-METALS-MT5` now carries a MEASURED
  cost calibration (F-082) — the first profile with one; `MP-CRYPTO-MAJORS` and `MP-FX-MAJORS`
  remain `PENDING_CALIBRATION` because no measured broker data exists for them. All three stay
  `DRAFT`: a calibrated cost model resolves one unresolved term, not admissibility.
- **Ambiguities:** whether `RF-HTF` (timeframe) is a genuine object or another scope dimension like
  instrument — flagged, not resolved, in the family registry's own notes for that row.
  Whether `RF-CARRY-BASIS` should split into its signal vs harvest payoffs — same status.
- **Enhancements:** implement the E-MT-01 probes (highest leverage — the frozen spec's own stated
  next step, 4 weeks undone); seal a first `MC-*` instance against one profile; ~~calibrate one
  profile's cost model to move it toward `FROZEN`~~ **DONE 2026-08-19 for `MP-METALS-MT5` (F-082)** — 7 of its
  8 unresolved terms remain, so `FROZEN` is still distant; disambiguate F-070's driver (F-038 vs F-048) with
  a third arm.
- **Cost model, resolved for metals:** 2026-08-19 (F-082, CH-cost-model-broker-truth) — the charter's
  own diagnosis ("cost model … lived as ambient state") had a concrete instance: the research harness
  charged a flat 12bps to every instrument, ~11.3x the repo's own MEASURED XAUUSD broker cost, while
  `forward_walk` filled every stop at exactly −1.000R. Both are now config-gated and default-inert, and
  `truth_standard_block` records which cost and fill model produced a result. Two lessons worth keeping:
  (a) the profiles' placeholder derived cost from VOLATILITY (`k * median(bar_range_pct)`) — trading cost
  is a BROKER property, and the measured decomposition replaced the proxy rather than calibrating it
  (adjudication UNK-COST-02); (b) a measurement can sit unused for two weeks because nothing binds it to
  the consumer — the calibration ran 2026-08-06 and the harness kept charging 12bps until 2026-08-19.
- **Need more info:** none currently blocking.
- **Asymmetry MC (2026-08-24):** `MC-ASYM-XAUUSD-M15-V1` / SEM-027 sealed, then
  single-pass holdout. PRIMARY FM-054 contrast sign-matched (train +0.415,
  holdout +0.469, n=9454). Unconditional E[ΔMFE] flipped. DIAGNOSTIC_PASS,
  F-091, no G001. F-086 stride unspent. Spec
  [`docs/research/asymmetry_object.md`](../research/asymmetry_object.md).
  Decomposition (same object, PRIMARY not retuned): naive E[Δ] spread ranks
  hour>session>vol; the directional object is trend_bias (P-stable, E[Δ|Δ>0]
  channel). Snapshot
  [`docs/analysis/asymmetry-decomposition-2026-08-24.md`](../analysis/asymmetry-decomposition-2026-08-24.md).
- **Magnitude prior MC (2026-08-24):** `MC-MAGPRIOR-XAUUSD-M15-V1` / SEM-028
  sealed before holdout. Side is given; FM-054 is a magnitude/time prior, not a
  side picker. Arm S DIAGNOSTIC_PASS (train +0.265 / holdout +0.209 MFE).
  Arm T DIAGNOSTIC_PASS (train −0.209 / holdout −0.220 bars — faster, not
  longer). Overlay k=0.5 diagnostic +0.052R. F-092. P-GOAL-04 not opened. Spec
  [`docs/research/magnitude_prior_object.md`](../research/magnitude_prior_object.md).
- **R-net overlay MC (2026-08-24):** `MC-RNET-OVERLAY-XAUUSD-M15-V1` / SEM-029
  sealed before holdout. Independent entry = clean_labels bar×side. PRIMARY
  k=0.5 overlay DIAGNOSTIC_PASS (train +0.0058 / holdout +0.0064) on a
  still-losing book (holdout E[y]=−0.55R). F-093. E>0 was not the gate.
  P-GOAL-04 not opened. Spec
  [`docs/research/rnet_size_overlay_object.md`](../research/rnet_size_overlay_object.md).
- **Sparse mother-range prior MC (2026-08-24):** `MC-MRPRIOR-XAUUSD-M15-V1` /
  SEM-030 sealed before holdout. Sparse independent signal = SEM-026
  mother-range inside entries; prior = SEM-028/FM-054 agreement. Both arms are
  `INSUFFICIENT`: holdout agree cell n=9 below the frozen n>=30 floor, with
  sign flips recorded. F-094. No retune, no side picker, no G001. Spec
  [`docs/research/mother_range_prior_object.md`](../research/mother_range_prior_object.md).
- **Evidence atlases (2026-08-24):** leakage / state-value / same-timestamp
  long−short MFE on the 94k grain (`src/research/evidence/atlases.py`,
  `CH-evidence-atlases`). Snapshot
  [`docs/analysis/evidence-atlases-2026-08-24.md`](../analysis/evidence-atlases-2026-08-24.md).
  Path-net is structurally ~0 for side-symmetric states; directional object is
  E[MFE_L−MFE_S]. No F-id, no G001.
- **Parquet evidence layer (2026-08-23):** the four XAUUSD parquet projections
  (`opportunities` / `clean_labels` / `events` / `crt_telemetry`) are a queryable
  **evidence layer**, not a training dataset. Spec
  [`docs/research/parquet_evidence_layer.md`](../research/parquet_evidence_layer.md);
  code `src/research/evidence/`. JSONL remains system of record. Two grains: the
  94k ledger is bar×direction (joinable to clean_labels); events/telemetry are a
  later CRT spine run and must not be 1:1 joined onto it. Candidate findings are
  measurements (n, effect, confidence) and are **not** auto-registered F-ids.
  Does not freeze a profile, does not seal an `MC-*`, does not grant G001.
- **Capability lock (2026-08-24):** the Parquet + MC + holdout engine is
  strong enough to find **research-grade informational edges**
  (`State → Future Path Difference`) and to reject non-economic ones.
  It has **not** shown `State → E[R]>0 after costs`. F-091/092/093 survived
  holdout then decomposed: +0.209 horizon MFE → +0.035 walk MFE → +0.026
  R-net. F-093 *was* every-bar independent entry + prior. The untested
  medium-probability object was a **sparse** independent signal + prior
  (`P-EVID-01`), now measured as SEM-030 / F-094 and underpowered on holdout.
  Spec lock:
  [`docs/research/parquet_evidence_layer.md`](../research/parquet_evidence_layer.md)
  § Demonstrated vs unproven. No new F-id. P-GOAL-04 unopened.
- **Parquet-bot brief (2026-08-27):** a Grok bot with Parquet file access must consume
  F-022/F-051/F-061/F-066/F-069/F-080/F-086…F-095 *before* reading OHLC/feature/state
  columns. CURRENT parquet is four evidence projections, not L0–L5 identity storage.
  Brief: [`.grok/PARQUET_BOT_BRIEF.md`](../../.grok/PARQUET_BOT_BRIEF.md). No G001.
- **Parquet formula parity (2026-08-27):** stored 38 overlapping feature columns on the
  XAUUSD clean_labels file are bit-identical to HEAD `FeaturePipeline` and match
  ontology geometry (FM-001/002/010). Remaining drift is formula identity (F-061, F-066)
  and schema 38 vs 48, not a dump error.
  [`docs/analysis/parquet-formula-parity-2026-08-27.md`](../analysis/parquet-formula-parity-2026-08-27.md).
- **Asymmetry atlas rerun (2026-08-27):** named query on the legal clean_labels join
  (n=47,166) **replicates** the 2026-08-24 atlas (E[ΔMFE]=+0.239). Not a new F-id.
  F-091 already showed that unconditional mean is a train/holdout mix. Events/telemetry
  not joined. RESEARCH_ONLY. Does not reverse F-086. No G001.
- **State value atlas rerun (2026-08-27):** `--atlas state_value` on the same 94k grain.
  MATCH 2026-08-24: hour E[MFE] spread 3.13, path_net=0 except side ±0.239 (the F-091
  mix). CRT engine states not on this grain. Not win rate. No G001.
- **Leakage atlas rerun (2026-08-27):** `--atlas leakage` MATCH 2026-08-24: 44,858
  reached ≥1R and missed unit TP (0.476); exclusive 2R-missed-TP 28,007.
  Path-conditioned, not t=0. All three 94k atlases now rerun MATCH. No G001.
- **Path A findings audit (2026-08-28):** atlas count ≠ F-088 SL-first mechanism.
  Spec lock corrected. Audit: [`docs/analysis/atlas-findings-audit-2026-08-28.md`](../analysis/atlas-findings-audit-2026-08-28.md).
- **2026-08-25 — result binding closes the F-083 silent gap (CH-jsonl-claim-surface PR-3):** a sealed contract could declare `evidence_artifacts` and `trust_status.mt00: PASS` while the run never happened, and nothing compared the instance to the artifacts its run produced — `tests/test_measurement_contract.py` validates SHAPE only. `configs/research/measurement_result_log.jsonl` is now the committed append-only record that a run EXECUTED, and any git-tracked `instances/MC-*.json` with `mt00 != UNRUN` must have a line binding artifact SHA-256s. `UNRUN` stays honestly UNRUN and needs nothing: all 8 tracked instances are UNRUN, so the floor ships green and vacuous — the point is that the NEXT sealed instance cannot skip it. Grounding: `CC-MC-SCHEMA-SHAPE` grounds on an UNRUN document (shape is not execution), `CC-MC-RESULT-BINDING` refuses it as `CC-MC-DECLARED-UNEXECUTED`, and a FAIL run with an honest line GROUNDS — **executed, not passed**. Research authority only; `economic_claims_allowed` is const false.
- **Sujan identity lock (2026-08-28):** a sealed `MC-*` can still measure the **wrong object**. F-095 REJECT of SEM-031 is real; identity with Sujan-as-narrated was never certified. Further Sujan work loads [`docs/governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md`](../governance/SUJAN_CRT_IDENTITY_EXTRACTION_SYSTEM.md) **before** a contract or implementation. Identity freeze precedes measurement. No retune of R4, no new G001. `P-SUJAN-04`.
- **2026-09-03 — spine citation pass:** named 8 previously unreferenced spine paths under Code covered (path existence on the GCMC spine join; not a behavior claim, not G001, not a file:line citation. Source still wins.).

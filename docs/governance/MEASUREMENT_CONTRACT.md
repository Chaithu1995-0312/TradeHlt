# MeasurementContract — Minimum Executable Evidence (E-MT-00 / E-MT-01)

**Status:** FROZEN v1.0.0 (2026-07-10) · **amended additively 2026-08-06** (§9 asset-class profiles, §10 L0 sufficiency criterion — schema v1.0.0, the FC matrix, and the E0–E4 bar are **unchanged**; §1–§8 are untouched)  
**MEASUREMENT_LAYER_STATUS = OPEN** — distinct from the schema freeze above: the *schema* is frozen
(its shape won't change without a version bump), but the *layer's operational readiness* is not —
zero `MC-*` instances are sealed, zero of the 27 `E-MT-01` probes below are implemented, all 3
asset-class profiles (`configs/research/measurement_contracts/*.v1.json`) are `DRAFT`. Do not read
"schema FROZEN" as "layer ready." Tracked as surface `RESEARCH_MEASUREMENT_CONTRACT` in
[`closure_authority_index.json`](closure_authority_index.json) (CLAUDE.md §6.2). Status advances
only when an `MC-*` instance actually clears E-MT-00 PASS + E-MT-01 COMPLETE (§2 below).  
**Schema:** [`measurement_contract.schema.json`](measurement_contract.schema.json)  
**Mutation matrix:** [`e_mt_01_adversarial_mutation_matrix.json`](e_mt_01_adversarial_mutation_matrix.json)  
**Prereg:** [`preregistered_experiments.md`](../../preregistered_experiments.md) (Tier 0)  
**Authority:** Substrate only — grants **no** economic SUPPORTED/FALSIFIED conclusions.

---

## 1. Why this exists

Tier-1 experiments can appear to measure edge while **silently substituting**:

| Intended | Silent substitute (historical class) |
|----------|--------------------------------------|
| Trades | Detections (F-022) |
| Forward-walk R | Stream `outcome`/`rr` (F-022/F-041B/F-045) |
| Named feature FM-0xx | Different formula under same key (F-046/F-050) |
| Fusion spine | CRT-only gate-OFF path (F-037) |
| True RR gate | Polarity∈[0,1] vs threshold 1.5 (F-048) |
| Net expectancy | Gross / p-value / IC (E-001B) |
| Independent n | Overlapping rows / detection count |

**Minimum bar:** every Tier-1 experiment must prove it measures the **declared** population, features, labels, costs, exits, splits, and metrics — or it cannot produce economic claims.

---

## 2. Minimum executable evidence (the bar)

For experiment `E-*`, economic claims are **inadmissible** until **all** of the following exist and are green:

### E0 — Sealed contract instance

1. A JSON document validating against `measurement_contract.schema.json` **v1.0.0**.
2. `contract_id` stable; `experiment_id` matches prereg.
3. `authority.economic_admissible == false` until E-MT-00 PASS.
4. All seven surfaces populated: **population, features, labels, costs, exits, splits, metrics**.
5. `pipeline_identity` names the real path (gate mode, engines, modules in/out, integrity level, flags).
6. `prohibited_substitutions` lists at least one forbid per surface the experiment uses, each linked to an `FC-*` class.

### E1 — Fingerprints (identity of the measured object)

| Artifact | Proves |
|----------|--------|
| `population_fingerprint` | Hash over declared unit keys (instrument, decision_ts, side, setup_id, …) — detection streams cannot silently replace trade units |
| `feature_binding_report` | Each output key → `fm_id` + formula_ref; collisions in `not_equal_to` fail |
| `label_rederive_report` | Stream y vs `forward_walk` under contract exits+costs; agreement ≥ `min_agreement` or fields banned |
| `cost_exit_fixture` | One sealed path: entry→exit with nonzero declared costs; success metric is **net** if required |
| `split_manifest` | Fold boundaries + purge/embargo empties; no forbidden overlap |
| `metric_gate_trace` | Success/kill evaluation uses only declared metrics; p/IC cannot alone SUPPORTED economic arms |

### E2 — Clean-path probes (E-MT-00)

Run the probe set in the mutation matrix `probes` section on the **declared** pipeline with **no** mutations.  
**PASS rule:** every probe required by the experiment’s surfaces is green; residual risks listed as non-blocking only if they cannot flip economic sign under stated assumptions.

### E3 — Adversarial matrix coverage (E-MT-01)

For **every** `failure_class` in `e_mt_01_adversarial_mutation_matrix.json` (v1: **27 classes, ≥1 seed each**):

| Requirement | Rule |
|-------------|------|
| Seeded defect exists | `seeded_defects.length ≥ 1` |
| Mutant is red | Activating the seed makes `detector_probe` **FAIL** |
| Clean is green | Same probe **PASS** without seed |
| No silent skip | Coverage report lists class → seed → probe → clean/mutant outcomes |

**Coverage incomplete ⇒ `trust_status.mt01_matrix_coverage = INCOMPLETE` ⇒ economic claims forbidden.**

### E4 — Trust status seal

```text
economic_claims_allowed
  ⇔ mt00 == PASS
  ∧ mt01_matrix_coverage == COMPLETE
  ∧ contract validates schema v1.0.0
  ∧ no BLOCKING open probe failures
```

Anything less: experiment may still run **diagnostically**, but results are `UNTRUSTED_PENDING_REPLICATION` / non-admissible.

---

## 3. Surface-by-surface contract (what must be declared)

### 3.1 Population

- `unit_of_analysis` ∈ candle | signal_event | **trade_decision** | settlement_event | panel_row | rebalance  
- `detection_vs_trade` must be explicit — **trade_decision** forbids counting pure detection streams (FC-POP-DETECTION-AS-TRADE).  
- Inclusion/exclusion rules + calendar window + instruments + timeframe.  
- `n_declared_min` = independent units for power claims.

**Executable evidence:** population fingerprint + PROBE-POP-UNIT-MATCH.

### 3.2 Features

- Feature ids + `formula_authority` (ontology / candle_math / …).  
- `name_binding`: key → fm_id + formula + units + `not_equal_to` collisions (F-050).  
- Point-in-time rule (no center-window / global-rank unless declared).  
- No silent categorical defaults (session→london).

**Executable evidence:** golden-candle formula parity + future-bar perturbation (PIT) + name-binding check.

### 3.3 Labels

- `label_family` and exact `y_definition`.  
- `derivation_authority`: economic labels must be `forward_walk.*` or cashflow — **never** `forbidden_stream_outcome`.  
- Banned stream fields listed.  
- Rederive protocol: matcher, `min_agreement`, on_fail ∈ BAN_FIELDS | BLOCK_EXPERIMENT | DIAGNOSTIC_ONLY.  
- Degeneracy check if multiple y’s claimed independent (F-045).

**Executable evidence:** PROBE-LBL-REDERIVE-AGREE + AUTHORITY + DEGENERACY.

### 3.4 Costs

- Named components (entry/exit/round_trip/funding) with bps or formula.  
- Gross diagnostic allowed; **promotable = net_only** (or none for info-stage).  
- Success gate uses net when economic.

**Executable evidence:** fixture round-trip costs > 0 when components declared; gate metric is net.

### 3.5 Exits

- `exit_family` + parameters + intrabar rule.  
- `not_equal_to`: stream outcome, undeclared live planner, etc.  
- Code entrypoint for the exit used to build y.

**Executable evidence:** PROBE-EXIT-AUTHORITY (path identity).

### 3.6 Splits

- Walk-forward / purged k-fold / …  
- Embargo + purge text; `overlap_policy`.  
- Seed + fold count.

**Executable evidence:** PROBE-SPLIT-PURGE-EMBARGO on synthetic overlapping labels.

### 3.7 Metrics

- Separate `information_metrics` vs `economic_metrics`.  
- Success + kill strings.  
- Multiplicity: n_variants + control (deflated Sharpe / …).  
- Authority ladder flags all true: info≠value, value≠authority, insufficient≠harmful.  
- Forbidden substitutions listed (p_as_edge, gross_as_success, n_detections_as_n_trades).

**Executable evidence:** authority-ladder + insufficient-guard + independence-n probes.

### 3.8 Pipeline identity (cross-cutting)

- ACTIVE_VERSION resolution; engine_gate_mode honesty (F-037).  
- expected_engines vs actual construction/calls.  
- modules explicitly out of path (orphans).  
- dataset_integrity_level and real call-sites (F-039).  
- feature_flags match runtime (F-004).  
- manifest sha == runtime artifact (F-041A).

---

## 4. Failure-class coverage (must have ≥1 seed each)

See matrix JSON for full seeds. Classes (**27**):

| ID | Anchor |
|----|--------|
| FC-POP-DETECTION-AS-TRADE | F-022 |
| FC-LABEL-STREAM-INCONSISTENT | F-022 |
| FC-LABEL-ZONE-ARTIFACT | F-041B |
| FC-LABEL-RR-TRAINING | F-045 |
| FC-LABEL-DEGENERATE-Y | F-045 |
| FC-FEATURE-NAME-COLLISION | F-050 |
| FC-FEATURE-FORMULA-DIVERGENCE | F-046/GD-001 |
| FC-FEATURE-LOOKAHEAD-CENTER | F-029 |
| FC-FEATURE-GLOBAL-RANK | F-029 |
| FC-SESSION-SILENT-DEFAULT | phase-integrity / E-001D |
| FC-ENGINE-GATE-OFF-SUBSTITUTION | F-037 |
| FC-ENGINE-RR-GAUSSIAN-DUPLICATE | F-038 |
| FC-ENGINE-CONFIDENCE-MISSCALE | F-044 |
| FC-ENGINE-SEMANTIC-MISWIRE-RR | F-048 |
| FC-ENGINE-ORPHAN-SIDECAR | F-012/013/005 |
| FC-ENGINE-INERT-FLAG | F-004 |
| FC-CONFIG-VERSION-SPLIT | F-016/018 |
| FC-CONFIG-ORPHAN-INTEGRITY | F-006 |
| FC-MANIFEST-RUNTIME-MISMATCH | F-041A |
| FC-L3-INTEGRITY-CALLSITE | F-039 |
| FC-COST-MODEL-SUBSTITUTION | F-025 + prereg |
| FC-EXIT-PROXY-NOT-GOVERNING | F-022/025/010 |
| FC-SPLIT-OVERLAP-LEAKAGE | purged-CV doctrine |
| FC-METRIC-STAT-AS-ECON | E-001B |
| FC-METRIC-OVERCLAIM-INSUFFICIENT | E-001A/E / F-031 |
| FC-METRIC-DECORATIVE-WIRING | E-001F |
| FC-METRIC-N-SUBSTITUTION | F-022 power illusion |

---

## 5. What is *not* minimum evidence

- Green pytest unrelated to the experiment path  
- A narrative “we used forward_walk” without rederive report  
- Presence of `dataset_integrity.py` without call-site proof  
- Historical F-xxx null/edge as substitute for contract PASS  
- Deflated Sharpe alone without population/label identity  
- Byte-identical ledger without declared cost model  

---

## 6. Implementation order (no E-MT-00 code before this freeze)

1. **Done:** schema v1.0.0 + mutation matrix v1 frozen (this directory).  
2. **Next:** implement probes as pure tests/fixtures; each SEED-* must be activatable.  
3. **Then:** E-MT-00 runner that loads a MeasurementContract instance + emits `mt00_report`.  
4. **Then:** Tier-1 experiments attach `MC-*` instances; economic write-path checks `economic_claims_allowed`.

---

## 7. Change control

- Schema `const` version bump requires a new schema file or migration note and matrix compatibility review.  
- Adding a **new** historical failure class requires a new `FC-*` + ≥1 seed before claiming matrix COMPLETE.  
- Do not delete FC classes; mark `status: RETIRED` only if the defect becomes structurally impossible and a probe still proves impossibility.

---

## 8. One-sentence standard

> **A Tier-1 result is measurement-trusted only if a sealed MeasurementContract names every surface, clean probes pass, and every repository-discovered failure class has a seeded mutant that the same probes catch.**

---

## 9. Asset-class profiles (subordinate layer, added 2026-08-06)

**Files:** `configs/research/measurement_contracts/{crypto_majors,fx_majors,metals_mt5}.v1.json`
**Floor:** `tests/test_measurement_contract.py`

A **profile** supplies reusable per-asset-class **defaults** for the surface fields of a sealed
`MC-*` instance. It is *subordinate*: it never overrides this charter, never relaxes E0–E4, never
sets `trust_status`, and never grants economic admissibility — only `mt00 == PASS` ∧
`mt01_matrix_coverage == COMPLETE` does that (§2 E4).

| | Contract instance (§1–§8) | Profile (this section) |
|---|---|---|
| Scope | one experiment | one asset class |
| Id | `MC-*` + `experiment_id` | `MP-*`, **never** an `experiment_id` |
| Answers | "was THIS experiment honestly measured?" | "what does this asset class default to?" |
| Grants | admissibility, once sealed and probed | nothing — defaults only |

**Why the layer exists.** Three surfaces are asset-class properties, not experiment choices, and
treating them as per-experiment is how the repo got the defects this charter already names:

1. **Costs are not portable.** The schema permits a flat bps constant. F-025/F-035 show 12bps is
   1.8–2.5× the median FX M15 bar, making magnitude claims cost-dominated. Profiles pin
   `cost_model_id = derived_per_instrument.v1` — cost derived from the instrument's *own* bar
   statistics. This is a **tightening**, never a relaxation, of `FC-COST-MODEL-SUBSTITUTION`.
2. **Clock semantics are provider properties.** F-066: MT5 session labels are broker-local
   mislabelled UTC (53.36% of XAUUSD bars wrong); Binance corpora are unaffected. The correct
   basis is a property of where the data came from.
3. **The label surface must NOT vary.** `labels` is byte-identical across all three profiles by
   design — if it varied by asset class, cross-class generalization claims (F-035's crypto→FX
   result) would be uninterpretable.

**Mechanical subordination.** Every enumerated value in a profile is drawn from this schema's own
enums (`unit_of_analysis`, `detection_vs_trade`, `derivation_authority`, `exit_family`,
`promotable`, `overlap_policy`, `formula_authority`, `engine_gate_mode`,
`dataset_integrity_level`). The floor test loads `measurement_contract.schema.json` and asserts
membership, so subordination is checked, not merely claimed.

**Profile lifecycle.**

```
DRAFT  ──calibrate──▶  CALIBRATED  ──freeze──▶  FROZEN
```

| Lifecycle | `profile_hash` | `unresolved_terms` | May an `MC-*` instance inherit it? |
|---|---|---|---|
| `DRAFT` | `null` | non-empty | **no** |
| `CALIBRATED` | `null` | empty | no — freeze first |
| `FROZEN` | required, must match recomputation | empty | **yes** |

`profile_hash = sha256(json.dumps(surface_defaults, sort_keys=True, separators=(",",":")))` — over
`surface_defaults` only, so prose edits never invalidate a measurement basis. Recomputed and
asserted by the test; never written by hand.

**All three v1 profiles ship `DRAFT`.** That is the honest state: the *method* is fixed, the
*values* are not calibrated. Each profile's `unresolved_terms` enumerates exactly what blocks its
freeze — six to eight items each, every one anchored to an existing finding. That list is the
actionable backlog for making research trustworthy, and it is short.

## 10. L0 sufficiency criterion (added 2026-08-06)

Research execution order is **strict `L0 → L1 → L2 → L3 → L4 → L5`** per family (layers defined in
[`research_family_registry.json`](research_family_registry.json)). A pivotality-first inversion for
already-wired channels was considered and **rejected** on 2026-08-06: an ablation measured under an
unverified contract carries no more authority than any other result.

That makes this criterion **the only bound on hygiene spend**, so it is stated as law:

> **L0 is complete FOR A FAMILY when the contract's terms are declared, strictly read, and that
> family's result is provably invariant to the remaining unknowns — NOT when the feature layer is
> clean.**
>
> Boundary-scoped and non-transitive, mirroring the Closure & Authority Index invariant. A clean
> upstream layer does not make a family's L0 complete; an unclean one does not necessarily block
> it. What matters is whether the *remaining* uncertainty can change *this family's* answer.

**Why it is needed.** The ARCH hygiene mass (F-046, F-047, F-050, F-051, F-053, F-054, F-056,
F-060–F-068) is large, high-quality, and every entry ends "grants NO authority." Under §6.1 that
work has enormous option value and zero terminal value. Without a per-family stopping rule, strict
ordering does not terminate — it becomes a licence for unbounded hygiene.

**Test invariance, don't assert it.** "Provably invariant" means *measured*: hold the family's
result fixed while varying the unresolved term across its plausible range. If the result does not
move, the term is not binding for that family and L0 is sufficient *for it*; if it moves, resolve
the term before L1. This is the F-036 method — vary the knob, diff the ledger — applied to contract
terms rather than config knobs.

**Claim binding.** Claims live in the existing `docs/current-findings.md` (§6.2 rules 1 and 5 —
extend the doc that owns conclusions, do not build a parallel store). Every non-terminal finding
carries `Family:` and `Contract:`. A claim is comparable only to claims sharing its contract
identity; `Contract: UNKNOWN` is permitted and honest, but carries **no comparability and settles
nothing**.

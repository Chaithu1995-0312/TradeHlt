# Discovery-First Program — Phenomena → Ontology → Engines

## Context

An external model proposed a 10-engine layered architecture. Two revisions later, the frame is
**discovery-first**: no engine is defined by name in advance. Discovery runs, phenomena are found,
independence is measured, semantics are assigned, an ontology entry is registered, and an engine is
born **only** when a phenomenon owns a distinct problem. The engine is the *last* artifact, not the
goal of the experiment.

This is also better-governed than engine-first: the Funding Ledger requires a **new ontology** to
reopen a killed axis, and a *discovered* decomposition is a new ontology, where "Trap Engine" is the
old one renamed.

### Findings that shaped the design (all verified at source this session)

**(1) The observation space is not clean — decisive for discovery specifically.** F-051:
centered-swing binding is non-PIT, contaminating **10 of 38 canonical dims**, `differ_rate ≈ 0.635`.
Discovery *amplifies* leakage: hypothesis testing is protected by a pre-registered target;
unsupervised structure search has none and will preferentially select leaking dims. FC1-A
(implemented 2026-07-11) provides a causal binding, making this tractable — and exploitable (A2).

**(2) GPU is unnecessary and unavailable.** 70,081 M15 rows/instrument; 6 crypto × 38 dims ≈ 16M
floats. Verified: **no torch, no CUDA, no faiss**. Present: sklearn 1.8.0 (incl. `HDBSCAN`,
`mutual_info_classif`), numpy 2.4.4, scipy. GPU leaves the critical path.

**(3) Phase A has two prior runs.** F-023 clustered this exact space (k=4): distinct anatomy, all
`win ≈ 0.34`, `mean_R ≈ 0` — shape, not expectancy. IC-003B attempted representation change for
compressible structure: `k*` unstable, "stop chasing shape libraries."

**(4) `reality_gap ≡ mfe_capture − e_gross`** (`exit_grid.py:191-193`; `min_cost` cancels).
`mfe_capture` is tie-break-immune (`horizon_excursion`); `e_gross` is tie-break-exposed
(`forward_walk`, `:127`). The unmeasured same-bar SL∧TP convention inflates F-025's `+4.16R`
one-for-one. **Discovery cannot exceed the quality of its labels** ⇒ Phase 0 runs first.

**(5) Ontology generation needs no new architecture.** `configs/formulas/market_ontology.yaml` v1.3
is the WHAT-layer authority with stable IDs, a `lifecycle` ladder
(`proposed → research → registered → parity_verified → consumable → deprecated`), a `depends_on`
DAG, and `authority: user_approved ... grants no promotion authority (§6.5)` already written in.

### The epistemic rule

**Prior findings are mandatory CONTROLS and DESIGN CONSTRAINTS — never vetoes.** No engine is
forbidden by name; each is designed as if for the first time. A well-powered prior null defines the
control arm the candidate must beat:

| Prior | NOT used as | IS used as |
|---|---|---|
| F-023 (shape not expectancy) | "don't cluster" | objective is **incremental information on outcome**, not morphology |
| IC-003B (`k*` unstable) | "no shape libraries" | **stability is a gate**, not an afterthought |
| F-043 (regime redundant 10/10) | "regime forbidden" | within-tercile-shuffle + lagged-regime **control arm** |
| F-020 (25/25 significant, 0 economic) | "don't test" | **economic effect-size floor**; significance saturates at N=70k |
| F-041B (0/8 zones E>0) | "zones forbidden" | honest `forward_walk` re-derivation, never stored labels |
| F-055 / F-038 / F-044 | — | `use_bitnet`, `rr_fusion.enabled` stay `false` |

---

## Pipeline

```
PIT-CLEAN DATA → CANONICAL FEATURES → REPRESENTATION → MULTIPLE DISCOVERY METHODS
  → INFORMATION TEST (incremental) → SEMANTIC INTERPRETATION (LLM, outcome-blind, recorded first)
  → ECONOMIC TEST (M4) → ONTOLOGY ENTRY → STATE CONTRACT → ENGINE → PROMOTION GATE
```

**Note the ordering of semantic interpretation:** it sits *before* the economic result is read. An
LLM that sees which clusters won and then explains them will confabulate a story for noise. Blind
interpretation, recorded first, makes the semantic label a **pre-registered hypothesis**.

## Governance frame

- **Isolation.** All work under `src/research/`. `engine_runner.py:53`
  `EXPECTED_ENGINES = {"crt","gaussian","zone_gate","rr"}` **untouched**. `forward_walk.py` and
  `src/interpreters/contract.py` stay **byte-identical**.
- **Authority ceiling.** Authority Level 1–2 (§6.5). Spine promotion needs `PROMOTE` from
  `qualification.py` **plus** measured ΔG001 — later, separate, gated.
- **Pre-registration before every phase** (E-001 six questions, frozen thresholds, stated prior,
  closure rule), per `docs/research/preregistration-program-9.md`.
- **Discovery confers no authority.** A discovered phenomenon is *information* until it clears M4.

---

## Phase 0 — Intrabar path (prerequisite: measurement precedes inference)

**0A · Ambiguity census** — `src/research/path/ambiguity_census.py`; reads `forward_walk`, never
edits it; synthetic test asserts reconstruction exact vs kernel. Three populations counted
separately: **P1** same-bar SL∧TP (`:127`, directional bias in `e_gross` — the only one touching
F-025), **P2** OCO double-edge (`:221` D1, selection effect), **P3** fill-bar TP suppression
(`:251` D2). Per instrument × per F-025 grid cell.
**Prior:** F-025 reports `same_bar 9.25%` — registered so the census isn't sold as discovery.
**Stop gate:** pooled `max_bias_R < 0.05R` ⇒ close with a cheap null; 0B–0D unfunded.

**0B · M5 resolution** — `m5_alignment.py`; `m15_children()` on `resample.bucket_floor(ts,"M15")`
(`resample.py:73`). Guards: corpus-parity precondition (failures **excluded**, never patched);
read-window invariant; measurement-only firewall. Three buckets: `RESOLVED_SL_FIRST` /
`RESOLVED_TP_FIRST` / `RESIDUAL_AMBIGUOUS`.

**0C · Path model** — **A RESOLVER** (sees bar `t`; retrospective only) vs **B FORECASTER**
(bars `< t`; headline). Reusing `replay_similarity_index.py` as a library (`decay_lambda=0.0`,
`use_faiss=False` — faiss absent anyway), new `aggregate_path_stats` (existing
`aggregate_top_k_stats` defines `win_rate` as `rr>=1.0`, a trade notion not a path notion).
IS-only index, embargo `max(atr,sma,volume)` windows, self-exclusion.
**Calibration, not accuracy:** reliability curve w/ per-bin n, Brier, ECE, PIT; gated on Brier skill
vs **B1** base rate and **B2 geometry `tp_dist/(sl_dist+tp_dist)`**. Beating B1 but not B2 is a
first-class FAIL: `GEOMETRY_REDUNDANT`.
**Prior:** magnitude targets (MFE/MAE) show skill; order target (`P(low_first)`) returns REDUNDANT.

**0D · Scope + F-025 rule** — verbatim: *M5 does not resolve intrabar order; each M5 bar carries the
identical ambiguity recursively. Bound-tightening (15→5 min, ~3×) plus inference. `P(low_first)` is
an estimate, not a measurement. No M1 exists (`fetch_and_verify_binance.py:50` has no `1m`), so this
floor cannot currently be lowered.*
Revision rule frozen **before** the number is seen: Δ<0.10R → `Update:` confirming robustness;
0.10–0.50R → corrected range + restated `ceiling_utilization`; >0.50R → full `CORRECTED:` (§6.2
rule 4 + E-001 phrase), propagated to all citing docs. **Pre-committed bound:** even at Δ>0.50R this
does not overturn F-019/020/021/035 (PF ≪ 1) — it moves the gap *decomposition*, not the *sign*.
Report per-cell; tight-TP/wide-SL cells collide most, so grid *ranking* may shift.

---

## Phase A — Discovery (plural methods, not "clustering")

**A1 · PIT-clean substrate (blocking).** Build under the **causal** binding (FC1-A;
FC1-D rolling-causal `volatility_regime`). Gate asserts none of F-051's 10 contaminated dims enter
under centered semantics. **No discovery runs on the default binding.**
New: `src/research/discovery/substrate.py`.

**A2 · Leakage quantification (the asset).** Identical discovery under **both** bindings; report the
delta. If structure is materially richer under centered, that delta **is** the leakage, quantified
at representation level — a number the repo lacks (PC-2 failed at ledger level). Prior: centered
looks richer, and that richness is contamination.

**A3 · Method roster — pre-registered, stratified by dependency cost.** Discovery ≠ clustering.
The roster is **frozen before running** (see A5).

| Tier | Methods | Dependency |
|---|---|---|
| **1 — runs today** | PCA · KernelPCA · Isomap (representation); KMeans · GMM · **HDBSCAN** · Spectral (partition); symbolic tokens (`candle_state/encoder.py`); sequence/DTW (`ic003b_sequence_geometry/`); information-bottleneck-style feature selection via `mutual_info_classif` | **none** (sklearn 1.8 + scipy) |
| **2 — small add** | UMAP; causal discovery (PC/GES) | `umap-learn`, `causal-learn` |
| **3 — deferred** | contrastive · predictive coding · self-supervised · diffusion embeddings | **torch** — a real decision in a deliberately dependency-light repo; deferred until Tier 1–2 justify it |

**Tier 1 alone is a far broader instrument than the prior two attempts** (F-023 = KMeans only;
IC-003B = DTW/euclidean sequences). Tier 3 is gated on Tier 1–2 producing *something*, so torch is
never added speculatively.

**A4 · Objective — incremental information, not shape.** The optimization target is
**conditional mutual information given what is already known**:

```
ΔI  =  I(Z ; Y | E)        Z = discovered phenomenon
                           Y = forward outcome (forward_walk-derived, never stored labels)
                           E = existing engines' outputs + bar geometry + current vol level
```

`ΔI ≈ 0` ⇒ kill it, regardless of how clean the clusters look. This is the direct formalization of
"morphology vs expectancy" and it is what makes engines *independent* by construction.

**Two estimator disciplines, both non-optional:**
- **Plug-in MI is biased upward** on finite samples with continuous targets — it will manufacture
  positive ΔI from noise. Use a **permutation-calibrated** estimator: report
  `ΔI − E[ΔI under label permutation]` with the permutation null distribution, never raw ΔI.
- **Bits are not money (F-020).** An economic effect-size floor gates alongside significance;
  IG ≈ 0.002 bits was "significant" at N=70k with zero economic pockets. Report ΔI **and** the
  economic delta; a phenomenon passing on bits alone is `INFORMATION_ONLY` (Authority Level 1).

**A5 · Method multiplicity control (the new p-hacking surface).** Running ten methods and reporting
the best is method-level p-hacking. Therefore: the roster is **frozen pre-registration**;
Benjamini-Hochberg correction spans the **full method × phenomenon cohort** (reuse
`qualification.finalize()`); **every method is reported including failures**; and adding a method
post hoc requires a new pre-registration, not an edit.

**A6 · Structural gates.** Each surviving phenomenon must clear: **stability** (`k*` / cluster
assignment stable under bootstrap and across instruments — IC-003B's lesson as a gate);
**recurrence** (recurs out-of-sample, not merely partitioning IS); **outcome separation** (F-023's
`win≈0.34 / mean_R≈0` is the explicit null to beat).

**Honest prior:** F-023 and IC-003B both point toward "shape, unstable `k*`, no outcome separation."
If Tier 1–2 return that, Phase A closes with a finding and **B–E are not funded** — a legitimate,
cheap outcome, and the third independent confirmation. This is the outcome to bet on.

---

## Phase B — Intent discovery

For each surviving phenomenon: *is this a separate problem?* Measured, not asserted.

- **Independence** = ΔI above, computed against every already-admitted phenomenon, so admitted
  engines are mutually non-redundant **by construction**.
- **Prior-derived control arms mandatory:** vol-correlated phenomena face F-043's within-tercile
  shuffle + lagged-regime control; zone-like phenomena face the geometric baseline.
- **Verdicts:** `INDEPENDENT` / `REDUNDANT` / `INFORMATION_ONLY` / `INSUFFICIENT`. `REDUNDANT` means
  it **collapses into an existing engine** — an explicitly good outcome that shrinks the architecture.

Only `INDEPENDENT` phenomena continue. Names are assigned **last**, from what the phenomenon owns.

---

## Phase C — Semantics → ontology → contract

**C1 · Semantic interpretation (LLM, outcome-blind).** The LLM reads latent structure + descriptive
statistics and proposes a natural-language abstraction. It **does not see outcome labels or economic
results**; its interpretation is written to an immutable artifact **before** economic results are
read. This is the LLM's genuine contribution — semantic abstractions over latent structure a human
might not name — and blindness is what makes it a hypothesis rather than storytelling.
Enforced by `test_interpretation_outcome_blind.py` (the input payload schema excludes outcome
fields; a test asserts no outcome key can reach the prompt).

**C2 · Ontology entry.** Each interpreted phenomenon registers in
`configs/formulas/market_ontology.yaml` under a new `discovered_phenomena` section with a **`PH-0NN`**
prefix (distinct from feature-math `FM-0NN`), at `lifecycle: proposed`, carrying `depends_on` edges
into the canonical DAG plus its discovery method, ΔI, controls beaten, and evidence pointer.
Promotion along the existing ladder is evidence-driven; the file already declares it grants no
promotion authority.

**C3 · State contract.** `src/interpreters/contract.py` is frozen and its `meta` is explicitly
opaque/decision-forbidden (`:64-74`), so non-directional answers have no typed channel. **Compose,
don't mutate:** sibling `src/research/engines_v2/contract.py` defining `EngineReading` (`question` /
typed `answer` / `confidence` / declared `consumes` / optional wrapped `InterpreterReading` /
`trace_id`), `BaseEngine` mirroring `BaseInterpreter`'s validate-never-trust-subclasses pattern
(`:170`). Directional engines reach measurement only via the unchanged `adapter.py` →
`forward_walk` → `qualification.py`. No new oracle.

Enforcement — `tests/research/engines_v2/`:

| File | Enforces |
|---|---|
| `test_engine_contract.py` | schema conformance, `confidence` ∈ [0,1], typed `answer` |
| `test_engine_determinism.py` | same window → identical `EngineReading` incl. `trace_id`; double-run byte parity |
| `test_engine_responsibility.py` | no two engines share a `question`; reads only declared `consumes` (recording `Mapping` proxy raises on undeclared access) |
| `test_engine_dependency_direction.py` | AST import graph is a DAG in declared order — no back-edges |
| `test_engines_v2_isolation.py` | **governance teeth** — `EXPECTED_ENGINES` unchanged; no `src/core\|engines\|config_layer` import of `research.engines_v2` |

Existing engines (CRT, RR, Gaussian, BitNet, ExecutionIntent) get **contract wrappers only** — zero
behavioral delta; wrappers cannot flip `use_bitnet` / `rr_fusion.enabled` (test-asserted).

---

## Phase D — Engine birth + promotion

An engine is built **only** for a phenomenon that is `INDEPENDENT`, interpreted, ontology-registered,
and contract-bound. Measured through the unchanged adapter → `forward_walk` → `qualification.py`.
Promotion to the spine requires `PROMOTE` **plus** measured ΔG001 — out of scope here.

## Phase E — Continuous evolution (design only)

Each engine reports failure modes and residual uncertainty; a neighbor may explain them; the LLM
proposes follow-ups (inert until pre-registered + gated). Enters the existing Funding Ledger loop.
**Not built unless Phase B yields ≥1 `INDEPENDENT` phenomenon** — an evolution loop over zero
engines is architecture without authority (§6.5). Pre-committed.

---

## Verification

```powershell
# Phase 0
python -m pytest tests/research/path tests/research/test_forward_walk.py `
                 tests/research/test_resample.py tests/research/test_resample_corpus_parity.py -q
python scripts/research/path_ambiguity_census.py --config configs/research/research_config_path_crypto.json

# Phase A (PIT gate blocking; centered run is A2-only)
python -m pytest tests/research/discovery -q
python scripts/research/discovery_run.py --binding causal
python scripts/research/discovery_run.py --binding centered --a2-leakage-only

# determinism (load-bearing): hashes must match
python scripts/research/discovery_run.py --out results/research/discovery/run_a.json
python scripts/research/discovery_run.py --out results/research/discovery/run_b.json
Get-FileHash results/research/discovery/run_a.json, results/research/discovery/run_b.json -Algorithm SHA256

# Phases C-D
python -m pytest tests/research/engines_v2 tests/research/narration tests/interpreters -q
python -m pytest tests/research/engines_v2/test_engines_v2_isolation.py -q
python -m pytest tests/test_formula_registry.py tests/test_feature_lineage.py -q   # ontology edits

# full regression before registering any finding
python -m pytest tests/research tests/interpreters tests/test_current_findings.py `
                 tests/test_config_integrity.py tests/test_behavior_census.py -q
```

Result JSON bodies must contain no wall-clock (Program 9 E-001 Q1 rule).

---

## Spine-touch register (all gated)

| Would-be change | Status |
|---|---|
| `engine_runner.py:53` `EXPECTED_ENGINES` | **forbidden in this plan** |
| `engine_runner.py:164/:188` trap/breakout | **gated** — needs `PROMOTE` + measured ΔG001 |
| `src/research/measurement/forward_walk.py` | **byte-untouched** |
| `src/interpreters/contract.py` | **byte-untouched** — sibling contract instead |
| `market_ontology.yaml` | **additive only** — new `discovered_phenomena` section, `PH-0NN` ids, `lifecycle: proposed` |
| `use_bitnet`, `rr_fusion.enabled` | stay `false`; test-asserted |
| `configs/production/*.json` | untouched |

---

## Critical files
- `src/research/measurement/forward_walk.py` — `:127` tie-break, `:221` OCO D1, `:278` `horizon_excursion`
- `src/research/exit_grid.py:186-201` — the `reality_gap ≡ mfe_capture − e_gross` algebra
- `src/features/feature_pipeline.py:391-460` — F-051 centered bind; FC1-A causal path
- `docs/governance/FC1-A-SWING-CAUSAL-implementation-contract-2026-07-11.md` — causal binding contract
- `configs/formulas/market_ontology.yaml` — WHAT-layer authority; lifecycle ladder for `PH-0NN` entries
- `src/research/candle_state/{encoder,m5_incremental}.py` · `src/research/ic003b_sequence_geometry/`
- `src/interpreters/contract.py` + `adapter.py` — frozen contract, sole bridge to measurement
- `src/research/qualification.py` — sole promotion gate; `finalize()` supplies cohort BH
- `docs/research/preregistration-program-9.md` — pre-registration template

# Model-Intent Forensics → Evidence-Driven, Gated Feature Expansion

## Context

Two forensic reports (`reports/OHLCV_LINEAGE_FORENSICS.md`, `reports/FEATURE_REACHABILITY_AUDIT.md`)
plus an external LLM critique asked: are the ~20 "ACTIVE_VIA_MODEL" canonical features dead weight, and
should every model consume all 38 features and be retrained? Directive: **no feature deletion; no forced
100% utilization; achieve 100% *understanding* of feature ownership and model intent first, then perform
evidence-driven expansion and retraining — measure-first, gate everything.**

### Reframed objective (binding)

Replace "make all 38 features 100% used" with three distinct targets:

```
100% feature UNDERSTANDING   — every feature's market meaning + current owner is known
100% justified OWNERSHIP     — every model's feature set is explained by intent (A) or evidence (B)
100% measurable CONTRIBUTION — every claim of value is backed by decision-flip / ΔG001 measurement
```

Keep two questions **separate** throughout — they are different problems:

- **Question A — intended information ownership:** what each model was *designed* to consume, and *why
  it deliberately ignores* the rest (different time horizon · independent vote · diversification against
  correlated failure · structural filter vs predictor). Specialization is often an advantage.
- **Question B — marginal information value:** which currently-ignored feature *measurably* improves
  predictive or decision quality, net of cost and **net of ensemble-correlation cost**.

A feature can be correctly owned (A) yet still not worth adding elsewhere (B), and vice-versa.

### Why this matters / intended outcome

Investigation (3 Explore agents + direct reads) suggests the binding ZoneGate defect is **label/exit
quality, not feature count** — but those claims are **hypotheses to independently verify (Phase 5), not
axioms**. The intended outcome is: a canonical **Model-Intent & Feature-Ownership Matrix** (the authority
all later work defers to), an empirical importance + decision-flip measurement, independent verification
of the ZoneGate/label/registry claims, and only then scoped, gated, advisory-first expansion/retraining
measured against G001/M4. Per CLAUDE.md §6.5, nothing earns production weight without demonstrated ΔG001.

## Doctrine guardrails (binding on every phase)

- **No deletions.** Features and config values are preserved; reclassification is documentation only.
- **Findings are not axioms.** The ZoneGate broken-label, registry split-brain, and model-internal claims
  below are flagged `[TO VERIFY]` and must be independently confirmed (Phase 5 / Phase 1 split-brain
  check) before they drive any architectural decision. Surface disagreements as §6.2 `TruthConflict`,
  never silently "fix".
- **Authority Ladder (§6.5):** information ≠ value ≠ authority ≠ architecture. Phases 1–4 earn
  research/docs authority only. Expansion/retrain (6) is advisory-first; **no production promotion**
  unless it clears ΔG001 under governed gates (Phase 8, separate).
- **Specialization is a feature, not a bug.** Forcing all models onto the same 38-vector risks
  `identical latent reps → correlated errors → weaker ensemble`. Expansion must be shown not to increase
  inter-model score correlation / correlated failure — this is a measured gate, not a preference.
- **Falsification backdrop:** F-019…F-040 falsified the *entry-information* edge across all axes tested;
  standing conclusion "binding constraint = EXECUTION MODEL, not predictability." The untested,
  high-ROI angle here is **label quality**, never isolated by that program — frame to reach a clean
  conclusion, not to manufacture an edge.
- **Research isolation:** all measurement/retrain runs in `src/research/` + `scripts/research/` via
  `forward_walk(exit_model="intrabar_fixed")` + the M4 `QualificationGate`; production spine and
  `configs/production/*` untouched until a separate governed promotion.

---

## Phase 1 — Model-Intent Reconstruction (DOCS · no code) — answers Question A

Consolidate verified per-model intent (already established from agent reads, with file:line). For each
model state: primary purpose · market phenomenon · features consumed · **why it deliberately ignores the
rest** (horizon / independent-vote / diversification / structural-filter).
- **CRT** (`crt_engine_v2.py`): structural state machine; raw Candle + internal EMA(2,5) + internal
  ATR(14); ignores canonical momentum/volatility *by design* → KEEP SPECIALIZED.
- **Gaussian** (`heuristic_gaussian_engine.py:305`): momentum Gaussian on 3/38 → expansion *candidate*.
- **RR** (`rr_engine.py:45`): candle-polarity on close/high/low (3/38); `min_rr` dead-but-kept →
  KEEP SPECIALIZED.
- **ZoneGate** (`zone_gate_engine.py` + `live_engine.py:202`): full-38 weighted-Gaussian; fail-open to
  0.5/pass on registry error.
- **BitNet** (`bitnet_inference.py:317`): 6-feature hard-reject gate (off by default) → candidate.
- **Regime/Breakout/Trap** (`engine_runner.py:144-213`): 3 features each → candidate.
- **Fusion** (`fusion_engine.py`): regime-weighted blend of 4 engine scores; not feature-driven.

**Split-brain check (here, not later):** `[TO VERIFY]` `models/zone_gate_registry.json` (referenced by
`model_registry.py:877`) appears empty (0 zones) while `models/zone_registry.json` (loaded by live
`BitNetZoneGate`) holds 8 zones — confirm which the active config (`v2_multi_2026_04`, branch `patch`)
actually scores through. If runtime loads the empty one, ZoneGate is silently fail-open in production →
`TruthConflict`.

---

## Phase 2 — Feature-Ownership Matrix (DOCS · the canonical authority)

The **deliverable everything else defers to.** Existing-doc-first: extend `docs/topics/feature-schema.md`,
or promote `docs/topics/model-intent-and-feature-ownership.md` from `_template.md`. Build the
**Model × 38-Feature matrix**, each cell ∈ {REQUIRED, BENEFICIAL, OPTIONAL, KEEP-SPECIALIZED, UNKNOWN}
with a WHY tagged as **(A) intent** or **(B) evidence-pending**. Built on verified consumption maps —
*not* the reports' biased "VECTOR_ONLY ≈ low value." No deletions; no expansion decided yet. Register a
finding (F-04x) capturing the matrix. **Finalize this before any retraining/architectural change.**

---

## Phase 3 — Static Weights + Permutation Importance (MEASURE) — begins Question B

Replace the report's biased **zero-ablation** with distribution-preserving measurement:
1. **Static weight read (cheapest, no model run).** New `scripts/research/zone_weight_introspection.py`:
   load `zone_registry.json`, emit per-zone + aggregate per-feature weights and `zero_indices` — read
   directly which of the 38 each zone uses.
2. **Predictive importance (reuse existing).** Run `scripts/research/edge_attribution_study.py`
   (`sklearn.permutation_importance` + mutual-info + drop-column LOO + survival/coverage gates) on the
   canonical set. **Do not build a new ablation script.**
Outputs → `docs/analysis/feature-importance-<date>.md` (point-in-time). Research authority only.

---

## Phase 4 — Decision-Flip Importance Through the Full Spine (MEASURE) — sharpest Question B

The question that actually matters: does perturbing a feature change a *trade decision*? Small new harness
reusing the spine-as-hypothesis adapter + `forward_walk`: **permute (not zero)** each feature column,
re-run the fusion decision path, count decision flips per feature → the **Decision Influence Matrix**
(ΔZone, ΔFusion, % trade-flips). Consistency check: a feature zeroed in every zone must show ~0 flips.

**Ensemble-correlation measurement (new, per review):** compute pairwise correlation of the 4 engine
scores at baseline, and (in Phase 6) re-compute after any expansion — expansion that raises inter-engine
correlation / correlated-failure is penalized regardless of marginal predictive gain. Record as a finding.

---

## Phase 5 — ZoneGate Label-Quality Verification (independent confirmation)

`[TO VERIFY]` Direct reads show 6/8 zones with negative mean_RR and ~96–98.65% SL-hit training labels
(zone_0: TP 1.3% / SL 98.65% / mean_RR −0.029, n=20,708) — consistent with F-038/F-025 but **not yet an
architectural assumption.** Independently confirm: (a) the metadata reflects the labels the zones were
actually fit on (not stale meta); (b) regenerate a sample of those labels via
`src/research/measurement/forward_walk.py` (`intrabar_fixed`) + `CostModel(cfg.round_trip_bps)` and
compare to stored outcomes; (c) confirm the registry that runtime loads is the one carrying these labels
(ties to Phase 1 split-brain). Output: a finding that either confirms "label-quality is the dominant
ZoneGate defect" or refutes it. **Go/No-Go gate for Phase 6** lives here: expand/retrain only if Phase 4
shows a currently-ignored feature with material decision-flip influence (B), **or** Phase 5 confirms the
label defect.

---

## Phase 6 — Scoped, Evidence-Driven Expansion / Retrain (advisory-first · ONLY if Go)

Sequenced; CRT/RR untouched (Question A says specialized by design).
- **Stage 6a — ZoneGate label/exit fix (root cause):** regenerate honest labels (forward_walk
  intrabar_fixed + `cfg.round_trip_bps`), locate the zone-registry builder (BitNetSearchEngine / the
  script that produced `zone_registry.json`), retrain a *candidate* registry to a **research path (NOT
  `models/`)**.
- **Stage 6b — feature-ownership expansion (gated on 6a + Phase 4):** expand Gaussian/Regime/BitNet to
  their *relevant* features only; retrain candidates in research paths.
Each stage measures: decision-flip vs baseline, **inter-engine correlation delta**, `metrics_oracle`
parity, M4 `QualificationGate`, `GoalValidator.evaluate()` vs G001. Register PROMOTE/REJECT findings.

**Cost configurability (user ask):** reuse the **existing** knob `ResearchConfig.round_trip_bps`
(`configs/research/research_config.json` → `costs.round_trip_bps`; `src/research/costs.py` already
config-driven). Thread `cfg.round_trip_bps` through all new label/retrain code; **never hardcode 12**;
replace literal "12bps" *display* strings in new code with config-derived values (follow the existing
`provenance_block(...)` pattern). Production-side cost knob out of scope unless separately requested.

---

## Phase 7 — G001 / M4 Validation (MEASURE · decides authority)

Run candidates through the frozen rails: M4 `QualificationGate` (7 gates, intrabar_fixed + configurable
bps), `metrics_oracle` 2-instrument determinism parity, `GoalValidator` report vs the G001 spec. A
candidate earns *research* authority on PROMOTE; it earns nothing toward production unless ΔG001 is
demonstrated **and** ensemble-correlation did not worsen.

## Phase 8 — Production-Promotion Discussion (NOT in this plan)

No `ModelRegistry.promote()` / `models/` write / `configs/production/*` change here. Promotion is a
separate, governed decision contingent on Phase 7 ΔG001 — explicitly deferred per §6.5.

---

## Files

**Create:** `scripts/research/zone_weight_introspection.py` · decision-flip + correlation harness
(`scripts/research/`) · `docs/analysis/feature-importance-<date>.md` · Stage 6a/6b retrain drivers
(only if Go).
**Modify (additive):** `docs/topics/feature-schema.md` *or* new `model-intent-and-feature-ownership.md`
(the Matrix) · `docs/current-findings.md` + §6.2 Truths Index in `CLAUDE.md` (F-04x: matrix; importance;
correlation; label verdict; expansion result) · `MEMORY.md` + `memory/project_model_intent_feature_ownership.md`.
**Reuse (do not rebuild):** `scripts/research/edge_attribution_study.py` · `src/research/measurement/forward_walk.py`
· `src/research/costs.py` · `src/research/qualification.py` · `src/analytics/metrics_oracle.py` ·
`src/config_layer/goal_validator.py`.

## Verification

- **Phases 1–2:** Matrix complete (every model×feature cell tagged A/B with WHY); split-brain documented.
- **Phases 3–4:** static weights + `edge_attribution_study.py` + decision-flip harness run clean and
  reconcile (zeroed-everywhere feature ⇒ ~0 flips); baseline inter-engine correlation recorded.
- **Phase 5:** label regeneration reproduces (or refutes) stored zone outcomes; verdict registered.
- **Phases 6–7:** `pytest` green per `docs/reference/testing.md`; `metrics_oracle` parity on candidate
  ledgers; M4 + GoalValidator attached; **no diff under `models/` or `configs/production/`**; expansion
  shows correlation not worsened.
- **Cost knob:** flip `costs.round_trip_bps`; confirm labels/net-RR move; grep new code for literal `12`
  cost constants (must be none).
- Every phase ends with a §6 SESSION LOG entry; findings flipped same-turn (Findings Mandate).

## Risks / most-likely failure mode

- **Forcing all models onto all 38 features** → eliminates intentional specialization, raises correlated
  error, adds complexity with no ΔG001. Guarded by Question-A/B separation + the correlation gate.
- **Treating unverified ZoneGate/label claims as fact** → mitigated by the `[TO VERIFY]` Phase 5 gate.
- **Most likely empirical outcome is another null** (F-019…F-040) — acceptable, high-knowledge-ROI *iff*
  the label-quality question is cleanly answered.

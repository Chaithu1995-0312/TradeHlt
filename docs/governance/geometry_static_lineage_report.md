# Geometry Static Lineage Report — Gate 5 Evidence Packaging

> **Purpose:** Consolidate all Gate 5 static lineage evidence into a single durable artifact.
> Gate 5 was declared complete 2026-07-08 (see `assistant_project.md` session log entry 2026-07-08,
> lines 172-178). This report packages the distributed evidence without redoing Gate 5,
> broadening the audit, changing classifications, remediating code, or beginning Gate 6.
>
> **Source artifacts:**
> - `docs/governance/geometry_contradiction_report.md` (Gate-5 lineage resolutions, lines 57-69)
> - `docs/governance/geometry_semantic_adjudication.jsonl` (110 records, reachability fields)
> - `docs/governance/geometry_family_registry.json` (23 families, 55 variants)
> - `docs/current-findings.md` (F-050 evidence block, lines 677-688)
> - `reports/FEATURE_REACHABILITY_AUDIT.md`
> - `assistant_project.md` (2026-07-08 session log, lines 172-178)
>
> **Date:** 2026-07-09
> **Author:** claude (evidence packaging only)
>
> **Packaging commit:** `ed1e418e47489dc8d76a2f7cc4e0cd340348b661`
>
> **Input artifact SHA-256 fingerprints:**
> | Artifact | SHA-256 |
> |----------|---------|
> | `docs/governance/geometry_semantic_adjudication.jsonl` | `a516fb8657efddc73478d36660154e3db254bce1d770d4e0a84e8de27559ec52` |
> | `docs/governance/geometry_contradiction_report.md` | `bd68496925eb48644ab58cce908972ea763f8478e7faef1a0874cd6913540334` |
> | `docs/governance/geometry_family_registry.json` | `8fd955be0fa870c4b74758f4e845e3f6764b38a2f5de96b7227e86011f465be5` |

---

## CHECK 2 — 71→3 Reproducibility

**PRE_GATE5_UNKNOWN_DENOMINATOR_NOT_REPRODUCIBLE**

No machine-readable pre-Gate-5 snapshot of the 71 UNKNOWN count exists. The frozen
`geometry_semantic_adjudication.jsonl` was created AFTER Gate 5 was completed, so it
reflects the post-resolution state. The 71 count is attested only in the session log
(`assistant_project.md` 2026-07-08 entry, line 175): *"UNKNOWNs collapsed 71→3"* with
subcomponents "artifact_reachable 62 (ALL Gate-5-deferred by design), training_reachable 9."

A mechanical count of the post-Gate-5 adjudication matrix confirms:

| Metric | Count |
|--------|:-----:|
| HISTORICAL_REPORTED_PRE_COUNT | 71 |
| MECHANICALLY_REPRODUCIBLE_FINAL_UNKNOWN_COUNT | 3 |

The 3 remaining UNKNOWNs are mechanically countable from the frozen adjudication matrix
by selecting records where `decision_reachable == "UNKNOWN"`.

---

## 1. F-050: `retest_depth` / `disp_strength` cached_features → training chain

### 1.1 Claim/Follow-up ID
F-050 (CS-1 from F-049 Gate-2B-P0 calibration). Also affects FM-021 / FM-020 name collision.

### 1.2 Affected Census/Adjudication Records
- `GEO-D-db6351fa92` (scorer disp_move site at `crt_gaussian_scorer.py:187`, SAME_MATH_DIFFERENT_NAME, FAM-01-F1-BODY)
- `GEO-D-286a0ea567` (scorer retest_retrace site at `crt_gaussian_scorer.py:190`, NON_EQUIVALENT_SAME_NAME, FAM-16-F6-CROSSRETRACE)

### 1.3 Producer File:line
- **Primary producer:** `src/config_layer/crt_gaussian_scorer.py:187-192` — computes
  `retest_retrace = abs(retest.close - disp.open) / disp_move` and emits as `"retest_depth"`
- **Sibling producer:** `src/config_layer/crt_gaussian_scorer.py:194` — computes
  `disp_str = wick_size / atr` and emits as `"disp_strength"`
- **Cache producer:** `src/config_layer/crt_engine_v2.py:1372` — caches both values into
  `state.cached_features` with comment `:1368-69`: *"Uses displacement-retrace definition … to
  match the empirical calibration in CRTGaussianScorer"*

### 1.4 Full Static Lineage Chain
```
crt_gaussian_scorer.py:187-192  (cross-candle retest_depth definition)
  → crt_engine_v2.py:1372       (cached_features snapshot, intentional match)
    → crt_engine_v2.py:1121-1127 (snapshot into state)
      → opportunities.jsonl      (detection stream, F-022 artifact labels)
        → stage1_dataset_builder.py (training dataset construction)
          → master_{crypto,forex,multiasset}_training.jsonl (training corpora)
            → trainer.py:807     (BitNet training chain)
```

### 1.5 Consumer File:line or Explicit No-Consumer Evidence
- **Training consumer:** `src/training/trainer.py:807` (BitNet model training)
- **Scoring consumer (live):** `src/config_layer/crt_engine_v2.py:1733` (`approve_with_soft_conf`
  reads `cached_features` when `use_bitnet=true`)
- **No consumer (pipeline):** The pipeline FM-021 `retest_depth` (`feature_pipeline.py:579-584`)
  is a different definition; no consumer reads the pipeline value into the same model path

### 1.6 training_reachable Verdict
**YES** — the cached_features → opportunities.jsonl → stage1_dataset_builder → master training
JSONL → trainer.py:807 chain is confirmed static.

### 1.7 artifact_reachable Verdict
**YES** — `opportunities.jsonl` files contain the cached values; `master_*_training.jsonl` files
contain them; BitNet model artifacts (if trained) embed them.

### 1.8 score_reachable Verdict
**YES** — when `use_bitnet=true`, the cached `retest_depth` enters `bitnet_score()` at
`crt_engine_v2.py:1733` and affects the score/rejection gate.

### 1.9 decision_reachable Verdict
**LATENT** — `use_bitnet=false` on the active config (`v2_multi_2026_04.json`), so the gate is
inert. If `use_bitnet` were enabled, the cached value would reach the decision gate.

### 1.10 Exact Evidence Commands/Queries Used
- Static source inspection of `crt_gaussian_scorer.py:187-194`
- Static source inspection of `crt_engine_v2.py:1368-1372, 1121-1127`
- Static source inspection of `stage1_dataset_builder.py` (training pipeline)
- Static source inspection of `trainer.py:807` (BitNet training consumer)
- Config inspection: `configs/production/v2_multi_2026_04.json` → `use_bitnet:false`

### 1.11 Corpus/Artifact Evidence Inspected
- `src/config_layer/crt_gaussian_scorer.py`
- `src/config_layer/crt_engine_v2.py`
- `src/training/stage1_dataset_builder.py`
- `src/training/trainer.py`
- `configs/production/v2_multi_2026_04.json`
- `docs/governance/geometry_contradiction_report.md` (lines 58-65)

### 1.12 Result
**YES** — chain confirmed. The cross-candle definition is internally intentional (comment
`:1368-69`); the defect is the **name collision** with FM-021/FM-020, not the math.

### 1.13 Dependency/Blocker for UNKNOWN
N/A — resolved YES.

### 1.14 Finding IDs Affected
- **F-050** (primary — name collision confirmed, lineage resolved)
- **F-004** (BitNet inert on active config bounds economic exposure)
- **F-022** (opportunities.jsonl is detection stream, not trade ledger — the cached values
  flow through the same artifact)

### 1.15 Remediation Consequence (without performing remediation)
- **Remediation class:** rename/register — register the cross-candle quantity under its own FM-id
  (e.g. `displacement_retrace`) + rename emission keys in scorer and engine cache
- **No formula change required** — the math is intentional
- **No retrain required** — the model was trained on the cross-candle definition; renaming
  prevents future train/serve skew
- **Residual risk:** train/serve skew if any model trained on cached values is ever scored with
  pipeline FM-021/FM-020 values (mitigated by F-004: BitNet inert on active config)

---

## 2. CS-3: F2-as-Volume Proxy Corpus Activation

### 2.1 Claim/Follow-up ID
CS-3 (from F-049 Gate-2G contradiction pass).

### 2.2 Affected Census/Adjudication Records
- `GEO-D-d711a57aa8` (feature_pipeline.py:214 — F2 written into volume column,
  SAME_MATH_DIFFERENT_NAME, FAM-12-F2-RANGE)

### 2.3 Producer File:line
`src/features/feature_pipeline.py:214` — writes `high-low` (F2) INTO the volume column as a
tick-volume proxy when all-zero-volume corpora are detected (FX majors with missing volume).

### 2.4 Full Static Lineage Chain
```
feature_pipeline.py:214 (F2→volume proxy on zero-volume corpora)
  → downstream feature consumers reading volume_ratio, volume_spike
    → (conditional on zero-volume corpus being processed)
```

### 2.5 Consumer File:line or Explicit No-Consumer Evidence
- `volume_ratio` consumers: various feature consumers
- `volume_spike` consumers: various feature consumers
- **No consumer on repository corpora** — no majority-zero-volume corpus exists in `data/*_M15.csv`

### 2.6 training_reachable Verdict
**NO** — the path never fired on repository corpora.

### 2.7 artifact_reachable Verdict
**LATENT** — conditional on future zero-volume corpora being processed through the pipeline.

### 2.8 score_reachable Verdict
**LATENT** — same condition.

### 2.9 decision_reachable Verdict
**LATENT** — same condition.

### 2.10 Exact Evidence Commands/Queries Used
- Static source inspection of `feature_pipeline.py:214`
- Corpus scan of `data/*_M15.csv` for zero-volume majority

### 2.11 Corpus/Artifact Evidence Inspected
- `src/features/feature_pipeline.py`
- Repository data corpora (`data/*_M15.csv`)

### 2.12 Result
**LATENT** — path exists but never activated on repository corpora.

### 2.13 Dependency/Blocker for UNKNOWN
N/A — resolved LATENT.

### 2.14 Finding IDs Affected
- None directly (latent path, no finding filed)

### 2.15 Remediation Consequence (without performing remediation)
- No remediation required for current corpora
- If future zero-volume corpora are added, the proxy-volume path activates and should be
  documented or gated

---

## 3. Canonical/Pipeline Features → rr_model and zone_registry Artifact Reachability

### 3.1 Claim/Follow-up ID
Gate-5 static lineage (canonical/pipeline features).

### 3.2 Affected Census/Adjudication Records
All CANONICAL_EQUIVALENT and MATH_EQUIVALENT_VARIANT records in the adjudication matrix
that feed into model training artifacts.

### 3.3 Producer File:line
- `src/features/feature_pipeline.py` (canonical pipeline features)
- `src/features/derived_math.py` (scalar registry implementations)

### 3.4 Full Static Lineage Chain
```
feature_pipeline.py (canonical features)
  → rr_model.json (49k rows, 38-dim, F-044)
  → zone_registry.json (38-dim, 8 zones, F-041)
```

### 3.5 Consumer File:line or Explicit No-Consumer Evidence
- **rr_model consumer:** `src/config_layer/rr/rr_fusion.py` (NanoInferenceEngine, F-044)
- **zone_registry consumer:** `src/engines/zone_gate_engine.py:230` (BitNetZoneGate, F-041)
- Both models embed pipeline-canonical features

### 3.6 training_reachable Verdict
**YES** — both models were trained on pipeline-canonical features.

### 3.7 artifact_reachable Verdict
**YES** — `models/rr_model.json` and `models/zone_registry.json` are durable artifacts.

### 3.8 score_reachable Verdict
**YES** — both models are loaded and scored at runtime (rr_fusion disabled per F-038, but the
model artifact exists; zone_registry is live per F-041).

### 3.9 decision_reachable Verdict
- **rr_model:** NO (rr_fusion disabled per F-038, F-044)
- **zone_registry:** YES (live hard gate per F-041)

### 3.10 Exact Evidence Commands/Queries Used
- Static source inspection of model loading paths
- F-044 evidence: `results/rr_confidence_probe/report.json`
- F-041 evidence: `scripts/research/zone_label_audit.py`

### 3.11 Corpus/Artifact Evidence Inspected
- `models/rr_model.json`
- `models/zone_registry.json`
- `src/config_layer/rr/rr_fusion.py`
- `src/engines/zone_gate_engine.py`

### 3.12 Result
**YES** — canonical/pipeline features reach both model artifacts.

### 3.13 Dependency/Blocker for UNKNOWN
N/A — resolved YES.

### 3.14 Finding IDs Affected
- **F-044** (rr_model confidence gate mis-specification)
- **F-041** (zone_registry manifest divergence, label contamination)
- **F-038** (rr_fusion disabled)

### 3.15 Remediation Consequence (without performing remediation)
- No remediation required for reachability (already documented)
- rr_fusion stays disabled per F-038/F-044

---

## 4. Live-Hook Geometry → Logs-Only / No Training Artifact Path

### 4.1 Claim/Follow-up ID
G5-1 (from F-049 Gate-2B followup).

### 4.2 Affected Census/Adjudication Records
Live-hook geometry derivation records (GD-001/GD-002 sites at `live_engine_hook.py:361-362`).

### 4.3 Producer File:line
`src/runtime/live_engine_hook.py:361-362` — computes non-canonical `body_ratio = body/total_wick`
and `wick_size = (high-low)-body_size`.

### 4.4 Full Static Lineage Chain
```
live_engine_hook.py:361-362 (non-canonical geometry)
  → auxiliary dict (diagnostic logging only)
    → runtime logs (no persistent artifact)
      → NO training dataset path
      → NO model artifact path
```

### 4.5 Consumer File:line or Explicit No-Consumer Evidence
- **No consumer:** the auxiliary dict is logged but never read by any training pipeline
- **No consumer:** backtests bypass live_engine_hook entirely (F-037)
- **No consumer:** the values are diagnostic-only

### 4.6 training_reachable Verdict
**NO** — live-hook values never enter any training pipeline.

### 4.7 artifact_reachable Verdict
**NO** — runtime logs are not durable training artifacts.

### 4.8 score_reachable Verdict
**NO** — the live-hook geometry does not enter any scoring engine.

### 4.9 decision_reachable Verdict
**YES (in code)** — the live-hook path (`pipeline_mode.py:160` → `LiveEngineHook` →
`EngineRunner.run()`) is decision-reachable in code, but the values are diagnostic-only
(auxiliary dict, not the primary feature path). The canonical pipeline features are used
for scoring.

### 4.10 Exact Evidence Commands/Queries Used
- Static source inspection of `live_engine_hook.py:361-362`
- Static source inspection of `pipeline_mode.py:160`
- Static source inspection of `EngineRunner.run()` feature consumption
- F-037 evidence (backtest gate-off, live-hook not in backtest spine)

### 4.11 Corpus/Artifact Evidence Inspected
- `src/runtime/live_engine_hook.py`
- `src/agent/modes/pipeline_mode.py`
- `src/core/engine_runner.py`

### 4.12 Result
**NO** — no training/artifact path. Diagnostic-only logging.

### 4.13 Dependency/Blocker for UNKNOWN
N/A — resolved NO.

### 4.14 Finding IDs Affected
- **GD-001/GD-002** (non-canonical geometry, decision-reachable in code but diagnostic-only)
- **F-047** (market ontology enforcement, grandfathered divergence)
- **F-048** (RR contract mismatch — live-hook path structurally cannot execute)

### 4.15 Remediation Consequence (without performing remediation)
- Rename/register the non-canonical variant under its own FM-id (research-only `wick_based`
  variant per `market_ontology.yaml`)
- No behavior change (diagnostic-only values)

---

## 5. Pipeline Auxiliary Wick Columns → No Readers

### 5.1 Claim/Follow-up ID
G5-3 (from F-049 Gate-2B followup).

### 5.2 Affected Census/Adjudication Records
Pipeline auxiliary column records (`feature_pipeline.py:186-187` — `upper_wick`/`lower_wick`).

### 5.3 Producer File:line
`src/features/feature_pipeline.py:186-187` — computes `upper_wick` and `lower_wick` columns.

### 5.4 Full Static Lineage Chain
```
feature_pipeline.py:186-187 (upper_wick, lower_wick columns)
  → DataFrame columns (produced but never consumed)
    → NO downstream reader found
```

### 5.5 Consumer File:line or Explicit No-Consumer Evidence
**No consumer** — grep confirms zero downstream readers of `upper_wick` or `lower_wick` columns
in `src/`, `scripts/`, or `tests/`.

### 5.6 training_reachable Verdict
**NO** — no consumer means no training path.

### 5.7 artifact_reachable Verdict
**NO** — columns are produced in-memory, never persisted to training artifacts.

### 5.8 score_reachable Verdict
**NO** — no scoring engine reads these columns.

### 5.9 decision_reachable Verdict
**NO** — no decision path reads these columns.

### 5.10 Exact Evidence Commands/Queries Used
- `grep -r "upper_wick" src/ scripts/ tests/` — zero matches outside producer
- `grep -r "lower_wick" src/ scripts/ tests/` — zero matches outside producer

### 5.11 Corpus/Artifact Evidence Inspected
- `src/features/feature_pipeline.py`
- Repository-wide grep for column name consumers

### 5.12 Result
**NO** — no readers, no training/artifact/score/decision path.

### 5.13 Dependency/Blocker for UNKNOWN
N/A — resolved NO.

### 5.14 Finding IDs Affected
- None (dead columns, no finding filed)

### 5.15 Remediation Consequence (without performing remediation)
- Optional: remove dead columns from pipeline output (hygiene, no behavior change)

---

## 6. Three GateIntelligence Decision-Reachability UNKNOWNs (F-048 Dependency)

### 6.1 Claim/Follow-up ID
C4 (from F-049 Gate-2G contradiction pass).

### 6.2 Affected Census/Adjudication Records
Three records at `gate_intelligence.py:223/256/257`:

| Exact Record ID | File:line | Family | Symbol |
|:---------------|-----------|--------|--------|
| `GEO-D-373ac0d94d` | `src/core/gate_intelligence.py:223` | FAM-09-SOFTCONF-SCORES | score |
| `GEO-D-505dd25eec` | `src/core/gate_intelligence.py:256` | FAM-06-RANGE-ATR-MULTIPLE | r |
| `GEO-D-4cc99bf89d` | `src/core/gate_intelligence.py:257` | FAM-06-RANGE-ATR-MULTIPLE | score |

### 6.3 Producer File:line
`src/core/gate_intelligence.py:223, 256, 257` — geometry derivations used by
GateIntelligence scoring.

### 6.4 Full Static Lineage Chain
```
gate_intelligence.py:223/256/257 (geometry derivations)
  → GateIntelligence.evaluate() at gate_intelligence.py:...
    → execution_planner.py:246 (Step 5 gate)
      → execution_planner.py:208 (Step 2 reject_engine — PRECEDES Step 5)
        → F-048: run() structurally never executes (RR polarity < 1.5 threshold)
          → GateIntelligence gate NEVER evaluated in practice
```

### 6.5 Consumer File:line or Explicit No-Consumer Evidence
- **In-code consumer:** `execution_planner.py:246` (Step 5 GateIntelligence gate)
- **Practical blocker:** `execution_planner.py:208` (Step 2 `reject_engine`) precedes Step 5,
  and F-048 makes `run()=="execute"` structurally unreachable → the gate is never evaluated
  in practice

### 6.6 training_reachable Verdict
**NO** — GateIntelligence is a runtime gate, not a training consumer.

### 6.7 artifact_reachable Verdict
**NO** — GateIntelligence produces no durable training artifacts.

### 6.8 score_reachable Verdict
**YES (in code)** — the derivations are computed and could affect GateIntelligence scores,
but the gate is never reached in practice.

### 6.9 decision_reachable Verdict
**UNKNOWN** — the in-code chain exists (YES), but practical decision reachability is contingent
on F-048 remediation. The gate is structurally never evaluated under current conditions.

### 6.10 Exact Evidence Commands/Queries Used
- Static source inspection of `gate_intelligence.py:223/256/257`
- Static source inspection of `execution_planner.py:208-246` (Step 2 precedes Step 5)
- F-048 evidence: `engine_runner.py:957-960` (RR polarity < 1.5 → always reject)
- F-048 evidence: `decision_engine.py:144` (low_rr gate)

### 6.11 Corpus/Artifact Evidence Inspected
- `src/core/gate_intelligence.py`
- `src/runtime/execution_planner.py`
- `src/core/engine_runner.py`
- `src/core/decision_engine.py`

### 6.12 Result
**UNKNOWN** — contingent on F-048 remediation.

### 6.13 Dependency/Blocker for UNKNOWN
**F-048** — the RR contract mismatch must be remediated (Option B: remove the redundant
DecisionEngine rr gate, or Option D: document dormant-live) before these three records can
be resolved to YES or NO.

### 6.14 Finding IDs Affected
- **F-048** (primary blocker — RR contract mismatch)
- **F-047** (market ontology enforcement — these are grandfathered divergences)

### 6.15 Remediation Consequence (without performing remediation)
- These three records resolve to YES (decision-reachable) only after F-048 Option B
  (remove redundant rr gate) is implemented
- If F-048 Option D (document dormant-live) is chosen, these records resolve to NO
  (gate never evaluated)

---

## Summary Reconciliation Table

| Metric | Before Gate 5 | After Gate 5 | Delta |
|--------|:------------:|:-----------:|:-----:|
| **Total UNKNOWNs** | **71** | **3** | **−68** |
| training_reachable UNKNOWNs | 9 | 0 | −9 |
| artifact_reachable UNKNOWNs | 62 | 0 | −62 |
| decision_reachable UNKNOWNs | — | 3 | — |

### Machine-Reconciliation Details

**PRE_GATE5_UNKNOWN_DENOMINATOR_NOT_REPRODUCIBLE**
- `HISTORICAL_REPORTED_PRE_COUNT = 71`
- `MECHANICALLY_REPRODUCIBLE_FINAL_UNKNOWN_COUNT = 3`
- The frozen adjudication matrix (`geometry_semantic_adjudication.jsonl`) reflects the
  post-Gate-5 state. The 71 pre-count is attested in the 2026-07-08 session log and
  the contradiction report (`geometry_contradiction_report.md:69`): *"UNKNOWNs collapsed 71→3"*.
- A post-Gate-5 mechanical count of `decision_reachable == "UNKNOWN"` produces exactly 3.

### Every Resolved UNKNOWN Maps to Durable Evidence in This Report

| Resolution | Count | Evidence Section |
|-----------|:-----:|:----------------:|
| F-050 chain CONFIRMED (YES) | ~9 training + ~62 artifact | §1 (F-050 lineage) |
| CS-3 proxy-volume LATENT | included in artifact UNKNOWNs | §2 (F2-as-volume) |
| Canonical/pipeline → rr_model/zone_registry (YES) | included in artifact UNKNOWNs | §3 (model artifacts) |
| Live-hook → logs-only (NO) | included in training UNKNOWNs | §4 (live-hook geometry) |
| Pipeline aux wick columns → no readers (NO) | included in training UNKNOWNs | §5 (aux columns) |
| GateIntelligence UNKNOWNs (3 remaining) | — | §6 (F-048 dependency) |

### Every Remaining UNKNOWN Has an Explicit Blocker

| Exact Record ID | File:line | Family | Blocker | Blocker Finding |
|:---------------|-----------|--------|---------|:---------------:|
| `GEO-D-373ac0d94d` | `src/core/gate_intelligence.py:223` | FAM-09-SOFTCONF-SCORES | F-048 RR contract mismatch | F-048 |
| `GEO-D-505dd25eec` | `src/core/gate_intelligence.py:256` | FAM-06-RANGE-ATR-MULTIPLE | F-048 RR contract mismatch | F-048 |
| `GEO-D-4cc99bf89d` | `src/core/gate_intelligence.py:257` | FAM-06-RANGE-ATR-MULTIPLE | F-048 RR contract mismatch | F-048 |

All three remaining UNKNOWNs share the same blocker: F-048 (the DecisionEngine RR gate
consumes a candle-polarity score against a reward/risk threshold, making `run()` structurally
unable to `execute`). These resolve only after F-048 remediation.

---

## Cross-Reference: Source Artifact Citations

| Evidence | Source | Lines |
|----------|--------|:-----:|
| F-050 chain CONFIRMED | `docs/governance/geometry_contradiction_report.md` | 58-65 |
| CS-3 LATENT | `docs/governance/geometry_contradiction_report.md` | 54-55 |
| Model artifacts YES | `docs/governance/geometry_contradiction_report.md` | 66-67 |
| Live-hook NO | `docs/governance/geometry_contradiction_report.md` | 68 |
| 3 UNKNOWNs remaining | `docs/governance/geometry_contradiction_report.md` | 69 |
| 71→3 UNKNOWN collapse | `assistant_project.md` (2026-07-08) | 175 |
| F-050 evidence | `docs/current-findings.md` | 677-688 |
| F-048 evidence | `docs/current-findings.md` | 665-675 |
| Adjudication records | `docs/governance/geometry_semantic_adjudication.jsonl` | 110 records |
| Family registry | `docs/governance/geometry_family_registry.json` | 23 families |

## Validator

A machine-readable validator `tests/test_gate5_lineage_report.py` checks:
1. adjudication JSONL record count (110)
2. final UNKNOWN count (exactly 3)
3. exact final UNKNOWN record IDs match
4. no report-listed UNKNOWN ID is absent from the matrix
5. all authoritative evidence paths exist
6. docs/current-findings.md F-050 cites geometry_static_lineage_report.md
7. assistant_project.md Gate 5 session entry cites geometry_static_lineage_report.md

**HASH_FRESHNESS_VALIDATION = NOT_ADDED** — adding hash-pinning at packaging time
was considered but rejected because the CI architecture does not currently maintain
a persistent HASHES file with per-artifact freshness dates and re-validation triggers.
Adding a parallel framework would risk drift from the existing CLAUDE.md §6 evidence
freshness mechanism. The SHA-256 fingerprints in this report's header serve as a
point-in-time record; a future HASH registry (`docs/governance/HASH_REGISTRY.md`)
with CI-enforced freshness dates could extend this, but creating one is beyond the
scope of this evidence-packaging pass.
---

## Addendum 2026-07-11 — governed surface updated (110 → 117)

The Census-v3 frozen denominator of 110 (108 derivation sites + 2 admitted executor_dispatch)
is superseded as a COUNT (the point-in-time analysis above stands): Phase-1 duplicate-formula
identity closure (2026-07-10: explicit `volume_range_proxy*` columns, live-hook math routed
through `candle_math`, FM-013 registered impl, probe/test-fixture sites) and the GD-004/GD-005
`disp_strength` closure (2026-07-11: `gd004_disp_rescale_probe.py` sites added; the
`crt_engine_v2` [PATCH 7] inline site routed through `derived_math.displacement_atr_ratio`
and thus retired from the derivation surface) changed the governed set. Regenerated via
`scripts/analysis/geometry_census.py` + `scripts/analysis/gate2b_adjudication.py`:
**117 governed / 117 adjudicated / 0 missing**. Floor: `tests/test_geometry_census.py`
(freshness) + `tests/test_gate2b_closure.py` + `tests/test_gate5_lineage_report.py`
(`EXPECTED_RECORD_COUNT = 117`).

**Addendum update (2026-07-11, lint hardening):** 117 → **115** — the `feature_monitor`
`__main__` demo now binds fixture noise to intermediates (transport), removing its governed
demo rows from the derivation surface. 115 governed / 115 adjudicated / 0 missing;
`EXPECTED_RECORD_COUNT = 115`.

**Addendum update (2026-07-11, IC-007 session audit):** 115 → **118** — the observational
`crt_xauusd_runtime_trace.py` probe added 3 TOOLING replica sites (body_size/candle_range/
body_ratio for its JSONL trace records); `crt_engine_v2` adjudication rows re-keyed after the
PLAN-001/Phase-2 line shifts. 118 governed / 118 adjudicated / 0 missing;
`EXPECTED_RECORD_COUNT = 118`.

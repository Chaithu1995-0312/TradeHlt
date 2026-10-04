# TradeNet Qualification Protocol

**Purpose:** Define the only path by which TradeNet may progress from **code-exists / spine-absent**
(F-005) to a production-authorized fusion neural consumer. This protocol freezes six stages:

0. **Label feasibility assessment** (lightweight; before any builder)
1. **Authoritative label generation**
2. **Retraining criteria**
3. **Offline acceptance metrics**
4. **Shadow-mode evaluation**
5. **Production promotion gates**

**Hard rules (non-optional):**

1. This document is **governance / research planning only**. It grants **no** production weight,
   **no** `neural_fn` wire into `EngineRunner`, and **no** economic authority (§6.5 Authority Ladder).
2. Opportunity-stream fields (`outcome` / `rr` / stream `mfe` as sole y) are **non-authoritative**
   labels (F-022 class). Using them as primary training or gate y is a **protocol violation**.
3. Registry `active:true` / `promote_tradenet` **≠** spine authority. Spine authority requires **GATE-P**.
4. Funding Ledger initiative **TradeNet V2 — KILLED** reopens only when this protocol’s reopen
   mapping (§10) is satisfied **and** a SESSION LOG + construction-protocol change is recorded.
5. `AUDITED ≠ CLOSED` (`tradenet_lineage_audit.md`). Completing any single gate does **not**
   transitively close lineage or authorize wire-up.

| Field | Value |
|-------|--------|
| Created | 2026-07-22 |
| Protocol id | `TN_QUAL_V1` |
| Protocol hash seed | `TN_QUAL_V1` + freeze block in §2 (full hash frozen at epoch charter) |
| Branch context | `feature/truth-registry-v2` |
| Active config (runtime truth) | `v2_multi_2026_04` (Tier 0 `ACTIVE_VERSION`) |
| Lineage parent | [`tradenet_lineage_audit.md`](tradenet_lineage_audit.md) |
| Pattern sibling | [`rr_production_readiness_checklist.md`](rr_production_readiness_checklist.md) · F-059 clean-label kill-test |
| Measurement substrate | [`MEASUREMENT_CONTRACT.md`](MEASUREMENT_CONTRACT.md) |
| Findings | F-005 · F-012 · F-022 · F-037 · F-051 · F-058 · F-059 (pattern) |
| Composite formula (frozen until new protocol) | `0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be` (`trade_net_v2.py`) |

---

## 0. Status vocabulary

| Token | Meaning |
|-------|---------|
| **OPEN** | Gate incomplete; downstream gates forbidden. |
| **READY** | Mechanical prerequisites for the gate’s work are met; work may begin. |
| **PASS** | Gate criteria cleared with versioned evidence under frozen `protocol_hash`. |
| **FAIL** | Gate criteria not met; must remediate or stop (no silent weaken). |
| **INDETERMINATE** | Evidence unusable (contamination, underpower, harness bug) — not KEEP, not RETIRE. |
| **KEEP_CANDIDATE** | Offline discrimination survives prereg; **research-only** (F-059 pattern). |
| **RETIRE** | Clean-label evidence shows no usable discrimination under prereg. |
| **ACCEPTED** | Explicit leave-as-is for a **named scope** only (who / date / scope / what it does **not** unlock). |
| **FEASIBLE_GO** | GATE-0 only: clean-label builder is practical **and** worth funding now. |
| **FEASIBLE_DEFER** | GATE-0 only: practical later, **not** worth implementing now (opportunity cost). |
| **INFEASIBLE_STOP** | GATE-0 only: honest clean labels cannot be built with available data/geometry. |

### Gate ladder (do not skip)

```text
GATE-0  Label feasibility assessment (lightweight; evidence-only)
   │
   ▼
GATE-L  Authoritative labels + clean dataset
   │
   ▼
GATE-O  Offline acceptance (train + kill-test metrics)
   │
   ▼
GATE-S  Shadow-mode evaluation (score only; zero decision weight)
   │
   ▼
GATE-P  Production promotion (spine wire + economic authority)
```

| Gate | Unlocks | Does **not** unlock |
|------|---------|---------------------|
| **GATE-0** | Funding decision for a clean-label **builder**; light prereg draft | Full dataset authority; train; KEEP/RETIRE; any spine work |
| **GATE-L** | Clean dataset generation; offline training on clean y | Wire, promote-to-spine, economic claims |
| **GATE-O** | KEEP_CANDIDATE / RETIRE / INDETERMINATE under prereg; shadow eligibility | Spine influence; live capital claims |
| **GATE-S** | Measured shadow ΔG001 / rank correlation evidence | `neural_fn` default-on; config promote of evaluate path |
| **GATE-P** | Production spine consumption of TradeNet score | Automatic multi-instrument rollout without per-instrument GATE-S PASS |

```text
TRADENET_SPINE_STATUS          = UNWIRED          # until GATE-P PASS
TRADENET_LINEAGE_STATUS        = INERT            # lineage audit
TRADENET_QUAL_PROTOCOL         = TN_QUAL_V1
TRADENET_GATE_0_STATUS         = PASS             # FEASIBLE_GO 2026-07-22 · run 20260721T220948Z
TRADENET_GATE_0_VERDICT        = FEASIBLE_GO
TRADENET_GATE_0_EVIDENCE       = docs/governance/tradenet_gate0_feasibility.LATEST.md
TRADENET_GATE_L_STATUS         = PASS             # TN_ENV_CLEAN_L2 · BNBUSDT 20260721T223243Z
TRADENET_GATE_L_PROTOCOL       = TN_ENV_CLEAN_L2  # STRETCH_3R (L1 SUPERSEDED — TP1≡TP2 collapse)
TRADENET_GATE_L_DATASET        = results/clean_labels/BNBUSDT/LATEST
TRADENET_GATE_L_PREREG         = docs/research-readiness/tn_env_clean_label_prereg.md
TRADENET_GATE_O_STATUS         = FAIL_NOISY       # 2026-07-22 nonlinear time-CV: all Bernoulli heads ~0.50 AUC
TRADENET_GATE_O_EVIDENCE       = docs/analysis/gate-o-nonlinear-BNBUSDT.LATEST.md
TRADENET_GATE_O_VERDICT        = NO_GO_OUTCOME_HEADS
TRADENET_GATE_S_STATUS         = BLOCKED_UNTIL_O  # O did not PASS
TRADENET_GATE_P_STATUS         = BLOCKED_UNTIL_S
TRADENET_RESEARCH_EPOCH_STATUS = NOT_AUTHORIZED
```

> **GATE-0 cleared 2026-07-22** (dual pilot with ENV-0).
>
> **GATE-L cleared 2026-07-22** · **L2 repair same day**: unit TP≡2R on BNB made L1
> `SURROGATE_2R` identical to y_tp1 (ρ≈0.9996). Repair:
> [`tp2_label_repair_report.md`](tp2_label_repair_report.md) · protocol
> `STRETCH_3R_BEFORE_SL` · L2 n=139,942 · y_tp2 rate 0.241 (was 0.333) · ρ(tp1,tp2)=0.79.
>
> **GATE-O (2026-07-22):** nonlinear HistGradientBoosting time-CV — TradeNet Bernoulli
> heads **NOISY** (AUC≈0.50–0.52). **NO_GO** for outcome-head training/shadow.
> Envelope continuous heads separately **GO_RESEARCH** (rank-IC 0.16–0.27) — see same
> report; does **not** unlock TradeNet GATE-S/P.

---

## 1. Contract map (never conflate)

| ID | Name | On CRT→Fusion spine today? | Owns |
|----|------|----------------------------|------|
| **A** | Fusion neural socket | **NO** — `EngineRunner` never passes `neural_fn` (always `None`) | Optional layer in `FusionEngine.evaluate()` |
| **B** | TradeNet v2 three-head | **NO** — built, not constructed by EngineRunner | `TradeNetV2` composite → intended `neural_fn` float |
| **C** | TradeNetMetaEngine | **NO** — CognitiveBus sidecar only (F-012) | `capital_quality_score` tiers — **out of band** for GATE-P spine |
| **D** | Legacy v1 binary `.pth` | **NO** | Binary p_win; bridge mode only — **not** GATE-O primary artifact |

This protocol qualifies **contract B** for eventual **contract A** consumption.  
**Contract C** (meta capital quality) requires a **separate** program if ever promoted.  
**Contract D** may be used only as a **diagnostic twin** in shadow; it cannot clear GATE-O alone.

`EXPECTED_ENGINES = {crt, gaussian, zone_gate, rr}` — TradeNet is **not** a fourth compute engine;
it is an optional neural layer on the **evaluate** path (`fusion_use_evaluate` + `neural_fn`).

---

## 2. GATE-0 — Label Feasibility Assessment (lightweight; ahead of GATE-L)

### 2.0 Purpose

Answer **with evidence**, before investing in a full clean-label builder:

> *Is an authoritative clean-label path for TradeNet **practical** (can we build honest y)
> and **worth implementing now** (ROI vs opportunity cost under F-001 / Funding Ledger)?*

GATE-0 is a **go / defer / stop** decision gate. It is **not** a dataset, not a train run, and
not a KEEP/RETIRE economic claim.

| Property | Rule |
|----------|------|
| Effort bound | **Lightweight** — pilot/probe + written report; default ≤ ~1 engineering day equivalent unless User expands |
| Code required | **None** to *define* the gate; a small **read-only probe script** is allowed and preferred for evidence |
| Full prereg (§3 freeze) | **Not** required for GATE-0; a short scope note in the feasibility report is enough |
| Authority granted on PASS | Only: “implement GATE-L builder is authorized as research tooling” when verdict = **FEASIBLE_GO** |
| Authority **not** granted | Clean-label *authority* for findings, offline KEEP, shadow, or spine wire |

### 2.1 Questions that must be answered (with evidence)

Every GATE-0 report fills the table. Empty cells → gate incomplete (not silent PASS).

| ID | Question | Evidence (minimum) | Practical if… |
|----|----------|--------------------|-----------------|
| **G0-Q1** | Can we define a **trade_decision** population (not pure detection count)? | Cite source files (e.g. opportunities / TRADE_OPENED / fusion ENTRY) + unit key fields present; count raw units for ≥1 in-scope instrument | Unit keys exist for entry, side, ts, instrument |
| **G0-Q2** | Are **entry / SL / TP1** (and TP2 if three-head stays) reconstructable without invention? | Field census: % units with finite entry, sl, tp1, tp2; document fallbacks (ATR mult → price) if any | ≥ prereg pilot floor with full geometry (default **≥80%** of sampled closed units, or explicit ACCEPT of two-head protocol) |
| **G0-Q3** | Is **OHLCV** available to run `forward_walk(intrabar_fixed)` after each unit’s entry bar? | Instrument → candle path; % units with ≥ `max_forward` future bars; no-lookahead slice feasible | Coverage ≥ **90%** of geometry-complete units on pilot instrument |
| **G0-Q4** | Can **38-dim features@decision** be attached (stored or re-emitted PIT-safely)? | % units with complete `CANONICAL_FEATURES`; or proven re-emit path + pit risk note (F-051) | Complete features on enough units to approach train floor **or** documented cheap re-emit |
| **G0-Q5** | Pilot **clean re-derive** works end-to-end on a **small N**? | Run `forward_walk` on **N∈[50, 200]** (or all if smaller) geometry-complete units; emit y_tp1 / y_survives_be (y_tp2 if geometry allows); zero exceptions or exceptions catalogued | ≥1 successful pilot matrix; crash rate explained |
| **G0-Q6** | What is the **contamination / agreement** signal vs stream labels (diagnostic only)? | On pilot: agreement rate stream `outcome`/`mfe` vs walk y; flag F-022-class divergence | Report exists (high *or* low agreement both informative — low agreement **strengthens** need for clean y, does not fail feasibility) |
| **G0-Q7** | Is **powered train n** plausible after filters? | Extrapolate from pilot pass-rate → expected closed n per instrument vs GATE-L floor (default 500) | Expected n ≥ floor **or** explicit multi-window / multi-source plan to reach floor |
| **G0-Q8** | **Engineering cost** of a full GATE-L builder? | Bullet estimate: reuse `forward_walk`, RR L3 patterns, `extract_feature_vector`; new LOC / scripts; risks | Estimate recorded; no unbounded “rewrite the stack” |
| **G0-Q9** | **Worth it now?** (ROI / opportunity cost) | Tie to F-001 (governance/throughput constraint), F-005 (unwired), Funding Ledger KILLED, competing funded work; expected value of clean y **before** any model edge claim | User-relevant: either clear research value of *measuring* TradeNet honestly, or explicit DEFER |

### 2.2 Verdict rules

```text
GATE_0_COMPLETE = all G0-Q1…G0-Q9 answered with cited evidence paths
                  ∧ report versioned under results/ or docs/governance/
                  ∧ date + owner recorded
```

| Verdict | When | Effect on ladder |
|---------|------|------------------|
| **FEASIBLE_GO** | Q1–Q5 practical; Q7 plan reaches power **or** accepted smaller research-only floor; Q8 cost bounded; Q9 = worth now (User or documented research priority) | `TRADENET_GATE_0_STATUS = PASS`; GATE-L engineering **may** start |
| **FEASIBLE_DEFER** | Practical (Q1–Q5/Q7/Q8 OK) but Q9 = not worth now | `PASS` as assessment, but `GATE-L = BLOCKED_DEFER` until User reopens; **no** builder implementation |
| **INFEASIBLE_STOP** | Any of Q1–Q5 hard-fail without remediate path; or geometry/OHLCV cannot support honest y | Stop TradeNet clean-label program; keep F-005 UNWIRED; optional RETIRE-path *research interest* only — **not** model RETIRE |
| **INDETERMINATE** | Missing data access, probe broken, or Q ambiguous | Stay OPEN; fix probe; do not start GATE-L |

```text
GATE_0_PASS_FOR_L = GATE_0_COMPLETE ∧ verdict == FEASIBLE_GO
```

**Only `FEASIBLE_GO` unblocks GATE-L implementation.**  
`FEASIBLE_DEFER` is a successful *assessment* but leaves GATE-L blocked by policy, not ignorance.

### 2.3 What GATE-0 forbids

| Forbidden | Why |
|-----------|-----|
| Shipping a production clean dataset as “done” | That is GATE-L |
| Training / registry promote on pilot labels | Pilot N is for feasibility, not OOS authority |
| KEEP_CANDIDATE / RETIRE / economic claims | Level-0 logistics, not Level-1 information |
| Using GATE-0 PASS to wire `neural_fn` | Still GATE-P |
| Skipping Q9 (“worth it”) because Q1–Q5 green | Practical ≠ worth funding under F-001 |

### 2.4 Suggested artifact

```text
results/tradenet/gate0_feasibility/<run_id>/
  report.md          # answers G0-Q1…Q9 + verdict
  pilot_summary.json # n_raw, n_geometry, n_walk_ok, agreement rates, expected_n
  (optional) probe log
```

Read-only probe may live under `scripts/analysis/` or `scripts/research/` (no spine imports that
mutate production). Prefer reusing `forward_walk` and existing opportunity loaders.

### 2.5 Relationship to experiment freeze

- GATE-0 may use **draft** instruments/exit/cost assumptions.  
- Full freeze (§3) is mandatory before GATE-L claims **authoritative** dataset status.  
- If GATE-0 assumptions diverge from the later freeze, re-run a **delta note** (not full GATE-0 redo) when the delta is small; re-run GATE-0 if population or geometry contract changes.

---

## 3. Experiment freeze (required before GATE-L work claims authority)

**Depends on:** `GATE_0_PASS_FOR_L` (verdict **FEASIBLE_GO**).  
Building the freeze doc without FEASIBLE_GO is allowed as draft paper; it grants **no** GATE-L authority.

Before any clean dataset or kill-test outcome is treated as authoritative, freeze a prereg
(`docs/research-readiness/tradenet-qualification-preregistration.md` + JSON twin) containing:

| Freeze field | Default for `TN_QUAL_V1` (must be written, not implied) |
|--------------|--------------------------------------------------------|
| Instruments | Explicit list (BNB baseline **required** if BNB is a product surface) |
| Timeframe | M15 |
| Population unit | **trade_decision** (entry event with entry/SL/TP1/TP2 geometry) — not pure detection count |
| Feature surface | 38-dim `CANONICAL_FEATURES` + `schema_hash` |
| PIT policy | Causal structure / rolling vol only (F-051 / FC1-A+D); `pit_status` token on dataset |
| Exit model | `forward_walk(..., exit_model="intrabar_fixed")` |
| Cost | 12 bps round-trip (same M4 family as F-019…F-059) unless prereg names another |
| Composite weights | `(0.4, 0.4, 0.2)` unless a **new** protocol id supersedes |
| Train/serve identity | v2 JSON envelope preferred; legacy `.pth` not GATE-O primary |
| Measure regime | gate-ON/OFF frozen (F-037/F-058) for any spine-touching shadow/ΔG001 cell |
| Split | Time-ordered OOS + purge/embargo; fold seeds fixed |
| `protocol_hash` | Hash of freeze block + protocol id |

**Epoch rule:** changing `schema_hash`, `label_def`, exit/cost, or composite weights **without** a new
freeze creates a **new** protocol candidate — old GATE-O/S evidence is non-transferable.

---

## 4. Authoritative label generation (GATE-L)

### 4.1 Non-authoritative sources (forbidden as primary y)

| Source | Why forbidden |
|--------|----------------|
| `logs/**/opportunities*.jsonl` `outcome` / `rr_achieved` as sole y | F-022 detection stream; 36.8% self-consistency historically |
| Stream `mfe` alone for `survives_be` without path re-derive | Same contamination class; F-041B flipped SL rates on re-derive |
| Binary fusion EXIT pairing without governing exit | Legacy train path; not three-head; may inherit stream defects |
| Synthetic y from model predictions | Circular |

Stream fields may be retained as **x-ref diagnostics** only (`label_rederive_report` agreement stats).

### 4.2 Authoritative label path

```text
population units (entry, side, instrument, ts, entry_px, sl, tp1, tp2, features@decision)
    → slice future bars strictly after entry (no lookahead)
    → forward_walk(intrabar_fixed) [+ optional multi-target path for TP2]
    → y_tp1, y_tp2, y_survives_be, y_R_net (diagnostic)
    → attach provenance {protocol_hash, schema_hash, pit_status, exit_model, cost_bps}
```

**Governing exit module:** `src/research/measurement/forward_walk.py`  
(`exit_model="intrabar_fixed"` = governing truth in that module’s contract).

### 4.3 Three-head label definitions (authoritative)

Let `1R = |entry − sl|` (price units). All booleans are path-derived **before or at** exit under the
governing walk — never from untrusted stream outcome enums alone.

| Head / column | Definition | Notes |
|---------------|------------|-------|
| **y_tp1** / `reaches_tp1` | 1 iff path touches **TP1** price before hard SL under governing walk (or walk exit ∈ TP1 family **and** TP1 was in geometry) | Prefer geometric touch over string enum |
| **y_tp2** / `reaches_tp2` | 1 iff path touches **TP2** before hard SL | Requires TP2 in unit geometry; if product only has single TP, prereg must declare TP2 as `N/A` and freeze a two-head composite **new protocol** |
| **y_survives_be** / `survives_be` | 1 iff `mfe_path >= 1R` (path MFE from walk, not stream) | Aligns with `Outcome.reached_1r` spirit; missing path MFE → drop unit or mark UNRESOLVED (must not silent-zero without count in provenance) |
| **y_R_net** (diagnostic, not a train head) | Net R after declared cost | For economic offline / shadow cells — not forced into BCE heads |

**Composite target (inference only; not a fourth train head):**

```text
tradenet_score = 0.4 * p_tp1 + 0.4 * p_tp2 + 0.2 * p_survives_be
```

### 4.4 Feature matrix (with labels)

| Rule | Requirement |
|------|-------------|
| Dim | 38 = `CANONICAL_FEATURE_DIM` |
| Extract | `extract_feature_vector` at **decision time** only |
| Names | Pipeline identities (FM-021 `retest_depth`, FM-020 `disp_strength`, …) |
| CRT cache FM-027/028 | **Not** TradeNet inputs (lineage audit) |
| PIT | Reject global-rank / centered-swing contaminated vectors unless prereg accepts mask + `PIT_UNCLEAN` (then GATE-P forbidden until clean) |
| Alignment | Same filter for X and Y (`filter_usable_records` class discipline) |

### 4.5 Dataset artifact contract

Minimum fields on the versioned clean dataset (JSONL or parquet + sidecar JSON):

```text
unit_id, instrument, decision_ts, side, entry, sl, tp1, tp2,
features{38}, y_tp1, y_tp2, y_survives_be, y_R_net?,
provenance: {
  protocol_id, protocol_hash, schema_hash, pit_status,
  exit_model, cost_bps, builder_entrypoint, builder_args,
  source_population_fingerprint, label_rederive_report_path
}
```

**GATE-L PASS requires all of:**

```text
GATE_L_PASS =
    GATE_0_PASS_FOR_L                    # §2 FEASIBLE_GO only
  ∧ prereg freeze recorded (§3)
  ∧ clean builder checked-in (script OK) — refuses stream-y as primary
  ∧ versioned dataset path recorded
  ∧ label_def matches §4.3
  ∧ schema_hash == prereg
  ∧ pit_status declared
  ∧ label_rederive_report exists (stream vs clean agreement; stream not primary)
  ∧ n_closed >= prereg.min_samples (default floor 500 closed units / instrument for train eligibility;
      power floors for metrics may be higher — see §6)
  ∧ MeasurementContract surfaces for population/features/labels/exits/costs/splits declared
    (economic_admissible remains false until later gates)
```

**Forbidden under GATE-L:** KEEP/RETIRE findings; shadow with production weight; `neural_fn` wire;
starting the full builder without **FEASIBLE_GO** (use GATE-0 first).

### 4.6 Relationship to current train script

`scripts/training/train_trade_net_v2.py::extract_labels` today uses stream `outcome` + stream `mfe`.
That path is **legacy / contaminated for authority** (F-022). GATE-L requires a **clean-label builder**
(new or extended script) that:

- loads population units + OHLCV,
- runs `forward_walk(intrabar_fixed)`,
- emits the dataset contract above,
- is the **only** y source `train_trade_net_v2` (or successor) accepts when `--labels clean` / protocol mode is set.

Until that builder exists and GATE-L PASSes, any retrain is **diagnostic-only** and must not update
findings as KEEP/RETIRE or clear any gate.

---

## 5. Retraining criteria

Retrain is **not** continuous and **not** justified by “model exists” or registry hygiene alone.

### 5.1 Allowed retrain triggers (any one → new candidate version)

| Code | Trigger | Evidence required |
|------|---------|-------------------|
| **TN-RT-01** | New GATE-L clean dataset (label_def or population window change) | New `protocol_hash` or dataset version; L PASS |
| **TN-RT-02** | Feature schema / formula identity change affecting the 38-dim train surface | New `schema_hash`; feature freeze pin / construction protocol |
| **TN-RT-03** | PIT remediation (e.g. causal swings) changes vectors materially | pit_status flip + parity report |
| **TN-RT-04** | GATE-O FAIL or RETIRE on incumbent candidate with a **new** prereg hypothesis | Written hypothesis id; no silent metric shopping |
| **TN-RT-05** | Shadow drift: live shadow calibration error or rank-IC collapse beyond prereg bands for N consecutive windows | Shadow report ids |
| **TN-RT-06** | Instrument expansion (e.g. first BNB model) | Per-instrument GATE-L population for that instrument |
| **TN-RT-07** | Explicit user-authorized research epoch under frozen prereg | Epoch charter |

### 5.2 Forbidden retrain justifications

| Claim | Why forbidden |
|-------|----------------|
| “CH-002 renamed CRT cache fields” | Pipeline TradeNet inputs unchanged; lineage `REBUILD_REQUIRED_NOW=NO` |
| “ETH registry has active:true” | Registry ≠ spine; no ΔG001 |
| “v2 code exists; need weights on disk” | Build ≠ authority |
| “Improve AUC on contaminated opportunity labels” | F-022; F-045/F-059 lesson |
| “BitNet / Gaussian retrain happened” | Orthogonal surfaces |
| Continuous auto-retrain from live fills | No live loop funded (F-001); not in this protocol |

### 5.3 Retrain output requirements

Every retrain candidate must produce:

1. v2 JSON envelope (`schema_version=tradenet_v2`) preferred;  
2. scaler + feature_order_hash + metrics block;  
3. registration via `register_tradenet` **without** auto-spine implications;  
4. `--shadow` / no-promote default until GATE-O PASS;  
5. lineage note: candidate id, dataset path, `protocol_hash`, git SHA.

**Auto-promote on first registry empty** (legacy trainer behavior) is **forbidden** under this protocol
for any instrument that is a production surface candidate.

---

## 6. Offline acceptance metrics (GATE-O)

Offline metrics answer: *does the model carry **information** about clean labels OOS?*  
They do **not** answer: *does wiring it improve G001?* (that is GATE-S/P).

### 6.1 Evaluation harness rules

| Rule | Requirement |
|------|-------------|
| Labels | Clean GATE-L dataset only |
| Heads | Report **per-head** and composite |
| Split | Time-ordered; default 5-fold or prereg 70/30 OOS; purge leakage |
| Controls | At least: label-shuffle null; optional score-shuffle |
| Gate bypass | N/A for TradeNet (no Mahalanobis gate); do not confuse with RR F-044 |
| Primary artifact | v2 envelope; legacy v1 only as diagnostic twin |
| Contamination | If any fold uses stream y → run void → INDETERMINATE |

### 6.2 Metric set (mandatory report columns)

| ID | Metric | Role |
|----|--------|------|
| **M-AUC-1** | ROC-AUC `p_tp1` vs `y_tp1` (OOS) | Head discrimination |
| **M-AUC-2** | ROC-AUC `p_tp2` vs `y_tp2` (OOS) | Head discrimination |
| **M-AUC-3** | ROC-AUC `p_survives_be` vs `y_survives_be` (OOS) | Head discrimination |
| **M-CORR-C** | Spearman (or Pearson, prereg-named) `tradenet_score` vs `y_R_net` | Economic association (diagnostic) |
| **M-TOP** | Mean `y_R_net` in top score decile vs random / bottom | Ranking skill |
| **M-CAL** | ECE or reliability slope per head (prereg-named) | Calibration |
| **M-BASE** | Same metrics on shuffle null | Floor |
| **M-N** | Independent OOS n per instrument | Power |

### 6.3 Acceptance thresholds (`TN_QUAL_V1` defaults)

Prereg may tighten; **may not silently loosen** without new protocol id.

| Criterion | PASS (KEEP_CANDIDATE eligible) | FAIL / RETIRE lean |
|-----------|--------------------------------|--------------------|
| Power | OOS n ≥ **500**/instrument for head AUC claims; pooled multi-instrument allowed only if prereg says so | n below floor → **INDETERMINATE** (not RETIRE) |
| Discrimination | ≥1 head with OOS AUC ≥ **0.55** **and** beats shuffle by ≥ **0.03** | All heads AUC ≤ shuffle + 0.03 |
| Composite | `M-CORR-C` > 0 **and** beats shuffle at prereg α (default 0.05, permutation or BH as prereg) | corr ≤ 0 or fails null |
| Top-decile | Top-decile mean `y_R_net` **>** random decile mean | Top ≤ random |
| Calibration | ECE ≤ prereg max (default **0.25**) or slope in prereg band | Gross miscalibration |
| Sign of mean R | Recorded honestly | **Mean R > 0 is NOT required for KEEP_CANDIDATE** (F-059 pattern: discrimination can exist with negative mean R) |

**Verdict tokens after GATE-O:**

| Verdict | Meaning | Next |
|---------|---------|------|
| **KEEP_CANDIDATE** | PASS discrimination under clean labels | May enter GATE-S |
| **RETIRE** | Powered FAIL | Stop or new hypothesis + new retrain trigger |
| **INDETERMINATE** | Underpowered / harness defect / residual contamination | Fix L/O; do not RETIRE or KEEP |

```text
GATE_O_PASS =
    GATE_L_PASS
  ∧ candidate envelope registered (not necessarily spine-promoted)
  ∧ offline report path versioned
  ∧ verdict ∈ {KEEP_CANDIDATE} under §6.3
  ∧ no stream-y primary labels
  ∧ findings update allowed only as research-authority (not production)
```

**Authority Ladder reminder:** GATE-O PASS = **information exists** (Level 1).  
It is **not** economic usefulness (Level 2), **not** production authority (Level 3).

---

## 7. Shadow-mode evaluation (GATE-S)

Shadow answers: *if the score had been available on the live-like path, would decisions / expectancy
improve — without yet letting it change decisions?*

### 7.1 Shadow invariants

| Invariant | Rule |
|-----------|------|
| Decision weight | **Exactly 0** — TradeNet must not alter entries, size, SL/TP, or vetoes |
| Socket | Score via `TradeNetV2.predict` / `make_neural_fn`; log only |
| Path parity | Same candles, config, gate-ON/OFF freeze as prereg measure regime |
| Compare | Baseline spine (neural_fn=None) vs counterfactual **logged** blend (not applied) |
| Artifacts | Append-only `logs/tradenet_shadow.jsonl` (or versioned results path) |
| Duration | Prereg min window (default ≥ 1 full OOS segment or ≥ 30 baseline trades if spine-starved, else INDETERMINATE) |

### 7.2 Shadow record schema (minimum)

```text
ts, instrument, unit_id / trade_id,
tradenet_score, p_tp1, p_tp2, p_survives_be, schema_version,
baseline_decision, baseline_fusion_score,
counterfactual_neural_blend,   # what evaluate() would have produced
y_clean_* (if resolvable later), realized_R_net (when closed),
protocol_hash, model_version, config_version
```

### 7.3 Shadow metrics

| ID | Metric | Gate use |
|----|--------|----------|
| **S-IC** | Rank IC of score vs eventual clean / realized R | Information persistence live-like |
| **S-LIFT** | Counterfactual Δexpectancy / ΔPF if top-k or threshold filter **had** applied (report-only) | Economic hypothesis |
| **S-ΔG001** | **Applied** only in a **controlled offline A/B** that replays with neural weight ∈ {0, w*} without shipping | Promotion evidence |
| **S-STAB** | Score drift / calibration vs GATE-O | Retrain trigger TN-RT-05 |
| **S-MISS** | Rate of `TRADENET_MISSING` / None | Coverage; BNB must not be missing if BNB is in scope |

### 7.4 Shadow PASS criteria

```text
GATE_S_PASS =
    GATE_O_PASS (KEEP_CANDIDATE)
  ∧ shadow window complete per prereg
  ∧ decision_weight == 0 throughout (audit: no EngineRunner neural_fn in production process)
  ∧ S-IC > 0 and beats null (prereg α) OR powered S-ΔG001 offline A/B shows non-negative lift
  ∧ S-MISS below prereg max for in-scope instruments (default 0% for instruments with registered models)
  ∧ no production config flip of fusion_use_evaluate / neural_fn
```

**Strong path to GATE-P (preferred):** offline replay A/B with `neural_weight` as in config (0.4)
vs 0.0, gate-ON frozen, same instruments — report **ΔG001** (expectancy, PF, trade count,
max DD).  

```text
S-ΔG001_PASS (default TN_QUAL_V1) =
    ΔE[R] > 0 on OOS (or prereg primary economic metric)
  ∧ does not worsen max DD beyond prereg band
  ∧ trade count change explained (veto vs filter semantics)
  ∧ byte-identical baseline arm reproduces known gate-ON corpus where applicable
```

If spine is throughput-starved (n small), shadow economic cells may be **INDETERMINATE** —
GATE-P remains blocked (do not invent power).

### 7.5 Explicit non-goals of shadow

- Enabling CognitiveBus TradeNetMetaEngine as “almost production”
- Treating registry promote as shadow PASS
- Using contaminated opportunity outcomes as shadow y

---

## 8. Production promotion gates (GATE-P)

GATE-P is the **only** gate that may authorize TradeNet to influence spine decisions.

### 8.1 What “production” means here

| Action | In GATE-P scope? |
|--------|------------------|
| Construct `TradeNetV2` / `make_neural_fn` in `EngineRunner` and pass `neural_fn` | **YES** |
| Set `fusion_use_evaluate: true` if required for neural path | **YES** (must be parity-tested) |
| Consume `neural_weight` from config | **YES** |
| `promote_tradenet` registry only | **NO** — insufficient alone |
| CognitiveBus meta tiers | **NO** — separate program |
| ConfigValidator / PromotionManager production config promote | **YES** if config changes; still needs ValidationReport APPROVE |

### 8.2 GATE-P checklist (all required)

| ID | Requirement |
|----|-------------|
| **TN-P-01** | `GATE_0_PASS_FOR_L` (via `GATE_L_PASS`) ∧ `GATE_L_PASS` ∧ `GATE_O_PASS` ∧ `GATE_S_PASS` under same `protocol_hash` |
| **TN-P-02** | Measured **ΔG001 > 0** (or prereg primary) on powered OOS A/B — Authority Ladder Level 2→3 |
| **TN-P-03** | Per-instrument models for every instrument in the promote set (no silent `TRADENET_MISSING` → None renormalize as “success”) |
| **TN-P-04** | v2 envelope train/serve identity; feature_order_hash matches live pipeline |
| **TN-P-05** | Construction protocol change class for runtime decision path; BUILD_IMPACT_MANIFEST; tests for wire + fail-open None path |
| **TN-P-06** | `active_models.yaml` TradeNet section added/updated (intent/runtime/evidence/status) |
| **TN-P-07** | Lineage audit re-run; F-005 update (VALIDATED → SUPERSEDED or narrowed) with Evidence |
| **TN-P-08** | Funding Ledger **TradeNet V2** reopen conditions met + initiative status updated |
| **TN-P-09** | ConfigValidator path green if production JSON changes; promotion_log entry if version promote |
| **TN-P-10** | Rollback plan: `neural_fn=None` + config flag restore byte-identical baseline ledger |
| **TN-P-11** | User approval for production behavior change (behavior-preservation policy) |
| **TN-P-12** | No reliance on F-022 stream labels in the promoted artifact’s training provenance |

```text
GATE_P_PASS =
    all TN-P-01 … TN-P-12
  ∧ TRADENET_SPINE_STATUS set to WIRED only after code+config deploy evidence
  ∧ economic authority claim scoped to instruments that passed GATE-S/P
```

### 8.3 Partial promote

Allowed: wire **one** instrument with others missing → `predict→None` → fusion renormalize.  
**Only if** prereg explicitly accepts partial coverage **and** missing instruments are listed as
out-of-scope. Default: **forbidden** for multi-instrument production configs.

### 8.4 Post-promote monitoring (minimum)

| Monitor | Action if breached |
|---------|-------------------|
| Shadow IC collapse (TN-RT-05) | Disable neural_fn (rollback) or retrain under §5 |
| TRADENET_MISSING spike | Page / auto-disable neural path |
| ΔG001 trailing window negative beyond band | Rollback; open new epoch |

---

## 9. Forbidden substitutions (quick list)

| Intended | Forbidden substitute |
|----------|----------------------|
| GATE-0 feasibility evidence | “Obviously we can build labels” / skip to GATE-L builder |
| Clean forward_walk y | Opportunity `outcome` / `rr` |
| Path MFE `survives_be` | Stream mfe without re-derive |
| trade_decision population | Raw detection count as n |
| GATE-O discrimination | Contaminated AUC (F-045 class) |
| ΔG001 | AUC / p-value alone |
| Spine wire | Registry `active:true` |
| Production authority | Shadow logs existing |
| TradeNet v2 composite | Legacy binary v1 alone |
| Evaluate neural path | MetaEngine capital_quality |
| gate-ON live path | gate-OFF CRT-only research spine without freeze (F-037) |

---

## 10. Artifact & ownership map

| Stage | Artifact (suggested paths) | Owner role |
|-------|----------------------------|------------|
| **GATE-0** | `results/tradenet/gate0_feasibility/<run_id>/report.md` (+ pilot_summary.json) | Research |
| Freeze | `docs/research-readiness/tradenet-qualification-preregistration.md` (+ `.json`) | Research |
| Labels | `results/tradenet/clean_labels/<dataset_id>/` + builder under `scripts/training/` or `scripts/data/` | Research |
| Train | `models/<INSTR>/tradenet_v2_*.json` + registry entry | Training |
| Offline | `results/tradenet/offline/<candidate_id>/report.json` | Research |
| Shadow | `logs/tradenet_shadow.jsonl` + `results/tradenet/shadow/<run_id>/` | Research / runtime observe |
| Promote | construction manifest + config diff + F-005 update + lineage addendum | Governance + Executor |
| Protocol | **this file** | Governance |

### Implementation backlog (not done by publishing this protocol)

These are **required engineering** to operationalize gates — listing them does **not** authorize starting without User funding:

0. **GATE-0 feasibility probe + report** (read-only; required before builder).  
1. Clean-label builder (`forward_walk` → three-head dataset) — **only after FEASIBLE_GO**.  
2. Train entrypoint flag refusing stream-y in protocol mode.  
3. Offline kill-test driver (mirror `rr_shadow_value` / F-059 harness shape).  
4. Shadow logger + offline A/B replay harness for S-ΔG001.  
5. EngineRunner `neural_fn` injection behind explicit config flag (default off).  
6. Floors: tests for label defs, None fail-open, promote checklist schema.  
7. `active_models.yaml` `tradenet:` section (hygiene; not a gate by itself).

---

## 11. Funding Ledger reopen mapping

Ledger entry **TradeNet V2 — KILLED** reopen conditions (paraphrase): Phase-0 gate clears **and**
wiring earns measured weight (weight-0 A/B lift).

| Ledger phrase | Protocol mapping |
|---------------|------------------|
| Feasibility of clean path | **GATE-0** FEASIBLE_GO (practical + worth now) |
| Phase-0 gate clears | GATE-L + GATE-O KEEP_CANDIDATE on clean labels (powered) |
| Wiring earns measured weight | GATE-S S-ΔG001_PASS (weight-0 vs weight-w* A/B) |
| Production deployment | GATE-P full checklist |

Until production-mapped conditions hold, the initiative stays **KILLED / unfunded** for production work.
**GATE-0** (and, if FEASIBLE_GO, GATE-L tooling) may be funded as **research** without reopening production.

---

## 12. Immediate current state (2026-07-22)

| Item | State |
|------|--------|
| Code v2 three-head | EXISTS (`trade_net_v2.py`) |
| GATE-0 feasibility report | **NOT RUN** |
| Clean-label builder | **ABSENT** (blocked until FEASIBLE_GO) |
| Train script labels | Stream-based → **non-authoritative** |
| Offline clean kill-test | **NOT RUN** under this protocol |
| Shadow harness | Described in historical design notes; **not** GATE-S PASS |
| EngineRunner neural_fn | **None** (F-005) |
| GATE-0…P | GATE-0 **OPEN**; L–P **BLOCKED** as in §0 |
| Allowed now | Doc hygiene; **GATE-0 probe + report**; draft prereg |
| Forbidden now | Full clean-label builder without FEASIBLE_GO; wire neural_fn; claim economic edge; promote ETH .pth to spine; “retrain because CH-002” |

```text
TN_QUAL_V1_PUBLICATION     = DOCUMENTED
TRADENET_SPINE_STATUS      = UNWIRED (F-005)
TRADENET_GATE_0_STATUS     = OPEN
TRADENET_GATE_L_STATUS     = BLOCKED_UNTIL_0
REBUILD_REQUIRED_NOW       = NO (lineage; until RT trigger)
PRODUCTION_AUTHORITY       = NONE
```

---

## 13. Key file map

| Role | Path |
|------|------|
| This protocol | `docs/governance/tradenet_qualification_protocol.md` |
| Lineage audit | `docs/governance/tradenet_lineage_audit.md` |
| v2 inference | `src/training/trade_net_v2.py` |
| v2 train (legacy labels) | `scripts/training/train_trade_net_v2.py` |
| Neural wrapper | `src/training/trainer.py` (`make_neural_fn`) |
| Fusion socket | `src/core/fusion_engine.py` (`neural_fn`, `evaluate`) |
| Non-wiring | `src/core/engine_runner.py` |
| Governing exit | `src/research/measurement/forward_walk.py` |
| Meta sidecar (OOB) | `src/engines/tradenet_meta_engine.py` |
| Registry | `src/core/model_registry.py` · `models/tradenet_registry.json` |
| Findings | `docs/current-findings.md` F-005, F-012, F-022 |
| GATE-0 report (when run) | `results/tradenet/gate0_feasibility/<run_id>/` |

---

## 14. Change control

| Change | Requires |
|--------|----------|
| Edit thresholds / label_def / composite weights | New protocol id (`TN_QUAL_V2+`) or explicit supersession section; invalidate open epoch |
| Add/adjust GATE-0 questions or pilot floors | Same protocol id if strictly additive/clarifying; if verdict semantics weaken, new id |
| Hygiene typo / cross-link | Same protocol id; no gate reset |
| Implement backlog items | Construction protocol + tests; does not auto PASS gates |
| GATE-P wire | Full §8 + User approval + behavior-change authorization |

**End of TN_QUAL_V1.**

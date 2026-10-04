# H-MSIP-001 / H-017 — Continuous Market-State Information During CRT Candidate Occupancy

> **PRE-REGISTERED before any outcome measurement.**  
> Status: **OPEN · EXPLORATORY_RESEARCH · RESEARCH_ONLY**  
> Date: 2026-07-14 · Architecture Decision **C** (frozen posture)

| Field | Value |
|-------|--------|
| Program alias | **H-MSIP-001** |
| Registry id | **H-017** |
| Title | CONTINUOUS_MARKET_STATE_INFORMATION_DURING_CRT_CANDIDATE_OCCUPANCY |
| Task class | EXPLORATORY_RESEARCH |
| Authority | RESEARCH_ONLY |
| CRT behavior change | **NO** |
| MSIP shadow authority change | **NO** |
| Threshold tuning | **NO** |
| Migration authorized | **NO** |

Machine twin: `h-msip-001-experiment-definition.json`

---

## 1. Why this experiment exists

MSIP Decision C delivered a deterministic observational MarketStateVector with provenance
(G-SHADOW-01 PASS on declared XAUUSD population). Local-math authority is resolved
(G-PARITY-01 PARTIAL). Architecture accumulation is frozen.

This experiment asks the **first falsifiable research question**: whether continuous market-state
partitions carry **incremental information about forward price distributions during CRT candidate
occupancy**, beyond matched market regime controls and beyond the CRT lifecycle state itself.

It does **not** authorize trading cutover, CRT input migration, or threshold retuning.

---

## 2. Hypothesis (H)

**H:** During periods when CRT is occupied by an active SWEEP, DISPLACEMENT, EXPANSION, RETEST,
or EXECUTION lifecycle, the shadow MarketStateVector identifies independent market-state conditions
associated with materially different forward price distributions that are **not** represented by
the active CRT candidate.

**Null (H₀):** After matching and multiple-testing control, MarketStateVector partitions observed
during active CRT candidate lifecycles do **not** produce reproducible out-of-sample differences
in forward market behavior relative to controls.

---

## 3. Population (frozen)

| Item | Value |
|------|--------|
| Corpus | Phase-1 XAUUSD M15 `data/mt5/XAUUSD_M15.csv` |
| Content pin | sha256 `4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56` |
| Time range | binding `2024-05-22T01:00:00` → `2026-05-21T23:45:00` |

**Eligible bars (all required):**

1. Complete MarketStateVector provenance (`status=COMPLETE`)
2. Valid forward-return horizon (enough future bars for max horizon)
3. Explicit CRT lifecycle observation (`crt_phase_observation.observed=true`)
4. No lookahead contamination (causal FeaturePipeline / FC1-A swings; no future features in treatment)

Warmup bars dropped by pipeline finalize are **out of population**.

---

## 4. Treatments and controls

### 4.1 Active-candidate universe (treatment super-set)

Bars where CRT observed state ∈  
`{SWEEP, DISPLACEMENT, EXPANSION, RETEST, EXECUTION}`.

(SHADOW_PENDING, RESOLUTION, EXPIRED, RANGE are **not** treatment occupancy for the primary contrast;
RANGE feeds the primary control.)

### 4.2 Primary treatment partitions (pre-registered — closed set)

Partitions use **discrete GOVERNED_OBSERVABLE / DETERMINISTIC_DERIVED_WHAT fields only**  
(no post-hoc HOW label bands; no free threshold search).

| Partition id | Field path | Levels |
|--------------|------------|--------|
| P-SWEEP | `structure_state.liquidity_sweep` | {-1, 0, +1} |
| P-STRUCT-HHLL | `structure_state.higher_high` × `structure_state.lower_low` | {(0,0),(1,0),(0,1),(1,1)} |
| P-VOL | `volatility_state.volatility_regime` | {0, 1, 2} |
| P-SESSION | `session_state.session` | {0, 1, 2} |
| P-TREND | `trend_state.trend_bias` | {-1, 0, +1} |
| P-BOS | `structure_state.break_of_structure` | {-1, 0, +1} |

**Primary analysis family (pre-registered):** test each partition **separately** on the active-candidate
universe (not a full multi-way Cartesian product — that is explicitly out of scope for H-MSIP-001
to avoid combinatorial fishing).

**Forbidden without a new pre-registration:** inventing continuous cutpoints on `body_ratio`,
`liquidity_distance`, `trend_strength`, ATR bands, or HOW `*_label` fields.

### 4.3 Primary control

Matched bars from the **same** instrument, timeframe, and matching block where:

- CRT observed state = `RANGE`
- no active candidate lifecycle

**Matching block keys (pre-registered):**

```text
session_state.session
× volatility_state.volatility_regime
× trend_state.trend_bias
```

Matching method: exact match on the triple; within block, 1:1 nearest-neighbor in calendar time
(absolute bar-index distance) with maximum distance **32 bars**; unmatched treatment bars dropped
and counted as `UNMATCHED`.

### 4.4 Secondary control (permutation)

Within the **active-candidate** universe only: shuffle MarketStateVector partition labels
**within** blocks defined by:

```text
session × volatility_regime × trend_bias
```

Recompute the primary statistic on each shuffle. Null distribution = permutation of the
partition→outcome association holding regime block structure fixed.

**Permutation count:** 2000 (seeded `rng_seed=20260714`).

---

## 5. Outcomes (pre-registered)

All outcomes measured from bar *t* using only future OHLCV (no feature leakage).

| Outcome id | Definition | Horizons (M15 bars) |
|------------|------------|---------------------|
| R_h | simple return `(close[t+h]/close[t]) - 1` | {1, 4, 8, 16, 32} |
| MFE_h | max favorable excursion vs close[t] using high path (unsigned max up) | {4, 8, 16, 32} |
| MAE_h | max adverse excursion vs close[t] using low path (unsigned max down) | {4, 8, 16, 32} |
| P_CONT_h | P(sign(R_h) equals sign of open→close on bar t) when |open-close|>0 else NaN | {4, 8, 16} |
| P_REV_h | P(sign(R_h) opposite to bar-t body sign) | {4, 8, 16} |
| TTE | time-to-threshold / time-to-event **only if** already supported by authoritative research helpers in-repo; else **NOT_IN_SCOPE for v1** | — |

**Primary outcome for success/failure decisions:** `R_h` at **h=8** (2 hours) — pre-registered.  
Other outcomes and horizons are **secondary** (reported; BH-corrected within their family).

Directional sign convention: report **two-sided** differences (no post-hoc “pick long or short”).

---

## 6. Primary statistic and testing

For each partition family P and each level ℓ:

1. Restrict to active-candidate bars with partition = ℓ and a successful match.
2. Compute mean outcome difference:
   - **Δ_match** = mean(Y | treatment, ℓ) − mean(Y | matched RANGE control)
3. Compute **Δ_perm** null from secondary control (permutation p-value for association of ℓ
   with Y inside active-candidate blocks).
4. Walk-forward: split population by calendar into **4 contiguous folds** (equal bar count of
   eligible population). Effect must keep **sign(Δ_match)** stable in ≥ 3/4 folds **and**
   hold on the held-out last fold for the primary outcome.

**Multiple testing:** Benjamini–Hochberg FDR **q = 0.10** within each partition family across levels
for the primary outcome; secondary outcomes corrected separately per family. No peaking at
secondary before primary is locked.

**Minimum support per tested state (pre-registered):**

- n_treatment(ℓ) ≥ **80** eligible bars
- n_matched_control(ℓ) ≥ **80**
- else cell = `INSUFFICIENT` (no PASS/FAIL claim)

---

## 7. Success criteria (all required for RESEARCH_SUPPORTIVE)

1. Pre-registered effect direction for at least one level ℓ on primary outcome R_8 (two-sided
   claim: |Δ_match| direction reported a priori as “any reproducible separation”, not a signed
   economic edge claim).
2. Minimum support met.
3. Walk-forward stability (3/4 folds + held-out last fold).
4. Effect survives matched RANGE control (|Δ_match| remains with FDR-significant separation).
5. Effect exceeds permutation null (p_perm ≤ 0.05 before BH; survives BH in family).
6. Effect not concentrated in one short calendar interval (no single calendar month contributes
   > 50% of |sum of signed contributions| to Δ_match).
7. Effect remains after multiple-testing correction.
8. Effect is **not** fully attributable to CRT lifecycle state alone: repeat analysis stratified
   by CRT state; residual MSV separation must remain for ≥1 partition after within-state
   conditioning (or report `CRT_STATE_ONLY` failure).

**Authority ladder:** even full success → **research information only**. No automatic fusion,
threshold, or production authority (§6.5).

---

## 8. Failure criteria (any → RESEARCH_NULL / RESEARCH_INCONCLUSIVE)

| Code | Condition |
|------|-----------|
| INSUFFICIENT | support gates fail for all levels |
| NO_OOS | fails walk-forward / held-out |
| MATCH_KILL | disappears under matched RANGE control |
| PERM_KILL | disappears under permutation control |
| REGIME_LOCAL | no reproducible recurrence across folds |
| CALENDAR_SPIKE | dominated by one calendar interval |
| CRT_STATE_ONLY | attributable only to existing CRT lifecycle state |
| POSTHOC | any analysis required post-hoc threshold selection (automatic FAIL / protocol violation) |

---

## 9. Execution requirements (observation harness — not MSIP redesign)

When the experiment is **run** (separate authorized measurement step):

1. Build COMPLETE MarketStateVector on Phase-1 corpus (`run_msip_shadow` or equivalent).
2. **Co-run CRT** for read-only `crt_phase_observation` (separate object graph; no CRT mutation).
3. Join OHLCV forward paths for outcomes.
4. Emit append-only evidence package under `results/research/h_msip_001/` with:
   - run manifest (corpus sha, config sha, commit, seeds)
   - per-cell tables
   - permutation summary
   - walk-forward folds
   - decision ledger line: `SUPPORTIVE | NULL | INCONCLUSIVE | PROTOCOL_VIOLATION`

**Not required for this pre-registration to be complete:** executing the run.  
This document freezes the protocol **before** outcomes are inspected.

---

## 10. Explicit non-goals

- CRTConfig threshold optimization  
- Concurrent candidates  
- CRT input migration / G-MIG-01  
- Production cutover  
- Treating shadow as trading authority  
- Creating ATR/EMA transform registry  
- Body/wick hygiene implementation  

---

## 11. Research Control Plane chain

```text
hypothesis_registry (H-017 / alias H-MSIP-001)
  → this experiment definition (pre-registered)
  → frozen Phase-1 XAUUSD population
  → matched + permutation controls
  → shadow MarketStateVector observations
  → evidence package
  → critique
  → decision ledger
```

---

## 12. Related infrastructure

| Asset | Path |
|-------|------|
| Shadow design | `docs/governance/msip_shadow_design_v1/` |
| Frozen posture | `docs/governance/msip_shadow_design_v1/MSIP_DECISION_C_FROZEN_POSTURE_V1.md` |
| Math authority | `docs/governance/crt_local_math_authority_resolution_v1/` |
| Shadow runner | `scripts/analysis/run_msip_shadow.py` |
| Hypothesis seed | `scripts/governance/seed_hypothesis_registry.py` |
| CRT funnel prior | `docs/governance/crt_xauusd_funnel_diagnostic-2026-07-14.md` |

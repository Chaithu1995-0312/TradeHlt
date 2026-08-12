# Phase 2+: Preregistered Experiment Candidates

**Status:** PREREG_DRAFT under **untrusted-measurement** assumption  
**Audit:** [`docs/analysis/knowledge-graph-first-principles-audit-2026-07-10.md`](docs/analysis/knowledge-graph-first-principles-audit-2026-07-10.md)  
**KG:** `knowledge_graph.json` v0.4-UNTRUSTED-MEASUREMENT

---

## Governing assumption (Certain)

Repository findings, backtests, lineage verdicts, profitability claims, nulls, and
falsifications are **not admissible as finalized economic evidence** until relevant bugs
are resolved and the measurement pipeline is revalidated.

Historical F-xxx / Program results are **untrusted observations requiring replication**,
not evidence for region closure. Do **not** kill or deprioritize experiments merely because
a prior finding claimed the region was null.

**Pipeline:**

```text
KG → literature coverage → hypothesis space → prereg experiments
  → dependency/data → MEASUREMENT-TRUST GATE → clean results
  → ONLY THEN: SUPPORTED | INSUFFICIENT | HARMFUL | ARCHITECTURALLY_CONSTRAINED
```

---

## Outcome vocabulary (governance, not empirical authority)

Outcomes must use:

`UNTESTED | INSUFFICIENT | SUPPORTED | HARMFUL | ARCHITECTURALLY_CONSTRAINED | UNTRUSTED_PENDING_REPLICATION`

- **INSUFFICIENT ≠ HARMFUL** (insufficient evidence must never be labeled harmful).
- No economic **SUPPORTED** / **HARMFUL** until **E-MT-00** passes for the pipeline that
  produced the labels, costs, and decision objects under test.
- Dual-report: **information metrics** (IC, AUC, mutual information) **and** **net economic
  metrics** (expectancy, deflated Sharpe). Information ≠ value ≠ authority.

---

## Untrusted historical priors (not binding constraints)

| Prior | Former use | Authority now |
|-------|------------|---------------|
| U-F030 (was C-F030) | Treated vol as predictable but non-consumable in spot long/short | **UNTRUSTED** — motivates clean replication (E-VOL-00, E-P2-01, E-VOL-DIR); does **not** close directional consumption a priori |
| F-xxx region “nulls” generally | Phase-3 falsified-region removal | **Invalid protocol** — replaced by Measurement-Trust + EIG ranking |

---

## Common design standards (all experiments)

- Walk-forward with **embargoed purged splits**; no overlapping-label leakage.
- **Leakage battery appendix** (mandatory): timestamp audit, feature availability at decision
  time, no future peak in event features, engine identity smoke tests where spine is used.
- Multiplicity: report **deflated Sharpe** (Bailey–López de Prado) when >1 variant; preregister
  exact variant count; for portfolio of many experiments, pre-register hierarchical / family-wise
  control or accept only sequential stage gates.
- Cost model: taker fees + funding + conservative slippage from repo execution assumptions;
  report **gross (diagnostic, non-promotable)** AND **net (success gate)**.
- Minimum sample (economic arms): prefer **≥ 100 independent (non-overlapping) trade decisions
  OOS** and ≥ 2 distinct volatility regimes in OOS; if independence cannot be achieved, state
  block-bootstrap design and power explicitly — do not treat n=100 overlapping as sufficient for
  ΔSharpe ≥ 0.15 claims.
- Success gate is defined on **NET** metrics only (except pure information-stage experiments).
- Prefer **forward-walk economic labels** under fixed exit/cost over stream-derived `outcome`
  fields of unknown integrity.

---

## Phase-3 gate (redefined)

**No experiment is funded for economic adjudication until:**

1. **E-MT-00** Measurement-Trust Gate is defined and the relevant pipeline path is in scope.
2. Experiment has a rank in the Tier 0→3 portfolio (below).
3. Dependencies (data, prior stage experiments) are satisfied.

**Removed:** “falsified-region removal” via findings export.

---

# Tier 0 — Substrate (blocking)

## E-MT-00 — Measurement-Trust Gate
**KG nodes:** MEAS-INTEGRITY → ALL_ALPHA_NODES  
**Type:** Substrate integrity (not alpha)  
**Frozen specs (write no E-MT-00 runner code that ignores these):**
- [`docs/governance/MEASUREMENT_CONTRACT.md`](docs/governance/MEASUREMENT_CONTRACT.md) — minimum executable evidence
- [`docs/governance/measurement_contract.schema.json`](docs/governance/measurement_contract.schema.json) — schema v1.0.0
- [`docs/governance/e_mt_01_adversarial_mutation_matrix.json`](docs/governance/e_mt_01_adversarial_mutation_matrix.json) — 26 FC-* × ≥1 seed each

**Hypothesis (H1):** For a declared research path, a sealed MeasurementContract instance is
schema-valid and all required clean-path probes (population, features, labels, costs, exits,
splits, metrics, pipeline identity) PASS — i.e. the path measures the **intended** objects with
no silent semantic substitution.
**H0:** At least one required probe FAILs, or the contract is incomplete.

**Design:** Load `MC-*` contract → run probe set on clean pipeline → emit `mt00_report`.  
Does **not** assert economic edge. Residual risks may be non-blocking only if they cannot flip
economic sign under stated assumptions.
**Success gates:** `trust_status.mt00 == PASS` and contract validates schema v1.0.0.
**Kill criteria:** Any blocking probe red → freeze economic adjudication; repair only.
**Authority:** Until pass **and** E-MT-01 matrix coverage COMPLETE, all Tier-1/E-P2 economic
verdicts remain inadmissible.

---

## E-MT-01 — Adversarial mutation matrix + label re-derivation
**KG nodes:** MEAS-INTEGRITY  
**Type:** Target quality + red-team coverage of historical failure classes  
**Frozen matrix:** [`docs/governance/e_mt_01_adversarial_mutation_matrix.json`](docs/governance/e_mt_01_adversarial_mutation_matrix.json)

**Hypothesis (H1):** (A) Economic labels match independent `forward_walk` under the contract’s
exits+costs at preregistered agreement; (B) for **every** `FC-*` failure class in the frozen
matrix (≥1 seed per class, including F-022/037/038/044/048/041/046/050/E-001*), activating the
seeded defect makes the mapped detector probe FAIL and the clean path PASS.
**H0:** Label disagreement beyond policy, or any FC-* class lacks a working seed/detector pair.

**Design:**  
1. Label re-derive report (PROBE-LBL-*).  
2. Activate each SEED-* in isolation on fixtures; record clean vs mutant.  
3. Coverage COMPLETE only if all **27** classes show mutant=FAIL, clean=PASS.

**Success gates:** `mt01_matrix_coverage == COMPLETE`; label `on_fail` policy honored
(BAN_FIELDS | BLOCK_EXPERIMENT | DIAGNOSTIC_ONLY).
**Kill criteria:** Missing seed for any historical class; mutant not caught; systematic label
contamination on fields used for “edge” → ban fields / block experiment.
**Note:** Historical F-xxx are **failure-mode anchors**, not economic closures.

---

# Tier 1 — Clean search foundation

## E-BASE-01 — Time-series momentum baseline
**KG nodes:** MOM-TS, FACTOR-CRYPTO-SIMPLE  
**Hypothesis (H1):** Simple TS momentum on crypto/FX majors has positive **net** expectancy under
embargoed WF + realistic costs.  
**H0:** Net ≤ 0 after costs / fails deflated-Sharpe gate.  
**Design:** Multi-asset panel; no architecture stack; preregister lookbacks and costs.  
**Success / kill:** Net E and deflated Sharpe vs 0; INSUFFICIENT if underpowered.

## E-BASE-02 — Naive inverse-vol sizing baseline
**KG nodes:** SIZE-VOLTARGET  
**Hypothesis (H1):** Harvey-style trailing inverse-vol sizing improves risk-adjusted net metrics
vs constant risk on a declared flat or simple base exposure.  
**H0:** No improvement vs unconditioned sizing.  
**Note:** Standalone baseline — not only a sub-baseline of E-P2-01.

## E-BASE-03 — Funding cashflow harvest baseline
**KG nodes:** CARRY-FUNDING-HARVEST  
**Hypothesis (H1):** Collecting funding (with declared hedge/inventory rule) is net-positive after
fees and adverse drift.  
**H0:** Funding income ≤ costs + drag.  
**Data:** `data/perp/*_FUNDING_8H.csv` (availability).  
**Note:** Distinct from funding-as-price-signal. Historical harvest nulls do **not** close this
until clean replication.

## E-BASE-04 — Intraday mean-reversion baseline
**KG nodes:** MR-INTRADAY  
**Hypothesis (H1):** Simple z-score / VWAP-fade rules have net edge under costs.  
**H0:** Net ≤ 0.

## E-BASE-05 — Seasonality / session battery
**KG nodes:** SEAS-CAL  
**Hypothesis (H1):** TOD × DOW × funding-phase cells show net edge after multiplicity control.  
**H0:** No cell survives deflated / multiplicity gate.

## E-VOL-00 — Pure vol / regime predictability (information only)
**KG nodes:** REGIME-HMM, REGIME-CPD  
**Type:** Information-stage (no payoff)

**Hypothesis (H1):** Trailing vol / regime features predict future realized vol (or regime labels)
with statistically reliable skill OOS (e.g. IC, ranked MSE, calibration).  
**H0:** No predictable component beyond naive baselines.

**Design:** No trading PnL success gate. Report skill vs naive trailing estimators.  
**Success gates:** Preregistered skill thresholds stable across ≥2 assets / folds.  
**Kill criteria:** No skill → deprioritize consumption experiments that require the forecast;
do **not** claim “vol is useless” economically without consumption tests.  
**Dependency:** Preferred after E-MT-00.

## E-P2-05 — Candle-state incremental information audit
**KG nodes:** CANDLE-STATE  

**Adversarial prior:** Aronson (2006) against many visual patterns under snooping controls;
Neely et al. (2014) supports aggregated technicals — adjudicate for this feature stack.

**Hypothesis (H1):** Discretized candle states (sweep/retest/FVG-class features) carry incremental
information after conditioning on plain vol + trend controls (ATR percentile, Hurst/trend-strength,
lagged returns).  
**H0:** Conditional mutual information ≈ 0 (redundant transforms).

**Design:** Conditional permutation importance + nested models. Defensive experiment.  
**Success gates:** Conditional ΔIC ≥ 0.01 net of controls, stable OOS.  
**Kill criteria:** ΔIC ≈ 0 → INSUFFICIENT for complexity justification; simplification ticket;
not HARMFUL without negative contribution evidence.  
**Variant E-P2-05b (optional):** Recompute on volume bars of matched average duration.

## E-P2-04 — Funding-rate natural experiments (causal layer)
**KG nodes:** GAP-04 × CARRY-CRYPTO-FUNDING  

**Hypothesis (H1):** Discrete funding settlements act as quasi-interventions: pre/post return and
flow behavior differs by funding extremity; effect survives placebo settlement times; simple
implementation net-positive after costs.  
**H0:** No systematic pre/post effect beyond placebo.

**Design:** Regression discontinuity in time around 8h settlements; placebo at random
pseudo-settlements; extremity quantiles.  
**Success gates:** Effect vs placebo (p < 0.01 after multiplicity) AND net-positive simple
implementation after costs.  
**Kill criteria:** Effect exists but net-negative → ARCHITECTURALLY_CONSTRAINED at this cost
structure; no effect → INSUFFICIENT.

---

# Tier 2 — Consumption & structure (after Tier 1 interpretable)

## E-P2-01 — Volatility consumability (revised)
**KG nodes:** REGIME-HMM → {SIZE-VOLTARGET, CARRY-CRYPTO-FUNDING, LP-AMM}; optional E-VOL-DIR  
**Type:** Architectural consumption  

**Dependency:** **E-VOL-00 must pass** (or a preregistered pure-skill substitute). Do **not**
assume historical H_atr / Program-4 validation.

**Hypothesis (H1):** A vol/regime forecast with demonstrated info-skill produces positive **net**
economic value in at least one consumption arm:  
- **Arm A:** inverse-forecast-vol sizing on a base strategy that is **either** (i) a Tier-1 baseline
  with non-negative OOS net under E-BASE, or (ii) a flat risk-exposure process if no positive base
  exists (sizing-only evaluation). Mandatory sub-baseline: **naive trailing inverse-vol**
  (Barroso & Santa-Clara 2015; Harvey et al. 2018) — success requires beating naive scaler, not
  merely unconditioned exposure.  
- **Arm B:** perp funding capture sized/timed by forecast vol regime.  
- **Arm C:** LP range-width modulation (if data permits; Milionis et al. 2022 LVR motivation).  
- **Arm D (optional, E-VOL-DIR):** directional spot/perp consumption of the same forecast —
  **re-opened**; not pre-killed by U-F030.

**H0:** Net value of conditioned arm ≤ unconditioned / naive baselines in each payoff space.

**Design:** ETHUSDT (+ BTCUSDT robustness); difference-in-Sharpe with stationary bootstrap
(block length selection stated); deflated Sharpe across arms.  
**Success gates (net):** ΔSharpe ≥ +0.15 vs relevant baseline with 90% bootstrap CI excluding 0;
max-DD not worsened > 10% relative (preregister if relaxed).  
**Kill criteria:** ΔSharpe ≤ 0 in majority of funded arms → consumption INSUFFICIENT or HARMFUL
per sign; report per-arm. Does **not** globally close vol research.

## E-CARRY-JOINT — Basis + funding cash-and-carry
**KG nodes:** CARRY-CASH-AND-CARRY  
**Hypothesis (H1):** Joint basis+funding construction is net-positive under realistic margin and fees.  
**H0:** Net ≤ 0.  
**Data:** `data/perp/*_BASIS_M15.csv` + `*_FUNDING_8H.csv`.

## E-P2-07 — Cross-exchange basis dispersion as regime instrument
**KG nodes:** ARB-SPATIAL × REGIME-CPD  

**Hypothesis (H1):** Same-asset price/funding dispersion across exchanges widens **ahead** of
vol regime transitions (lead ≥ 4 M15 bars) on ≥2 assets.  
**H0:** Coincident/lagging only; no incremental lead vs single-venue vol estimators.

**Design:** Lead-lag / cross-correlation with significance bands.  
**Consumption (separate stage if H1 supported):** input to sizing/EWS layers — preregister
separately; do not auto-claim economic authority from lead alone.

## E-XASSET-01 — Cross-asset lead-lag
**KG nodes:** XASSET-LEADLAG  
**Hypothesis (H1):** BTC (or major) leads alts with tradable lag net of costs.  
**H0:** No incremental net edge after costs and multiplicity.

## E-VOL-DIR — Directional vol/regime consumption
**KG nodes:** REGIME-HMM, REGIME-MOE  
**Note:** May be run as E-P2-01 Arm D. Exists so directional path is not deleted by contaminated
priors. Requires E-VOL-00. Same net gates as other consumption arms.

---

# Tier 3 — Contingent / data-gated

## E-P2-03 — Critical-transition early warning (stage 1)
**KG nodes:** GAP-05 → RISK-EWS  

**Hypothesis (H1):** Early-warning indicators (rolling variance ratio, lag-1 AC, flickering) over
price + funding + OI rise in K bars before liquidation-cascade events (preregistered event
definition; prefer actual liquidation data when available; |return|/OI proxy as robustness only).  
**H0:** Pre-event distributions ≈ matched controls.

**Design:** Event study (stage 1), not a trading backtest. Matched controls by regime and TOD.  
**Success gates (stage 1):** AUC ≥ 0.65 **or** utility-justified threshold preregistered for
de-risking false-alarm cost; lead ≥ 8 bars; stable across two assets.  
**Kill criteria:** AUC ≤ 0.55 (or utility fail) → INSUFFICIENT; no stage 2.  
**Stage 2:** Separate prereg for consumption (sizing/de-risking and/or directional — not
pre-banned).  
**Dependency:** Liquidation/OI PIT data; E-MT leakage battery on event labels.

## E-P2-02 — Order-flow orthogonality vs candle geometry
**KG nodes:** OF-IMBALANCE × CANDLE-STATE  

**Hypothesis (H1):** L2 imbalance / OFI features add incremental predictive information for
M1–M15 forward returns after candle-geometry features.  
**H0:** Incremental ≈ 0.

**Design:** Nested models; identical labels/splits/costs; horizon ≥ decision latency + data delay.  
**Success gates:** ΔIC ≥ 0.01 stable across ≥3 OOS folds AND positive net PnL delta; top-10
feature churn < 50%/fold.  
**Kill criteria:** ΔIC < 0.005 or sign-unstable → INSUFFICIENT; stable negative net → HARMFUL.  
**Dependency:** **L2 data acquisition** — parked until available.

## E-P2-06 — Narrative contagion factor (crypto)
**KG nodes:** GAP-02 × ALT-NLP  

**Hypothesis (H1):** Narrative infection-rate (topic mention-share growth / SIR-style R) predicts
1–5d returns/volume orthogonally to polarity.  
**H0:** No content beyond polarity baseline.

**Design:** Panel regression; strict point-in-time text snapshots; frozen topic model + sealed code.  
**Success gates:** Orthogonal IC ≥ 0.02 at 1–5d, two disjoint OOS years.  
**Kill criteria:** IC ≈ polarity baseline → INSUFFICIENT.  
**Note:** Highest data-engineering cost; low near-term rank unless data is cheap.

## E-META-01 — Meta-labeling on passing bases
**KG nodes:** METHOD-METALABEL  
**Hypothesis (H1):** Meta-model improves net metrics of any E-BASE strategy that is non-negative OOS.  
**H0:** No improvement after costs.  
**Dependency:** At least one base with non-empty opportunity set.

## E-COST-01 — Impact / slippage model calibration
**KG nodes:** EXEC-TCA-ML, LIQ-PROXY  
**Hypothesis (H1):** Calibrated cost model predicts realized implementation shortfall better than
flat bps assumption.  
**H0:** No improvement in cost prediction error.  
**Authority:** Diagnostic for all short-horizon economic claims.

---

## Ranked research portfolio (summary)

| Tier | Fund order |
|------|------------|
| 0 | E-MT-00 → E-MT-01 |
| 1 | E-BASE-01…05 · E-VOL-00 · E-P2-05 · E-P2-04 |
| 2 | E-P2-01 (revised) · E-CARRY-JOINT · E-P2-07 · E-XASSET-01 · E-VOL-DIR |
| 3 | E-P2-03 s1 · E-META-01 · E-COST-01 · E-P2-02 (if L2) · E-P2-06 (if cheap PIT) |

**Stopping conditions:** see audit §10. Global: E-MT-00 fail → freeze economic claims;
E-VOL-00 fail → deprioritize E-P2-01; all E-BASE net-null → reallocate toward structural /
execution without a priori closing complex regions.

---

## Inputs for execution (not for closure)

1. **Measurement-trust checklist** implementation plan (E-MT-00).
2. **Structural data inventory** (already partial): OHLCV, funding, basis — not L2/social/options.
3. Optional literature backfill for EVIDENCE_PENDING KG nodes — ranking input only; not
   economic truth.
4. **Do not** import F-001…F-0xx as region kills. Optional: list as **replication tickets**
   with fresh prereg only.

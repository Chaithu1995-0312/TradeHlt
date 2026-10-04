# BNBUSDT "In-Spine Null" — Module Ledger (Built · Executed · Missed)

> **Point-in-time synthesis, not a living doc.** Organizes the BNBUSDT edge search **by module**
> (the existing ledgers — [`current-findings.md`](../current-findings.md) F-001–F-017,
> [`alpha-ledger-recovery-2026-06-03.md`](alpha-ledger-recovery-2026-06-03.md) — organize it by
> finding/edge). Every number is carried from a prior doc; **no new runs**. Branch `patch`, active
> prod `v2_multi_2026_04 - deepdeektry` (pre-TP3), governing exit model `intrabar_touch`.
>
> **Why now.** Before stopping single-knob BNBUSDT sweeps and redirecting, capture honestly *what
> the in-spine search actually ruled out* vs *what it only assumed it ruled out* — so the redirect
> is chosen against a true picture. Current verdicts live in `current-findings.md`; this is the map.

---

## TL;DR

The headline "every in-spine BNBUSDT lever is null under realistic exits" is **half-true and
worth stating precisely**:

- **Six levers were tested and are genuinely null / non-binding** (§A). The strongest-looking one
  — session policy — was **in-sample overfitting**: its +20.59% was measured under *close-only*
  exits *and* in-sample; under governing `intrabar_touch` + OOS it collapses (this session →
  KEEP_INCUMBENT, F-017).
- **Three engines that run on every candle were NEVER isolated** (§B): Gaussian, Zone Gate, RR.
  "Null" is an *assumption* for these, not a measurement.
- **The "no edge" research verdicts came from a DIFFERENT pipeline** (§C) than production — not
  interchangeable.
- **Two unreconciled contradictions sit in the evidence base** (§D): the funnel's binding
  constraint *moved* between measurements, and the evidence mixes ≥2 config versions, so not all
  numbers are same-config comparable.

---

## A. Production-spine levers — TESTED → null / non-binding

| Lever (module · file:line) | BUILT | EXECUTED (evidence · headline) | MISSED / residual |
|---|---|---|---|
| **EMA directional gate** (`crt_engine_v2.py:1405,1605`) | weak-link + conf-weights config knobs; governed per-instrument override resolver (`production_config.resolve_instrument_overrides`, dormant) | `bnb_ema_gate_ab.py` A/B → **byte-identical no-op** (15 tr, PF 1.029, det×2). [`project_ema_gate_inert`] | Tested only on the 15 *realized* trades; can't move trades it never gated. Not the binding constraint. |
| **Detection tier-2 threshold** (`crt_engine_v2.py:395,1707`) | `tier_2_threshold=0.30` + `approve_with_soft_conf` | `roi-funnel-diagnosis-...05-30` — score gate **NOT binding**: 134/135 soft-confs approved | — |
| **Consensus gate** (`fusion_engine.py:158,172,733`) | gate defined (`min_consensus_signals=2`, `agreement=0.60`) | **Dormant**: `weight_strategy_consensus=0.0` (`:158`) → never reached. [`project_consensus_gate_dormant`] | Never exercised live; not a throughput lever. |
| **Shadow displacement / TTL** (`crt_engine_v2.py:374,2076`) | `SHADOW_PENDING` branch, TTL guard (495c), `shadow_age_penalty_lambda` | Phase 4b: quality does **not** improve at any λ → `shadow_advisory_only=true`. [`project_phase4b_findings`] | Advisory-only; SHADOW_LEAK=0 verified. |
| **Session filter** (`crt_engine_v2.py:375,2604,2614`) | `allowed_sessions` gate at RETEST→EXECUTION; `session_sweep.py` ladder + OOS/G1 mode | **In-sample** (`session-sweep-...06-01`, close-only): V0 15/PF1.79/+4.91% → V3 35/PF2.54/**+20.59%**. **OOS + intrabar** (`session-sweep-...06-11`, this session): V0 15/PF**1.03**/+0.12%; V3 +0.21%/mo IS → **+0.07%/mo OOS** (PF1.09); V2 flips negative → **KEEP_INCUMBENT**. [F-017] | In-sample gain was regime overfitting + close-only confound. Tiny-N (OOS 3–13 trades). |
| **Exit model** (`crt_engine_v2.py:353,2108`) | `CRTConfig.exit_model="intrabar_touch"` default; `exit_model_band.py` dual-bound | `exit-model-adoption-...06-10`: PF **0.942 → 0.459** (2.05× inflation), E −0.038 → **−0.418R**; `validate-prod` → **REJECT**. [`project_exit_model_adoption`] | *Governing* change, not a lever to "win" — it set the truth standard that nulls the others. |

**Net A:** under the governing exit model, the active BNBUSDT config is break-even-to-losing
(V0 PF 1.03), and none of the five tunable levers above converts that into a robust, OOS-surviving
edge.

## B. Production-spine modules — NEVER ISOLATED (the honest gap)

These run on **every candle** but were never A/B'd or zeroed on BNBUSDT in this program — so "null"
is an *assumption*, not a measurement. Several are already documented as built-but-orphaned.

| Module (file) | BUILT | EXECUTED on BNBUSDT? | MISSED |
|---|---|---|---|
| **Gaussian engine** (`heuristic_gaussian_engine.py`) | kernel scorer + ML variant (`GAUSSIAN_IMPL=ml`) | **No isolation.** Run logs this session show `ModelRegistry NoOpScorer active (no active gaussian registered)` → gaussian gating effectively **off**, never measured. | Is the gate even live? Unmeasured. |
| **Zone Gate engine** (`zone_gate_engine.py`) | BitNet cluster (hard) / Z-weighted (soft); fail-open on registry error | Never isolated. Note: zone rejects ARE the binding choke in the v4/35-trade state (§D), yet zone weight was never swept. | The one filter that *became* binding (06-06) was never A/B'd. |
| **RR engine** (`rr_engine.py`) | distance-based RR scorer; canonical RR label pipeline | Never isolated (prior rr=2.0 contamination fixed, but no A/B). | — |
| **Regime weights / RegimeGovernor** (`regime_governor.py`, `fusion_engine.py:165`) | per-regime fusion profiles; quota gate (`ultron_gate_enabled`) | No regime-weight sensitivity sweep. | — |
| **DynamicThreshold** (`dynamic_threshold.py`) | percentile(85) gate, clamp [0.45,0.65] | Replaces static score_threshold; never A/B'd vs static. | — |
| **Belief gate** (`engine_runner.py:815`) | temporal-conviction accumulator | **Dormant** in backtest (no `belief_registry` injected). | — |
| **UltronRiskGate** (`ultron_risk_gate.py`) | 7-check capital waterfall | **Live-only** — not in the backtest spine that produced every number here. [F-010, F-013] | All headline ROI is pre-risk-gate; live PnL unverified. |
| **TradeNet v2 / sidecars** | built models | **Unwired / sidecar-only.** [F-005, F-012, F-013] | Risk is *rebuilding*, not building. |

**Net B:** the search falsified the *directional/throughput* knobs but never touched three of the
four scoring engines or the live risk gate. The claim should read **"every *tested* in-spine lever
is null,"** not "every lever."

## C. Research-pipeline measurements — SEPARATE context

These produced the strongest "no edge" language — but via the **research forward_walk** pipeline
(fixed 1.0/2.0×ATR SL/TP, flat 12 bps cost), **not** the production CRT engine
(`bnbusdt_execution_forensics.md`). Different config, exits, and costs → **verdicts are not
interchangeable** with the production spine.

| Measurement | EXECUTED (evidence · headline) | MISSED |
|---|---|---|
| **Forensics (World A)** | `bnbusdt-forensics-...06-10`: gross E[R] **−0.002 / +0.008 ≈ 0**; net −0.439 / −0.409R; `plain_stop_loss` **~90%** of R lost. "No directional information to harvest." | Research geometry only; one SL/TP definition. |
| **Conditional edge** | `bnbusdt-conditional-edge-...06-10`: **130 tests, 0 BH survivors**, World-A holds. +0.186R March pocket dissolves (BH q=0.130). | Linear/simple conditioning only (non-linear untested, per doc §). |
| **M4 QualificationGate** | `edge-discovery-m4-...06-10`: **PROMOTE: none.** random_uniform −0.351; expansion 0.517/−0.468R; mean_reversion 0.743/−0.215R (p=0.0005 *significant but still negative* → fails gate 2). | Two behaviors only; hypothesis space not expanded. |
| **Process characterization** | `project_process_characterizer` (memory + run JSON; plan `this-is-a-brilliant-kind-sphinx.md`): H_atr 0.885 (persistent) vs H_returns 0.527 (random walk); direction conditional entropy ≈ **0.999** (coin-flip given vol band). "Vol has memory, direction doesn't." | At N≈70k, statistically-significant ≠ economically-exploitable. |
| **Spine-as-Hypothesis** | `project_spine_as_hypothesis`: v2 spine 15 tr, PF **0.805**, E −0.145R, qualify INSUFFICIENT (n<30); beats toys/control but net-negative. | v4 spine NOT loadable on `patch` (TP3 schema gap, F-016). |

## D. Coherence gaps / unreconciled contradictions (the most valuable "missed")

1. **The funnel's binding constraint MOVED — on different config states.**
   - `roi-funnel-diagnosis-...05-30` (15-trade state): RETEST→EXECUTION **11.2%** binding; **64**
     session rejects (44 OFF + 20 ASIA); "session filter = single biggest frequency lever."
   - `funnel-diagnosis-...06-06` (**35-trade** state): **DISPLACEMENT→EXPANSION 5.04%** binding;
     RETEST→EXECUTION "**no longer session**" — only 29 *zone* rejects.
   These describe **two different configs**, never reconciled into one timeline. My 06-11 sweep ran
   the restrictive 15-trade v2 (session-binding); the 06-06 funnel + gate-contribution ran a
   35-trade state.
2. **Config-version drift across the evidence base.** `gate-contribution-...06-03` explicitly ran
   on **`v4_multi_2026_06`** (35 trades); `session-sweep-...06-01` and this session ran **v2**
   (15 trades); F-016 confirms v4 is **not even loadable on `patch`**. ⇒ The +0.545R EXECUTION
   edge and +20.59% session result (v4/close-only) and the intrabar v2 nulls are **not
   same-config comparable**. Treat cross-doc number comparisons with care.
3. **Stale V0 baseline constant.** `session_sweep.py:56` still asserts 15/PF1.79/+4.91% (close-only,
   2026-05-29) → false-fails the legacy V0 gate under governing exits (true 15/PF1.03/+0.12%).
   Fix spawned as a separate task; not yet applied.
4. **Overclaim correction** (= §B): "every in-spine lever" → "every *tested* in-spine lever."

## E. Net conclusion + what it licenses

**Genuinely ruled out** (measured): the 6 tested levers (§A) + the 2 research behaviors and any
conditional pocket (§C). **Only assumed ruled out** (never measured): the Gaussian / Zone Gate / RR
scoring engines and the live UltronRiskGate (§B). **Not comparable as one number line:** the v2 vs
v4 / intrabar vs close-only evidence (§D).

This licenses **stopping single-knob *directional/session* sweeps on the v2 BNBUSDT spine** — that
seam is exhausted (corroborates F-015). It does **not** license "BNBUSDT has no edge, full stop,"
because the scoring-engine seam and the live risk/execution layer were never isolated, and the most
favorable evidence (v4, 35 trades) was never re-measured under intrabar truth.

**Rational redirects (decision deferred to user):**
- **(a) Other instruments** — per-instrument doctrine (F-009); pool executed trades cross-instrument
  (F-015 note) rather than manufacturing per-instrument N.
- **(b) Research M4** — expand hypothesis space / universe behind the QualificationGate (the gate
  held: PROMOTE none was honest, not a failure).
- **(c) Spine/exit re-examination** — isolate the never-tested engines (§B), or re-measure the v4
  35-trade state under `intrabar_touch` (needs the post-TP3 code line, F-016).

## Provenance

Sources: `docs/analysis/{roi-baseline-...05-29, roi-funnel-diagnosis-...05-30,
session-sweep-...06-01, gate-contribution-...06-03, funnel-diagnosis-...06-06,
exit-model-adoption-...06-10, bnbusdt-forensics-...06-10, bnbusdt-conditional-edge-...06-10,
edge-discovery-m4-...06-10, bnbusdt_execution_forensics, bnbusdt_process_analysis,
session-sweep-...06-11}`, `current-findings.md` F-001–F-017, memory (`project_*`), and this
session's run telemetry. Code anchors verified in `crt_engine_v2.py`, `fusion_engine.py`,
`engine_runner.py`. No `results/*` regenerated.

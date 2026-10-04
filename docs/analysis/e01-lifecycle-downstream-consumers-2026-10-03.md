# E01 lifecycle sweep: C1–C7 full corpus + downstream consumers (2026-10-03)

> Point-in-time diagnostic evidence for **F-112** (`docs/current-findings.md`), the follow-up to
> `docs/analysis/e01-lifecycle-shadow-impact-2026-10-03.md`. **Not** activation evidence, not an
> economic finding, not a revalidation of any downstream finding.

## Identity
- Corpus: `data/mt5/XAUUSD_M15.csv`, 47,275 rows, 47,197 after the pipeline's 78-bar warmup,
  sha256 `4d73f5cebe33ec91…`.
- ACTIVE `v2_htfcrt_2026_08` (`sweep_semantics = latest_unconsumed`) vs non-promoted SHADOW
  `v2_htfcrt_e01lifecycle_shadow_2026_10` (`e01_lifecycle`). params `config_hash` `7de09f62…` in both.
- Code: `semanticos_impl` @ `f2e44ae` + the uncommitted CH-e01-lifecycle-sweep-identity tree.
- Run artifacts (session scratch, not tracked):
  - Step A ACTIVE: `run_20261003_110720_…_v2_htfcrt_2026_08_7de09f62`.
  - Step A SHADOW: `run_20261003_110727_…_v2_htfcrt_e01lifecycle_shadow_2026_10_7de09f62`.
  - Step B: the script in the Appendix (`consumers_ab.py`), 516 s.

## Step A: Semantic OS C1–C7 integration checks, both arms
Command: `scripts/governance/semantic_os_integration.py --csv data/mt5/XAUUSD_M15.csv
[--version v2_htfcrt_e01lifecycle_shadow_2026_10]`. Replay gate PASS in both arms (7,113 events).

| Check / concept | ACTIVE | SHADOW |
|---|---|---|
| C1 MKT-P01 | 2,888 AGREE | identical |
| C2 MKT-E01 (engine sweep) | 1,798 AGREE / 11 UNEXPLAINED / 1,026 NOT_CHECKABLE | identical |
| C3 MKT-E04, TRS-01 | 399 / 399 AGREE | identical |
| C4 MKT-E11 / MKT-E12 / TRS-03 | 101+36 EXP / 63+2 UNEXPL / 73+123 EXP | identical |
| C5 TRS-04 / TRS-05 / TRS-06 | 3 AGREE + 3 EXP / 3 AGREE / 6 AGREE | identical |
| C6 DEX-05 | 3 AGREE | identical |
| C7 MKT-E01 (sweep slots) | 6,348 AGREE / 75 EXP / **12,424 UNEXPLAINED** | 10,066 AGREE / 45 EXP / **0 UNEXPLAINED** |
| C7 MKT-C04 (`double_sweep`) | 1,203 AGREE / 2,358 EXP / 1 UNEXPLAINED | **1,713 AGREE** |
| C7 C01 / C03 / C06 / C07 / E08 / L01 | 18,754 / 1+3 UNEXPL / 1 / 2,985 / 26,451 / 12,730 | identical |

ACTIVE C7 E01 UNEXPLAINED by mechanism (all 12,424 classified):
- 4,437: the slot fires on a level already BROKEN.
- 4,269: the slot re-fires on a level already SWEPT.
- 3,662: an older ACTIVE level was swept that the slot never tests.
- 56: UPPER-first precedence.

The single ACTIVE C04 row is bar 18 (start of corpus). It is unclassified.

**Pre-registered (written before results):**
- P-A1, C1–C4 identical between arms: **PASS**.
- P-A2, C5/C6 checkable with TRS-06 AGREE: **PASS**.
- P-A3, SHADOW 0 E01/C04 UNEXPLAINED: **PASS**.

**UNEXPLAINED in both arms (independent of this change; read, not classified here):**
- C2 at 11 bars (5397, 5858, 10754, 20451, 23685, 29810, 33149, 35220, 39842, 41298, 42344). On each
  bar both edges are GP-04 sweeps, but the engine records only UPPER.
- C4 MKT-E12 at bars 18798 and 37041. The engine says EXPIRED; the contract says ACTIVE.
- C7 MKT-C03 at bars 529, 10927 and 46840. `trend_bias` = 0 while the contract gives ±1. These are
  **not** warmup bars, which is relevant to the open C03 warmup rule.

**Check gap (reported, not fixed):** C5 TRS-06 accepts TP1 at *any* declared intent multiple. It
does not check that the multiple matches the intent the engine derived. Related: the
`RETEST_REPLAY.tp1_mult` telemetry records the base multiplier.

## Step B: downstream consumers
Two FeaturePipeline frames over the full corpus, with the active `feature_pipeline` section, differing
only in `sweep_semantics`. Asserted: the 43 slots outside the five below are identical on every bar.
The script wrote nothing to the repo's `logs/`: `repo_logs_changed = []`, and EngineRunner's
enveloped-telemetry writer was silenced.

### B0. Input shift (47,197 bars)
| Slot | Bars changed | Share | Non-zero ACTIVE → SHADOW | Transitions |
|---|---:|---:|---|---|
| `liquidity_sweep` | 6,235 | 13.2% | 7,542 → 5,033 | 1→0 2,301 · −1→0 2,022 · 0→−1 926 · 0→1 888 · 1→−1 74 · −1→1 24 |
| `sweep_detected` | 6,137 | 13.0% | 7,542 → 5,033 | 1→0 4,323 · 0→1 1,814 |
| `double_sweep` | 2,359 | 5.0% | 3,052 → 1,713 | 1→0 1,849 · 0→1 510 |
| `candles_since_sweep` | 33,687 | 71.4% | — | (counter reset points moved) |
| **`retest_depth` (FM-021)** | **8,213** | **17.4%** | 27,405 → 24,876 | — |

**`retest_depth` moves transitively.** `retest_flag` reads `liquidity_sweep != 0`
(`feature_pipeline.py` `compute_structure_liquidity`), and FM-021 is gated on `retest_flag`.
- **The Step 6 registration did not declare this.** It named only the four sweep identities FM-090..093.
- **The Step 6 parity tests did not cover it.** They checked the four sweep slots only. On the live
  path, `runtime/live_rail_feeder.py` takes `retest_depth` from a rolling-window FeaturePipeline,
  while `core/feature_store.py` carries the lifecycle only for the four sweep slots. In `e01_lifecycle`
  mode, live `retest_depth` may therefore differ from batch: **UNVERIFIED**, not tested.

### B1. Live-rail planner + GateIntelligence
Inputs and coverage:
- `ExecutionPlannerV1_2.plan` with `planner_config_from_production(active, "XAUUSD")`, run on every
  bar × {LONG, SHORT}, 94,394 calls per arm.
- The engine result is forced to `execute`, so this measures the planner's own intent + gate stage.
- Features are the canonical frame columns, as `live_path_replay.py --feature-source canonical` uses.

| | ACTIVE | SHADOW |
|---|---:|---:|
| `execute` (gate approved) | 2,077 | 1,382 |
| `reject_gate` | 92,313 | 93,006 |
| `reject_unknown_intent` | 4 | 6 |
| intent LIQ_SWEEP | 17,878 | 11,936 |
| intent REVERSAL / CONTINUATION | 34,293 / 34,293 | 37,208 / 37,208 |
| intent PULLBACK / BREAKOUT | 5,534 / 2,392 | 5,492 / 2,544 |

- **Approval flips:** 1,146 approved → rejected and 451 rejected → approved, net −695 (−33%).
  **CORRECTED 2026-10-03 (see B1-L):** these approval counts are not live-faithful. The harness added
  `volume_ma20 = volume / volume_ratio`, which the live rail never carries. Live-faithful approvals are
  209 → 198 (−5%).
- **Intent and score:** intent score changed on 19,818 calls; maximum |Δ final score| = 0.40.
- **Mechanism, read from the flip examples:** a LIQ_SWEEP intent scores 0.5·sweep + 0.5·double_sweep.
  When the lifecycle consumes a level, `double_sweep` (intent 1.0 → 0.5) or `sweep_detected`
  (LIQ_SWEEP → CONTINUATION/REVERSAL, intent → 0) drops, taking the score below the 0.55 threshold.
- **Context:**
  - The planner is reachable only on the live rail: F-073, there is no production live rail; F-103,
    the backtest never imports the planner.
  - F-109 found its gate hostile to CRT entries on XAUUSD.
  - These are per-bar hypothetical calls, not trades.

### B1-L. Live-faithful re-run + semantic census of the planner/gate (2026-10-03)
Why it was re-run:
- B1's `pfeats` (Appendix, `consumers_ab.py`) injected `volume_ma20`.
- The live rail carries exactly the 48 canonical keys (`LiveRailFeeder._ensure_features` →
  `feature_pipeline.build_features:403`, "EXACTLY those keys") and never `volume_ma20` (SEM-004 / F-065).
- Its `lowest_low_20/5` and `highest_high_20/5` have no producer anywhere in `src/`.

Instrument:
- Same corpus (`data/mt5/XAUUSD_M15.csv`, 47,275 rows → 47,197 frame rows), active config
  `v2_htfcrt_2026_08`, both `sweep_semantics` arms, every bar × {LONG, SHORT}.
- Mode `live` = canonical keys + `volume`. Mode `b1` = the same plus the B1 `volume_ma20` injection.
- Mode `b1` reproduces B1 exactly (2,077 / 1,382), which validates the instrument.
- Scratch script `gate_semantic_census.py` (session scratchpad, not tracked); OBSERVATION_ONLY.

| | A live | B live | A b1 (=B1) | B b1 (=B1) |
|---|---:|---:|---:|---:|
| `execute` (approved) | **209** | **198** | 2,077 | 1,382 |
| approved LIQ_SWEEP / BREAKOUT / PULLBACK | 93 / 116 / 0 | 81 / 117 / 0 | 1,440 / 530 / 107 | 695 / 553 / 134 |
| calls with `vol_score` ≠ 0 | 0 | 0 | 0 | 0 |
| calls with `liquidity_score` ≠ 0 | 0 | 0 | 94,390 | 94,388 |
| LIQ_SWEEP from `double_sweep` alone (no sweep on the bar) | 2,794 (0 approved) | 1,870 (0 approved) | 2,794 | 1,870 |
| LIQ_SWEEP with event: implied bias aligned / opposed | 7,542 / 7,542 | 5,033 / 5,033 | same | same |
| approved LIQ_SWEEP: aligned / opposed | 44 / **49** | 40 / **41** | 745 / 695 | 331 / 364 |

How to read it:
- **Live arithmetic, from source and confirmed by the counts.** With vol ≡ 0 (F-109
  `legacy_relative`) and liquidity ≡ 0, the score is `final = 0.35·intent + 0.25·structure`.
  Clearing 0.55 needs intent ≥ 0.857.
  - LIQ_SWEEP intent is 0, 0.5 or 1.0, so a live LIQ_SWEEP approval requires `sweep_detected` AND
    `double_sweep`.
  - So the MKT-C04 condition is **necessary** for every live sweep approval.
  - PULLBACK never clears 0.55 live.
- **Direction-blind.** A bar with a sweep event becomes LIQ_SWEEP for **both** directions, which is
  why aligned equals opposed.
  - Among gate approvals, the opposed side is the majority: 49 of 93 (active) and 41 of 81 (e01).
  - These are per-bar hypothetical calls with the direction forced both ways. In production the
    direction comes from EngineRunner, so the live mismatch rate is **UNVERIFIED**.
- **E01 impact on the live rail is small.** Approvals fall 209 → 198 (−5%), not −33%. The B1
  magnitude came from the injected volume half.

Semantic census (matrix):

| # | Consumer site | Expected input | Actual input | Closure (§6.8) |
|---|---|---|---|---|
| 1 | `_derive_intent` LIQ_SWEEP (`execution_planner.py:389`) + `_compute_entry` (`:441-447`) | MKT-E01 event on the bar with `implied_bias` == direction | Unsigned `sweep_detected` or `double_sweep`; direction never compared; signed `liquidity_sweep` unused | CONFIRMED DEFECT (MKT-E01 rule) |
| 2 | `_intent_score` LIQ_SWEEP (`gate_intelligence.py:245-246`) | ~~Same-side confirmation~~ **CORRECTED 2026-10-03 (B1-C):** an ordered opposite-side-then-current sweep (engine `double_confirmed` lineage) | C04 two-sided condition used as a +0.5 bonus | Narrowed to a §6.2 TruthConflict, open (see B1-C) |
| 3 | `double_sweep` alone triggers LIQ_SWEEP | Event on the bar | Condition over W = 5 bars; the entry wick is not a sweep wick | CONFIRMED DEFECT (event vs condition) |
| 4 | PULLBACK (`execution_planner.py:392-397`, `gate_intelligence.py:239-243`) | Retrace fraction of the displacement leg; recency of the same-side founding sweep | FM-021 = \|close−ema_fast\|/ATR (distance from the EMA, not a fraction); FM-065 counts from either side | USER AUTHORIZATION REQUIRED (retest semantics PROPOSED, OQ7) |
| 5 | `_liquidity_score` sweep-extent half (`gate_intelligence.py:298-311`) | MKT-E01 `sweep_extreme` (R1-A) | 8th independent detector on inputs with no producer → constant 0 | DOCUMENTATION GAP (SEM-004 extended) + STALE / LEGACY ARTIFACT |

Divergence rows recorded:
- Rows 1 and 5 on MKT-E01; rows 2 and 3 on MKT-C04 (`concept_contracts.yaml`).
- SEM-004 `observed_behaviour` is extended.
- No code changed. A fix is a separate, authorized live-rail behaviour change.

### B1-F. Direction/event fix: A/B (CH-planner-liq-sweep-direction, 2026-10-03)
The user authorized rows 1 and 3 only, as an atomic change:
- New strict key `execution_planner.liq_sweep_semantics`.
  - `legacy_unsigned` is the old rule. It is declared on all 13 live configs, including the active one.
  - `e01_direction_aligned`: LIQ_SWEEP iff signed `liquidity_sweep` ≠ 0 and implied bias ==
    `selected_direction`.
- Not touched: row 2 (the gate's C04 bonus), gate arithmetic, row 4 (PULLBACK / OQ7) and row 5.

Instrument:
- Same corpus and live-faithful features as B1-L, plus the signed `liquidity_sweep`, which the live
  rail carries.
- Both planner settings run on the same calls.
- Scratch `liq_direction_ab.py`; OBSERVATION_ONLY.

| | A legacy | A aligned | B legacy | B aligned |
|---|---:|---:|---:|---:|
| `execute` (approved) | 209 | **185** | 198 | **185** |
| approved LIQ_SWEEP / BREAKOUT / PULLBACK | 93 / 116 / 0 | 44 / 139 / 2 | 81 / 117 / 0 | 40 / 143 / 2 |
| LIQ_SWEEP intents | 17,878 | 7,542 | 11,936 | 5,033 |

Read-out:
- **Legacy reproduces B1-L exactly**: 209 / 93 and 198 / 81.
- **Aligned matches the contract.** The LIQ_SWEEP intent count equals B1-L's direction-aligned count
  exactly (7,542 and 5,033), and approved LIQ_SWEEP equals B1-L's aligned approvals (44 and 40).
  Every opposed-bias and double_sweep-only call left the label.
- **Where the relabelled calls went (A):** CONTINUATION 4,887, REVERSAL 2,984, PULLBACK 1,984,
  BREAKOUT 480. One call became an exact EMA tie (UNKNOWN).
- **Approval flips (A):**
  - 46 approved → rejected: BREAKOUT 30, PULLBACK 9, CONTINUATION 7.
  - 22 rejected → approved: BREAKOUT 20, PULLBACK 2. A bar that loses its LIQ_SWEEP label can
    qualify under the next intent.
- **Approval flips (B):** 38 approved → rejected, 25 rejected → approved.
- **Net effect:** approvals −11.5% (A) and −6.6% (B).
- **Scope:**
  - These are per-bar hypothetical calls with the direction forced both ways, not trades. In
    production EngineRunner supplies one direction, so the production effect is UNVERIFIED.
  - Live rail only (F-073 / F-103).
- **Not activated.** Every config keeps `legacy_unsigned`; a test pins this
  (`test_live_configs_declare_legacy_unsigned`).

### B1-C. What the gate's `double_sweep` bonus means (Step C, 2026-10-03, read-only)
**Correction (E-001).** B1-L row 2 assumed the consumer meant "same-side confirmation". That was an
ungrounded inference, now marked `CORRECTED`.

**Lineage, verified at source.**
- The bonus arrived in the initial bulk commit `5897209f` (2026-04-30) with no design note.
- The term is the engine's `SweepEvent.double_confirmed` (`crt_engine_v2.py:965-968`): the previous
  sweep was the **opposite** side, an ordered two-sided sequence that ends in the current sweep
  (`active_models.yaml:301`).
- It is structurally always False, so it has never executed (MKT-E01 divergence, DEPRECATED).
- Every reader applies it as a bonus: engine `score_sweep` +0.4 (`:2087`), risk +0.10 (`:2387`),
  `engines/scoring_engine.py` 0.7 → 1.0, `s10_trap` +0.10, and this gate +0.5.
- What the gate actually receives is FM-060/FM-092: an unordered condition whose registered
  interpretation is *"trap / whipsaw … neither side is in control"*, worded as a caution.
- No Ontology v2 concept owns the ordered meaning. MKT-E04 is the only same-side confirmation concept,
  and no consumer ever meant it. No active trained artifact gives evidence for either meaning (BitNet
  reads the engine's constant-False flag and is off).

**Measurement.**
- Population: every bar where `e01_direction_aligned` labels LIQ_SWEEP. That is one row per bar,
  because the signed slot fixes the direction: 7,542 bars (active features) and 5,033 (e01 features).
  These equal B1-F exactly.
- Outcome contract, `outcome_type: RESEARCH_PROXY`:
  - entry at the signal-bar close (**not** the live 300 s LIMIT, which M15 cannot observe);
  - SL/TP from `compute_crt_levels(atr_abs)` with the live-hook arguments (sl_atr_buffer 0.2,
    tp1_liq_sweep 1.2, tp2 2.0);
  - `multi_tp_walk` (partial 0.5, trail 0.5, 40 bars);
  - gross R primary.
  - Comparative information test only; not valid for live execution or fill claims.
- Statistics:
  - Train = first 70% of bars (through 2025-10-14 11:15), holdout = the rest.
  - Moving-block bootstrap over bar index (480-bar blocks, all rows of a bar together, 2,000
    resamples, seed 20261003).
  - Effect = mean R(flag = 1) − mean R(flag = 0).
- Script: scratch `double_sweep_meaning.py`; OBSERVATION_ONLY.

| Candidate | Live approvals A / B | A train → holdout effect (R) | B train → holdout effect (R) | Stable? |
|---|---:|---|---|---|
| X0 current C04 | 44 / 40 | +0.043 [−0.031, +0.120] → −0.101 [−0.214, +0.017] | +0.124 [+0.037, +0.216] → −0.090 [−0.254, +0.076] | no, sign flips |
| X1w ordered, within W | 44 / 36 | identical to X0 | +0.121 [+0.034, +0.211] → −0.070 [−0.241, +0.108] | no, sign flips |
| X1e engine-literal (previous event opposite, any distance) | 70 / 73 | +0.016 → −0.028 | +0.065 → −0.033 | no, sign flips |
| X2 MKT-E04 impulse on bar i+1 (**diagnostic, lookahead**) | 58 / 43 | +1.07 → +1.01 | +1.13 → +1.17 | stable but **mechanical** |
| X3 no bonus | **0 / 0** | n/a | n/a | n/a |

What this shows:
- **Under the aligned consumer, C04 already is the ordered meaning.**
  - A rolling C04 that includes a current-bar sweep can only be 1 if the opposite side was swept in
    the previous W − 1 bars.
  - Active features: X0 ≡ X1w on 1,655/1,655 bars. e01 features: 740 shared bars, and the other 38 are
    all bar-local two-sided bars.
  - So the (a)/(b) TruthConflict matters only when the sweep isn't on the bar, which the direction fix
    already removes. What stays open is the registered "caution" wording vs the bonus polarity.
- **No decision-time candidate carries stable information about this outcome.** Every one flips sign
  from train to holdout, and every all-sample CI crosses zero:
  - X0: A +0.003 [−0.060, +0.064]; B +0.061 [−0.021, +0.141].
  - X1e: A +0.004; B +0.037.
  - The one positive train CI (B, +0.12) reverses in holdout.
- **X2's +1R is not evidence.** Bar i + 1 is the first bar of the walk, so "the next bar moved away from
  the sweep" partly *is* the outcome. It is not available at decision time.
- **Removing the bonus (X3) makes LIQ_SWEEP unapprovable** on the live rail: the 0.35·0.5 + 0.25
  ceiling of 0.425 is below 0.55. So the bonus is functioning as a gate, not as information.
- Population baseline, gross R: −0.005 (A) and −0.057 (B). With SEM-015 measured cost: −0.121 and
  −0.187.

**Status.**
- Recorded as an open MKT-C04 divergence (`decide_in: step_D_double_sweep_role`).
- No meaning chosen, and no code or config changed.
- Not done: C04 change, activation, a new "same-side confirmation", moving to E04, removing the bonus,
  OQ7.
- Diagnostic, no G001.

### B1-D. GateIntelligence scoring/authority census (Step D, 2026-10-03, read-only)
Question: why does a gate that declares four factors run on two, leaving an unresolved sweep feature
as the de facto authorization?

**What the declared gate is.** `gate_intelligence.py:148-212`, active config weights
0.35 / 0.20 / 0.20 / 0.25, threshold 0.55:

| Component | Weight | Declared inputs | Status on the live rail |
|---|---:|---|---|
| intent | 0.35 | per intent (see B1-L / B1-C) | live; REVERSAL ≈ 0 (F-061 saturation), CONTINUATION 0 by design |
| vol | 0.20 | `high − low` ÷ `atr` | **0 on 100% of calls** |
| liquidity | 0.20 | ½ volume spike (`volume_ma20`) + ½ sweep extent (`lowest_low_20/5`, `highest_high_20/5`) | **0 on 100% of calls** |
| structure | 0.25 | EMA alignment + `disp_strength / 3` | live (non-zero on 99.9%); dimensionally sound (FM-020 is in ATR multiples) |

**Why vol is 0: dead from birth.**
- Canonical `atr` has been close-relative since the first commit (`atr_14_raw / close`,
  `feature_pipeline.py:384-386` @`5897209f`).
- The tent function divides a dollar range by that ratio (r ≈ 10³), so it clamps to 0.
- F-109 added `gate_vol_atr_basis` (default `legacy_relative`); `absolute` exists but has never been
  activated.

**Why liquidity is 0: two independent causes, both from birth.**
- **Volume half.** `volume_ma20` exists only as a non-canonical pipeline column. The planner's
  production input never carried it: not the first committed `live_engine_hook._build_engine_input`
  (`5897209f`), and not today's `LiveRailFeeder` → `build_features` (exactly the 48 canonical keys).
  This is F-065 H7 / SEM-004.
- **Sweep-extent half.** It is dead **twice**:
  - (i) No producer of `lowest_low_*` / `highest_high_*` exists in any commit of `src/` (git history).
  - (ii) The formula `(lowest_low_20 − lowest_low_5)/atr` (LONG) is ≤ 0 whenever both windows trail to
    the current bar, because the 5-bar window is inside the 20-bar one. Measured: with nested inputs
    supplied (S3), liquidity is still 0 on every call.
  - The docstring's "positive = sweep below the 20-bar low" needs a 20-bar window that **excludes** the
    last 5 bars, a convention nothing defines.

**Why the tests never caught it.**
- Both unit suites (`test_gate_intelligence.py`, `test_execution_planner.py`) feed fixtures with
  absolute-unit `atr` (2.0 on close 100), `volume_ma20` and `lowest_low_*` values that production never
  supplies.
- Those fixtures are nested-consistent (e.g. ll20 = 96 < ll5 = 98.5), so even they never exercise a
  positive sweep extent.
- The two dead components contribute in tests and nowhere else: the same test-encodes-the-hole pattern
  as F-108.

**Authority of the numbers.**
- The weights and threshold arrived in the initial bulk commit with no calibration record.
- The gate has never been outcome-evaluated: the backtest never imports the planner (F-103), and it
  has no G001.
- `config-reachability-report` lists all four weights as READ_AND_USED. That is true syntactically, but
  vol and liquidity multiply a constant 0: read ≠ governed (the F-056 lesson).
- `KNOWN_ILLUSIONS.md` #3 ("keys dead") is stale. CORRECTED in place.

**Measurement.** Decision space only, OBSERVATION_ONLY:
- XAUUSD M15, 47,275 rows → 47,197 frame bars × {LONG, SHORT}; active config and features.
- Each scenario adds exactly one set of the gate's own declared inputs. Scratch
  `gate_authority_census.py`.
- "Necessary" = approval drops below 0.55 if that component's contribution is removed.

| Scenario | Approvals | BREAKOUT / LIQ_SWEEP / PULLBACK | Components necessary for approvals |
|---|---:|---|---|
| S0 live (legacy_unsigned) | **209** | 116 / 93 / 0 | intent 209/209, structure 209/209 |
| S0 live (e01_direction_aligned) | 185 | 139 / 44 / 2 | intent 185, structure 185 |
| S1 + vol basis `absolute` | 4,675 | 636 / 2,027 / 2,011 | vol 4,466 |
| S2 + `volume_ma20` (= B1's injection) | 2,077 | 530 / 1,440 / 107 | liquidity 1,868 |
| S3 + extent inputs, nested windows | 209 | identical to S0 | liquidity never non-zero |
| S4 + extent inputs, disjoint windows | 501 | 169 / 305 / 27 | liquidity 292 |
| S5 all declared inputs (S1 + S2 + S4) | **13,057** | 1,841 / 7,661 / 3,511 | intent 13,033, vol 10,207, structure 9,113, liquidity 8,382 |
| S5 + e01_direction_aligned | 9,981 | 2,207 / 2,571 / 5,149 | intent 9,957, vol 7,539, structure 6,787, liquidity 4,975 |

What this shows:
- **The single-factor authority is an artifact of missing inputs, not a design choice.** Live, the gate
  is `0.35·intent + 0.25·structure ≥ 0.55`. That needs intent ≥ 0.857, which only a BREAKOUT, or a
  LIQ_SWEEP with `double_sweep`, can reach.
  - With every declared input present, approvals rise **62×** (209 → 13,057).
  - Authority then spreads across all four components, and PULLBACK becomes the largest aligned class.
- **The threshold was set against a four-factor sum that has never existed in production.** The live
  ceiling is 0.60, so 0.55 sits 0.05 below it.
- **Volume caveat.** XAUUSD `volume` is tick volume (F-099, TICK_VOLUME_APPROXIMATE), so the volume half
  would measure tick activity even if wired.
- Decision space only: none of these counts says whether the approvals would be good trades.

**Closures (§6.8).**
- vol = 0: CONFIRMED DEFECT, already F-109; the fix exists behind a key, so activation is USER
  AUTHORIZATION REQUIRED.
- Volume half: F-065 H7, USER AUTHORIZATION REQUIRED.
- Sweep-extent half: CONFIRMED DEFECT (no producer; the nested reading is zero by construction) plus
  TEST / CONTRACT GAP (window convention undefined).
- Weights and threshold: INSUFFICIENT EVIDENCE for their values; authority unearned (§6.5).
- Unit fixtures supplying production-absent inputs: TEST / CONTRACT GAP.
- `KNOWN_ILLUSIONS` #3: DOCUMENTATION GAP, corrected.
- No code or config changed. `e01_direction_aligned` is not activated, and `double_sweep` is not removed.

### B1-E. Do the dormant gate components carry outcome information? (F-113 follow-up, 2026-10-03, read-only)
Each dormant component is tested **separately**, then in combination, before any repair (user
direction).

Components and scenarios:
- **S1** `gate_vol_atr_basis = absolute`.
- **S2** `volume_ma20`, the pipeline's own column. XAUUSD volume is tick volume (F-099).
- **S3H** sweep extent with disjoint windows (the 20 bars before the last 5, vs the last 5).
  **HYPOTHESIS only**: this is the dead formula's docstring reading, not a known-correct definition.
- Combinations: S12, S13H, S23H, S123H.

Outcome contract `RESEARCH_PROXY`:
- entry at the signal-bar close;
- SL/TP from `compute_crt_levels(atr_abs)` with the live hook's per-intent `tp1_atr_multiplier_<intent>`
  (BREAKOUT 1.5 / PULLBACK 0.8 / LIQ_SWEEP 1.2 / REVERSAL 1.0), `tp2` 2.0, `sl_atr_buffer` 0.2;
- `multi_tp_walk` (partial 0.5, trail 0.5, 40 bars);
- gross R primary, SEM-015 net secondary;
- comparative information only, not valid for live execution or fill claims.

Population and statistics:
- 94,394 bar × direction calls; 60,096 are eligible (intents with declared TP multipliers).
  CONTINUATION has none, so the live hook would reject its 13 S123H approvals.
- Train = bars before 2025-10-14 11:15 (70%); holdout = the rest.
- Moving-block bootstrap over bar index (480-bar blocks; both directions of a bar move together;
  2,000 resamples).
- Eligible base rate: −0.080 R gross.
- Scratch `gate_component_outcome.py`.

**T1/T2: does adding the component improve the approved set?** Δ = mean R(approved) − mean R(S0
approved).

| Scenario | Approved (all) | Mean R approved (all) | Δ vs S0, train | Δ vs S0, holdout | Sign stable? |
|---|---:|---|---|---|---|
| S0 live | 209 | −0.130 [−0.292, +0.026] | — | — | — |
| S1 vol abs | 4,675 | −0.054 [−0.084, −0.028] | +0.116 [−0.050, +0.269] | −0.024 [−0.308, +0.236] | no |
| S2 volume | 2,077 | −0.052 [−0.104, −0.001] | +0.151 [−0.026, +0.312] | −0.106 [−0.420, +0.151] | no |
| S3H extent (hyp.) | 501 | −0.022 [−0.115, +0.078] | +0.118 [−0.031, +0.264] | +0.088 [−0.137, +0.292] | yes, but every CI crosses 0 |
| S12 | 10,963 | −0.092 [−0.115, −0.068] | +0.080 | −0.065 | no |
| S13H | 6,335 | −0.063 [−0.089, −0.038] | +0.102 | −0.017 | no |
| S23H | 2,849 | −0.059 [−0.099, −0.017] | +0.125 | −0.064 | no |
| S123H (all declared) | 13,047 | −0.096 [−0.115, −0.077] | +0.075 | −0.066 | no |

**T3: is a component informative on its own (threshold-free, eligible calls)?** Effect = mean R(high)
− mean R(low).

| Component | Train | Holdout | All |
|---|---|---|---|
| vol (S1 score, median split) | −0.024 [−0.042, −0.007] | +0.004 [−0.025, +0.034] | −0.016 |
| volume half (S2 score, median split) | −0.043 [−0.067, −0.019] | +0.005 [−0.026, +0.036] | −0.029 |
| sweep extent (S3H, > 0) | −0.020 [−0.048, +0.008] | +0.023 [−0.018, +0.067] | −0.008 |

What this shows:
- **No dormant component shows stable outcome information on this object.**
  - vol and volume score *negatively* in train (higher score → worse R; the CIs exclude 0), then
    ≈ 0 in holdout.
  - Every Δ-vs-live except S3H flips sign from train to holdout.
- **S3H is the only same-sign case,** and it is not a candidate:
  - every CI crosses 0;
  - it adds only 292 calls;
  - its window convention is a hypothesis.
  - **Status: INSUFFICIENT, not a lead.**
- **Repairing the inputs would mainly add volume at about the base rate.** The full repair approves
  13,047 calls at −0.096 R gross (−0.252 net), indistinguishable from the eligible base rate of −0.080.
  The approved set gets 62× larger without getting better.
- **The live gate itself shows no edge on this object either.** S0's 209 approvals: −0.130 R gross,
  train −0.178 → holdout −0.013. The point estimate sits below the eligible base rate. That is a
  comparison of point estimates only; no paired test was run.

**Input-surface classification (added 2026-10-04, after a dataset-lineage check).** How each scenario
relates to what the canonical research dataset actually has:

| Scenario | Data used | In the canonical 48-dim vector? | Classification |
|---|---|---|---|
| S1 | canonical `atr` (FM-041) × `close` = FM-074, selected by an existing config key | yes (FM-041 slot; FM-074 is a registered transform) | counterfactual **configuration** of canonical data |
| S2 | `volume_ma20` = SMA(volume, `volume_ma_window`) | raw `volume` **is** canonical (FM-089, slot 4; MT5 `tick_volume`, `volume_semantic: TICK_VOLUME`); `volume_ratio` **is** canonical (FM-062, slot 5); `volume_ma20` is **not** canonical | counterfactual **wiring** of a canonical feature. The gate's volume half equals `0.5·min(1, volume_ratio/2)` **exactly** (verified on 2,922 XAUUSD bars, max abs diff 0.0, no zero-volume or zero-mean rows). So S2 tested FM-062 through the gate's formula, delivered under a key no producer sends. It is not synthetic data. |
| S3H | `lowest_low_*` / `highest_high_*` with disjoint windows | no; no FM identity, no producer in any commit | counterfactual **synthetic input**: a hypothesis-defined construction the dataset does not possess |

Consequences:
- **Correct wording for the volume half.** "Volume is missing" is wrong. The canonical dataset carries
  MT5 tick volume (FM-089) and its ratio (FM-062). What is missing is the **wiring**: the gate reads the
  non-canonical `volume_ma20`, which no producer delivers, instead of FM-062, which is in the same dict.
- **No record of a deliberate exclusion.** The only recorded decision is to *defer* the wiring fix
  (SEM-004 `validation_rules`, F-065).
- **FM-089's semantics are not certified.** `TICK_VOLUME_APPROXIMATE` (F-099/F-100); OHLCV closure
  still lists BC-4 as a blocker (`CORPUS_AUTHORITY.md`). Any S2 conclusion is conditional on reading
  tick volume as participation.

**Instrument note (disclosed).**
- S0 / S1 / S2 / S3H approval counts equal the B1-D census exactly (209 / 4,675 / 2,077 / 501).
- S123H totals 13,060 here (13,047 eligible + 13 CONTINUATION) vs 13,057 in B1-D. The difference is a
  warm-up edge in both scratch instruments.
  - On the first ~25 bars `highest_high_20` is absent while `highest_high_5` exists. The gate defaults
    the missing key to 0.0, so the SHORT extent saturates.
  - The two scripts use different `min_periods`.
  - 6 approvals fall in that window, all in train, which is negligible for these statistics.

**Status.**
- Diagnostic; no G001; no economic claim.
- No component earns repair authority (§6.5).
- No code or config changed.

### B2. EngineRunner fusion gate (the backtest's post-commit veto)
Setup:
- `EngineRunner.run` with the active `engine_runner` section, on every bar × {LONG, SHORT}.
- The input is built like `backtest_v2`'s `_feat_map_er`, with two declared deviations: `atr` =
  canonical atr × close (FM-074), not `engine.state.atr_abs`; and no orchestrator consensus score or
  belief registry.
- The backtest veto rule is applied, including `backtest.bypass_zone_invalid = true`.

Results:
- Decision flips 0, reason flips 0, veto flips 0 (36,794 vetoes in each arm), selected-engine flips 0.
- Score differs on 48 of 94,394 calls, max |Δ| 0.045.
- **Non-informative by construction.** Every call is rejected at either:
  - the adapter: `invalid_session` 0.0 = 24,714 and 4.0 = 12,016; or
  - the DecisionEngine's first check, `feature_cluster_similarity_invalid` (57,600), which the
    backtest bypasses. Because this rejection fires first (`decision_engine.py:158`), the
    score-threshold and p_win checks are never reached. A small score change therefore cannot reach
    a decision on this path.
  - Plus 64 `ultron_gate:regime_range_no_direction`.
  - P-B3 is scored PASS, but it shows the gate cannot see the change, not that the change is harmless.

### B3. Trained artifacts not reachable on the active config
Verified in `configs/production/v2_htfcrt_2026_08.json` and source:
- `rr_fusion.enabled = false`.
- `use_bitnet = false`.
- TradeNet is unwired (F-005).
- ZoneGate scores every in-session bar `valid = False` (B2 above), so its sweep dimensions decide
  nothing on this path.
- `crt_gaussian_scorer` reads `candles_since_sweep` only as a fallback after `retest_index`. Its effect
  on the 3 trades is already covered: the backtest A/B showed identical `S_score`.
- `engines/live_engine.py:1036` reads `candles_since_sweep` on the legacy live path (F-073, no
  production rail).
- Each would see the B0 input shift if wired. No scoring was done.

**Pre-registered:**
- P-B1, material `sweep_detected` shift: **PASS** (13.0%).
- P-B2, LIQ_SWEEP counts change: **PASS** (−33%).
- P-B3, small fusion deltas with few or no flips: **PASS, non-informative** (see B2).

## Findings to name for revalidation if activated (named, not revalidated)
These findings cite these slots in their text. Whether each one's *evidence values* would move is
UNVERIFIED per finding:
- **Directly consume slot values:**
  - F-106: engine SWEEP vs `sweep_detected` overlap 927/1792.
  - F-107: `candles_since_sweep` 47,183/47,183.
  - F-108 and F-109: planner intent counts and LIQ_SWEEP. B1 shows these move.
  - F-054: certification of FM-021 and the sweep slots. FM-090..093 are uncertified.
- **Mention `retest_depth` / FM-021 / FM-065 / liq_sweep in a naming or other context; check each:**
  F-023, F-038, F-047, F-050, F-063, F-064, F-072.
- **Whole-vector consumers that do not name the slots; check each:** F-086, F-097, F-036, F-041,
  F-045, F-059.

## Status
Diagnostic evidence only. The producer fix:
- leaves C1–C6 identical and clears every E01/C04 UNEXPLAINED row;
- reaches the CRT TP1-intent path (prior doc);
- materially changes the live-rail planner's intent labels (LIQ_SWEEP 17,878 → 11,936). Its effect on
  live-faithful gate approvals is small, 209 → 198. CORRECTED 2026-10-03 from "materially changes …
  gate decisions": the −33% was an artifact of the `volume_ma20` injection, see B1-L;
- is invisible to the backtest fusion gate, because that gate never reaches its score checks.

Two Step 6 gaps are now recorded: the undeclared transitive `retest_depth` change, and an untested
live parity for `retest_depth`. No activation, system-wide-risk or economic conclusion.

## Addendum (same day): FM-021 gap closed (CH-e01-lifecycle-retest-identity)
- **Declared.** FM-094 `retest_flag_e01` (structural_states) and FM-095 `retest_depth_e01`
  (derived_metrics) are now registered in `configs/formulas/market_ontology.yaml`.
  - Both are `active: false`, with `config_key feature_pipeline.sweep_semantics`.
  - They use the same formulas and impl as FM-061 / FM-021, fed by FM-090.
  - The ontology closure of the four sweep slots is exactly FM-061 + FM-021. That matches B0's
    assertion that the other 43 vector slots are identical.
- **Live parity measured, not just argued.**
  - The "rolling-window" description above was wrong: `runtime/live_rail_feeder.py` keeps every
    pushed bar and re-runs the full pipeline each bar.
  - `tests/test_e01_sweep_semantics.py::test_live_feeder_matches_batch_at_every_prefix` shows
    `retest_depth` and the four sweep slots equal batch at all 90 ready prefixes, in both modes.
  - `test_retest_flag_follows_the_selected_sweep_identity` pins FM-094's formula to the code.
- **No emitted value changed.** The only `src/` edit is a comment; the XAUUSD vector regression passes.

## Appendix: `consumers_ab.py` (scratch instrument, reproduced verbatim)
```python
"""E01 lifecycle downstream-consumer A/B (OBSERVATION_ONLY; no src/ or config edit).

Two FeaturePipeline frames over the same corpus, identical except feature_pipeline.sweep_semantics
(ARM A = latest_unconsumed, the ACTIVE value; ARM B = e01_lifecycle). For every bar x {LONG, SHORT}:
  B0  input shift on the four sweep slots (and an assertion that the other 44 slots are identical)
  B1  ExecutionPlannerV1_2.plan (intent classifier + GateIntelligence), active planner config
  B2  EngineRunner.run (the fusion gate the backtest runs at TRADE_OPENED), active engine_runner config,
      input dict built the way backtest_v2 builds _feat_map_er
Usage: consumers_ab.py <out_json> [--limit N] [--skip-engine]
"""
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(r"D:\Tradelatest")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import core.engine_runner as _er_mod  # noqa: E402
from config_layer.execution_planner import ExecutionPlannerV1_2, planner_config_from_production  # noqa: E402
from config_layer.production_config import PROD_VERSION, get_full_config_dict, get_prod_section  # noqa: E402
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402

# EngineRunner appends curated telemetry to the SHARED repo logs/; silence it (observation must not
# write into other sessions' streams). Any other write is caught by the logs/ snapshot check below.
_er_mod._emit_enveloped_jsonl = lambda *a, **k: None

SWEEP = ("liquidity_sweep", "sweep_detected", "double_sweep", "candles_since_sweep",
         # FM-021, moves TRANSITIVELY: retest_flag reads liquidity_sweep != 0 (feature_pipeline.py
         # compute_structure_liquidity). Found by this script's own assert on the first trial.
         "retest_depth")
CSV = ROOT / "data" / "mt5" / "XAUUSD_M15.csv"
out_path = Path(sys.argv[1])
limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
skip_engine = "--skip-engine" in sys.argv


def logs_snapshot():
    d = ROOT / "logs"
    return {p.name: p.stat().st_size for p in d.rglob("*") if p.is_file()} if d.exists() else {}


logs_before = logs_snapshot()
t0 = time.time()
raw = pd.read_csv(CSV)
print(f"[ab] PROD_VERSION={PROD_VERSION} csv={CSV} rows={len(raw)}", flush=True)
fp = dict(get_prod_section("feature_pipeline"))
assert fp["sweep_semantics"] == "latest_unconsumed", fp["sweep_semantics"]
frames = {}
for arm, sem in (("A", "latest_unconsumed"), ("B", "e01_lifecycle")):
    cache = out_path.parent / f"ab_frame_{arm}.pkl"   # scratch cache, keyed by arm (same corpus+config)
    if cache.exists():
        df, vec = pd.read_pickle(cache)
    else:
        df, vec = FeaturePipeline(raw, cfg={**fp, "sweep_semantics": sem}).run()
        pd.to_pickle((df, vec), cache)
    frames[arm] = (df.reset_index(drop=True), np.asarray(vec, dtype=float))
    print(f"[ab] arm {arm} ({sem}) frame rows={len(df)} vec={frames[arm][1].shape} t={time.time()-t0:.0f}s", flush=True)

dfA, vA = frames["A"]
dfB, vB = frames["B"]
assert len(dfA) == len(dfB) and vA.shape == vB.shape
assert (dfA["timestamp"].astype(str).values == dfB["timestamp"].astype(str).values).all()
sweep_idx = [CANONICAL_FEATURES.index(k) for k in SWEEP]
other = [i for i in range(vA.shape[1]) if i not in sweep_idx]
same_other = np.array_equal(np.nan_to_num(vA[:, other], nan=-9e9), np.nan_to_num(vB[:, other], nan=-9e9))
diff_cols = [CANONICAL_FEATURES[i] for i in other
             if not np.array_equal(np.nan_to_num(vA[:, i], nan=-9e9), np.nan_to_num(vB[:, i], nan=-9e9))]
assert same_other, f"non-sweep slots differ: {diff_cols}"

n = len(dfA) if limit is None else min(limit, len(dfA))
res = {"prod_version": PROD_VERSION, "csv": str(CSV), "csv_rows": len(raw), "frame_rows": len(dfA),
       "bars_evaluated": n, "non_sweep_slots_identical": bool(same_other), "B0": {}}

# ── B0 input shift ─────────────────────────────────────────────────────────────────────────
for k, i in zip(SWEEP, sweep_idx):
    a, b = vA[:n, i], vB[:n, i]
    ch = a != b
    trans = Counter((float(x), float(y)) for x, y in zip(a[ch], b[ch])) if k != "candles_since_sweep" else None
    res["B0"][k] = {"changed": int(ch.sum()), "share": round(float(ch.mean()), 6),
                    "nonzero_A": int((a != 0).sum()), "nonzero_B": int((b != 0).sum())}
    if trans is not None:
        res["B0"][k]["transitions"] = {f"{x:g}->{y:g}": c for (x, y), c in sorted(trans.items())}
print("[ab] B0", json.dumps(res["B0"]), flush=True)

# ── B1 planner + gate ──────────────────────────────────────────────────────────────────────
full = get_full_config_dict()
pcfg = planner_config_from_production(full, "XAUUSD")
planner = ExecutionPlannerV1_2(pcfg)
PKEYS = ("close", "high", "low", "atr", "body_ratio", "disp_strength", "sweep_detected", "double_sweep",
         "retest_depth", "candles_since_sweep", "ema_fast", "ema_slow", "momentum_score")
OPT = ("volume", "swing_high", "swing_low", "higher_high", "lower_low")
missing_cols = [k for k in PKEYS if k not in dfA.columns]
res["B1_missing_frame_columns"] = missing_cols


def pfeats(df, r):
    row = df.iloc[r]
    f = {k: float(row[k]) for k in PKEYS}
    f["sweep_detected"] = bool(f["sweep_detected"])
    f["double_sweep"] = bool(f["double_sweep"])
    f["candles_since_sweep"] = int(f["candles_since_sweep"])
    for k in OPT:
        if k in df.columns:
            f[k] = float(row[k])
    if "volume_ratio" in df.columns and float(row["volume_ratio"]) > 0:
        f["volume_ma20"] = float(row["volume"]) / float(row["volume_ratio"])
    return f


def plan(f, d):
    out = planner.plan({"decision": "execute", "selected_direction": d, "confidence": 0.0, "regime": "na"},
                       f, {"symbol": "XAUUSD", "signal": "BUY" if d == 1 else "SELL", "score": 0.0})
    g = out.get("gate") or {}
    return (out.get("decision"), out.get("trade_intent") or (out.get("trace") or {}).get("intent"),
            g.get("approved"), (g.get("components") or {}).get("intent_score"),
            (g.get("components") or {}).get("liquidity_score"), g.get("final_score"))


b1 = {"decisions_A": Counter(), "decisions_B": Counter(), "intent_A": Counter(), "intent_B": Counter(),
      "intent_flips": Counter(), "decision_flips": Counter(), "approved_flips": Counter(),
      "intent_score_delta_nonzero": 0, "final_score_delta_nonzero": 0, "max_abs_final_delta": 0.0}
flip_examples = []
if not missing_cols:
    for r in range(n):
        fa, fb = pfeats(dfA, r), pfeats(dfB, r)
        for d in (1, -1):
            pa, pb = plan(fa, d), plan(fb, d)
            b1["decisions_A"][pa[0]] += 1; b1["decisions_B"][pb[0]] += 1
            b1["intent_A"][str(pa[1])] += 1; b1["intent_B"][str(pb[1])] += 1
            if pa[1] != pb[1]:
                b1["intent_flips"][f"{pa[1]}->{pb[1]}"] += 1
            if pa[0] != pb[0]:
                b1["decision_flips"][f"{pa[0]}->{pb[0]}"] += 1
                if len(flip_examples) < 25:
                    flip_examples.append({"ts": str(dfA["timestamp"].iloc[r]), "dir": d, "A": pa, "B": pb})
            if pa[2] != pb[2]:
                b1["approved_flips"][f"{pa[2]}->{pb[2]}"] += 1
            if (pa[3] or 0) != (pb[3] or 0):
                b1["intent_score_delta_nonzero"] += 1
            if (pa[5] or 0) != (pb[5] or 0):
                b1["final_score_delta_nonzero"] += 1
                b1["max_abs_final_delta"] = max(b1["max_abs_final_delta"], abs((pa[5] or 0) - (pb[5] or 0)))
res["B1"] = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in b1.items()}
res["B1"]["decision_flip_examples"] = flip_examples
print(f"[ab] B1 done t={time.time()-t0:.0f}s", json.dumps({k: res['B1'][k] for k in ('decisions_A', 'decisions_B', 'intent_flips', 'decision_flips', 'approved_flips')}), flush=True)

# ── B2 EngineRunner (fusion gate) ──────────────────────────────────────────────────────────
if not skip_engine:
    from core.engine_runner import EngineRunner
    er_cfg = dict(get_prod_section("engine_runner"))
    er_cfg.setdefault("fusion_engine", dict(get_prod_section("fusion_engine")))
    for k, v in dict(get_prod_section("decision_engine")).items():
        er_cfg.setdefault(k, v)
    er_cfg["instrument"] = "XAUUSD"
    runners = {"A": EngineRunner(dict(er_cfg)), "B": EngineRunner(dict(er_cfg))}

    def er_input(df, vec, r, d):
        row = df.iloc[r]
        m = {name: vec[r][i] for i, name in enumerate(CANONICAL_FEATURES)}
        for k in ("close", "high", "low", "open", "volume"):
            m.setdefault(k, float(row[k]))
        # backtest passes engine.state.atr_abs (price units); per bar outside the engine the closest
        # declared quantity is FM-074 atr_absolute = atr * close (declared deviation).
        m.setdefault("atr", float(vec[r][CANONICAL_FEATURES.index("atr")]) * float(row["close"]))
        m.setdefault("timestamp", str(row["timestamp"]))
        m["_data_integrity"] = "real"
        m["direction"] = m["signal_dir"] = m["trade_direction"] = d
        return m

    # Backtest veto rule (backtest_v2 ~:4098): a REJECT/HOLD vetoes unless the reason is
    # feature_cluster_similarity_invalid and backtest.bypass_zone_invalid is true.
    bypass_zone = bool(get_prod_section("backtest")["bypass_zone_invalid"])

    def veto(res_):
        dec = str(res_.get("decision") or res_.get("status", "")).upper()
        if dec not in ("REJECT", "REJECTED", "HOLD"):
            return False
        return not (bypass_zone and "feature_cluster_similarity_invalid" in str(res_.get("reason")))

    b2 = {"decision_A": Counter(), "decision_B": Counter(), "decision_flips": Counter(),
          "reason_A": Counter(), "reason_flips": Counter(), "veto_A": 0, "veto_B": 0, "veto_flips": Counter(),
          "score_delta_nonzero": 0, "max_abs_score_delta": 0.0, "selected_engine_flips": Counter(),
          "bypass_zone_invalid": bypass_zone}
    ex2 = []
    for r in range(n):
        for d in (1, -1):
            ctx = {"instrument": "XAUUSD", "timeframe": "M15", "strategy_consensus_direction": d}
            ra = runners["A"].run(er_input(dfA, vA, r, d), context=dict(ctx)) or {}
            rb = runners["B"].run(er_input(dfB, vB, r, d), context=dict(ctx)) or {}
            da = str(ra.get("decision") or ra.get("status", "")); db = str(rb.get("decision") or rb.get("status", ""))
            b2["decision_A"][da] += 1; b2["decision_B"][db] += 1
            b2["reason_A"][f"{ra.get('reject_stage')}:{str(ra.get('reason'))[:60]}"] += 1
            va, vb = veto(ra), veto(rb)
            b2["veto_A"] += va; b2["veto_B"] += vb
            if va != vb:
                b2["veto_flips"][f"{va}->{vb}"] += 1
            if da != db or str(ra.get("reason")) != str(rb.get("reason")) or va != vb:
                if da != db:
                    b2["decision_flips"][f"{da}->{db}"] += 1
                else:
                    b2["reason_flips"][f"{ra.get('reject_stage')}:{ra.get('reason')} -> {rb.get('reject_stage')}:{rb.get('reason')}"[:160]] += 1
                if len(ex2) < 25:
                    ex2.append({"ts": str(dfA["timestamp"].iloc[r]), "dir": d,
                                "A": [da, ra.get("reject_stage"), ra.get("reason"), ra.get("score")],
                                "B": [db, rb.get("reject_stage"), rb.get("reason"), rb.get("score")]})
            sa, sb = ra.get("score"), rb.get("score")
            if sa != sb:
                b2["score_delta_nonzero"] += 1
                try:
                    b2["max_abs_score_delta"] = max(b2["max_abs_score_delta"], abs(float(sa) - float(sb)))
                except (TypeError, ValueError):
                    pass
            if ra.get("selected_engine") != rb.get("selected_engine"):
                b2["selected_engine_flips"][f"{ra.get('selected_engine')}->{rb.get('selected_engine')}"] += 1
        if r and r % 5000 == 0:
            print(f"[ab] B2 bar {r}/{n} t={time.time()-t0:.0f}s", flush=True)
    res["B2"] = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in b2.items()}
    res["B2"]["decision_flip_examples"] = ex2
    res["B2"]["sample_result_keys"] = sorted(ra.keys())
    res["B2"]["atr_basis_deviation"] = "atr = canonical atr * close (FM-074), not engine.state.atr_abs"
    res["B2"]["context_deviation"] = "no StrategyOrchestrator consensus score, no belief_registry"
    print(f"[ab] B2 done t={time.time()-t0:.0f}s", json.dumps({k: res['B2'][k] for k in ('decision_A', 'decision_flips', 'reason_flips', 'veto_A', 'veto_B', 'veto_flips', 'score_delta_nonzero', 'selected_engine_flips')}), flush=True)

logs_after = logs_snapshot()
res["repo_logs_changed"] = sorted(k for k in set(logs_before) | set(logs_after) if logs_before.get(k) != logs_after.get(k))
res["elapsed_s"] = round(time.time() - t0, 1)
out_path.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
print(f"[ab] wrote {out_path} repo_logs_changed={res['repo_logs_changed']} elapsed={res['elapsed_s']}s", flush=True)
```

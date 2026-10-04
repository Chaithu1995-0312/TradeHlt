# Feature-Math Grandfather Divergence Adjudication — Matrix v1 (source evidence)

> **Point-in-time forensic (2026-07-07).** NOT a living doc (§6.2 rule 5). Adjudicates the 10
> grandfather pins (GD-001…GD-010) that F-047's ownership-lint census established. **Read-only: no
> source site was modified.** `Matrix v1 = source evidence` (semantic class, formula equivalence,
> execution- and decision-reachability with cited call-chains). `observed_*` columns are all
> `not_measured` here — they are populated only in **Matrix v2** (Gate 2), and only for the sites this
> matrix proves warrant a differential probe.
>
> Durable ledger: `scripts/analysis/feature_math_lint.py` (GD records + `durable_key`). Retirement:
> `docs/governance/feature-math-grandfather-retirements.json` (append-only). Ratchet + integrity:
> `tests/test_feature_math_lint.py`.

## Why this phase exists

F-047 shipped the enforcement architecture but **grandfathered 10 pre-existing live-surface
divergences** — a *baseline ratchet*, not proof of full canonicalization. Two defects motivated this
adjudication: the pins were fragile (`file::name`, no fingerprint) and reachability had been *assumed*.
Two independent reachability traces **contradicted each other** on the load-bearing site.

## The contradiction, and how it was resolved (source-authoritative)

- **Trace 1:** live `body_ratio` → `EngineRunner` → CRT scoring → fusion → decision (reachable).
- **Trace 2:** the CRT-scoring path (`crt_engine.compute` → `scoring_engine.compute_scores`) is
  *orphaned* — `EngineRunner` imports `crt_compute` but never calls it.

**Resolution (reading method boundaries, not trusting a trace):**
- `engine_runner.py:654` `crt_result = crt_compute(trade_id="Test:", features=input_data, context={})`
  sits inside **`def run(...)` (engine_runner.py:570)** — the live scoring method (its own comment,
  :657-659, states `run()` is called by `backtest_v2.py:1639-1641` and references "the live path").
  → **Trace 1 is correct; Trace 2 is wrong.** The `trade_id="Test:"` is a cosmetic hardcoded label, not
  a harness marker. `crt_compute` → `crt_engine.py:22` reads `features["body_ratio"]` →
  `compute_scores` `s_breakout` (`scoring_engine.py:40`) → `crt_result` → `fusion.compute` (:787) →
  APPROVE/REJECT.
- **New finding on `move`:** `crt_engine.py:23` passes `move=float(features["disp_strength"])`. So the
  scoring-local `disp_strength = move/atr` (GD-004) is `features["disp_strength"] / atr` — a **re-scaled
  distinct quantity**, not a wrong body_ratio and not the FM-020 feature. → rename, not a formula fix.
- **Live-hook exposure is CONDITIONAL:** `live_engine_hook` (which computes the non-canonical
  body_ratio/wick_size/body_size) is wired only via `agent/modes/pipeline_mode.py:160`. **Backtests do
  NOT use it** (they build features from the canonical `feature_pipeline`). So GD-001/002/003 are
  `execution_reachability = conditional` (live-hook path only; live production PnL itself F-010-unverified).

**Tooling gap (recorded):** no static tool here proves function-reachability from a live entry point —
`config_reachability.py` = config keys only; `gen_pyan.py`/`pyan_call_flow.dot` = unannotated,
module/function graph clutter; `framework_registry` = hand-curated. Manual source reading is
authoritative; pyan edges are corroboration only.

## The `same_quantity` identity criterion (used below)

A site is `same_quantity` **only if all hold**, else `name_collision_distinct` / `unknown`:
same intended market concept · same units/dimensionality · same observation timestamp · same
timeframe/context · same downstream semantic contract. (Name equality alone is insufficient; formula
equality is a *separate* dimension.) This is decisive for the three `disp_strength` sites — each is a
**distinct** quantity that merely reuses the name.

## Matrix v1

| GD | Site (`qualname::target`) | FM | semantic_class | formula_equivalence | exec_reach | decision_reach |
|---|---|---|---|---|---|---|
| GD-001 | live_engine_hook `_build_ohlcv_and_auxiliary::body_ratio` | FM-010 | same_quantity | non_equivalent | conditional | **reachable** |
| GD-002 | live_engine_hook `_build_ohlcv_and_auxiliary::wick_size` | FM-002 | same_quantity | non_equivalent | conditional | **reachable** |
| GD-003 | live_engine_hook `_build_ohlcv_and_auxiliary::body_size` | FM-001 | same_quantity | **byte_identical** | conditional | reachable |
| GD-004 | scoring_engine `compute_scores::disp_strength` | FM-020 | name_collision_distinct | non_equivalent | reachable | reachable |
| GD-005 | crt_engine_v2 `StateMachine.try_expansion_to_retest::disp_strength` | FM-020 | name_collision_distinct | non_equivalent | reachable | reachable (hard REJECT) |
| GD-006 | crt_engine_v2 `RangeDetector.detect_sweep::upper_wick` | FM-003 | name_collision_distinct | non_equivalent | reachable | **unreachable** (diagnostic) |
| GD-007 | crt_engine_v2 `RangeDetector.detect_sweep::lower_wick` | FM-004 | name_collision_distinct | non_equivalent | reachable | **unreachable** (diagnostic) |
| GD-008 | crt_sweep_taxonomy `candle_geometry::upper_wick` | FM-003 | name_collision_distinct | non_equivalent | **unreachable** (dead) | unreachable |
| GD-009 | crt_sweep_taxonomy `candle_geometry::lower_wick` | FM-004 | name_collision_distinct | non_equivalent | **unreachable** (dead) | unreachable |
| GD-010 | rr_engine `RREngine.compute::candle_range` | FM-002 | same_quantity | **byte_identical** | conditional (gate-ON) | conditional |

All `observed_value_drift` / `observed_score_drift` / `observed_decision_flips` = **not_measured**
(Matrix v1). Full per-pin `evidence` call-chains + `review_trigger` live in the GD records
(`scripts/analysis/feature_math_lint.py`) and the machine-readable `.json` beside this doc.

## Gate-2 eligibility (mechanical, derived from Matrix v1)

A differential drift probe is built **only** for sites where a *canonical counterpart exists and the
wrong value can reach a decision*:
```
semantic_class == same_quantity  AND  formula_equivalence == non_equivalent  AND
decision_reachability ∈ {reachable, conditional}
```
- **Eligible: GD-001 (body_ratio), GD-002 (wick_size).** These are the only two where a wrong FORMULA
  of a *real* feature can reach the fusion decision (via the live-hook path).
- **Not eligible:** GD-003/GD-010 (`byte_identical` — no drift possible); GD-004/005 (`name_collision_
  distinct` — a distinct quantity, no canonical to diff against → **rename**); GD-006/007
  (decision-unreachable diagnostic); GD-008/009 (dead).

## Remediation dispositions (all DEFERRED to their own governed Phase-B finding)

Per the ratchet, a pin's GD-id is retired (via the manifest) only in the change that resolves its site.

| GD | disposition | Phase-B unit |
|---|---|---|
| GD-001, GD-002 | route live body_ratio/wick_size through the registry — **behavior-changing** | finding, gated on the Gate-2 drift/flip evidence + user approval |
| GD-003, GD-010 | route through candle_math — **byte-identical** | determinism-gated parity finding |
| GD-004, GD-005 | **rename** the distinct scoring/structural quantity | rename finding (no registry routing) |
| GD-006, GD-007 | rename → `upper/lower_wick_ratio` (FM-011/012) or accept | low-priority (decision-unreachable) |
| GD-008, GD-009 | **delete** dead `candle_geometry()` (§6.2) | dead-code finding (resolves both) |

## Matrix v2 — differential measurement (Gate 2, 2026-07-07)

Read-only probe `scripts/analysis/feature_math_drift_probe.py` drove the **real** `crt_engine.compute`
(the verified direct consumer) twice per bar — canonical `body/candle_range` vs current `body/total_wick`,
all else fixed — on **BNBUSDT M15, 19,922 bars**. Results (`reports/feature-math-drift-probe.md`):

| Channel | Measurement |
|---|---|
| value differs (bars) | **97.0%** |
| current ≥ canonical (systematic inflation) | **99.2%** (confirms `candle_range ≥ total_wick` ⇒ current ≥ canonical) |
| current `body_ratio` > 1.0 (bound violation — impossible for canonical) | **46.0%** of bars |
| \|Δ body_ratio\| | median 0.50 · p95 7.11 · max 494 (total_wick→0) |
| **CRT score changes** | **96.7%** of bars (inflated 95.9%) |
| \|Δ CRT score\| | median 0.026 · p95 0.060 · max 0.125 |

**Score-channel verdict:** the non-canonical formula systematically inflates the CRT breakout score on
~97% of bars. `observed_value_drift`/`observed_score_drift` = **measured**. (Step 7b only — score drift
is NOT decision drift; see 7c below.)

> **CORRECTED 2026-07-08 (E-001).** An earlier revision of this section declared Matrix v2 "frozen" and
> ranked GD-001/GD-002 as the **#1 behavior-changing** unit **on score drift alone**, while
> `observed_decision_flips` was still `not_measured`. That was premature under the plan's own exit
> criteria (Gate 2 = value → score → **decision**). Step 7c below supplies the missing measurement and
> the ranking is re-derived from it. (`<old>`: "Matrix v2 frozen; GD-001/002 rank #1 behavior-changing".)

> **RETRACTED 2026-07-08 (E-001, second correction).** The Step-7c decision-flip result below (0 flips)
> and the re-ranking that followed were finalized on a harness whose **causal validity was never proven**.
> On inspection the experiment fails admissibility: (1) **corpus parity** — the score/drift probe used
> 19,922 candles, this decision probe used 70,002 (different corpora); (2) **input isolation** — Branch A/B
> differ in `body_ratio` AND `wick_size`, not a single variable; (3) **no positive control** — the harness
> was never shown able to DETECT a flip, so `0` is uninterpretable; (4) unresolved runtime-path deviations
> (zone-invalid monkeypatch, session-encoding fix, `direction` from `trend_bias`, omitted FeatureStore).
> `observed_decision_flips` is reset to **not_measured**; Matrix v2 is **UN-frozen**; the ranking below is
> **not authoritative**. The numbers below are retained ONLY as a record of the retracted attempt.
>
> **V1–V10 outcome (2026-07-08, `reports/decision-flip-validation.md`): `POSITIVE_CONTROL_NOT_CONSTRUCTIBLE`.**
> The `run()` boundary **structurally cannot execute** — the DecisionEngine rr gate compares the RR engine's
> polarity score (`rr_ratio ∈ [0,1]`, `rr_engine.py:79`) against `rr_threshold=1.5`, so `low_rr` fires on
> every candle after the score passes (0/70,002 executes); and in the backtest `run()` is a **veto** whose
> only non-veto reject-reason is `zone_gate_invalid` (bypassed), which is body_ratio-independent. body_ratio
> reaches only the fused SCORE → it can change the reject *reason* (low_score↔low_rr) but never `execute`/veto.
> ⇒ **decision-inert at the `run()` boundary BY STRUCTURE** (source-confirmed; stronger than a counterfactual,
> and the correct explanation for the retracted "0 flips"). A per-candle `run()` harness is the WRONG
> instrument; the right one is a full-**backtest LEDGER diff** (canonical vs current body_ratio → which CRT
> trades survive the veto), predicted 0 but **not yet empirically measured**. So `observed_decision_flips`
> stays `not_measured` (empirically), with a source-structural decision-inertia argument on record.

## (RETRACTED) Matrix v2 — Step 7c decision-flip measurement (Gate 2, 2026-07-08)

Read-only harness `scripts/analysis/feature_math_decision_flip_probe.py` drove the **real
`EngineRunner.run()`** decision boundary twice per candle — Branch A (current `body/total_wick`) vs
Branch B (canonical), all else fixed — on **BNBUSDT M15, 70,002 candles**. A/B share the same evolved
adaptive state per candle (deepcopy snapshot); `zone_gate_invalid` bypassed exactly as `backtest_v2`
does (it is orthogonal to body_ratio and otherwise rejects every candle); session encoding fixed
(pipeline `0=london` vs adapter `0=asia`).

| Measurement | Value |
|---|---|
| score-gated candles (reached the body_ratio-sensitive score/rr gate) | **39,456** / 70,002 |
| **decision flips (adaptive)** | **0** (rate 0.000%) |
| decision flips (frozen-threshold sensitivity) | **0** |
| conditional flip rate (among score-gated) | **0 / 39,456 = 0.000%** |
| approvals (current A) / (canonical B) | **0 / 0** |
| reason histogram (canonical) | low_score 39,418 · invalid_session:asia 23,346 · low_rr 6,918 · regime 320 |

**7c verdict — DECISION-INERT.** Despite 96.7% CRT-score drift, canonicalizing GD-001/GD-002 produced
**0 decision flips across 70,002 candles / 39,456 score-gated candles**. The fused-score Δ (0.4·ΔCRT ≈
0.002–0.013, p95 0.024) never bridges the score/rr/threshold gauntlet. `observed_decision_flips` =
**measured (0)**.
**BOUND, not exhaustive:** the harness evaluates every candle (0 approvals in either branch) — it does
NOT reproduce the ~13 CRT-state-gated live setups where `run()` actually executes; a definitive
live-setup flip rate would need the CRT-spine harness. Direction of evidence is nonetheless decisive:
inflating body_ratio (which raises the score on 96.7% of bars) added **0** executes and flipped **0**
decisions.

## (RETRACTED) Remediation ranking — depended on the unvalidated 0-flip measurement

**This ranking is withdrawn.** It was derived from the retracted 0-flip result; until the harness passes
V1–V10 the decision-flip rate is `not_measured`, so GD-001/002 remain at their Matrix-v1 status
(same_quantity, non_equivalent, decision-reachable) with urgency **UNDETERMINED** — neither "#1
behavior-changing" nor "hygiene" is established. The table below is retained only as the retracted attempt:

| Rank | GD | disposition | why (measured) |
|---|---|---|---|
| 1 | GD-005 | **rename** (`displacement_atr_ratio`) | decision-reachable HARD REJECT; distinct quantity (correctness) |
| 2 | GD-004 | **rename** scoring-local var | decision-reachable; distinct (`features['disp_strength']/atr`) |
| 3 | GD-003, GD-010 | byte-identical route-through | determinism-gated, zero behavior change |
| 4 | **GD-001, GD-002** | route through registry — **hygiene** (was "#1 behavior-changing") | score-material but **0 measured decision flips** → correctness, not urgency |
| 5 | GD-006, GD-007 | rename→`upper/lower_wick_ratio` or accept | decision-unreachable diagnostic |
| 6 | GD-008, GD-009 | **delete** dead `candle_geometry()` | unreachable dead code |

## Incidental observations (tangential to GD-001/002 — flagged, not adjudicated here)
- **Session encoding mismatch:** feature-pipeline `SESSION_MAP` (`london=0,newyork=1,asian=2`) vs
  `trap_validator` (`0=asia,1=london,2=new_york`). The backtest engine-gate passes the pipeline int
  directly → the adapter misreads london as asia. Live normalizes to strings, so likely live-safe;
  worth its own finding.
- **`zone_gate_invalid` always-rejects in `run()`:** DecisionEngine:129 needs `zone_gate['valid']`,
  which `run()`'s `zone_result` never sets → every candle rejects unless bypassed (backtest bypasses;
  live path presumably sets validity via a flow not visible in `run()`). Governance-relevant; separate.

## Scope caveats (E-001)
- Decision-inert **at the run() boundary on this harness** ≠ proof of zero live impact: F-010 (live
  unverified) + the harness not being CRT-setup-gated. But score drift demonstrably does NOT propagate
  to decisions here. **No production-loss claim; and no "harmless" claim beyond the measured 0 flips.**

---

## Phase-B closure — GD-004 / GD-005 (2026-07-11, `CH-gd004-gd005-disp-strength-closure`)

The Matrix-v1 remediation-priority items #1 and #2 are CLOSED, identity-only (byte-identical,
parity-tested; no behavior change):

- **GD-005** — adjudicated **exactly FM-028** (`Candle.wick_size ≡ candle_range` per F-046);
  [PATCH 7] gate routed through `derived_math.displacement_atr_ratio`, local renamed
  `_displacement_atr_ratio`. Pin retired.
- **GD-004** — adjudicated a genuinely **NEW third identity** (probe on BNBUSDT 29,922 bars:
  equals FM-028 **0.00%**, equals FM-020 2.08% zero-disp bars only) → registered
  **FM-029 `disp_strength_atr_rescale`** (`FM-020/atr_rel`), routed + local renamed. Pin retired.
  Characterization: the as-wired value saturates `s_breakout`'s `min(x/2,1)` on **97.5%** of bars.
  The suspected `crt_engine.py:23` caller mis-wire (raw move plausibly intended) is **deferred**
  as `FU-CRT-MOVE-MISWIRE` (gate-ON behavior change; bounded per F-037/F-048).

GD-001/002/003 (2026-07-10) + GD-004/005 (2026-07-11) are now retired; **no `disp_strength` pin remains** — bare `disp_strength` derivation is
now a hard lint failure. Remaining open pins: GD-006/007 (decision-unreachable diagnostic ratios),
GD-008/009 (dead `candle_geometry()`), GD-010 (byte-identical `candle_range` route-through).
Evidence: `docs/governance/gd004_gd005_disp_strength_closure-2026-07-11.{md,json}` +
`docs/governance/gd004_disp_rescale_probe-2026-07-11.json`.

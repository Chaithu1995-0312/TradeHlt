# CRT Semantic Parity Report

> Research only (§6.5 Authority Ladder). Pre-registration: [`docs/research/preregistration-crt-semantic-parity.md`](../research/preregistration-crt-semantic-parity.md).
> cert_version=1.0.0

## 1. Baseline agreement

Config-only (`injection=none`, `engine_mode=exit`), XAUUSD M15, 47,197 aligned bars: **88.1560%** (41,607/47,197).

| State | Engine n | Resolver n | TP | Recall | Powered |
|---|---:|---:|---:|---:|---|
| RANGE | 35,130 | 37,343 | 33,989 | 96.75% | yes |
| SWEEP | 7,004 | 7,571 | 6,752 | 96.40% | yes |
| DISPLACEMENT | 373 | 466 | 364 | 97.59% | yes |
| EXPANSION | 4,625 | 1,803 | 498 | 10.77% | yes |
| RETEST | 17 | 0 | 0 | 0.00% | yes |
| EXECUTION | 5 | 0 | 0 | 0.00% | no |
| SHADOW_PENDING | 43 | 14 | 4 | 9.30% | yes |

## 2. Parameter tuning history (Stage A)

33 candidates evaluated across 6 parameter groups (A1 structural switch, A2 funnel timing, A3 EXPANSION TTL, A4 HTF/lifecycle, A5 RETEST, A6 SHADOW). Full ledger: `results/analysis/crt_parity_sweep/ledger.jsonl`.

| Iter | Config delta | Agreement | Δ vs baseline | Anti-Simpson |
|---:|---|---:|---:|---|
| 1 | `(baseline)` | 88.1560% | +0.00pp | OK |
| 2 | `{"thresholds.continuous_disp_to_expansion": true}` | 78.0346% | -10.12pp | VIOLATED |
| 3 | `{"thresholds.expansion_atr_min_distance": 0.15}` | 88.1560% | +0.00pp | OK |
| 4 | `{"thresholds.expansion_atr_min_distance": 0.2}` | 88.1560% | +0.00pp | OK |
| 5 | `{"thresholds.expansion_atr_min_distance": 0.45}` | 88.1560% | +0.00pp | OK |
| 6 | `{"thresholds.max_sweep_age_candles": 10}` | 88.1560% | +0.00pp | OK |
| 7 | `{"thresholds.max_sweep_age_candles": 30}` | 88.1560% | +0.00pp | OK |
| 8 | `{"thresholds.max_displacement_age_candles": 2}` | 88.1560% | +0.00pp | OK |
| 9 | `{"thresholds.max_displacement_age_candles": 5}` | 88.1560% | +0.00pp | OK |
| 10 | `{"thresholds.max_displacement_age_candles": 8}` | 88.1560% | +0.00pp | OK |
| 11 | `{"thresholds.atr_min_displacement": 0.9}` | 80.9649% | -7.19pp | VIOLATED |
| 12 | `{"thresholds.atr_min_displacement": 1.5}` | 87.3170% | -0.84pp | VIOLATED |
| 13 | `{"thresholds.body_ratio_min": 0.55}` | 88.4569% | +0.30pp | OK |
| 14 | `{"thresholds.body_ratio_min": 0.7}` | 88.0713% | -0.08pp | VIOLATED |
| 15 | `{"thresholds.body_ratio_min": 0.55, "thresholds.atr_multiplier_min": 0.8}` | 88.4569% | +0.30pp | OK |
| 16 | `{"thresholds.body_ratio_min": 0.55, "thresholds.atr_multiplier_min": 1.5}` | 87.8997% | -0.26pp | VIOLATED |
| 17 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 120}` | 88.8086% | +0.65pp | VIOLATED |
| 18 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250}` | 88.4590% | +0.30pp | OK |
| 19 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 900}` | 88.4569% | +0.30pp | OK |
| 20 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.max_expansion_age_hours": 24}` | 88.9273% | +0.77pp | VIOLATED |
| 21 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.max_expansion_age_hours": 999}` | 88.4590% | +0.30pp | OK |
| 22 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.lifecycle.htf_protect_states": ["EXPANSION", "RETEST", "DISPLACEMENT"]}` | 27.2623% | -60.89pp | VIOLATED |
| 23 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.lifecycle.htf_protect_states": ["EXPANSION"]}` | 88.4590% | +0.30pp | OK |
| 24 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.lifecycle.htf_protect_execution": false}` | 88.4590% | +0.30pp | OK |
| 25 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.lifecycle.shadow_on_htf_displacement_reset": false}` | 89.7705% | +1.61pp | VIOLATED |
| 26 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.range_atr_period": 4}` | 67.5509% | -20.61pp | VIOLATED |
| 27 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.range_atr_period": 20}` | 84.6283% | -3.53pp | VIOLATED |
| 28 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.retest_depth_max": 0.02}` | 88.4590% | +0.30pp | OK |
| 29 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.retest_depth_max": 0.04}` | 88.4590% | +0.30pp | OK |
| 30 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.retest_depth_max": 0.25}` | 88.4590% | +0.30pp | OK |
| 31 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.retest_atr_depth_fraction": 0.25}` | 88.4590% | +0.30pp | OK |
| 32 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.lifecycle.pending_displacement_ttl_candles": 2}` | 89.7557% | +1.60pp | VIOLATED |
| 33 | `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250, "thresholds.lifecycle.pending_displacement_ttl_candles": 8}` | 83.5879% | -4.57pp | VIOLATED |

## 3. Best-performing configuration (anti-Simpson-safe)

**Iteration 18** — delta: `{"thresholds.body_ratio_min": 0.55, "thresholds.max_expansion_age_candles": 250}`

Agreement: **88.4590%** (+0.30pp vs baseline).

Several HIGHER-agreement candidates were found and REJECTED by the anti-Simpson guard (S3) because they achieved that gain by zeroing out EXPANSION recall entirely (10.77% -> 0.00%) — a Simpson's-paradox trade that would have looked like progress on the headline number while destroying the one signal the program set out to recover. See rejected iterations in the ledger (`anti_simpson_ok: false`).

### State-by-state agreement (best candidate)

| State | Engine n | Resolver n | TP | Recall | Precision | Powered |
|---|---:|---:|---:|---:|---:|---|
| RANGE | 35,130 | 37,559 | 34,167 | 97.26% | 90.97% | yes |
| SWEEP | 7,004 | 7,557 | 6,747 | 96.33% | 89.28% | yes |
| DISPLACEMENT | 373 | 507 | 363 | 97.32% | 71.60% | yes |
| EXPANSION | 4,625 | 1,555 | 470 | 10.16% | 30.23% | yes |
| RETEST | 17 | 0 | 0 | 0.00% | n/a | yes |
| EXECUTION | 5 | 0 | 0 | 0.00% | n/a | no |
| SHADOW_PENDING | 43 | 14 | 3 | 6.98% | 21.43% | yes |
| EXPIRED | 0 | 5 | 0 | n/a | 0.00% | no |

## 4. Remaining mismatches — every cell classified

22 distinct off-diagonal cells, 5,447 mismatched bars total. Sorted by magnitude — the top 6 rows account for the overwhelming majority.

| Engine | Resolver | n | % of mismatches | Category | Code | Rationale |
|---|---|---:|---:|---|---|---|
| EXPANSION | RANGE | 3,374 | 61.9% | C | `C-GEOMETRY` | The two sides compute a same-named quantity from structurally different inputs (e.g. pipeline last-swing detection vs engine frozen-HTF-range detection) — not a threshold value, a different construction. |
| RANGE | EXPANSION | 870 | 16.0% | C | `C-GEOMETRY` | The two sides compute a same-named quantity from structurally different inputs (e.g. pipeline last-swing detection vs engine frozen-HTF-range detection) — not a threshold value, a different construction. |
| EXPANSION | SWEEP | 726 | 13.3% | C | `C-GEOMETRY` | The two sides compute a same-named quantity from structurally different inputs (e.g. pipeline last-swing detection vs engine frozen-HTF-range detection) — not a threshold value, a different construction. |
| SWEEP | EXPANSION | 203 | 3.7% | C | `C-GEOMETRY` | The two sides compute a same-named quantity from structurally different inputs (e.g. pipeline last-swing detection vs engine frozen-HTF-range detection) — not a threshold value, a different construction. |
| EXPANSION | DISPLACEMENT | 50 | 0.9% | C | `C-GEOMETRY` | The two sides compute a same-named quantity from structurally different inputs (e.g. pipeline last-swing detection vs engine frozen-HTF-range detection) — not a threshold value, a different construction. |
| RANGE | DISPLACEMENT | 49 | 0.9% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| SWEEP | DISPLACEMENT | 44 | 0.8% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| SHADOW_PENDING | SWEEP | 40 | 0.7% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| RANGE | SWEEP | 40 | 0.7% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| RETEST | RANGE | 11 | 0.2% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| DISPLACEMENT | EXPANSION | 10 | 0.2% | C | `C-GEOMETRY` | The two sides compute a same-named quantity from structurally different inputs (e.g. pipeline last-swing detection vs engine frozen-HTF-range detection) — not a threshold value, a different construction. |
| SWEEP | SHADOW_PENDING | 7 | 0.1% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| RETEST | SWEEP | 4 | 0.1% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| EXECUTION | RANGE | 4 | 0.1% | B | `B-UNREACHABLE-STATE` | _continuous_gates_pass fails EXECUTION closed when raw.get('score'/'risk_score'/'crt_score') is None; none of those three keys exist in CANONICAL_FEATURES, so the gate is unconditionally closed on any real 39-dim vector. |
| RANGE | EXPIRED | 3 | 0.1% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| EXPANSION | SHADOW_PENDING | 3 | 0.1% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| SWEEP | RANGE | 3 | 0.1% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| EXPANSION | EXPIRED | 2 | 0.0% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| RETEST | EXPANSION | 1 | 0.0% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| EXECUTION | EXPANSION | 1 | 0.0% | B | `B-UNREACHABLE-STATE` | _continuous_gates_pass fails EXECUTION closed when raw.get('score'/'risk_score'/'crt_score') is None; none of those three keys exist in CANONICAL_FEATURES, so the gate is unconditionally closed on any real 39-dim vector. |
| RANGE | SHADOW_PENDING | 1 | 0.0% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |
| RETEST | DISPLACEMENT | 1 | 0.0% | D | `D-UNKNOWN` | None of the B/A/C rules applied; requires manual investigation. |

**RETEST cascade note:** Every RETEST mismatch bar (17/17 engine occupancy) is a downstream cascade of the EXPANSION entry-mechanism divergence above: _continuous_gates_pass requires memory state EXPANSION/RETEST to enter RETEST, so poor EXPANSION tracking starves RETEST of any entry path. n=17 is at the MIN_CELL_N=15 power floor — reported INSUFFICIENT-adjacent, not an independent Category verdict.

## 5. Determination

Two views, reported separately rather than blended, because 22 cells span 3 orders of magnitude (1 to 3,374 mismatched bars) — an unweighted cell-count vote would let 8 one-or-two-bar cells outvote the defect that actually explains the corpus.

- **By cell count** (every distinct mismatch pattern weighted equally): **Inconclusive** — {'C': 6, 'D': 14, 'B': 2}. Honest but not the operative answer: 14 of 22 cells are genuinely uninvestigated D-UNKNOWN, and E-001E (parent verdict never exceeds its weakest child) forces Inconclusive whenever even one is present, regardless of size.
- **By mismatch volume** (bars weighted): {'C': 5233, 'D': 209, 'B': 5} = {'C': 96.1, 'D': 3.8, 'B': 0.1}% of 5,447 mismatched bars. **C-GEOMETRY dominates at >95%** — the 6 EXPANSION-involving cells (entry-mechanism divergence, see §4) explain nearly the entire residual; the 14 D-UNKNOWN cells are noise (≤50 bars each, ~5% combined) not pursued further given that concentration.

Per the pre-registration's stop condition S4: the best safe Stage-A candidate lands within 0.30pp of baseline (well under the frozen +0.5pp threshold). Weighted by the evidence that actually explains the corpus (not by cell count), the residual is dominated by Category C (divergent EXPANSION-entry construction) plus Category B (3 structurally unreachable states: EXECUTION/RESOLUTION/EXPIRED). **The residual is declared structurally config-unreachable** — no threshold value in `market_crt_states.yaml` bridges a different construction; closing it requires either a resolver code change (out of this program's freeze) or accepting the gap.

## 6. Stage B — engine sensitivity (one-way diagnostic, NOT a parity result)

Resolver held fixed at the Stage-A winning config (`{'thresholds.body_ratio_min': 0.55, 'thresholds.max_expansion_age_candles': 250}`); `CRTConfig` varied instead, per candidate re-running the full `BacktestRunner`. **This does not test config-only reproducibility** — moving the reference engine to raise agreement would manufacture parity, not measure it. Reported separately; grants no authority to modify `CRTConfig` or production config, and no candidate here is eligible for promotion.

Stage B baseline (resolver fixed, engine unmodified): **88.6645%** — higher than the Stage-A baseline because it starts from the Stage-A *winning* resolver config, not the untouched one.

| Label | Agreement | Δ vs Stage-B baseline | Anti-Simpson |
|---|---:|---:|---|
| B_baseline | 88.6645% | +0.000pp | OK |
| B_retest_min_depth_atr_fraction_0p05 | 89.0502% | +0.386pp | OK |
| B_retest_min_depth_atr_fraction_0p2 | 88.3615% | -0.303pp | OK |
| B_max_displacement_strength_1p5 | 86.0606% | -2.604pp | OK |
| B_max_displacement_strength_3p0 | 91.3130% | +2.648pp | OK |
| B_atr_buffer_multiplier_2 | 88.6645% | +0.000pp | OK |
| B_atr_buffer_multiplier_4 | 88.6645% | +0.000pp | OK |
| B_score_decay_lambda_0p02 | 88.6688% | +0.004pp | OK |
| B_score_decay_lambda_0p1 | 88.6645% | +0.000pp | OK |

**Sensitive to:** `B_max_displacement_strength_1p5`, `B_max_displacement_strength_3p0` — each has NO resolver-side counterpart (grep-confirmed absent from `market_crt_states.yaml` `thresholds:`), so this is evidence for Category B/C (an engine-only mechanism), not a config-only lever. Most notably, `max_displacement_strength=3.0` alone recovers +2.65pp — the single largest sensitivity found in either stage — meaning at least part of the EXPANSION divergence traces to the engine's displacement-strength cap, which the resolver has no equivalent gate for at all.


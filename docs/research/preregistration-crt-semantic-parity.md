# Pre-Registration — CRT Semantic Parity (CRTStateResolver ↔ BacktestRunner, Configuration-Only)

> **Status:** PRE-REGISTERED (written before any sweep candidate is evaluated). Authority:
> research/docs only (§6.5 Authority Ladder). This document FREEZES the primary metric, the
> baseline, the swept parameters, the classification taxonomy, and the stop conditions **before**
> the sweep runs, so a null cannot be quietly re-spun into a finding and a hit cannot be
> threshold-shopped. Enforced socially by the Epistemic Integrity ritual (Program E-001,
> [`docs/governance/EPISTEMIC_INTEGRITY.md`](../governance/EPISTEMIC_INTEGRITY.md)).

## Context & scope

Research question (user-specified, verbatim intent): **can `CRTStateResolver` reproduce
`BacktestRunner`'s semantic CRT-state decisions through configuration tuning alone?** This is a
controlled experiment under an explicit repository freeze — no formula changes, no new features,
no ontology edits, no `src/` implementation changes during this program. Only existing
configuration values (`configs/formulas/market_crt_states.yaml` thresholds, plus — per user
decision — `CRTConfig` engine overrides in a separate, clearly-labeled diagnostic stage) may be
tuned.

**Primary-metric correction (discovered, not assumed).** The existing instrument
(`scripts/research/crt_state_confusion_matrix.py`) historically ran with the resolver's
`engine_reset`/`engine_state_to` oracle-assist parameters unconditionally enabled — i.e. the
resolver was fed the engine's own RESET events and STATE_TRANSITION targets on every call. That
mode does **not** answer "configuration alone": it hands the resolver privileged information no
config-only deployment would have. The instrument now exposes an explicit `injection` axis
(`none | reset | state_to | full`; `scripts/research/crt_state_confusion_matrix.py::INJECTION_MODES`).
**`injection=none` is the only mode that measures the stated research question and is the
program's primary metric.** The other three modes are retained as labeled diagnostics only (they
bound how much of the residual survives even with oracle assistance, which is evidence for
Category B, never a parity claim).

**Concurrent-edit note.** Mid-session, another actor (the user's own parallel session) modified
`src/features/crt_state_resolver.py` and `configs/formulas/market_crt_states.yaml` live (the
"B1h" change: a new `continuous_disp_to_expansion` threshold, default `false`, plus reworked
`engine_state_to` FROM>TO injection semantics). This program's baseline is measured against that
settled state, confirmed stable via `git status`/mtime before re-measuring, and confirmed
deterministic (see below). It supersedes the earlier stale 64.16% figure quoted in prior session
notes and the earlier oracle-contaminated 88–99% figures from before the injection axis existed.

## Reproducibility (verified before registering any prediction)

`injection=none`, `engine_mode=exit`, default HTF phase-lock, over the full 47,275-bar XAUUSD M15
corpus (`data/mt5/XAUUSD_M15.csv`): **2 independent processes × 3 in-process resolver runs each =
6/6 identical** `sha256("|".join(states))[:16] = 78083e6816b42cea`. Deterministic; the sweep is
interpretable.

## Baseline (frozen; the denominator for every "% improvement" claim below)

`injection=none`, `engine_mode=exit` — the CLI's actual comparison semantics
(`--engine-mode` default; matches resolver post-process/sticky semantics):

| State | Engine n | Resolver n | TP | Recall | Powered (n≥15) |
|---|---:|---:|---:|---:|---|
| RANGE | 35,130 | 37,343 | 33,989 | 96.75% | yes |
| SWEEP | 7,004 | 7,571 | 6,752 | 96.40% | yes |
| DISPLACEMENT | 373 | 466 | 364 | 97.59% | yes |
| **EXPANSION** | **4,625** | **1,803** | **498** | **10.77%** | yes |
| RETEST | 17 | 0 | 0 | 0.00% | borderline |
| EXECUTION | 5 | 0 | 0 | 0.00% | **no** |
| SHADOW_PENDING | 43 | 14 | 4 | 9.30% | borderline |

**Overall agreement: 41,607 / 47,197 = 88.16%.**

Top confusions: `EXPANSION→RANGE 3,335`, `RANGE→EXPANSION 1,052`, `EXPANSION→SWEEP 735`,
`SWEEP→EXPANSION 242`, `EXPANSION→DISPLACEMENT 54`. RANGE/SWEEP/DISPLACEMENT are already at
parity; essentially the entire 11.84-point gap is one state.

Diagnostic-only injected arms (NOT parity claims), same corpus/mode, for calibrating how much of
the residual is oracle-closeable: `reset`-only 89.54%, `state_to`-only 99.07%, `full` 99.96%.
The `state_to`-only arm nearly closing the gap (recovering EXPANSION recall to ~99%) is evidence
that the *entry/exit timing logic* for EXPANSION, not the feature vector itself, is the
locus of the defect — informs the Category A/B split below but is not itself config-only evidence.

## Predictions (frozen before the first sweep candidate)

1. **EXECUTION is structurally unreachable by any resolver configuration.** `_continuous_gates_pass`
   fails EXECUTION closed whenever `raw.get("score"/"risk_score"/"crt_score")` is `None`
   (`src/features/crt_state_resolver.py` — the score-gate block), and none of those three keys is
   in `CANONICAL_FEATURES` (`src/features/feature_schema.py`). Category B. Confidence: Certain.
   *Falsifier:* any Stage-A candidate emits ≥1 EXECUTION bar.
2. **RESOLUTION and EXPIRED stay unreachable** (declarative `when: {}` — trade-state/TTL-only in
   `configs/formulas/market_crt_states.yaml`). Category B. *Falsifier:* either appears in any
   candidate's resolver counts.
3. **EXPANSION recall is recoverable by config alone into the 60–90% range**, primarily via
   `thresholds.continuous_disp_to_expansion` (currently `false`) and/or `expansion_atr_min_distance`
   /`max_sweep_age_candles`/`max_displacement_age_candles` funnel-timing knobs — because the
   `state_to`-only diagnostic (99% recall) shows the feature vector already carries enough signal;
   the gap is entry/exit *timing*, which the existing continuous-funnel gates target directly.
   Category A (predicted, to be confirmed). *Falsifier:* best Stage-A candidate stays within 5pp
   of the 10.77% baseline recall.
4. **RETEST stays at ≤2 true positives.** 17 engine bars is close to the `MIN_CELL_N=15` power
   floor; even a large recall swing is 0–3 raw bars. Reported INSUFFICIENT-adjacent, never a hard
   Category verdict. *Falsifier:* TP ≥ 5 on a single candidate (would itself be a low-power,
   caveated result).
5. **Overall config-only ceiling: 88.16% + 8pp ≤ ceiling ≤ 88.16% + 12pp** (i.e. roughly
   96–100%, since RANGE/SWEEP/DISPLACEMENT are already saturated and EXPANSION is the only state
   with real headroom — recovering it to ~90% recall adds ~4,625×0.8/47,197 ≈ +7.8pp). *Falsifier:*
   any candidate exceeding 100.0% (impossible) or the best full coordinate-descent pass landing
   below 92%.
6. **RANGE/SWEEP/DISPLACEMENT do not regress by more than 2pp on any accepted candidate** — the
   anti-Simpson stop condition (S3, below) exists specifically to prevent trading this away for a
   headline agreement gain.
7. **SHADOW_PENDING stays under-powered (43 engine bars)** and any recall change is reported with
   an explicit low-power caveat, not promoted to a category verdict on its own.

## Swept parameters (Stage A — resolver-only, config-only)

Engine events computed once (existing `results/run_20260724_104845_XAUUSD/XAUUSD_events.jsonl`);
only `market_crt_states.yaml`-equivalent candidate YAMLs vary. Ordered by predicted impact given
the measured EXPANSION-dominant profile:

- **A1 (highest predicted impact):** `continuous_disp_to_expansion {false, true}` — the newly
  added B1h flag, directly gating the continuous (non-oracle) DISPLACEMENT→EXPANSION promotion
  path that is OFF in the baseline.
- **A2 — EXPANSION entry/exit funnel timing:** `expansion_atr_min_distance`, `max_sweep_age_candles`,
  `max_displacement_age_candles`, `atr_min_displacement`, `body_ratio_min`, `atr_multiplier_min`.
- **A3 — EXPANSION lifecycle/TTL:** `max_expansion_age_candles`, `max_expansion_age_hours`
  (governs how long a wrongly-entered or wrongly-held EXPANSION persists before self-correcting).
- **A4 — HTF/lifecycle switches:** `lifecycle.htf_protect_states`, `lifecycle.htf_protect_execution`,
  `lifecycle.shadow_on_htf_displacement_reset`, `range_atr_period`.
- **A5 — RETEST (under-powered, low expected yield):** `retest_depth_max`, `retest_atr_depth_fraction`.
- **A6 — SHADOW:** `pending_displacement_ttl_candles`.
- **A7 — `states:` evaluation order** (first-match-wins is a genuine config lever) — named
  permutations only, tried last, only if A1–A3 plateau.

**Strategy:** A1 first (single boolean, cheap, highest predicted impact) → coordinate descent over
A2–A6 → a 2-factor local interaction check around the winner. Budget ≤250 candidates.

## Stage B — engine sensitivity (one-way diagnostic, promotion forbidden)

Per user decision, `CRTConfig` overrides may also be swept, re-running `BacktestRunner` per
candidate. This does **not** test "config-only reproducibility" — moving the reference engine
manufactures parity rather than testing it — so Stage B is scoped as a **one-way sensitivity
diagnostic**: which engine-side gates the residual is sensitive to, reported separately from the
Stage-A parity number, with promotion explicitly forbidden. Params (each has no resolver
counterpart, so each is a candidate explanation for any unclosable gap):
`retest_min_depth_atr_fraction`, `max_displacement_strength`, `atr_buffer_multiplier`,
`score_decay_lambda`. Budget ≤24 candidates, `engine_mode=exit` held fixed throughout.

## Mismatch classification taxonomy (every residual mismatch classified, never left bare)

`scripts/research/crt_parity_classifier.py` — pure, stdlib-only, synthetically drivable:

| Code | Category | Rule |
|---|---|---|
| `B-UNREACHABLE-STATE` | B | `engine_state ∈ {EXECUTION, RESOLUTION, EXPIRED}` |
| `B-NO-COUNTERPART` | B | Engine transition reason names a gate absent from resolver config |
| `A-THRESHOLD-DELTA` | A | Same named threshold, different value, gating the observed cell |
| `A-SWEEP-REACHABLE` | A | A swept candidate demonstrably shrank this cell (second pass) |
| `C-PHASE-ERROR` | C | Marginals agree (`\|res_n−eng_n\|/eng_n ≤ 0.15`) but recall ≤ 0.60 |
| `C-GEOMETRY` | C | Same-named quantity computed from structurally different inputs |
| `INSUFFICIENT` | — | `engine_n < MIN_CELL_N = 15` (precedent: `blind_label_score.py`); never REJECT |
| `D-UNKNOWN` | D | Fallthrough — investigated, never left unlabeled |

## Stop conditions

- **S0** reproducibility gate fails on re-check → hard stop (already passed; re-verified at the
  start of every sweep run in case the file changes again).
- **S1** a full coordinate-descent pass yields < +0.10pp overall → stop that stage.
- **S2** budget: Stage A ≤250 candidates, Stage B ≤24.
- **S3 (anti-Simpson):** reject any candidate that raises overall agreement while dropping any
  *powered* (`engine_n ≥ 15`) per-state recall by more than 5pp.
- **S4** if the best Stage-A candidate is within +0.5pp of the A1-only result, declare the
  remaining residual **structurally config-unreachable** and stop — a valid, registrable outcome.

## Determination (reported at closure, one of)

Configuration | Implementation | Mixed | Inconclusive — per the classified mismatch inventory,
not a single blended percentage.

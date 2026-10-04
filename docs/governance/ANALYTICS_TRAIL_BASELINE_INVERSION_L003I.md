# L-003I — Trail baseline direction / base-rate inversion

> **Ontology note (L-003J):** Primary measured object is `JOINT_OUTCOME_STATE` / `Y_joint = (Y_scanner, Y_oracle)`. `scanner_outcome` and `oracle_outcome` are **components**, not rival labels. Named joint populations (e.g. `JOINT_STATE_SL_TP`, `BOTH_SL`) are **states**, not errors. `LABEL_MATCH` / `LABEL_MISMATCH` remain terminal-label equality only; prefer state membership over "who is right". See `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`.

**Status:** MEASURED (falsification-oriented observation)
**Title:** `BASELINE_DIRECTION_MEASURED`
**L-003 remains NOT frozen** — attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS)
**Date (UTC):** 2026-09-07T19:34:04.182378Z
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`
**run_id:** `l003i_trail_baseline_inversion_20260907_193404`
**version / doctrine:** `L-003I.v1`

Machine-readable: `docs/governance/analytics_trail_baseline_inversion_l003i-2026-09-07.json`.

## Banner / discipline

**Observation → Measurement → Evidence → Promotion.**

- **Question:** Given L-003H measured P(trail_activated | JOINT)=1.0, what is the **inverse** base-rate direction P(JOINT | trail_activated) (and siblings)?
- **Method:** Bayes-facing contingency tables derived from the same L-003H replay universe counters (n=559,768); no new candle replay; no `src/` edits.
- **NOT answered:** trail *causes* JOINT / label mismatch; counterfactual without-trail world; promotion.
- **Lean retained (not upgraded):** `LEAN_SUPPORTS_TRAIL_EARLY_EXIT_PATTERN_IN_JOINT_STATE_SL_TP`


## Noun note — exit ordering (L-003-FREEZE.v1)

| Role | Name |
|---|---|
| Relation class (preferred) | `exit_ordering_relation` |
| Canonical observation | `scanner_exit_precedes_oracle_tp` |
| Formula | `scanner_exit_bar < oracle_tp_bar` (or oracle exit bar when TP) |
| Alias / deprecated | `scanner_exit_before_oracle_tp`, `trail_exit_before_oracle_tp`, `seb` |

Do **not** encode cause in the observation name. Historical counters/keys may retain aliases for reproducibility; new prose prefers the canonical name + relation class.

Freeze ref: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` / run_id `l003_package_freeze_20260907_201945`.

## Path semantics (explicit)

- **Path + TrailLogic → scanner:** trailing walk (`trail_mult=0.5`) → `scanner_outcome_replay`
- **Path + FixedLogic → oracle:** `intrabar_fixed` walk → `oracle_outcome_replay`
- No counterfactual without-trail world is constructed. Conditionals are associations within dual-path replay labels.

## Universe

n = **559,768** (BNB+BTC+ETH+SOL), reused from L-003H run `l003h_trail_exit_transitions_20260907_192115`.
Base rate P(JOINT_STATE_SL_TP) = **31.53%** (n_joint=176,471).

## A. Primary inversion (aggregate)

| Conditional | Estimate | Lift vs base (~31.53%) |
|---|---:|---:|
| P(JOINT \| trail_activated=1) | 47.19% | 1.4970× |
| P(JOINT \| trail_activated=0) | 0.00% | 0.0000× |
| P(JOINT \| trail_exit=1) | 48.22% | 1.5295× |
| P(JOINT \| trail_exit=0) | 0.00% | 0.0000× |
| P(JOINT \| seb=1) | 100.00% | 3.1720× |
| P(JOINT \| seb=0) | 2.03% | 0.0643× |

Factor margins: n(trail_activated=1)=373,920; n(trail_exit=1)=365,991; n(seb=1)=168,540.

Noun note: `seb` is a **deprecated alias** for canonical `scanner_exit_precedes_oracle_tp` (`exit_ordering_relation`); retained in historical counters only.

## B. Confusion-style 2×2 counts (contingency language only)

**Do NOT call trail a predictor of edge.** Cells are co-occurrence counts.

### trail_activated × JOINT

|  | JOINT=1 | JOINT=0 |
|---|---:|---:|
| trail_activated=1 | 176,471 | 197,449 |
| trail_activated=0 | 0 | 185,848 |

### trail_exit × JOINT

|  | JOINT=1 | JOINT=0 |
|---|---:|---:|
| trail_exit=1 | 176,471 | 189,520 |
| trail_exit=0 | 0 | 193,777 |

### seb × JOINT

|  | JOINT=1 | JOINT=0 |
|---|---:|---:|
| seb=1 | 168,540 | 0 |
| seb=0 | 7,931 | 383,297 |

## C. Among trail_activated=1 — joint-state mix (critical base-rate story)

n(trail_activated=1) = 373,920.

| joint_state bucket | n among ta=1 | fraction |
|---|---:|---:|
| BOTH_SL | 182,208 | 48.73% |
| JOINT_STATE_SL_TP | 176,471 | 47.19% |
| BOTH_TP | 7,634 | 2.04% |
| OTHER | 7,607 | 2.03% |

**Critical:** L-003H already showed BOTH_TP also has 100% trail_activated. Among activations, BOTH_SL is the plurality (~48.73%); JOINT is only ~47.19%. Activation alone does **not** select JOINT.

## D. Precision / recall style (descriptive label-association only)

Treating `trail_exit` as a descriptive "detector" of JOINT (NOT trading performance):

- **precision** = P(JOINT | trail_exit=1) = 48.22%
- **recall** = P(trail_exit | JOINT) = 100.00% (matches L-003H ~1.0)

These are **label-association stats**, not trading performance / edge claims.

## E. LOIO stability of inversion conditionals

| holdout | n_train | P(JOINT|ta=1) | P(JOINT|te=1) |
|---|---:|---:|---:|
| holdout_BNBUSDT | 419,826 | 46.88% | 47.92% |
| holdout_BTCUSDT | 419,826 | 47.47% | 48.45% |
| holdout_ETHUSDT | 419,826 | 47.33% | 48.28% |
| holdout_SOLUSDT | 419,826 | 47.10% | 48.22% |

LOIO P(JOINT|ta=1): mean=47.19%, std=0.002227, range=[46.88%, 47.47%].
LOIO P(JOINT|te=1): mean=48.22%, std=0.001888, range=[47.92%, 48.45%].

## F. Baseline-direction reading (wording discipline)

BASELINE_WEAKENS_TRAIL_AS_JOINT_MARKER: among trail_activated=1, JOINT is only 0.4719 (~47.2%) while BOTH_SL is 0.4873; P(JOINT|trail_activated)=0.4719 vs base 0.3153 (lift 1.497). Trail activation is necessary-looking for JOINT (recall-side from H) but not precise for JOINT; BOTH_TP also 100% activated. trail_exit lifts slightly more than activation alone; seb is near-certain for JOINT when true but is path-timing not causation.

- Keep lean: **LEAN_SUPPORTS_TRAIL_EARLY_EXIT_PATTERN_IN_JOINT_STATE_SL_TP** (from L-003H exit-timing / trail_exit differentiation vs BOTH_TP).
- Do **not** upgrade to causality.
- Baseline direction **weakens** any reading that treats trail_activated as approximately identifying JOINT; it **leaves intact** the H finding that within JOINT, trail/exit timing patterns differ from BOTH_TP (seb / trail_exit), and that JOINT is trail-activated at 100% while BOTH_SL is ~50%.

## Per-instrument snapshot (P(JOINT|ta=1) / P(JOINT|te=1) / P(JOINT|seb=1))

- **BNBUSDT** n=139,942; P(J|ta)=48.13%; P(J|te)=49.10%; P(J|seb)=100.00%; base=32.01%
- **BTCUSDT** n=139,942; P(J|ta)=46.38%; P(J|te)=47.52%; P(J|seb)=100.00%; base=31.01%
- **ETHUSDT** n=139,942; P(J|ta)=46.79%; P(J|te)=48.03%; P(J|seb)=100.00%; base=31.25%
- **SOLUSDT** n=139,942; P(J|ta)=47.48%; P(J|te)=48.21%; P(J|seb)=100.00%; base=31.84%

## Flags

- `promotion`: False
- `l003_frozen`: False
- `attribution_unblocked`: False
- `economic_claims`: False
- `registry_edits`: False
- `causal_language_upgrade`: False

## Reproducibility

- Derived from: `docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json` (L-003H counters)
- Derivation script: `scripts/research/l003i_trail_baseline_inversion.py`
- Parent measurement script (not re-run): `scripts/research/l003h_trail_exit_transition_replay.py`
- Commit: `d7c25f6e55616261b8b229b000875abd3bd315eb`

## Parent links

- L-003H: `docs/governance/ANALYTICS_TRAIL_EXIT_TRANSITIONS_L003H.md`
- L-003F: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md`

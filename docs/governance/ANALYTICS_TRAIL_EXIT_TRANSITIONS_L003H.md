# L-003H — Trail / exit transition events (candle replay)

> **Ontology note (L-003J):** Primary measured object is `JOINT_OUTCOME_STATE` / `Y_joint = (Y_scanner, Y_oracle)`. `scanner_outcome` and `oracle_outcome` are **components**, not rival labels. Named joint populations (e.g. `JOINT_STATE_SL_TP`, `BOTH_SL`) are **states**, not errors. `LABEL_MATCH` / `LABEL_MISMATCH` remain terminal-label equality only; prefer state membership over "who is right". See `docs/governance/ANALYTICS_JOINT_OUTCOME_STATE_ONTOLOGY_L003J.md`.

**Status:** MEASURED (falsification-oriented observation)
**L-003 remains NOT frozen** — attribution remains blocked (IDENTITY + OUTCOME_SEMANTICS)
**Date (UTC):** 2026-09-07T19:23:21.428584Z
**Branch pin:** `feature/trace-parquet-duckdb-query` @ `d7c25f6e55616261b8b229b000875abd3bd315eb`
**run_id:** `l003h_trail_exit_transitions_20260907_192115`
**version / doctrine:** `L-003H.v1`

Machine-readable: `docs/governance/analytics_trail_exit_transitions_l003h-2026-09-07.json`.

## Banner / discipline
> **Ontology note (L-003J):** Measured scanner_exit_bar earlier than oracle is **path-timing association**; it does not upgrade detector-stopped-early beyond that inequality, and does not establish trail causality.



**Observation → Measurement → Evidence → Promotion.**

- **Question:** Does `JOINT_STATE_SL_TP` show measured trail/exit transition patterns that `BOTH_SL` / `BOTH_TP` do not?
- **Method:** candle replay of trailing walk (scanner process, `trail_mult=0.5`) and fixed walk (`intrabar_fixed` oracle) with event hooks — **not** inferred from T_MAE alone.
- **NOT answered:** trail *causes* label mismatch; which Y should replace the other; promotion.

## Terminology (L-003-TERM.v1 compliant)

| Term | Meaning | Claim class |
|---|---|---|
| `scanner_outcome_replay` | re-simulated `opportunity_scanner._simulate` trailing walk | measured |
| `art_outcome` | opportunities.jsonl scanner label (artifact) | measured (identity xref) |
| `oracle_outcome_replay` | re-simulated `forward_walk(exit_model=intrabar_fixed)` | measured |
| `JOINT_STATE_SL_TP` | scanner=SL_HIT × oracle=TP_HIT | joint state_id (canonical) |
| `EARLY_STOP_CANDIDATE` | SAFE_ALIAS for `JOINT_STATE_SL_TP` only | research alias — NOT observation that detector stopped early |
| `trail_activated` | stop first ratchets from initial SL on trailing walk | measured event |
| `scanner_exit_precedes_oracle_tp` (alias `scanner_exit_before_oracle_tp` / `seb`) | oracle TP and `scanner_exit_bar < oracle_tp_bar`; class `exit_ordering_relation` | measured path-timing operationalization; **not** trail-causality proof; cause-free name |
| "detector stopped early" | interpretive claim | **INFERENCE** unless exit timestamps prove inequality (rate measured here) |


## Noun note — exit ordering (L-003-FREEZE.v1)

| Role | Name |
|---|---|
| Relation class (preferred) | `exit_ordering_relation` |
| Canonical observation | `scanner_exit_precedes_oracle_tp` |
| Formula | `scanner_exit_bar < oracle_tp_bar` (or oracle exit bar when TP) |
| Alias / deprecated | `scanner_exit_before_oracle_tp`, `trail_exit_before_oracle_tp`, `seb` |

Do **not** encode cause in the observation name. Historical counters/keys may retain aliases for reproducibility; new prose prefers the canonical name + relation class.

Freeze ref: `docs/governance/ANALYTICS_L003_PACKAGE_FREEZE.md` / run_id `l003_package_freeze_20260907_201945`.

## Horizon / defaults

- `MAX_FORWARD=40` for **both** trailing and fixed exit outcomes (matches anatomy governing layer / scanner `max_forward_candles=40`).
- `trail_mult=0.5` (scanner default).
- PEAK_HORIZON=96 is **not** used here (peak timing is out of scope for exit-transition events).
- Standalone script: `scripts/research/l003h_trail_exit_transition_replay.py` (no `src/` edits).

## Falsification criteria (stated upfront)

1. If `JOINT_STATE_SL_TP` has `trail_activated` rate ≈ `BOTH_SL` (no enrichment) → weakens trail-involvement hypothesis.
2. If `scanner_exit_before_oracle_tp` is not near-certain in `JOINT_STATE_SL_TP` → weakens "stopped earlier" inference.
3. If `trail_activated` enrichment is large in `JOINT_STATE_SL_TP` vs `BOTH_TP` → supports trail-involvement candidate (still not causation of label mismatch alone).

## A. Population census (replay joint states)

n = **559,768** (BNB+BTC+ETH+SOL).

| state_id | n | rate |
|---|---:|---:|
| `BOTH_SL` | 367,923 | 65.73% |
| `JOINT_STATE_SL_TP` | 176,471 | 31.53% |
| `BOTH_TP` | 7,634 | 1.36% |
| `SCANNER_SL_ORACLE_TIMEOUT` | 7,312 | 1.31% |
| `FALSE_TP_CANDIDATE` | 280 | 0.05% |
| `BOTH_TIMEOUT` | 148 | 0.03% |

### Reconcile vs L-003F (~31.53% JOINT_STATE_SL_TP / EARLY_STOP_CANDIDATE)

- Replay `JOINT_STATE_SL_TP` n/rate: **176,471** / 31.53%
- Artifact×oracle-replay `JOINT_STATE_SL_TP` n/rate: **176,471** / 31.53%
- L-003F expected ESC n/rate: **176,471** / 31.53%
- Artifact joint vs L-003F rate delta: 3.923482585488358e-07
- Scanner label match (art_outcome == scanner_outcome_replay): 100.00%
- Notes: L-003F used anatomy art_outcome × anatomy oracle outcome; this pass reconciles artifact scanner labels × re-simulated oracle, and separately reports fully re-simulated joint states.

## B. Trail / exit transitions by joint state

| Metric | JOINT_STATE_SL_TP | BOTH_SL | BOTH_TP |
|---|---:|---:|---:|
| n | 176,471 | 367,923 | 7,634 |
| trail_activated_rate | 100.00% | 49.52% | 100.00% |
| median bars_to_trail_activation | 1.0 | 1.0 | 1.0 |
| trail_exit_rate | 100.00% | 49.52% | 0.00% |
| scanner_exit_before_oracle_tp_rate | 95.51% | 0.00% | 0.00% |
| scanner_exit_before_oracle_tp among oracle TP | 95.51% (n_otp=176471) | — | — |
| median scanner_exit_bar | 1.0 | 2.0 | 1.0 |
| median oracle_exit_bar | 6.0 | 3.0 | 1.0 |

### Exit-bar delta (oracle_exit_bar − scanner_exit_bar) in JOINT_STATE_SL_TP

- median=4.0, p25=2.0, p75=8.0, mean=6.358217497492506
- frac(delta>0)=95.51% (positive ⇒ scanner exited earlier than oracle)

## C. Falsification lean

**Overall lean:** `LEAN_SUPPORTS_TRAIL_EARLY_EXIT_PATTERN_IN_JOINT_STATE_SL_TP`

- SUPPORTS_TRAIL_INVOLVEMENT_VS_BOTH_SL: trail_activated enrichment=0.5048 (JOINT=1.0000 vs BOTH_SL=0.4952)
- SUPPORTS_STOPPED_EARLIER_OPERATIONALIZATION: scanner_exit_before_oracle_tp among oracle-TP in JOINT_STATE_SL_TP=0.9551 (still not trail-causality proof)
- NO_TRAIL_ACTIVATED_ENRICHMENT_VS_BOTH_TP: both near-certain activation (JOINT=1.0000, BOTH_TP=1.0000) — trail_activated alone does not separate these states
- DIFFERENTIATES_VS_BOTH_TP_VIA_EXIT_TIMING: seb_otp JOINT=0.9551 vs BOTH_TP=0.0
- DIFFERENTIATES_VS_BOTH_TP_VIA_TRAIL_EXIT: trail_exit_rate JOINT=1.0000 vs BOTH_TP=0.0000

Caveats:
- scanner_exit_before_oracle_tp is a measured path-timing operationalization; not proof of trail causality alone
- detector stopped early remains INFERENCE unless exit timestamps prove scanner_exit_bar < oracle_tp_bar (this pass measures that inequality rate)
- trail_activated enrichment vs BOTH_SL supports trail-involvement candidate; both JOINT and BOTH_TP are fully trail-activated so activation alone does not separate them — exit timing / trail_exit does
- trail_activated enrichment is not causation of label mismatch alone

## D. LOIO stability (trail_activated within JOINT_STATE_SL_TP)

| holdout | n_JOINT_STATE_SL_TP | trail_activated_rate |
|---|---:|---:|
| holdout_BNBUSDT | 131,680 | 100.00% |
| holdout_BTCUSDT | 133,079 | 100.00% |
| holdout_ETHUSDT | 132,746 | 100.00% |
| holdout_SOLUSDT | 131,908 | 100.00% |

LOIO rate mean=100.00%, std=0.0, range=[1.0, 1.0].

## E. Per-instrument snapshot

- **BNBUSDT** n=139,942; JOINT_STATE_SL_TP n=44,791 (32.01%); trail_activated=100.00%; seb_otp=95.64%
- **BTCUSDT** n=139,942; JOINT_STATE_SL_TP n=43,392 (31.01%); trail_activated=100.00%; seb_otp=95.07%
- **ETHUSDT** n=139,942; JOINT_STATE_SL_TP n=43,725 (31.25%); trail_activated=100.00%; seb_otp=95.12%
- **SOLUSDT** n=139,942; JOINT_STATE_SL_TP n=44,563 (31.84%); trail_activated=100.00%; seb_otp=96.18%

## Flags

- `promotion`: False
- `l003_frozen`: False
- `attribution_unblocked`: False
- `economic_claims`: False
- `registry_edits`: False

## Reproducibility

- Script: `scripts/research/l003h_trail_exit_transition_replay.py`
- Commit: `d7c25f6e55616261b8b229b000875abd3bd315eb`
- Events (BNB CSV): `D:\Tradelatest\results\research\l003h_trail_exit_transitions\l003h_trail_exit_transitions_20260907_192115_BNBUSDT_events.csv`
- Runtime_s aggregate: {'per_instrument': {'BNBUSDT': 6.950013875961304, 'BTCUSDT': 6.89926290512085, 'ETHUSDT': 6.731527805328369, 'SOLUSDT': 6.88356614112854}, 'total': 35.97611737251282}

## Parent links

- L-003F: `docs/governance/ANALYTICS_JOINT_OUTCOME_STATES_L003F.md`
- L-003G: `docs/governance/ANALYTICS_JOINT_STATE_ENTRY_PREDICTABILITY_L003G.md`

## Follow-on: L-003I baseline direction

User review of L-003H noted missing baseline direction (P(JOINT|trail_*) vs P(trail|JOINT)). See `docs/governance/ANALYTICS_TRAIL_BASELINE_INVERSION_L003I.md` / `docs/governance/analytics_trail_baseline_inversion_l003i-2026-09-07.json` (run_id `l003i_trail_baseline_inversion_20260907_193404`, title BASELINE_DIRECTION_MEASURED). Lean not upgraded to causality.

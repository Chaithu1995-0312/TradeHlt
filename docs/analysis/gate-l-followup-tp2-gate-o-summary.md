# GATE-L Follow-up Summary — TP2 Repair + GATE-O (2026-07-22)

Research only. No production train/wire/promote.

## Phase A — TP2 root cause

**Cause:** BNBUSDT opportunity unit TP is **exactly 2R** for 100% of units. L1 policy
`SURROGATE_2R_BEFORE_SL` therefore ran an identical second walk → TP1≡TP2 (ρ≈0.9996).

Not a `forward_walk` bug. Full write-up:
[`docs/governance/tp2_label_repair_report.md`](../governance/tp2_label_repair_report.md).

**Repair:** protocol **`TN_ENV_CLEAN_L2`** · `STRETCH_3R_BEFORE_SL` · y_tp2 = hit **+3R** before SL.

## Phase B — Rebuild

| Field | L1 | L2 |
|-------|----|----|
| protocol_id | TN_ENV_CLEAN_L1 | **TN_ENV_CLEAN_L2** |
| n_clean | 139,942 | **139,942** |
| y_tp1 rate | 0.333 | **0.333** (unchanged) |
| y_tp2 rate | 0.333 | **0.241** |
| y_survives_be | 0.503 | **0.503** (unchanged) |
| ρ(tp1,tp2) | 0.9996 | **0.794** |
| P(tp2\|tp1) | ≈1.0 | **0.724** |
| P(tp1\|tp2) | ≈1.0 | **1.0** (nested stretch) |
| stream y_tp1 agree | 0.680 | **0.680** |
| protocol_hash | (L1) | `09beb486…0ec8` |
| dataset | …/20260721T221711Z | **…/20260721T223243Z** + LATEST |

Envelope labels unchanged by construction (only TP2 walk differs).

## Phase C — GATE-O nonlinear (HistGradientBoosting, time-CV, n=60k)

| Label | Nonlinear metric | Tag |
|-------|------------------|-----|
| y_tp1 | AUC **0.508** | NOISY |
| y_tp2 | AUC **0.518** | NOISY |
| y_survives_be | AUC **0.501** | NOISY |
| y_mfe_r | Spearman IC **0.164** | CANDIDATE_LEARNABLE |
| y_mae_r_heat | IC **0.160** | CANDIDATE_LEARNABLE |
| y_holding_bars | IC **0.268** | CANDIDATE_LEARNABLE |
| y_time_to_mfe | IC **0.187** | CANDIDATE_LEARNABLE |

Linear vs nonlinear: **negligible lift** on Bernoulli heads (~0.00–0.01 AUC).  
Prior Stage-4 conclusion stands and is strengthened under time-ordered CV.

In-sample regime AUCs for y_tp2 look higher (~0.62–0.66) but **do not survive** time CV → non-stationarity / overfit warning; do not promote.

## GO / NO-GO

| Surface | Verdict | Meaning |
|---------|---------|---------|
| **TradeNet outcome heads** | **NO_GO** | Do not train / shadow / wire Bernoulli TradeNet on this feature surface + population |
| **EnvelopeNet heads** | **GO_RESEARCH** | Offline multi-head train *eligible as research*; not production; no fusion/planner yet |
| Production / neural_fn / planner | **NO** | Unchanged |

## Architectural recommendations (revised)

1. **Pause TradeNet outcome modeling** until a new feature surface, population, or label ontology is justified — clean y exists and is still unpredictable OOS.
2. **Advance EnvelopeNet as the primary predictive research track** (excursion + risk + timing multi-head), using L2 labels.
3. Keep **y_R_net / timeout** diagnostic.
4. **Do not** treat in-sample regime AUC as GATE-O PASS.
5. Multi-instrument L2 rebuild recommended before any Envelope train charter.

## Artifacts

- Repair: `docs/governance/tp2_label_repair_report.md`
- L2 dataset: `results/clean_labels/BNBUSDT/LATEST`
- GATE-O: `docs/analysis/gate-o-nonlinear-BNBUSDT.LATEST.md`
- Probe: `scripts/research/gate_o_nonlinear_probe.py`

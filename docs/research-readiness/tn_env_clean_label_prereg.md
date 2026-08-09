# Preregistration — TN_ENV_CLEAN_L1 (TradeNet + EnvelopeNet clean labels)

| Field | Value |
|-------|--------|
| Protocol id | **`TN_ENV_CLEAN_L2`** (supersedes `TN_ENV_CLEAN_L1` for new work) |
| Created | 2026-07-22 |
| TP2 repair | [`docs/governance/tp2_label_repair_report.md`](../governance/tp2_label_repair_report.md) |
| Depends on | TN GATE-0 **FEASIBLE_GO** · ENV-0 **FEASIBLE_GO** · Phase A TP2 RCA |
| Authority | Research dataset only — **no** train promote, **no** `neural_fn`, **no** planner attach |
| Builder | `src/research/clean_labels/` · CLI `scripts/research/build_clean_labels_tn_env.py` |
| Machine freeze | `research.clean_labels.protocol.freeze_block()` |

## Freeze block (authoritative)

| Field | Frozen value |
|-------|----------------|
| Instruments (default pilot) | BNBUSDT (extend per-run via CLI) |
| Timeframe | M15 |
| Population unit | Opportunity entry row with entry/sl/tp + features (detection stream; re-labeled) |
| Feature surface | 38-dim `CANONICAL_FEATURES` / `SCHEMA_HASH` |
| PIT policy | `PIT_UNCLEAN_STORED_FEATURES` (F-051 era stored vectors; GATE-P forbidden) |
| Exit model | `forward_walk(..., exit_model="intrabar_fixed")` |
| Max forward | 40 bars |
| Cost | 12 bps RT → diagnostic `y_R_net` only |
| TP2 policy | **`STRETCH_3R_BEFORE_SL`** — no source `tp2`; walk TP=**+3R** (L1 2R collapsed: unit TP≡2R on BNB) |
| Composite weights | `(0.4, 0.4, 0.2)` under stretch y_tp2 definition |
| Min samples (train-eligible) | 500 clean units / instrument |
| Envelope labels | `y_mfe_r`, `y_mae_r_heat`, `y_holding_bars`, `y_time_to_mfe`, `y_time_to_1r`, `y_expired_timeout` via `horizon_excursion` + primary walk |

## Forbidden primary y

- Stream `outcome` / `rr_achieved`
- Stream `mfe` as sole `survives_be`

Stream fields may appear only under `diagnostics` / `label_rederive_report`.

## GATE-L PASS criteria (dataset)

See `TN_QUAL_V1` §4.5 + `dataset_meta.json` → `gate_l_checklist`.  
This prereg freezes identity; a concrete run **PASSes** when `train_eligible=true` and artifacts exist under `results/clean_labels/<instrument>/<run_id>/`.

## Non-goals

- Offline KEEP/RETIRE (GATE-O)
- Shadow weight (GATE-S)
- Spine wire (GATE-P)
- Envelope fusion/planner consumption (ENV-P)

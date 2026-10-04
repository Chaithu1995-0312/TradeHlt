# Charter — Envelope Offline Train (narrow)

| Field | Value |
|-------|--------|
| Charter id | **`ENV_OFFLINE_TRAIN_V1`** |
| Created | 2026-07-22 |
| Status | **ACTIVE (research)** · first BNBUSDT run **TRAIN_COMPLETE / SIGNAL_RETAINED** 2026-07-22 |
| Depends on | `TN_ENV_CLEAN_L2` · GATE-O **GO_RESEARCH** ([gate-o-nonlinear-BNBUSDT.LATEST.md](../analysis/gate-o-nonlinear-BNBUSDT.LATEST.md)) |
| Design parent | [`ENV_ARCH_V1`](../architecture/envelope-layer-design.md) |
| Authority | **Research offline train only** — no production, no registry, no spine, no planner, no fusion |

---

## 1. Why this charter exists

GATE-O found continuous envelope targets **rank-learnable** (Spearman IC ≈ 0.16–0.27) while TradeNet Bernoulli heads remained **NOISY** (AUC ≈ 0.50).  

This charter authorizes a **single, narrow offline training run family** so EnvelopeNet can produce research artifacts under a frozen scope — without smuggling production authority.

---

## 2. In scope (frozen)

| Item | Freeze |
|------|--------|
| Label protocol | **`TN_ENV_CLEAN_L2` only** (refuse L1 / other hashes) |
| Instrument | **BNBUSDT** (this charter version; multi-inst = new charter) |
| Feature surface | 38-dim `CANONICAL_FEATURES` / `feature_vector` at decision time |
| PIT stamp | Inherit dataset `pit_status` (`PIT_UNCLEAN_STORED_FEATURES`) — **GATE-P still forbidden** |
| Heads (train) | `y_mfe_r`, `y_mae_r_heat`, `y_holding_bars`, `y_time_to_mfe` |
| Heads (explicitly out) | All TradeNet Bernoulli · `y_R_net` · timeout · path_* twins · reached_* flags |
| Model class | Independent `HistGradientBoostingRegressor` **per head** (sklearn) |
| Hyperparams (v1 fixed) | `max_depth=6`, `max_iter=100`, `learning_rate=0.08`, `min_samples_leaf=40`, `l2_regularization=0.0`, `random_state=42` |
| Split | Time-ordered by `entry_index`: **60% train / 20% val / 20% test** (contiguous) |
| Primary metrics (test) | Spearman IC · RMSE · R² (report all; **IC is primary rank quality**) |
| Secondary | Val IC (overfit check: test_IC − val_IC) · per-side IC long/short |
| Artifacts | `results/envelope_offline/BNBUSDT/<run_id>/` only — **not** `models/` registries |
| Entry point | `scripts/research/train_envelope_offline.py` |

### Multi-head packaging

One run produces four head models + one `envelope_bundle.json` metadata file:

```text
heads:
  mfe_r:      joblib artifact
  mae_r_heat: joblib artifact
  holding_bars: joblib artifact
  time_to_mfe: joblib artifact
bundle: charter_id, protocol_hash, schema_hash, metrics, split, seed
```

Inference helper (research): `predict_envelope(features) -> dict` — **not** imported by EngineRunner.

---

## 3. Out of scope (hard bans)

| Forbidden | Why |
|-----------|-----|
| TradeNet / outcome heads | GATE-O **NO_GO** |
| `models/*_registry.json` promote | No GOV-3 path |
| `active_models.yaml` activation | No production identity |
| `neural_fn` / Fusion / Planner / Ultron | No spine consumption |
| Production config keys | No config-first activation |
| Changing clean-label protocol mid-charter | L2 frozen; L3 = new charter |
| Claiming ΔG001 / economic edge | Rank IC ≠ expectancy |
| Multi-instrument in v1 | Scope creep |

---

## 4. Pass / fail (charter completion — not production KEEP)

| Token | Meaning |
|-------|---------|
| **TRAIN_COMPLETE** | All four heads fit; test metrics written; bundle hash recorded |
| **SIGNAL_RETAINED** | Every head test Spearman IC **> 0.10** (floor from GATE-O lower bound) |
| **SIGNAL_WEAK** | Some heads IC ∈ (0, 0.10] — retain artifacts; demote weak heads to diagnostic in write-up |
| **SIGNAL_FAIL** | Any head test IC ≤ 0 **or** catastrophic overfit (val_IC − test_IC > 0.15 with test_IC < 0.05) |
| **PRODUCTION_KEEP** | **Not available under this charter** |

Charter run is successful if `TRAIN_COMPLETE` holds.  
`SIGNAL_RETAINED` vs `SIGNAL_WEAK` guides whether a **future** ENV train charter expands or stops.

---

## 5. What success does *not* unlock

Even `SIGNAL_RETAINED`:

- does **not** set ENV-S / ENV-P  
- does **not** attach envelope to Fusion coherence or planner TTL  
- does **not** reopen TradeNet outcome training  

Next program: multi-instrument replication, or **shadow weight-0** — charter
[`envelope_shadow_weight0_charter.md`](envelope_shadow_weight0_charter.md) (`ENV_SHADOW_W0_V1`, first BNB run complete).

---

## 6. Risks

| Risk | Handling |
|------|----------|
| PIT_UNCLEAN features | Declared; no production path |
| MFE/MAE distributional symmetry | Train both; report if predictions nearly anti-correlated |
| Holding vs MFE independence | Expected — separate heads required |
| Overfit time structure | Contiguous time split; report val vs test IC gap |
| Negative R² with positive IC | Allowed — primary metric is rank IC (GATE-O pattern) |

---

## 7. Implementation map

| Piece | Path |
|-------|------|
| Charter (this file) | `docs/research-readiness/envelope_offline_train_charter.md` |
| Train logic | `src/research/envelope_offline/train.py` |
| CLI | `scripts/research/train_envelope_offline.py` |
| Output root | `results/envelope_offline/` |

---

## 8. Confirmation block

```text
CHARTER_ID                 = ENV_OFFLINE_TRAIN_V1
LABEL_PROTOCOL             = TN_ENV_CLEAN_L2
INSTRUMENT                 = BNBUSDT
HEADS                      = y_mfe_r, y_mae_r_heat, y_holding_bars, y_time_to_mfe
PRODUCTION_AUTHORITY       = NONE
SPINE_WIRE                 = FORBIDDEN
REGISTRY_PROMOTE           = FORBIDDEN
TRADENET_OUTCOME_TRAIN     = FORBIDDEN
```

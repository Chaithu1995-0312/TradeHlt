# Charter — Envelope Shadow Weight-0 Logging

| Field | Value |
|-------|--------|
| Charter id | **`ENV_SHADOW_W0_V1`** |
| Created | 2026-07-22 |
| Status | **ACTIVE (research)** · first BNBUSDT run **SHADOW_COMPLETE** 2026-07-22 (n=139,942) |
| Depends on | `ENV_OFFLINE_TRAIN_V1` **SIGNAL_RETAINED** · `TN_ENV_CLEAN_L2` |
| Design parent | [`ENV_ARCH_V1`](../architecture/envelope-layer-design.md) · offline charter |
| Authority | **Observe-only logging** — decision weight **exactly 0** |

---

## 1. Purpose

Emit Envelope multi-head predictions as an **append-only shadow stream** so research can:

- inspect score distributions in the wild (batch over clean-label population),
- track calibration vs clean y without re-training,
- prepare evidence for a *future* weight>0 / planner charter,

**without** any path that can change trade admission, size, TTL, or levels.

This is the Envelope analogue of TradeNet GATE-S “score only; zero decision weight” — scoped narrower (batch/research runner, not live spine).

---

## 2. In scope (frozen)

| Item | Freeze |
|------|--------|
| Model source | One `ENV_OFFLINE_TRAIN_V1` bundle under `results/envelope_offline/<inst>/` (LATEST or explicit path) |
| Bundle gate | Refuse if `signal_rollup` ∉ {`SIGNAL_RETAINED`, `SIGNAL_WEAK`} or missing heads |
| Population (v1) | **Batch only**: rows from `TN_ENV_CLEAN_L2` `clean_labels.jsonl` (same unit_id / features) |
| Instrument | **BNBUSDT** (multi-inst = new charter) |
| Heads logged | `mfe_r`, `mae_r_heat`, `holding_bars`, `time_to_mfe` predictions |
| Decision weight | **`decision_weight: 0.0`** hard-coded on every line |
| Fusion / planner fields | **`fusion_weight: 0.0`**, **`planner_influence: false`**, **`spine_consumed: false`** |
| Log format | JSONL append-only |
| Log root | `results/envelope_shadow/<instrument>/<run_id>/` |
| Entry point | `scripts/research/run_envelope_shadow_weight0.py` |
| Optional summary | Spearman IC / error vs clean y on the logged population (diagnostic) |

### Shadow line schema (minimum)

```text
{
  "kind": "envelope_shadow_w0",
  "charter_id": "ENV_SHADOW_W0_V1",
  "train_charter_id": "ENV_OFFLINE_TRAIN_V1",
  "protocol_id": "TN_ENV_CLEAN_L2",
  "instrument": "BNBUSDT",
  "unit_id": "...",
  "decision_ts": "...",
  "entry_index": int,
  "side": "long|short",
  "pred": { "mfe_r", "mae_r_heat", "holding_bars", "time_to_mfe" },
  "actual": { ... } | null,          // if clean y present
  "decision_weight": 0.0,
  "fusion_weight": 0.0,
  "planner_influence": false,
  "spine_consumed": false,
  "bundle_dir": "...",
  "bundle_dataset_protocol_hash": "..."
}
```

---

## 3. Out of scope (hard bans)

| Forbidden | Why |
|-----------|-----|
| Import from / call by `EngineRunner`, `FusionEngine`, `DecisionEngine`, `ExecutionPlanner`, `UltronRiskGate` | Would risk non-zero influence |
| Live MT5 / control-plane hot path | Out of charter v1 |
| `decision_weight > 0` | Violates weight-0 |
| Using shadow scores to filter dataset rows for promotion | Authority smuggling |
| Registry / `active_models` enablement | Production identity |
| TradeNet outcome scoring in this stream | Separate NO_GO track |
| Economic ΔG001 claims from shadow alone | Log ≠ edge |

---

## 4. Pass / fail (charter completion)

| Token | Meaning |
|-------|---------|
| **SHADOW_COMPLETE** | Shadow JSONL written; every line has `decision_weight==0`; summary JSON written |
| **SHADOW_CALIBRATION_OK** | Optional: all four heads Spearman(pred, actual) > 0 on logged set (sanity, not GATE-O redo) |
| **SHADOW_FAIL** | Bundle missing/invalid, or any line without weight-0 fields, or spine import detected in module graph (manual) |
| **WEIGHT_POSITIVE / SPINE_ATTACH** | **Not available** under this charter |

---

## 5. What success does *not* unlock

`SHADOW_COMPLETE` does **not** authorize:

- Fusion coherence channel  
- Planner TTL/TP/SL rewrite  
- ENV-P or production promote  
- Reopening TradeNet outcome training  

Next program would be a **separate** charter (e.g. multi-inst shadow, or explicit weight>0 experiment with measured ΔG001 gates).

---

## 6. Risks

| Risk | Handling |
|------|----------|
| Bundle path drift | Pin `bundle_dir` + train `dataset_protocol_hash` on every line |
| Train/serve skew | Shadow uses same 38-vector as train rows from L2 file |
| Accidental consumer | No public export from `src/core/`; research package only |
| Log volume | Allow `--max-rows`; full BNB ~140k lines OK for research disk |

---

## 7. Implementation map

| Piece | Path |
|-------|------|
| Charter (this file) | `docs/research-readiness/envelope_shadow_weight0_charter.md` |
| Shadow logic | `src/research/envelope_offline/shadow.py` |
| CLI | `scripts/research/run_envelope_shadow_weight0.py` |
| Output root | `results/envelope_shadow/` |

---

## 8. Confirmation block

```text
CHARTER_ID                 = ENV_SHADOW_W0_V1
TRAIN_BUNDLE               = ENV_OFFLINE_TRAIN_V1 (SIGNAL_RETAINED|WEAK)
LABEL_PROTOCOL             = TN_ENV_CLEAN_L2
DECISION_WEIGHT            = 0.0   # hard
FUSION_WEIGHT              = 0.0   # hard
PLANNER_INFLUENCE          = false # hard
SPINE_CONSUMED             = false # hard
PRODUCTION_AUTHORITY       = NONE
```

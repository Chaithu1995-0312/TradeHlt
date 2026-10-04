> Created: 2026-06-04 · Updated: 2026-06-04 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# TradeNet v2 — 3-Head Survival Classifier

> **Status: KILLED (2026-06-03) — superseded by the Funding Ledger in [`docs/current-findings.md`](../current-findings.md) (TradeNet V2 = KILLED; evidence F-001, F-005).** Retained for replay, **not** active work. Reopen only if the Phase-0 economic-edge gate clears **and** wiring TradeNet v1 into the fusion slot earns measured weight (weight-0.0 A/B lift) — and a SESSION LOG entry is filed per `CLAUDE.md §6.2`.

## Context

The current TradeNet is a single-sigmoid binary win/loss classifier. A trade that hits TP1 then gets stopped at breakeven is labeled "LOSS" — same as a trade that never reached 1R. The binary label conflates three distinct survival outcomes and gives the fusion engine a coarse signal.

This patch replaces the output head with three independent sigmoid heads (`p_tp1`, `p_tp2`, `p_survives_be`) on the existing 38-dim canonical feature vector, packages weights in a JSON envelope (mirroring the BitNet `model_contract` pattern), and registers per instrument under an `__active__` map (mirroring the Gaussian versioning pattern that just landed). The composite TradeNet score consumed by `FusionEngine.neural` becomes `0.4·p_tp1 + 0.4·p_tp2 + 0.2·p_survives_be`.

### Premise corrections vs. the original brief (locked-in)

- **v1 is already 38-dim, not 6-dim.** Input layer unchanged. No "6-feature bottleneck" — that was a misread.
- **Strategy one-hot flags dropped from this patch.** `active_strategies` is not emitted upstream; deferring to a follow-up.
- **`SL-BE` is not an exit_reason in the codebase** ([src/runtime/backtest_v2.py:803](src/runtime/backtest_v2.py)). `survives_be` is synthesized from the `mfe` field in `opportunities_*.jsonl` (confirmed key, value in price units): `survives_be = 1 iff mfe >= 1R` where `1R = abs(entry - sl)`.
- **v1 stores `.pth` PyTorch state_dicts, not JSON envelopes** ([src/training/trainer.py:589-609](src/training/trainer.py)). Legacy bridge handles `.pth` loading explicitly.
- **`min_samples = 500`** (reuses `training_trigger.min_new_samples`), counted on closed records only (exit_reason ∉ {"OPEN", ""}).
- **No `fusion_engine.py` change required.** The composite is computed inside the inference class; the wrapper at [src/training/trainer.py:803-841](src/training/trainer.py) still returns a single float through `FusionEngine.neural`. This is contrary to the brief's "one formula change" — but the brief's goal is achieved without touching fusion_engine.

## Files modified / created

### New
- **`src/training/trade_net_v2.py`** — pure-numpy `TradeNetV2` inference class. JSON envelope loader, 3-head forward pass, MFE-based composite. Legacy `.pth` bridge with `TRADENET_LEGACY_LOAD` integrity event (CRITICAL). Returns `None` when no model for instrument, emits `TRADENET_MISSING` (CRITICAL).
- **`scripts/training/train_trade_net_v2.py`** — PyTorch training script. Reads via existing `TradeDataset.from_opportunities()` ([scripts/training/phase5_calibration.py:382-460](scripts/training/phase5_calibration.py)). Extracts 3-label tensor. Trains 38→32→16→[3 heads] with 3 independent BCE terms. Exports JSON envelope. Registers + promotes via per-instrument registry. `--shadow` skips promotion.

### Modified
- **`src/core/model_registry.py`** — extend the `TradeNetRegistry` portion (already has `register_tradenet` at line 1278). Add `__active__` map migration (mirror Gaussian, lines [350-380](src/core/model_registry.py)). Replace single-active `promote(version)` with `promote(version, *, instrument=None, force=False, max_regression=0.01) -> (bool, str)`. Convenience wrappers at [1285-1298](src/core/model_registry.py) updated. `_default` bucket fallback for entries without instrument tag.
- **`src/training/trainer.py:803-841`** — `make_neural_fn` updated to detect v2 envelope vs. v1 `.pth` and route appropriately. For v2: instantiate `TradeNetV2`, call `predict(features)`, return `tradenet_score` (the composite). For v1: unchanged path. The wrapper signature stays `Callable[[dict], float]`, preserving the FusionEngine contract.
- **`models/tradenet_registry.json`** — schema-extended with `__active__` map; existing per-version entries (with `active: bool`) remain valid via legacy fallback scan.

### Unchanged (verified)
- `src/core/fusion_engine.py` — no change. The `evaluate()` path at [lines 583-606](src/core/fusion_engine.py) already handles `n_score=None` by renormalizing to gaussian-only. The `compute()` 4-engine path doesn't consume TradeNet directly.
- `src/runtime/backtest_v2.py` `TradeRecord` — no change.
- BitNet `model_contract.py` — referenced as the envelope pattern but not imported (mirror, don't depend).
- `configs/production/v1_multi_2026_03.json` — `training_trigger.min_new_samples = 500` reused; no new key.

## Architecture

### v2 net topology (PyTorch, training side)
```
Input         : 38-dim canonical feature vector (no strategy flags in this patch)
Shared trunk  : Linear(38, 32) → ReLU → Dropout(0.2) → Linear(32, 16) → ReLU
Heads (×3)    : Linear(16, 1) → Sigmoid     (one each for p_tp1, p_tp2, p_survives_be)
Loss          : sum of 3 BCELoss(reduction='none') terms, each with per-head class-balanced
                pos_weight = n_neg / n_pos (matches v1 imbalance handling pattern at trainer.py:651-661)
```

### JSON envelope schema (mirroring BitNet `model_contract.py`)
```json
{
  "schema_version":     "tradenet_v2",
  "feature_dim":        38,
  "feature_order_hash": "<sha256[:16] of CANONICAL_FEATURES list>",
  "feature_names":      [...38 names...],
  "trunk": [
    {"type": "linear", "in": 38, "out": 32, "weight": [[...]], "bias": [...]},
    {"type": "relu"},
    {"type": "linear", "in": 32, "out": 16, "weight": [[...]], "bias": [...]},
    {"type": "relu"}
  ],
  "heads": {
    "p_tp1":         {"weight": [[...]], "bias": [...]},
    "p_tp2":         {"weight": [[...]], "bias": [...]},
    "p_survives_be": {"weight": [[...]], "bias": [...]}
  },
  "scaler": {"mean": [...38...], "std": [...38...]},
  "metadata": {
    "instrument": "ETHUSDT",
    "trained_at": "2026-05-21T...Z",
    "n_samples_closed": 1234,
    "n_samples_total": 1500,
    "epochs": 100,
    "class_balance": {"p_tp1": [n_neg, n_pos], "p_tp2": [...], "p_survives_be": [...]},
    "metrics": {"auc_p_tp1": 0.71, "auc_p_tp2": 0.68, "auc_p_survives_be": 0.65}
  }
}
```

### Label extraction (revised vs. brief — `SL-BE` does not exist)
Per record (from `TradeDataset` or `opportunities_*.jsonl`):
```python
exit_reason = rec.get("outcome") or rec.get("exit_reason") or ""
mfe         = float(rec.get("mfe", 0.0))
entry, sl   = float(rec["entry"]), float(rec["sl"])
one_r       = abs(entry - sl)

reaches_tp1   = 1 if exit_reason in ("TP1", "TP2", "TP1_HIT", "TP2_HIT") else 0
reaches_tp2   = 1 if exit_reason in ("TP2", "TP2_HIT") else 0
survives_be   = 1 if (one_r > 0 and mfe >= one_r) else 0   # MFE proxy

# Missing-MFE fallback: emit TRADENET_SURVIVES_BE_UNRESOLVED (INFO), label as 0.
if "mfe" not in rec:
    emit_integrity_event("TRADENET_SURVIVES_BE_UNRESOLVED", "INFO",
                         "trade_net_v2", {"trade_id": rec.get("trade_id")})
```

Note: with MFE-rule, TP1 outcomes will typically have `survives_be=1` (since TP1 is at ≥1R), which differs from the brief's table — but the brief's table was rooted in non-existent SL-BE semantics. The MFE rule is the defensible derivable label.

### Composite score (inside `TradeNetV2.predict`)
```python
def predict(self, features: dict) -> dict:
    vec    = extract_feature_vector(features)              # 38-dim
    vec    = (vec - self.mean) / self.std                  # numpy scaler
    h      = relu(vec @ W1 + b1)                           # 38→32
    h      = relu(h @ W2 + b2)                             # 32→16 (no dropout at inference)
    p_tp1  = sigmoid(h @ W_tp1 + b_tp1)
    p_tp2  = sigmoid(h @ W_tp2 + b_tp2)
    p_be   = sigmoid(h @ W_be  + b_be)
    score  = 0.4*p_tp1 + 0.4*p_tp2 + 0.2*p_be
    return {"tradenet_score": float(score),
            "p_tp1": float(p_tp1), "p_tp2": float(p_tp2),
            "p_survives_be": float(p_be),
            "schema_version": "tradenet_v2"}
```

### Per-instrument registry (mirror Gaussian exactly)
- `models/tradenet_registry.json` gains an `__active__: {INSTRUMENT: version}` meta key on first migration ([model_registry.py:350-380](src/core/model_registry.py) is the Gaussian template — copy structurally).
- `TradeNetRegistry.promote(version, *, instrument=None, force=False, max_regression=0.01) -> (bool, str)`:
  - In-process `threading.RLock`; cross-process `.lock` file via `O_CREAT|O_EXCL`.
  - Resolves instrument from explicit arg → entry's `instrument` field → `_default`.
  - Reads current active from `__active__[instrument]`; falls back to entry-level `active=true` scan with matching `instrument` for pre-migration registries.
  - Deactivates current for THIS instrument only; activates new; updates `__active__[instrument]`.
  - Atomic write via `.tmp` + `os.replace`.
  - GOV-3 single-active-per-instrument guard.
  - Regression guard: blocks if `new_auc_p_tp1 < cur_auc_p_tp1 - max_regression` unless `force=True` (TradeNet uses AUC of `p_tp1` as the primary metric — mirroring Gaussian's `corr_expected_rr` role).

### Legacy `.pth` bridge
`TradeNetV2.__init__(model_path: str | Path, instrument: Optional[str] = None)`:
1. Resolves model path from registry (`__active__[instrument]` → entry → `model_file`).
2. If extension is `.pth` OR loaded JSON lacks `schema_version == "tradenet_v2"`:
   - Emit `TRADENET_LEGACY_LOAD` at **CRITICAL** severity (per user direction: creates operator pressure).
   - Lazy-import torch, load state_dict, build v1 model (38→32→16→1).
   - `predict()` returns `{"tradenet_score": float, "p_tp1": None, "p_tp2": None, "p_survives_be": None, "schema_version": "legacy_v1"}`.
3. If no model for instrument at all (no entry, no `_default`):
   - Emit `TRADENET_MISSING` at **CRITICAL**.
   - `predict()` returns `None`. Existing fusion logic at [fusion_engine.py:599-606](src/core/fusion_engine.py) already handles None by falling back to gaussian-only.

### Training script — minimum-sample gate
```python
closed = [r for r in dataset.trades if r.get("exit_reason", r.get("outcome", "")) not in ("OPEN", "")]
if len(closed) < int(config["training"]["training_trigger"]["min_new_samples"]):  # = 500
    emit_integrity_event("TRADENET_INSUFFICIENT_DATA", "WARNING", "train_trade_net_v2",
                         {"instrument": args.instrument, "n_closed": len(closed), "floor": 500})
    sys.exit(0)
```

### `--shadow` mode (optional, deferrable)
- After training + registering, do NOT promote.
- Iterate the next session's `opportunities_*.jsonl` writes (or replay a recent slice), call v1 + v2 in parallel, append per-trade `{ts, instrument, trade_id, v1_score, v2_composite, v2_p_tp1, v2_p_tp2, v2_p_survives_be, outcome}` to `logs/tradenet_shadow.jsonl` (new file; format mirrors `logs/opportunities_*.jsonl`).
- Compute Spearman rank correlation `p_tp1` vs. `reaches_tp1` across the slice; promote only if correlation > 0 and not worse than v1's `tradenet_score` vs. `outcome` correlation.

## Reuse map (functions/utilities to lean on)

| Existing | Location | Used for |
| --- | --- | --- |
| `extract_feature_vector` | [src/features/dataset_builder.py:38-98](src/features/dataset_builder.py) | Both training-time matrix build and inference-time vector extraction |
| `CANONICAL_FEATURES`, `CANONICAL_FEATURE_DIM` | [src/features/feature_schema.py:46-67](src/features/feature_schema.py) | Feature order canonicalization + envelope hash |
| `StandardScaler` | [src/training/trainer.py](src/training/trainer.py) (existing class with `from_dict` / `to_dict`) | Scaler serialization compatibility with v1 |
| `register_tradenet` | [src/core/model_registry.py:1278](src/core/model_registry.py) | Already accepts `instrument=`; reuse as-is |
| `TradeDataset.from_opportunities` | [scripts/training/phase5_calibration.py:382-460](scripts/training/phase5_calibration.py) | Primary data source (carries `mfe`) |
| `emit_integrity_event` | [src/utils/integrity_events.py:50-96](src/utils/integrity_events.py) | All integrity events (`TRADENET_LEGACY_LOAD`, `TRADENET_MISSING`, `TRADENET_SURVIVES_BE_UNRESOLVED`, `TRADENET_INSUFFICIENT_DATA`) |
| Gaussian promotion mechanics | [src/core/model_registry.py:463-619](src/core/model_registry.py) | Structural template for `TradeNetRegistry.promote` |
| `BitNet build_envelope` shape | [src/bitnet/model_contract.py:59-90](src/bitnet/model_contract.py) | Envelope-shape mirror (do not import) |

## Verification

### Unit-level (the brief's commands, corrected for the locked-in decisions)
```bash
# 1 — label extraction correctness (MFE-based, not exit_reason-only)
python -c "
from scripts.training.train_trade_net_v2 import extract_labels
cases = [
    {'exit_reason': 'TP2', 'mfe': 100.0, 'entry': 100.0, 'sl': 99.0},      # 1R=1.0, mfe=100 → be=1
    {'exit_reason': 'TP1', 'mfe': 2.0,   'entry': 100.0, 'sl': 99.0},      # 1R=1.0, mfe=2   → be=1
    {'exit_reason': 'SL',  'mfe': 0.3,   'entry': 100.0, 'sl': 99.0},      # 1R=1.0, mfe=0.3 → be=0
    {'exit_reason': 'SL',  'mfe': 1.5,   'entry': 100.0, 'sl': 99.0},      # mfe>1R reaches BE → be=1
    {'exit_reason': 'TIMEOUT', 'mfe': 0.5, 'entry': 100.0, 'sl': 99.0},
]
labels = extract_labels(cases)
assert labels[0].tolist() == [1, 1, 1]   # TP2
assert labels[1].tolist() == [1, 0, 1]   # TP1 + mfe>=1R
assert labels[2].tolist() == [0, 0, 0]   # SL without reaching 1R
assert labels[3].tolist() == [0, 0, 1]   # SL but reached 1R first
assert labels[4].tolist() == [0, 0, 0]   # TIMEOUT short of 1R
print('PASS')
"

# 2 — input matrix shape correct (38, not 43)
python -c "
from scripts.training.train_trade_net_v2 import build_input_matrix, INPUT_DIM
recs = [{'features': {k: 0.0 for k in __import__('features.feature_schema').feature_schema.CANONICAL_FEATURES}} ] * 10
X = build_input_matrix(recs)
assert X.shape == (10, 38), X.shape
print('PASS', X.shape)
"

# 3 — legacy .pth bridge loads, emits CRITICAL event, returns single-score result
python -c "
from src.training.trade_net_v2 import TradeNetV2
m = TradeNetV2('models/<existing v1 .pth path>', instrument='ETHUSDT')
out = m.predict({k: 0.0 for k in __import__('features.feature_schema').feature_schema.CANONICAL_FEATURES})
assert out['schema_version'] == 'legacy_v1'
assert out['p_tp1'] is None and out['p_tp2'] is None and out['p_survives_be'] is None
assert 0.0 <= out['tradenet_score'] <= 1.0
print('PASS')
"

# 4 — per-instrument isolation: promoting ETHUSDT does not deactivate EURUSD
python -c "
from src.core.model_registry import TradeNetRegistry
r = TradeNetRegistry()
# register fake v_eth + v_eur; promote each independently; assert __active__ entries don't collide
"

# 5 — short backtest with v1 still active, confirm no regression on ETHUSDT
python scripts/backtest/run_backtest.py --instrument ETHUSDT --bars 500
```

### Integration
- Run `python -m pytest tests/test_gaussian_update_pipeline.py -q` as the template — write equivalent `tests/test_tradenet_v2_pipeline.py`: registration, promotion blocking on regression, GOV-3 single-active guard per instrument, atomic write under concurrent processes.
- After v2 promotion for one instrument, confirm `FusionEngine.evaluate()` continues to return non-None `neural` score and that the composite is in `[0, 1]`.

### Promotion sequence
```
ETHUSDT:  train → (optional --shadow) → promote
EURUSD:   train → (optional --shadow) → promote
XAUUSD:   train → (optional --shadow) → promote
```
Per-instrument independence is provided by the `__active__` map; failed promotion on one instrument does not affect others.

### Rollback
`promote_tradenet(prior_version, instrument=INSTR, force=True)` — same as Gaussian rollback. Prior versions remain in the registry; no archive needed (versioned-never-overwrite pattern, matches RR / ZoneGate).

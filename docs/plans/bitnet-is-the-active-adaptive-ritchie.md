> Created: 2026-06-04 · Updated: 2026-06-04 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# BitNet Adaptive Threshold

> **Status: FROZEN (2026-06-03) — per the Funding Ledger in [`docs/current-findings.md`](../current-findings.md) (BitNet V2 adaptive threshold = FROZEN; evidence F-004).** The BitNet v1 gate is live at the hardcoded `0.55` (`crt_engine_v2.py:1800`); the adaptive infrastructure is unused. Retained for replay, **not** active work. Reopen only when enough `bitnet_score_at_entry` outcomes accrue to fit per-instrument/per-regime thresholds **and** the adaptive threshold beats the static gate on net rr — plus a SESSION LOG entry per `CLAUDE.md §6.2`.

## Context

`BitNetRunner` uses a hardcoded `0.5` threshold at `src/bitnet/bitnet_runner.py:130`. No per-instrument adaptation, no config key, no learning from outcomes. Additionally, `bitnet_score_at_entry` is not persisted on `TradeRecord` — verified against `src/runtime/backtest_v2.py:200` and the actual CSV header at `results/portfolio_raw/EURUSD/run_20260511_011915_EURUSD/EURUSD_trades.csv` (70 columns, zero `bitnet_*`).

This patch has three sequential parts:
1. Wire `bitnet_score_at_entry` onto `TradeRecord` so closed trades carry the score that led to their approval.
2. Replace the hardcoded threshold with a per-instrument per-regime lookup, sourced from a managed JSON file.
3. Build a threshold adapter that fits against the accumulated labelled history and writes calibrated thresholds back.

**Dependency order — do not skip steps.** Steps 1 and 2 can ship together. Step 3 requires N closed trades with `bitnet_score_at_entry` populated — run at least one full backtest after Steps 1+2 before implementing Step 3.

---

## Step 1 — Wire `bitnet_score_at_entry` onto TradeRecord

**Files:** `src/runtime/backtest_v2.py`, `src/runtime/live_engine_hook.py`

**`src/runtime/backtest_v2.py:200` — add two fields to `TradeRecord` dataclass:**

```python
bitnet_score_at_entry:    float = 0.0   # BitNet confidence score at approval time
bitnet_decision_at_entry: str   = ""    # "ACCEPT" | "REJECT" | "" (not evaluated)
```

Both fields default to safe values — old records without them load cleanly via the existing `from_dict` filtering pattern.

**Populate at approval time** — find the site in `BacktestRunner` where `BitNetRunner.predict()` is called (or `bitnet_score()` helper at `src/config_layer/crt_engine_v2.py:1030,1096`). At that call site, capture the result dict and write both fields into the `TradeRecord` before it is appended to the trade list:

```python
bitnet_result = bitnet_runner.predict(features)
trade.bitnet_score_at_entry    = bitnet_result.get("score", 0.0)
trade.bitnet_decision_at_entry = bitnet_result.get("decision", "")
```

**Confirm the CSV export** includes both new columns — `BacktestRunner` writes `TradeRecord` fields to CSV. The two new fields should appear automatically if the CSV writer uses `dataclasses.asdict()`. Verify the column appears in `*_trades.csv` after the first post-patch backtest run.

**Live path:** `src/runtime/live_engine_hook.py` — same pattern. At the point where the live engine calls BitNet for an approval decision, attach both fields to the alert payload (same shape as the `features` snapshot wiring from Fix 4).

---

## Step 2 — Replace hardcoded threshold with per-instrument per-regime lookup

**Files:** `src/bitnet/bitnet_runner.py`, `src/bitnet/bitnet_thresholds.json` (new), both prod configs

**`src/bitnet/bitnet_runner.py` — extend constructor and threshold lookup:**

Constructor currently takes only `model_path`. Extend:

```python
def __init__(
    self,
    model_path: str | Path,
    *,
    instrument: str = "UNKNOWN",
    config:     dict | None = None,
):
    # ... existing model load ...
    self._instrument  = instrument
    self._config      = config or {}
    self._thresholds  = self._load_thresholds()
```

Add `_load_thresholds()`:

```python
def _load_thresholds(self) -> dict:
    """Load per-instrument per-regime thresholds from bitnet_thresholds.json.
    Falls back to hardcoded 0.5 per instrument if file absent or parse fails."""
    path = Path(self._config.get(
        "bitnet_thresholds_path",
        "src/bitnet/bitnet_thresholds.json"
    ))
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        from src.utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "BITNET_THRESHOLD_LOAD_FAILED", "WARNING", "bitnet_runner",
            {"path": str(path), "error": str(exc),
             "fallback": "hardcoded 0.5 for all instruments"}
        )
        return {}
```

Add `_threshold_for(regime)`:

```python
def _threshold_for(self, regime: str = "UNKNOWN") -> float:
    """Per-instrument per-regime threshold with fallback chain:
       instrument+regime → instrument+UNKNOWN → global → 0.5"""
    inst_block = self._thresholds.get(self._instrument, {})
    # Try exact regime match
    val = inst_block.get(regime.upper())
    if val is not None:
        return float(val)
    # Try instrument-level default
    val = inst_block.get("DEFAULT")
    if val is not None:
        return float(val)
    # Global default
    val = self._thresholds.get("__default__")
    if val is not None:
        return float(val)
    # Hardcoded floor — never silent
    return 0.5
```

**Replace `src/bitnet/bitnet_runner.py:130`:**

```python
# Before:
decision = "ACCEPT" if score > 0.5 else "REJECT"

# After:
regime    = features.get("_regime", "UNKNOWN")   # injected by caller if available
threshold = self._threshold_for(regime)
decision  = "ACCEPT" if score > threshold else "REJECT"
```

Note: `features.get("_regime")` — the `_` prefix marks it as metadata, not a canonical feature. It is not in `CANONICAL_FEATURES` and is stripped before the feature vector is assembled. The caller injects it alongside the feature dict. If absent, fallback is `"UNKNOWN"` → uses the instrument-level DEFAULT threshold.

**`src/bitnet/bitnet_thresholds.json` — initial file:**

```json
{
    "__default__": 0.5,
    "__schema_version__": "bitnet_thresholds_v1",
    "__note__": "Per-instrument per-regime acceptance thresholds. Managed by BitNetThresholdAdapter.",
    "ETHUSDT": {
        "DEFAULT":  0.5,
        "TRENDING": 0.5,
        "RANGING":  0.5,
        "UNKNOWN":  0.5
    },
    "EURUSD": {
        "DEFAULT":  0.5,
        "TRENDING": 0.5,
        "RANGING":  0.5,
        "UNKNOWN":  0.5
    }
}
```

All values start at `0.5` — identical to current hardcoded behaviour. Zero behavioural change until the adapter calibrates them. This is deliberate.

**Add to both prod configs under `bitnet` section:**

```json
"bitnet": {
    "bitnet_thresholds_path": "src/bitnet/bitnet_thresholds.json"
}
```

Re-hash both configs after editing (`python scripts/maintenance/_compute_hash.py`).

---

## Step 3 — Threshold adapter (run AFTER Step 1 produces labelled data)

**New file: `src/bitnet/bitnet_threshold_adapter.py`**

The adapter reads closed trade records where `bitnet_score_at_entry` is populated, fits a calibrated threshold per instrument per regime, and writes updated values back to `bitnet_thresholds.json`.

**Core logic:**

```python
def calibrate(
    self,
    instrument: str,
    regime: str,
    records: list[dict],
    *,
    target_precision: float = 0.60,   # min fraction of ACCEPTs that reach TP1
    min_samples: int = 50,
) -> tuple[float, dict]:
    """
    Find the threshold T such that:
      precision(score > T) >= target_precision
    where precision = fraction of trades with bitnet_score > T that reached TP1.

    Returns (threshold, diagnostics_dict).
    Falls back to 0.5 if insufficient samples.
    """
```

Algorithm — threshold sweep:

```python
candidates = np.arange(0.30, 0.85, 0.02)   # sweep 0.30 → 0.84 in steps of 0.02
best_threshold = 0.5
best_precision = 0.0

for t in candidates:
    approved = [r for r in records
                if r.get("bitnet_score_at_entry", 0.0) > t]
    if len(approved) < min_samples:
        continue
    tp1_hits = sum(
        1 for r in approved
        if str(r.get("exit_reason", "")).upper() in ("TP1", "TP2", "SL-BE")
    )
    precision = tp1_hits / len(approved)
    # Take the lowest threshold that meets the precision target
    # (maximizes trade count while maintaining quality floor)
    if precision >= target_precision and t < best_threshold:
        best_threshold = t
        best_precision = precision

return best_threshold, {
    "instrument": instrument,
    "regime": regime,
    "n_records": len(records),
    "n_approved_at_threshold": len([
        r for r in records
        if r.get("bitnet_score_at_entry", 0.0) > best_threshold
    ]),
    "precision_at_threshold": best_precision,
    "target_precision": target_precision,
}
```

**Writer — updates `bitnet_thresholds.json` atomically:**

```python
def write_threshold(
    self,
    instrument: str,
    regime: str,
    threshold: float,
    diagnostics: dict,
) -> None:
    thresholds = self._load()
    thresholds.setdefault(instrument, {})
    thresholds[instrument][regime.upper()] = round(threshold, 4)
    # Emit before write so audit trail exists even if write fails
    from src.utils.integrity_events import emit_integrity_event
    emit_integrity_event(
        "BITNET_THRESHOLD_UPDATED", "INFO", "bitnet_threshold_adapter",
        {"instrument": instrument, "regime": regime,
         "new_threshold": threshold, **diagnostics}
    )
    self._save_atomic(thresholds)
```

**CLI entry point** — `scripts/training/calibrate_bitnet_thresholds.py`:

```bash
python scripts/training/calibrate_bitnet_thresholds.py \
    --instrument ETHUSDT \
    --regime TRENDING \
    --trades-csv results/portfolio_raw/ETHUSDT/run_*/ETHUSDT_trades.csv \
    --target-precision 0.60 \
    --min-samples 50
```

**Wire into `auto_train_from_opportunities.py`** — after `_maybe_promote()`, add an optional `_calibrate_bitnet_thresholds(instrument)` call gated by `--calibrate-bitnet` flag. Same pattern as `--refresh-zones`.

---

## What does NOT change

- `BitNetRunner.predict()` return shape — `{"score", "decision", "error"}` unchanged
- All existing callers of `BitNetRunner` — `instrument=` is kw-only with default `"UNKNOWN"`, existing construction sites keep working
- `CANONICAL_FEATURES` — `_regime` is never added to the canonical list
- `src/bitnet/model_contract.py` — threshold file is separate from model envelope, no contract change
- The `0.5` floor — it is always the last fallback, never removed

---

## Critical files

- `src/bitnet/bitnet_runner.py:130` — hardcoded threshold to replace
- `src/runtime/backtest_v2.py:200` — `TradeRecord` dataclass (add two fields)
- `src/runtime/live_engine_hook.py` — live path approval site (mirror the wiring)
- `src/config_layer/crt_engine_v2.py:1030,1096` — existing `bitnet_score()` call sites for reference
- `src/runtime/backtest_bitnet.py:244-247,336,356-357` — reference impl of BitNet-gated decision flow
- `src/utils/integrity_events.py` — `emit_integrity_event()` for `BITNET_THRESHOLD_LOAD_FAILED` and `BITNET_THRESHOLD_UPDATED`
- `configs/production/v1_multi_2026_03.json`, `configs/production/v2_multi_2026_04 - deepdeektry.json` — add `bitnet.bitnet_thresholds_path`, re-hash
- `src/bitnet/bitnet_thresholds.json` — new file, initial all-0.5 values
- `src/bitnet/bitnet_threshold_adapter.py` — new file (Step 3)
- `scripts/training/calibrate_bitnet_thresholds.py` — new CLI entry (Step 3)

---

## Verification

```bash
# Step 1 — confirm bitnet_score_at_entry appears in CSV after backtest
python scripts/backtest/run_backtest.py --instrument ETHUSDT --bars 2000
python -c "
import pandas as pd, glob
f = sorted(glob.glob('results/portfolio_raw/ETHUSDT/**/*_trades.csv', recursive=True))[-1]
df = pd.read_csv(f)
assert 'bitnet_score_at_entry' in df.columns, f'missing column. cols: {list(df.columns)}'
print('PASS — bitnet_score_at_entry present,', len(df), 'trades')
print(df[['bitnet_score_at_entry','bitnet_decision_at_entry','exit_reason']].head())
"

# Step 2 — confirm threshold lookup works and fallback chain fires
python -c "
from src.bitnet.bitnet_runner import BitNetRunner
runner = BitNetRunner('models/bitnet_export.json', instrument='ETHUSDT')
t_trend = runner._threshold_for('TRENDING')
t_unk   = runner._threshold_for('UNKNOWN')
t_fake  = runner._threshold_for('NONEXISTENT')
print(f'TRENDING={t_trend} UNKNOWN={t_unk} NONEXISTENT={t_fake}')
assert t_fake == 0.5, 'fallback chain broken'
print('PASS')
"

# Step 3 — calibrator produces valid threshold from synthetic records
python -c "
import random
from src.bitnet.bitnet_threshold_adapter import BitNetThresholdAdapter
records = []
for _ in range(200):
    score = random.uniform(0.3, 0.9)
    exit_reason = 'TP1' if score > 0.55 and random.random() > 0.3 else 'SL'
    records.append({'bitnet_score_at_entry': score, 'exit_reason': exit_reason})
adapter = BitNetThresholdAdapter()
threshold, diag = adapter.calibrate('ETHUSDT', 'TRENDING', records,
                                     target_precision=0.60, min_samples=20)
print(f'Calibrated threshold: {threshold:.4f}')
print(f'Diagnostics: {diag}')
assert 0.30 <= threshold <= 0.85
print('PASS')
"

# Step 4 — confirm integrity event emitted on threshold update
python -c "
import json, pathlib
from src.bitnet.bitnet_threshold_adapter import BitNetThresholdAdapter
adapter = BitNetThresholdAdapter()
adapter.write_threshold('ETHUSDT', 'TRENDING', 0.62, {'n_records': 200})
events = [json.loads(l) for l in
          pathlib.Path('logs/integrity_events.jsonl').read_text().splitlines()[-10:]]
kinds  = [e.get('event') for e in events]
assert 'BITNET_THRESHOLD_UPDATED' in kinds, kinds
print('PASS — event fired:', [e for e in events if e.get('event') == 'BITNET_THRESHOLD_UPDATED'][-1])
"
```

---

## Success criteria

- `bitnet_score_at_entry` and `bitnet_decision_at_entry` appear in `*_trades.csv` after first post-patch backtest
- Threshold lookup follows fallback chain: regime → DEFAULT → `__default__` → 0.5
- All existing construction sites work unchanged (kw-only `instrument=` with UNKNOWN default)
- Calibrator produces threshold in [0.30, 0.85] from synthetic labelled records
- `BITNET_THRESHOLD_UPDATED` integrity event fires on every threshold write
- Zero behavioural change until calibration runs (all thresholds start at 0.5)

---

## Sequencing

Ship Steps 1 and 2 together. Run one full backtest to accumulate labelled data. Then implement and verify Step 3 against real scores.

---

## Hotfix — UnicodeDecodeError on Windows when loading production config

### Context
My earlier config-rewrite script used `json.dump(..., ensure_ascii=False)`, which converted any pre-existing Unicode escape sequences (`\uXXXX`) in the JSON into actual UTF-8 bytes. `production_config.py` opens config files with `with open(path)` — no explicit encoding — so Python falls back to the Windows system codec (cp1252). cp1252 cannot decode the UTF-8 byte `0x9d` at position 1983, causing a `UnicodeDecodeError` at runtime.

### Root cause
Three `with open(...)` calls in `src/config_layer/production_config.py` lack `encoding='utf-8'`:
- Line 183 — `get_prod_metadata()` → reads full registry dict
- Line 223 — `load_prod_config_from_registry()` → the specific line in the traceback
- Line 326 — `get_prod_section()` → reads a named section

Line 362 already has `encoding="utf-8"` (correctly fixed in an earlier pass).

### Fix
Add `encoding="utf-8"` to the three bare `with open(registry_path)` calls.

```python
# Line 183:
with open(registry_path, encoding="utf-8") as f:

# Line 223:
with open(registry_path, encoding="utf-8") as f:

# Line 326:
with open(registry_path, encoding="utf-8") as f:
```

### Files
- `src/config_layer/production_config.py` — lines 183, 223, 326 (3 surgical edits)

### Verification
```bash
python src/runtime/backtest_v2.py --csv data/ETHUSDT_M15.csv --instrument ETHUSDT --output results/
# Should load config cleanly — no UnicodeDecodeError
```

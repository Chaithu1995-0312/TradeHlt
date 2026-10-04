> Created: 2026-05-09 · Updated: 2026-05-09 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Zone Registry Fix — Per-Instrument Registry with Underpowered Auto-Bypass

## Status: CRT Session Filter (previous plan) — ✅ DONE
All 5 steps implemented. `allowed_sessions` guard fires before `try_retest_to_execution`. Tests pass.

---

## Context

The zone_gate rejects EURUSD signals via `zone_gate_invalid` because the current `models/zone_registry.json` was built from **27 profitable trades across 8 instruments** (AUDUSD, BTCUSDT, ETHUSDT, EURCAD, EURUSD, GBPUSD, USDJPY, XAUUSD). The resulting single centroid is a cross-instrument average that does not represent EURUSD-specific profitable patterns. EURUSD signals deviate from this average → low Gaussian similarity score (< 0.5 threshold) → `zone_gate_invalid` → WR collapse.

**Data reality** (from `results/` CSVs):
| Instrument | Total trades | Profitable | In current zone |
|---|---|---|---|
| EURUSD | 8 | 3 | Diluted into 27-trade global centroid |
| Total (all instruments) | 71 | 27 | All merged into 1 zone |

**Root cause**: 3 EURUSD profitable trades is far too few for meaningful KMeans clustering (zone builder needs ≥ 10 samples). The zone gate is generating spurious `zone_gate_invalid` rejections that have no signal quality basis.

---

## Diagnosis

`models/zone_registry.json`:
- 1 zone, `weight=19.0` (total profitable trades used in build)
- `sigma[4]=0.0`, `sigma[5]=0.0`, `sigma[30]=0.0` — zero-variance features (constant across all trades)
- `threshold=0.5` — tight given cross-instrument training noise

`BitNetZoneGate` in `src/engines/live_engine.py`:
- `get_zone_registry_path(instrument, base_dir="models/bitnet")` already checks `models/bitnet/{INSTRUMENT}/zone_registry.json` before falling back to global — **per-instrument loading is already wired**
- `check()` computes weighted Gaussian similarity; returns `allowed=False` when best score < threshold

`HealthTracker.is_dead()` in `src/core/fusion_engine.py`:
- Requires `mean == 0.0 AND variance == 0.0` exactly — does NOT fire with the current registry because sigma-zero features produce near-zero but non-constant scores across candles

Current backtest bypass: `BACKTEST_BYPASS_ZONE_INVALID=1` (default on) — skips `zone_gate_invalid` rejections in backtest mode. This is correct short-term but not principled.

---

## Plan

### Step 1 — Add `zone_min_samples` guard to `BitNetZoneGate` (immediate fix)

**File:** `src/engines/live_engine.py` — `BitNetZoneGate.__init__()` and `check()`

In `__init__()`, after zones are loaded:
```python
# Compute total training samples across all zones
_total_samples = sum(float(z.get("weight", 0)) for z in self._zones)
_min_samples = float(config.get("zone_min_samples", 50))  # default 50
self._underpowered = bool(self._zones) and (_total_samples < _min_samples)
if self._underpowered:
    _log.warning(
        "ZoneGate: registry has only %.0f training samples (< %.0f min). "
        "Gate will auto-bypass (underpowered_zone_registry).",
        _total_samples, _min_samples,
    )
```

In `check()`, at the top of the method:
```python
if self._underpowered:
    return {
        "allowed": True,
        "score": 1.0,
        "threshold": 0.0,
        "zone_id": None,
        "reason": "underpowered_zone_registry",
        "top_scores": [],
    }
```

**Config key** to add to `configs/production/v2_multi_2026_04.json` under `engine_runner`:
```json
"zone_min_samples": 50
```

Current registry `weight=19 < 50` → auto-bypass fires → `zone_gate_invalid` never fires → no spurious rejections.

When a proper per-instrument registry is built with ≥ 50 samples, auto-bypass deactivates automatically.

### Step 2 — Add `--instrument` filter to zone builder (tool improvement)

**File:** `build_zone_registry_from_trades.py`

Modify `collect_profitable_vectors()` signature to accept optional instrument filter:
```python
def collect_profitable_vectors(trade_csv_paths, instrument: str | None = None):
    ...
    for path in trade_csv_paths:
        df = pd.read_csv(path)
        # Filter by instrument if requested
        if instrument and "instrument" in df.columns:
            df = df[df["instrument"].str.upper() == instrument.upper()]
            if df.empty:
                continue
        ...
```

Modify `main()` to accept `--instrument` and `--output` CLI args:
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--instrument", default=None, help="Filter by instrument (e.g. EURUSD)")
parser.add_argument("--output", default="models/zone_registry.json")
parser.add_argument("--min-points", type=int, default=5)
args = parser.parse_args()

# Auto-route output to per-instrument path if --instrument given
if args.instrument and args.output == "models/zone_registry.json":
    instr_key = f"{args.instrument}_M15"  # matches get_zone_registry_path lookup
    output_path = f"models/bitnet/{instr_key}/zone_registry.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
else:
    output_path = args.output
```

This makes the existing `get_zone_registry_path("EURUSD_M15")` lookup in `live_engine.py` auto-find the per-instrument file.

### Step 3 — Recompute config hash

After adding `zone_min_samples` to `configs/production/v2_multi_2026_04.json`:
```bash
cd D:\Tradelatest
python -c "
import json, hashlib
with open('configs/production/v2_multi_2026_04.json') as f:
    data = json.load(f)
params = data['params']
canonical = json.dumps(params, sort_keys=True)
h = hashlib.sha256(canonical.encode()).hexdigest()
data['config_hash'] = h
with open('configs/production/v2_multi_2026_04.json', 'w') as f:
    json.dump(data, f, indent=2)
print('New hash:', h[:24])
"
```

### Step 4 — Tests

**File:** `tests/test_zone_gate_min_samples.py` (new)

```python
def test_underpowered_registry_auto_bypasses():
    """BitNetZoneGate with weight=19 < zone_min_samples=50 returns allowed=True always."""
    gate = BitNetZoneGate(zones=[...weight=19 zone...], config={"zone_min_samples": 50})
    result = gate.check(feature_vector=[0.0]*35)
    assert result["allowed"] is True
    assert result["reason"] == "underpowered_zone_registry"

def test_powered_registry_enforces_threshold():
    """BitNetZoneGate with weight=60 >= zone_min_samples=50 enforces similarity threshold."""
    gate = BitNetZoneGate(zones=[...weight=60 zone with known centroid...], config={"zone_min_samples": 50})
    # Feed a feature vector distant from centroid
    result = gate.check(feature_vector=[999.0]*35)
    assert result["allowed"] is False
```

### Step 5 — Verify

```bash
cd D:\Tradelatest

# 1. Confirm zone gate no longer rejects signals (underpowered bypass active)
set BACKTEST_ENGINE_GATE=1
set BACKTEST_BYPASS_ZONE_INVALID=0   # turn off old bypass — new mechanism takes over
python src/runtime/backtest_v2.py --instrument EURUSD --csv data/EURUSD_M15.csv
# Expect: zone_gate_invalid count = 0 in rejection summary

# 2. Run regression suite
pytest tests/test_zone_gate_min_samples.py tests/test_engine_runner_dual_gate.py tests/test_crt_session_filter.py -v

# 3. Future: rebuild per-instrument registry once more data exists
python build_zone_registry_from_trades.py --instrument EURUSD
# → writes models/bitnet/EURUSD_M15/zone_registry.json (auto-loaded by live_engine)
```

---

## Critical Files

| File | Change |
|------|--------|
| `src/engines/live_engine.py` | Add `_underpowered` flag in `BitNetZoneGate.__init__()`, bypass in `check()` |
| `configs/production/v2_multi_2026_04.json` | Add `engine_runner.zone_min_samples: 50` |
| `build_zone_registry_from_trades.py` | Add `--instrument` CLI arg and per-instrument output routing |
| `tests/test_zone_gate_min_samples.py` (new) | Bypass + enforce threshold tests |

## Existing Utilities Reused
- `BitNetZoneGate.__init__()` / `check()` — `src/engines/live_engine.py` (already the scoring authority)
- `get_zone_registry_path(instrument)` — `src/engines/live_engine.py:45–55` (per-instrument path already supported)
- `build_zone_registry_from_trades.py` — existing builder, just add `--instrument` filter

## Expected Outcome

| Metric | Before (zone gate active, bad registry) | After (underpowered bypass) |
|---|---|---|
| `zone_gate_invalid` rejections | ~63% of all rejects | 0 |
| Signals passing to ultron gate | ~37% | ~100% (of session-allowed signals) |
| WR | 37% (suppressed) | TBD — depends on CRT quality |
| Zone gate effectiveness | Noise (cross-instrument centroid) | Neutral (gate inactive until proper registry built) |

**Long-term fix**: Once profitable EURUSD trade count reaches ≥ 50 (from longer CSV or multi-run accumulation), run `python build_zone_registry_from_trades.py --instrument EURUSD` to activate per-instrument zone filtering. The `zone_min_samples=50` threshold auto-reactivates the gate when that file exists.

## Out of Scope
- WR improvement to 70% — requires CRT threshold tuning or more data (separate task)
- Multi-instrument portfolio backtest (Phase C infrastructure already ready)
- Ultron gate regime context (separate blocker — needs HTF regime signal in feature dict)

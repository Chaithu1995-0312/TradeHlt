> Created: 2026-05-10 · Updated: 2026-05-10 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Config Version Single Source of Truth Refactor

## Context

The production config version is currently resolved in `production_config.py` with a silent fallback to `"v1_multi_2026_03"` when `ACTIVE_VERSION` is missing. This allows a misconfigured environment to run silently on a stale version. Additionally, long-running processes (backtest, live engine, engine runner) do not log which version they used, and trade CSVs/summary JSONs carry no `config_version` field, making post-hoc audit impossible. The goal is to: (1) make version resolution fail-fast, (2) stamp every output and log line with the active version.

---

## Files to Modify

| File | Change type |
|---|---|
| `src/config_layer/production_config.py` | Remove fallback, add fail-fast + logging |
| `src/runtime/backtest_v2.py` | Version log, TradeRecord field, CSV+JSON stamps, custom-config warning |
| `src/runtime/live_engine_hook.py` | Version log on init |
| `src/core/engine_runner.py` | Version log on init |
| `src/strategies/strategy_orchestrator.py` | Version log on init |
| `src/core/collector.py` | Add `config_version` to every JSONL record |
| `src/governance/promotion_manager.py` | Add `promoted_version` key to registry payload |
| `scripts/training/phase5_calibration.py` | Log version; uses model_registry not prod config — no config-load change needed |
| `scripts/training/auto_tuner.py` | Log version; uses ConfigBuilder — no config-load change needed |

---

## Step-by-Step Implementation

### 1. `src/config_layer/production_config.py` (lines 54–68)

**Remove:** `_FALLBACK_PROD_VERSION`, the try/except fallback in `_resolve_prod_version()`.

**Add:** `get_active_version()` function and a module-level logger.

```python
import logging as _logging

_log = _logging.getLogger(__name__)

def get_active_version() -> str:
    """Read version from ACTIVE_VERSION pointer file. Raises RuntimeError if missing."""
    if not _ACTIVE_VERSION_FILE.exists():
        raise RuntimeError(
            "No active version pointer found at configs/production/ACTIVE_VERSION. "
            "Run promotion_manager.py promote first."
        )
    try:
        resolved = _ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise RuntimeError(
            f"Failed to read configs/production/ACTIVE_VERSION: {e}"
        ) from e
    if not resolved:
        raise RuntimeError(
            "configs/production/ACTIVE_VERSION is empty. "
            "Run promotion_manager.py promote first."
        )
    _log.info("Active production config: %s", resolved)
    return resolved

PROD_VERSION: str = get_active_version()
```

Remove `_FALLBACK_PROD_VERSION` constant entirely. Keep `_ACTIVE_VERSION_FILE` as-is.

---

### 2. `src/runtime/backtest_v2.py`

#### 2a. Add version log at start of `BacktestRunner.run()` (line ~1343)

```python
from config_layer.production_config import PROD_VERSION
self.log.info("Production config version: %s", PROD_VERSION)
```

#### 2b. Add `config_version` field to `TradeRecord` dataclass (after line 248, after `cached_double_sweep`)

```python
config_version: str = field(default_factory=lambda: PROD_VERSION)
```

Import `PROD_VERSION` at module top alongside other `config_layer` imports (already imported via `BacktestConfig.from_prod_config()`). Add at module level:
```python
from config_layer.production_config import PROD_VERSION as _PROD_VERSION
```
Use `_PROD_VERSION` as the default so it's evaluated once at module load (not deferred).

Actually simpler: use `field(default="")` and populate from `PROD_VERSION` in `TradeJournal.on_trade_closed()` — but the cleanest pattern matching the codebase is a module-level import and `field(default_factory=...)`.

Use this exact pattern:
```python
# Near top of file after other config_layer imports
from config_layer.production_config import PROD_VERSION

# In TradeRecord dataclass, after cached_double_sweep field:
config_version: str = field(default_factory=lambda: PROD_VERSION)
```

#### 2c. Add `config_version` column in `TradeJournal.to_csv_rows()` (after line 909)

After `row["cached_double_sweep"] = int(r.cached_double_sweep)`, add:
```python
row["config_version"] = r.config_version
```

#### 2d. Add `config_version` in `BacktestMetrics.to_dict()` (after line 983, inside the returned dict)

```python
"config_version": PROD_VERSION,
```

#### 2e. Handle `--config` CLI override (lines 1969–1973 in `main()`)

Replace the existing block:
```python
if args.config:
    with open(args.config) as f:
        overrides = json.load(f)
    safe_print(f"Config overrides loaded from {args.config} (not applied to CRT backtest)")
```

With:
```python
if args.config:
    import warnings as _w
    bt_log.warning(
        "Using overridden config: %s (production version %s ignored)",
        args.config, PROD_VERSION,
    )
    # Patch PROD_VERSION sentinel so all downstream records reflect the override
    import config_layer.production_config as _pc
    _pc.PROD_VERSION = f"CUSTOM:{Path(args.config).name}"
```

This means `TradeRecord.config_version` defaults and `BacktestMetrics.to_dict()` will show `"CUSTOM:<filename>"` instead of the production version.

---

### 3. `src/runtime/live_engine_hook.py`

In `HookedLiveEngine.__init__` (or right after logger init at line ~80), add:

```python
from config_layer.production_config import PROD_VERSION
self.logger.info("Production config version: %s", PROD_VERSION)
```

---

### 4. `src/core/engine_runner.py`

In `EngineRunner.__init__` (after collector init at line ~351), add:

```python
from config_layer.production_config import PROD_VERSION as _pv
self._log.info("Production config version: %s", _pv)
```

Check which logger name `EngineRunner` uses (likely `self._log` or similar); adjust accordingly.

---

### 5. `src/strategies/strategy_orchestrator.py`

In `StrategyOrchestrator.__init__` or `compute()`, add equivalent version log using that class's logger.

---

### 6. `src/core/collector.py` — `collect()` function (line ~107)

In the `record` dict construction, add:

```python
from config_layer.production_config import PROD_VERSION
```

Inside `record`:
```python
"config_version": PROD_VERSION,
```

Place it after the `"t"` field for visibility. The `collect()` function is module-level, so import at top of file rather than inside the function.

---

### 7. `src/governance/promotion_manager.py` — `_build_registry_entry()` (line ~342)

`promoted_at` already exists in the payload (line 356). Add an explicit `promoted_version` key as a convenience alias:

```python
"promoted_version": version,   # explicit alias alongside "version" key
```

Add this in `_build_registry_entry()` immediately after `"version": version` (line 353).

---

### 8. Scripts — version logging only

**`scripts/training/phase5_calibration.py`** — after existing `log = logging.getLogger("Phase5")`, add:
```python
from config_layer.production_config import PROD_VERSION
log.info("Production config version: %s", PROD_VERSION)
```

**`scripts/training/auto_tuner.py`** — after existing `tuner_log = logging.getLogger("AutoTuner")`, add:
```python
from config_layer.production_config import PROD_VERSION
tuner_log.info("Production config version: %s", PROD_VERSION)
```

Neither script does direct `json.load()` on the production config file — both use proper gateways (`model_registry`, `ConfigBuilder`) — so no config-loading changes are needed.

---

## Verification

After implementation:

```bash
# 1. Smoke test version resolution
python -c "from config_layer.production_config import PROD_VERSION; print(PROD_VERSION)"
# Should print: v2_multi_2026_04

# 2. Confirm fail-fast when ACTIVE_VERSION absent
python -c "
import os, pathlib
p = pathlib.Path('configs/production/ACTIVE_VERSION')
p.rename('configs/production/ACTIVE_VERSION.bak')
try:
    import importlib, config_layer.production_config as m
    importlib.reload(m)
except RuntimeError as e:
    print('PASS:', e)
finally:
    pathlib.Path('configs/production/ACTIVE_VERSION.bak').rename(p)
"

# 3. Run a short backtest and verify
python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD --output results/test_plan

# Check log contains version line:
grep "Production config version" logs/backtest_debug.log

# Check summary JSON has config_version field:
python -c "import json; d=json.load(open('results/test_plan/EURUSD_summary.json')); print(d['config_version'])"

# Check trade CSV has config_version column:
python -c "import csv; r=next(csv.DictReader(open('results/test_plan/EURUSD_trades.csv'))); print(r['config_version'])"
```

---

## Notes / Constraints

- `PROD_VERSION` is evaluated **once at import time** — changing `_pc.PROD_VERSION` in the `--config` override path works because `TradeRecord.config_version` uses `lambda: PROD_VERSION` (late binding), and `BacktestMetrics.to_dict()` reads `PROD_VERSION` at call time.
- The import `from config_layer.production_config import PROD_VERSION` inside `collect()` must be moved to **module level** (not inside the function) to avoid repeated import overhead on the hot path.
- `EngineRunner` is used in both backtest and live paths, so the version log there covers both without duplication.
- No schema hash changes — `PROD_VERSION` is metadata, not a `params` key.
- No `CANONICAL_FEATURES` changes — this refactor is pure metadata plumbing.

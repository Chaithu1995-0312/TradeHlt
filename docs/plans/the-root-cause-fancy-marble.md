> Created: 2026-05-10 · Updated: 2026-05-10 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Fix backtest_v2.py ignoring CRT parameters from production config JSON

## Context

`backtest_v2.py main()` constructs `CRTConfig` directly with only three hardcoded CLI defaults, bypassing the production JSON entirely. The `crt_engine` section (containing fields like `body_ratio_min`, `atr_multiplier_min`, `retest_depth_max`, etc.) is never loaded. This means every backtest silently runs with market-router hardcoded defaults instead of the tuned JSON values.

There is also a secondary bug: `BacktestRunner.__init__` falls back to a bare `CRTConfig()` if `bt_config.crt_config` is None, which also bypasses the JSON.

---

## Critical files

- `src/runtime/backtest_v2.py` — primary fix (lines 1990–2010, line 1281)
- `src/config_layer/production_config.py` — provides `load_prod_config_from_registry`, `_coerce_crt_engine`, `PROD_VERSION`
- `src/config_layer/config_builder.py` — provides `ConfigBuilder.from_existing()` for applying CLI overrides on top of loaded config

---

## Changes

### 1. `src/runtime/backtest_v2.py` — top-level imports (line 64)

Add to the existing production_config import line:

```python
# Before:
from config_layer.production_config import PROD_VERSION

# After:
from config_layer.production_config import (
    PROD_VERSION,
    load_prod_config_from_registry,
)
from config_layer.config_builder import ConfigBuilder
```

---

### 2. `src/runtime/backtest_v2.py` — CLI arg defaults (lines 1990–1992)

Change the three CRT CLI arg defaults from hardcoded values to `None`, consistent with every other JSON-backed arg in `main()`:

```python
# Before:
ap.add_argument("--sweep-age",    type=int,   default=20)
ap.add_argument("--decay",        type=float, default=0.10)
ap.add_argument("--threshold",    type=float, default=0.75)

# After:
ap.add_argument("--sweep-age",    type=int,   default=None)
ap.add_argument("--decay",        type=float, default=None)
ap.add_argument("--threshold",    type=float, default=None)
```

---

### 3. `src/runtime/backtest_v2.py` — CRTConfig construction (lines 1999–2010)

Replace the direct `CRTConfig()` instantiation with a proper JSON load + CLI override layer:

```python
# Before:
_cli_overrides: dict = {}

crt_cfg = CRTConfig(
    max_sweep_age_candles=args.sweep_age,
    score_decay_lambda=args.decay,
    score_threshold=args.threshold,
)
# Always record CRT overrides — these always deviate from the JSON default.
_cli_overrides["--sweep-age"]  = str(args.sweep_age)
_cli_overrides["--decay"]      = str(args.decay)
_cli_overrides["--threshold"]  = str(args.threshold)
_cli_overrides["--scorer"]     = args.scorer

# After:
_cli_overrides: dict = {}

# Determine instrument for market routing. Multi-instrument runs use EURUSD as the
# Forex baseline; crt_engine JSON values override the base, so numeric params are
# correct regardless of which instrument is routed later.
_instr_hint = (
    args.instrument if args.instrument not in ("AUTO", "ALL")
    else Path(args.csv).stem.upper() if not Path(args.csv).is_dir()
    else "EURUSD"
)

# Load ALL CRTConfig fields from the production JSON (params + crt_engine merged).
crt_cfg = load_prod_config_from_registry(PROD_VERSION, _instr_hint)

# Apply explicit CLI overrides only for flags that were actually passed.
_crt_cli: dict = {}
if args.sweep_age is not None:
    _crt_cli["max_sweep_age_candles"] = args.sweep_age
    _cli_overrides["--sweep-age"] = str(args.sweep_age)
if args.decay is not None:
    _crt_cli["score_decay_lambda"] = args.decay
    _cli_overrides["--decay"] = str(args.decay)
if args.threshold is not None:
    _crt_cli["score_threshold"] = args.threshold
    _cli_overrides["--threshold"] = str(args.threshold)

if _crt_cli:
    crt_cfg = ConfigBuilder.from_existing(_instr_hint, crt_cfg, extra_overrides=_crt_cli)

_cli_overrides["--scorer"] = args.scorer
```

---

### 4. `src/runtime/backtest_v2.py` — BacktestRunner fallback (line 1281)

Fix the bare `CRTConfig()` fallback to go through `ConfigBuilder` instead of hardcoded defaults:

```python
# Before:
self.crt_cfg  = bt_config.crt_config or CRTConfig()

# After:
self.crt_cfg  = bt_config.crt_config or ConfigBuilder.build(
    bt_config.instrument or "EURUSD"
)
```

This still uses market-router base defaults (not the full JSON), but is only hit when `BacktestConfig` is constructed without a `crt_config` (test/API paths), not the `main()` path.

---

## Verification

1. **Smoke test — single instrument:**
   ```
   python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD --output results/test_fix
   ```
   Check the `*_config.json` dump in `results/test_fix/` — `body_ratio_min`, `atr_multiplier_min`, `retest_depth_max` should now match the `crt_engine` section in the active production JSON.

2. **CLI override still works:**
   ```
   python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD --threshold 0.80
   ```
   The config dump should show `score_threshold: 0.80` and only `--threshold` recorded in `cli_overrides`.

3. **No CLI flags — all from JSON:**
   ```
   python src/runtime/backtest_v2.py --csv data/EURUSD_M15.csv --instrument EURUSD
   ```
   `cli_overrides` dict in the config dump should NOT contain `--sweep-age`, `--decay`, or `--threshold` (previously they were always recorded even when not passed).

4. **Existing tests:**
   ```
   python -m pytest tests/ -x -q
   ```
   No regressions expected; tests that construct `BacktestRunner` directly with an explicit `crt_config` are unaffected.

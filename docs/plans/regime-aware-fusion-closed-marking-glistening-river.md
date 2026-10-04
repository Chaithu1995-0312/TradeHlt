> Created: 2026-05-21 · Updated: 2026-05-21 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan — Gaussian Versioning Per Instrument

## Context

`gaussian_registry.json` currently uses a flat `{version_id: entry}` shape where each entry carries `active: bool`. A single `active: True` flag is the system's only active-version pointer, so **any instrument promotion overwrites the active flag for every other instrument** — promoting a new EURUSD model also flips XAUUSD off. There is no rollback path. Separately, `trainer.load_gaussian_model` reads `bundle["scaler"]` without auditing missing-scaler cases, so the loud `KeyError` it raises today never lands in `logs/integrity_events.jsonl` and is invisible to forensics.

This patch isolates the active-version pointer per instrument, adds a per-instrument rollback path, and audits the missing-scaler failure mode — without rewriting the registry schema or breaking existing callers.

## Decisions (locked from user feedback)

| Question | Decision |
| --- | --- |
| Registry shape | **Hybrid:** keep `{version_id: entry}` flat. Add one top-level `__active__: {instrument: version}` map. The `__` prefix signals "registry metadata, not a version entry" so any iterator can skip it cleanly. |
| `promote_gaussian` signature | Add `*, instrument: Optional[str] = None` (keyword-only) to the method **and** the module-level wrapper. When `instrument is None`, derive from `reg[version].get("instrument")` and emit `GAUSSIAN_PROMOTE_INSTRUMENT_INFERRED` info event. |
| `trainer.py` scaler guard | Add explicit `bundle.get("scaler") is None` check that emits `GAUSSIAN_MISSING_SCALER` ERROR event. **Preserve** original exception type — `KeyError` for missing key, `RuntimeError` for explicit `None`. |
| Engine instrument source | `__init__(self, config, *, instrument: Optional[str] = None, preload_registry: bool = False)`. Body: `self._instrument = instrument or config.get("instrument", "EURUSD")`. |

## Files To Modify

### 1. `src/core/model_registry.py`

**Lines 86–95** (`_save_atomic`) — unchanged. Atomic write mechanism is correct.

**Lines 98–108** (`_assert_single_active`) — unchanged. Stays generic for non-gaussian registries (tradenet, zone, RR still use the legacy single-active invariant).

**Line 350–353** (`GaussianModelRegistry._save`) — **stop calling** `_assert_single_active(reg, active_key="active")`. The gaussian registry now allows multiple entries with `active: True` (one per instrument during transition). Replace with a new assertion `_assert_single_active_per_instrument(reg)` defined below.

**New helpers** (place above `class GaussianModelRegistry` at line 320):

```python
_ACTIVE_MAP_KEY = "__active__"   # double-underscore => not a version entry

def _is_meta_key(k: str) -> bool:
    return k.startswith("__")

def _assert_single_active_per_instrument(reg: dict) -> None:
    """At most one entry per instrument may have active=True."""
    by_inst: dict[str, list[str]] = {}
    for k, v in reg.items():
        if _is_meta_key(k) or not isinstance(v, dict):
            continue
        if v.get("active", False):
            inst = v.get("instrument", "_unknown")
            by_inst.setdefault(inst, []).append(k)
    for inst, versions in by_inst.items():
        if len(versions) > 1:
            raise RuntimeError(
                f"GOV-3 violation: instrument {inst!r} has multiple "
                f"active versions {versions}. Write aborted."
            )

def _migrate_gaussian_registry(reg: dict) -> dict:
    """One-time migration: if __active__ map is absent, populate it from
    existing entry-level active flags. Idempotent — safe to call on every load."""
    if _ACTIVE_MAP_KEY in reg:
        return reg
    active_map: dict[str, str] = {}
    for k, v in reg.items():
        if _is_meta_key(k) or not isinstance(v, dict):
            continue
        if v.get("active", False):
            inst = v.get("instrument")
            if inst:
                active_map[inst] = k
            else:
                log.warning(
                    "Gaussian migration: version %s is active but has no "
                    "instrument field — skipping in __active__ map", k
                )
    reg[_ACTIVE_MAP_KEY] = active_map
    try:
        from src.utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "GAUSSIAN_REGISTRY_MIGRATED", "INFO", "model_registry",
            {"active_map": active_map, "n_versions": len([
                k for k in reg if not _is_meta_key(k)
            ])}
        )
    except Exception:
        pass   # don't block migration on telemetry
    return reg
```

**`_load` (line 341–348)** — wrap the parsed dict in `_migrate_gaussian_registry()`:

```python
def _load(self) -> dict:
    if not self.reg_path.exists():
        return {}
    try:
        raw = json.loads(self.reg_path.read_text(encoding="utf-8"))
        return _migrate_gaussian_registry(raw)
    except Exception as e:
        log.warning(f"Gaussian registry load failed: {e}")
        return {}
```

**`promote_gaussian` (lines 400–498)** — change signature to keyword-only `instrument`:

```python
def promote_gaussian(
    self,
    version: str,
    *,
    instrument: Optional[str] = None,
    force: bool = False,
    max_regression: float = 0.01,
) -> tuple[bool, str]:
```

Inside the lock body, after the existing schema-version and GAP-3 checks succeed but **before** the "Derive current_active from registry scan" block (line 454):

```python
# Resolve instrument target for this promotion
if instrument is None:
    instrument = reg[version].get("instrument")
    if instrument:
        try:
            from src.utils.integrity_events import emit_integrity_event
            emit_integrity_event(
                "GAUSSIAN_PROMOTE_INSTRUMENT_INFERRED", "INFO", "model_registry",
                {"version": version, "instrument": instrument}
            )
        except Exception:
            pass
if not instrument:
    return False, (
        f"Gaussian promotion BLOCKED: cannot determine instrument for "
        f"{version}. Pass instrument= explicitly or re-register the entry "
        f"with an 'instrument' field."
    )
```

Replace `active_versions = [k for k, v in reg.items() if v.get("active", False)]` with an instrument-scoped scan:

```python
active_map = reg.setdefault(_ACTIVE_MAP_KEY, {})
current_active = active_map.get(instrument)   # may be None for first deploy

# Belt-and-braces: also scan for legacy entry-level active flag in case the
# active map is stale (e.g., manual edit). Map takes priority.
if current_active is None:
    for k, v in reg.items():
        if _is_meta_key(k) or not isinstance(v, dict):
            continue
        if v.get("active") and v.get("instrument") == instrument:
            current_active = k
            break
```

In all three "promote" branches (first deploy, current not found, success path), update the **write logic** to:

```python
# Deactivate any current active for THIS instrument only
if current_active and current_active in reg:
    reg[current_active]["active"] = False
reg[version]["active"] = True
active_map[instrument] = version   # __active__ map is source of truth
reg[_ACTIVE_MAP_KEY] = active_map
self._save(reg)
```

The cross-instrument entries with `active: True` are untouched. `_assert_single_active_per_instrument` (called from `_save`) enforces the new invariant.

**`get_active_gaussian` (lines 500–505)** — keep the no-arg signature for backward compatibility, add a new method:

```python
def get_active_gaussian(self) -> Optional[str]:
    """Legacy: returns active version for default instrument (EURUSD)."""
    return self.get_active_version("EURUSD")

def get_active_version(self, instrument: str) -> Optional[str]:
    reg = self._load()
    active_map = reg.get(_ACTIVE_MAP_KEY, {})
    return active_map.get(instrument)

def rollback_gaussian(self, instrument: str) -> tuple[bool, str]:
    """Promote the previous (by trained_at desc) version for the instrument."""
    reg = self._load()
    active_map = reg.get(_ACTIVE_MAP_KEY, {})
    current = active_map.get(instrument)
    if not current:
        return False, f"No active version for instrument {instrument!r}"
    # All entries for this instrument, sorted newest-first
    candidates = sorted(
        [k for k, v in reg.items()
         if not _is_meta_key(k) and isinstance(v, dict)
         and v.get("instrument") == instrument and k != current],
        key=lambda k: reg[k].get("trained_at", ""),
        reverse=True,
    )
    if not candidates:
        return False, "no_history"
    previous = candidates[0]
    return self.promote_gaussian(previous, instrument=instrument, force=True)
```

**Module-level wrappers (lines 1032–1048)** — propagate the kw-only arg:

```python
def promote_gaussian(version: str, *, instrument: Optional[str] = None,
                     force: bool = False, max_regression: float = 0.01) -> tuple[bool, str]:
    return _gaussian_registry.promote_gaussian(
        version, instrument=instrument, force=force, max_regression=max_regression
    )

def get_active_gaussian() -> Optional[str]:
    return _gaussian_registry.get_active_gaussian()

def get_active_version(instrument: str) -> Optional[str]:
    return _gaussian_registry.get_active_version(instrument)

def rollback_gaussian(instrument: str) -> tuple[bool, str]:
    return _gaussian_registry.rollback_gaussian(instrument)
```

### 2. `src/engines/heuristic_gaussian_engine.py`

**`__init__` (line 175)** — add kw-only `instrument` parameter:

```python
def __init__(self, config: dict, *, instrument: Optional[str] = None,
             preload_registry: bool = False):
    self.config = config
    self._instrument = instrument or config.get("instrument", "EURUSD")
    self._registry: Optional[GaussianRegistry] = None
    self._loaded_version: Optional[str] = None
    # ... rest unchanged
```

**`_load_registry` (lines 197–213)** — pass instrument to the loader and record loaded version:

```python
def _load_registry(self) -> None:
    registry_path = self.config.get("gaussian_registry_path", GAUSSIAN_REGISTRY_PATH)
    try:
        self._registry = GaussianRegistry(
            registry_path, instrument=self._instrument
        ).load()
        self._loaded_version = self._registry.active_version
        logger.info(
            "HeuristicGaussianEngine[%s]: loaded registry — active '%s'",
            self._instrument, self._loaded_version,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        try:
            from src.utils.integrity_events import emit_integrity_event
            emit_integrity_event(
                "GAUSSIAN_NO_MODEL", "WARNING", "heuristic_gaussian_engine",
                {"instrument": self._instrument, "error": str(exc)}
            )
        except Exception:
            pass
        logger.warning(
            "HeuristicGaussianEngine[%s]: registry load failed (%s). "
            "Using config/default mu=%.2f, sigma=%.2f.",
            self._instrument, exc,
            self._mu_override or 0.0, self._sigma_override or 1.0,
        )
        self._registry = None
        self._loaded_version = None
```

**`GaussianRegistry` class (line 60)** — accept `instrument` and read from `__active__` map with legacy fallback:

```python
def __init__(self, registry_path: str = GAUSSIAN_REGISTRY_PATH,
             models_dir: str = GAUSSIAN_MODELS_DIR,
             instrument: str = "EURUSD"):
    self.registry_path = registry_path
    self.models_dir = models_dir
    self.instrument = instrument
    self._entries: dict = {}
    self._active_version: Optional[str] = None
```

In `load()` (line 70), filter meta keys when normalizing, then prefer `__active__[instrument]`:

```python
self._entries = {
    v: _normalize_registry_entry(v, entry)
    for v, entry in raw.items()
    if not v.startswith("__") and isinstance(entry, dict)
}

active_map = raw.get("__active__", {})
requested_version = active_map.get(self.instrument)

if requested_version is None:
    # Legacy fallback: scan entry-level active flag scoped by instrument
    matches = [
        v for v, e in self._entries.items()
        if e.get("active") and e.get("instrument") == self.instrument
    ]
    if matches:
        requested_version = matches[0]

if requested_version is None:
    raise RuntimeError(
        f"GaussianRegistry: no active version for instrument "
        f"{self.instrument!r} in {self.registry_path}"
    )

self._active_version = self._resolve_with_fallback(requested_version)
return self
```

**`compute` reload guard (lines 245–255)** — version-stamp compare:

```python
if self._registry is None and self._mu_override is None:
    self._load_registry()
    self._watcher.mark_loaded()
elif self._registry is not None and self._watcher.needs_reload():
    prev = self._loaded_version
    self._registry = None
    self._load_registry()
    self._watcher.mark_loaded()
    if self._loaded_version != prev:
        logger.info(
            "HeuristicGaussianEngine[%s]: reloaded — '%s' -> '%s'",
            self._instrument, prev, self._loaded_version,
        )
```

### 3. `src/training/trainer.py`

**`load_gaussian_model` (lines 406–453)** — add scaler audit before the existing read at line 438:

```python
# Audit missing-scaler failures so they show up in logs/integrity_events.jsonl
# rather than crashing silently. Preserves original exception types.
if bundle.get("scaler") is None:
    try:
        from src.utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "GAUSSIAN_MISSING_SCALER", "ERROR", "trainer",
            {"model_path": str(path), "model_name": name,
             "note": "re-train with current trainer to produce a scaler"}
        )
    except Exception:
        pass
    if "scaler" not in bundle:
        raise KeyError("scaler")   # preserve missing-key semantics
    raise RuntimeError(
        f"Gaussian model '{name}' has scaler=None. "
        f"Re-train with the current trainer to produce a calibrated scaler. "
        f"Refusing to load uncalibrated model."
    )
```

Note: `load_gaussian_model` takes `name: str`, not `(path, instrument=...)` as the prompt suggested. Instrument context isn't available at this call site — the integrity event uses `model_name` instead.

### 4. `scripts/auto_train_from_opportunities.py`

**`_maybe_promote` (line 151)** — add `instrument` parameter, thread to `promote_gaussian`:

```python
def _maybe_promote(version: str, instrument: str) -> None:
    # ... existing import-guard block
    ok, reason = promote_gaussian(version, instrument=instrument)
    # ... existing event emission
```

**Call site in `_train_instrument`** — already has `instrument`, pass it through: `_maybe_promote(version, instrument)`.

### 5. `scripts/training/phase5_calibration.py`

**Line 1618** — pass `instrument` argument:

```python
if get_active_gaussian() is None:
    promoted, reason = promote_gaussian(version, instrument=args.instrument or "EURUSD")
```

The `--instrument` argparse already exists (line 1347) so no new arg is needed.

### 6. `models/gaussian_registry.json`

No manual edit. `_migrate_gaussian_registry()` populates `__active__` lazily on first read.

## What is OUT of scope

- `_save_atomic`, `_PROMOTE_LOCK`, `_file_lock` — unchanged
- `_assert_single_active` (the generic helper at line 98) — unchanged; still used by tradenet/zone/RR registries
- `register_gaussian` — unchanged; entries already carry `instrument` field
- `list_gaussian`, `print_gaussian_leaderboard` — touched only to skip `__active__` meta key via `_is_meta_key(k)` filter inside their iteration
- PATCH-v3 schema check, GAP-3 corr floor, FIX-3 regression guard — all unchanged
- `RegistryWatcher` — unchanged; the version-stamp compare runs after `_load_registry()` re-reads the file
- The on-disk `gaussian_registry.json` is NOT pre-edited; migration runs lazily

## Verification

Run from repo root after implementation. The prompt's verification snippets need three fixes (signatures and free-function call sites) — corrected versions:

```powershell
# 1 — migration: legacy registry layout migrates cleanly on first read
python -c "
from src.core.model_registry import _migrate_gaussian_registry
old = {
    'gaussian_EURUSD_v1': {'active': True, 'instrument': 'EURUSD', 'trained_at': '2026-05-01'},
    'gaussian_XAUUSD_v1': {'active': True, 'instrument': 'XAUUSD', 'trained_at': '2026-05-01'},
}
migrated = _migrate_gaussian_registry(old)
assert migrated['__active__'] == {'EURUSD': 'gaussian_EURUSD_v1', 'XAUUSD': 'gaussian_XAUUSD_v1'}
print('PASS — migration:', migrated['__active__'])
"

# 2 — instrument isolation: EURUSD promotion does not touch XAUUSD
python -c "
import json, tempfile, pathlib
from src.core.model_registry import GaussianModelRegistry
d = pathlib.Path(tempfile.mkdtemp())
reg = GaussianModelRegistry(models_dir=d)
# seed (need register + promote; metrics dict must satisfy schema gate)
reg.register_gaussian('gaussian_EURUSD_v1', 'x.json', [], {'corr_expected_rr': 0.1}, instrument='EURUSD')
reg.register_gaussian('gaussian_XAUUSD_v1', 'y.json', [], {'corr_expected_rr': 0.1}, instrument='XAUUSD')
reg.register_gaussian('gaussian_EURUSD_v2', 'z.json', [], {'corr_expected_rr': 0.1}, instrument='EURUSD')
reg.promote_gaussian('gaussian_EURUSD_v1', force=True)
reg.promote_gaussian('gaussian_XAUUSD_v1', force=True)
reg.promote_gaussian('gaussian_EURUSD_v2', force=True)
assert reg.get_active_version('XAUUSD') == 'gaussian_XAUUSD_v1'
assert reg.get_active_version('EURUSD') == 'gaussian_EURUSD_v2'
print('PASS — XAUUSD untouched after EURUSD re-promote')
"

# 3 — rollback restores the previous EURUSD version
python -c "
import tempfile, pathlib
from src.core.model_registry import GaussianModelRegistry
d = pathlib.Path(tempfile.mkdtemp())
reg = GaussianModelRegistry(models_dir=d)
reg.register_gaussian('gaussian_EURUSD_v1', 'a.json', [], {'corr_expected_rr': 0.1, 'trained_at': '2026-05-01T00:00:00Z'}, instrument='EURUSD')
reg.register_gaussian('gaussian_EURUSD_v2', 'b.json', [], {'corr_expected_rr': 0.1, 'trained_at': '2026-05-15T00:00:00Z'}, instrument='EURUSD')
reg.promote_gaussian('gaussian_EURUSD_v1', force=True)
reg.promote_gaussian('gaussian_EURUSD_v2', force=True)
ok, ver = reg.rollback_gaussian('EURUSD')
assert ok and 'gaussian_EURUSD_v1' in ver
print('PASS — rolled back to:', ver)
"

# 4 — scaler=None guard raises RuntimeError, scaler missing key raises KeyError
python -c "
import json, tempfile, pathlib
from src.training.trainer import load_gaussian_model, MODELS_DIR
# Case A: scaler=None
p1 = MODELS_DIR / 'tmp_scaler_none.json'
p1.write_text(json.dumps({'model': {}, 'scaler': None}))
try:
    load_gaussian_model('tmp_scaler_none.json')
    print('FAIL A')
except RuntimeError as e:
    print('PASS A — RuntimeError:', e)
finally:
    p1.unlink(missing_ok=True)
# Case B: scaler key absent
p2 = MODELS_DIR / 'tmp_scaler_missing.json'
p2.write_text(json.dumps({'model': {}}))
try:
    load_gaussian_model('tmp_scaler_missing.json')
    print('FAIL B')
except KeyError as e:
    print('PASS B — KeyError:', e)
finally:
    p2.unlink(missing_ok=True)
"

# 5 — quick backtest, confirm no regression in active path
python scripts/backtest/run_backtest.py --instrument EURUSD --bars 500

# 6 — confirm integrity events landed
python -c "
import json, pathlib
events = [json.loads(l) for l in pathlib.Path('logs/integrity_events.jsonl').read_text().splitlines()[-50:]]
kinds = [e.get('event_type') for e in events]
print('Recent integrity events:', set(kinds))
assert 'GAUSSIAN_REGISTRY_MIGRATED' in kinds, 'migration event not logged'
"
```

### Success criteria

- Migration runs lazily, emits `GAUSSIAN_REGISTRY_MIGRATED` once
- EURUSD re-promotion leaves `__active__["XAUUSD"]` unchanged
- `rollback_gaussian("EURUSD")` returns `(True, "<prev_version>")`
- `scaler: None` raises `RuntimeError`; missing key raises `KeyError`; both emit `GAUSSIAN_MISSING_SCALER`
- Backtest completes clean, zero new errors
- Logs show `GAUSSIAN_REGISTRY_MIGRATED` event

"""
model_registry.py
═══════════════════════════════════════════════════════════════════════════════
Versioned model registry with promotion guard.

Every trained model is registered with its eval metrics and composite score.
A new model is ONLY promoted to "active" if it beats the current best by
at least PROMOTION_MARGIN — preventing noisy score fluctuations from
silently deploying a worse model.

Registry lives at models/registry.json.
Active model name lives at models/active.txt.
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from training.evaluator import EvalResult

# PATCH v3: schema enforcement on model load
from features.feature_schema import schema_for_model, SCHEMA_VERSION

# PATCH v3: schema version enforcement on model load

log = logging.getLogger("ModelRegistry")

MODELS_DIR       = Path("models")
REGISTRY_PATH    = MODELS_DIR / "registry.json"
ACTIVE_PATH      = MODELS_DIR / "active.txt"
PROMOTION_MARGIN = 0.02   # new model must beat current by this margin

# ─────────────────────────────────────────────────────────────────────────────
# ATOMICITY HELPERS  (GOV-3)
# ─────────────────────────────────────────────────────────────────────────────

# In-process lock — prevents concurrent promote() calls within one process.
_PROMOTE_LOCK = threading.RLock()


@contextmanager
def _file_lock(lock_path: Path, timeout: float = 5.0):
    """
    Cross-process exclusive lock via O_CREAT|O_EXCL atomic file creation.

    Raises TimeoutError if the lock cannot be acquired within `timeout` seconds.
    Safe on both POSIX and Windows (same-drive rename semantics apply).
    """
    deadline = time.monotonic() + timeout
    fd = None
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            break
        except FileExistsError:
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"ModelRegistry: could not acquire lock {lock_path} "
                    f"within {timeout}s. Another process may be promoting."
                )
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _save_atomic(path: Path, data: dict) -> None:
    """
    Atomic JSON write: serialise to a .tmp sibling then os.replace().
    os.replace() is atomic on POSIX (rename(2)) and Windows (MoveFileExW
    with MOVEFILE_REPLACE_EXISTING) when source and target share a drive.
    Guarantees readers never see a partial write.
    """
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _assert_single_active(reg: dict, active_key: str = "promoted") -> None:
    """
    GOV-3 invariant: at most one entry may have active_key=True.
    Raises RuntimeError before any write if the invariant would be violated.
    """
    active = [k for k, v in reg.items() if v.get(active_key, False)]
    if len(active) > 1:
        raise RuntimeError(
            f"GOV-3 violation: dual-active state detected "
            f"({active_key}=True on {active}). Write aborted."
        )


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY ENTRY
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ModelEntry:
    name:            str
    composite_score: float
    accuracy:        float
    precision:       float
    recall:          float
    bucket_stats:    dict
    n_val_samples:   int
    trained_at:      str   # ISO timestamp
    promoted:        bool  = False


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class ModelRegistry:

    def __init__(self, models_dir: Path = MODELS_DIR, promotion_margin: float = PROMOTION_MARGIN) -> None:
        self.dir               = models_dir
        self.reg_path          = models_dir / "registry.json"
        self.act_path          = models_dir / "active.txt"
        self._promotion_margin = promotion_margin
        self.dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_prod_config(cls, models_dir: Path = MODELS_DIR) -> "ModelRegistry":
        """Production constructor — fail-fast. Strict-reads the GOV-3 promotion margin from the
        ``governance`` section (no silent default); a missing section/key raises. The
        ``PROMOTION_MARGIN`` module constant remains the canonical default for unit-test /
        standalone construction only (config-first doctrine §6.5)."""
        from config_layer.production_config import get_prod_section
        section = get_prod_section("governance")
        if "promotion_margin" not in section:
            raise KeyError(
                "Required config key 'promotion_margin' missing from 'governance' section. "
                "Add it to the production config (config-first doctrine: no silent defaults)."
            )
        return cls(models_dir=models_dir, promotion_margin=float(section["promotion_margin"]))

    # ── Load / Save ───────────────────────────────────────────────────────────

    def _load(self) -> dict[str, dict]:
        if not self.reg_path.exists():
            return {}
        try:
            return json.loads(self.reg_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Registry load failed: {e}. Starting fresh.")
            return {}

    def _save(self, reg: dict) -> None:
        # GOV-3: guard before write, then atomic rename
        _assert_single_active(reg, active_key="promoted")
        _save_atomic(self.reg_path, reg)

    # ── Register ──────────────────────────────────────────────────────────────

    def register(self, model_name: str, eval_result: EvalResult) -> ModelEntry:
        """
        Add a trained + evaluated model to the registry.
        Does NOT promote automatically — call try_promote() separately.
        """
        reg  = self._load()
        entry = ModelEntry(
            name            = model_name,
            composite_score = round(eval_result.composite_score, 6),
            accuracy        = round(eval_result.accuracy,        4),
            precision       = round(eval_result.precision,       4),
            recall          = round(eval_result.recall,          4),
            bucket_stats    = eval_result.bucket_stats,
            n_val_samples   = eval_result.n_samples,
            trained_at      = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            promoted        = False,
        )
        reg[model_name] = asdict(entry)
        self._save(reg)
        log.info(f"Registered {model_name}  composite={entry.composite_score:.4f}")
        return entry

    # ── Promotion ─────────────────────────────────────────────────────────────

    def try_promote(self, model_name: str) -> tuple[bool, str]:
        """
        Promote model_name to active if it beats current best by PROMOTION_MARGIN.

        Atomicity guarantees (GOV-3):
          - In-process: guarded by _PROMOTE_LOCK (threading.RLock)
          - Cross-process: guarded by a .lock file (O_CREAT|O_EXCL)
          - Write: _save_atomic() writes to .tmp then os.replace() — no partial writes
          - GOV-3 guard: _assert_single_active() fires before any disk write
          - active.txt written AFTER the registry is safely on disk; get_active()
            falls back to scanning promoted=True in registry if the file is stale.

        Returns (promoted: bool, reason: str)
        """
        lock_path = self.reg_path.with_suffix(".lock")
        with _PROMOTE_LOCK, _file_lock(lock_path):
            reg = self._load()

            if model_name not in reg:
                return False, f"{model_name} not in registry"

            new_score = reg[model_name]["composite_score"]

            # Derive current active from registry (promoted flag) — canonical truth.
            # This avoids a TOCTOU race between get_active() and the write below.
            promoted_names = [k for k, v in reg.items() if v.get("promoted", False)]
            current_name   = promoted_names[0] if promoted_names else None
            current_score  = reg[current_name]["composite_score"] if current_name else 0.0

            if new_score > current_score + self._promotion_margin:
                # Demote old, promote new — all in-memory before any write
                if current_name and current_name in reg:
                    reg[current_name]["promoted"] = False
                reg[model_name]["promoted"] = True

                # Single atomic write — GOV-3 guard inside _save()
                self._save(reg)

                # active.txt is a convenience cache; written after registry is safe.
                # If this write fails, get_active() falls back to the registry scan.
                try:
                    self.act_path.write_text(model_name, encoding="utf-8")
                except OSError as e:
                    log.warning(
                        "try_promote: registry updated but active.txt write failed (%s). "
                        "get_active() will fall back to registry scan.", e
                    )

                reason = (
                    f"promoted {model_name} (score={new_score:.4f}) "
                    f"over {current_name or 'none'} (score={current_score:.4f}) "
                    f"Δ={new_score - current_score:+.4f}"
                )
                log.info(reason)
                print(f"\n  ✅ PROMOTED: {reason}\n")
                return True, reason
            else:
                reason = (
                    f"not promoted: {model_name} score={new_score:.4f} "
                    f"vs active={current_score:.4f} "
                    f"Δ={new_score - current_score:+.4f} < margin={self._promotion_margin}"
                )
                log.info(reason)
                print(f"\n  ⚠  NOT PROMOTED: {reason}\n")
                return False, reason

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_active(self) -> Optional[str]:
        """
        Return name of the currently active model, or None.

        Primary source: active.txt (fast path).
        Fallback: scan registry for promoted=True (used when active.txt is stale
        or missing after a crash between the registry write and active.txt write).
        If active.txt names a model not in the registry, fallback is used and
        active.txt is repaired.
        """
        reg = self._load()
        name: Optional[str] = None

        if self.act_path.exists():
            candidate = self.act_path.read_text(encoding="utf-8").strip()
            if candidate and candidate in reg and reg[candidate].get("promoted", False):
                return candidate
            # active.txt stale or inconsistent — fall through to registry scan
            if candidate:
                log.warning(
                    "get_active: active.txt names '%s' but registry shows it as "
                    "not promoted. Falling back to registry scan.", candidate
                )

        # Fallback: find promoted=True in registry
        promoted = [k for k, v in reg.items() if v.get("promoted", False)]
        if len(promoted) == 1:
            name = promoted[0]
            # Repair active.txt
            try:
                self.act_path.write_text(name, encoding="utf-8")
            except OSError:
                pass
            return name
        if len(promoted) > 1:
            log.error(
                "get_active: GOV-3 violation detected in registry — "
                "multiple promoted models: %s. Returning first.", promoted
            )
            return promoted[0]
        return None

    def get_best(self) -> Optional[tuple[str, float]]:
        """Return (name, score) of highest-scoring registered model."""
        reg = self._load()
        if not reg:
            return None
        best = max(reg.items(), key=lambda kv: kv[1]["composite_score"])
        return best[0], best[1]["composite_score"]

    def list_all(self) -> list[dict]:
        reg = self._load()
        return sorted(reg.values(), key=lambda x: x["composite_score"], reverse=True)

    def print_leaderboard(self, n: int = 10) -> None:
        entries = self.list_all()[:n]
        active  = self.get_active()
        print(f"\n  {'─'*60}")
        print(f"  Model Leaderboard (top {n})")
        print(f"  {'─'*60}")
        print(f"  {'Name':<30} {'Score':>7}  {'Acc':>6}  {'Active'}")
        print(f"  {'─'*60}")
        for e in entries:
            flag = " ← ACTIVE" if e["name"] == active else ""
            print(
                f"  {e['name']:<30} {e['composite_score']:>7.4f}  "
                f"{e['accuracy']:>6.4f}  {flag}"
            )
        print(f"  {'─'*60}\n")


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN REGISTRY — per-instrument active map + helpers
# ─────────────────────────────────────────────────────────────────────────────

_ACTIVE_MAP_KEY = "__active__"


def _is_meta_key(k: str) -> bool:
    # Double-underscore prefix marks registry metadata (not a version entry).
    return isinstance(k, str) and k.startswith("__")


def _assert_single_active_per_instrument(reg: dict) -> None:
    """At most one entry per instrument may have active=True."""
    by_inst: dict = {}
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
    """One-time migration: populate __active__ map from entry-level active flags
    when the map is absent. Idempotent — safe to call on every load."""
    if not isinstance(reg, dict) or _ACTIVE_MAP_KEY in reg:
        return reg
    active_map: dict = {}
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
        from utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "GAUSSIAN_REGISTRY_MIGRATED", "INFO", "model_registry",
            {
                "active_map": active_map,
                "n_versions": sum(1 for k in reg if not _is_meta_key(k)),
            },
        )
    except Exception:
        pass
    return reg


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN MODEL REGISTRY  (versioned, never overwrites)
# ─────────────────────────────────────────────────────────────────────────────

class GaussianModelRegistry:
    """
    Versioned registry for Gaussian model bundles.

    Each entry stores:
      {version, feature_schema, metrics: {corr, calibration_error, timestamp}}

    NEVER overwrites — every save creates a new version entry.
    Rollback = promote any prior version name.
    """

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.dir      = models_dir
        self.reg_path = models_dir / "gaussian_registry.json"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.reg_path.exists():
            return {}
        try:
            raw = json.loads(self.reg_path.read_text(encoding="utf-8"))
            return _migrate_gaussian_registry(raw)
        except Exception as e:
            log.warning(f"Gaussian registry load failed: {e}")
            return {}

    def _save(self, reg: dict) -> None:
        # GOV-3: per-instrument invariant — one active per instrument, written atomically.
        _assert_single_active_per_instrument(reg)
        _save_atomic(self.reg_path, reg)

    def register_gaussian(
        self,
        version: str,
        model_file: str,
        feature_schema: list,
        metrics: dict,
        instrument: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict:
        reg = self._load()
        if version in reg:
            log.warning(f"Version {version} already exists — not overwriting")
            return reg[version]

        expected_schema_version = schema_for_model("gaussian").version

        entry = {
            "version":        version,
            "model_file":     model_file,
            "feature_schema": feature_schema,
            # PATCH v3: embed schema version in every registry entry
            # Prevents stale models from being loaded after a schema bump.
            "schema_version": expected_schema_version,
            "metrics": {
                "corr_expected_rr":  metrics.get("corr_expected_rr",  0.0),
                "calibration_error": metrics.get("calibration_error", 1.0),
                "n_train":           metrics.get("n_train",           0),
                "n_val":             metrics.get("n_val",             0),
            },
            "trained_at": metrics.get("trained_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
            "active":     False,
        }
        if instrument:
            entry["instrument"] = instrument
        if run_id:
            entry["run_id"] = run_id
        reg[version] = entry
        self._save(reg)
        log.info(
            f"GaussianRegistry | registered {version} "
            f"corr={entry['metrics']['corr_expected_rr']:+.4f} "
            f"cal={entry['metrics']['calibration_error']:.4f}"
        )
        return entry

    def promote_gaussian(
        self,
        version: str,
        *,
        instrument: Optional[str] = None,
        force: bool = False,
        max_regression: float = 0.01,
    ) -> tuple[bool, str]:
        """
        Promote a Gaussian version to active for a given instrument.

        Active pointer lives in reg["__active__"][instrument]. Promotion only
        affects the named instrument; other instruments' active versions are
        untouched.

        FIX 3: Compares against current active model metrics for the SAME
        instrument. Blocks promotion if new model regresses by more than
        max_regression on corr_expected_rr (unless force=True).

        Parameters
        ----------
        version        : version to promote
        instrument     : target instrument; if None, derived from reg[version]["instrument"]
        force          : bypass performance comparison (use for first deploy or testing)
        max_regression : max allowed corr decrease vs current active (default 0.01 = 1%)
        """
        lock_path = self.reg_path.with_suffix(".lock")
        with _PROMOTE_LOCK, _file_lock(lock_path):
            reg = self._load()
            if version not in reg:
                return False, f"Version {version} not in Gaussian registry"

            # PATCH v3: block promotion if model was trained with a different schema version
            expected_schema_version = schema_for_model("gaussian").version
            entry_schema_version = reg[version].get("schema_version")
            if entry_schema_version and entry_schema_version != expected_schema_version:
                reason = (
                    f"Gaussian promotion BLOCKED (PATCH v3 schema mismatch): {version} "
                    f"was trained with schema version '{entry_schema_version}' but "
                    f"current schema is '{expected_schema_version}'. Re-train before promoting."
                )
                log.error(reason)
                return False, reason

            new_metrics = reg[version].get("metrics", {})
            new_corr    = new_metrics.get("corr_expected_rr", 0.0)
            new_cal     = new_metrics.get("calibration_error", 1.0)

            # GAP-3 fix: absolute quality floor — blocks ALL promotions when corr < 0.
            # A negative-corr model performs worse than random; never deploy regardless
            # of force=True, first-deployment path, or regression-guard bypass.
            if new_corr < 0.0:
                reason = (
                    f"Gaussian promotion BLOCKED (GAP-3 absolute floor): {version} "
                    f"corr={new_corr:+.4f} < 0.0 — model degrades performance. "
                    f"Re-train with corrected data or features. "
                    f"force=True does NOT bypass this guard."
                )
                log.error(reason)
                return False, reason

            # Resolve instrument target — explicit arg wins; else derive from entry;
            # else fall back to a "_default" bucket so legacy callers that never set
            # an instrument continue to work. Misuse is audited so call sites can be
            # found and updated.
            if instrument is None:
                instrument = reg[version].get("instrument")
                if instrument:
                    try:
                        from utils.integrity_events import emit_integrity_event
                        emit_integrity_event(
                            "GAUSSIAN_PROMOTE_INSTRUMENT_INFERRED", "INFO", "model_registry",
                            {"version": version, "instrument": instrument},
                        )
                    except Exception:
                        pass
            if not instrument:
                instrument = "_default"
                try:
                    from utils.integrity_events import emit_integrity_event
                    emit_integrity_event(
                        "GAUSSIAN_PROMOTE_INSTRUMENT_MISSING", "WARNING", "model_registry",
                        {"version": version,
                         "note": "no instrument arg passed and entry has no 'instrument' field — "
                                 "promoted into '_default' bucket. Update caller to pass instrument=."},
                    )
                except Exception:
                    pass

            # Per-instrument active pointer — __active__ map is source of truth.
            active_map = reg.setdefault(_ACTIVE_MAP_KEY, {})
            current_active = active_map.get(instrument)

            # Legacy fallback: if map is empty for this instrument, scan entries
            # (covers freshly-migrated registries where the map was just built).
            if current_active is None:
                for k, v in reg.items():
                    if _is_meta_key(k) or not isinstance(v, dict):
                        continue
                    if v.get("active") and v.get("instrument") == instrument:
                        current_active = k
                        break

            # First deployment for this instrument — no comparison needed
            if current_active is None:
                reg[version]["active"] = True
                active_map[instrument] = version
                reg[_ACTIVE_MAP_KEY] = active_map
                self._save(reg)
                reason = (
                    f"First Gaussian deployment for {instrument}: {version} "
                    f"(corr={new_corr:+.4f})"
                )
                log.info(reason)
                return True, reason

            if current_active not in reg:
                reg[version]["active"] = True
                active_map[instrument] = version
                reg[_ACTIVE_MAP_KEY] = active_map
                self._save(reg)
                reason = (
                    f"Promoted Gaussian {version} for {instrument} "
                    f"(current active not found in registry)"
                )
                log.info(reason)
                return True, reason

            cur_metrics = reg[current_active].get("metrics", {})
            cur_corr    = cur_metrics.get("corr_expected_rr", 0.0)
            cur_cal     = cur_metrics.get("calibration_error", 1.0)

            if not force:
                if new_corr < cur_corr - max_regression:
                    reason = (
                        f"Gaussian promotion BLOCKED (FIX3): {version} corr={new_corr:+.4f} "
                        f"< current {current_active} corr={cur_corr:+.4f} - {max_regression} "
                        f"(regression={cur_corr - new_corr:.4f} > max_regression={max_regression}). "
                        f"Use force=True to override."
                    )
                    log.warning(reason)
                    return False, reason

            # Deactivate current for THIS instrument only; activate new.
            reg[current_active]["active"] = False
            reg[version]["active"] = True
            active_map[instrument] = version
            reg[_ACTIVE_MAP_KEY] = active_map
            # Single atomic write; per-instrument GOV-3 guard inside _save()
            self._save(reg)
            reason = (
                f"Promoted Gaussian {version} for {instrument} "
                f"(corr={new_corr:+.4f} cal={new_cal:.4f}) "
                f"over {current_active} (corr={cur_corr:+.4f} cal={cur_cal:.4f})"
            )
            log.info(reason)
            return True, reason

    def get_active_gaussian(self) -> Optional[str]:
        """Legacy: returns active version for the default instrument (EURUSD).
        Prefer get_active_version(instrument) for new callers."""
        return self.get_active_version("EURUSD")

    def get_active_version(self, instrument: str) -> Optional[str]:
        reg = self._load()
        active_map = reg.get(_ACTIVE_MAP_KEY, {})
        return active_map.get(instrument)

    def rollback_gaussian(self, instrument: str) -> tuple[bool, str]:
        """Promote the previous (by trained_at desc) version for the instrument.
        Returns (False, "no_history") if there is no prior version to roll back to."""
        reg = self._load()
        active_map = reg.get(_ACTIVE_MAP_KEY, {})
        current = active_map.get(instrument)
        if not current:
            return False, f"No active version for instrument {instrument!r}"
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

    def list_gaussian(self) -> list[dict]:
        reg = self._load()
        return sorted(
            [v for k, v in reg.items() if not _is_meta_key(k) and isinstance(v, dict)],
            key=lambda x: x.get("trained_at", ""),
            reverse=True,
        )

    def print_gaussian_leaderboard(self) -> None:
        entries = self.list_gaussian()
        active  = self.get_active_gaussian()
        print(f"\n  {'─'*65}")
        print(f"  Gaussian Model Leaderboard")
        print(f"  {'─'*65}")
        print(f"  {'Version':<30} {'Corr':>7}  {'CalErr':>7}  {'Active'}")
        print(f"  {'─'*65}")
        for e in entries:
            flag = " ← ACTIVE" if e.get("version") == active else ""
            m = e.get("metrics", {})
            print(
                f"  {e['version']:<30} "
                f"{m.get('corr_expected_rr', 0):>+7.4f}  "
                f"{m.get('calibration_error', 0):>7.4f}  {flag}"
            )
        print(f"  {'─'*65}\n")


# ─────────────────────────────────────────────────────────────────────────────
# DYNAMIC GAUSSIAN SCORER LOADER
#
# Replaces the hardcoded _P5_PARAMS / CRTCalibratedScorer pattern that required
# editing backtest_v2.py for every retrain. Runtime modules call
# load_active_gaussian_scorer() and get a ready-to-use scorer object whose
# .compute(features, candle_idx) signature matches CRTCalibratedScorer.
# ─────────────────────────────────────────────────────────────────────────────

import math as _math

# Direction-mirroring constants (must match phase5_calibration._MIRROR_*).
# Applied at inference time for short trades when the model was trained in long perspective.
_GMIRROR_NEGATE: frozenset = frozenset({
    "ema_spread", "trend_bias", "trend_strength", "momentum_score",
    "rsi_14", "macd_line", "macd_signal", "macd_hist_raw", "macd_hist_z",
    "break_of_structure", "liquidity_sweep",
})
_GMIRROR_SWAP: list = [("higher_high", "lower_low"), ("swing_high", "swing_low")]


def _mirror_features_for_short(x: list, feature_order) -> list:
    """Mirror a 35-dim feature vector from short perspective to long perspective."""
    idx = {name: i for i, name in enumerate(feature_order)}
    result = list(x)
    for fname in _GMIRROR_NEGATE:
        i = idx.get(fname)
        if i is not None:
            result[i] = -result[i]
    for fa, fb in _GMIRROR_SWAP:
        ia, ib = idx.get(fa), idx.get(fb)
        if ia is not None and ib is not None:
            result[ia], result[ib] = result[ib], result[ia]
    return result


class GaussianScorer:
    """Calibrated GaussianNB scorer loaded from a JSON params bundle.

    Params shape matches what phase5_calibration.py emits in
    `models/gaussian_{version}.json`:
      {schema_version, schema_checksum, feature_names, n_features, n_classes,
       class_priors, means, vars, rr_weights, scaler_mean, scaler_std}
    """

    def __init__(self, params: dict, version: Optional[str] = None) -> None:
        self.version       = version
        self._n_features   = int(params["n_features"])
        self._n_classes    = int(params["n_classes"])
        self._priors       = params["class_priors"]
        self._means        = params["means"]
        self._vars         = params["vars"]
        self._rr_weights   = params["rr_weights"]
        self._scaler_mean  = params["scaler_mean"]
        self._scaler_std   = params["scaler_std"]

    @classmethod
    def from_json(cls, path: Path, version: Optional[str] = None) -> "GaussianScorer":
        raw = json.loads(path.read_text(encoding="utf-8"))
        # save_gaussian_model() writes nested {model:{...}, scaler:{mean,std}}
        if "model" in raw and "scaler" in raw:
            params = dict(raw["model"])
            params["scaler_mean"] = raw["scaler"]["mean"]
            params["scaler_std"] = raw["scaler"]["std"]
        else:
            params = raw  # legacy flat format
        return cls(params, version=version)

    def _scale(self, x):
        return [(x[i] - self._scaler_mean[i]) / self._scaler_std[i]
                for i in range(self._n_features)]

    def _predict_proba(self, xs):
        lp = []
        for c in range(self._n_classes):
            v = _math.log(self._priors[c] + 1e-300)
            for f in range(self._n_features):
                mu, va = self._means[c][f], self._vars[c][f]
                v -= 0.5 * _math.log(2 * _math.pi * va) + (xs[f] - mu) ** 2 / (2 * va)
            lp.append(v)
        mx = max(lp)
        ex = [_math.exp(v - mx) for v in lp]
        t  = sum(ex)
        return [e / t for e in ex]

    def compute(self, features, candle_idx, direction: str = "long"):
        if not features:
            return None
        try:
            from features.feature_pipeline import build_feature_vector as _b
            from features.feature_schema import CANONICAL_FEATURE_ORDER as _CFO
            x  = _b(features)
            if direction == "short":
                x = _mirror_features_for_short(x, _CFO)
            p  = self._predict_proba(self._scale(x))
            er = sum(w * q for w, q in zip(self._rr_weights, p))
            sc = min(1.0, max(0.0, er / (max(self._rr_weights) or 1.0)))
            return {
                "score":       round(sc, 4),
                "p_win":       round(p[2] + p[3], 4),
                "p_loss":      round(p[0], 4),
                "p_weak":      round(p[1], 4),
                "p_mid":       round(p[2], 4),
                "p_strong":    round(p[3], 4),
                "expected_rr": round(er, 4),
            }
        except Exception:
            return None


class NoOpScorer:
    """Fallback scorer used when no active gaussian model is on disk.

    Mirrors the existing default behaviour of CRTGaussianScorer.compute() —
    returns None so downstream gates treat the score as neutral.
    """

    def __init__(self, reason: str = "no active gaussian model") -> None:
        self.reason = reason
        log.warning("NoOpScorer active (%s) — gaussian gating disabled.", reason)

    def compute(self, features, candle_idx, direction: str = "long"):
        return None


def load_active_gaussian_scorer(models_dir: Path = MODELS_DIR):
    """Return the active gaussian scorer or a NoOpScorer fallback.

    Resolution order for the model file:
      1. registry entry's `model_file` field (if present and exists)
      2. convention: `models/gaussian_{version}.json`
    """
    version = get_active_gaussian()
    if version is None:
        return NoOpScorer("no active gaussian registered")

    reg = _gaussian_registry._load()
    entry = reg.get(version, {})
    candidate_path: Optional[Path] = None

    declared = entry.get("model_file")
    if declared:
        p = Path(declared)
        if p.exists():
            candidate_path = p

    if candidate_path is None:
        p = models_dir / f"gaussian_{version}.json"
        if p.exists():
            candidate_path = p

    if candidate_path is None:
        return NoOpScorer(f"active gaussian {version} not on disk")

    try:
        scorer = GaussianScorer.from_json(candidate_path, version=version)
        log.info("Active gaussian loaded: %s (%s)", version, candidate_path)
        return scorer
    except Exception as e:
        log.warning("Gaussian load failed for %s (%s): %s", version, candidate_path, e)
        return NoOpScorer(f"load failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ZONE GATE REGISTRY  (versioned, never overwrites)
# ─────────────────────────────────────────────────────────────────────────────

class ZoneGateRegistry:
    """
    Versioned registry for Zone Gate model files.

    Each entry stores:
      {version, model_file, n_zones, n_clusters_requested, feature_order,
       trained_at, active}

    On promote(): sets active=True for the target version and writes the
    versioned file content to the canonical zone_registry.json path so that
    existing engine_runner / runtime code continues reading from config-driven
    path without changes.
    """

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.dir      = models_dir
        self.reg_path = models_dir / "zone_gate_registry.json"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.reg_path.exists():
            return {}
        try:
            return json.loads(self.reg_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("ZoneGateRegistry load failed: %s", e)
            return {}

    def _save(self, reg: dict) -> None:
        _assert_single_active(reg, active_key="active")
        _save_atomic(self.reg_path, reg)

    def register(
        self,
        version: str,
        model_file: str,
        n_zones: int,
        n_clusters_requested: int,
        feature_order: list,
    ) -> dict:
        reg = self._load()
        if version in reg:
            log.warning("ZoneGate version %s already registered — skipping", version)
            return reg[version]
        entry = {
            "version":              version,
            "model_file":           model_file,
            "n_zones":              n_zones,
            "n_clusters_requested": n_clusters_requested,
            "feature_order":        feature_order,
            "trained_at":           time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "active":               False,
        }
        reg[version] = entry
        self._save(reg)
        log.info("ZoneGateRegistry | registered %s (%d zones)", version, n_zones)
        return entry

    def promote(self, version: str) -> tuple[bool, str]:
        lock_path = self.reg_path.with_suffix(".lock")
        with _PROMOTE_LOCK, _file_lock(lock_path):
            reg = self._load()
            if version not in reg:
                return False, f"ZoneGate version {version} not in registry"
            for k in reg:
                reg[k]["active"] = False
            reg[version]["active"] = True
            self._save(reg)
            reason = f"ZoneGate promoted: {version}"
            log.info(reason)
            return True, reason

    def get_active(self) -> Optional[str]:
        reg = self._load()
        for v, entry in reg.items():
            if entry.get("active", False):
                return v
        return None

    def get_active_entry(self) -> Optional[dict]:
        reg = self._load()
        for entry in reg.values():
            if entry.get("active", False):
                return entry
        return None

    def list_versions(self) -> list[dict]:
        reg = self._load()
        return sorted(reg.values(), key=lambda x: x.get("trained_at", ""), reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# RR MODEL REGISTRY  (versioned, never overwrites)
# ─────────────────────────────────────────────────────────────────────────────

class RRModelRegistry:
    """
    Versioned registry for RR dataset + model files.

    Dataset and model may be registered separately (build-dataset → train-model
    are separate CLI commands). Both share the same version key so the registry
    entry grows from {dataset_file} → {dataset_file, model_file} as training progresses.
    """

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.dir      = models_dir
        self.reg_path = models_dir / "rr_registry.json"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.reg_path.exists():
            return {}
        try:
            return json.loads(self.reg_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("RRModelRegistry load failed: %s", e)
            return {}

    def _save(self, reg: dict) -> None:
        _assert_single_active(reg, active_key="active")
        _save_atomic(self.reg_path, reg)

    def register_dataset(
        self,
        version: str,
        dataset_file: str,
        n_samples: int,
        n_features: int,
        instrument: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict:
        """Register or update a dataset-only entry (model may be trained later)."""
        reg     = self._load()
        existing = reg.get(version, {})
        entry = {
            "version":      version,
            "dataset_file": dataset_file,
            "model_file":   existing.get("model_file", None),
            "model_exists": bool(existing.get("model_file")),
            "n_samples":    n_samples,
            "n_features":   n_features,
            "metrics":      existing.get("metrics", {}),
            "trained_at":   existing.get(
                "trained_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            ),
            "active":       existing.get("active", False),
        }
        if instrument:
            entry["instrument"] = instrument
        if run_id:
            entry["run_id"] = run_id
        reg[version] = entry
        self._save(reg)
        log.info("RRRegistry | registered dataset %s (%d samples)", version, n_samples)
        return entry

    def register_model(
        self,
        version: str,
        model_file: str,
        metrics: dict,
    ) -> dict:
        """Update (or create) a registry entry with the trained model path + metrics."""
        reg = self._load()
        entry = reg.get(version, {
            "version":      version,
            "dataset_file": None,
            "n_samples":    0,
            "n_features":   35,
            "trained_at":   time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "active":       False,
        })
        entry["model_file"]   = model_file
        entry["model_exists"] = True
        entry["metrics"]      = metrics
        reg[version] = entry
        self._save(reg)
        log.info("RRRegistry | registered model %s", version)
        return entry

    def promote(self, version: str) -> tuple[bool, str]:
        lock_path = self.reg_path.with_suffix(".lock")
        with _PROMOTE_LOCK, _file_lock(lock_path):
            reg = self._load()
            if version not in reg:
                return False, f"RR version {version} not in registry"
            for k in reg:
                reg[k]["active"] = False
            reg[version]["active"] = True
            self._save(reg)
            reason = f"RR promoted: {version}"
            log.info(reason)
            return True, reason

    def get_active(self) -> Optional[str]:
        reg = self._load()
        for v, entry in reg.items():
            if entry.get("active", False):
                return v
        return None

    def get_active_entry(self) -> Optional[dict]:
        reg = self._load()
        for entry in reg.values():
            # Gap-7 fix: skip orphan entries where model_file was never written.
            # These arise when a dataset is built but training never completes.
            # Returning such an entry would cause TypeError on open(model_file).
            if entry.get("active", False) and entry.get("model_file") is not None:
                return entry
        return None

    def list_versions(self) -> list[dict]:
        reg = self._load()
        return sorted(reg.values(), key=lambda x: x.get("trained_at", ""), reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# TRADENET REGISTRY  (versioned, never overwrites)
# ─────────────────────────────────────────────────────────────────────────────

def _migrate_tradenet_registry(reg: dict) -> dict:
    """Populate __active__ map from entry-level active flags on first load.
    Idempotent — safe to call on every load."""
    if not isinstance(reg, dict) or _ACTIVE_MAP_KEY in reg:
        return reg
    active_map: dict = {}
    for k, v in reg.items():
        if _is_meta_key(k) or not isinstance(v, dict):
            continue
        if v.get("active", False):
            inst = v.get("instrument")
            if inst:
                active_map[inst] = k
            else:
                log.warning(
                    "TradeNet migration: version %s is active but has no "
                    "instrument field — skipping in __active__ map", k
                )
    reg[_ACTIVE_MAP_KEY] = active_map
    try:
        from utils.integrity_events import emit_integrity_event
        emit_integrity_event(
            "TRADENET_REGISTRY_MIGRATED", "INFO", "model_registry",
            {
                "active_map": active_map,
                "n_versions": sum(1 for k in reg if not _is_meta_key(k)),
            },
        )
    except Exception:
        pass
    return reg


class TradeNetRegistry:
    """
    Versioned registry for TradeNet model files (.pth v1 or JSON envelope v2).

    Per-instrument active pointer lives in reg["__active__"][instrument].
    Promotion only affects the named instrument — other instruments are untouched.
    Mirrors GaussianModelRegistry semantics.
    """

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.dir      = models_dir
        self.reg_path = models_dir / "tradenet_registry.json"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.reg_path.exists():
            return {}
        try:
            raw = json.loads(self.reg_path.read_text(encoding="utf-8"))
            return _migrate_tradenet_registry(raw)
        except Exception as e:
            log.warning("TradeNetRegistry load failed: %s", e)
            return {}

    def _save(self, reg: dict) -> None:
        _assert_single_active_per_instrument(reg)
        _save_atomic(self.reg_path, reg)

    def register(
        self,
        version: str,
        model_file: str,
        metrics: dict,
        instrument: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict:
        reg = self._load()
        if version in reg:
            log.warning("TradeNet version %s already registered — skipping", version)
            return reg[version]
        entry = {
            "version":    version,
            "model_file": model_file,
            "metrics":    metrics,
            "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "active":     False,
        }
        if instrument:
            entry["instrument"] = instrument
        if run_id:
            entry["run_id"] = run_id
        reg[version] = entry
        self._save(reg)
        log.info("TradeNetRegistry | registered %s", version)
        return entry

    def promote(
        self,
        version: str,
        *,
        instrument: Optional[str] = None,
        force: bool = False,
        max_regression: float = 0.01,
    ) -> tuple[bool, str]:
        """
        Promote a TradeNet version to active for a given instrument.

        Primary metric for regression guard: ``metrics["auc_p_tp1"]`` (mirrors
        Gaussian's ``corr_expected_rr`` role). When the new entry has no
        ``auc_p_tp1`` field — legacy v1 entries store only generic ``metrics``
        — the regression guard is skipped silently and ``force`` semantics
        still apply.
        """
        lock_path = self.reg_path.with_suffix(".lock")
        with _PROMOTE_LOCK, _file_lock(lock_path):
            reg = self._load()
            if version not in reg:
                return False, f"TradeNet version {version} not in registry"

            new_metrics = reg[version].get("metrics", {}) or {}
            new_auc = new_metrics.get("auc_p_tp1")

            if instrument is None:
                instrument = reg[version].get("instrument")
                if instrument:
                    try:
                        from utils.integrity_events import emit_integrity_event
                        emit_integrity_event(
                            "TRADENET_PROMOTE_INSTRUMENT_INFERRED", "INFO", "model_registry",
                            {"version": version, "instrument": instrument},
                        )
                    except Exception:
                        pass
            if not instrument:
                instrument = "_default"
                try:
                    from utils.integrity_events import emit_integrity_event
                    emit_integrity_event(
                        "TRADENET_PROMOTE_INSTRUMENT_MISSING", "WARNING", "model_registry",
                        {"version": version,
                         "note": "no instrument arg and entry has no 'instrument' field — "
                                 "promoted into '_default' bucket. Update caller to pass instrument=."},
                    )
                except Exception:
                    pass

            active_map = reg.setdefault(_ACTIVE_MAP_KEY, {})
            current_active = active_map.get(instrument)
            if current_active is None:
                for k, v in reg.items():
                    if _is_meta_key(k) or not isinstance(v, dict):
                        continue
                    if v.get("active") and v.get("instrument") == instrument:
                        current_active = k
                        break

            if current_active is None or current_active not in reg:
                reg[version]["active"] = True
                active_map[instrument] = version
                reg[_ACTIVE_MAP_KEY] = active_map
                self._save(reg)
                reason = (
                    f"First TradeNet deployment for {instrument}: {version}"
                    + (f" (auc_p_tp1={new_auc:+.4f})" if new_auc is not None else "")
                )
                log.info(reason)
                return True, reason

            cur_metrics = reg[current_active].get("metrics", {}) or {}
            cur_auc = cur_metrics.get("auc_p_tp1")

            if not force and new_auc is not None and cur_auc is not None:
                if new_auc < cur_auc - max_regression:
                    reason = (
                        f"TradeNet promotion BLOCKED: {version} auc_p_tp1={new_auc:+.4f} "
                        f"< current {current_active} auc_p_tp1={cur_auc:+.4f} - {max_regression} "
                        f"(regression={cur_auc - new_auc:.4f}). Use force=True to override."
                    )
                    log.warning(reason)
                    return False, reason

            reg[current_active]["active"] = False
            reg[version]["active"] = True
            active_map[instrument] = version
            reg[_ACTIVE_MAP_KEY] = active_map
            self._save(reg)
            tag = ""
            if new_auc is not None and cur_auc is not None:
                tag = f" (auc_p_tp1={new_auc:+.4f} over {cur_auc:+.4f})"
            reason = f"Promoted TradeNet {version} for {instrument}{tag} over {current_active}"
            log.info(reason)
            return True, reason

    def get_active(self) -> Optional[str]:
        """Legacy: returns active version for any instrument (first match in __active__).
        Prefer get_active_version(instrument) for new callers."""
        reg = self._load()
        active_map = reg.get(_ACTIVE_MAP_KEY, {})
        if active_map:
            return next(iter(active_map.values()))
        for v, entry in reg.items():
            if _is_meta_key(v) or not isinstance(entry, dict):
                continue
            if entry.get("active", False):
                return v
        return None

    def get_active_version(self, instrument: str) -> Optional[str]:
        reg = self._load()
        active_map = reg.get(_ACTIVE_MAP_KEY, {})
        v = active_map.get(instrument)
        if v:
            return v
        # Legacy fallback: scan entries
        for k, entry in reg.items():
            if _is_meta_key(k) or not isinstance(entry, dict):
                continue
            if entry.get("active") and entry.get("instrument") == instrument:
                return k
        return None

    def get_active_entry(self, instrument: Optional[str] = None) -> Optional[dict]:
        reg = self._load()
        if instrument:
            v = self.get_active_version(instrument)
            return reg.get(v) if v else None
        # Legacy: first active entry
        for k, entry in reg.items():
            if _is_meta_key(k) or not isinstance(entry, dict):
                continue
            if entry.get("active", False):
                return entry
        return None

    def rollback_tradenet(self, instrument: str) -> tuple[bool, str]:
        reg = self._load()
        active_map = reg.get(_ACTIVE_MAP_KEY, {})
        current = active_map.get(instrument)
        if not current:
            return False, f"No active TradeNet version for instrument {instrument!r}"
        candidates = sorted(
            [k for k, v in reg.items()
             if not _is_meta_key(k) and isinstance(v, dict)
             and v.get("instrument") == instrument and k != current],
            key=lambda k: reg[k].get("trained_at", ""),
            reverse=True,
        )
        if not candidates:
            return False, "no_history"
        return self.promote(candidates[0], instrument=instrument, force=True)

    def list_versions(self) -> list[dict]:
        reg = self._load()
        return sorted(
            [v for k, v in reg.items() if not _is_meta_key(k) and isinstance(v, dict)],
            key=lambda x: x.get("trained_at", ""),
            reverse=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MODULE-LEVEL SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_registry          = ModelRegistry.from_prod_config()  # GOV-3 margin read fail-fast from config
_gaussian_registry = GaussianModelRegistry()
_zone_gate_registry = ZoneGateRegistry()
_rr_registry        = RRModelRegistry()
_tradenet_registry  = TradeNetRegistry()


def register(model_name: str, eval_result: EvalResult) -> ModelEntry:
    return _registry.register(model_name, eval_result)


def try_promote(model_name: str) -> tuple[bool, str]:
    return _registry.try_promote(model_name)


def get_active() -> Optional[str]:
    return _registry.get_active()


def print_leaderboard(n: int = 10) -> None:
    _registry.print_leaderboard(n)


# Gaussian registry convenience functions
def register_gaussian(version: str, model_file: str, feature_schema: list, metrics: dict,
                      instrument: Optional[str] = None,
                      run_id: Optional[str] = None) -> dict:
    return _gaussian_registry.register_gaussian(version, model_file, feature_schema, metrics,
                                                instrument=instrument, run_id=run_id)


def promote_gaussian(
    version: str,
    *,
    instrument: Optional[str] = None,
    force: bool = False,
    max_regression: float = 0.01,
) -> tuple[bool, str]:
    return _gaussian_registry.promote_gaussian(
        version, instrument=instrument, force=force, max_regression=max_regression
    )


def get_active_gaussian() -> Optional[str]:
    return _gaussian_registry.get_active_gaussian()


def get_active_version(instrument: str) -> Optional[str]:
    return _gaussian_registry.get_active_version(instrument)


def rollback_gaussian(instrument: str) -> tuple[bool, str]:
    return _gaussian_registry.rollback_gaussian(instrument)


def print_gaussian_leaderboard() -> None:
    _gaussian_registry.print_gaussian_leaderboard()


# Zone Gate registry convenience functions
def register_zone_gate(
    version: str,
    model_file: str,
    n_zones: int,
    n_clusters_requested: int,
    feature_order: list,
) -> dict:
    return _zone_gate_registry.register(
        version, model_file, n_zones, n_clusters_requested, feature_order
    )


def promote_zone_gate(version: str) -> tuple[bool, str]:
    return _zone_gate_registry.promote(version)


def get_active_zone_gate() -> Optional[str]:
    return _zone_gate_registry.get_active()


def get_active_zone_gate_entry() -> Optional[dict]:
    return _zone_gate_registry.get_active_entry()


def list_zone_gate_versions() -> list[dict]:
    return _zone_gate_registry.list_versions()


# RR Model registry convenience functions
def register_rr_dataset(
    version: str,
    dataset_file: str,
    n_samples: int,
    n_features: int,
    instrument: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    return _rr_registry.register_dataset(version, dataset_file, n_samples, n_features,
                                          instrument=instrument, run_id=run_id)


def register_rr_model(version: str, model_file: str, metrics: dict) -> dict:
    return _rr_registry.register_model(version, model_file, metrics)


def promote_rr(version: str) -> tuple[bool, str]:
    return _rr_registry.promote(version)


def get_active_rr() -> Optional[str]:
    return _rr_registry.get_active()


def get_active_rr_entry() -> Optional[dict]:
    return _rr_registry.get_active_entry()


def list_rr_versions() -> list[dict]:
    return _rr_registry.list_versions()


# TradeNet registry convenience functions
def register_tradenet(version: str, model_file: str, metrics: dict,
                      instrument: Optional[str] = None,
                      run_id: Optional[str] = None) -> dict:
    return _tradenet_registry.register(version, model_file, metrics,
                                       instrument=instrument, run_id=run_id)


def promote_tradenet(
    version: str,
    *,
    instrument: Optional[str] = None,
    force: bool = False,
    max_regression: float = 0.01,
) -> tuple[bool, str]:
    return _tradenet_registry.promote(
        version, instrument=instrument, force=force, max_regression=max_regression
    )


def get_active_tradenet(instrument: Optional[str] = None) -> Optional[str]:
    if instrument:
        return _tradenet_registry.get_active_version(instrument)
    return _tradenet_registry.get_active()


def get_active_tradenet_entry(instrument: Optional[str] = None) -> Optional[dict]:
    return _tradenet_registry.get_active_entry(instrument)


def get_active_tradenet_version(instrument: str) -> Optional[str]:
    return _tradenet_registry.get_active_version(instrument)


def rollback_tradenet(instrument: str) -> tuple[bool, str]:
    return _tradenet_registry.rollback_tradenet(instrument)


def list_tradenet_versions() -> list[dict]:
    return _tradenet_registry.list_versions()

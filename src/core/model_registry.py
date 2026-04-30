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

    def __init__(self, models_dir: Path = MODELS_DIR) -> None:
        self.dir      = models_dir
        self.reg_path = models_dir / "registry.json"
        self.act_path = models_dir / "active.txt"
        self.dir.mkdir(parents=True, exist_ok=True)

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

            if new_score > current_score + PROMOTION_MARGIN:
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
                    f"Δ={new_score - current_score:+.4f} < margin={PROMOTION_MARGIN}"
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
            return json.loads(self.reg_path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning(f"Gaussian registry load failed: {e}")
            return {}

    def _save(self, reg: dict) -> None:
        # GOV-3: guard then atomic rename
        _assert_single_active(reg, active_key="active")
        _save_atomic(self.reg_path, reg)

    def register_gaussian(
        self,
        version: str,
        model_file: str,
        feature_schema: list,
        metrics: dict,
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
        force: bool = False,
        max_regression: float = 0.01,
    ) -> tuple[bool, str]:
        """
        Promote a Gaussian version to active.

        FIX 3: Compares against current active model metrics.
        Blocks promotion if new model regresses by more than max_regression
        on corr_expected_rr (unless force=True).

        Parameters
        ----------
        version        : version to promote
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

            # Derive current_active from registry scan (single source of truth inside lock)
            active_versions = [k for k, v in reg.items() if v.get("active", False)]
            current_active  = active_versions[0] if active_versions else None

            # First deployment — no comparison needed
            if current_active is None:
                reg[version]["active"] = True
                self._save(reg)
                reason = f"First Gaussian deployment: {version} (corr={new_corr:+.4f})"
                log.info(reason)
                return True, reason

            if current_active not in reg:
                reg[version]["active"] = True
                self._save(reg)
                reason = f"Promoted Gaussian {version} (current active not found in registry)"
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

            # Deactivate current, activate new — all in-memory before write
            reg[current_active]["active"] = False
            reg[version]["active"] = True
            # Single atomic write; GOV-3 guard inside _save()
            self._save(reg)
            reason = (
                f"Promoted Gaussian {version} (corr={new_corr:+.4f} cal={new_cal:.4f}) "
                f"over {current_active} (corr={cur_corr:+.4f} cal={cur_cal:.4f})"
            )
            log.info(reason)
            return True, reason

    def get_active_gaussian(self) -> Optional[str]:
        reg = self._load()
        for version, entry in reg.items():
            if entry.get("active", False):
                return version
        return None

    def list_gaussian(self) -> list[dict]:
        reg = self._load()
        return sorted(reg.values(), key=lambda x: x.get("trained_at", ""), reverse=True)

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
# MODULE-LEVEL SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_registry = ModelRegistry()
_gaussian_registry = GaussianModelRegistry()


def register(model_name: str, eval_result: EvalResult) -> ModelEntry:
    return _registry.register(model_name, eval_result)


def try_promote(model_name: str) -> tuple[bool, str]:
    return _registry.try_promote(model_name)


def get_active() -> Optional[str]:
    return _registry.get_active()


def print_leaderboard(n: int = 10) -> None:
    _registry.print_leaderboard(n)


# Gaussian registry convenience functions
def register_gaussian(version: str, model_file: str, feature_schema: list, metrics: dict) -> dict:
    return _gaussian_registry.register_gaussian(version, model_file, feature_schema, metrics)


def promote_gaussian(version: str) -> tuple[bool, str]:
    return _gaussian_registry.promote_gaussian(version)


def get_active_gaussian() -> Optional[str]:
    return _gaussian_registry.get_active_gaussian()


def print_gaussian_leaderboard() -> None:
    _gaussian_registry.print_gaussian_leaderboard()

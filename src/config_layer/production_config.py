"""
production_config.py
═══════════════════════════════════════════════════════════════════════════════
PRODUCTION CONFIG — Registry-driven, hash-verified, auditable.

Architecture contract (hardened):
  - PROD_VERSION is resolved automatically from configs/production/ACTIVE_VERSION
    (written by PromotionManager on every successful promotion).
  - The hardcoded fallback below is used only when no pointer file exists
    (e.g. fresh clone, first run before any promotion).
  - PROD_PARAMS are NOT hardcoded. They are loaded from the registry JSON.
    This eliminates the dual-source drift problem.
  - get_prod_config(instrument) loads from registry → verifies hash → builds config.
  - If registry file is missing → RuntimeError (never run with engine defaults).
  - If config_hash mismatch → RuntimeError (tampering detected).
  - load_prod_config_from_registry() is the shared loader for both live and replay.

Version history:
  v1_multi_2026_03 — initial multi-instrument tuned config (2026-03-24)

Usage:
    from production_config import get_prod_config, PROD_VERSION

    cfg = get_prod_config("EURUSD")   # FOREX profile + prod overrides
    cfg = get_prod_config("BTCUSDT")  # CRYPTO profile + prod overrides

    # Historical replay
    cfg = load_prod_config_from_registry("v1_multi_2026_03", "EURUSD")
═══════════════════════════════════════════════════════════════════════════════
"""

from __future__ import annotations

import hashlib
import json
import warnings
from datetime import time as dt_time
from pathlib import Path
from typing import Optional

from config_layer.config_builder import ConfigBuilder
from config_layer.crt_engine_v2 import CRTConfig


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTION VERSION
# Resolved automatically from configs/production/ACTIVE_VERSION (pointer file
# written by PromotionManager._write_to_registry on every promotion).
# Hardcoded string below is the fallback for fresh checkouts with no pointer.
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTION_REGISTRY_DIR: str = "configs/production"

_FALLBACK_PROD_VERSION: str = "v1_multi_2026_03"
_ACTIVE_VERSION_FILE: Path = Path(PRODUCTION_REGISTRY_DIR) / "ACTIVE_VERSION"

def _resolve_prod_version() -> str:
    """Return version from pointer file, or fall back to hardcoded default."""
    try:
        if _ACTIVE_VERSION_FILE.exists():
            resolved = _ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
            if resolved:
                return resolved
    except OSError:
        pass
    return _FALLBACK_PROD_VERSION

PROD_VERSION: str = _resolve_prod_version()


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRITY CHECK
# ─────────────────────────────────────────────────────────────────────────────

def _compute_params_hash(params: dict) -> str:
    """Compute SHA-256 of params dict (sorted keys for determinism)."""
    canonical = json.dumps(params, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verify_config_hash(params: dict, stored_hash: str) -> None:
    """
    Verify that params match the stored hash.
    Raises RuntimeError if mismatch — indicates accidental edit or tampering.
    """
    computed = _compute_params_hash(params)
    if computed != stored_hash:
        raise RuntimeError(
            f"Config integrity check FAILED.\n"
            f"  Stored hash:   {stored_hash}\n"
            f"  Computed hash: {computed}\n"
            f"  The production registry file may have been manually edited.\n"
            f"  Use promotion_manager.py to update configs safely."
        )


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_registry_path(version: str, registry_dir: str = PRODUCTION_REGISTRY_DIR) -> Path:
    return Path(registry_dir) / f"{version}.json"


def _assert_registry_exists(path: Path) -> None:
    """Fail fast if the registry file is missing — never run with engine defaults."""
    if not path.exists():
        available = sorted(path.parent.glob("*.json")) if path.parent.exists() else []
        available_versions = [p.stem for p in available if not p.name.startswith("promotion_log")]
        raise RuntimeError(
            f"\n{'═'*60}\n"
            f"  ❌ PRODUCTION CONFIG NOT FOUND\n\n"
            f"  Expected: {path}\n\n"
            f"  This is a hard stop. Never run with engine defaults in\n"
            f"  execution mode — that bypasses all tuning and validation.\n\n"
            f"  To fix:\n"
            f"    1. Check that production_configs/ exists.\n"
            f"    2. Run: python promotion_manager.py list\n"
            f"    3. Update PROD_VERSION in production_config.py.\n\n"
            f"  Available versions: {available_versions or 'none'}\n"
            f"{'═'*60}\n"
        )


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def get_prod_config(instrument: str) -> CRTConfig:
    """
    Build the production CRTConfig for the given instrument.

    Loads params from the production registry (PROD_VERSION).
    Verifies config hash before building — detects accidental edits.
    Market router automatically applies FOREX or CRYPTO base profile.

    Parameters
    ----------
    instrument : str
        Trading instrument (e.g. 'EURUSD', 'BTCUSDT').

    Returns
    -------
    CRTConfig
        Frozen, immutable config. Ready for CRTEngine or BacktestRunner.

    Raises
    ------
    RuntimeError
        If production registry file is missing (never run with defaults).
    RuntimeError
        If config_hash mismatch (file was tampered).
    """
    return load_prod_config_from_registry(PROD_VERSION, instrument)


def get_prod_version() -> str:
    """Return the current production version string."""
    return PROD_VERSION


def get_prod_metadata() -> dict:
    """
    Return the full production registry entry for the current version.
    Includes params, validation_summary, hash, and notes.
    """
    registry_path = _get_registry_path(PROD_VERSION)
    _assert_registry_exists(registry_path)
    with open(registry_path) as f:
        return json.load(f)


def load_prod_config_from_registry(
    version: str,
    instrument: str,
    registry_dir: str = PRODUCTION_REGISTRY_DIR,
    verify_hash: bool = True,
) -> CRTConfig:
    """
    Load a versioned config from the production registry and build a CRTConfig.

    Parameters
    ----------
    version : str
        Version string, e.g. 'v1_multi_2026_03'.
    instrument : str
        Trading instrument.
    registry_dir : str
        Path to the production_configs/ folder.
    verify_hash : bool
        If True (default), verifies config_hash before building.
        Set False only for debugging — never in production.

    Returns
    -------
    CRTConfig
        Frozen config built from the stored params.

    Raises
    ------
    RuntimeError
        If the registry file is missing.
    RuntimeError
        If config_hash verification fails.
    """
    registry_path = _get_registry_path(version, registry_dir)
    _assert_registry_exists(registry_path)

    with open(registry_path) as f:
        data = json.load(f)

    params = data.get("params", {})
    if not params:
        raise RuntimeError(
            f"Production registry {registry_path} has no 'params' key.\n"
            "This file may be corrupted. Re-run promotion_manager.py to rebuild."
        )

    # ── Hash verification ──────────────────────────────────────────────────
    if verify_hash:
        stored_hash = data.get("config_hash")
        if stored_hash:
            _verify_config_hash(params, stored_hash)
        else:
            warnings.warn(
                f"Registry {registry_path} has no 'config_hash' field. "
                "Run promotion_manager.py to regenerate with hash.",
                stacklevel=2,
            )

    # ── Merge crt_engine section into overrides ────────────────────────────
    # crt_engine.* fields map 1-to-1 with CRTConfig fields. params section
    # wins over crt_engine defaults (tuned params take precedence).
    crt_engine = data.get("crt_engine", {})
    if crt_engine:
        coerced = _coerce_crt_engine(crt_engine)
        merged = {**coerced, **params}   # params (tuned) wins over crt_engine defaults
    else:
        merged = params

    return ConfigBuilder.build(instrument, overrides=merged)


def _coerce_crt_engine(raw: dict) -> dict:
    """
    Coerce JSON-native types in the crt_engine section to the types expected
    by CRTConfig fields (tuples, datetime.time objects, etc.).
    """
    result = dict(raw)

    # conf_weights: JSON list → tuple (CRTConfig expects tuple)
    if "conf_weights" in result and isinstance(result["conf_weights"], list):
        result["conf_weights"] = tuple(result["conf_weights"])

    # sizing_bands: JSON list-of-lists → list[tuple]
    if "sizing_bands" in result and isinstance(result["sizing_bands"], list):
        result["sizing_bands"] = [
            tuple(band) for band in result["sizing_bands"]
        ]

    # session_windows: JSON {"NAME": ["HH:MM", "HH:MM"]} → {name: (time, time)}
    if "session_windows" in result and isinstance(result["session_windows"], dict):
        parsed = {}
        for name, bounds in result["session_windows"].items():
            h0, m0 = map(int, bounds[0].split(":"))
            h1, m1 = map(int, bounds[1].split(":"))
            parsed[name] = (dt_time(h0, m0), dt_time(h1, m1))
        result["session_windows"] = parsed

    return result


def get_prod_section(section: str, version: Optional[str] = None) -> dict:
    """
    Return a raw dict section from the production config JSON.

    Used by subsystems (rr_pattern_miner, crt_gaussian_scorer, llama_gate, etc.)
    to load their own config blocks without going through CRTConfig.

    Parameters
    ----------
    section : str
        Top-level key in the JSON, e.g. 'rr_model', 'gaussian_scorer',
        'tuner', 'portfolio', 'llama_gate', 'training'.
    version : str | None
        Config version. Defaults to PROD_VERSION.

    Returns
    -------
    dict
        The section dict.

    Raises
    ------
    RuntimeError
        If the registry file is missing or the section is absent.
    """
    v = version or PROD_VERSION
    registry_path = _get_registry_path(v)
    _assert_registry_exists(registry_path)
    with open(registry_path) as f:
        data = json.load(f)
    if section not in data:
        raise RuntimeError(
            f"Section '{section}' not found in production config {registry_path}.\n"
            f"Available sections: {sorted(k for k in data if not k.startswith('_'))}\n"
            f"Add the missing section to v1_multi_2026_03.json."
        )
    return data[section]


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("  Production Config — Smoke Test")
    print("═" * 60)

    print(f"\n  Version : {PROD_VERSION}")
    print(f"  Registry: {_get_registry_path(PROD_VERSION)}")

    try:
        meta = get_prod_metadata()
        print(f"\n  Registry entry loaded:")
        print(f"    created_at:   {meta.get('created_at', '?')[:10]}")
        h = meta.get('config_hash', '⚠️  MISSING')
        print(f"    config_hash:  {h[:24]}...")
        print(f"\n  Params:")
        for k, v in meta.get("params", {}).items():
            print(f"    {k:<35} = {v}")
    except RuntimeError as e:
        print(f"\n  ERROR: {e}")
        exit(1)

    print(f"\n  Building configs:")
    for instr in ["EURUSD", "GBPUSD", "BTCUSDT", "XAUUSD"]:
        try:
            cfg = get_prod_config(instr)
            market = ConfigBuilder.market_type(instr)
            print(
                f"    {instr:<10} [{market}]  "
                f"retest_depth_max={cfg.retest_depth_max}  "
                f"body_ratio_min={cfg.body_ratio_min}  "
                f"atr_mult={cfg.atr_multiplier_min}"
            )
        except Exception as e:
            print(f"    {instr:<10} ERROR: {e}")

    print(f"\n  Immutability check:")
    try:
        import dataclasses as _dc
        cfg = get_prod_config("EURUSD")
        cfg.body_ratio_min = 0.99
        print("  ❌ FAILED — config is mutable!")
    except (_dc.FrozenInstanceError, AttributeError):
        print("  ✅ PASSED — FrozenInstanceError raised correctly")

    print(f"\n  Hash integrity check:")
    try:
        cfg = get_prod_config("EURUSD")
        print("  ✅ PASSED — hash verified on load")
    except RuntimeError as e:
        print(f"  ❌ FAILED — {e}")

    print("\n" + "═" * 60 + "\n")
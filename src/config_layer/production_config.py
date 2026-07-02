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

import logging as _logging

from config_layer.config_builder import ConfigBuilder, _validate_override_keys
from config_layer.crt_engine_v2 import CRTConfig

_log = _logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTION VERSION
# Resolved from configs/production/ACTIVE_VERSION (pointer file written by
# PromotionManager on every successful promotion). Raises RuntimeError if the
# file is absent or empty — never silently falls back to a hardcoded version.
# ─────────────────────────────────────────────────────────────────────────────

PRODUCTION_REGISTRY_DIR: str = "configs/production"

_ACTIVE_VERSION_FILE: Path = Path(PRODUCTION_REGISTRY_DIR) / "ACTIVE_VERSION"


def get_active_version() -> str:
    """Read version from ACTIVE_VERSION pointer file. Raises RuntimeError if missing/empty."""
    if not _ACTIVE_VERSION_FILE.exists():
        raise RuntimeError(
            "No active version pointer found at configs/production/ACTIVE_VERSION. "
            "Run promotion_manager.py promote first."
        )
    try:
        resolved = _ACTIVE_VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(
            f"Failed to read configs/production/ACTIVE_VERSION: {exc}"
        ) from exc
    if not resolved:
        raise RuntimeError(
            "configs/production/ACTIVE_VERSION is empty. "
            "Run promotion_manager.py promote first."
        )
    _log.info("Active production config: %s", resolved)
    return resolved


PROD_VERSION: str = get_active_version()


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
# SESSION-OVERRIDE RESOLVERS  (single source of truth — shared by the registry
# loader, ConfigValidator, and the analysis sweeps)
#
# Instrument-scoped session expansion lets BNBUSDT run +ASIA +OFF_SESSION without
# touching ETH/BTC. See plan: trd-m6-stays-downstream.
# ─────────────────────────────────────────────────────────────────────────────

def _canon_session(raw: str) -> str:
    """
    Canonicalize a session label to the engine-facing form.

    The engine compares against `session_windows` keys ("LONDON"/"NEWYORK"/
    "ASIA"/"OVERLAP") which strip underscores, BUT the off-session sentinel must
    stay "OFF_SESSION" — "OFFSESSION" would never match and off-session trades
    would be silently rejected.
    """
    s = str(raw).upper()
    if s.replace("_", "") == "OFFSESSION":
        return "OFF_SESSION"
    return s.replace("_", "")


def resolve_allowed_sessions(
    engine_runner_cfg: Optional[dict], instrument: str
) -> Optional[tuple[str, ...]]:
    """
    Resolve the canonical allowed-session tuple for an instrument.

    A per-instrument entry in `engine_runner.allowed_sessions_overrides` (matched
    case-insensitively) wins over the global `engine_runner.allowed_sessions`.

    Returns None when nothing applies (no override match AND no global key) so the
    caller leaves the config's existing sessions untouched.
    """
    if not isinstance(engine_runner_cfg, dict):
        return None

    overrides = engine_runner_cfg.get("allowed_sessions_overrides") or {}
    if isinstance(overrides, dict) and overrides:
        lut = {str(k).upper(): v for k, v in overrides.items()}
        hit = lut.get(str(instrument).upper())
        if hit is not None:
            return tuple(_canon_session(s) for s in hit)

    if "allowed_sessions" in engine_runner_cfg:
        return tuple(_canon_session(s) for s in engine_runner_cfg["allowed_sessions"])

    return None


def resolve_breakout_disp_threshold(
    crt_engine_cfg: Optional[dict], instrument: str
) -> Optional[float]:
    """
    Resolve the per-symbol BREAKOUT displacement threshold.

    A per-instrument entry in `crt_engine.breakout_disp_threshold_overrides`
    (case-insensitive) wins over the global `crt_engine.breakout_disp_threshold`.
    Returns None when neither is present so the caller keeps its own default
    (historical 1.5). Shared by the CRT engine and ExecutionPlanner so backtest
    and live can never diverge on intent classification.
    """
    if not isinstance(crt_engine_cfg, dict):
        return None

    overrides = crt_engine_cfg.get("breakout_disp_threshold_overrides") or {}
    if isinstance(overrides, dict) and overrides:
        lut = {str(k).upper(): v for k, v in overrides.items()}
        hit = lut.get(str(instrument).upper())
        if hit is not None:
            return float(hit)

    if "breakout_disp_threshold" in crt_engine_cfg:
        return float(crt_engine_cfg["breakout_disp_threshold"])

    return None


def resolve_instrument_overrides(
    crt_engine_cfg: Optional[dict], instrument: str
) -> dict:
    """
    Resolve per-instrument CRTConfig field overrides.

    A per-instrument entry in `crt_engine.instrument_overrides` (matched
    case-insensitively) supplies CRTConfig field values that win over the global
    `params`/`crt_engine` config for that instrument ONLY. Keys are validated
    against the CRTConfig schema (fail-fast on typos); values are coerced to
    CRTConfig types (e.g. conf_weights list → tuple) via `_coerce_crt_engine`.

    Returns {} when no override applies, so the caller leaves config untouched.

    This is the governed per-instrument deployment vehicle — the SAME pattern as
    `resolve_allowed_sessions`, and the ONLY supported place for instrument-scoped
    CRT param divergence. Never hardcode per-instrument params in market_router.
    """
    if not isinstance(crt_engine_cfg, dict):
        return {}
    overrides = crt_engine_cfg.get("instrument_overrides") or {}
    if not isinstance(overrides, dict) or not overrides:
        return {}
    lut = {str(k).upper(): v for k, v in overrides.items()}
    hit = lut.get(str(instrument).upper())
    if not isinstance(hit, dict) or not hit:
        return {}
    coerced = _coerce_crt_engine(hit)
    _validate_override_keys(coerced)  # ValueError on unknown CRTConfig field
    return coerced


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
    with open(registry_path, encoding="utf-8") as f:
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

    with open(registry_path, encoding="utf-8") as f:
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
            raise RuntimeError(
                f"Registry {registry_path} has no 'config_hash' field — "
                "refusing to load an unhashed config. "
                "Run promotion_manager.py to regenerate with hash."
            )

    # ── Merge crt_engine section into overrides ────────────────────────────
    # crt_engine.* fields map 1-to-1 with CRTConfig fields. params section
    # wins over crt_engine defaults (tuned params take precedence).
    crt_engine = data.get("crt_engine", {})
    if crt_engine:
        coerced = _coerce_crt_engine(crt_engine)
        # `instrument_overrides` is a meta sub-dict (handled by
        # resolve_instrument_overrides below from the raw crt_engine), NOT a
        # CRTConfig field — strip it so ConfigBuilder key-validation doesn't reject.
        coerced.pop("instrument_overrides", None)
        merged = {**coerced, **params}   # params (tuned) wins over crt_engine defaults
    else:
        merged = dict(params)

    # ── Resolve allowed_sessions (global + per-instrument override) ─────────
    # JSON stores lowercase ("london", "new_york"); the engine wants canonical
    # keys ("LONDON", "NEWYORK", "OFF_SESSION"). resolve_allowed_sessions is the
    # single source of truth shared with ConfigValidator and the sweeps.
    _er = data.get("engine_runner", {})
    _sessions = resolve_allowed_sessions(_er, instrument)
    if _sessions is not None:
        merged["allowed_sessions"] = _sessions

    # ── Per-instrument CRT overrides (governed; applied LAST so they win) ────
    # The ONLY supported place for instrument-scoped CRT param divergence.
    # Merged after params/crt_engine/allowed_sessions so they are never
    # silently overwritten (the failure mode of hardcoding in market_router).
    _inst_over = resolve_instrument_overrides(crt_engine, instrument)
    if _inst_over:
        merged.update(_inst_over)

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
    with open(registry_path, encoding="utf-8") as f:
        data = json.load(f)
    if section not in data:
        raise RuntimeError(
            f"Section '{section}' not found in production config {registry_path}.\n"
            f"Available sections: {sorted(k for k in data if not k.startswith('_'))}\n"
            f"Add the missing section to v1_multi_2026_03.json."
        )
    return data[section]


# ─────────────────────────────────────────────────────────────────────────────
# FULL CONFIG ACCESSOR
# ─────────────────────────────────────────────────────────────────────────────

def get_full_config_dict(version: Optional[str] = None) -> dict:
    """
    Return the entire production registry JSON for the given version.

    Unlike get_prod_section(), which fetches one section, this returns every
    top-level key (params, engine_runner, crt_engine, fusion_engine, …) as a
    single dict.  Useful for config dumps and audit tooling.

    Parameters
    ----------
    version : str | None
        Config version string.  Defaults to PROD_VERSION.

    Returns
    -------
    dict
        Raw registry JSON (no hash verification — audit-only path).
    """
    v = version or PROD_VERSION
    registry_path = _get_registry_path(v)
    _assert_registry_exists(registry_path)
    with open(registry_path, encoding="utf-8") as f:
        return json.load(f)


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
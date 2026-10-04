"""
config_dumper.py
────────────────
Writes the complete resolved configuration to a timestamped JSON file
so every backtest/live run is fully auditable — no guessing which params
were actually active.
"""
from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, time as dt_time, timezone
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SERIALISATION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable values to safe equivalents."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    if isinstance(obj, dt_time):
        return obj.strftime("%H:%M")
    if isinstance(obj, datetime):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _make_serializable(dataclasses.asdict(obj))
    # numpy scalars — avoid importing numpy just for the check
    typ = type(obj)
    if typ.__module__ == "numpy":
        if hasattr(obj, "item"):
            return obj.item()
        return str(obj)
    return obj


def _asdict_serializable(dc_instance) -> dict:
    """Convert a dataclass instance to a JSON-safe dict."""
    return _make_serializable(dataclasses.asdict(dc_instance))


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def dump_config(
    config_dict: dict,
    instrument: str,
    run_id: str,
    output_dir: str = "logs/config_dumps",
) -> str:
    """
    Write config_dict to <output_dir>/<instrument>_<run_id>_config.json.

    Adds top-level metadata (dumped_at, instrument, run_id, config_version)
    and returns the absolute file path as a string.

    Parameters
    ----------
    config_dict : dict
        Assembled config — must be JSON-serializable after _make_serializable().
    instrument : str
        Trading pair / instrument name (e.g. "EURUSD").
    run_id : str
        Unique run identifier (e.g. "20260510_153045").
    output_dir : str
        Directory for dump files.  Created if absent.

    Returns
    -------
    str
        Absolute path of the written file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    filename = f"{instrument}_{run_id}_config.json"
    path = out / filename

    # Pull config_version from the dict if it's already there; else try import.
    config_version = config_dict.get("config_version")
    if config_version is None:
        try:
            from config_layer.production_config import PROD_VERSION
            config_version = PROD_VERSION
        except Exception:
            config_version = "UNKNOWN"

    metadata = {
        "dumped_at":      datetime.now(timezone.utc).isoformat(),
        "instrument":     instrument,
        "run_id":         run_id,
        "config_version": config_version,
    }

    payload = {**metadata, **_make_serializable(config_dict)}
    # Ensure top-level metadata fields are not overwritten by config_dict keys
    # that happen to share the same name.
    payload.update(metadata)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        _log.info("Full config dumped to: %s", path)
    except OSError as exc:
        _log.warning("Config dump failed (%s) — run continues.", exc)
        return str(path)

    return str(path)

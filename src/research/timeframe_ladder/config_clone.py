"""Research clones of v2_htfcrt_2026_08 for the Program 12 ladder.

The params block is copied unchanged, so the stored config_hash still verifies.
This module does not write configs/production and does not change ACTIVE_VERSION.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_ROOT = Path(__file__).resolve().parents[3]
SOURCE_REL = "configs/production/v2_htfcrt_2026_08.json"
CLONE_REL = {"H1": "configs/research/ladder_h1.json", "H4": "configs/research/ladder_h4.json"}
TIMEFRAMES = ("H1", "H4")


def source_path() -> Path:
    return _ROOT / SOURCE_REL


def load_source() -> dict:
    return json.loads(source_path().read_text(encoding="utf-8"))


def _set_path(doc: dict, path: tuple[str, ...], value) -> None:
    cur = doc
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value


def _get_path(doc: dict, path: tuple[str, ...]):
    cur = doc
    for key in path:
        cur = cur[key]
    return cur


def knob_specs(timeframe: str) -> list[tuple[tuple[str, ...], object]]:
    """§5 ladder knobs. H1 keeps the active session list. No D1 file."""
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"timeframe must be one of {TIMEFRAMES}, got {timeframe!r}")
    if timeframe == "H1":
        ttl, gap, parent_tf = 240, 180, "H4"
        sessions = ["london", "new_york", "overlap"]
    else:
        ttl, gap, parent_tf = 60, 600, "D1"
        sessions = ["london", "new_york", "overlap", "asia", "off_session"]
    return [
        (("setup", "entry_semantics"), "resting_order"),
        (("setup", "trade_ttl_candles"), ttl),
        (("crt_engine", "max_expansion_age_hours"), 0),
        (("backtest", "gap_reset_minutes"), gap),
        (("backtest", "htf_clock_basis"), "calendar"),
        (("backtest", "engine_gate_enabled"), False),
        (("backtest", "timeframe"), timeframe),
        (("parent_crt", "timeframe"), parent_tf),
        (("engine_runner", "allowed_sessions"), sessions),
    ]


def build_clone(timeframe: str) -> dict:
    source = load_source()
    clone = json.loads(json.dumps(source))
    for path, value in knob_specs(timeframe):
        _set_path(clone, path, value)
    if clone["params"] != source["params"]:
        raise RuntimeError("ladder clone changed the params block")
    if clone.get("config_hash") != source.get("config_hash"):
        raise RuntimeError("ladder clone changed config_hash")
    if clone.get("version") != source.get("version"):
        raise RuntimeError("ladder clone changed version")
    return clone


def knob_rows(timeframe: str) -> list[dict]:
    source = load_source()
    clone = build_clone(timeframe)
    rows = []
    for path, _value in knob_specs(timeframe):
        dotted = ".".join(path)
        before = _get_path(source, path)
        after = _get_path(clone, path)
        rows.append({
            "knob": dotted,
            "active": before,
            "ladder": after,
            "changed": before != after,
        })
    return rows


def format_diff_markdown() -> str:
    lines = [
        "# Ladder research clones vs v2_htfcrt_2026_08",
        "",
        "Files: `configs/research/ladder_h1.json`, `configs/research/ladder_h4.json`.",
        "The `params` block and `config_hash` are unchanged. `configs/production` is not edited.",
        "No D1 clone: one month cannot support a D1 ladder, and D1 is Step 4.",
        "",
    ]
    for tf in TIMEFRAMES:
        lines.append(f"## {tf}")
        lines.append("")
        lines.append("| Knob | Active | Ladder | Changed |")
        lines.append("|---|---|---|---|")
        for row in knob_rows(tf):
            lines.append(
                f"| `{row['knob']}` | `{row['active']}` | `{row['ladder']}` | "
                f"{'yes' if row['changed'] else 'no'} |"
            )
        lines.append("")
    lines.append(
        "Stop floor 1.5×ATR is not an engine key. It is applied in "
        "`research.timeframe_ladder.stop_floor`."
    )
    lines.append("")
    return "\n".join(lines)


def write_clones() -> None:
    for tf, rel in CLONE_REL.items():
        dest = _ROOT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(build_clone(tf), indent=2) + "\n", encoding="utf-8")
    (_ROOT / "docs" / "research" / "ladder_clone_diff.md").write_text(
        format_diff_markdown(), encoding="utf-8"
    )


def load_crt_config(clone: dict, registry_dir: str | Path, instrument: str = "XAUUSD"):
    """Write the clone as `{version}.json` so verify_hash=True accepts it."""
    from config_layer.production_config import load_prod_config_from_registry

    version = str(clone["version"])
    dest_dir = Path(registry_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / f"{version}.json").write_text(json.dumps(clone), encoding="utf-8")
    return load_prod_config_from_registry(
        version, instrument, registry_dir=str(dest_dir), verify_hash=True
    )


def _swap_identity(old, new) -> None:
    for mod in list(sys.modules.values()):
        if mod is None:
            continue
        ns = getattr(mod, "__dict__", None)
        if not isinstance(ns, dict):
            continue
        for attr, val in list(ns.items()):
            if val is old:
                ns[attr] = new


@contextmanager
def bind_research_config(clone: dict) -> Iterator[None]:
    """Point get_prod_section / get_full_config_dict at this clone for the block.

    Restores every module attribute that still points at the clone callables,
    including imports that happened inside the block.
    """
    import config_layer.production_config as pc

    orig_section = pc.get_prod_section
    orig_full = pc.get_full_config_dict

    def section(name, version=None):
        if name not in clone:
            raise RuntimeError(f"research clone has no section {name!r}")
        return clone[name]

    def full(version=None):
        return clone

    _swap_identity(orig_section, section)
    _swap_identity(orig_full, full)
    try:
        yield
    finally:
        _swap_identity(section, orig_section)
        _swap_identity(full, orig_full)

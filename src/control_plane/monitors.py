from __future__ import annotations

import glob
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

MonitorSource = Literal["jsonl_tail", "json_file", "log_regex", "file_stat"]
MonitorFormat = Literal["int", "float", "str", "duration", "timestamp"]

DEFAULT_MONITORS_PATH = "configs/control_plane/monitors.json"


@dataclass(frozen=True)
class MonitorFieldSpec:
    name: str
    label: str
    source: MonitorSource
    path_template: str
    extractor: Mapping[str, Any]
    format: MonitorFormat = "str"
    unit: str = ""


def default_monitors_path(repo_root: Path) -> Path:
    return repo_root / DEFAULT_MONITORS_PATH


def _warn(msg: str) -> None:
    print(f"[monitors] {msg}", file=sys.stderr)


def load_monitor_specs(path: Path | str) -> dict[str, tuple[MonitorFieldSpec, ...]]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        _warn(f"failed to parse {p}: {exc}")
        return {}
    if not isinstance(data, dict):
        _warn(f"{p}: expected top-level object")
        return {}
    out: dict[str, tuple[MonitorFieldSpec, ...]] = {}
    for command_id, entries in data.items():
        if not isinstance(entries, list):
            _warn(f"{p}:{command_id} must be a list, skipping")
            continue
        specs: list[MonitorFieldSpec] = []
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                _warn(f"{p}:{command_id}[{idx}] must be object, skipping")
                continue
            source = entry.get("source")
            if source not in ("jsonl_tail", "json_file", "log_regex", "file_stat"):
                _warn(f"{p}:{command_id}[{idx}] unknown source={source!r}, skipping")
                continue
            fmt = entry.get("format", "str")
            if fmt not in ("int", "float", "str", "duration", "timestamp"):
                _warn(f"{p}:{command_id}[{idx}] unknown format={fmt!r}, using str")
                fmt = "str"
            try:
                spec = MonitorFieldSpec(
                    name=str(entry["name"]),
                    label=str(entry.get("label", entry["name"])),
                    source=source,
                    path_template=str(entry.get("path_template", "")),
                    extractor=dict(entry.get("extractor", {})),
                    format=fmt,
                    unit=str(entry.get("unit", "")),
                )
            except KeyError as exc:
                _warn(f"{p}:{command_id}[{idx}] missing required key {exc}, skipping")
                continue
            specs.append(spec)
        out[command_id] = tuple(specs)
    return out


_TEMPLATE_RE = re.compile(r"\{(args\.[A-Za-z0-9_]+|run_id|repo_root|log_dir)\}")
_GLOB_CHARS = re.compile(r"[*?\[]")


def resolve_path(
    template: str,
    args: Mapping[str, Any],
    run_id: str,
    repo_root: Path,
    state_dir: Path,
) -> Path | None:
    def _sub(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.startswith("args."):
            key = token[len("args."):]
            val = args.get(key)
            return "" if val is None else str(val)
        if token == "run_id":
            return run_id
        if token == "repo_root":
            return str(repo_root)
        if token == "log_dir":
            return str((state_dir / run_id).resolve())
        return ""

    resolved = _TEMPLATE_RE.sub(_sub, template)
    if not resolved:
        return None

    p = Path(resolved)
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    else:
        p = p.resolve()

    if _GLOB_CHARS.search(str(p)):
        matches = glob.glob(str(p), recursive=True)
        if not matches:
            return None
        matches.sort(key=lambda m: Path(m).stat().st_mtime if Path(m).exists() else 0, reverse=True)
        return Path(matches[0])
    return p


def _walk_key(obj: Any, dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if part == "__len__":
            return len(cur)
        if isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(f"cannot access '{part}' on non-dict at '{dotted}'")
    return cur


_JSONPATH_TOKEN = re.compile(r"^\[(-?\d+)\]$")


def _walk_jsonpath(obj: Any, jsonpath: str) -> Any:
    if not jsonpath:
        return obj
    cur: Any = obj
    parts = [p for p in re.split(r"\.(?![^\[]*\])", jsonpath) if p]
    for part in parts:
        if part == "__len__":
            return len(cur)
        m = _JSONPATH_TOKEN.match(part)
        if m:
            cur = cur[int(m.group(1))]
            continue
        while part.startswith("["):
            m2 = re.match(r"^\[(-?\d+)\]", part)
            if not m2:
                break
            cur = cur[int(m2.group(1))]
            part = part[m2.end():]
            if not part:
                break
        if not part:
            continue
        if part == "__len__":
            return len(cur)
        head, _, tail = part.partition("[")
        if head:
            if isinstance(cur, dict):
                cur = cur[head]
            else:
                raise KeyError(f"cannot access '{head}' on non-dict")
        while tail:
            m3 = re.match(r"^(-?\d+)\]", tail)
            if not m3:
                break
            cur = cur[int(m3.group(1))]
            tail = tail[m3.end():]
            if tail.startswith("["):
                tail = tail[1:]
            else:
                break
    return cur


def _extract_jsonl_tail(path: Path, cfg: Mapping[str, Any]) -> Any:
    key = str(cfg.get("key", ""))
    if not key:
        raise ValueError("jsonl_tail requires 'key'")
    size = path.stat().st_size
    read_from = max(0, size - 65536)
    with path.open("rb") as fh:
        fh.seek(read_from)
        chunk = fh.read()
    text = chunk.decode("utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("empty jsonl")
    last = json.loads(lines[-1])
    return _walk_key(last, key)


def _extract_json_file(path: Path, cfg: Mapping[str, Any]) -> Any:
    jsonpath = str(cfg.get("jsonpath", ""))
    data = json.loads(path.read_text(encoding="utf-8"))
    return _walk_jsonpath(data, jsonpath)


def _extract_log_regex(path: Path, cfg: Mapping[str, Any]) -> Any:
    pattern = cfg.get("pattern")
    if not pattern:
        raise ValueError("log_regex requires 'pattern'")
    group = int(cfg.get("group", 1))
    scan = cfg.get("scan", "tail_last")
    size = path.stat().st_size
    if scan == "first":
        read_from = 0
        read_size = min(size, 262144)
    else:
        read_from = max(0, size - 262144)
        read_size = size - read_from
    with path.open("rb") as fh:
        fh.seek(read_from)
        chunk = fh.read(read_size)
    text = chunk.decode("utf-8", errors="replace")
    regex = re.compile(pattern, re.MULTILINE)
    matches = list(regex.finditer(text))
    if not matches:
        raise ValueError("no regex match")
    target = matches[0] if scan == "first" else matches[-1]
    return target.group(group)


def _extract_file_stat(path: Path, cfg: Mapping[str, Any]) -> Any:
    attr = cfg.get("attr", "size")
    if attr == "exists":
        return path.exists()
    st = path.stat()
    if attr == "size":
        return st.st_size
    if attr == "mtime":
        return st.st_mtime
    raise ValueError(f"unknown file_stat attr={attr!r}")


_EXTRACTORS = {
    "jsonl_tail": _extract_jsonl_tail,
    "json_file": _extract_json_file,
    "log_regex": _extract_log_regex,
    "file_stat": _extract_file_stat,
}


def _format_value(value: Any, fmt: MonitorFormat) -> Any:
    if value is None:
        return None
    try:
        if fmt == "int":
            return int(float(value))
        if fmt == "float":
            return round(float(value), 6)
        if fmt == "timestamp":
            if isinstance(value, (int, float)):
                return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
            return str(value)
        if fmt == "duration":
            secs = float(value)
            if secs < 0:
                secs = 0.0
            total = int(secs)
            h, rem = divmod(total, 3600)
            m, s = divmod(rem, 60)
            return f"{h}:{m:02d}:{s:02d}"
        return str(value)
    except Exception:
        return value


def extract_fields(
    specs: tuple[MonitorFieldSpec, ...],
    args: Mapping[str, Any],
    run_id: str,
    repo_root: Path,
    state_dir: Path,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in specs:
        entry: dict[str, Any] = {
            "name": spec.name,
            "label": spec.label,
            "value": None,
            "unit": spec.unit,
            "format": spec.format,
        }
        try:
            resolved = resolve_path(spec.path_template, args, run_id, repo_root, state_dir)
            if resolved is None or not resolved.exists():
                raise FileNotFoundError(f"path not found: {spec.path_template}")
            raw = _EXTRACTORS[spec.source](resolved, spec.extractor)
            entry["value"] = _format_value(raw, spec.format)
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        out.append(entry)
    return out

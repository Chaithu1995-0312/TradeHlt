"""
parquet_store.py — derived Parquet projections over append-only JSONL corpora.

Sibling of `jsonl_writer.py`. The JSONL file stays the SYSTEM OF RECORD; a Parquet
projection is a derived, regenerable sidecar that exists purely so research readers can
prune columns instead of parsing every byte. Nothing here writes JSONL, mutates a source,
or deletes anything.

Why this module exists (measured, not assumed): full-scan JSON parse already runs at
~40 s/GB, so raw scan speed is NOT the bottleneck. The corpora this targets are wide and
sparse — `*_crt_telemetry.jsonl` carries 17 of 28 columns absent in >50% of rows across
disjoint `kind` values — and readers routinely want 3 of 44 columns. Column pruning and a
typed schema are the only benefits Parquet uniquely provides; that is the whole mandate.

Three guarantees:

  1. LOSSLESS. `compact_jsonl(..., verify=True)` reconstructs every record and compares it
     to the source line. Key ABSENCE is distinguished from an explicit JSON `null` (a
     presence mask is emitted only for columns where both occur), so a round-tripped record
     equals the original dict, not a null-padded superset of it.
  2. NEVER STALE. The sidecar manifest pins the source's size/mtime/sha256. A projection
     that does not match its source is ignored — `iter_records` falls back to `iter_jsonl`.
     A projection can never serve data its source does not contain.
  3. OPTIONAL. `pyarrow` sits behind an import guard (conventions.md 3.2). Absent pyarrow,
     every read path degrades to JSONL instead of raising.

Type policy is decided ONCE at conversion time from a full scan of the source and recorded
in the manifest, so readers reconstruct deterministically rather than re-inferring.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Sequence

from utils.jsonl_writer import iter_jsonl

logger = logging.getLogger("parquet_store")

try:  # optional-import guard (conventions.md 3.2)
    import pyarrow as pa
    import pyarrow.parquet as pq
    import pyarrow.dataset as ds

    _PARQUET_AVAILABLE = True
    _PARQUET_IMPORT_ERROR: "Exception | None" = None
except Exception as _exc:  # noqa: BLE001 - absence is a supported state, not an error
    pa = None  # type: ignore[assignment]
    pq = None  # type: ignore[assignment]
    ds = None  # type: ignore[assignment]
    _PARQUET_AVAILABLE = False
    _PARQUET_IMPORT_ERROR = _exc

# 1.1 adds the optional `<key>.__null__` companion column for FLATTEN parents that carry an
# explicit JSON null, and persists the `verified` block into the on-disk manifest. Both are
# additive: a 1.0 manifest lacks `null_mask`/`verified` and decodes exactly as it always did.
MANIFEST_VERSION = "1.1"
_CHUNK_ROWS = 50_000
_PRESENT_SUFFIX = "__present__"
# Companion to _PRESENT_SUFFIX for FLATTEN columns only. `__present__` separates ABSENT from
# PRESENT; it cannot separate an explicit JSON `null` parent from a real dict, because a null
# parent and an all-null dict flatten to byte-identical child columns. Emitted only when the
# source actually carries a null parent, so projections without one are unchanged.
_NULL_SUFFIX = "__null__"
_HASH_CHUNK = 4 << 20

# Projection freshness states.
FRESH = "FRESH"              # projection exists and matches its source
STALE = "STALE"              # projection exists but the source moved on -> ignore it
ABSENT = "ABSENT"            # no projection built yet
UNAVAILABLE = "UNAVAILABLE"  # pyarrow not installed -> JSONL only

# Column policies (recorded per column in the manifest).
_SCALAR = "scalar"
_JSON = "json"
_LIST_F64 = "list_f64"
_FLATTEN = "flatten"


def parquet_available() -> bool:
    """True when pyarrow imported. Callers degrade to JSONL when False."""
    return _PARQUET_AVAILABLE


def projection_path(src: "Path | str") -> Path:
    """Sidecar location for *src*: `foo.jsonl` -> `foo.parquet` (file or dataset dir)."""
    return Path(src).with_suffix(".parquet")


def manifest_path(src: "Path | str") -> Path:
    """Sidecar manifest for *src*: `foo.jsonl` -> `foo.parquet.manifest.json`."""
    return Path(str(projection_path(src)) + ".manifest.json")


# --------------------------------------------------------------------------- #
# source fingerprinting
# --------------------------------------------------------------------------- #
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(_HASH_CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _fingerprint(path: Path, *, with_hash: bool) -> dict:
    st = path.stat()
    fp: dict[str, Any] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns}
    if with_hash:
        fp["sha256"] = _sha256(path)
    return fp


def projection_status(src: "Path | str", *, strict: bool = False) -> str:
    """FRESH / STALE / ABSENT / UNAVAILABLE for the projection of *src*.

    Default compares size+mtime (cheap on multi-GB corpora). `strict=True` re-hashes the
    source — use it when correctness matters more than latency.
    """
    if not _PARQUET_AVAILABLE:
        return UNAVAILABLE
    src = Path(src)
    mpath = manifest_path(src)
    if not src.exists() or not mpath.exists() or not projection_path(src).exists():
        return ABSENT
    try:
        manifest = json.loads(mpath.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return STALE
    recorded = manifest.get("source", {})
    current = _fingerprint(src, with_hash=strict)
    if recorded.get("size") != current["size"] or recorded.get("mtime_ns") != current["mtime_ns"]:
        return STALE
    if strict and recorded.get("sha256") != current.get("sha256"):
        return STALE
    return FRESH


# --------------------------------------------------------------------------- #
# pass 1 — decide the schema from the whole source
# --------------------------------------------------------------------------- #
def _scalar_kind(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    return "other"


class _ColumnProbe:
    """Accumulates what a single key looks like across the whole source."""

    def __init__(self) -> None:
        self.rows_present = 0
        self.explicit_null = False
        self.scalar_kinds: set[str] = set()
        self.saw_dict = False
        self.saw_list = False
        self.numeric_list_only = True
        self.dict_keysets: set[tuple] = set()
        self.dict_scalar_only = True
        # Key ORDER of flattened dicts is load-bearing: replay_memory_engine builds its
        # feature vector with `features_dict.values()`, so re-emitting the same keys in a
        # different order silently scrambles the vector. Track first-seen order, and
        # whether every occurrence agreed on it.
        self.dict_key_orders: set[tuple] = set()
        self.first_key_order: "tuple | None" = None

    def observe(self, v: Any) -> None:
        self.rows_present += 1
        if v is None:
            self.explicit_null = True
            return
        if isinstance(v, dict):
            self.saw_dict = True
            self.dict_keysets.add(tuple(sorted(v.keys())))
            order = tuple(v.keys())
            self.dict_key_orders.add(order)
            if self.first_key_order is None:
                self.first_key_order = order
            if any(isinstance(x, (dict, list)) for x in v.values()):
                self.dict_scalar_only = False
            return
        if isinstance(v, list):
            self.saw_list = True
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
                self.numeric_list_only = False
            return
        self.scalar_kinds.add(_scalar_kind(v))

    def policy(self) -> str:
        """Resolve to one column policy. Ambiguity always degrades to lossless JSON text."""
        if sum([self.saw_dict, self.saw_list, bool(self.scalar_kinds)]) > 1:
            return _JSON
        if self.saw_dict:
            # Flattening is only safe (and only enables pruning) when every occurrence
            # carries the SAME keys and every leaf is a scalar.
            if len(self.dict_keysets) == 1 and self.dict_scalar_only:
                return _FLATTEN
            return _JSON
        if self.saw_list:
            return _LIST_F64 if self.numeric_list_only else _JSON
        kinds = self.scalar_kinds
        if not kinds:
            return _SCALAR  # all-null (or always-absent) column
        if kinds <= {"bool"} or kinds <= {"int"} or kinds <= {"float"} or kinds <= {"str"}:
            return _SCALAR
        # int+float in one column would silently coerce ints to floats -> not round-trippable.
        return _JSON


def _kind_name(probe: _ColumnProbe) -> str:
    kinds = probe.scalar_kinds
    if kinds <= {"bool"} and kinds:
        return "bool"
    if kinds <= {"int"} and kinds:
        return "int64"
    if kinds <= {"float"} and kinds:
        return "float64"
    return "string"


def _scan_source(src: Path, skip_predicate: "Callable[[dict], bool] | None") -> dict:
    """Full pass over *src* deciding the column policy for every key."""
    probes: dict[str, _ColumnProbe] = {}
    child_probes: dict[str, dict[str, _ColumnProbe]] = {}
    rows = 0
    for rec in iter_jsonl(src):
        if not isinstance(rec, dict):
            continue
        if skip_predicate is not None and skip_predicate(rec):
            continue
        rows += 1
        for k, v in rec.items():
            probes.setdefault(k, _ColumnProbe()).observe(v)
            if isinstance(v, dict):
                bucket = child_probes.setdefault(k, {})
                for ck, cv in v.items():
                    bucket.setdefault(ck, _ColumnProbe()).observe(cv)
    return {"rows": rows, "probes": probes, "child_probes": child_probes}


def _build_plan(scan: dict) -> dict:
    """Turn probes into a serialisable column plan (the manifest's `columns` block)."""
    rows = scan["rows"]
    plan: dict[str, dict] = {}
    for key, probe in scan["probes"].items():
        policy = probe.policy()
        # Three null regimes, and a reader MUST be told which one it is looking at:
        #   always present            -> a null column value is an explicit JSON null
        #   sometimes absent, never null -> a null column value means the key was absent
        #   both                      -> ambiguous, so carry a presence mask
        always_present = probe.rows_present == rows
        entry: dict[str, Any] = {
            "policy": policy,
            "always_present": always_present,
            "mask": not always_present and probe.explicit_null,
        }
        if policy == _FLATTEN:
            children = scan["child_probes"].get(key, {})
            # SOURCE order, never sorted — see _ColumnProbe.dict_key_orders for why.
            order = list(probe.first_key_order or sorted(children.keys()))
            entry["children"] = order
            entry["key_order_stable"] = len(probe.dict_key_orders) <= 1
            entry["child_types"] = {ck: _kind_name(children[ck]) for ck in order if ck in children}
            # The parent dict itself can be absent; its children cannot express that.
            entry["mask"] = not always_present
            # ...nor can they express a parent that is present but explicitly null: it
            # flattens to the same all-null children a real all-null dict produces. That is
            # the third null regime named above, and it needs its own bit.
            entry["null_mask"] = probe.explicit_null
        elif policy == _SCALAR:
            entry["type"] = _kind_name(probe)
        plan[key] = entry
    return plan


def _arrow_type(name: str):
    return {
        "bool": pa.bool_,
        "int64": pa.int64,
        "float64": pa.float64,
        "string": pa.string,
    }.get(name, pa.string)()


def _arrow_schema(plan: dict):
    fields = []
    for key, entry in plan.items():
        policy = entry["policy"]
        if policy == _SCALAR:
            fields.append(pa.field(key, _arrow_type(entry.get("type", "string"))))
        elif policy == _JSON:
            fields.append(pa.field(key, pa.string()))
        elif policy == _LIST_F64:
            fields.append(pa.field(key, pa.list_(pa.float64())))
        elif policy == _FLATTEN:
            for child in entry["children"]:
                fields.append(
                    pa.field(f"{key}.{child}", _arrow_type(entry["child_types"].get(child, "string")))
                )
        if entry.get("mask"):
            fields.append(pa.field(f"{key}.{_PRESENT_SUFFIX}", pa.bool_()))
        if entry.get("null_mask"):
            fields.append(pa.field(f"{key}.{_NULL_SUFFIX}", pa.bool_()))
    return pa.schema(fields)


# --------------------------------------------------------------------------- #
# pass 2 — encode
# --------------------------------------------------------------------------- #
def _json_dump(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def _encode_scalar(v: Any, type_name: str) -> Any:
    if v is None:
        return None
    if type_name == "string" and not isinstance(v, str):
        return _json_dump(v)
    if type_name == "float64":
        f = float(v)
        # NaN/Inf are not representable in JSON text; keep them out of typed columns.
        return f if math.isfinite(f) else None
    return v


def _encode_chunk(records: Sequence[dict], plan: dict) -> dict:
    cols: dict[str, list] = {}
    for key, entry in plan.items():
        if entry["policy"] == _FLATTEN:
            for child in entry["children"]:
                cols[f"{key}.{child}"] = []
        else:
            cols[key] = []
        if entry.get("mask"):
            cols[f"{key}.{_PRESENT_SUFFIX}"] = []
        if entry.get("null_mask"):
            cols[f"{key}.{_NULL_SUFFIX}"] = []

    for rec in records:
        for key, entry in plan.items():
            policy = entry["policy"]
            present = key in rec
            value = rec.get(key)
            if entry.get("mask"):
                cols[f"{key}.{_PRESENT_SUFFIX}"].append(present)
            if entry.get("null_mask"):
                # None when the key is absent -- `__present__` already owns that state, and
                # claiming False here would assert "present and non-null" about a missing key.
                cols[f"{key}.{_NULL_SUFFIX}"].append(value is None if present else None)
            if policy == _FLATTEN:
                d = value if isinstance(value, dict) else {}
                for child in entry["children"]:
                    ctype = entry["child_types"].get(child, "string")
                    cols[f"{key}.{child}"].append(
                        _encode_scalar(d.get(child), ctype) if present else None
                    )
            elif policy == _JSON:
                cols[key].append(_json_dump(value) if present and value is not None else None)
            elif policy == _LIST_F64:
                cols[key].append([float(x) for x in value] if present and value is not None else None)
            else:
                cols[key].append(_encode_scalar(value, entry.get("type", "string")) if present else None)
    return cols


def _sanitize(value: Any) -> str:
    s = "__null__" if value is None else str(value)
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:96] or "__empty__"


class _PartitionedWriter:
    """Lazily opens one ParquetWriter per partition value under a dataset directory."""

    def __init__(self, root: Path, schema, partition_by: "str | None", compression: str) -> None:
        self._root = root
        self._schema = schema
        self._key = partition_by
        self._compression = compression
        self._writers: dict[str, Any] = {}
        self._counts: dict[str, int] = {}

    def _writer_for(self, part: str):
        w = self._writers.get(part)
        if w is None:
            if self._key is None:
                target = self._root
            else:
                target = self._root / f"{self._key}={part}" / "part-0.parquet"
            target.parent.mkdir(parents=True, exist_ok=True)
            w = pq.ParquetWriter(target, self._schema, compression=self._compression)
            self._writers[part] = w
        return w

    def write(self, records: Sequence[dict], plan: dict) -> None:
        if self._key is None:
            groups: dict[str, list] = {"": list(records)}
        else:
            groups = {}
            for rec in records:
                groups.setdefault(_sanitize(rec.get(self._key)), []).append(rec)
        for part, rows in groups.items():
            table = pa.table(_encode_chunk(rows, plan), schema=self._schema)
            self._writer_for(part).write_table(table)
            self._counts[part] = self._counts.get(part, 0) + len(rows)

    def close(self) -> dict:
        for w in self._writers.values():
            w.close()
        return dict(self._counts)


def _rmtree(path: Path) -> None:
    import shutil

    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*.parquet"))


def compact_jsonl(
    src: "Path | str",
    dest: "Path | str | None" = None,
    *,
    partition_by: "str | None" = None,
    skip_predicate: "Callable[[dict], bool] | None" = None,
    compression: str = "zstd",
    verify: bool = False,
) -> dict:
    """Build a Parquet projection of *src*. Returns the manifest.

    `partition_by` splits output into `<dest>/<key>=<value>/part-0.parquet` subdirectories
    so a reader can skip whole files; the partition column is ALSO retained in-file so the
    projection stays self-describing. `skip_predicate(rec) -> True` drops a record from the
    projection entirely (used for the `run_header` line in `opportunities.jsonl`).

    `verify=True` re-reads the projection and compares every reconstructed record against
    the source. That comparison is what makes "lossless" a fact rather than a claim.
    """
    if not _PARQUET_AVAILABLE:
        raise RuntimeError(
            f"pyarrow is required to build a Parquet projection: {_PARQUET_IMPORT_ERROR}. "
            "Install it with `pip install tradelatest[parquet]`."
        )
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)
    out = Path(dest) if dest is not None else projection_path(src)

    scan = _scan_source(src, skip_predicate)
    plan = _build_plan(scan)
    if not plan:
        raise ValueError(f"{src} produced no columns (empty or unparseable)")

    _rmtree(out)
    writer = _PartitionedWriter(out, _arrow_schema(plan), partition_by, compression)
    buf: list[dict] = []
    written = 0
    try:
        for rec in iter_jsonl(src):
            if not isinstance(rec, dict):
                continue
            if skip_predicate is not None and skip_predicate(rec):
                continue
            buf.append(rec)
            if len(buf) >= _CHUNK_ROWS:
                writer.write(buf, plan)
                written += len(buf)
                buf = []
        if buf:
            writer.write(buf, plan)
            written += len(buf)
    finally:
        partitions = writer.close()

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "source_path": src.name,
        "source": _fingerprint(src, with_hash=True),
        "rows": written,
        "columns": plan,
        "partition_by": partition_by,
        "partitions": partitions,
        "compression": compression,
        "layout": "dataset" if partition_by else "file",
        "bytes_in": src.stat().st_size,
        "bytes_out": _tree_size(out),
    }
    def _persist() -> None:
        manifest_path(src).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # `verify_projection` reads the manifest off disk (projection_status -> _load_manifest),
    # so it cannot run before the first write. The SECOND write is the point: previously
    # `verified` was attached only to the returned in-memory dict, so a MISMATCHed projection
    # left an on-disk manifest byte-indistinguishable from a verified one -- a failed check
    # was indistinguishable from an absent one (the F-056/F-079/F-083/F-085 silent-gap class).
    _persist()
    if verify:
        manifest["verified"] = verify_projection(src, skip_predicate=skip_predicate)
        _persist()
    return manifest


# --------------------------------------------------------------------------- #
# read side
# --------------------------------------------------------------------------- #
def _load_manifest(src: Path) -> dict:
    return json.loads(manifest_path(src).read_text(encoding="utf-8"))


def _physical_columns(plan: dict, wanted: "Sequence[str] | None") -> "list[str] | None":
    if wanted is None:
        return None
    cols: list[str] = []
    for key in wanted:
        entry = plan.get(key)
        if entry is None:
            continue
        if entry["policy"] == _FLATTEN:
            cols.extend(f"{key}.{c}" for c in entry["children"])
        else:
            cols.append(key)
        if entry.get("mask"):
            cols.append(f"{key}.{_PRESENT_SUFFIX}")
        if entry.get("null_mask"):
            cols.append(f"{key}.{_NULL_SUFFIX}")
    return cols


def _decode_row(row: dict, plan: dict, keys: Iterable[str]) -> dict:
    out: dict[str, Any] = {}
    for key in keys:
        entry = plan[key]
        policy = entry["policy"]
        if entry.get("mask") and not row.get(f"{key}.{_PRESENT_SUFFIX}"):
            continue  # the key was absent in the source record
        if entry.get("null_mask") and row.get(f"{key}.{_NULL_SUFFIX}"):
            out[key] = None  # present, but an explicit null parent -- not an all-null dict
            continue
        if policy == _FLATTEN:
            out[key] = {c: row.get(f"{key}.{c}") for c in entry["children"]}
            continue
        value = row.get(key)
        if value is None:
            # A mask that survived the check above says "present", so this is an explicit
            # null. Without a mask, `always_present` is what disambiguates: an unmasked
            # always-present column can only be an explicit null, while an unmasked
            # sometimes-absent column never carries one.
            if entry.get("mask") or entry.get("always_present"):
                out[key] = None
            continue
        if policy == _JSON:
            out[key] = json.loads(value)
        elif policy == _LIST_F64:
            out[key] = list(value)
        else:
            out[key] = value
    return out


def _iter_jsonl_projected(src: Path, columns: "Sequence[str] | None") -> Iterator[dict]:
    """JSONL fallback that honours `columns`, so both paths return identical shapes."""
    if columns is None:
        yield from iter_jsonl(src)
        return
    wanted = list(columns)
    for rec in iter_jsonl(src):
        yield {k: rec[k] for k in wanted if k in rec}


def iter_records(
    path: "Path | str",
    *,
    columns: "Sequence[str] | None" = None,
    strict: bool = False,
) -> Iterator[dict]:
    """Stream records from *path*, preferring a FRESH Parquet projection.

    This is the single seam readers migrate to. It is a drop-in for `iter_jsonl` except
    that `columns` prunes the read to those top-level keys — the reason the projection
    exists at all. Any condition that makes the projection untrustworthy (missing pyarrow,
    no projection, source moved on, unreadable sidecar) falls back to the JSONL source, so
    a caller can never be served data its source does not contain.
    """
    src = Path(path)
    status = projection_status(src, strict=strict)
    if status != FRESH:
        if status == STALE:
            logger.debug("iter_records: stale projection for %s -> reading JSONL", src)
        yield from _iter_jsonl_projected(src, columns)
        return
    try:
        plan = _load_manifest(src)["columns"]
        keys = [k for k in (columns if columns is not None else plan.keys()) if k in plan]
        dataset = ds.dataset(projection_path(src), format="parquet")
        for batch in dataset.to_batches(columns=_physical_columns(plan, keys)):
            for row in batch.to_pylist():
                yield _decode_row(row, plan, keys)
    except Exception as exc:  # noqa: BLE001 - a broken projection must never block a read
        logger.warning("iter_records: projection unusable for %s (%s) -> JSONL", src, exc)
        yield from _iter_jsonl_projected(src, columns)


# --------------------------------------------------------------------------- #
# verification — the correctness gate
# --------------------------------------------------------------------------- #
def _normalize(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _normalize(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_normalize(x) for x in v]
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        # NaN/Inf match the encoder's handling; rounding absorbs float64 text round-tripping.
        return None if not math.isfinite(v) else round(v, 12)
    return v


def _canonical(rec: dict) -> str:
    """Order-insensitive, float-tolerant canonical form for record comparison.

    Deliberately order-INSENSITIVE, because a columnar layout cannot reproduce per-record
    key order when records disagree about it. Key ORDER is checked separately by
    `_order_violation`, which is narrower and can therefore be strict.
    """
    return json.dumps(_normalize(rec), sort_keys=True, ensure_ascii=False, default=str)


def _order_violation(want: dict, got: dict, plan: dict) -> "str | None":
    """Name of the first flatten group whose key ORDER was not preserved, if any.

    This exists because `_canonical` cannot see ordering, and ordering is not cosmetic
    here: `replay_memory_engine._parse_jsonl` builds its feature vector from
    `features_dict.values()`, so a reordered `features` dict yields a scrambled vector
    with no error anywhere. That defect shipped once and was caught only by real-reader
    parity, not by the round-trip gate — hence this check.
    """
    for key, entry in plan.items():
        if entry.get("policy") != _FLATTEN or not entry.get("key_order_stable"):
            continue
        a, b = want.get(key), got.get(key)
        if isinstance(a, dict) and isinstance(b, dict) and list(a.keys()) != list(b.keys()):
            return key
    return None


def _diff(want: dict, got: dict, *, limit: int = 6) -> dict:
    """Only the keys that differ. Full records are unreadable at 48 columns."""
    keys = set(want) | set(got)
    out: dict[str, Any] = {}
    for k in sorted(keys):
        a, b = _normalize(want.get(k)), _normalize(got.get(k))
        if a == b and (k in want) == (k in got):
            continue
        out[k] = {
            "source": "<absent>" if k not in want else _clip(a),
            "projection": "<absent>" if k not in got else _clip(b),
        }
        if len(out) >= limit:
            out["..."] = f"{len(keys)} keys compared, showing first {limit} differences"
            break
    return out


def _clip(v: Any, width: int = 120) -> Any:
    s = repr(v)
    return v if len(s) <= width else s[:width] + "..."


def verify_projection(
    src: "Path | str",
    *,
    skip_predicate: "Callable[[dict], bool] | None" = None,
) -> dict:
    """Compare the projection record-for-record against the source. The correctness gate.

    Returns `{ok, rows, mismatches, first_mismatch}`. `ok=False` means the projection is
    NOT a faithful copy of its source and must not be trusted.
    """
    src = Path(src)
    status = projection_status(src)
    if status != FRESH:
        return {"ok": False, "rows": 0, "mismatches": -1, "reason": status}

    manifest = _load_manifest(src)
    plan = manifest["columns"]
    keys = list(plan.keys())
    dataset = ds.dataset(projection_path(src), format="parquet")

    def _projected() -> Iterator[dict]:
        for batch in dataset.to_batches():
            for row in batch.to_pylist():
                yield _decode_row(row, plan, keys)

    def _source() -> Iterator[dict]:
        for rec in iter_jsonl(src):
            if not isinstance(rec, dict):
                continue
            if skip_predicate is not None and skip_predicate(rec):
                continue
            yield rec

    if manifest.get("partition_by") is not None:
        # Partitioning reorders rows, so compare as multisets keyed by canonical form.
        from collections import Counter

        want = Counter(_canonical(r) for r in _source())
        got = Counter(_canonical(r) for r in _projected())
        only_source, only_projection = want - got, got - want
        first = None
        if only_source or only_projection:
            # Pair one unmatched record from each side so the diff is readable.
            a = json.loads(next(iter(only_source))) if only_source else {}
            b = json.loads(next(iter(only_projection))) if only_projection else {}
            first = {
                "unmatched_in_source": sum(only_source.values()),
                "unmatched_in_projection": sum(only_projection.values()),
                "diff": _diff(a, b),
            }
        return {
            "ok": not (only_source or only_projection),
            "rows": sum(want.values()),
            "mismatches": sum(only_source.values()) + sum(only_projection.values()),
            "first_mismatch": first,
        }

    mismatches = 0
    first: "dict | None" = None
    rows = 0
    for i, (want_rec, got_rec) in enumerate(zip(_source(), _projected())):
        rows += 1
        if _canonical(want_rec) != _canonical(got_rec):
            mismatches += 1
            if first is None:
                first = {"row": i, "diff": _diff(want_rec, got_rec)}
            continue
        bad = _order_violation(want_rec, got_rec, plan)
        if bad is not None:
            mismatches += 1
            if first is None:
                first = {
                    "row": i,
                    "reason": f"key order not preserved for flatten group {bad!r}",
                    "source_order": list(want_rec[bad].keys())[:8],
                    "projection_order": list(got_rec[bad].keys())[:8],
                }
    if rows != manifest["rows"]:
        mismatches += abs(rows - manifest["rows"])
        first = first or {"reason": f"row count {rows} != manifest {manifest['rows']}"}
    return {"ok": mismatches == 0, "rows": rows, "mismatches": mismatches, "first_mismatch": first}

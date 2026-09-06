"""
duckdb_query.py — optional DuckDB query surface over Parquet projections.

Sibling of `parquet_store.py`. JSONL remains the system of record; Parquet projections
are regenerable read-only sidecars (`utils.parquet_store`). This module opens ephemeral
in-memory DuckDB views over those projections so research scripts can run descriptive SQL
without maintaining a .db file.

Doctrine:
  * Additive / read-only. Nothing here writes JSONL, mutates a source, or deletes anything.
  * Optional. `duckdb` sits behind an import guard (conventions.md 3.2). Absent duckdb,
    `duckdb_available()` is False and `open_views` raises with an install hint — the same
    spirit as `parquet_store.compact_jsonl` when pyarrow is missing.
  * No imports from feature_pipeline / crt_engine / feature_states / recompute modules.
    This helper mirrors persisted artifacts only; it does not invent emitters.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    import duckdb as _duckdb_mod

try:  # optional-import guard (conventions.md 3.2)
    import duckdb as _duckdb

    _DUCKDB_AVAILABLE = True
    _DUCKDB_IMPORT_ERROR: Exception | None = None
except Exception as _exc:  # noqa: BLE001 - absence is a supported state, not an error
    _duckdb = None  # type: ignore[assignment]
    _DUCKDB_AVAILABLE = False
    _DUCKDB_IMPORT_ERROR = _exc

_VIEW_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def duckdb_available() -> bool:
    """True when duckdb imported. Callers degrade or skip when False."""
    return _DUCKDB_AVAILABLE


def _sql_quote(path: str) -> str:
    """Single-quote a path/glob for embedding in DuckDB SQL (escape interior quotes)."""
    return "'" + path.replace("'", "''") + "'"


def _validate_view_name(name: str) -> str:
    if not _VIEW_NAME_RE.match(name):
        raise ValueError(
            f"invalid view name {name!r}: must match {_VIEW_NAME_RE.pattern}"
        )
    return name


def open_views(
    table_globs: dict[str, str],
    *,
    read_only: bool = True,
) -> "_duckdb_mod.DuckDBPyConnection":
    """Open an in-memory DuckDB connection with one VIEW per name→glob entry.

    Each entry becomes::

        CREATE VIEW {name} AS SELECT * FROM read_parquet('{glob}')

    *glob* may point at a single ``.parquet`` file or a hive-style partitioned
    directory glob (e.g. ``.../XAUUSD_crt_telemetry.parquet/kind=*/*.parquet``).
    Paths are embedded with single-quote escaping; forward slashes are preferred.

    ``read_only`` is accepted for API clarity. The connection is always ephemeral
    in-memory; views are SELECT-only over ``read_parquet``.
    """
    if not _DUCKDB_AVAILABLE:
        raise RuntimeError(
            f"duckdb is required to open Parquet query views: {_DUCKDB_IMPORT_ERROR}. "
            "Install it with `pip install tradelatest[parquet]`."
        )
    if not table_globs:
        raise ValueError("table_globs must contain at least one name→glob entry")

    # read_only is documentary: in-memory + SELECT-only views; no on-disk .db to lock.
    _ = read_only
    con = _duckdb.connect(database=":memory:")
    for name, glob in table_globs.items():
        _validate_view_name(name)
        if not isinstance(glob, str) or not glob.strip():
            raise ValueError(f"glob for view {name!r} must be a non-empty string")
        # Normalize Windows separators so DuckDB glob matching is consistent.
        glob_posix = glob.replace("\\", "/")
        sql = (
            f"CREATE VIEW {name} AS SELECT * FROM read_parquet({_sql_quote(glob_posix)})"
        )
        con.execute(sql)
    return con

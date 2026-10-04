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

STORY-43.2 (safe query contract). Three things `open_views` previously only DOCUMENTED —
"read-only", lineage safety, fail-closed on an ambiguous run — were not actually enforced,
and were caught the same way this repo's other silent-gap defects were (F-079/F-083/F-085):
by checking whether the guard the docstring promised was reachable from the call sites that
needed it. It mostly wasn't:

  1. `read_only=True` was accepted and then DISCARDED (`_ = read_only`). Proven exploitable:
     `open_views({...}, read_only=True)` followed by `con.execute("COPY (SELECT 1) TO
     '...parquet'")` wrote a file to disk.
  2. DuckDB's Python Relation API is a SECOND write path with NO SQL text at all —
     `con.sql(...)` returns a `DuckDBPyRelation` carrying `.to_parquet()` / `.to_csv()` /
     `.create()` / `.insert_into()` / `.to_table()` / `.write_parquet()` / `.write_csv()` /
     `.update()` / `.create_view()` / `.insert()`, none of which are SQL text a keyword
     scan could ever see. Proven: `con.sql("select 1").to_parquet(path)` wrote a file
     with zero string-based SQL involved.
  3. `assert_view_lineage` (fail-closed on an ambiguous/mixed-run join) existed only in the
     `query_trace.py` CLI. Of `open_views`'s five call sites, only that CLI called it — the
     other four, including two that join `crt_construction`+`bar_structure` on `bar_index`,
     had ZERO lineage protection despite `src/research/evidence/catalog.py:16` stating in
     writing that this exact join's legality "is enforced there instead, by
     `query_trace.assert_view_lineage`". That delegation was false for every caller but one.

Fixed by two independent, composable layers, both now the DEFAULT so a caller has to opt
OUT rather than remember to opt in (the same "no silent config default" posture as the rest
of this repo — see CLAUDE.md §6.5):

  * `open_views(..., read_only=True)` (default) now returns a `_ReadOnlyConnection` wrapper,
    not the raw `DuckDBPyConnection`. The wrapper (a) screens every SQL string reaching
    `execute`/`sql`/`query`/`from_query`/`executemany` for a write/administrative keyword
    (comments and string/identifier literals stripped first, so a WHERE clause containing
    the word "copy" is never mistaken for the statement `COPY`), and (b) denies a fixed,
    small list of write/administrative METHOD names outright (`to_parquet`, `insert_into`,
    `install_extension`, …). Every `DuckDBPyRelation`/`DuckDBPyConnection` a wrapped call
    returns is recursively re-wrapped by TYPE, not by hand-enumerating the ~180 read/compose
    methods across both classes — a future duckdb read method works with zero changes here;
    a future duckdb WRITE method only needs adding to the two small denylists below.
    `read_only=False` returns the raw, unwrapped connection for a caller that has an actual
    reason to need it (none exist in this repo today).
  * `open_views(..., check_lineage=True)` (default) calls `assert_view_lineage` on the
    freshly created views before returning, so a caller gets fail-closed lineage checking
    for free instead of having to know it exists. `check_lineage=False` is for a caller
    that already runs its own richer, domain-aware lineage check on top (query_trace.py's
    own `assert_view_lineage`, which additionally understands `bar_matrix`'s sidecar-manifest
    lineage — a family concept this module deliberately does not know about).

`LineageConflictError` here is a plain `RuntimeError`, NOT the `SystemExit`-based class of
the same name in `query_trace.py`. That CLI-only choice is correct for a script's `main()`;
it would be a serious footgun embedded in a library call several frames inside research code
that reasonably wraps calls in `except Exception:` — `SystemExit` is a `BaseException` and
would silently skip such a handler and fall through toward killing the interpreter.
`query_trace.py` re-raises its own `SystemExit`-based error with the identical message after
catching this one, so its existing CLI behavior and tests are unchanged byte-for-byte.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, TYPE_CHECKING

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


# ── Read-only enforcement (STORY-43.2 layer 1) ─────────────────────────────────

class WriteRefusedError(PermissionError):
    """A caller tried to write, install an extension, or administer the catalog through a
    connection/relation `open_views` returned with `read_only=True` (the default)."""


# `DuckDBPyRelation`'s own documented "Relation API — Write" surface (duckdb 1.x). Small
# and closed-form by design: denying by NAME here, and auto-wrapping every OTHER
# Relation/Connection a call returns (see `_wrap` below), means a future duckdb READ method
# needs no change to this file, while a future WRITE method needs exactly one line added
# here — the opposite failure mode of hand-allowlisting the ~110 read/compose methods.
_DENIED_RELATION_METHODS = frozenset({
    "create", "create_view", "insert", "insert_into",
    "to_csv", "to_parquet", "to_table", "to_view",
    "update", "write_csv", "write_parquet",
})
# Administrative/capability-granting Connection methods: none of them write a source file
# by themselves once ATTACH/INSTALL/LOAD/register_filesystem are denied, but none of them
# belong on a "read-only analytics over Parquet" surface either, so they are denied on the
# same least-privilege footing as the write methods above.
_DENIED_CONNECTION_METHODS = frozenset({
    "install_extension", "load_extension",
    "register_filesystem", "unregister_filesystem",
    "create_function", "remove_function", "table_function",
    "append", "begin", "commit", "rollback", "checkpoint",
    "register", "unregister",
})
# Connection methods that accept a raw SQL string as their first argument (or `query=`/
# `sql=` kwarg) and must have that text screened before it reaches DuckDB.
_SQL_TEXT_METHODS = frozenset({"execute", "sql", "query", "from_query", "executemany"})

# Keywords that make a SQL statement a write, a schema change, an extension/catalog
# administration action, or a config mutation — anything this read-only surface refuses.
#
# Deliberately NOT here: REPLACE. DuckDB has no standalone `REPLACE INTO`/`REPLACE ...`
# write statement (verified: `REPLACE INTO t VALUES (...)` is a ParserException) — the only
# write-relevant form is `CREATE OR REPLACE ...`, already caught by CREATE. `replace(...)`
# is also an extremely common scalar string function (`replace(path, '\', '/')`), and a
# denylist entry with no matching write statement was a pure false-positive that broke
# every real caller using it in an ordinary read (test_retrieval_lexical_parquet.py's
# `src/retrieval/lexical.py:834`, caught by this file's own regression tests re-running
# that suite after the fact — a lesson in verifying a keyword denylist against the actual
# grammar, not against what sounds dangerous).
_DENIED_SQL_KEYWORDS = frozenset({
    "COPY", "EXPORT", "IMPORT", "ATTACH", "DETACH", "INSTALL", "LOAD",
    "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
    "CREATE", "ALTER", "DROP", "TRUNCATE",
    "VACUUM", "CHECKPOINT", "PRAGMA", "SET", "RESET", "CALL",
})
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"--[^\n]*")
_STRING_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")
_QUOTED_IDENT_RE = re.compile(r'"(?:[^"]|"")*"')
_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _redact_sql_for_keyword_scan(sql: str) -> str:
    """Strip comments and string/identifier literals before keyword-scanning, so a WHERE
    clause literal like `'please copy this'` is never mistaken for the statement COPY, and
    a genuine attempt to smuggle a keyword inside `-- COPY` or a quoted identifier doesn't
    dodge the scan either (both are removed, not preserved as "safe" text)."""
    s = _BLOCK_COMMENT_RE.sub(" ", sql)
    s = _LINE_COMMENT_RE.sub(" ", s)
    s = _STRING_LITERAL_RE.sub(" ", s)
    s = _QUOTED_IDENT_RE.sub(" ", s)
    return s


def _refuse_if_write_sql(sql: str) -> None:
    redacted = _redact_sql_for_keyword_scan(sql)
    hit = {w.upper() for w in _WORD_RE.findall(redacted)} & _DENIED_SQL_KEYWORDS
    if hit:
        raise WriteRefusedError(
            f"refused: SQL contains write/administrative keyword(s) {sorted(hit)} — this "
            "connection is read-only (utils.duckdb_query doctrine: additive/read-only, "
            f"nothing here writes JSONL, mutates a source, or deletes anything). SQL: {sql!r}"
        )


def _wrap(value: Any) -> Any:
    """Re-wrap a call's return value BY TYPE, not by method name — this is what lets the
    proxy stay safe across the whole `.filter(...).limit(...).sql(...)` chain vocabulary
    without hand-enumerating it. Anything that isn't a Relation/Connection (a DataFrame, a
    list of rows, a scalar, None, a plain attribute) is already materialized/terminal and
    passes through unwrapped."""
    if _duckdb is not None:
        if isinstance(value, _duckdb.DuckDBPyRelation):
            return _ReadOnlyRelation(value)
        if isinstance(value, _duckdb.DuckDBPyConnection):
            return _ReadOnlyConnection(value)
    return value


class _ReadOnlyProxyBase:
    """Wraps one DuckDB object; `__getattr__` is the sole enforcement point. A denied
    method name raises before the underlying call ever happens; a permitted SQL-text
    method has its argument keyword-screened; every other call's result is re-wrapped by
    `_wrap` so the read-only property is a graph invariant, not a one-hop check."""

    __slots__ = ("_wrapped",)
    _denied: frozenset = frozenset()
    _sql_methods: frozenset = frozenset()

    def __init__(self, wrapped: Any) -> None:
        object.__setattr__(self, "_wrapped", wrapped)

    def __getattr__(self, name: str) -> Any:
        if name in self._denied:
            raise WriteRefusedError(
                f"refused: {type(self._wrapped).__name__}.{name}() is a write/"
                "administrative method — this connection is read-only "
                "(utils.duckdb_query doctrine: additive/read-only, nothing here writes "
                "JSONL, mutates a source, or deletes anything)."
            )
        attr = getattr(self._wrapped, name)
        if not callable(attr):
            return _wrap(attr)
        is_sql_method = name in self._sql_methods

        def _call(*args: Any, **kwargs: Any) -> Any:
            if is_sql_method:
                sql_text = args[0] if args else kwargs.get("query", kwargs.get("sql"))
                if isinstance(sql_text, str):
                    _refuse_if_write_sql(sql_text)
            return _wrap(attr(*args, **kwargs))

        return _call

    def __repr__(self) -> str:  # pragma: no cover - debugging convenience only
        return f"<read-only {type(self._wrapped).__name__}>"


class _ReadOnlyRelation(_ReadOnlyProxyBase):
    _denied = _DENIED_RELATION_METHODS


class _ReadOnlyConnection(_ReadOnlyProxyBase):
    _denied = _DENIED_CONNECTION_METHODS
    _sql_methods = _SQL_TEXT_METHODS


# ── Lineage enforcement (STORY-43.2 layer 2) ───────────────────────────────────

class LineageConflictError(RuntimeError):
    """A view spans more than one run/corpus, or two attributable views disagree.

    Library-level (RuntimeError-based) sibling of `query_trace.LineageConflictError`
    (SystemExit-based) — see the module docstring for why the two must differ."""


def read_view_lineage(con: Any, view_name: str) -> dict:
    """Read `run_id`/`corpus_sha256` straight out of one already-open view's DATA (never
    trusted from a path or a directory name). Generic core, extracted from
    `query_trace.assert_view_lineage` so every `open_views` caller gets the same check, not
    only the `query_trace.py` CLI — this module has no `bar_matrix`-style non-projection
    family concept, so a view with neither column is reported `attributable: False`, which
    is the correct generic answer (a family-aware caller, i.e. `query_trace.py`, layers its
    own richer per-family lineage reading — e.g. `bar_matrix`'s sidecar manifest.json — on
    top of this, via `check_lineage=False` on `open_views` plus its own follow-up call)."""
    cols = {r[0] for r in con.execute(f"describe {view_name}").fetchall()}
    run_ids: list[str] = []
    shas: list[str] = []
    if "run_id" in cols:
        run_ids = [
            r[0] for r in con.execute(
                f"select distinct run_id from {view_name} where run_id is not null"
            ).fetchall()
        ]
    if "corpus_sha256" in cols:
        shas = [
            r[0] for r in con.execute(
                f"select distinct corpus_sha256 from {view_name} "
                "where corpus_sha256 is not null"
            ).fetchall()
        ]
    return {
        "run_ids": run_ids,
        "corpus_shas": shas,
        "attributable": bool(run_ids or shas),
    }


def check_lineage_conflicts(report: dict[str, dict], *, verbose: bool = False) -> dict:
    """Refuse-or-pass over an ALREADY-BUILT `{name: lineage_record}` report (each record
    shaped like `read_view_lineage`'s return). Kept separate from `read_view_lineage` so a
    family-aware caller (bar_matrix's sidecar-manifest lineage, which carries no run_id/
    corpus_sha256 COLUMN at all) can merge its own per-name records into the SAME conflict
    check `open_views` runs internally — one definition of what counts as a conflict, not
    two that could silently diverge. Raises `LineageConflictError` when:
      * any single view spans MORE THAN ONE run_id or corpus_sha256;
      * two ATTRIBUTABLE views disagree on run_id or corpus_sha256.
    A view carrying neither column is UNATTRIBUTABLE — reported by name (when `verbose`),
    never silently treated as compatible with the attributable views."""
    internally_split = {
        name: r for name, r in report.items()
        if len(r["run_ids"]) > 1 or len(r["corpus_shas"]) > 1
    }
    if internally_split:
        lines = [
            f"    {name}: run_ids={r['run_ids']} corpus_shas={r['corpus_shas']}"
            for name, r in internally_split.items()
        ]
        raise LineageConflictError(
            "view(s) span MORE THAN ONE run — a family's projection directory holds "
            "records from different emits:\n" + "\n".join(lines) +
            "\n  --run-dir alone cannot catch this; it scopes by PATH, not by the "
            "run_id/corpus_sha256 actually inside the files."
        )

    attributable = {name: r for name, r in report.items() if r["attributable"]}
    run_id_sets = {
        name: frozenset(r["run_ids"]) for name, r in attributable.items() if r["run_ids"]
    }
    sha_sets = {
        name: frozenset(r["corpus_shas"]) for name, r in attributable.items() if r["corpus_shas"]
    }
    if len(set(run_id_sets.values())) > 1:
        raise LineageConflictError(
            "attributable views disagree on run_id:\n" +
            "\n".join(f"    {name}: {sorted(v)}" for name, v in run_id_sets.items()) +
            "\n  Views from different runs do not join safely — the join would return "
            "rows silently pairing the wrong records, or zero rows, either way without "
            "saying so."
        )
    if len(set(sha_sets.values())) > 1:
        raise LineageConflictError(
            "attributable views disagree on corpus_sha256:\n" +
            "\n".join(f"    {name}: {sorted(v)}" for name, v in sha_sets.items())
        )

    if verbose:
        unattributable = sorted(name for name, r in report.items() if not r["attributable"])
        run_id = next(iter(next(iter(run_id_sets.values()), frozenset())), None)
        corpus = next(iter(next(iter(sha_sets.values()), frozenset())), None)
        print(
            f"lineage: run_id={run_id or 'n/a'}  "
            f"corpus={((corpus or '')[:12] + '...') if corpus else 'n/a'}"
            f"  views={','.join(sorted(attributable))}"
        )
        print(
            f"         UNATTRIBUTABLE (no run identity in-record): "
            f"{','.join(unattributable) or '(none)'}"
        )
    return report


def assert_view_lineage(
    con: Any, view_names: Iterable[str], *, verbose: bool = False
) -> dict:
    """Convenience: `read_view_lineage` every named view, then `check_lineage_conflicts`
    the combined report. What `open_views(check_lineage=True)` (the default) calls
    internally; exposed directly for a caller (`query_trace.py`) that wants to fold in its
    own family-specific lineage records — e.g. `bar_matrix`'s sidecar manifest — before the
    conflict check runs, via `read_view_lineage` + a manual merge + `check_lineage_conflicts`."""
    report = {name: read_view_lineage(con, name) for name in view_names}
    return check_lineage_conflicts(report, verbose=verbose)


# ── View construction ───────────────────────────────────────────────────────────

def open_views(
    table_globs: dict[str, str],
    *,
    read_only: bool = True,
    check_lineage: bool = True,
) -> "_duckdb_mod.DuckDBPyConnection":
    """Open an in-memory DuckDB connection with one VIEW per name→glob entry.

    Each entry becomes::

        CREATE VIEW {name} AS SELECT * FROM read_parquet('{glob}')

    *glob* may point at a single ``.parquet`` file or a hive-style partitioned
    directory glob (e.g. ``.../XAUUSD_crt_telemetry.parquet/kind=*/*.parquet``).
    Paths are embedded with single-quote escaping; forward slashes are preferred.

    ``read_only`` (default ``True``) returns a wrapped connection that refuses every write
    and administrative operation — both the SQL-text kind (``COPY``/``ATTACH``/``INSERT``/…)
    and the DuckDB Relation-API kind (``.to_parquet()``/``.insert_into()``/…), which carries
    no SQL text at all and is a distinct surface a caller could reach even with `read_only`
    SQL screening alone. ``read_only=False`` returns the raw, unwrapped `DuckDBPyConnection`
    for a caller with an actual documented reason to need one (none exist in this repo
    today; the parameter still defaults closed).

    ``check_lineage`` (default ``True``) runs `assert_view_lineage` over the just-created
    views before returning, so a caller gets fail-closed lineage checking without having to
    know to ask for it — closing the gap where only one of `open_views`'s five call sites
    called it. Set `check_lineage=False` only when the caller runs its own richer,
    family-aware lineage check afterward (`query_trace.py` does, for `bar_matrix`'s
    sidecar-manifest lineage, which this generic function cannot see).
    """
    if not _DUCKDB_AVAILABLE:
        raise RuntimeError(
            f"duckdb is required to open Parquet query views: {_DUCKDB_IMPORT_ERROR}. "
            "Install it with `pip install tradelatest[parquet]`."
        )
    if not table_globs:
        raise ValueError("table_globs must contain at least one name→glob entry")

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

    if check_lineage:
        assert_view_lineage(con, table_globs.keys())

    return _ReadOnlyConnection(con) if read_only else con

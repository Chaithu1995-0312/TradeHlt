"""
identity_chain.py — the Phase 3 closed identity chain, 7-invariant fail-loud checker.

The single entry point that MECHANICALLY verifies the identity chain across the Spine
journal (trades.csv), Oracle labeler (labels.csv), layer-trace (L8), journal, and engine
telemetry (crt_telemetry.jsonl), all joined through the canonical bar-clock bridge.

INVARIANTS
----------
I1  telemetry_envelope_uniformity    every crt_telemetry record carries non-empty
                                     run_id / instrument / timeframe / corpus_sha256.
I2  accepted_lifecycle_completeness  every CANDIDATE_LIFECYCLE row has candidate_id;
                                     every ACCEPTED row additionally has trade_id + bar_ts.
I3  bridge_monotonicity              DECISION_DISTANCE bar_ts is non-decreasing with
                                     candle_index; bar-identity rows are non-decreasing
                                     with bar_index (the clock never runs backwards).
I4  trade_lifecycle_bidirectional    every trades.csv candidate_id maps to EXACTLY ONE
                                     lifecycle row (missing or duplicated = FAIL).
I5  strict_accepted_resolution       every ACCEPTED.trade_id resolves to BOTH trades.csv
                                     AND its L8 row on the SAME bar_open_ts (and the same
                                     frozen-PK instrument) — fail-loud.
I6  l8_set_closure                   the set of L8 trade_ids equals the set of ACCEPTED
                                     trade_ids (every birth recorded once, nothing extra).
I7  label_provenance                 labels.csv rows carry dataset_hash / label_run_id /
                                     label_generated_utc and a parseable bar timestamp.
I8  label_trace_resolution           every labels.csv row's (lt_id, bar_open_ts) resolves
                                     to an L3 layer-trace row under that SAME lt_id, its
                                     trace_id's embedded timestamp agrees with its own
                                     bar_open_ts column, and the file carries exactly one
                                     lt_id (CH-oracle-join-spine).
I9  basis_declaration                every outcome-bearing row (labels.csv / trades.csv)
                                     carries all five governance.measurement_basis axes
                                     as closed-vocabulary members (free text FAILs), and
                                     measurement_basis.can_compare over every pair of
                                     distinct bases present returns a named verdict,
                                     never crashes (CH-measurement-basis-declaration).
                                     Unlike I8, a file may legitimately hold SEVERAL
                                     distinct bases (labels.csv carries 4 arms) — I9 does
                                     not require one basis per file.

SKIP semantics: an invariant whose input file was not supplied is recorded SKIP (graceful
partial activation); FAIL is reserved for a real invariant violation and forces a non-zero
CLI exit. Nothing here computes a market quantity — it only verifies identity joins.

Two verdict modes (``check_run(..., require_all=...)``):
  - default (``require_all=False``): a run is CLOSED iff no invariant FAILs. SKIP passes.
    This is the graceful-partial-activation mode for step-by-step wiring (e.g.
    telemetry-only) and is unchanged behavior.
  - strict (``require_all=True``): a run is CLOSED iff every invariant is PASS. A SKIP
    is treated as a violation. Use this once all five input streams are expected to be
    present — it is the only mode that actually proves the chain is closed end to end;
    the default mode proves only that nothing *checked* failed, which is a materially
    weaker claim (see docs/memory/identity-chain-memory.md).
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from governance.identity_spine import normalize_bar_ts, resolve_bar
from governance.measurement_basis import (
    ALLOW_SAME_BASIS,
    BASIS_AXES,
    DENY_COST_MODEL_MISMATCH,
    DENY_FILL_MODEL_MISMATCH,
    DENY_REFERENCE_LEVEL_MISMATCH,
    DENY_TIE_BREAK_MISMATCH,
    DENY_UNSTAMPED_OPERAND,
    DENY_WALK_KERNEL_MISMATCH,
    UNSTAMPED,
    basis_from_row,
    can_compare,
    canonicalise,
)

_KNOWN_BASIS_VERDICTS = frozenset({
    ALLOW_SAME_BASIS, DENY_UNSTAMPED_OPERAND, DENY_WALK_KERNEL_MISMATCH,
    DENY_REFERENCE_LEVEL_MISMATCH, DENY_FILL_MODEL_MISMATCH,
    DENY_COST_MODEL_MISMATCH, DENY_TIE_BREAK_MISMATCH,
})

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

INVARIANTS = (
    ("I1", "telemetry_envelope_uniformity"),
    ("I2", "accepted_lifecycle_completeness"),
    ("I3", "bridge_monotonicity"),
    ("I4", "trade_lifecycle_bidirectional"),
    ("I5", "strict_accepted_resolution"),
    ("I6", "l8_set_closure"),
    ("I7", "label_provenance"),
    ("I8", "label_trace_resolution"),
    ("I9", "basis_declaration"),
)


@dataclass(frozen=True)
class Outcome:
    invariant: str
    name: str
    status: str
    detail: str = ""


# --------------------------------------------------------------------------- #
# loaders
# --------------------------------------------------------------------------- #
def read_jsonl(path: "str | Path") -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def read_trades_csv(path: "str | Path") -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _norm_ts(value) -> Optional[str]:
    """Best-effort canonical bar ts; None when absent/empty; raises on unparseable."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s == "None":
        return None
    return normalize_bar_ts(s)


def _lifecycle_records(telemetry: list[dict]) -> list[dict]:
    return [r for r in telemetry if r.get("kind") == "CANDIDATE_LIFECYCLE"]


def _decision_records(telemetry: list[dict]) -> list[dict]:
    return [r for r in telemetry if r.get("kind") == "DECISION_DISTANCE"]
# SEAM-A


# --------------------------------------------------------------------------- #
# verifiers — each returns (status, detail)
# --------------------------------------------------------------------------- #
def verify_envelope_uniformity(telemetry: list[dict]) -> tuple[str, str]:
    bad = []
    for i, r in enumerate(telemetry):
        for key in ("run_id", "instrument", "timeframe", "corpus_sha256"):
            if not str(r.get(key) or "").strip():
                bad.append(f"row[{i}] kind={r.get('kind')} missing/non-empty '{key}'")
    if bad:
        return FAIL, "; ".join(bad[:8])
    return PASS, f"all {len(telemetry)} telemetry records carry the full identity envelope"


def verify_lifecycle_completeness(telemetry: list[dict]) -> tuple[str, str]:
    life = _lifecycle_records(telemetry)
    bad = []
    accepted = 0
    for i, r in enumerate(life):
        if not str(r.get("candidate_id") or "").strip():
            bad.append(f"lifecycle[{i}] missing candidate_id")
        if r.get("death_reason") == "ACCEPTED":
            accepted += 1
            for key in ("trade_id", "bar_ts"):
                if not str(r.get(key) or "").strip():
                    bad.append(
                        f"ACCEPTED lifecycle[{i}] candidate={r.get('candidate_id')} missing '{key}'"
                    )
            if not str(r.get("bar_ts") or "").strip():
                continue
            try:
                normalize_bar_ts(r["bar_ts"])
            except ValueError as exc:
                bad.append(f"ACCEPTED lifecycle[{i}] unparseable bar_ts: {exc}")
    if bad:
        return FAIL, "; ".join(bad[:8])
    return PASS, f"{len(life)} lifecycle rows complete; {accepted} ACCEPTED rows carry trade_id + bar_ts"


def verify_bridge_monotonicity(
    telemetry: list[dict],
    bar_identity: Optional[list[dict]],
) -> tuple[str, str]:
    """The bar clock never runs backwards: emitted rows must be non-decreasing in bar_ts.

    Index-coupled checks would miss exactly the drift class Phase 3 exists for (two streams
    counting the same clock differently), so this is timestamp-only: a row that is emitted
    later in the stream but carries an EARLIER canonical bar time is a clock violation.
    """
    problems = []
    prev_ts = None
    for i, r in enumerate(_decision_records(telemetry)):
        ts = _norm_ts(r.get("bar_ts"))
        if ts is None:
            problems.append(
                f"DECISION_DISTANCE[{i}] missing bar_ts (candle_index={r.get('candle_index')})"
            )
            continue
        if prev_ts is not None and ts < prev_ts:
            problems.append(f"DECISION_DISTANCE[{i}] bar_ts went backwards: {prev_ts} -> {ts}")
        prev_ts = ts
    if bar_identity:
        last_ts = None
        for i, b in enumerate(bar_identity):
            ts = _norm_ts(b.get("bar_open_ts"))
            if ts is None:
                problems.append(f"bar_identity[{i}] missing bar_open_ts")
                continue
            if last_ts is not None and ts < last_ts:
                problems.append(
                    f"bar_identity[{i}] bar_open_ts went backwards: {last_ts} -> {ts} "
                    f"(bar_index={b.get('bar_index')})"
                )
            last_ts = ts
    if problems:
        return FAIL, "; ".join(problems[:8])
    n = len(_decision_records(telemetry)) + (len(bar_identity) if bar_identity else 0)
    return PASS, f"bar clock monotone across {n} index->ts observations"
# SEAM-B


def verify_trade_lifecycle_bidirectional(
    trades: list[dict],
    telemetry: list[dict],
) -> tuple[str, str]:
    life = _lifecycle_records(telemetry)
    bad = []
    by_cid: dict[str, int] = {}
    for r in life:
        cid = str(r.get("candidate_id") or "")
        by_cid[cid] = by_cid.get(cid, 0) + 1
    seen: dict[str, int] = {}
    for i, t in enumerate(trades):
        cid = str(t.get("candidate_id") or "")
        if not cid:
            bad.append(f"trades.csv[{i}] missing candidate_id (trade_id={t.get('trade_id')})")
            continue
        seen[cid] = seen.get(cid, 0) + 1
    for cid, n in sorted(seen.items()):
        if n > 1:
            bad.append(f"trades.csv candidate_id {cid!r} duplicated {n}x in trades")
        if by_cid.get(cid, 0) != 1:
            bad.append(
                f"trades.csv candidate_id {cid!r} -> lifecycle rows = "
                f"{by_cid.get(cid, 0)} (expected exactly 1)"
            )
    for cid, n in sorted(by_cid.items()):
        if n > 1:
            bad.append(f"lifecycle candidate_id {cid!r} duplicated {n}x")
    if bad:
        return FAIL, "; ".join(bad[:8])
    return PASS, f"{len(trades)} trades.csv rows each map to exactly one lifecycle row"
# SEAM-C


def _post_commit_vetoed(layer_rows: list[dict], lt_id: str) -> set[str]:
    """trade_ids CRT committed (lifecycle ACCEPTED) that a backtest post-commit gate then vetoed
    (drift / Phase-5 / EngineRunner) — evidenced ONLY by an L5 `REJECT` row carrying that
    trade_id in THIS run. Such a trade legitimately has no trades.csv row and no L8 row; without
    this set I5/I6 FAILed every run that had a veto (k23 lt_20260924_194133, CRT-0024). A veto
    with no L5 row is still a FAIL — the exemption needs evidence, never inference."""
    return {
        str(r.get("trade_id"))
        for r in layer_rows
        if r.get("layer") == "L5" and r.get("status") == "REJECT" and r.get("trade_id")
        and str(r.get("run_id") or "") == lt_id
    }


def verify_strict_accepted_resolution(
    trades: list[dict],
    telemetry: list[dict],
    layer_rows: Optional[list[dict]],
    run_manifest: Optional[dict] = None,
) -> tuple[str, str]:
    if layer_rows is None:
        return SKIP, "no layer-trace input supplied"
    life = _lifecycle_records(telemetry)
    accepted = [r for r in life if r.get("death_reason") == "ACCEPTED"]
    by_trade_id: dict[str, list[dict]] = {}
    for t in trades:
        by_trade_id.setdefault(str(t.get("trade_id") or ""), []).append(t)
    # `layer_rows` may be the SHARED cross-run trace file (layer_trace.py has no per-run
    # rotation yet) and `trade_id` is minted per-run, not globally unique — scope the L8
    # lookup to THIS run's own layer-trace id. F-101: the telemetry envelope's `run_id`
    # (the canonical/ReportWriter id) and the layer-trace subsystem's own `run_id` are TWO
    # DIFFERENT strings for the same physical run, not joinable by equality — so prefer the
    # authoritative `run_manifest.json["layer_trace_id"]` pointer; fall back to telemetry's
    # own `run_id` only when no manifest was supplied (matches the golden fixture, which
    # mints one shared id for both).
    _lt_id = str((run_manifest or {}).get("layer_trace_id") or "")
    if not _lt_id:
        _lt_id = next((str(r.get("run_id")) for r in telemetry if r.get("run_id")), "")
    l8_by_tid: dict[str, list[dict]] = {}
    for r in layer_rows:
        if (r.get("layer") == "L8" and r.get("trade_id")
                and str(r.get("run_id") or "") == _lt_id):
            l8_by_tid.setdefault(str(r.get("trade_id")), []).append(r)
    vetoed = _post_commit_vetoed(layer_rows, _lt_id)
    bad = []
    tested = 0
    n_vetoed = 0
    for r in accepted:
        tid = str(r.get("trade_id") or "")
        if not tid:
            continue   # I2 already fails; don't double-report
        if tid in vetoed:
            n_vetoed += 1
            if by_trade_id.get(tid) or l8_by_tid.get(tid):
                bad.append(
                    f"ACCEPTED.trade_id {tid!r}: vetoed post-commit (L5 REJECT) yet has "
                    f"trades.csv rows={len(by_trade_id.get(tid, []))} L8 rows={len(l8_by_tid.get(tid, []))}"
                )
            continue
        bar_ts = _norm_ts(r.get("bar_ts"))
        if bar_ts is None:
            continue
        tested += 1
        inst = str(r.get("instrument") or "")
        trades_rows = by_trade_id.get(tid, [])
        if len(trades_rows) != 1:
            bad.append(
                f"ACCEPTED.trade_id {tid!r}: trades.csv rows = {len(trades_rows)} (expected exactly 1)"
            )
            continue
        tinst = str(trades_rows[0].get("instrument") or "")
        if inst and tinst and inst != tinst:
            bad.append(f"ACCEPTED.trade_id {tid!r}: instrument {inst!r} != trades.csv {tinst!r}")
        if _norm_ts(trades_rows[0].get("opened_at")) != bar_ts:
            bad.append(
                f"ACCEPTED.trade_id {tid!r}: lifecycle bar_ts {bar_ts} != "
                f"trades.csv opened_at {trades_rows[0].get('opened_at')}"
            )
        l8_rows = l8_by_tid.get(tid, [])
        if len(l8_rows) != 1:
            bad.append(f"ACCEPTED.trade_id {tid!r}: L8 rows = {len(l8_rows)} (expected exactly 1)")
            continue
        l8_ts = _norm_ts(l8_rows[0].get("bar_ts"))
        if l8_ts != bar_ts:
            bad.append(f"ACCEPTED.trade_id {tid!r}: L8 bar_ts {l8_ts} != lifecycle bar_ts {bar_ts}")
        l8_inst = str(l8_rows[0].get("instrument") or "")
        if inst and l8_inst and inst != l8_inst:
            bad.append(f"ACCEPTED.trade_id {tid!r}: instrument {inst!r} != L8 {l8_inst!r}")
    if bad:
        return FAIL, "; ".join(bad[:8])
    return PASS, (
        f"all {tested} ACCEPTED trade_ids resolve to trades.csv AND L8 on the same bar_ts"
        + (f"; {n_vetoed} vetoed post-commit (L5 REJECT evidence, absent from ledger)" if n_vetoed else "")
    )
# SEAM-D


def verify_l8_set_closure(
    trades: list[dict],
    telemetry: list[dict],
    layer_rows: Optional[list[dict]],
    run_manifest: Optional[dict] = None,
) -> tuple[str, str]:
    if layer_rows is None:
        return SKIP, "no layer-trace input supplied"
    life = _lifecycle_records(telemetry)
    accepted_tids = {
        str(r.get("trade_id") or "") for r in life if r.get("death_reason") == "ACCEPTED"
    }
    accepted_tids.discard("")
    # Same layer-trace-id scoping as verify_strict_accepted_resolution (I5) — F-101: telemetry's
    # `run_id` and the layer-trace subsystem's own `run_id` are different strings for the same
    # run, so prefer the manifest's `layer_trace_id` pointer over telemetry's `run_id`.
    _lt_id = str((run_manifest or {}).get("layer_trace_id") or "")
    if not _lt_id:
        _lt_id = next((str(r.get("run_id")) for r in telemetry if r.get("run_id")), "")
    l8_tids = [
        str(r.get("trade_id") or "")
        for r in layer_rows
        if r.get("layer") == "L8" and r.get("trade_id")
        and str(r.get("run_id") or "") == _lt_id
    ]
    trade_tids = {str(t.get("trade_id") or "") for t in trades}
    dup = {tid for tid in l8_tids if l8_tids.count(tid) > 1}
    problems = []
    # Post-commit vetoes (L5 REJECT evidence) leave the ledger by design: drop them from the
    # ACCEPTED set, but they must then be absent from BOTH trades.csv and L8.
    vetoed = _post_commit_vetoed(layer_rows, _lt_id) & accepted_tids
    leaked = vetoed & (trade_tids | set(l8_tids))
    if leaked:
        problems.append(f"post-commit vetoed trade_ids still in trades.csv/L8: {sorted(leaked)}")
    accepted_tids = accepted_tids - vetoed
    if dup:
        problems.append(f"duplicate L8 trade_ids: {sorted(dup)}")
    if not l8_tids:
        problems.append("no L8 trade rows recorded")
    missing_in_trades = accepted_tids - trade_tids
    if missing_in_trades:
        problems.append(f"ACCEPTED trade_ids missing from trades.csv: {sorted(missing_in_trades)}")
    l8_missing_birth = set(l8_tids) - accepted_tids
    if l8_missing_birth:
        problems.append(f"L8 trade_ids with no ACCEPTED lifecycle: {sorted(l8_missing_birth)}")
    accepted_missing_l8 = accepted_tids - set(l8_tids)
    if accepted_missing_l8:
        problems.append(f"ACCEPTED trade_ids without an L8 birth row: {sorted(accepted_missing_l8)}")
    if problems:
        return FAIL, "; ".join(problems[:8])
    return PASS, (
        f"L8 set == ACCEPTED set ({len(accepted_tids)} trade_ids), all in trades.csv"
        + (f"; {len(vetoed)} vetoed post-commit excluded on L5 evidence" if vetoed else "")
    )
# SEAM-E


def verify_label_provenance(
    labels: list[dict],
    corpus_sha256: Optional[str],
) -> tuple[str, str]:
    if not labels:
        return FAIL, "labels.csv supplied but has no rows"
    cols = set(labels[0].keys())
    missing = [c for c in ("dataset_hash", "label_run_id", "label_generated_utc") if c not in cols]
    if missing:
        return FAIL, f"labels.csv missing lineage columns: {missing}"
    problems = []
    hashes = set()
    for i, r in enumerate(labels):
        if not str(r.get("dataset_hash") or "").strip():
            problems.append(f"labels[{i}] blank dataset_hash")
        if not str(r.get("label_run_id") or "").strip():
            problems.append(f"labels[{i}] blank label_run_id")
        if not str(r.get("label_generated_utc") or "").strip():
            problems.append(f"labels[{i}] blank label_generated_utc")
        hashes.add(str(r.get("dataset_hash") or ""))
        if not str(r.get("timestamp") or "").strip():
            problems.append(f"labels[{i}] missing timestamp (bar clock)")
        else:
            try:
                normalize_bar_ts(r["timestamp"])
            except ValueError as exc:
                problems.append(f"labels[{i}] unparseable timestamp: {exc}")
    if len(hashes) > 1 and "" not in hashes:
        problems.append(f"labels.csv mixes {len(hashes)} dataset_hashes: {sorted(hashes)[:4]}")
    if corpus_sha256 and hashes and hashes != {corpus_sha256}:
        problems.append(
            f"labels dataset_hash {sorted(hashes)[:4]} != supplied corpus_sha256 {corpus_sha256[:16]}..."
        )
    if problems:
        return FAIL, "; ".join(problems[:8])
    return PASS, (
        f"{len(labels)} label rows carry dataset_hash/label_run_id/label_generated_utc "
        "and a parseable bar timestamp"
    )
# SEAM-F


def _l3_bar_open_ts_keys(layer_rows: list[dict]) -> set[tuple[str, str]]:
    """(run_id, bar_open_ts) for every L3 row that resolves to a real bar.

    L3 is authoritative for this join: emitted exactly once per bar
    (`runtime.backtest_v2`), the only layer carrying the engine's own state, and never
    `NOT_REACHED`-conditional the way L4 is when `parent_crt` is disabled.
    """
    keys: set[tuple[str, str]] = set()
    for r in layer_rows:
        if r.get("layer") != "L3":
            continue
        pk = resolve_bar(r)
        if pk is None:   # run-scoped row (bar_ts=None) — not a bar, never joins on one
            continue
        keys.add((str(r.get("run_id") or ""), pk[2]))
    return keys


def verify_label_trace_resolution(
    labels: list[dict],
    layer_rows: Optional[list[dict]],
) -> tuple[str, str]:
    """I8: every label row's (lt_id, bar_open_ts) resolves to an L3 row under that SAME
    lt_id, `trace_id`'s embedded timestamp agrees with the row's own `bar_open_ts` (a
    label whose two identity columns were copied from different bars must FAIL, not
    silently join on whichever one looks parseable), and the file carries exactly one
    lt_id (a silent cross-run merge is a violation, not a detail).
    """
    if layer_rows is None:
        return SKIP, "no layer-trace input supplied"
    if not labels:
        return SKIP, "no labels supplied"
    cols = set(labels[0].keys())
    missing = [c for c in ("lt_id", "trace_id") if c not in cols]
    if missing:
        return FAIL, f"labels.csv missing join columns: {missing}"

    l3_keys = _l3_bar_open_ts_keys(layer_rows)
    problems = []
    lt_ids_seen: set[str] = set()
    tested = 0
    for i, r in enumerate(labels):
        lt = str(r.get("lt_id") or "").strip()
        tid = str(r.get("trace_id") or "").strip()
        if not lt:
            problems.append(f"labels[{i}] blank lt_id")
            continue
        if not tid:
            problems.append(f"labels[{i}] blank trace_id")
            continue
        lt_ids_seen.add(lt)
        bar_open_ts_raw = r.get("bar_open_ts") or r.get("timestamp")
        if not str(bar_open_ts_raw or "").strip():
            problems.append(f"labels[{i}] missing bar_open_ts/timestamp")
            continue
        try:
            bar_open_ts = normalize_bar_ts(bar_open_ts_raw)
        except ValueError as exc:
            problems.append(f"labels[{i}] unparseable bar timestamp: {exc}")
            continue
        # trace_id = f"{run_id}:{instrument}:{bar_ts.isoformat()}" (runtime.layer_trace.
        # make_trace_id). maxsplit=2 leaves the isoformat ts (itself colon-bearing) whole.
        parts = tid.split(":", 2)
        if len(parts) != 3 or parts[0] != lt:
            problems.append(f"labels[{i}] trace_id {tid!r} does not start with its own lt_id {lt!r}")
            continue
        try:
            tid_ts = normalize_bar_ts(parts[2])
        except ValueError as exc:
            problems.append(f"labels[{i}] trace_id {tid!r} timestamp component unparseable: {exc}")
            continue
        if tid_ts != bar_open_ts:
            problems.append(
                f"labels[{i}] trace_id timestamp {tid_ts} != row bar_open_ts {bar_open_ts} "
                "(identity columns copied from different bars)"
            )
            continue
        tested += 1
        if (lt, bar_open_ts) not in l3_keys:
            problems.append(f"labels[{i}] (lt_id={lt}, bar_open_ts={bar_open_ts}) has no L3 row")
    if len(lt_ids_seen) > 1:
        problems.append(f"labels.csv mixes {len(lt_ids_seen)} lt_ids: {sorted(lt_ids_seen)[:4]}")
    if problems:
        return FAIL, "; ".join(problems[:8])
    return PASS, f"{tested} label rows resolve to an L3 row under their single lt_id {sorted(lt_ids_seen)}"
# SEAM-G


def verify_basis_declaration(
    labels: Optional[list[dict]],
    trades: Optional[list[dict]],
) -> tuple[str, str]:
    """I9: every outcome-bearing row's declared measurement basis is a REAL declaration,
    and `measurement_basis.can_compare` never crashes on any pair of distinct bases
    actually present in the supplied streams.

    Unlike I8, a single file may legitimately hold SEVERAL distinct bases — labels.csv
    carries 4 arms (2 sl_geom x 2 tie_break) by design — so this invariant does NOT
    require one basis per file. What it requires is that every row's five axes are a
    REAL declaration: non-blank, a recognised (canonicalisable) spelling, and NOT an
    explicit UNSTAMPED — a pre-change file that never stamped these columns at all is
    exactly what SHOULD fail here, the same fail-closed shape I7/I8 already use for a
    stale artifact.

    SCOPE NOTE: does not cross-reference a file's manifest.json arm-set declaration —
    `check_run` has no manifest input wired for either stream. It verifies the ROWS
    themselves, which is the surface `can_compare` and every downstream reader actually
    consumes; cross-referencing the manifest is disclosed as unimplemented, not silently
    skipped.
    """
    if not labels and not trades:
        return SKIP, "no labels.csv or trades.csv input supplied"
    problems: list[str] = []
    tested = 0
    bases_by_stream: dict[str, set] = {}
    for stream_name, rows in (("labels", labels or []), ("trades", trades or [])):
        if not rows:
            continue
        seen_bases = set()
        for i, r in enumerate(rows):
            row_ok = True
            for axis in BASIS_AXES:
                raw = r.get(axis)
                if not str(raw or "").strip():
                    problems.append(f"{stream_name}[{i}] blank {axis}")
                    row_ok = False
                    continue
                canon = canonicalise(axis, raw)
                if canon is None:
                    problems.append(f"{stream_name}[{i}] unrecognised {axis} value {raw!r}")
                    row_ok = False
                elif canon == UNSTAMPED:
                    problems.append(f"{stream_name}[{i}] {axis} is explicitly UNSTAMPED")
                    row_ok = False
            tested += 1
            if row_ok:
                seen_bases.add(basis_from_row(r))
        bases_by_stream[stream_name] = seen_bases

    all_bases = [b for s in bases_by_stream.values() for b in s]
    for i in range(len(all_bases)):
        for j in range(i + 1, len(all_bases)):
            try:
                verdict, _rationale = can_compare(all_bases[i], all_bases[j])
            except Exception as exc:  # noqa: BLE001 — this crash IS the invariant violation
                problems.append(f"can_compare crashed on a real basis pair: {exc}")
                continue
            if verdict not in _KNOWN_BASIS_VERDICTS:
                problems.append(f"can_compare returned an unrecognised verdict {verdict!r}")
    if problems:
        return FAIL, "; ".join(problems[:8])
    return PASS, (
        f"{tested} rows carry a real 5-axis basis; can_compare returns a named verdict "
        f"on all {len(all_bases)} distinct bases present"
    )
# SEAM-H


def check_run(
    telemetry_path: "str | Path | None" = None,
    trades_path: "str | Path | None" = None,
    layer_trace_path: "str | Path | None" = None,
    labels_path: "str | Path | None" = None,
    bar_identity_path: "str | Path | None" = None,
    corpus_sha256: Optional[str] = None,
    require_all: bool = False,
    run_manifest_path: "str | Path | None" = None,
) -> tuple[bool, list[Outcome]]:
    """Run the seven invariants over the supplied stream files.

    Returns ``(all_pass, outcomes)``. A missing input file marks the invariants that need it
    as SKIP (graceful partial activation, e.g. telemetry-only at step 3), while a present file
    with a real violation FAILs. ``corpus_sha256`` lets I7 bind label rows to the run corpus.

    ``require_all`` selects the verdict mode (see module docstring): False (default) treats
    SKIP as passing — ``all_pass`` is True iff no invariant FAILed. True treats SKIP as a
    violation — ``all_pass`` is True iff every invariant is PASS. Either way, the returned
    ``outcomes`` list is identical; only the aggregate verdict differs.

    ``run_manifest_path`` (optional): the per-run ``run_manifest.json`` written by
    `ReportWriter`. F-101: its telemetry envelope's `run_id` and the layer-trace subsystem's
    own `run_id` are different strings for the same run — I5/I6 use the manifest's
    ``layer_trace_id`` to scope their L8 lookup to this run when supplied, falling back to
    telemetry's own `run_id` otherwise.
    """
    telemetry = read_jsonl(telemetry_path) if telemetry_path else []
    trades = read_trades_csv(trades_path) if trades_path else []
    layer_rows = read_jsonl(layer_trace_path) if layer_trace_path else None
    bar_identity = read_jsonl(bar_identity_path) if bar_identity_path else None
    labels = read_jsonl(labels_path) if labels_path and str(labels_path).endswith(".jsonl") \
        else _read_labels(labels_path)
    run_manifest = (
        json.loads(Path(run_manifest_path).read_text(encoding="utf-8"))
        if run_manifest_path else None
    )

    checks = (
        ("I1", verify_envelope_uniformity(telemetry) if telemetry_path
         else (SKIP, "no telemetry input")),
        ("I2", verify_lifecycle_completeness(telemetry) if telemetry_path
         else (SKIP, "no telemetry input")),
        ("I3", verify_bridge_monotonicity(telemetry, bar_identity)
         if (telemetry_path or bar_identity_path) else (SKIP, "no telemetry / bar-identity input")),
        ("I4", verify_trade_lifecycle_bidirectional(trades, telemetry)
         if (telemetry_path and trades_path) else (SKIP, "need telemetry + trades.csv")),
        ("I5", verify_strict_accepted_resolution(trades, telemetry, layer_rows, run_manifest)
         if (telemetry_path and trades_path) else (SKIP, "need telemetry + trades.csv")),
        ("I6", verify_l8_set_closure(trades, telemetry, layer_rows, run_manifest)
         if (telemetry_path and trades_path) else (SKIP, "need telemetry + trades.csv")),
        ("I7", verify_label_provenance(labels, corpus_sha256)
         if labels_path else (SKIP, "no labels.csv input")),
        ("I8", verify_label_trace_resolution(labels, layer_rows)
         if labels_path else (SKIP, "no labels.csv input")),
        ("I9", verify_basis_declaration(
            labels if labels_path else None, trades if trades_path else None)
         if (labels_path or trades_path) else (SKIP, "no labels.csv or trades.csv input")),
    )
    outcomes = [
        Outcome(inv, name, status, detail)
        for inv, (status, detail) in checks
        for name in (next(n for i, n in INVARIANTS if i == inv),)
    ]
    if require_all:
        return all(o.status == PASS for o in outcomes), outcomes
    return all(o.status != FAIL for o in outcomes), outcomes


def _read_labels(path: "str | Path | None") -> list[dict]:
    if path is None:
        return []
    with Path(path).open(encoding="utf-8", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]
"""CC-CTX-RUN-SCOPED-OBSERVATION must be a real check, not a decorative catalog row.

CH-v3-unified-market-structure-v1.

A `CAN` claim class that always answers UNKNOWN grounds nothing, and a `CAN` class that answers
GROUNDED on any file that happens to exist grounds nothing either. This class exists to say "the
engine CRT state at this identified bar of this identified run was X" — the exact claim
`logs/crt_transitions.jsonl` cannot support — so the check must verify the properties that
difference rests on, and must REFUSE when they are absent.

This floor earned itself immediately: on its first real run it rejected the stream for a
one-bar coverage hole (the backtest's initialisation bar `continue`d before the emit site), a
gap that every other test in this program passed straight over.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from governance.semantic_grounding import SemanticGrounder  # noqa: E402

REL = "CC-CTX-RUN-SCOPED-OBSERVATION"
CANNOT_REL = "CC-CTX-NOT-DECISION"
STREAM_DIR = _ROOT / "logs" / "bar_structure"


def _record(i: int, **over) -> dict:
    rec = {
        "schema_version": "1.0.0",
        "run_id": "run_20260829_000000",
        "instrument": "XAUUSD",
        "timeframe": "M15",
        "corpus_path": "data/mt5/XAUUSD_M15.csv",
        "corpus_sha256": "a" * 64,
        "config_version": "v3_unified_market_structure_2026_09",
        "config_hash": "7de09f62",
        "feature_schema_version": "5.0",
        "feature_schema_hash": "f52bf5d3",
        "bar_index": i,
        "timestamp": f"2025-01-01T00:{i % 60:02d}:00",
        "phase": "LIVE",
        "crt_state_after": "RANGE",
    }
    rec.update(over)
    return rec


def _write(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


@pytest.fixture(scope="module")
def grounder() -> SemanticGrounder:
    return SemanticGrounder.load()


def _ground(grounder, path: Path, rel: str = REL):
    rel_path = path.relative_to(_ROOT).as_posix()
    return grounder.ground("JSONL", rel_path, relation=rel)


def _status(g) -> str:
    return getattr(g, "status", None) or (g.get("status") if isinstance(g, dict) else None)


# ---- the class must REFUSE the decision claim outright ------------------------------------

def test_cannot_class_refuses_regardless_of_file_contents(grounder, tmp_path):
    """`CC-CTX-NOT-DECISION` is polarity CANNOT, so it refuses before any file is read. A
    context feature influencing a decision is not a thing this stream can ever evidence."""
    p = STREAM_DIR / "_test_refusal_bar_structure.jsonl"
    _write(p, [_record(i) for i in range(10)])
    try:
        g = _ground(grounder, p, CANNOT_REL)
        assert _status(g) == "REFUSED"
    finally:
        p.unlink(missing_ok=True)


# ---- the CAN class must actually check ------------------------------------------------------

def test_gapless_identified_stream_grounds(grounder):
    p = STREAM_DIR / "_test_good_bar_structure.jsonl"
    _write(p, [_record(i) for i in range(200)])
    try:
        g = _ground(grounder, p)
        assert _status(g) == "GROUNDED", getattr(g, "ungrounded_reason", g)
    finally:
        p.unlink(missing_ok=True)


def test_a_coverage_hole_is_refused(grounder):
    """THE case this check exists for, and the one it caught in the real stream.

    A stream missing a single bar cannot answer "the state at bar i" for arbitrary i, which is
    the failure mode that leaves `logs/crt_transitions.jsonl` unidentified. One missing bar out
    of 200 must be enough to fail it.
    """
    p = STREAM_DIR / "_test_hole_bar_structure.jsonl"
    records = [_record(i) for i in range(200) if i != 77]
    _write(p, records)
    try:
        g = _ground(grounder, p)
        assert _status(g) != "GROUNDED"
        assert "gapless" in (getattr(g, "ungrounded_reason", "") or "")
    finally:
        p.unlink(missing_ok=True)


def test_missing_identity_is_refused(grounder):
    """Empty `instrument` is exactly why the global CRT transitions stream is unidentified."""
    for field in ("instrument", "corpus_sha256", "run_id"):
        p = STREAM_DIR / f"_test_no_{field}_bar_structure.jsonl"
        _write(p, [_record(i, **{field: ""}) for i in range(50)])
        try:
            g = _ground(grounder, p)
            assert _status(g) != "GROUNDED", f"grounded despite empty {field}"
            assert field in (getattr(g, "ungrounded_reason", "") or "")
        finally:
            p.unlink(missing_ok=True)


def test_two_runs_concatenated_are_refused(grounder):
    """Concatenating two runs makes `bar_index` ambiguous and silently recreates the
    unidentified failure mode, even though every individual line looks well-formed."""
    p = STREAM_DIR / "_test_two_runs_bar_structure.jsonl"
    a = [_record(i) for i in range(100)]
    b = [_record(i, run_id="run_20260830_000000") for i in range(100)]
    _write(p, a + b)
    try:
        g = _ground(grounder, p)
        assert _status(g) != "GROUNDED"
        assert "runs" in (getattr(g, "ungrounded_reason", "") or "")
    finally:
        p.unlink(missing_ok=True)


def test_absent_stream_is_unknown_not_grounded(grounder):
    """The stream is runtime-untracked, so absence is normal in a fresh clone — and must read
    as UNKNOWN rather than as either a pass or a hard error."""
    p = STREAM_DIR / "_test_absent_bar_structure.jsonl"
    p.unlink(missing_ok=True)
    g = _ground(grounder, p)
    assert _status(g) != "GROUNDED"
    assert "absent" in (getattr(g, "ungrounded_reason", "") or "")

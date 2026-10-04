"""Floors for `data_ingestion.corpus_store` -- the Parquet read-cache over an
admitted OHLCV corpus.

Per the 2026-09-09 resolution recorded in `docs/governance/CORPUS_AUTHORITY.md`'s
frozen sentence ("a stored derived CSV, if ever written, is a cache whose hash is
checked against a rebuild. Never a second admitted corpus."), this module is exactly
that cache. These floors exist to hold the two guarantees that make trusting the
cache instead of the CSV safe:

  * EQUIVALENCE -- a full-corpus `read()` must be byte-identical, row for row, to
    the pre-migration authority (`CandleLoader` on the same admitted CSV). If this
    ever diverges, the cache is wrong, not the engine reading it.
  * FAIL-CLOSED -- a cache that no longer matches its source CSV's fingerprint
    (size/mtime, or content hash under `strict=True`) must never be served. It
    raises; it does not silently fall back to stale Parquet bytes.

Runs against the real canonical XAUUSD corpus (skipped if absent), matching the
skip convention already used by `tests/test_corpus_gate.py`.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data_ingestion import corpus_store as cs  # noqa: E402
from data_ingestion.dataset_registry import admit_csv_path  # noqa: E402
from data_ingestion.xauusd_phase1_candidate import (  # noqa: E402
    PHASE1_END,
    PHASE1_ROWS,
    PHASE1_SHA256,
    PHASE1_START,
)

_REPO = Path(__file__).resolve().parents[1]
_CANONICAL = _REPO / "data" / "mt5" / "XAUUSD_M15.csv"

pytestmark = pytest.mark.skipif(
    not _CANONICAL.is_file(), reason="canonical XAUUSD corpus not present"
)


@pytest.fixture(scope="module", autouse=True)
def _built_cache():
    """Build once for the module; every test reads the same cache."""
    result = cs.build("XAUUSD", "M15")
    yield result


def test_build_matches_phase1_binding(_built_cache):
    r = _built_cache
    assert r.rows == PHASE1_ROWS
    assert r.csv_sha256 == PHASE1_SHA256
    assert r.admission_decision in ("APPROVE", "WARN")


def test_status_is_fresh_after_build():
    assert cs.status("XAUUSD", "M15", strict=True) == cs.FRESH
    assert cs.status("XAUUSD", "M15", strict=False) == cs.FRESH


def test_manifest_hash_format_is_self_consistent():
    """Regression: `admission.file_hash` (dataset_integrity's "sha256:"-prefixed
    format) must never leak into the freshness-check field -- it would make every
    build report itself STALE. See corpus_store.build()'s `source_fp` comment."""
    mpath = cs._manifest_path(_CANONICAL)
    manifest = json.loads(mpath.read_text(encoding="utf-8"))
    assert manifest["source"]["sha256"] == PHASE1_SHA256
    assert not manifest["source"]["sha256"].startswith("sha256:")
    assert manifest["admission_file_hash"].endswith(PHASE1_SHA256)


def test_full_corpus_read_matches_candleloader_byte_identical():
    """The load-bearing equivalence proof: corpus_store must not change a single
    value the pre-migration authority (CandleLoader) would have produced."""
    from runtime.backtest_v2 import CandleLoader

    store_read = cs.read("XAUUSD", "M15")
    guarded = admit_csv_path(str(_CANONICAL), "XAUUSD").filepath
    loader_candles = list(CandleLoader(guarded, "XAUUSD").stream())

    assert len(store_read.candles) == len(loader_candles) == PHASE1_ROWS
    for a, b in zip(store_read.candles, loader_candles):
        assert (a.timestamp, a.open, a.high, a.low, a.close, a.volume) == (
            b.timestamp, b.open, b.high, b.low, b.close, b.volume,
        )
    assert store_read.resolved == (PHASE1_START, PHASE1_END)


def test_windowed_read_honors_lead_in_and_window_flags():
    start = datetime(2026, 4, 1)
    end = datetime(2026, 4, 30, 23, 45)
    r = cs.read("XAUUSD", "M15", start=start, end=end, warmup_bars=400)

    assert r.lead_in_bars == 400
    assert r.window_start_idx == 400
    # every candle before window_start_idx is lead-in (in_window False), every one
    # at/after it is in_window True, and vice versa -- no interleaving.
    assert all(not f for f in r.in_window[: r.window_start_idx])
    assert all(f for f in r.in_window[r.window_start_idx:])
    assert r.candles[r.window_start_idx].timestamp >= start
    assert r.candles[-1].timestamp <= end
    # index is re-stamped 0-based over the returned slice, not the corpus-global position
    assert [c.index for c in r.candles] == list(range(len(r.candles)))


def test_window_outside_corpus_range_fails_closed():
    with pytest.raises(cs.CorpusStoreError):
        cs.read("XAUUSD", "M15", start=datetime(2030, 1, 1), end=datetime(2030, 1, 31))


def test_windowed_read_honors_tail_bars():
    """The forward-walk buffer, symmetric to lead-in: bars past `end` are served (so a
    signal near the window boundary still gets a full future to walk forward into) but
    flagged `in_window=False`, exactly like lead-in bars are before `start`."""
    start = datetime(2026, 4, 1)
    end = datetime(2026, 4, 30, 23, 45)
    r = cs.read("XAUUSD", "M15", start=start, end=end, warmup_bars=120, tail_bars=60)

    assert r.tail_bars == 60
    last_in_window_idx = max(i for i, f in enumerate(r.in_window) if f)
    tail_slice = r.in_window[last_in_window_idx + 1:]
    assert len(tail_slice) == 60
    assert all(not f for f in tail_slice)
    assert r.candles[last_in_window_idx].timestamp <= end
    assert r.candles[last_in_window_idx + 1].timestamp > end
    assert r.candles[-1].timestamp > end
    # index re-stamping still holds with a tail present
    assert [c.index for c in r.candles] == list(range(len(r.candles)))


def test_tail_bars_never_hides_an_empty_window():
    """A window with zero bars inside [start, end) must fail closed even when a large
    tail_bars would otherwise paper over it with bars from past `end`."""
    # A window landing entirely inside one 15-minute gap (no bar can satisfy both bounds)
    # -- pick two timestamps 1 second apart, guaranteed to straddle no M15 bar.
    start = datetime(2026, 4, 1, 0, 0, 1)
    end = datetime(2026, 4, 1, 0, 0, 2)
    with pytest.raises(cs.CorpusStoreError, match="zero bars"):
        cs.read("XAUUSD", "M15", start=start, end=end, tail_bars=10_000)


def test_absent_cache_fails_closed_before_build():
    assert cs.status("EURUSD_NEVER_BUILT", "M15") == cs.ABSENT
    with pytest.raises(cs.CorpusStoreError):
        cs.read("EURUSD_NEVER_BUILT", "M15")


def test_ensure_fresh_is_idempotent_and_leaves_cache_fresh():
    """The convenience wrapper every migrated call site uses: build-if-needed, always FRESH
    on return, safe to call every time (not just once)."""
    result1 = cs.ensure_fresh("XAUUSD", "M15")
    assert result1 == cs.FRESH
    # Second call: cache is already FRESH, must be a no-op (no rebuild), same result.
    result2 = cs.ensure_fresh("XAUUSD", "M15")
    assert result2 == cs.FRESH
    assert cs.status("XAUUSD", "M15", strict=True) == cs.FRESH


def test_stale_manifest_is_never_silently_served():
    """Corrupt only the manifest's recorded hash (never the real CSV, which other
    concurrent sessions in this repo may be reading) and confirm both `status()`
    and `read()` refuse rather than serving mismatched data. Restored in `finally`."""
    mpath = cs._manifest_path(_CANONICAL)
    original = mpath.read_text(encoding="utf-8")
    try:
        manifest = json.loads(original)
        manifest["source"]["sha256"] = "0" * 64
        mpath.write_text(json.dumps(manifest), encoding="utf-8")

        assert cs.status("XAUUSD", "M15", strict=True) == cs.STALE
        with pytest.raises(cs.CorpusStoreError, match="STALE"):
            cs.read("XAUUSD", "M15", strict=True)

        # non-strict compares only size/mtime, which were untouched -> still FRESH.
        # This is documenting the tradeoff, not endorsing non-strict for real reads.
        assert cs.status("XAUUSD", "M15", strict=False) == cs.FRESH
    finally:
        mpath.write_text(original, encoding="utf-8")

    assert cs.status("XAUUSD", "M15", strict=True) == cs.FRESH

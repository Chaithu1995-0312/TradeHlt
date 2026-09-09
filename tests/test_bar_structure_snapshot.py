"""BarStructureSnapshot (SEM-035): record shape, null semantics, and decision neutrality.

CH-v3-unified-market-structure-v1.

The empirical neutrality proof is the full-corpus parity harness
(`scripts/analysis/v3_config_parity.py`, arm B: emit ON vs OFF, byte-identical ledger). These
are the fast structural floors that keep the claim honest between runs:

  - the emitter cannot mutate engine or feed state (it takes read-only views and returns None);
  - the record's key order is stable, because `parquet_store._order_violation` treats a
    reordered flatten group as corruption and a scrambled vector raises no error anywhere;
  - `{f}_distance` is never null and never absent, because `0.0` means NO STRUCTURE in the
    `features.smc` convention and a null would silently become "no reading" downstream;
  - the record actually carries all ten declared context families, so requirement 3 cannot
    quietly regress to nine.
"""

from __future__ import annotations

import copy
import json
import random
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer.crt_engine_v2 import Candle  # noqa: E402
from runtime.bar_structure_snapshot import (  # noqa: E402
    SNAPSHOT_SCHEMA_VERSION,
    ZONE_FAMILIES,
    BarStructureEmitter,
    SnapshotConfig,
    _state_name,
)

WARMUP = 78
N_BARS = 320


class _FakeEngineState:
    """Minimal stand-in with the field names `_crt_block` reads. Deliberately not a real
    `EngineState`: the point is to pin the ACCESSOR contract, so a rename upstream surfaces
    here as nulls rather than as an exception nobody sees."""

    def __init__(self) -> None:
        self.atr_abs = 3.0
        self.active_range = None
        self.sweep_event = None
        self.displacement_candle = None
        self.retest_candle = None
        self.direction = None
        self.pending_displacement_ttl = None
        self.htf_remaining_candles = 5
        self.evaluating_soft_conf = False
        self.active_trade = None


def _cfg(tmp: Path) -> SnapshotConfig:
    return SnapshotConfig(
        enabled=True,
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        output_dir=str(tmp),
        filename_suffix="_bar_structure.jsonl",
        flush_every=50,
        emit_on_warmup_bars=True,
        families={},
        eqh_eql_tolerance_atr=0.1,
        eqh_eql_max_swings=8,
        memoize_break_events=True,
    )


def _emitter(tmp: Path) -> BarStructureEmitter:
    return BarStructureEmitter(
        _cfg(tmp),
        run_id="test_run",
        instrument="XAUUSD",
        timeframe="M15",
        corpus_path="data/mt5/XAUUSD_M15.csv",
        corpus_hash="0" * 64,
        config_version="v3_unified_market_structure_2026_09",
        config_hash="7de09f62",
        swing_window=2,
        smc_max_window=100,
        timestamp_basis="broker_local",
        objective_gate_enabled=False,
        objective_gate_mode="allow_exists_only",
        parent_timeframe="H4",
        htf_thresholds={"expansion_min_range_ratio": 1.2},
        feature_schema_version="5.0",
        feature_schema_hash="f52bf5d3",
    )


def _candles(n: int = N_BARS, seed: int = 11) -> list:
    rng = random.Random(seed)
    price = 2000.0
    t0 = datetime(2025, 1, 1)
    out = []
    for i in range(n):
        price += rng.gauss(0, 2)
        out.append(Candle(
            timestamp=t0 + timedelta(minutes=15 * i),
            open=price,
            high=price + abs(rng.gauss(0, 1.5)),
            low=price - abs(rng.gauss(0, 1.5)),
            close=price + rng.gauss(0, 0.8),
            volume=10.0,
            index=i,
        ))
    return out


@pytest.fixture(scope="module")
def records() -> list:
    tmp = Path(tempfile.mkdtemp())
    em = _emitter(tmp)
    st = _FakeEngineState()
    for i, c in enumerate(_candles()):
        if i < WARMUP:
            em.emit_warmup(c, i)
        else:
            em.emit(
                candle=c, bar_index=i, engine_state=st,
                result={"action": "NONE", "candle_index": i},
                prev_state="RANGE", curr_state="RANGE",
                htf_candle_id="XAUUSD-HTF-000001", parent_feed=None,
                break_of_structure=1.0, trend_bias=-1.0,
            )
    manifest = em.close()
    return [json.loads(line) for line in Path(manifest["path"]).read_text(encoding="utf-8").splitlines()]


# ---- coverage -------------------------------------------------------------------------

def test_every_bar_emits_exactly_one_gapless_record(records):
    """`bar_index` must be a gapless 0..N-1 series INCLUDING warmup.

    That gaplessness is the whole basis for `CC-CTX-RUN-SCOPED-OBSERVATION`: a stream with a
    coverage hole cannot answer "the state at bar i" for arbitrary i, which is the failure mode
    that leaves `logs/crt_transitions.jsonl` unidentified.
    """
    assert len(records) == N_BARS
    assert [r["bar_index"] for r in records] == list(range(N_BARS))
    assert sum(1 for r in records if r["phase"] == "WARMUP") == WARMUP
    assert sum(1 for r in records if r["phase"] == "LIVE") == N_BARS - WARMUP


def test_identity_fields_present_on_every_record(records):
    """The identity block is what separates this stream from the unidentified ones."""
    required = ("schema_version", "run_id", "instrument", "timeframe", "corpus_path",
                "corpus_sha256", "config_version", "config_hash",
                "feature_schema_version", "feature_schema_hash", "bar_index",
                "timestamp", "timestamp_basis", "emitted_by", "phase")
    for r in records:
        for key in required:
            assert r.get(key) is not None, f"{key} missing/null on bar {r['bar_index']}"


# ---- key order ------------------------------------------------------------------------

def test_key_order_is_stable_within_a_phase(records):
    """`parquet_store._order_violation` treats a reordered flatten group as corruption, because
    a scrambled vector raises no error anywhere downstream. Records of one phase must agree."""
    for phase in ("WARMUP", "LIVE"):
        keys = [list(r.keys()) for r in records if r["phase"] == phase]
        assert keys, f"no {phase} records"
        assert all(k == keys[0] for k in keys), f"{phase} key order drifted"


# ---- null semantics --------------------------------------------------------------------

def test_zone_distance_is_never_null_and_never_absent(records):
    """`0.0` means NO STRUCTURE (the `features.smc` convention), not zero distance. A null
    would silently read as "no measurement" and change what an absence means."""
    for r in records:
        if r["phase"] != "LIVE":
            continue
        for fam in ZONE_FAMILIES:
            key = f"{fam}_distance"
            assert key in r, f"{key} absent on bar {r['bar_index']}"
            assert r[key] is not None, f"{key} is null on bar {r['bar_index']}"
            assert isinstance(r[key], float)


def test_zone_geometry_is_null_exactly_when_absent(records):
    """Present => every geometry field populated. Absent => every geometry field null. No
    third state, so `{f}_present` can be trusted as the single presence authority."""
    geom = ("bullish", "high", "low", "mid", "formed_at_index", "age_bars", "inside")
    for r in records:
        if r["phase"] != "LIVE":
            continue
        for fam in ZONE_FAMILIES:
            present = r[f"{fam}_present"]
            for suffix in geom:
                val = r[f"{fam}_{suffix}"]
                if present:
                    assert val is not None, f"{fam}_{suffix} null while present"
                else:
                    assert val is None, f"{fam}_{suffix} populated while absent"


def test_all_ten_context_families_are_represented(records):
    """Requirement 3 cannot quietly regress to nine families."""
    live = next(r for r in records if r["phase"] == "LIVE")
    for key in (
        "crt_state_after",            # CRT
        "parent_crt_state",           # Parent CRT
        "htf_state",                  # HTF
        "objective_status",           # ObjectiveStatus
        "fvg_present",                # FVG
        "order_block_present",        # Order Block
        "breaker_present",            # Breaker
        "mitigation_present",         # Mitigation
        "choch_value",                # CHoCH
        "eqh_present", "eql_present",  # EQH/EQL
        "pdh_present", "pdl_present",  # PDH/PDL
    ):
        assert key in live, f"context family field {key} missing from the record"


def test_window_truncation_flag_is_a_warmup_marker_not_a_filter(records):
    """Documented honestly, and pinned so nobody starts filtering on it.

    `{f}_window_truncated` is `len(window) >= smc_max_window` — False only for the first ~100
    bars and True thereafter. Using it as an exclusion criterion would drop nearly the whole
    corpus while removing no bias, which is why the contract lists it under
    `forbidden_metric_substitutions`.
    """
    live = [r for r in records if r["phase"] == "LIVE"]
    truncated = [r for r in live if r["fvg_window_truncated"]]
    assert len(truncated) / len(live) > 0.9, (
        "the flag is expected to be near-constant post-warmup; if that changed, the "
        "contract's forbidden_metric_substitutions entry needs revisiting"
    )
    assert all(r["smc_window_len"] <= r["smc_max_window"] for r in live)


def test_parent_block_is_all_null_when_the_feed_is_disabled(records):
    """`ParentCRTFeed.from_prod_config` returns None when `parent_crt.enabled` is false. Null
    is the honest reading (not observed) — never 0, never a default enum member."""
    live = next(r for r in records if r["phase"] == "LIVE")
    assert live["parent_enabled"] is False
    for key in ("parent_crt_state", "parent_bias", "htf_state", "htf_range_ratio",
                "objective_status", "objective_direction"):
        assert live[key] is None


# ---- decision neutrality ---------------------------------------------------------------

def test_emit_returns_none_and_mutates_no_engine_state():
    """The structural half of the requirement 4/5 proof.

    The empirical half is the full-corpus parity harness. This pins that the emitter cannot
    influence a decision even in principle: it returns nothing a caller could branch on, and it
    leaves the engine state object it was handed bit-identical.
    """
    tmp = Path(tempfile.mkdtemp())
    em = _emitter(tmp)
    st = _FakeEngineState()
    before = copy.deepcopy(st.__dict__)
    result_dict = {"action": "NONE", "candle_index": 5}
    result_before = copy.deepcopy(result_dict)

    for i, c in enumerate(_candles(120)):
        returned = em.emit(
            candle=c, bar_index=i, engine_state=st, result=result_dict,
            prev_state="RANGE", curr_state="SWEEP",
            htf_candle_id="H4-1", parent_feed=None,
            break_of_structure=0.0, trend_bias=0.0,
        )
        assert returned is None, "emit returned a value a caller could branch on"

    assert st.__dict__ == before, "emitter mutated engine state"
    assert result_dict == result_before, "emitter mutated the process_candle result dict"


def test_disabled_emitter_writes_nothing():
    """`enabled: false` is the shipped default on v3; it must be a true no-op."""
    tmp = Path(tempfile.mkdtemp())
    cfg = _cfg(tmp)
    disabled = SnapshotConfig(**{**cfg.__dict__, "enabled": False})
    em = BarStructureEmitter(
        disabled, run_id="off", instrument="XAUUSD", timeframe="M15",
        corpus_path="c", corpus_hash="0" * 64, config_version="v3", config_hash="h",
        swing_window=2, smc_max_window=100, timestamp_basis="broker_local",
        objective_gate_enabled=False, objective_gate_mode="allow_exists_only",
        parent_timeframe="H4", htf_thresholds={}, feature_schema_version="5.0",
        feature_schema_hash="h",
    )
    st = _FakeEngineState()
    for i, c in enumerate(_candles(40)):
        em.emit_warmup(c, i)
        em.emit(candle=c, bar_index=i, engine_state=st,
                result={"action": "NONE", "candle_index": i},
                prev_state="RANGE", curr_state="RANGE",
                htf_candle_id=None, parent_feed=None)
    em.close()
    assert em.rows_written == 0
    assert not em.path.exists()


# ---- state normalisation ---------------------------------------------------------------

def test_state_name_accepts_both_enum_and_string():
    """`BacktestRunner` passes `.name` STRINGS while a direct `EngineState` read yields the
    enum. A bare `getattr(str, "name", None)` would silently write nulls into the very column
    the attribution program strata on."""
    from config_layer.state_identity import CRTState

    assert _state_name(CRTState.RANGE) == "RANGE"
    assert _state_name("SWEEP") == "SWEEP"
    assert _state_name(None) is None

"""STORY-83.11b -- mode C (`decider="resolver"`): the resolver founds the RETEST, the engine's own
soft-confirmation / risk / build_trade path decides execution.

Floors, all short synthetic fixtures (no corpus):
  * construction no longer raises; the engine-mode buffer cap is unchanged, mode C widens it;
  * founding installs the four handed-over objects from the engine's own candle buffer and
    opens the normal soft-confirmation window;
  * every non-founding outcome is a RECORDED rejection/skip, never a fabricated value;
  * `decider="engine"` never founds from a map;
  * the sidecar writer/reader round-trips and fails closed.

Grants no authority (§6.5); mode C is a comparison arm, never a parity claim (F-069).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from charts import resolver_overlay as ro
from config_layer.crt_engine_v2 import Candle
from config_layer.state_identity import VALID_TRANSITIONS, CRTState, Direction
from tests.helpers.crt_config import bar_features_for_test, crt_engine_for_test

_T0 = datetime(2026, 7, 7, 0, 0)


def _candles(n: int) -> list[Candle]:
    out = []
    for i in range(n):
        p = 100 + (i % 3) * 0.5
        out.append(Candle(_T0 + timedelta(minutes=15 * i), p, p + 1, p - 1, p + 0.2))
    return out


def _row(cs: list[Candle], **over) -> dict:
    ts = cs[-1].timestamp.isoformat()
    row = dict(timestamp=ts, direction="LONG", h_ref="102.0", l_ref="99.0",
               sweep_ts=cs[10].timestamp.isoformat(),
               displacement_ts=cs[12].timestamp.isoformat(), retest_ts=ts)
    row.update(over)
    return row


def _run(engine, cs):
    action = None
    for c in cs:
        action = engine.process_candle(c, "H1", bar_features=bar_features_for_test())
    return action


def _mode_c(cs, **row_over):
    e = crt_engine_for_test(decider="resolver")
    e.set_founding_map({cs[-1].timestamp.isoformat(): _row(cs, **row_over)})
    return e


def test_mode_c_constructs_and_widens_only_its_own_buffer():
    e_c, e_e = crt_engine_for_test(decider="resolver"), crt_engine_for_test()
    cfg = e_e.config
    assert e_e._buffer_cap == cfg.atr_period * cfg.atr_buffer_multiplier  # engine mode: unchanged
    assert e_c._buffer_cap > e_e._buffer_cap
    assert e_c._buffer_cap >= e_e._buffer_cap + cfg.max_expansion_age_candles


def test_resolver_founding_edge_is_declared():
    assert CRTState.RETEST in VALID_TRANSITIONS[CRTState.RANGE]


def test_mode_c_without_a_map_fails_closed():
    e = crt_engine_for_test(decider="resolver")
    with pytest.raises(RuntimeError, match="set_founding_map"):
        e.process_candle(_candles(1)[0], "H1", bar_features=bar_features_for_test())


def test_engine_mode_refuses_a_founding_map():
    with pytest.raises(ValueError):
        crt_engine_for_test().set_founding_map({})


def test_founding_installs_the_four_objects_and_opens_soft_conf():
    cs = _candles(30)
    e = _mode_c(cs)
    action = _run(e, cs)
    st = e.state
    assert action["action"] == "RETEST_CONFIRMED"
    assert st.current_state is CRTState.RETEST and st.evaluating_soft_conf
    assert st.direction is Direction.LONG
    assert (st.active_range.h_ref, st.active_range.l_ref) == (102.0, 99.0)
    assert st.retest_candle is cs[-1]
    assert st.displacement_candle is cs[12]              # the engine's own buffered candle
    assert st.sweep_event.candle is cs[10]
    assert st.sweep_event.price == cs[10].low            # LONG = low swept (detect_sweep geometry)
    assert st.sweep_event.double_confirmed is False      # not resolver-owned -> not inferred
    assert st.cached_features is not None and "displacement_atr_ratio" in st.cached_features
    assert any(ev.event == "BEGIN_SOFT_CONF" for ev in st.event_log)


def test_short_direction_uses_the_swept_high():
    cs = _candles(30)
    e = _mode_c(cs, direction="SHORT")
    _run(e, cs)
    assert e.state.direction is Direction.SHORT
    assert e.state.sweep_event.price == cs[10].high


def test_missing_bar_is_a_recorded_rejection_not_a_founding():
    cs = _candles(30)
    e = _mode_c(cs, sweep_ts=(_T0 - timedelta(days=9)).isoformat())
    action = _run(e, cs)
    assert action["action"] == "RESOLVER_FOUNDING_REJECTED"
    assert action["reason"] == "resolver_founding_bar_missing"
    assert e.state.current_state is CRTState.RANGE and not e.state.evaluating_soft_conf
    assert e.state.sweep_event is None and e.state.displacement_candle is None


def test_unknown_direction_is_a_recorded_rejection():
    cs = _candles(30)
    action = _run(_mode_c(cs, direction="NONE"), cs)
    assert action["reason"] == "resolver_founding_direction_unknown"


def test_busy_engine_skips_founding():
    cs = _candles(30)
    e = _mode_c(cs)
    _run(e, cs[:-1])
    e.state.evaluating_soft_conf = True                  # a soft-conf window is already open
    e.process_candle(cs[-1], "H1", bar_features=bar_features_for_test())
    assert any(ev.event == "RESOLVER_FOUNDING_SKIPPED" for ev in e.state.event_log)
    assert e.state.retest_candle is None                 # nothing installed over the open window


def test_off_state_bar_resets_to_range_before_founding():
    cs = _candles(30)
    e = _mode_c(cs)
    _run(e, cs[:-1])
    e.state.current_state = CRTState.SWEEP               # engine mid-episode of its own
    action = e.process_candle(cs[-1], "H1", bar_features=bar_features_for_test())
    assert action["action"] == "RETEST_CONFIRMED" and e.state.current_state is CRTState.RETEST


# ── sidecar ────────────────────────────────────────────────────────────────

def test_founding_row_converts_indices_to_timestamps_by_calibrated_offset():
    stamps = [_T0 + timedelta(minutes=15 * i) for i in range(50)]
    # resolver counter is 1-based (bar i has candle_index i+1); the offset is calibrated on the
    # retest index itself, so the row does not depend on that convention.
    mem = SimpleNamespace(retest_candle_index=31, sweep_candle_index=11,
                          displacement_candle_index=13, displacement_direction=-1,
                          range_h_ref=102.0, range_l_ref=99.0)
    row = ro._founding_row(mem, 30, stamps)
    assert row["timestamp"] == row["retest_ts"] == stamps[30].isoformat()
    assert row["sweep_ts"] == stamps[10].isoformat()
    assert row["displacement_ts"] == stamps[12].isoformat()
    assert row["direction"] == "SHORT" and row["h_ref"] == "102.0"


def test_founding_row_writes_unknown_indices_empty_never_guessed():
    stamps = [_T0 + timedelta(minutes=15 * i) for i in range(5)]
    mem = SimpleNamespace(retest_candle_index=4, sweep_candle_index=-1,
                          displacement_candle_index=-1, displacement_direction=0,
                          range_h_ref=1.0, range_l_ref=0.0)
    row = ro._founding_row(mem, 3, stamps)
    assert row["sweep_ts"] == "" and row["displacement_ts"] == "" and row["direction"] == "NONE"


def _write_cache(root, sha, rows, meta_rows=None, meta_sha=None):
    d = root / f"XAUUSD__{sha[:8]}__default"
    d.mkdir(parents=True)
    import csv
    import json
    with open(d / ro.FOUNDING_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ro.FOUNDING_FIELDS)
        w.writeheader()
        w.writerows(rows)
    (d / "meta.json").write_text(json.dumps({
        "corpus_sha256": meta_sha or sha,
        "founding_rows": len(rows) if meta_rows is None else meta_rows}), encoding="utf-8")


def test_load_founding_map_round_trip_and_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(ro, "CACHE_ROOT", tmp_path)
    sha = "a" * 64
    cs = _candles(30)
    rows = [_row(cs)]
    _write_cache(tmp_path, sha, rows)
    assert ro.load_founding_map("XAUUSD", sha) == {rows[0]["timestamp"]: rows[0]}

    with pytest.raises(FileNotFoundError):                          # never built
        ro.load_founding_map("XAUUSD", "b" * 64)

    sha2 = "c" * 64
    _write_cache(tmp_path, sha2, rows, meta_sha="d" * 64)           # stale
    with pytest.raises(ValueError, match="stale"):
        ro.load_founding_map("XAUUSD", sha2)

    sha3 = "e" * 64
    _write_cache(tmp_path, sha3, rows, meta_rows=5)                 # truncated / edited
    with pytest.raises(ValueError, match="row count"):
        ro.load_founding_map("XAUUSD", sha3)

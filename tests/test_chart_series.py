"""Acceptance floor for INFRA-CPC-V1 Workstream A0 (own OHLC chart renderer).

Test ids map to the design's §9 acceptance criteria:
  A-AC1  exported series OHLC matches the source corpus exactly (sample N>=50)
  A-AC3  legend lists colour tokens by name + clock basis
  A-AC3b legend never conflates pipeline FM-043/044 with CRT soft-conf EMAs
  Z-AC1  no ZONE-X module reachable from chart code

plus the causality and fail-closed properties this implementation relies on.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from charts import chart_series as cs          # noqa: E402
from charts import crt_overlay as co           # noqa: E402
from charts import render as rd                # noqa: E402
from config_layer.crt_engine_v2 import Candle  # noqa: E402

CORPUS = _REPO / "data" / "mt5" / "XAUUSD_M15.csv"


def _synth(n: int, start: datetime | None = None, step_min: int = 15) -> list[Candle]:
    """Deterministic synthetic M15 candles (no randomness, no network)."""
    t0 = start or datetime(2024, 5, 22, 1, 0, 0)
    out = []
    for i in range(n):
        base = 2400.0 + (i % 37) * 1.5 - (i % 11) * 0.75
        out.append(Candle(
            timestamp=t0 + timedelta(minutes=step_min * i),
            open=base,
            high=base + 2.0,
            low=base - 2.0,
            close=base + ((1.0) if i % 2 == 0 else (-1.0)),
            volume=100.0 + i,
            index=i,
        ))
    return out


# ── Z-AC1 ──────────────────────────────────────────────────────────────────────
def test_zac1_no_zonex_import_in_chart_code():
    """Z-AC1: chart code must not import any ZONE-X module."""
    for mod in ("chart_series.py", "crt_overlay.py", "render.py", "__init__.py"):
        text = (_SRC / "charts" / mod).read_text(encoding="utf-8").lower()
        assert "zone_x" not in text and "zonex" not in text, f"ZONE-X reachable from {mod}"


# ── timeframe ladder / causality ───────────────────────────────────────────────
@pytest.mark.parametrize("n", [96, 97, 400, 401, 404])
def test_timeframe_aggregation_agrees_on_every_emitted_bucket(n):
    """M15->H1->H4 and M15->H4 agree on every bucket BOTH emit.

    Measured 2026-08-22: prefix equality always holds; the two paths differ only in
    COUNT, by at most one trailing bucket, and only when the series ends exactly on a
    bucket boundary (the H1 pass has already dropped the final complete-but-unflushed
    hour, so the H4 pass never sees it). `to_timeframe` always resamples direct from
    M15 and never composes, so this cannot affect a chart — the test pins the real
    property so a future refactor cannot quietly widen the divergence.
    """
    base = _synth(n)
    direct = cs.to_timeframe(base, "H4")
    via_h1 = cs.to_timeframe(cs.to_timeframe(base, "H1"), "H4")
    k = min(len(direct), len(via_h1))
    key = lambda c: (c.timestamp, c.open, c.high, c.low, c.close)  # noqa: E731
    assert [key(c) for c in direct[:k]] == [key(c) for c in via_h1[:k]]
    assert 0 <= len(direct) - len(via_h1) <= 1


def test_trailing_partial_bucket_is_dropped():
    """A bucket is emitted only once a later bucket opens — no in-progress bar leaks."""
    base = _synth(5)                       # 5 * 15min = 75min -> H1 bucket 2 is partial
    h1 = cs.to_timeframe(base, "H1")
    assert len(h1) == 1
    assert h1[0].timestamp == datetime(2024, 5, 22, 1, 0, 0)


def test_aggregation_never_fabricates_candles_across_a_gap():
    """A gap yields fewer buckets, never synthetic filler bars."""
    a = _synth(8)
    b = _synth(8, start=datetime(2024, 5, 27, 1, 0, 0))     # skip the weekend
    h1 = cs.to_timeframe(a + b, "H1")
    days = {c.timestamp.date() for c in h1}
    assert days == {datetime(2024, 5, 22).date(), datetime(2024, 5, 27).date()}


def test_unsupported_timeframe_raises():
    with pytest.raises(ValueError):
        cs.to_timeframe(_synth(10), "M3")


# ── state projection ───────────────────────────────────────────────────────────
def test_downsample_takes_state_at_bucket_close_not_a_later_one():
    base = _synth(8)                                   # 2 full H1 buckets
    states = ["RANGE"] * 4 + ["SWEEP"] * 4
    states[3] = "DISPLACEMENT"                         # last child of bucket 1
    h1 = cs.to_timeframe(base, "H1")
    got = cs.downsample_states(base, states, h1, "H1")
    assert got[0] == "DISPLACEMENT", "bucket must take the state as of its LAST child"


def test_downsample_missing_bucket_is_unavailable_not_borrowed():
    base = _synth(4)
    htf = cs.to_timeframe(base, "H1") + [
        Candle(timestamp=datetime(2030, 1, 1), open=1, high=1, low=1, close=1)
    ]
    got = cs.downsample_states(base, ["RANGE"] * 4, htf, "H1")
    assert got[-1] == cs.CRT_UNAVAILABLE


def test_m15_downsample_is_identity():
    base = _synth(6)
    states = ["RANGE", "SWEEP", "SWEEP", "EXPANSION", "RETEST", "RANGE"]
    assert cs.downsample_states(base, states, base, "M15") == states


# ── ChartSeries invariants ─────────────────────────────────────────────────────
def test_series_rejects_misaligned_state_track():
    with pytest.raises(ValueError):
        cs.ChartSeries("XAUUSD", "M15", _synth(5), ["RANGE"] * 4, "NONE", {})


def test_state_changes_marks_every_transition():
    s = cs.ChartSeries("X", "M15", _synth(6),
                       ["RANGE", "RANGE", "SWEEP", "SWEEP", "EXPANSION", "RANGE"],
                       "RESOLVED:test", {})
    assert s.state_changes() == [2, 4, 5]


# ── legend (A-AC3 / A-AC3b) ────────────────────────────────────────────────────
def _legend(states: list[str]) -> dict:
    s = cs.ChartSeries("XAUUSD", "H4", _synth(len(states)), states, "RESOLVED:vX",
                       {"session_timestamp_basis": "broker_local"})
    return cs.build_legend(s)


def test_aac3_legend_lists_tokens_and_clock_basis():
    leg = _legend(["RANGE", "SWEEP", "EXPANSION"])
    assert leg["crt_color_tokens"] == {
        "RANGE": "crt.range", "SWEEP": "crt.sweep", "EXPANSION": "crt.exp"}
    assert leg["session_timestamp_basis"] == "broker_local"
    assert "F-066" in leg["clock_note"]
    for tok in leg["crt_color_tokens"].values():
        assert leg["crt_token_hex"][tok].startswith("#")


def test_aac3_legend_omits_states_not_present():
    leg = _legend(["RANGE"])
    assert "EXECUTION" not in leg["crt_color_tokens"]


def test_aac3b_legend_separates_pipeline_and_crt_emas():
    guard = _legend(["RANGE"])["ema_label_guard"]
    assert "FM-043" in guard and "crt_live_ema_fast" in guard and "DISTINCT" in guard


def test_legend_declares_a1_a2_layers_absent():
    """A0 must not advertise story tags or an FM panel it does not draw."""
    leg = _legend(["RANGE"])
    assert leg["layers"]["V0_bars"] is True
    assert leg["layers"]["V2_story_tags"] is False
    assert leg["layers"]["V3_fm_panel"] is False


# ── CRT overlay fail-closed behaviour ──────────────────────────────────────────
def test_alignment_joins_on_timestamp_not_candle_index():
    """Regression: the two event families do NOT share an index basis.

    Measured on the real run - STATE_TRANSITION sits at shift +62 while 121 session-gap
    RESETs sit at shift 0. Joining on `candle_index` (with or without a unanimity
    requirement) is therefore wrong; the timestamp is the only unambiguous key.
    """
    ts = [c.timestamp for c in _synth(300)]
    events = [
        (70 - 62, "SWEEP", ts[70]),        # shift +62, like a STATE_TRANSITION
        (150, "RANGE", ts[150]),           # shift 0, like a session-gap RESET
        (240 - 62, "EXPANSION", ts[240]),
    ]
    placed = co._bar_positions(events, ts)
    assert [p[0] for p in placed] == [70, 150, 240]
    assert [p[1] for p in placed] == ["SWEEP", "RANGE", "EXPANSION"]


def test_alignment_fails_closed_on_foreign_corpus():
    """A timestamp absent from the base series is a wrong corpus, not a shift."""
    ts = [c.timestamp for c in _synth(50)]
    events = [(4, "SWEEP", ts[3]), (9, "SWEEP", datetime(1999, 1, 1))]
    with pytest.raises(ValueError, match="absent from the base series"):
        co._bar_positions(events, ts)


def test_alignment_rejects_empty_event_stream():
    with pytest.raises(ValueError):
        co._bar_positions([], [c.timestamp for c in _synth(5)])


def test_index_shift_diagnostic_reports_disagreement_without_gating():
    """The shift is recorded, not enforced - a mixed stream must still render."""
    ts = [c.timestamp for c in _synth(300)]
    events = [(70 - 62, "SWEEP", ts[70]), (150, "RANGE", ts[150]),
              (240 - 62, "X", ts[240])]
    d = co.index_shift_diagnostic(events, ts)
    assert d["modal_shift"] == 62
    assert d["distinct_shifts"] == 2
    assert 0 < d["agreement"] < 1


def test_forward_fill_starts_at_range_and_holds():
    states = co._forward_fill([(3, "SWEEP"), (6, "EXPANSION")], 9)
    assert states == ["RANGE"] * 3 + ["SWEEP"] * 3 + ["EXPANSION"] * 3


def test_unavailable_track_never_emits_a_real_state():
    tr = co.unavailable("spine down", 12)
    assert set(tr.states) == {cs.CRT_UNAVAILABLE}
    assert not tr.resolved
    assert tr.version is None and tr.offset is None
    assert cs.CRT_UNAVAILABLE not in cs.CRT_COLOR_TOKENS


# ── render degradation ─────────────────────────────────────────────────────────
def test_svg_fallback_renders_without_mplfinance(tmp_path):
    s = cs.ChartSeries("XAUUSD", "H1", _synth(40), ["RANGE"] * 20 + ["SWEEP"] * 20,
                       "RESOLVED:vX", {"session_timestamp_basis": "broker_local"})
    names = rd.render_tiles(s, tmp_path, fmt="svg")
    assert names == ["chart_H1_01.svg"]
    body = (tmp_path / names[0]).read_text(encoding="utf-8")
    assert body.startswith("<svg") and body.rstrip().endswith("</svg>")
    assert "SWEEP" in body                      # legend swatch present


def test_tiling_splits_and_covers_every_bar(tmp_path):
    s = cs.ChartSeries("XAUUSD", "H1", _synth(25), [cs.CRT_UNAVAILABLE] * 25,
                       "NONE", {})
    names = rd.render_tiles(s, tmp_path, bars_per_tile=10, fmt="svg")
    assert len(names) == 3                      # 10 + 10 + 5


def test_state_runs_are_contiguous_and_total():
    runs = rd._state_runs(["A", "A", "B", "B", "B", "C"])
    assert runs == [(0, 1, "A"), (2, 4, "B"), (5, 5, "C")]
    assert sum(b - a + 1 for a, b, _ in runs) == 6


# ── export pack ────────────────────────────────────────────────────────────────
def test_export_pack_writes_every_contract_file(tmp_path):
    s = cs.ChartSeries("XAUUSD", "D1", _synth(5), ["RANGE"] * 5, "NONE",
                       {"active_version": "vX", "session_timestamp_basis": "broker_local"})
    out = cs.write_export(s, tmp_path, chart_files=["chart_D1_01.png"])
    for f in ("series.csv", "legend.json", "config_pin.json", "INDEX.md"):
        assert (out / f).is_file(), f"missing {f}"
    assert json.loads((out / "legend.json").read_text())["design_id"] == "INFRA-CPC-V1"
    assert "chart_D1_01.png" in (out / "INDEX.md").read_text()


def test_series_csv_roundtrips_floats_exactly(tmp_path):
    base = _synth(20)
    s = cs.ChartSeries("XAUUSD", "M15", base, ["RANGE"] * 20, "NONE", {})
    cs.write_export(s, tmp_path)
    with open(tmp_path / "series.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 20
    for row, c in zip(rows, base):
        assert float(row["open"]) == c.open
        assert float(row["close"]) == c.close


# ── A-AC1: real corpus parity ──────────────────────────────────────────────────
@pytest.mark.skipif(not CORPUS.is_file(), reason="XAUUSD corpus not present")
def test_aac1_exported_m15_bars_match_source_csv_exactly():
    """A-AC1: sample N>=50 exported bars must equal the source rows byte-for-value."""
    base = cs.load_base_candles(CORPUS, "XAUUSD")
    with open(CORPUS, newline="", encoding="utf-8-sig") as f:
        src = list(csv.DictReader(f))
    assert len(base) == len(src)

    n = len(base)
    sample = [0, 1, 2, n - 3, n - 2, n - 1] + [(i * n) // 60 for i in range(60)]
    checked = 0
    for i in sorted(set(sample)):
        c, row = base[i], src[i]
        assert c.timestamp == datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
        assert c.open == float(row["open"])
        assert c.high == float(row["high"])
        assert c.low == float(row["low"])
        assert c.close == float(row["close"])
        checked += 1
    assert checked >= 50, f"A-AC1 requires N>=50, sampled {checked}"


@pytest.mark.skipif(not CORPUS.is_file(), reason="XAUUSD corpus not present")
def test_corpus_identity_is_pinned_in_config_pin():
    """The export must carry the corpus sha256 the fail-closed guard binds."""
    from data_ingestion.xauusd_phase1_candidate import PHASE1_SHA256
    pin = cs.build_config_pin("XAUUSD", CORPUS)
    assert pin["corpus_sha256"] == PHASE1_SHA256
    assert pin["session_timestamp_basis"]


# ── CRT aliasing guard ─────────────────────────────────────────────────────────
def test_aliasing_flagged_when_bar_spans_more_than_the_state_dwell():
    """D1 swallows ~5 CRT transitions per bar, so its colour must be labelled aliased."""
    # Real XAUUSD shape: 47,275 base bars / 2,382 transitions -> dwell ~19.8;
    # 515 D1 buckets -> ~92 base bars per bucket -> undersampled.
    s = cs.ChartSeries("XAUUSD", "D1", _synth(515), ["SWEEP"] * 515, "RESOLVED:vX", {},
                       base_bars=47275, base_transitions=2382)
    al = cs.crt_aliasing(s)
    assert al["aliased"] is True
    assert al["bars_per_bucket"] > al["mean_dwell_base_bars"]
    assert "ALIASED" in al["note"]


def test_aliasing_regression_low_change_rate_does_not_mean_legible():
    """The FIRST implementation used change-rate>0.5 and would have passed D1.

    D1's real change rate is 0.327 because SWEEP dominates 69% of buckets — a LOW rate is
    what heavy undersampling of a dominant-state process looks like. Pin the correction.
    """
    states = (["SWEEP"] * 7 + ["EXPANSION"] * 3) * 50          # rate 0.2, well under 0.5
    s = cs.ChartSeries("XAUUSD", "D1", _synth(500), states, "RESOLVED:vX", {},
                       base_bars=47275, base_transitions=2382)
    al = cs.crt_aliasing(s)
    assert al["change_rate"] < 0.5
    assert al["aliased"] is True, "low change rate must NOT be read as legible"


def test_aliasing_not_flagged_when_sampling_is_fine_enough():
    """H4 spans ~15 base bars, inside the ~20-bar dwell -> legible."""
    s = cs.ChartSeries("XAUUSD", "H4", _synth(3094), ["RANGE"] * 3094, "RESOLVED:vX", {},
                       base_bars=47275, base_transitions=2382)
    al = cs.crt_aliasing(s)
    assert al["aliased"] is False
    assert "Legible" in al["note"]


def test_aliasing_undetermined_without_base_facts():
    """Absent dwell data the answer is UNDETERMINED, never a confident 'legible'."""
    s = cs.ChartSeries("XAUUSD", "D1", _synth(100), ["RANGE"] * 100, "RESOLVED:vX", {})
    al = cs.crt_aliasing(s)
    assert al["aliased"] is False
    assert "UNDETERMINED" in al["note"]


def test_aliasing_absent_without_a_crt_layer():
    s = cs.ChartSeries("XAUUSD", "D1", _synth(10), [cs.CRT_UNAVAILABLE] * 10, "NONE", {})
    assert cs.crt_aliasing(s)["aliased"] is False
    assert cs.build_legend(s)["crt_aliasing"]["change_rate"] is None


def test_aliasing_warning_reaches_the_image_title():
    """The PNG travels without legend.json, so the warning must be in the title."""
    states = ["RANGE", "SWEEP"] * 50
    s = cs.ChartSeries("XAUUSD", "D1", _synth(100), states, "RESOLVED:vX",
                       {"session_timestamp_basis": "broker_local"},
                       base_bars=47275, base_transitions=2382)
    assert "ALIASED" in rd._title(s, 0, 99)


# ── RESET handling (regression) ────────────────────────────────────────────────
def test_reset_events_return_the_machine_to_range(tmp_path):
    """RESET is the ONLY way back to RANGE — a transition-only parser is wrong.

    Measured on the real XAUUSD run: STATE_TRANSITION into RANGE occurs 0 times, while
    1,798 RESET events carry a non-RANGE `state_from`. Reading transitions alone
    forward-fills SWEEP/EXPANSION forever and yields a chart on which the engine is
    essentially never in RANGE — plausible-looking, and a pure parser artifact.
    """
    ev = tmp_path / "X_events.jsonl"
    rows = [
        {"event": "STATE_TRANSITION", "timestamp": "2024-05-22T01:30:00",
         "candle_index": 2, "state_from": "RANGE", "state_to": "SWEEP"},
        {"event": "RESET", "timestamp": "2024-05-22T02:00:00",
         "candle_index": 4, "state_from": "SWEEP", "state_to": "RANGE"},
    ]
    ev.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    parsed = co._parse_state_events(ev)
    assert [p[1] for p in parsed] == ["SWEEP", "RANGE"], "RESET must be parsed"

    states = co._forward_fill(co._bar_positions(parsed, [datetime(2024,5,22,1,0)+timedelta(minutes=15*i) for i in range(7)]), 7)
    assert states == ["RANGE", "RANGE", "SWEEP", "SWEEP", "RANGE", "RANGE", "RANGE"]


def test_same_bar_reset_and_transition_keep_engine_emission_order(tmp_path):
    """When both land on one bar, file order decides — not a sort on candle_index."""
    ev = tmp_path / "X_events.jsonl"
    rows = [
        {"event": "RESET", "timestamp": "2024-05-22T01:15:00",
         "candle_index": 1, "state_from": "SWEEP", "state_to": "RANGE"},
        {"event": "STATE_TRANSITION", "timestamp": "2024-05-22T01:15:00",
         "candle_index": 1, "state_from": "RANGE", "state_to": "SWEEP"},
    ]
    ev.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    parsed = co._parse_state_events(ev)
    assert [p[1] for p in parsed] == ["RANGE", "SWEEP"]
    assert co._forward_fill(co._bar_positions(parsed, [datetime(2024,5,22,1,0)+timedelta(minutes=15*i) for i in range(3)]), 3)[1] == "SWEEP"   # last emission on the bar wins


def test_aliasing_uses_window_matched_base_count():
    """base_bars must track the SAME window as the bars, or the ratio is nonsense.

    Regression: a 3-month H1 window (1,464 bars) divided by the FULL 47,275-bar corpus
    reported 32.3 base bars per H1 bucket. An H1 bar spans 4.
    """
    s = cs.ChartSeries("XAUUSD", "H1", _synth(1464), ["RANGE"] * 1464, "RESOLVED:vX", {},
                       base_bars=5856, base_transitions=650)     # 4 base bars per bucket
    al = cs.crt_aliasing(s)
    assert al["bars_per_bucket"] == 4.0
    assert al["aliased"] is False

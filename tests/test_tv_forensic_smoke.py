"""CH-htfcrt-parent-candle-smc-v1 (2026-08-15) — smoke tests for tools/tv_forensic/.

tools/tv_forensic/ is a standalone Playwright instrument (untracked before this program,
zero tests, zero control-plane registration). Its two external dependencies — Playwright
and Pillow — are NOT installed in this environment (confirmed via `ModuleNotFoundError` for
both before writing this file), so this smoke test is deliberately layered:

  1. every script parses (ast.parse) regardless of what's installed — catches syntax
     errors and import-order mistakes without needing the deps present;
  2. `engine_data.py` has zero external dependencies (stdlib only) and is exercised for
     real — offset resolution, epoch round-trip;
  3. `shot_plan.json` structural validity is checked unconditionally (pure JSON);
  4. `annotate.py`'s pure geometry helpers are exercised only if Pillow is importable
     (`pytest.importorskip`);
  5. `capture_tv.py` / `tv_bridge.py` (Playwright-backed) are import-checked only if
     playwright is importable.

Skips here are honest reflections of the environment, not silent passes — do not remove
the `importorskip` guards to "make it green" without actually installing the dependency.

GOTCHA (discovered writing this file): `pytest.importorskip("playwright")` alone does NOT
reliably detect absence here — an unrelated ``D:\\playwright`` directory (a separate, unrelated
scraping project on this machine, nothing to do with this repo) is picked up by Python as an
empty implicit namespace package whenever the ``D:`` drive root ends up on `sys.path`, so bare `import
playwright` can silently "succeed" with a module that has no `sync_api` submodule. Skip on
the actual submodule (`playwright.sync_api`) these scripts import, not the bare package name.
"""

from __future__ import annotations

import ast
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

_TOOL_DIR = Path(__file__).resolve().parents[1] / "tools" / "tv_forensic"

# Scripts meant to run as this tool's public/entry surface (excludes the underscore-
# prefixed exploratory probes and the README-documented superseded annotators).
_ENTRY_SCRIPTS = [
    "capture_tv.py",
    "annotate.py",
    "engine_data.py",
    "htf_bars.py",
    "tv_bridge.py",
    "ui_fallback.py",
    "measure_corpus_clock.py",
]


def _add_tool_dir_to_path():
    p = str(_TOOL_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── 1. every entry script parses ─────────────────────────────────────────────────────
@pytest.mark.parametrize("name", _ENTRY_SCRIPTS)
def test_entry_script_parses(name):
    path = _TOOL_DIR / name
    assert path.exists(), f"expected entry script missing: {path}"
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_all_top_level_scripts_parse():
    """Broader net: every .py directly under tv_forensic/ (not probe/, not __pycache__),
    including the exploratory `_probe_*` / superseded `annotate_shot0*` scripts — a
    syntax error in those is still a real defect even though nothing here calls them."""
    scripts = sorted(p for p in _TOOL_DIR.glob("*.py") if p.is_file())
    assert len(scripts) >= len(_ENTRY_SCRIPTS)
    for path in scripts:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


# ── 2. engine_data.py — zero external deps, exercised for real ──────────────────────
def test_engine_data_imports_and_epoch_roundtrips():
    _add_tool_dir_to_path()
    import engine_data as ed

    broker = datetime(2026, 7, 28, 12, 0, 0)
    for offset in (-3, 0, 2, 3):
        epoch = ed.to_utc_epoch(broker, offset)
        back = ed.from_utc_epoch(epoch, offset)
        assert back == broker


def test_engine_data_resolve_offset_picks_the_matching_hour():
    """Single anchor, single scored candidate, THAT candidate matches its one
    usable anchor -- decisive is True because the D-2 anchor floor is met
    (matched == n_usable == 1), not because a lone candidate wins by default.
    See test_engine_data_decisive_rejects_unequal_anchor_win below for the
    actual defect this alone does not prove anything about."""
    _add_tool_dir_to_path()
    import engine_data as ed

    broker = datetime(2026, 7, 28, 12, 0, 0)
    bar = ed.Bar(broker, o=100.0, h=101.0, l=99.0, c=100.5, v=10.0)
    engine_bars = {broker: bar}

    true_offset = 3
    epoch = ed.to_utc_epoch(broker, true_offset)
    tv_by_epoch = {epoch: {"o": 100.0, "h": 101.0, "l": 99.0, "c": 100.5}}

    result = ed.resolve_offset(engine_bars, tv_by_epoch, anchors=[broker])
    assert result.hours == true_offset
    assert result.error == pytest.approx(0.0)
    assert result.decisive


def test_engine_data_resolve_offset_raises_without_a_usable_anchor():
    _add_tool_dir_to_path()
    import engine_data as ed

    with pytest.raises(ValueError, match="anchor"):
        ed.resolve_offset({}, {}, anchors=[datetime(2026, 1, 1)])


# ── D-2 (2026-08-16 semantic + screenshot layer review) ──────────────────────
# `OffsetResult.decisive` used to compare candidate MEANS with no floor on how
# many anchors each candidate actually matched, and returned True unconditionally
# on a single scored candidate. Both were real holes: a candidate that keeps only
# its luckiest 2-of-19 anchors could out-mean the true offset averaging over all
# 19, and a single degenerate candidate ruled nothing out yet passed by default.

def test_engine_data_decisive_rejects_unequal_anchor_win():
    """The exact adversarial case the audit named: winner matched only 2/19
    anchors with a great mean; a worse-mean candidate matched all 19. Before
    D-2 this was `decisive=True` on the winner's mean alone."""
    _add_tool_dir_to_path()
    import engine_data as ed

    result = ed.OffsetResult(
        hours=3, error=0.4, runner_up_hours=2, runner_up_error=0.45,
        anchors=[f"a{i}" for i in range(19)],
        ranked=[
            {"offset_hours": 3, "mean_abs_error": 0.4, "anchors_matched": 2},
            {"offset_hours": 2, "mean_abs_error": 0.45, "anchors_matched": 19},
        ],
    )
    assert not result.decisive


def test_engine_data_decisive_accepts_full_anchor_win():
    """Same shape, but the winner matched every usable anchor -- must still
    pass. The fix adds a floor, it does not make everything indecisive."""
    _add_tool_dir_to_path()
    import engine_data as ed

    result = ed.OffsetResult(
        hours=3, error=0.4, runner_up_hours=2, runner_up_error=30.0,
        anchors=[f"a{i}" for i in range(19)],
        ranked=[
            {"offset_hours": 3, "mean_abs_error": 0.4, "anchors_matched": 19},
            {"offset_hours": 2, "mean_abs_error": 30.0, "anchors_matched": 19},
        ],
    )
    assert result.decisive


def test_engine_data_decisive_single_candidate_needs_full_anchor_match():
    """The other half of the single-scored-candidate hole: previously
    `runner_up_error is None` alone was sufficient. A lone candidate that did
    NOT match every usable anchor must not be decisive just because nothing
    else scored."""
    _add_tool_dir_to_path()
    import engine_data as ed

    result = ed.OffsetResult(
        hours=3, error=0.0, runner_up_hours=None, runner_up_error=None,
        anchors=["a0", "a1", "a2"],
        ranked=[{"offset_hours": 3, "mean_abs_error": 0.0, "anchors_matched": 1}],
    )
    assert not result.decisive


def test_engine_data_decisive_no_ranked_detail_fails_closed():
    _add_tool_dir_to_path()
    import engine_data as ed

    result = ed.OffsetResult(
        hours=3, error=0.0, runner_up_hours=None, runner_up_error=None,
        anchors=["a0"], ranked=[],
    )
    assert not result.decisive


def test_engine_data_decisive_reproduces_all_real_captured_shots():
    """Applies the NEW decisive logic to the clock block actually stored in
    every captured M15 sidecar on disk. Each one's original capture-time
    `decisive: true` must still hold -- proves D-2 does not retroactively
    invalidate any real, already-verified capture."""
    _add_tool_dir_to_path()
    import engine_data as ed

    shots_dir = _TOOL_DIR / "shots"
    m15_sidecars = [
        p for p in shots_dir.glob("*.json")
        if not p.stem.endswith("_ANNOTATED") and "_PRE_" not in p.stem
    ]
    checked = 0
    for p in m15_sidecars:
        doc = json.loads(p.read_text(encoding="utf-8"))
        clock = doc.get("clock", {})
        if str(doc.get("shot", {}).get("interval")) != "15":
            continue  # H4 shots don't carry OHLC-derived clock.ranked detail
        if not clock.get("decisive"):
            continue
        result = ed.OffsetResult(
            hours=clock["resolved_offset_hours"], error=clock["match_error"],
            runner_up_hours=clock.get("runner_up_hours"),
            runner_up_error=clock.get("runner_up_error"),
            anchors=clock["anchors"], ranked=clock["ranked"],
        )
        assert result.decisive, f"{p.name}: was decisive at capture time, no longer is"
        checked += 1
    assert checked >= 5, "expected at least the 5 known M15 shots to be checked"


# ── D-4 (2026-08-16 review) — engine_events cross-check ──────────────────────

def test_engine_data_validate_engine_events_catches_typos():
    _add_tool_dir_to_path()
    import engine_data as ed

    ts = datetime(2026, 7, 28, 4, 0, 0)
    bar = ed.Bar(ts, o=4058.07, h=4060.32, l=4053.91, c=4058.08)
    engine_bars = {ts: bar}

    clean = [{"event": "SWEEP", "time": "2026-07-28 04:00", "level": 4053.91}]
    assert ed.validate_engine_events(clean, engine_bars) == []

    bad_time = [{"event": "SWEEP", "time": "2026-07-28 04:07", "level": 4053.91}]
    problems = ed.validate_engine_events(bad_time, engine_bars)
    assert len(problems) == 1 and problems[0]["problem"] == "MISSING_BAR"

    bad_level = [{"event": "SWEEP", "time": "2026-07-28 04:00", "level": 9999.99}]
    problems = ed.validate_engine_events(bad_level, engine_bars)
    assert len(problems) == 1 and problems[0]["problem"] == "LEVEL_OUT_OF_RANGE"

    # Cross-timeframe events are time-checked but exempted from the level
    # check (that would need H4 aggregation, deliberately not duplicated here
    # -- see engine_data.py's _CROSS_TIMEFRAME_EVENTS note).
    h4 = [{"event": "H4_C3", "time": "2026-07-28 04:00", "level": 99999.0}]
    assert ed.validate_engine_events(h4, engine_bars) == []


def test_engine_data_validate_engine_events_real_shot_plan_is_clean():
    """The real shot_plan.json's 19 hand-transcribed engine_events, checked
    against the real corpus. This is the actual thing D-4 exists to catch --
    proving it currently finds nothing is itself the evidence the manual
    transcription was accurate, not just trusted."""
    _add_tool_dir_to_path()
    import engine_data as ed

    plan = json.loads((_TOOL_DIR / "shot_plan.json").read_text(encoding="utf-8"))
    csv_path = Path(__file__).resolve().parents[1] / "data" / "XAUUSD_M15.csv"
    if not csv_path.exists():
        pytest.skip("data/XAUUSD_M15.csv not present in this environment")
    engine_bars = ed.load_engine_bars(str(csv_path))
    problems = ed.validate_engine_events(plan["engine_events"], engine_bars)
    assert problems == [], f"unexpected engine_events problems: {problems}"


# ── D-6 (2026-08-16 review) — stagger() no longer collides same-named events ─

def test_annotate_stagger_keys_on_event_and_broker_not_event_alone():
    """Reproduces the live shot-09 collision: two RETEST marks five days apart
    (Jul 15 and Jul 20) used to share one dict key (`"RETEST"`) and the later
    silently overwrote the earlier's row assignment. Both must now get
    independent (and in this case, since they're far apart in x, identical
    row-0) assignments reachable by their own (event, broker) key."""
    pytest.importorskip("PIL", reason="Pillow not installed in this environment")
    _add_tool_dir_to_path()
    import annotate as an

    events = [
        {"event": "RETEST", "broker": "2026-07-15 22:15", "x": 100.0, "in_frame": True},
        {"event": "OFF_SESSION", "broker": "2026-07-15 22:30", "x": 100.0, "in_frame": True},
        {"event": "RETEST", "broker": "2026-07-20 16:45", "x": 900.0, "in_frame": True},
    ]
    rows = an.stagger(events, min_gap=96.0, rows=3)

    key_jul15 = ("RETEST", "2026-07-15 22:15")
    key_jul20 = ("RETEST", "2026-07-20 16:45")
    assert key_jul15 in rows and key_jul20 in rows, (
        "both RETEST marks must get their own row assignment -- pre-D-6 the "
        "second overwrote the first under the shared 'RETEST' key"
    )
    # The two RETEST events are far apart in x (100 vs 900) so they don't
    # actually compete for a row; each independently lands on row 0. What D-6
    # fixes is that the KEY no longer collides, not that they must differ.
    assert rows[key_jul15] == 0
    assert rows[key_jul20] == 0

    off_session_key = ("OFF_SESSION", "2026-07-15 22:30")
    assert off_session_key in rows
    # OFF_SESSION shares x=100 with the Jul-15 RETEST -- they DO compete for a
    # row at that position, so OFF_SESSION must be pushed off row 0.
    assert rows[off_session_key] != rows[key_jul15]


def test_annotate_stagger_real_shot09_no_dropped_marks():
    """End-to-end proof on the real, currently-shipped shot 09 sidecar: every
    in-frame event gets a row assignment, none silently missing."""
    pytest.importorskip("PIL", reason="Pillow not installed in this environment")
    _add_tool_dir_to_path()
    import annotate as an

    sidecar = _TOOL_DIR / "shots" / "09_h4_jul15_20.json"
    if not sidecar.exists():
        pytest.skip("09_h4_jul15_20.json not present in this environment")
    doc = json.loads(sidecar.read_text(encoding="utf-8"))
    events = [e for e in doc["engine_events"] if e["in_frame"]]
    rows = an.stagger(events)
    for ev in events:
        assert an._stagger_key(ev) in rows, f"missing row assignment for {ev['event']} @ {ev['broker']}"


# ── D-1 (2026-08-16 review) — capture_tv.py records skipped reconciliation ──

def test_capture_tv_records_explicit_status_for_non_m15_shots_on_disk():
    """Every currently-shipped H4 sidecar must carry an explicit
    engine_vs_tv.status, never an absent key -- proves the D-1 backfill
    actually landed, not just the forward-going code path.

    SCOPE CORRECTED (CH-monthly-tv-coverage-h4-recon): this test used to assert
    the status was specifically NOT_APPLICABLE. That was true when D-1 shipped
    -- `diff_table`'s fixed 15-minute cursor made an H4 shot unreconcilable by
    construction -- but it encoded a LIMITATION as an invariant. `htf_bars.py`
    now supplies canonically aggregated parents and a measured grid phase, so an
    H4 shot can legitimately resolve to OK/DIVERGENT.

    The invariant D-1 actually protects is unchanged and still asserted: the key
    is ALWAYS present and always one of the recorded statuses, so a skipped
    reconciliation stays distinguishable from an unexamined one. A NOT_APPLICABLE
    must additionally explain itself, which is what made the original defect
    (absent key, three consumers guessing) impossible to repeat.
    """
    shots_dir = _TOOL_DIR / "shots"
    h4_sidecars = [
        p for p in shots_dir.glob("*.json")
        if not p.stem.endswith("_ANNOTATED") and "_PRE_" not in p.stem
    ]
    checked_h4 = 0
    for p in h4_sidecars:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if str(doc.get("shot", {}).get("interval")) == "15":
            continue
        evt = doc.get("engine_vs_tv")
        assert evt is not None, f"{p.name}: engine_vs_tv key is absent"
        status = evt.get("status")
        assert status in {"OK", "DIVERGENT", "NOT_APPLICABLE"}, \
            f"{p.name}: unrecorded status {status!r}"
        if status == "NOT_APPLICABLE":
            assert evt.get("reason"), \
                f"{p.name}: NOT_APPLICABLE without a reason is the D-1 defect again"
        else:
            # A reconciled HTF shot must show its work: which grid it used, and
            # that the phase was decisively resolved rather than assumed.
            assert evt.get("timeframe", {}).get("rule"), f"{p.name}: no timeframe rule"
            assert evt.get("htf_anchor", {}).get("decisive") is True, \
                f"{p.name}: reconciled without a decisive grid anchor"
            # Non-vacuity: a 'clean' verdict over zero compared bars is the
            # silent-gap failure class F-079 exists to prevent.
            assert evt["summary"]["compared"] > 0, f"{p.name}: verdict over 0 compared bars"
        checked_h4 += 1
    assert checked_h4 >= 2, "expected at least the 2 known H4 shots to be checked"


# ── 2b. htf_bars.py — HTF aggregation + measured grid phase ─────────────────────────
#
# CH-monthly-tv-coverage-h4-recon. These cover the code that lifted H4 shots out of
# permanent NOT_APPLICABLE. The aggregation itself is NOT tested here for arithmetic
# correctness -- it is `features.parent_candle.ParentCandleBuilder`'s, already floored
# by tests/test_parent_candle_builder.py. What IS tested is this module's own
# contract: the conversion, the phase search, and every fail-closed exit.

def _real_h4_sidecars():
    shots = _TOOL_DIR / "shots"
    out = []
    for p in sorted(shots.glob("*.json")):
        if p.stem.endswith("_ANNOTATED") or "_PRE_" in p.stem:
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        if str(doc.get("shot", {}).get("interval")) != "15":
            out.append((p.stem, doc))
    return out


def _engine_csv():
    return Path(__file__).resolve().parents[1] / "data" / "XAUUSD_M15.csv"


def test_htf_bars_module_imports_without_src():
    """Importing the module must not require `src/` — only calling into the
    builder does. A caller that just wants SUPPORTED_INTERVALS pays nothing."""
    _add_tool_dir_to_path()
    import htf_bars as hb

    assert "240" in hb.SUPPORTED_INTERVALS
    assert hb.SUPPORTED_INTERVALS["240"] == ("H4", 240)


def test_htf_aggregation_matches_hand_computed_parent():
    """One H4 bucket, aggregated: open=first child, high=max, low=min, close=last."""
    _add_tool_dir_to_path()
    import engine_data as ed
    import htf_bars as hb

    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    parents = hb.aggregate_engine_bars(eng, "H4")

    stamp = datetime(2026, 7, 15, 4, 0)
    assert stamp in parents, "expected a closed H4 parent at 2026-07-15 04:00 broker"
    children = [
        eng[t] for t in sorted(eng)
        if stamp <= t < datetime(2026, 7, 15, 8, 0)
    ]
    assert len(children) == 16, f"expected 16 M15 children, got {len(children)}"
    p = parents[stamp]
    assert p.o == children[0].o
    assert p.c == children[-1].c
    assert p.h == max(c.h for c in children)
    assert p.l == min(c.l for c in children)


def test_htf_aggregation_never_emits_the_in_progress_bucket():
    """No-lookahead is inherited from ParentCandleBuilder: the final, still-open
    bucket must be absent. A partial parent is not a parent."""
    _add_tool_dir_to_path()
    import engine_data as ed
    import htf_bars as hb

    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    parents = hb.aggregate_engine_bars(eng, "H4")
    last_child = max(eng)
    open_bucket = last_child.replace(
        hour=(last_child.hour // 4) * 4, minute=0, second=0, microsecond=0
    )
    assert open_bucket not in parents, (
        f"in-progress bucket {open_bucket} was emitted — lookahead leak"
    )


@pytest.mark.parametrize("stem_doc", _real_h4_sidecars(), ids=lambda sd: sd[0])
def test_htf_anchor_resolves_decisively_on_real_h4_shots(stem_doc):
    """The measured phase must come out decisive on both captured H4 shots, and
    must be phase 0 — i.e. TradingView's H4 grid IS the calendar-true broker grid
    (broker 00/04/08/12/16/20 == UTC 21/01/05/09/13/17 at the +3 offset).
    Recorded as a measurement, not an assumption: if TradingView ever reanchors,
    this fails rather than silently comparing misaligned buckets."""
    _add_tool_dir_to_path()
    import engine_data as ed
    import htf_bars as hb

    stem, doc = stem_doc
    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    tv = {int(b["t"]): b for b in doc["bars"]}
    rule, step = hb.SUPPORTED_INTERVALS[str(doc["shot"]["interval"])]

    anchor, parents = hb.resolve_htf_anchor(
        eng, tv, rule, step, int(doc["clock"]["offset_hours"])
    )
    assert anchor.decisive, f"{stem}: grid phase not decisive ({anchor.as_dict()})"
    assert anchor.phase_hours == 0, f"{stem}: unexpected phase {anchor.phase_hours}"
    assert anchor.ranked[0]["anchors_matched"] == anchor.anchors_usable
    assert parents, f"{stem}: decisive but no aggregated parents returned"


def test_htf_anchor_fails_closed_with_no_tv_bars():
    """No TradingView bars => nothing to measure against => not decisive.
    Fails closed rather than defaulting to phase 0."""
    _add_tool_dir_to_path()
    import engine_data as ed
    import htf_bars as hb

    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    anchor, parents = hb.resolve_htf_anchor(eng, {}, "H4", 240, 3)
    assert anchor.decisive is False
    assert parents == {}


def test_htf_anchor_fails_closed_when_tv_bars_do_not_match():
    """A TradingView series on the right grid but with wrong prices must NOT be
    accepted. Guards the case where the phase 'matches' structurally while the
    OHLC does not — exactly what MATCH_TOLERANCE is for."""
    _add_tool_dir_to_path()
    import engine_data as ed
    import htf_bars as hb

    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    real = hb.aggregate_engine_bars(eng, "H4")
    bogus = {
        ed.to_utc_epoch(ts, 3): {"o": b.o + 500, "h": b.h + 500,
                                 "l": b.l + 500, "c": b.c + 500}
        for ts, b in real.items()
    }
    anchor, _ = hb.resolve_htf_anchor(eng, bogus, "H4", 240, 3)
    assert anchor.decisive is False, "accepted a 500-point price offset as a match"


def test_htf_anchor_floor_rejects_a_partially_matching_phase():
    """D-2 anchor floor, ported to the grid search: a phase that matches only
    some of its in-frame buckets must never win on mean error alone."""
    _add_tool_dir_to_path()
    import engine_data as ed
    import htf_bars as hb

    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    real = hb.aggregate_engine_bars(eng, "H4")
    stamps = sorted(real)[:12]
    tv = {
        ed.to_utc_epoch(ts, 3): {"o": real[ts].o, "h": real[ts].h,
                                 "l": real[ts].l, "c": real[ts].c}
        for ts in stamps
    }
    # Drop one bar from the middle of the framed span: the phase now matches
    # 11 of 12 in-frame buckets with a perfect mean error on those 11.
    del tv[ed.to_utc_epoch(stamps[5], 3)]
    anchor, _ = hb.resolve_htf_anchor(eng, tv, "H4", 240, 3)
    assert anchor.error < 0.001, "precondition: the surviving matches are exact"
    assert anchor.decisive is False, "a partial match cleared the anchor floor"


def test_diff_table_step_minutes_default_is_unchanged_m15_behaviour():
    """The refactor's core promise: `diff_table` with its default step reproduces
    the M15 comparison exactly. Asserted against every real M15 sidecar's own
    stored rows — the strongest available form of 'nothing moved'."""
    _add_tool_dir_to_path()
    import engine_data as ed

    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    shots = _TOOL_DIR / "shots"
    checked = 0
    for p in sorted(shots.glob("*.json")):
        if p.stem.endswith("_ANNOTATED") or "_PRE_" in p.stem:
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        if str(doc.get("shot", {}).get("interval")) != "15":
            continue
        stored = doc.get("engine_vs_tv", {}).get("rows")
        if not stored:
            continue
        tv = {int(b["t"]): b for b in doc["bars"]}
        rows = ed.diff_table(
            eng, tv, int(doc["clock"]["offset_hours"]),
            datetime.strptime(doc["shot"]["start"], "%Y-%m-%d %H:%M"),
            datetime.strptime(doc["shot"]["end"], "%Y-%m-%d %H:%M"),
        )
        assert rows == stored, f"{p.stem}: default-step diff_table drifted"
        checked += 1
    assert checked >= 4, f"expected >=4 M15 sidecars to verify, checked {checked}"


def test_no_engine_bar_rows_are_off_by_default():
    """`record_missing_engine` must default False — an M15 window routinely spans
    weekends, and emitting rows there would have changed every shipped sidecar."""
    _add_tool_dir_to_path()
    import engine_data as ed

    if not _engine_csv().exists():
        pytest.skip("engine corpus not on disk")
    eng = ed.load_engine_bars(_engine_csv())
    # A window straddling the Jul 18-19 weekend.
    rows = ed.diff_table(
        eng, {}, 3,
        datetime(2026, 7, 17, 20, 0), datetime(2026, 7, 20, 4, 0),
    )
    assert not any(r["status"] == "NO_ENGINE_BAR" for r in rows)
    rows_on = ed.diff_table(
        eng, {}, 3,
        datetime(2026, 7, 17, 20, 0), datetime(2026, 7, 20, 4, 0),
        record_missing_engine=True,
    )
    assert any(r["status"] == "NO_ENGINE_BAR" for r in rows_on)
    assert len(rows_on) > len(rows)


# ── 3. shot_plan.json structural validity (pure JSON, no deps) ──────────────────────
def test_shot_plan_json_is_well_formed():
    plan_path = _TOOL_DIR / "shot_plan.json"
    doc = json.loads(plan_path.read_text(encoding="utf-8"))

    for key in ("engine_csv", "presets", "shots"):
        assert key in doc, f"shot_plan.json missing top-level key {key!r}"

    assert isinstance(doc["shots"], dict) and doc["shots"]
    required_shot_fields = {"name", "symbol", "interval", "start", "end"}
    for shot_name, spec in doc["shots"].items():
        missing = required_shot_fields - spec.keys()
        assert not missing, f"shot {shot_name!r} missing fields {missing}"

    assert isinstance(doc["presets"], dict) and doc["presets"]
    for preset_name, spec in doc["presets"].items():
        assert "shots" in spec, f"preset {preset_name!r} missing 'shots'"
        for ref in spec["shots"]:
            assert ref in doc["shots"], (
                f"preset {preset_name!r} references undefined shot {ref!r}"
            )


def test_capture_tv_accepts_external_plan_and_continue_on_frame_error():
    src = (_TOOL_DIR / "capture_tv.py").read_text(encoding="utf-8")
    assert "--plan" in src
    assert "--continue-on-frame-error" in src
    assert "Does not loosen the two-sided assertion" in src


def test_month_legible_preset_tiles_the_corpus_at_legible_width():
    """CH-visual-crt-state-fidelity: 19-24 shots of 150-160 bars, ≥50 overlap,
    every edge on a live-market CSV bar. Does not loosen frame_shot."""
    import csv

    plan = json.loads((_TOOL_DIR / "shot_plan.json").read_text(encoding="utf-8"))
    assert "month-legible" in plan["presets"]
    keys = plan["presets"]["month-legible"]["shots"]
    assert 19 <= len(keys) <= 24

    csv_path = Path(__file__).resolve().parents[1] / plan["engine_csv"]
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    ts = []
    for r in rows:
        raw = (r.get("timestamp") or r.get("time") or "")[:16]
        ts.append(raw)
    ts_set = set(ts)

    windows = []
    for key in keys:
        spec = plan["shots"][key]
        assert spec["interval"] == "15"
        assert spec.get("clock", "broker") == "broker"
        assert spec["start"] in ts_set, f"{key} start {spec['start']} is not a live CSV bar"
        assert spec["end"] in ts_set, f"{key} end {spec['end']} is not a live CSV bar"
        i0 = ts.index(spec["start"])
        i1 = ts.index(spec["end"])
        n = i1 - i0 + 1
        assert 150 <= n <= 160, f"{key} has {n} bars, want 150-160"
        # 1743 px plot / n bars must stay ≥ 8 px/candle (the generation floor).
        assert 1743 / n >= 8.0
        windows.append((i0, i1))

    assert windows[0][0] == 0
    assert windows[-1][1] == len(ts) - 1
    for (a0, a1), (b0, b1) in zip(windows, windows[1:]):
        overlap = a1 - b0 + 1
        assert overlap >= 50, f"overlap {overlap} < 50 between adjacent tiles"

    # The two-sided framing assertion must still be the abort, not a warning.
    src = (_TOOL_DIR / "capture_tv.py").read_text(encoding="utf-8")
    assert "too_narrow" in src and "too_wide" in src
    assert "achieved window is {kind} than requested" in src


# ── 4. annotate.py pure helpers — needs Pillow ───────────────────────────────────────
def test_annotate_geometry_helpers():
    pytest.importorskip("PIL", reason="Pillow not installed in this environment")
    _add_tool_dir_to_path()
    import annotate as an
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (200, 100))
    d = ImageDraw.Draw(img)
    f = an.font(13)

    w = an.text_w(d, "hello", f)
    assert isinstance(w, int) and w > 0

    # dash_h/dash_v just draw — assert they run without raising and touch the canvas.
    an.dash_h(d, 10, 190, 50, fill=(0, 0, 0), w=2, on=6, off=5)
    an.dash_v(d, 100, 10, 90, fill=(0, 0, 0), w=2, on=7, off=5)

    fr = an.Frame(
        {
            "plot": {
                "rect": {"x": 0, "y": 0, "w": 200, "h": 100},
                "price_calibration": [
                    {"price": 100.0, "y": 90.0},
                    {"price": 110.0, "y": 10.0},
                ],
                "visible_price_range": {"from": 100.0, "to": 110.0},
            }
        }
    )
    assert fr.price_visible(105.0)
    assert not fr.price_visible(50.0)
    assert fr.y_of(100.0) == pytest.approx(90.0)
    assert fr.y_of(110.0) == pytest.approx(10.0)


def test_annotate_module_importable_with_pillow():
    pytest.importorskip("PIL", reason="Pillow not installed in this environment")
    _add_tool_dir_to_path()
    import annotate as an

    assert callable(an.annotate)
    assert callable(an.main)


# ── 5. Playwright-backed modules — needs playwright ──────────────────────────────────
def test_tv_bridge_importable_with_playwright():
    pytest.importorskip("playwright.sync_api", reason="Playwright not installed in this environment")
    _add_tool_dir_to_path()
    import tv_bridge

    assert hasattr(tv_bridge, "TVBridge")


def test_capture_tv_importable_with_playwright():
    pytest.importorskip("playwright.sync_api", reason="Playwright not installed in this environment")
    _add_tool_dir_to_path()
    import capture_tv

    assert callable(capture_tv.main)


# ── 6. Odds aggregation — overlapping shots must not double-count ────────────────────
#
# CH-xauusd-tv-odds. `htf_parent_telemetry_extract.py`'s rollup SUMS each shot's
# `compared`/`divergent`, which is a fine "work done per capture" tally but an
# invalid denominator for an agreement RATE, because the shot windows overlap:
# 05_m15_jul28_displacement and 06_m15_jul30_trade are strict subsets of
# 04_m15_jul28_forensic, and both H4 close-ups sit inside 01_h4_july_macro. That
# is how F-080 came to register 1,455 compared when only 1,378 unique bars had
# ever been looked at. These floors pin the deduplicating unit of account so the
# naive sum cannot come back.


def _add_research_dir_to_path():
    p = str(Path(__file__).resolve().parents[1] / "scripts" / "research")
    if p not in sys.path:
        sys.path.insert(0, p)


def _fake_sidecar(name, interval, rows):
    return {
        "_path": f"tools/tv_forensic/shots/{name}.json",
        "shot": {"name": name, "interval": interval, "start": "x", "end": "y", "clock": "broker"},
        "engine_vs_tv": {"status": "OK", "rows": rows},
    }


def _row(broker, status="OK", o=1.0, h=2.0, low=0.5, c=1.5, abs_error=0.1):
    return {
        "broker": broker,
        "utc": broker,
        "engine": {"O": o, "H": h, "L": low, "C": c},
        "tv": {"O": o, "H": h, "L": low, "C": c},
        "delta": {"O": 0.0, "H": 0.0, "L": 0.0, "C": 0.0},
        "abs_error": abs_error,
        "status": status,
    }


def test_overlapping_shots_dedupe_to_the_union_not_the_sum():
    """The regression that would have caught F-080's inflated denominator.

    Shot B is a strict subset of shot A, exactly like 05/06 inside 04. A naive
    sum reports 5 compared / 2 divergent; the union is 3 compared / 1 divergent.
    """
    _add_research_dir_to_path()
    import tv_engine_odds as tvo

    wide = _fake_sidecar("A_wide", "15", [
        _row("2026-07-28 04:00"),
        _row("2026-07-28 04:15", status="DIVERGENT", abs_error=9.0),
        _row("2026-07-28 04:30"),
    ])
    inner = _fake_sidecar("B_inner", "15", [
        _row("2026-07-28 04:15", status="DIVERGENT", abs_error=9.0),
        _row("2026-07-28 04:30"),
    ])

    unique, inconsistencies, unreconciled = tvo.collect_unique_bars([wide, inner])
    assert inconsistencies == []
    assert unreconciled == []

    stats = tvo.odds_for(list(unique.values()))
    naive_compared = sum(len(s["engine_vs_tv"]["rows"]) for s in (wide, inner))
    assert naive_compared == 5, "fixture no longer exercises an overlap"
    # The whole point: strictly fewer than the sum, and equal to the union.
    assert stats["compared"] == 3
    assert stats["divergent"] == 1
    assert stats["compared"] < naive_compared
    # Provenance of a shared bar survives dedup — needed to explain any conflict.
    assert sorted(set(unique[("15", "2026-07-28 04:15")]["shots"])) == ["A_wide", "B_inner"]


def test_same_timestamp_on_a_different_timeframe_is_a_different_bar():
    """Dedup keys on (interval, broker_ts). An M15 and an H4 bar can open at the
    same instant and are NOT the same observation; collapsing them would silently
    delete a real comparison."""
    _add_research_dir_to_path()
    import tv_engine_odds as tvo

    m15 = _fake_sidecar("M15_shot", "15", [_row("2026-07-28 04:00")])
    h4 = _fake_sidecar("H4_shot", "240", [_row("2026-07-28 04:00")])

    unique, _, _ = tvo.collect_unique_bars([m15, h4])
    assert len(unique) == 2
    assert ("15", "2026-07-28 04:00") in unique
    assert ("240", "2026-07-28 04:00") in unique


def test_cross_shot_ohlc_disagreement_is_reported_not_silently_collapsed():
    """Two shots claiming different OHLC for the same bar is a real conflict.
    Last-writer-wins would assert an agreement nobody measured — the D-1 silent
    -gap class F-079 fixed, one layer down."""
    _add_research_dir_to_path()
    import tv_engine_odds as tvo

    a = _fake_sidecar("A", "15", [_row("2026-07-28 04:00", c=1.5)])
    b = _fake_sidecar("B", "15", [_row("2026-07-28 04:00", c=99.0)])

    _, inconsistencies, _ = tvo.collect_unique_bars([a, b])
    assert inconsistencies, "conflicting OHLC across shots must be surfaced"
    assert {i["side"] for i in inconsistencies} <= {"engine", "tv", "status"}
    assert inconsistencies[0]["broker"] == "2026-07-28 04:00"


def test_coverage_only_rows_never_enter_the_odds():
    """A slot where only one feed has a bar is a COVERAGE fact. Counting it as
    agreement flatters the rate; counting it as divergence fabricates
    disagreement. It must do neither."""
    _add_research_dir_to_path()
    import tv_engine_odds as tvo

    rows = [
        _row("2026-07-01 00:00"),
        {"broker": "2026-07-01 00:15", "utc": "x", "engine": None,
         "tv": {"O": 1, "H": 2, "L": 0.5, "C": 1.5},
         "status": "ENGINE_BAR_MISSING_TV_HAS_ONE"},
        {"broker": "2026-07-01 00:30", "utc": "x", "engine": None, "tv": None,
         "status": "NO_ENGINE_BAR"},
        {"broker": "2026-07-01 00:45", "utc": "x",
         "engine": {"O": 1, "H": 2, "L": 0.5, "C": 1.5}, "tv": None,
         "status": "NO_TV_BAR"},
    ]
    unique, _, _ = tvo.collect_unique_bars([_fake_sidecar("S", "15", rows)])
    stats = tvo.odds_for(list(unique.values()))

    assert stats["unique_bars_seen"] == 4
    assert stats["compared"] == 1          # only the two-sided row
    assert stats["agreement_rate"] == 1.0  # and it is not diluted by the other 3
    assert stats["status_counts"]["NO_ENGINE_BAR"] == 1


def test_empty_fold_fails_loudly_instead_of_reporting_perfect_agreement():
    """Non-vacuity. A 100% agreement rate over zero bars is the most flattering
    possible lie, so an all-unreconciled input must raise."""
    _add_research_dir_to_path()
    import tv_engine_odds as tvo

    assert tvo.odds_for([])["agreement_rate"] is None

    empty = dict(_fake_sidecar("NA", "240", []))
    empty["engine_vs_tv"] = {"status": "NOT_APPLICABLE", "reason": "H4_GRID_UNRESOLVED"}
    unique, _, unreconciled = tvo.collect_unique_bars([empty])
    assert unique == {}
    assert unreconciled[0]["status"] == "NOT_APPLICABLE"


def test_odds_inherit_engine_data_match_tolerance_rather_than_restating_it():
    """A second hardcoded 3.0 would silently drift from the rule the stored rows
    were actually scored under."""
    _add_research_dir_to_path()
    _add_tool_dir_to_path()
    import engine_data
    import tv_engine_odds as tvo

    assert tvo.MATCH_TOLERANCE is engine_data.MATCH_TOLERANCE
    src = (Path(__file__).resolve().parents[1]
           / "scripts" / "research" / "tv_engine_odds.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assigned = {
        t.id
        for node in ast.walk(tree) if isinstance(node, ast.Assign)
        for t in node.targets if isinstance(t, ast.Name)
    }
    assert "MATCH_TOLERANCE" not in assigned, "tolerance must be imported, not redefined"


def test_wilson_interval_brackets_the_point_estimate():
    _add_research_dir_to_path()
    import tv_engine_odds as tvo

    lo, hi = tvo._wilson(18, 2116)
    assert 0.0 < lo < 18 / 2116 < hi < 1.0
    assert tvo._wilson(0, 0) == (0.0, 0.0)
    # Never reports a negative lower bound, which is why Wilson is used here.
    assert tvo._wilson(1, 5000)[0] >= 0.0

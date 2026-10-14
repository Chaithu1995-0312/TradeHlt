"""Program 12 Slice 2 ladder units. No BacktestRunner. No corpus admission."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from config_layer.crt_engine_v2 import Candle
from research.timeframe_ladder import config_clone
from research.timeframe_ladder.clusters import assign_clusters, n_clusters
from research.timeframe_ladder.config_clone import (
    build_clone,
    format_diff_markdown,
    knob_specs,
    load_crt_config,
    load_source,
)
from research.timeframe_ladder.controls import (
    passive_drift_r,
    percentile_rank,
    random_entry_means,
    random_seeds,
    verdict,
)
from research.timeframe_ladder.run import (
    EXPECTED_PARENT_SHA256,
    ParentWindowError,
    assert_declared_parent,
    assemble_report,
    funnel_counts,
    render_funnel_markdown,
    walk_journal,
)
from research.timeframe_ladder.stop_floor import FLOOR_ATR_MULT, apply_stop_floor

_PKG = Path(config_clone.__file__).resolve().parent
_FORBIDDEN_CALLS = {"declare_in_process", "admit_csv_path", "CandleLoader"}


def _c(ts, o, h, l, cl, idx) -> Candle:
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=1.0, index=idx)


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.add(func.id)
        elif isinstance(func, ast.Attribute):
            found.add(func.attr)
    return found


def test_package_does_not_call_admission_or_declare():
    offenders = []
    for path in sorted(_PKG.glob("*.py")):
        hit = _calls(path) & _FORBIDDEN_CALLS
        if hit:
            offenders.append(f"{path.name}: {sorted(hit)}")
    assert not offenders, offenders


def test_init_does_not_import_run():
    text = (_PKG / "__init__.py").read_text(encoding="utf-8")
    assert "import run" not in text
    assert "execute_timeframe" not in text


def test_clone_keeps_params_hash_and_sets_section_five_knobs():
    source = load_source()
    for timeframe, ttl, parent_tf, sessions in (
        ("H1", 240, "H4", ["london", "new_york", "overlap"]),
        ("H4", 60, "D1", ["london", "new_york", "overlap", "asia", "off_session"]),
    ):
        clone = build_clone(timeframe)
        assert clone["params"] == source["params"]
        assert clone["config_hash"] == source["config_hash"]
        assert clone["version"] == source["version"]
        assert clone["setup"]["entry_semantics"] == "resting_order"
        assert clone["setup"]["trade_ttl_candles"] == ttl
        assert clone["crt_engine"]["max_expansion_age_hours"] == 0
        assert clone["backtest"]["engine_gate_enabled"] is False
        assert clone["backtest"]["htf_clock_basis"] == "calendar"
        assert clone["backtest"]["timeframe"] == timeframe
        assert clone["parent_crt"]["enabled"] is True
        assert clone["parent_crt"]["timeframe"] == parent_tf
        assert clone["engine_runner"]["allowed_sessions"] == sessions
    rendered = format_diff_markdown()
    assert "1.5" in rendered
    assert "configs/production" in rendered
    assert "ladder_h1.json" in rendered
    names = {".".join(path) for path, _value in knob_specs("H1")}
    assert "setup.entry_semantics" in names
    assert "params" not in names


def test_load_crt_config_verifies_hash(tmp_path):
    h1 = load_crt_config(build_clone("H1"), tmp_path / "h1")
    h4 = load_crt_config(build_clone("H4"), tmp_path / "h4")
    assert h1.max_expansion_age_hours == 0
    assert h4.max_expansion_age_hours == 0
    assert tuple(h1.allowed_sessions) == ("LONDON", "NEWYORK", "OVERLAP")
    assert tuple(h4.allowed_sessions) == ("LONDON", "NEWYORK", "OVERLAP", "ASIA", "OFF_SESSION")


def test_bind_restores_parent_feed_alias():
    import config_layer.production_config as pc
    import runtime.parent_crt_feed as feed

    orig_section = pc.get_prod_section
    orig_full = pc.get_full_config_dict
    orig_feed = feed.get_prod_section
    clone = build_clone("H4")
    from research.timeframe_ladder.config_clone import bind_research_config

    with bind_research_config(clone):
        assert pc.get_prod_section is not orig_section
        assert feed.get_prod_section is not orig_feed
        assert feed.get_prod_section("backtest")["timeframe"] == "H4"
        assert feed.get_prod_section("parent_crt")["timeframe"] == "D1"
        assert pc.get_full_config_dict()["setup"]["trade_ttl_candles"] == 60
    assert pc.get_prod_section is orig_section
    assert pc.get_full_config_dict is orig_full
    assert feed.get_prod_section is orig_feed


def test_stop_floor_widens_only_inside_the_band_and_keeps_multipliers():
    wide = apply_stop_floor(100.0, 97.0, 103.6, 106.0, atr=2.0, direction="LONG")
    assert wide["floored"] is False
    assert wide["sl"] == 97.0
    assert wide["tp1_mult"] == pytest.approx(1.2)
    tight = apply_stop_floor(100.0, 99.0, 101.2, 102.4, atr=2.0, direction="LONG")
    assert FLOOR_ATR_MULT == 1.5
    assert tight["floored"] is True
    assert tight["risk"] == pytest.approx(3.0)
    assert tight["sl"] == pytest.approx(97.0)
    assert tight["tp1"] == pytest.approx(100.0 + 1.2 * 3.0)
    assert tight["tp2"] == pytest.approx(100.0 + 2.4 * 3.0)
    short = apply_stop_floor(100.0, 101.0, 98.8, 97.6, atr=2.0, direction="SHORT")
    assert short["sl"] == pytest.approx(103.0)
    assert short["tp1"] == pytest.approx(100.0 - 1.2 * 3.0)


def test_clusters_share_sweep_and_overlap():
    rows = [
        {"entry_idx": 0, "exit_idx": 2, "sweep_idx": 1},
        {"entry_idx": 10, "exit_idx": 12, "sweep_idx": 1},
        {"entry_idx": 2, "exit_idx": 4, "sweep_idx": 9},
        {"entry_idx": 20, "exit_idx": 21, "sweep_idx": 19},
    ]
    ids = assign_clusters(rows)
    assert ids[0] == ids[1] == ids[2]
    assert ids[3] != ids[0]
    assert n_clusters([]) == 0
    assert n_clusters(rows) == 2


def test_verdict_floor_ignores_a_positive_interval():
    label = verdict(
        n_clusters=3,
        ci_low_vs_drift=1.0,
        random_percentile=99.0,
        long_ci_low=1.0,
        short_ci_low=1.0,
    )
    assert label == {
        "verdict": "INSUFFICIENT",
        "failing_condition": "n_clusters < 30",
        "expectancy_published": False,
    }
    assert verdict(n_clusters=None)["verdict"] == "INSUFFICIENT"


def test_verdict_names_a_one_sided_drift_split():
    label = verdict(
        n_clusters=40,
        ci_low_vs_drift=0.1,
        random_percentile=96.0,
        long_ci_low=0.2,
        short_ci_low=-0.1,
    )
    assert label["verdict"] == "STOP"
    assert "directional_gold_beta" in label["failing_condition"]
    assert "short_vs_drift" in label["failing_condition"]
    both = verdict(
        n_clusters=40,
        ci_low_vs_drift=0.1,
        random_percentile=96.0,
        long_ci_low=-0.1,
        short_ci_low=-0.1,
    )
    assert "directional_gold_beta" not in (both["failing_condition"] or "")


def test_passive_and_random_entry_are_not_a_second_runner():
    assert passive_drift_r(100.0, 103.0, 2.0, "long") == pytest.approx(1.5)
    assert passive_drift_r(100.0, 103.0, 2.0, "short") == pytest.approx(-1.5)
    closes = [float(i) for i in range(10)]
    means = random_entry_means(
        closes,
        [{"direction": "long", "holding": 1, "risk": 1.0}],
        [7, 8],
    )
    assert len(means) == 2
    assert all(m == pytest.approx(1.0) for m in means)
    assert percentile_rank(1.0, [0.0, 0.5, 1.0]) == pytest.approx(200 / 3)
    assert random_seeds()[0] == 20261005
    assert random_seeds()[-1] == 20261005 + 99
    assert len(random_seeds()) == 100


def _series(n=6):
    start = datetime(2026, 7, 7, 1, 0, 0)
    return [
        _c(start + timedelta(hours=i), 100 + i, 101 + i, 99 + i, 100.2 + i, i)
        for i in range(n)
    ]


def test_walk_uses_event_structural_prices_not_the_journal_stop():
    candles = _series()
    events = [
        {
            "event": "STATE_TRANSITION",
            "state_to": "SWEEP",
            "candle_index": 0,
            "metadata": {},
        },
        {
            "event": "TRADE_OPENED",
            "candle_index": 1,
            "metadata": {
                "id": "T1",
                "price": 101.2,
                "sl": 98.2,
                "tp1": 104.8,
                "tp2": 108.4,
                "direction": "LONG",
            },
        },
    ]
    journal = [{
        "trade_id": "T1",
        "direction": "LONG",
        "entry_raw": 101.5,
        "sl": 90.0,
        "tp1": 110.0,
        "tp2": 120.0,
        "opened_at": "2026-07-07T02:00:00",
        "live_atr": 2.0,
        "candle_idx": 99,
        "pnl_rr_net": 4.0,
    }]
    walked = walk_journal(candles, events, journal, ttl=2)
    assert walked["n_price_fallback"] == 0
    assert len(walked["rows"]) == 1
    row = walked["rows"][0]
    assert row["price_source"] == "event_metadata"
    assert row["entry_idx"] == 1
    assert row["sweep_idx"] == 0
    assert row["risk"] == pytest.approx(3.0)
    report = assemble_report(
        timeframe="H1",
        parent={
            "path": "data/XAUUSD_M15.csv",
            "n": 2116,
            "first": "2026-07-07 01:00:00",
            "last": "2026-08-06 23:45:00",
            "sha256": EXPECTED_PARENT_SHA256,
        },
        projected_n=6,
        funnel=funnel_counts(events, 1),
        walk=walked,
        candles=candles,
    )
    blob = json.dumps(report)
    assert report["verdict"] == "INSUFFICIENT"
    assert report["expectancy_published"] is False
    assert report["n_clusters"] == 1
    assert "net_r" not in blob
    assert "mean_r" not in blob
    assert "4.0" not in blob
    md = render_funnel_markdown({
        "parent": {
            "path": "data/XAUUSD_M15.csv",
            "n": 2116,
            "first": "2026-07-07 01:00:00",
            "last": "2026-08-06 23:45:00",
            "sha256": EXPECTED_PARENT_SHA256,
        },
        "timeframes": [report],
    })
    assert "INSUFFICIENT" in md
    assert "mean_r" not in md


def test_missing_atr_is_counted_and_not_walked():
    candles = _series()
    events = [{
        "event": "TRADE_OPENED",
        "candle_index": 1,
        "metadata": {"id": "T9", "price": 100.0, "sl": 97.0, "tp1": 103.0, "tp2": 106.0, "direction": "SHORT"},
    }]
    journal = [{"trade_id": "T9", "direction": "SHORT", "live_atr": "0", "entry_raw": "1", "sl": "2", "tp1": "3", "tp2": "4"}]
    walked = walk_journal(candles, events, journal, ttl=2)
    assert walked["rows"] == []
    assert walked["n_atr_unpublished"] == 1
    assert walked["n_journal"] == 1


def test_declared_parent_constant_and_refusal():
    assert EXPECTED_PARENT_SHA256 == (
        "478b075150935c950ccc749925709db783e337c55c886d6dda1e3ee8b9692c5b"
    )
    with pytest.raises(ParentWindowError):
        assert_declared_parent({
            "path": "data/XAUUSD_M15.csv",
            "n": 1,
            "first": "2026-07-07 01:00:00",
            "last": "2026-08-06 23:45:00",
            "sha256": EXPECTED_PARENT_SHA256,
        })

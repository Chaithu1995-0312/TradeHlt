"""Floor: parquet evidence layer is a query surface, not a training dataset."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from research.evidence.catalog import (  # noqa: E402
    LEGAL_JOINS,
    SURFACES,
    IllegalJoinError,
    assert_join,
)
from research.evidence.atlases import (  # noqa: E402
    asymmetry_atlas,
    leakage_atlas,
    state_value_surface,
)
from research.evidence.queries import (  # noqa: E402
    FORBIDDEN_PRIMARY_Y,
    answer_question,
    feature_effectiveness,
    join_ledger,
    opportunity_quality,
    route_question,
    rows_to_cols,
)
from research.evidence.records import AUTHORITY, EvidenceRecord  # noqa: E402

_PKG = _SRC / "research" / "evidence"
FORBIDDEN_RUNTIME_MODULES = (
    "config_layer.crt_engine_v2",
    "runtime.backtest_v2",
    "training",
    "xgboost",
    "sklearn",
)


def _runtime_imports(tree: ast.Module) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


@pytest.mark.parametrize(
    "rel",
    ["catalog.py", "queries.py", "driver.py", "records.py", "atlases.py", "__init__.py"],
)
def test_no_engine_or_trainer_import(rel: str):
    src = (_PKG / rel).read_text(encoding="utf-8")
    imported = _runtime_imports(ast.parse(src))
    hits = [
        m for m in FORBIDDEN_RUNTIME_MODULES
        if any(imp == m or imp.startswith(m + ".") for imp in imported)
    ]
    assert hits == [], f"{rel} imports forbidden producers: {hits}"


def test_illegal_join_refused():
    with pytest.raises(IllegalJoinError, match="94k"):
        assert_join("opportunities", "events")
    with pytest.raises(IllegalJoinError):
        assert_join("clean_labels", "telemetry")
    assert_join("opportunities", "clean_labels")
    assert_join("events", "telemetry")
    assert frozenset({"opportunities", "clean_labels"}) in LEGAL_JOINS


def test_surfaces_name_roles_and_grains():
    assert SURFACES["opportunities"].role == "decision_ledger"
    assert SURFACES["clean_labels"].role == "outcome_surface"
    assert SURFACES["events"].role == "state_machine_journal"
    assert SURFACES["telemetry"].role == "decision_flight_recorder"
    assert SURFACES["opportunities"].grain == SURFACES["clean_labels"].grain == "bar_x_direction"
    assert SURFACES["events"].grain == SURFACES["telemetry"].grain == "crt_spine_run"
    assert SURFACES["opportunities"].grain != SURFACES["events"].grain


def test_evidence_record_cannot_grant_production_authority():
    with pytest.raises(ValueError, match="authority"):
        EvidenceRecord(
            question="x", surface="clean_labels", n=10,
            effect_name="y", effect_size=0.0, confidence="LIKELY",
            candidate_finding="no", authority="PRODUCTION",
        )
    rec = EvidenceRecord(
        question="count", surface="clean_labels", n=100,
        effect_name="n", effect_size=100.0, confidence="CERTAIN",
        candidate_finding="file count",
    )
    assert rec.authority == AUTHORITY
    assert any("F-022" in c for c in rec.caveats)


def test_census_uses_y_tp1_not_stream_outcome():
    rows = []
    for i in range(40):
        rows.append({
            "decision_ts": f"t{i}",
            "instrument": "XAUUSD",
            "side": "long" if i % 2 == 0 else "short",
            "y_tp1": 1 if i < 20 else 0,
            "outcome": "SL_HIT",
            "diagnostics": {"stream_outcome": "SL_HIT"},
            "features": {"rsi_14": float(i), "atr": 0.01, "open": 2000.0},
        })
    cols = rows_to_cols(rows)
    recs = feature_effectiveness(cols)
    rsi = next(r for r in recs if r.extra.get("feature") == "rsi_14")
    # rsi increases with i; first 20 are wins so LOW rsi has higher y_tp1 → negative delta
    assert rsi.effect_size is not None
    assert rsi.effect_size < 0
    with pytest.raises(KeyError, match="y_tp1"):
        feature_effectiveness({"outcome": ["SL_HIT"] * 40, "features.rsi_14": list(range(40))})


def test_low_cardinality_feature_is_categorical_not_median():
    rows = []
    for i in range(60):
        bias = 1.0 if i < 30 else -1.0
        rows.append({
            "y_tp1": 1 if i < 30 else 0,
            "features": {"trend_bias": bias, "rsi_14": float(i)},
        })
    recs = feature_effectiveness(rows_to_cols(rows))
    tb = next(r for r in recs if r.extra.get("feature") == "trend_bias")
    assert tb.extra["split"] == "categorical"
    assert tb.effect_name == "y_tp1_spread_across_levels"
    assert tb.extra["levels"]["1.0"]["y_tp1"] == 1.0
    assert tb.extra["levels"]["-1.0"]["y_tp1"] == 0.0


def test_quality_separates_mfe_from_tp():
    rows = []
    for i in range(40):
        rows.append({
            "y_tp1": 0 if i < 30 else 1,
            "y_mfe_r": 2.0 if i < 25 else 0.1,
            "y_reached_1r_horizon": 1 if i < 25 else 0,
            "y_mae_r_heat": 1.0,
            "y_R_net": -0.5,
        })
    rec = opportunity_quality(rows_to_cols(rows))[0]
    assert rec.extra["high_mfe_low_tp"] == 25
    assert rec.extra["losses_with_mfe_ge_1R"] == 25
    assert rec.authority == AUTHORITY


def test_join_is_identity_not_cartesian():
    opp = [
        {"timestamp": "t0", "instrument": "XAUUSD", "direction": "long", "entry": 1},
        {"timestamp": "t0", "instrument": "XAUUSD", "direction": "short", "entry": 2},
    ]
    lab = [
        {"decision_ts": "t0", "instrument": "XAUUSD", "side": "long", "y_tp1": 1},
        {"decision_ts": "t0", "instrument": "XAUUSD", "side": "short", "y_tp1": 0},
    ]
    joined = join_ledger(opp, lab)
    assert len(joined) == 2
    by_side = {r["side"]: r["y_tp1"] for r in joined}
    assert by_side == {"long": 1, "short": 0}


def test_question_routes_to_quality_not_all():
    assert route_question("Find losses with large MFE") == "quality"
    assert route_question("rejection causes and candidate death") == "lifecycle"
    recs = answer_question(
        "high-MFE low-TP conditions",
        lab=rows_to_cols([{
            "y_tp1": 0, "y_mfe_r": 1.5, "y_reached_1r_horizon": 1,
            "y_mae_r_heat": 0.2, "y_R_net": -1.0,
        }] * 40),
    )
    assert recs[0].extra["route"] == "quality"
    assert any("Quality" in r.candidate_finding or "quality" in r.question for r in recs)


def test_leakage_ladder_is_exclusive_and_complete():
    rows = []
    # 10 captured; 10 reached 2 missed; 10 reached 1 not 2; 10 reached 0.5 only; 10 no half-R
    specs = (
        [(1, 1, 1, 1)] * 10
        + [(0, 1, 1, 1)] * 10
        + [(0, 1, 1, 0)] * 10
        + [(0, 1, 0, 0)] * 10
        + [(0, 0, 0, 0)] * 10
    )
    for y, r05, r1, r2 in specs:
        rows.append({
            "y_tp1": y, "y_reached_0_5r": r05, "y_reached_1r_horizon": r1,
            "y_reached_2r_horizon": r2, "y_mfe_r": 2.0 if r1 else 0.2,
            "y_mae_r_heat": 1.2 if r2 else 0.2,
        })
    recs = leakage_atlas(rows_to_cols(rows))
    ladder = next(r for r in recs if r.effect_name == "leak_reached_1_not_2_rate")
    assert ladder.extra["ladder"] == {
        "tp_captured": 10,
        "leak_reached_2_missed_tp": 10,
        "leak_reached_1_not_2": 10,
        "leak_reached_0_5_not_1": 10,
        "missed_tp_no_half_r": 10,
    }
    assert sum(ladder.extra["ladder"].values()) == 50


def test_state_value_is_not_win_rate():
    rows = []
    for i in range(80):
        rows.append({
            "y_tp1": 1 if i < 10 else 0,
            "y_tp2": 0,
            "y_mfe_r": 3.0 if i < 40 else 0.5,
            "y_mae_r_heat": 0.4 if i < 40 else 2.0,
            "y_time_to_mfe": 4.0,
            "y_holding_bars": 8.0,
            "features": {"session": 0.0 if i < 40 else 1.0, "rsi_14": float(i)},
            "side": "long",
        })
    recs = state_value_surface(rows_to_cols(rows))
    assert any(r.effect_name == "not_win_rate" for r in recs)
    session = next(r for r in recs if r.question == "state value: session")
    cells = {c["state"]: c for c in session.extra["cells"]}
    assert session.effect_name == "e_mfe_spread"
    assert cells["session=0.0"]["e_mfe"] == 3.0
    assert cells["session=1.0"]["e_mfe"] == 0.5
    assert "win_rate" not in session.to_dict()
    assert cells["session=0.0"]["path_net"] == 3.0 - 0.4


def test_asymmetry_pairs_same_timestamp():
    rows = []
    for t in range(40):
        rows.append({
            "decision_ts": f"t{t}", "side": "long",
            "y_tp1": 1, "y_mfe_r": 2.0, "y_mae_r_heat": 0.5,
            "features": {"trend_bias": 1.0},
        })
        rows.append({
            "decision_ts": f"t{t}", "side": "short",
            "y_tp1": 0, "y_mfe_r": 0.5, "y_mae_r_heat": 2.0,
            "features": {"trend_bias": 1.0},
        })
    recs = asymmetry_atlas(rows_to_cols(rows))
    uncond = next(r for r in recs if r.effect_name == "e_long_mfe_minus_short_mfe")
    assert uncond.n == 40
    assert uncond.effect_size == 1.5  # 2.0 - 0.5
    assert uncond.extra["p_delta_mfe_gt_0"] == 1.0
    tb = next(r for r in recs if r.question == "asymmetry given trend_bias")
    assert tb.extra["cells"][0]["e_delta_mfe"] == 1.5


def test_question_routes_atlases():
    assert route_question("Reached 1R Missed TP") == "leakage"
    assert route_question("state value surface") == "state_value"
    assert route_question("Long MFE - Short MFE") == "asymmetry"


def test_four_surfaces_declared():
    assert set(SURFACES) == {"opportunities", "clean_labels", "events", "telemetry"}
    for banned in FORBIDDEN_PRIMARY_Y:
        assert "stream" in banned or banned in ("outcome", "rr_achieved")

"""Floor: M11 hour_of_day certification."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PROBE = _ROOT / "scripts" / "analysis" / "hour_of_day_certification.py"
_EVIDENCE = _ROOT / "docs" / "governance" / "hour_of_day_certification-2026-07-14.json"


def _load():
    spec = importlib.util.spec_from_file_location("hod_probe", _PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def probe():
    return _load()


def test_dag_deps_timestamp_only():
    from importlib.util import spec_from_file_location, module_from_spec

    spec = spec_from_file_location(
        "fdl", _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    )
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    nd = next(n for n in mod.build_dag()["nodes"] if n["name"] == "hour_of_day")
    assert nd["deps"] == ["timestamp"]
    # index 32 under schema v4.0 (was 31 pre-MACD-split; the histogram split at 2026-07-22
    # shifted the v3.0 tail +1 -- see features/feature_schema.py:47-68).
    assert nd["canonical_index"] == 32
    # CORRECTED 2026-07-22 (FM-052 v2, market_ontology.yaml:1735-1743): session's DAG dep was
    # deliberately changed FROM timestamp TO hour_of_day, matching what the pipeline actually
    # executes (compute_context: df["session"] = classify_session_feature_series(df["hour_of_day"]),
    # not a direct timestamp read). This reverses the prior "M11 note for M12" assumption below
    # -- the ontology and feature_dag_layers.py both now consistently declare
    # session.depends_on=[hour_of_day], so the DAG accurately reflects the real execution-reuse
    # edge rather than an idealized direct-from-timestamp one.
    sess = next(n for n in mod.build_dag()["nodes"] if n["name"] == "session")
    assert sess["deps"] == ["hour_of_day"]


def test_intended_quantity_adjudicated():
    from importlib.util import spec_from_file_location, module_from_spec

    fdl = spec_from_file_location(
        "fdl", _ROOT / "scripts" / "analysis" / "feature_dag_layers.py"
    )
    fmod = module_from_spec(fdl)
    fdl.loader.exec_module(fmod)
    fcs = spec_from_file_location(
        "fcs", _ROOT / "scripts" / "governance" / "feature_certification_state.py"
    )
    smod = module_from_spec(fcs)
    fcs.loader.exec_module(smod)
    iq = smod._intended_quantities(fmod.build_dag())["hour_of_day"]
    assert "UNADJUDICATED" not in iq
    assert "int8" in iq
    assert "0..23" in iq or "0-23" in iq or "{0..23}" in iq


def test_oracle_not_series_dt_hour(probe):
    import inspect
    import ast

    src = inspect.getsource(probe.oracle_hour_of_day)
    tree = ast.parse(src)
    # body must not call attribute chain *.dt.hour
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "hour":
            # allow py.hour from to_pydatetime(); forbid .dt.hour
            if isinstance(node.value, ast.Attribute) and node.value.attr == "dt":
                pytest.fail("oracle must not use Series.dt.hour")


def test_parity_and_boundaries(probe):
    stamps = [
        datetime(2024, 1, 1, 0, 0),
        datetime(2024, 1, 1, 23, 59),
        datetime(2024, 6, 1, 12, 0),
    ]
    o = probe.oracle_hour_of_day(stamps)
    p = probe.pipeline_hour_of_day(stamps)
    assert np.array_equal(o, p)
    assert list(o) == [0, 23, 12]
    assert o.dtype == np.int8


def test_nat_raises(probe):
    with pytest.raises(ValueError):
        probe.oracle_hour_of_day([pd.NaT])


def test_prefix_future_determinism(probe):
    series = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(48)]
    full = probe.oracle_hour_of_day(series)
    assert np.array_equal(probe.oracle_hour_of_day(series[:20]), full[:20])
    mut = list(series)
    mut[20:] = [datetime(2099, 1, 1, 5)] * 28
    assert np.array_equal(probe.oracle_hour_of_day(mut[:20]), full[:20])
    assert np.array_equal(probe.oracle_hour_of_day(series), probe.oracle_hour_of_day(series))


def test_compute_context_parity(probe):
    from features.feature_pipeline import FeaturePipeline

    df = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1) + timedelta(hours=h) for h in range(24)],
            "open": 1.0,
            "high": 1.1,
            "low": 0.9,
            "close": 1.0,
            "volume": 100.0,
        }
    )
    fp = FeaturePipeline(df)
    fp.compute_context()
    assert np.array_equal(
        fp.df["hour_of_day"].to_numpy(),
        probe.oracle_hour_of_day(fp.df["timestamp"].tolist()),
    )


def test_full_battery(probe):
    b = probe.run_battery()
    assert b["overall_verdict"] == "CERTIFIED"


def test_evidence_when_present():
    if not _EVIDENCE.exists():
        pytest.skip("evidence not yet written")
    raw = _EVIDENCE.read_bytes()
    assert len(hashlib.sha256(raw).hexdigest()) == 64
    art = json.loads(raw.decode("utf-8"))
    assert art["TARGET_FEATURE"] == "hour_of_day"
    assert art["PER_NODE_VERDICT"] == "CERTIFIED"
    assert art["PRODUCTION_BEHAVIOR_CHANGED"] == "NO"
    assert art["FULL_DEPENDENCIES"] == ["timestamp"]

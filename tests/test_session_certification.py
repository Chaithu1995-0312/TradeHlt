"""Floor: M12B canonical FeaturePipeline session certification."""
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
_PROBE = _ROOT / "scripts" / "analysis" / "session_certification.py"
_EVIDENCE = _ROOT / "docs" / "governance" / "session_certification-2026-07-14.json"


def _load():
    spec = importlib.util.spec_from_file_location("session_probe", _PROBE)
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
    nd = next(n for n in mod.build_dag()["nodes"] if n["name"] == "session")
    # CORRECTED 2026-07-22 (see session_certification.py module docstring): session's DAG dep is
    # deliberately hour_of_day, not timestamp directly -- matches the ontology (FM-052
    # depends_on=[hour_of_day]) and what the pipeline actually executes.
    assert nd["deps"] == ["hour_of_day"]
    # index 31 under schema v4.0 (was 30 pre-MACD-split; shifted +1, feature_schema.py:47-68).
    assert nd["canonical_index"] == 31


def test_intended_quantity_not_unadjudicated():
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
    iq = smod._intended_quantities(fmod.build_dag())["session"]
    assert "UNADJUDICATED" not in iq
    # CORRECTED 2026-07-31: the witness was re-certified against FM-052 v4.0 (window model,
    # 5-value domain) -- the v3.0 "00-07"/"0 for hours" 3-value-partition text this test used to
    # pin no longer describes what session actually computes; asserting it would pin the OLD,
    # already-fixed defect back in as "expected".
    assert "window model" in iq or "ASIA" in iq
    assert "int8" in iq
    assert "hour_of_day" in iq


def test_exhaustive_24h(probe):
    # v4.0 buckets: ASIA h0-6(7h) LONDON h7-11(5h) OVERLAP h12-15(4h) NEWYORK h16-20(5h) CLOSED h21-23(3h).
    stamps = [datetime(2024, 6, 1, h, 0) for h in range(24)]
    o = probe.oracle_session(stamps)
    exp = np.array([0] * 7 + [1] * 5 + [3] * 4 + [2] * 5 + [4] * 3, dtype=np.int8)
    assert np.array_equal(o, exp)
    assert o.dtype == np.int8


def test_transitions(probe):
    assert int(probe.oracle_session_code_from_hour(7)) == 1  # LONDON starts
    assert int(probe.oracle_session_code_from_hour(8)) == 1
    assert int(probe.oracle_session_code_from_hour(15)) == 3  # still OVERLAP (NEWYORK started at 12)
    assert int(probe.oracle_session_code_from_hour(16)) == 2  # LONDON ends -> NEWYORK only
    assert int(probe.oracle_session_code_from_hour(23)) == 4  # NEWYORK ended at 21 -> CLOSED
    assert int(probe.oracle_session_code_from_hour(0)) == 0


def test_pipeline_parity(probe):
    stamps = [datetime(2024, 1, 1, h, 15) for h in range(24)]
    assert np.array_equal(
        probe.oracle_session(stamps),
        probe.pipeline_session_from_timestamps(stamps),
    )


def test_nat_raises(probe):
    with pytest.raises(ValueError):
        probe.oracle_session([pd.NaT])


def test_pit_prefix_future_sens(probe):
    series = [datetime(2024, 2, 1) + timedelta(hours=i) for i in range(48)]
    full = probe.oracle_session(series)
    assert np.array_equal(probe.oracle_session(series[:20]), full[:20])
    mut = list(series)
    mut[20:] = [datetime(2099, 1, 1, 3)] * 28
    assert np.array_equal(probe.oracle_session(mut[:20]), full[:20])
    # ASIA(h6)->LONDON(h7) boundary crossing; second element (h3, ASIA) held fixed and unaffected.
    a = probe.oracle_session([datetime(2024, 5, 1, 6), datetime(2024, 5, 1, 3)])
    b = probe.oracle_session([datetime(2024, 5, 1, 7), datetime(2024, 5, 1, 3)])
    assert int(a[0]) == 0 and int(b[0]) == 1 and int(a[1]) == int(b[1]) == 0


def test_encoding_isolation_SESSION_MAP(probe):
    from features.feature_schema import SESSION_MAP

    # CORRECTED 2026-07-31: SESSION_MAP's v3.0 permutation bug (asian=2.0 vs pipeline Asia=0) was
    # RESOLVED by the v4.0 migration -- SESSION_MAP now derives from the single-owner
    # session_classifier.SESSION_NAME_TO_ORDINAL, so it necessarily agrees with the pipeline.
    # This test's direction is flipped from "prove divergence" to "prove parity" accordingly.
    assert int(probe.oracle_session_code_from_hour(3)) == 0
    assert float(SESSION_MAP["asian"]) == 0.0
    assert int(probe.oracle_session_code_from_hour(3)) == int(SESSION_MAP["asian"])
    indep = probe.assert_oracle_independence()
    assert indep["ok"] is True


def test_full_battery(probe):
    b = probe.run_battery()
    assert b["overall_verdict"] == "CERTIFIED"


def test_evidence_when_present():
    if not _EVIDENCE.exists():
        pytest.skip("evidence not yet written")
    raw = _EVIDENCE.read_bytes()
    assert len(hashlib.sha256(raw).hexdigest()) == 64
    art = json.loads(raw.decode("utf-8"))
    assert art["TARGET_FEATURE"] == "session"
    assert art["PER_NODE_VERDICT"] == "CERTIFIED"
    # CORRECTED 2026-07-31: session's DAG dep is hour_of_day (FM-052 v4.0), not timestamp.
    assert art["CURRENT_DAG_DEPS"] == ["hour_of_day"]
    assert art["PRODUCTION_BEHAVIOR_CHANGED"] == "NO"

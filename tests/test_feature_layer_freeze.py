"""Mechanical floor for FEATURE-LAYER-MUTATION-FREEZE-2026-07-20.

Asserts:
  * freeze policy + pin exist and carry the status token
  * freeze is classified as a GOVERNANCE freeze (not scientific closure)
  * schema / source-file pins match the frozen snapshot
  * XAUUSD-only feature-matrix vector SHA matches
  * coverage metadata scopes what the benchmark does / does not exercise
  * BNB is NOT part of the feature freeze pin (runtime suite later)

Does not grant activation authority. Does not assert trade/PnL outcomes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FREEZE_PIN = ROOT / "docs" / "governance" / "feature-layer-freeze-pin-2026-07-20.json"
FREEZE_POLICY = ROOT / "docs" / "governance" / "feature-layer-mutation-freeze-2026-07-20.md"
ROADMAP = ROOT / "docs" / "implementation_plan" / "backtest-runtime-roadmap-2026-07-20.md"

FREEZE_ID = "FEATURE-LAYER-MUTATION-FREEZE-2026-07-20"
STATUS_TOKEN = "FEATURE_LAYER_MUTATION_FREEZE = ACTIVE"
XAU_KEY = "XAUUSD_W2026-03-23-to-2026-05-21"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_pin() -> dict:
    assert FREEZE_PIN.is_file(), f"missing freeze pin: {FREEZE_PIN}"
    return json.loads(FREEZE_PIN.read_text(encoding="utf-8"))


def test_freeze_policy_and_roadmap_exist():
    assert FREEZE_POLICY.is_file()
    text = FREEZE_POLICY.read_text(encoding="utf-8")
    assert FREEZE_ID in text
    assert STATUS_TOKEN in text
    assert "governance freeze" in text.lower() or "GOVERNANCE" in text
    assert "accepted future" in text.lower() or "Accepted future" in text
    assert "scientifically extensible" in text.lower() or "not a scientific" in text.lower()
    assert ROADMAP.is_file(), "backtest/runtime roadmap must exist after freeze"
    road = ROADMAP.read_text(encoding="utf-8")
    assert "backtest" in road.lower() and "runtime" in road.lower()


def test_freeze_pin_schema_governance_class():
    pin = _load_pin()
    assert pin.get("freeze_id") == FREEZE_ID
    assert pin.get("status_token") == STATUS_TOKEN
    assert pin.get("freeze_class") == "GOVERNANCE_FREEZE"
    assert pin.get("active_config_version") == "v2_multi_2026_04"
    schema = pin["schema"]
    # 39 under schema v4.0 (was 38 pre-2026-07-22 SCHEMA-V4-VECTOR-MIGRATION; pin refreshed
    # 2026-08-01 per that program's own already-authorized regeneration requirement).
    assert schema["feature_dim"] == 39
    assert schema["feature_count"] == 39
    assert len(schema["canonical_features"]) == 39
    assert "regression_benchmarks" in pin
    assert "source_file_pins" in pin
    assert isinstance(pin.get("accepted_future_programs"), list)
    assert len(pin["accepted_future_programs"]) >= 8


def test_feature_benchmark_is_xauusd_only():
    """BNB (and other instruments) are runtime-suite territory, not this freeze pin."""
    pin = _load_pin()
    benches = pin["regression_benchmarks"]
    assert list(benches.keys()) == [XAU_KEY], (
        f"feature freeze pin must be XAUUSD-only; got {list(benches.keys())}"
    )
    for forbidden in ("BNB", "BNBUSDT", "BTC", "ETH", "SOL"):
        blob = json.dumps(benches)
        assert forbidden not in blob, f"feature pin must not embed {forbidden} benchmark"
    rt = pin.get("runtime_benchmarks") or {}
    assert rt.get("status") == "NOT_YET_OPENED"
    assert "R-1" in (rt.get("opens_with") or "") or "R-2" in (rt.get("opens_with") or "")


def test_source_file_pins_match():
    pin = _load_pin()
    for name, meta in pin["source_file_pins"].items():
        path = ROOT / meta["path"]
        assert path.is_file(), f"{name}: missing {path}"
        live = _sha256_file(path)
        assert live == meta["sha256"], (
            f"{name}: source drift under feature-layer freeze. "
            f"pinned={meta['sha256'][:16]}… live={live[:16]}… "
            f"If intentional, update the freeze pin in the same change set (waiver procedure)."
        )


def test_schema_pins_match():
    from features.feature_schema import (
        CANONICAL_FEATURE_DIM,
        CANONICAL_FEATURES,
        SCHEMA_HASH,
        SCHEMA_VERSION,
    )

    pin = _load_pin()
    schema = pin["schema"]
    assert SCHEMA_VERSION == schema["schema_version"]
    assert SCHEMA_HASH == schema["schema_hash"]
    assert CANONICAL_FEATURE_DIM == schema["feature_dim"]
    assert list(CANONICAL_FEATURES) == schema["canonical_features"]


def _run_vector(path: Path) -> tuple[np.ndarray, int, int]:
    from features.feature_pipeline import FeaturePipeline

    df = pd.read_csv(path)
    n_in = len(df)
    _out_df, vectors = FeaturePipeline(df).run()
    v = np.ascontiguousarray(vectors)
    return v, n_in, int(v.shape[0])


def test_xauusd_window_vector_regression():
    pin = _load_pin()
    bench = pin["regression_benchmarks"][XAU_KEY]
    path = ROOT / bench["input_path"]
    assert path.is_file(), path
    assert _sha256_file(path) == bench["input_sha256"], (
        "XAUUSD window CSV bytes drifted — freeze pin input contract broken"
    )
    vectors, n_in, n_out = _run_vector(path)
    assert n_in == bench["input_rows"]
    assert n_out == bench["output_rows"]
    assert list(vectors.shape) == bench["vector_shape"]
    assert str(vectors.dtype) == bench["vector_dtype"]
    live = hashlib.sha256(vectors.tobytes()).hexdigest()
    assert live == bench["vector_sha256"], (
        f"XAUUSD feature-vector regression failed under freeze. "
        f"pinned={bench['vector_sha256'][:16]}… live={live[:16]}… "
        "Feature math or config periods changed without updating the freeze pin."
    )


def test_xauusd_coverage_metadata_scopes_false_green():
    """Parity of the feature matrix must not be misread as full-path behavioral equivalence."""
    pin = _load_pin()
    cov = pin["regression_benchmarks"][XAU_KEY]["coverage"]
    assert cov["benchmark_class"] == "FEATURE_MATRIX"
    assert cov["feature_rows_out"] == 3871
    assert cov["warmup_drop"] == 78
    ex = cov["exercises"]
    assert ex["feature_pipeline_batch_run"] is True
    # 39-dim under schema v4.0 (pin refreshed 2026-08-01; the "38" key is retained, now False,
    # per the refresh script -- see canonical_39_vector_emission for the current-truth flag).
    assert ex["canonical_38_vector_emission"] is False
    assert ex["canonical_39_vector_emission"] is True
    dne = cov["does_not_exercise"]
    for key in (
        "backtest_v2",
        "crt_state_machine",
        "session_filter",
        "zone_gate",
        "fusion_gate",
        "decision_engine",
        "execution_planner",
        "ultron_risk_gate",
        "partial_tp",
        "trade_ledger",
    ):
        assert dne[key] is False, f"coverage must mark {key} as not exercised by feature pin"
    assert cov["trade_count"] is None


def test_accepted_future_programs_are_named():
    pin = _load_pin()
    ids = {p["id"] for p in pin["accepted_future_programs"]}
    for required in (
        "M16-WU-SESSION-ENCODING",
        "M16-WU-SUPERSEDED-VECTOR-MIGRATION",
        "T-11-FEEDER-HANDSHAKE",
        "STATEFUL-6",
    ):
        assert required in ids, f"missing accepted future program {required}"

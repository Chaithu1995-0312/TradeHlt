"""
test_stage1_dataset_builder.py
==============================
Tests for src/training/stage1_dataset_builder.py.

Covers:
  - RR + duration bucket boundary semantics (inclusive lower, exclusive upper)
  - Scope classification (crypto + forex patterns)
  - Feature-quality 4-component composite + 0.70 rejection threshold
  - validate_record_shape: missing canonical keys, extras preserved
  - iter_opportunities: skips run_header, surfaces JSON errors
  - transform_record: win_flag, replay_ready, metadata stamping
  - build_dataset end-to-end:
      * deterministic output sha256 (back-to-back runs)
      * strong duplicate key (instrument,timestamp,direction,entry,sl,run_id)
      * strict_layout raises on missing trades.csv
      * default mode tolerates missing companions
      * out-of-scope instruments listed in scope_summary
      * all 4 report files written
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest


# Ensure src/ on sys.path (conftest does this too — belt-and-braces).
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from training.stage1_dataset_builder import (
    BUCKET_VERSION,
    BuilderConfig,
    CANONICAL_FEATURES,
    RR_BUCKETS,
    DURATION_BUCKETS,
    build_dataset,
    classify_scope,
    compute_feature_quality,
    duration_bucket,
    iter_opportunities,
    is_run_header,
    resolve_auto_scope,
    rr_bucket,
    transform_record,
    validate_record_shape,
)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _valid_features(seed: float = 0.1) -> dict:
    """Build a fully populated canonical features dict with varied values."""
    out = {}
    for i, k in enumerate(CANONICAL_FEATURES):
        out[k] = seed + i * 0.013
    out["session"] = 0.0
    out["trend_bias"] = 1.0
    out["volatility_regime"] = 1.0
    out["hour_of_day"] = 10.0
    return out


def _valid_record(
    instrument: str = "BTCUSDT",
    timestamp: str = "2022-01-02 07:45:00",
    direction: str = "long",
    rr: float = 1.5,
    duration: int = 12,
    seed: float = 0.1,
    extras: dict | None = None,
) -> dict:
    feats = _valid_features(seed)
    if extras:
        feats.update(extras)
    return {
        "timestamp": timestamp,
        "instrument": instrument,
        "direction": direction,
        "entry": 47100.5,
        "sl": 46980.0,
        "tp": 47280.0,
        "outcome": "TP_HIT" if rr > 0 else "SL_HIT",
        "rr_achieved": rr,
        "duration_candles": duration,
        "mfe": 5.4,
        "mae": -2.1,
        "features": feats,
    }


def _write_jsonl(path: Path, records: list, instrument: str, run_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({
            "type": "run_header",
            "run_id": run_id,
            "instrument": instrument,
            "started_at": "2026-05-22T00:00:00Z",
        }) + "\n")
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _make_layout(
    tmp_path: Path,
    instrument: str = "BTCUSDT",
    run_id: str = "20260522_120000",
    records: list | None = None,
    with_trades_csv: bool = True,
) -> tuple[Path, Path]:
    """Materialize a minimal (jsonl_root, csv_root) layout under tmp_path."""
    if records is None:
        records = [_valid_record(instrument=instrument)]
    jsonl_root = tmp_path / "logs"
    csv_root = tmp_path / "results"
    opp_path = jsonl_root / instrument / run_id / "opportunities.jsonl"
    _write_jsonl(opp_path, records, instrument, run_id)
    if with_trades_csv:
        csv_path = csv_root / f"run_{run_id}_{instrument}" / f"{instrument}_trades.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.write_text("trade_id,outcome\n1,TP_HIT\n", encoding="utf-8")
    return jsonl_root, csv_root


# ─── BUCKETING ────────────────────────────────────────────────────────────────

def test_rr_bucket_boundaries_inclusive_lower_exclusive_upper():
    # Edge points: 0.0 → SCRATCH, 1.0 → BASE, 2.0 → STRONG, 3.0 → OUTLIER
    assert rr_bucket(-0.0001) == (0, "LOSS")
    assert rr_bucket(0.0) == (1, "SCRATCH")
    assert rr_bucket(0.9999) == (1, "SCRATCH")
    assert rr_bucket(1.0) == (2, "BASE")
    assert rr_bucket(1.9999) == (2, "BASE")
    assert rr_bucket(2.0) == (3, "STRONG")
    assert rr_bucket(3.0) == (4, "OUTLIER")
    assert rr_bucket(99.0) == (4, "OUTLIER")
    assert rr_bucket(-1.0) == (0, "LOSS")
    assert rr_bucket(float("nan")) == (-1, "INVALID")


def test_duration_bucket_boundaries_inclusive_lower_exclusive_upper():
    # FAST 0-3, NORMAL 4-10, SWING 11-30, EXTENDED 31-90, RUNNER >90
    assert duration_bucket(0) == (0, "FAST")
    assert duration_bucket(3) == (0, "FAST")
    assert duration_bucket(4) == (1, "NORMAL")
    assert duration_bucket(10) == (1, "NORMAL")
    assert duration_bucket(11) == (2, "SWING")
    assert duration_bucket(30) == (2, "SWING")
    assert duration_bucket(31) == (3, "EXTENDED")
    assert duration_bucket(90) == (3, "EXTENDED")
    assert duration_bucket(91) == (4, "RUNNER")
    assert duration_bucket(99999) == (4, "RUNNER")
    assert duration_bucket(-1) == (-1, "INVALID")
    assert duration_bucket("abc") == (-1, "INVALID")


def test_bucket_version_is_stamped():
    assert BUCKET_VERSION == 1
    assert len(RR_BUCKETS) == 5
    assert len(DURATION_BUCKETS) == 5


# ─── SCOPE ────────────────────────────────────────────────────────────────────

def test_classify_scope_crypto_patterns():
    assert classify_scope("BTCUSDT", "crypto") is True
    assert classify_scope("ETHUSDT", "crypto") is True
    assert classify_scope("SOLUSDT", "crypto") is True
    assert classify_scope("BNBUSDT", "crypto") is True
    assert classify_scope("DOGEUSDT", "crypto") is True
    assert classify_scope("XRPUSDT", "crypto") is True
    assert classify_scope("EURUSD", "crypto") is False
    assert classify_scope("GBPUSD", "crypto") is False
    assert classify_scope("XAUUSD", "crypto") is False


def test_classify_scope_forex_patterns():
    assert classify_scope("EURUSD", "forex") is True
    assert classify_scope("GBPUSD", "forex") is True
    assert classify_scope("XAUUSD", "forex") is True
    assert classify_scope("AUDUSD", "forex") is True
    assert classify_scope("BTCUSDT", "forex") is False


def test_classify_scope_all_admits_everything():
    assert classify_scope("ANYTHING", "all") is True
    assert classify_scope("BTCUSDT", "all") is True


def test_resolve_auto_scope_homogeneous_crypto():
    assert resolve_auto_scope(["BTCUSDT", "ETHUSDT", "SOLUSDT"]) == "crypto"


def test_resolve_auto_scope_homogeneous_forex():
    assert resolve_auto_scope(["EURUSD", "GBPUSD"]) == "forex"


def test_resolve_auto_scope_mixed_falls_back_to_all():
    assert resolve_auto_scope(["BTCUSDT", "EURUSD"]) == "all"


# ─── FEATURE QUALITY ──────────────────────────────────────────────────────────

def test_feature_quality_perfect_record_scores_high():
    q = compute_feature_quality(_valid_features())
    assert q["score"] >= 0.95
    assert q["present_frac"] == 1.0
    assert q["finite_frac"] == 1.0
    assert q["variance_flag"] == 1.0


def test_feature_quality_all_zero_vector_rejected_below_threshold():
    feats = {k: 0.0 for k in CANONICAL_FEATURES}
    q = compute_feature_quality(feats)
    # present=1.0, finite=1.0, non_default=0.0, variance=0.0 → 0.5
    assert q["score"] == pytest.approx(0.5)
    assert q["score"] < 0.70


def test_feature_quality_constant_nonzero_vector_low_variance():
    feats = {k: 1.0 for k in CANONICAL_FEATURES}
    q = compute_feature_quality(feats)
    # present=1, finite=1, non_default=1, variance=0 → 0.75 (passes 0.70)
    assert q["score"] == pytest.approx(0.75)
    assert q["variance_flag"] == 0.0


def test_feature_quality_missing_keys_reduces_present_frac():
    feats = _valid_features()
    feats.pop("rsi_14")
    # macd_hist_raw (was macd_hist pre-2026-07-22 SCHEMA-V4-VECTOR-MIGRATION, which split the
    # single v3.0 column into macd_hist_raw + macd_hist_z).
    feats.pop("macd_hist_raw")
    q = compute_feature_quality(feats)
    assert q["present_frac"] < 1.0
    assert q["score"] < 1.0


# ─── VALIDATION ───────────────────────────────────────────────────────────────

def test_validate_record_shape_missing_canonical_key_rejected():
    rec = _valid_record()
    rec["features"].pop("rsi_14")
    ok, reason, normalized = validate_record_shape(rec, "WARN")
    assert ok is False
    assert reason == "missing_features"
    assert normalized is None


def test_validate_record_shape_extras_preserved():
    rec = _valid_record(extras={"my_custom_signal": 1.23, "another_extra": "tag"})
    ok, reason, normalized = validate_record_shape(rec, "WARN")
    assert ok is True
    assert reason == ""
    assert set(normalized["features"].keys()) == set(CANONICAL_FEATURES)
    assert normalized["extra_features"] == {
        "my_custom_signal": 1.23,
        "another_extra": "tag",
    }


def test_validate_record_shape_missing_top_level_rejected():
    rec = _valid_record()
    del rec["instrument"]
    ok, reason, _ = validate_record_shape(rec, "WARN")
    assert ok is False
    assert reason == "schema_mismatch"


def test_validate_record_shape_no_outcome_rejected():
    rec = _valid_record()
    del rec["rr_achieved"]
    ok, reason, _ = validate_record_shape(rec, "WARN")
    assert ok is False
    assert reason == "no_outcome"


def test_validate_record_strict_rejects_unparseable_feature_value():
    rec = _valid_record()
    rec["features"]["rsi_14"] = "not_a_number"
    ok, reason, _ = validate_record_shape(rec, "STRICT")
    assert ok is False
    assert reason == "type_mismatch"


def test_validate_record_warn_coerces_bad_value_to_zero():
    rec = _valid_record()
    rec["features"]["rsi_14"] = "not_a_number"
    ok, reason, normalized = validate_record_shape(rec, "WARN")
    assert ok is True
    assert normalized["features"]["rsi_14"] == 0.0


# ─── ITER_OPPORTUNITIES ───────────────────────────────────────────────────────

def test_iter_opportunities_skips_run_header(tmp_path):
    path = tmp_path / "opportunities.jsonl"
    _write_jsonl(path, [_valid_record()], "BTCUSDT", "20260522_000000")
    items = list(iter_opportunities(path))
    assert len(items) == 1
    line_no, rec, err = items[0]
    assert line_no == 2  # line 1 was the header
    assert err is None
    assert rec["instrument"] == "BTCUSDT"


def test_iter_opportunities_surfaces_parse_error(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text(
        json.dumps({"type": "run_header", "run_id": "x"}) + "\n"
        "{not json at all}\n"
        + json.dumps(_valid_record()) + "\n",
        encoding="utf-8",
    )
    items = list(iter_opportunities(path))
    assert len(items) == 2
    bad_line_no, bad_rec, bad_err = items[0]
    assert bad_line_no == 2
    assert bad_rec is None
    assert bad_err is not None
    good_line_no, good_rec, good_err = items[1]
    assert good_line_no == 3
    assert good_rec is not None
    assert good_err is None


def test_is_run_header_recognizes_both_keys():
    assert is_run_header({"type": "run_header"}) is True
    assert is_run_header({"kind": "run_header"}) is True
    assert is_run_header({"timestamp": "x"}) is False


# ─── TRANSFORM ────────────────────────────────────────────────────────────────

def test_transform_record_stamps_win_flag_and_replay_ready():
    rec = _valid_record(rr=2.4, duration=18)
    ok, _, normalized = validate_record_shape(rec, "WARN")
    assert ok is True
    out, rej = transform_record(
        rec, normalized,
        {"run_id": "R1", "line_no": 17, "path": "logs/X/R1/opportunities.jsonl"},
        min_feature_quality=0.70,
    )
    assert rej is None
    assert out is not None
    assert out["win_flag"] == 1
    assert out["rr_bucket_label"] == "STRONG"
    assert out["duration_bucket_label"] == "SWING"
    assert out["metadata"]["replay_ready"] is True
    assert out["metadata"]["replay_version"] == 1
    assert out["metadata"]["bucket_version"] == 1
    assert out["metadata"]["source_run_id"] == "R1"
    assert out["metadata"]["source_line_no"] == 17


def test_transform_record_low_quality_rejected():
    rec = _valid_record()
    rec["features"] = {k: 0.0 for k in CANONICAL_FEATURES}
    ok, _, normalized = validate_record_shape(rec, "WARN")
    assert ok is True
    out, rej = transform_record(
        rec, normalized,
        {"run_id": "R", "line_no": 1, "path": "p"},
        min_feature_quality=0.70,
    )
    assert out is None
    assert rej == "low_feature_quality"


def test_transform_record_negative_rr_yields_loss_bucket_and_zero_win():
    rec = _valid_record(rr=-0.5, duration=2)
    _, _, normalized = validate_record_shape(rec, "WARN")
    out, _ = transform_record(
        rec, normalized,
        {"run_id": "R", "line_no": 1, "path": "p"},
        min_feature_quality=0.70,
    )
    assert out["win_flag"] == 0
    assert out["rr_bucket_label"] == "LOSS"
    assert out["duration_bucket_label"] == "FAST"


# ─── END-TO-END BUILD ─────────────────────────────────────────────────────────

def _basic_cfg(tmp_path: Path, **overrides) -> BuilderConfig:
    base = dict(
        jsonl_root=tmp_path / "logs",
        csv_root=tmp_path / "results",
        output_dir=tmp_path / "data",
        reports_dir=tmp_path / "reports",
        market_scope="crypto",
        validation_level="WARN",
        strict_layout=False,
        min_feature_quality=0.70,
        instruments_override=None,
    )
    base.update(overrides)
    return BuilderConfig(**base)


def test_build_dataset_emits_all_four_reports(tmp_path):
    _make_layout(tmp_path, records=[_valid_record(), _valid_record(timestamp="2022-01-02 08:00:00")])
    cfg = _basic_cfg(tmp_path)
    result = build_dataset(cfg)

    assert result.output_path.exists()
    assert result.integrity_report_path.exists()
    assert result.instrument_summary_path.exists()
    assert result.input_manifest_path.exists()
    assert result.scope_summary_path.exists()

    integrity = json.loads(result.integrity_report_path.read_text(encoding="utf-8"))
    assert integrity["totals"]["accepted"] == 2
    assert integrity["totals"]["rejected_total"] == 0
    assert integrity["output_sha256"] == result.output_sha256
    assert integrity["bucket_version"] == 1
    assert integrity["replay_version"] == 1


def test_build_dataset_deterministic_output_hash(tmp_path):
    records = [
        _valid_record(timestamp="2022-01-02 07:45:00", rr=1.2),
        _valid_record(timestamp="2022-01-02 08:00:00", rr=-0.5),
        _valid_record(timestamp="2022-01-02 09:00:00", rr=2.1),
    ]
    _make_layout(tmp_path, records=records)
    cfg = _basic_cfg(tmp_path)
    r1 = build_dataset(cfg)
    r2 = build_dataset(cfg)
    assert r1.output_sha256 == r2.output_sha256
    assert r1.output_sha256 != ""
    assert r1.accepted == r2.accepted == 3


def test_build_dataset_duplicate_key_collapses_repeats_within_a_run(tmp_path):
    rec = _valid_record(timestamp="2022-01-02 07:45:00", direction="long")
    # Two identical rows in the same run → second is dropped.
    _make_layout(tmp_path, records=[rec, dict(rec)])
    cfg = _basic_cfg(tmp_path)
    result = build_dataset(cfg)
    assert result.accepted == 1
    assert result.rejected.duplicate == 1


def test_build_dataset_duplicate_key_admits_long_and_short_at_same_timestamp(tmp_path):
    a = _valid_record(direction="long", rr=1.2)
    b = _valid_record(direction="short", rr=-0.5)
    _make_layout(tmp_path, records=[a, b])
    cfg = _basic_cfg(tmp_path)
    result = build_dataset(cfg)
    # Different direction → not duplicates.
    assert result.accepted == 2
    assert result.rejected.duplicate == 0


def test_build_dataset_records_sorted_by_timestamp(tmp_path):
    records = [
        _valid_record(timestamp="2022-01-02 09:00:00", rr=1.2),
        _valid_record(timestamp="2022-01-02 07:45:00", rr=-0.5),
        _valid_record(timestamp="2022-01-02 08:00:00", rr=2.1),
    ]
    _make_layout(tmp_path, records=records)
    cfg = _basic_cfg(tmp_path)
    result = build_dataset(cfg)
    timestamps = [
        json.loads(line)["timestamp"]
        for line in result.output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert timestamps == sorted(timestamps)


def test_strict_layout_raises_on_missing_trades_csv(tmp_path):
    _make_layout(tmp_path, with_trades_csv=False)
    cfg = _basic_cfg(tmp_path, strict_layout=True)
    with pytest.raises(RuntimeError):
        build_dataset(cfg)


def test_default_layout_tolerates_missing_trades_csv(tmp_path):
    _make_layout(tmp_path, with_trades_csv=False)
    cfg = _basic_cfg(tmp_path, strict_layout=False)
    result = build_dataset(cfg)
    assert result.accepted == 1
    manifest = json.loads(result.input_manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["missing_trades"]) == 1


def test_out_of_scope_instruments_recorded_in_scope_summary(tmp_path):
    # EURUSD is forex; under scope=crypto it must be rejected.
    _make_layout(tmp_path, instrument="EURUSD", run_id="20260522_000000",
                 records=[_valid_record(instrument="EURUSD")])
    cfg = _basic_cfg(tmp_path, market_scope="crypto")
    result = build_dataset(cfg)
    scope = json.loads(result.scope_summary_path.read_text(encoding="utf-8"))
    assert "EURUSD" in scope["rejected_instruments"]
    assert result.rejected.out_of_scope >= 1
    assert result.accepted == 0


def test_instruments_override_takes_precedence_over_scope(tmp_path):
    _make_layout(tmp_path, instrument="EURUSD", run_id="20260522_000000",
                 records=[_valid_record(instrument="EURUSD")])
    cfg = _basic_cfg(tmp_path, market_scope="crypto",
                     instruments_override=("EURUSD",))
    result = build_dataset(cfg)
    assert result.accepted == 1


def test_per_record_metadata_carries_source_provenance(tmp_path):
    _make_layout(tmp_path, instrument="BTCUSDT", run_id="20260522_120000",
                 records=[_valid_record(instrument="BTCUSDT")])
    cfg = _basic_cfg(tmp_path)
    result = build_dataset(cfg)
    line = result.output_path.read_text(encoding="utf-8").splitlines()[0]
    rec = json.loads(line)
    md = rec["metadata"]
    assert md["source_run_id"] == "20260522_120000"
    assert md["feature_dim"] == len(CANONICAL_FEATURES)
    assert md["feature_hash"]  # non-empty
    assert "opportunities.jsonl" in md["source_path"]


def test_malformed_line_does_not_abort_build(tmp_path):
    instrument = "BTCUSDT"
    run_id = "20260522_120000"
    jsonl_root = tmp_path / "logs"
    opp_path = jsonl_root / instrument / run_id / "opportunities.jsonl"
    opp_path.parent.mkdir(parents=True, exist_ok=True)
    valid = _valid_record(instrument=instrument)
    opp_path.write_text(
        json.dumps({"type": "run_header", "run_id": run_id}) + "\n"
        + "{not valid json\n"
        + json.dumps(valid) + "\n",
        encoding="utf-8",
    )
    cfg = _basic_cfg(tmp_path)
    result = build_dataset(cfg)
    assert result.accepted == 1
    assert result.rejected.malformed_json == 1


def test_no_inputs_strict_layout_raises(tmp_path):
    cfg = _basic_cfg(tmp_path, strict_layout=True)
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    with pytest.raises(RuntimeError):
        build_dataset(cfg)


def test_no_inputs_default_returns_empty_build(tmp_path):
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    cfg = _basic_cfg(tmp_path)
    result = build_dataset(cfg)
    assert result.accepted == 0
    assert result.output_path.exists()
    assert result.output_path.read_text(encoding="utf-8") == ""

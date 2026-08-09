"""
Ledger completeness floor (target-strategy-architecture.md §13 item8 / §9).

TradeProvenanceV1 had zero consumers before this — these tests pin the two
new mechanisms end to end:
  1. runtime.backtest_v2._build_provenance_base() resolves config/model/strategy
     identity once per run.
  2. utils.trade_logger.TradeLogger.log_entry() writes it (+ feature_vector_sha
     + gates_fired) additively, and — the concrete bug this session caught —
     gates_fired (a CRTConfig snapshot containing datetime.time session
     windows) must survive json.dumps rather than silently failing the whole
     ENTRY write (TradeLogger._write fails open, so a serialization bug here
     previously deleted every ENTRY record with no visible error).
"""
from __future__ import annotations

import dataclasses
import json

from config_layer.config_builder import ConfigBuilder
from utils.trade_logger import TradeLogger


def test_build_provenance_base_resolves_identity():
    from runtime.backtest_v2 import _build_provenance_base

    base = _build_provenance_base("XAUUSD", "")
    assert base["config_version"]
    assert base["config_hash"]
    assert base["promotion_version"]
    assert base["strategy_id"]  # falls back to the resolved StrategyPackage name
    assert "gaussian_impl=" in (base["model_version"] or "")


def test_build_provenance_base_honors_explicit_strategy_id():
    from runtime.backtest_v2 import _build_provenance_base

    base = _build_provenance_base("XAUUSD", "my_pinned_strategy")
    assert base["strategy_id"] == "my_pinned_strategy"


def test_build_provenance_base_never_raises_on_bad_instrument():
    """Best-effort — a resolution failure degrades fields, it does not abort the run."""
    from runtime.backtest_v2 import _build_provenance_base

    base = _build_provenance_base("TOTALLY_UNRECOGNIZED_XYZ", "")
    assert base["config_version"]  # global fields still populate
    # model_version may be "" if every registry lookup misses — must not raise.


def test_log_entry_writes_provenance_fields(tmp_path):
    logger = TradeLogger(tmp_path / "fusion.jsonl")
    logger.log_entry(
        trade_id="T1", instrument="XAUUSD", direction="LONG", session="LONDON",
        regime="", features={}, fusion_result={}, risk_pct=0.005,
        entry_price=1.0, sl_price=0.9, tp1_price=1.1, tp2_price=1.2,
        provenance={"strategy_id": "s1", "config_hash": "abc"},
        feature_vector_sha="deadbeef",
        gates_fired={"body_ratio_min": 0.65},
    )
    lines = (tmp_path / "fusion.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["provenance"]["strategy_id"] == "s1"
    assert rec["feature_vector_sha"] == "deadbeef"
    assert rec["gates_fired"]["body_ratio_min"] == 0.65


def test_log_entry_defaults_are_additive_and_backward_compatible(tmp_path):
    """Callers that don't pass the new kwargs (existing call sites elsewhere in
    the repo, if any) still produce a valid, old-shape-compatible record."""
    logger = TradeLogger(tmp_path / "fusion.jsonl")
    logger.log_entry(
        trade_id="T2", instrument="XAUUSD", direction="LONG", session="LONDON",
        regime="", features={}, fusion_result={}, risk_pct=0.005,
        entry_price=1.0, sl_price=0.9, tp1_price=1.1, tp2_price=1.2,
    )
    rec = json.loads((tmp_path / "fusion.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert rec["provenance"] == {}
    assert rec["feature_vector_sha"] == ""
    assert rec["gates_fired"] == {}


def test_gates_fired_crtconfig_snapshot_survives_json_round_trip(tmp_path):
    """The regression this session caught: CRTConfig.session_windows carries
    datetime.time objects. A naive dataclasses.asdict() + json.dumps() raises
    TypeError, which TradeLogger._write swallows — silently deleting the ENTRY
    record with no traceback. gates_fired must already be JSON-safe by the time
    it reaches log_entry."""
    crt_cfg = ConfigBuilder.build("XAUUSD")
    raw = dataclasses.asdict(crt_cfg)
    assert any(
        hasattr(v, "hour") or (isinstance(v, dict) and any(hasattr(x, "hour") for x in _flatten(v)))
        for v in raw.values()
    ), "fixture assumption broken: CRTConfig no longer carries a datetime.time field"

    safe = json.loads(json.dumps(raw, default=str))
    logger = TradeLogger(tmp_path / "fusion.jsonl")
    logger.log_entry(
        trade_id="T3", instrument="XAUUSD", direction="LONG", session="LONDON",
        regime="", features={}, fusion_result={}, risk_pct=0.005,
        entry_price=1.0, sl_price=0.9, tp1_price=1.1, tp2_price=1.2,
        gates_fired=safe,
    )
    lines = (tmp_path / "fusion.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, "ENTRY record silently dropped — the json-safety regression"
    rec = json.loads(lines[0])
    assert rec["event"] == "ENTRY"


def _flatten(d):
    for v in d.values():
        if isinstance(v, (tuple, list)):
            yield from v
        else:
            yield v

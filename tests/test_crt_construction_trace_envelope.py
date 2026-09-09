"""Floors for the CRTConstructionTrace SCHEMA v2.0.0 "ResolverEngine envelope".

CH-resolver-engine-envelope. Companion to `tests/test_crt_construction_trace.py` (which pins
the v1 join: engine label vs ontology label). This file pins the three things the v1 -> v2
widening can get wrong:

  1. a DROPPED TRANSITION — a bar can take more than one, and a scalar field would hide it
     (the F-056/F-079/F-083/F-085 silent-gap class);
  2. a HALF-POPULATED ROW SHAPE — warmup and live rows must carry the same columns, or a
     reader has to branch on `phase` to parse a record;
  3. a RIVAL STATE LABEL — the envelope's whole premise is that the resolver contributes
     `F_t | S_t` and never a competing `S_t`. If a `resolver.crt_state` ever appears, one
     trace row can contradict itself and the join stops being a join.

Decision-neutrality of the emitter as a whole is NOT proven here: the real instrument is the
3-arm A/B/C run in `scripts/research/emit_dual_construction_trace.py` (config OFF vs ON over a
real corpus). Neutrality of `resolve_metadata()` specifically is proven in
`tests/test_resolver_metadata.py::test_behavior_neutral`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from runtime.crt_construction_trace import (  # noqa: E402
    TRACE_SCHEMA_VERSION,
    ConstructionTraceConfig,
    ConstructionTraceEmitter,
)

_ONTOLOGY = "configs/formulas/market_crt_states.yaml"

#: Every column SCHEMA v2.0.0 adds. Asserted on BOTH row phases.
V2_COLUMNS = (
    "agree_scope", "engine.crt_state", "engine.transitions", "engine.live_context",
    "resolver.feature_vector", "resolver.l2_map", "resolver.predicate_affinity",
    "resolver.continuous_passed", "resolver.projected_site", "resolver.supply_ok",
    "resolver.missing_when", "producer_id",
)


class _FakeResolver:
    """Stand-in so row shape is testable without a full 13-key canonical feature dict.

    Mirrors the seam used by the v1 test file. `resolve_metadata` is deliberately absent on
    the base class so the "resolver cannot produce an envelope" path is reachable.
    """

    def __init__(self, fixed_state: str = "RANGE") -> None:
        self.fixed_state = fixed_state

    def resolve(self, features, timestamp=None, *, htf_id=None, **kwargs):
        return self.fixed_state


def _cfg(tmp_path, *, record_resolver_engine: bool) -> ConstructionTraceConfig:
    return ConstructionTraceConfig(
        enabled=True, schema_version=TRACE_SCHEMA_VERSION, output_dir=str(tmp_path),
        filename_suffix="_x.jsonl", flush_every=500, ontology_source=_ONTOLOGY,
        record_engine_gates=False, emit_on_warmup_bars=True,
        record_resolver_engine=record_resolver_engine,
    )


def _emitter(cfg: ConstructionTraceConfig) -> ConstructionTraceEmitter:
    return ConstructionTraceEmitter(
        cfg, run_id="test_run", instrument="XAUUSD", timeframe="M15",
        corpus_path="data/mt5/XAUUSD_M15.csv", corpus_hash="deadbeef",
        config_version="v4_dual_construction_2026_09", config_hash="feedface",
        ontology_version=1,
    )


def _fake_emitter(tmp_path, *, record_resolver_engine=True, fixed_state="RANGE"):
    em = _emitter(_cfg(tmp_path, record_resolver_engine=record_resolver_engine))
    em._resolver = _FakeResolver(fixed_state)  # test seam
    return em


def _last_row(em: ConstructionTraceEmitter) -> dict:
    em.flush()
    return json.loads(em.path.read_text(encoding="utf-8").strip().splitlines()[-1])


def _emit(em, **over):
    kwargs = dict(
        bar_index=0, timestamp=None, htf_id="H1",
        engine_state_before="RANGE", engine_state_after="RANGE",
        engine_action="NONE", engine_reason=None,
        feature_dict={"x": 1.0}, gate_hooks=None,
    )
    kwargs.update(over)
    em.emit(**kwargs)


# ── row shape ─────────────────────────────────────────────────────────────────────────────
def test_schema_version_is_v2():
    assert TRACE_SCHEMA_VERSION == "2.0.0"


def test_v2_columns_present_on_live_row(tmp_path):
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    _emit(em, engine_state_after="SWEEP")
    row = _last_row(em)
    for col in V2_COLUMNS:
        assert col in row, f"v2 column missing on live row: {col}"
    assert row["engine.crt_state"] == "SWEEP"
    assert row["producer_id"] == "resolver_engine_v1"
    assert row["agree_scope"] == "m15_ontology_injection_none"


def test_v2_columns_present_on_warmup_row(tmp_path):
    em = _fake_emitter(tmp_path)
    em.emit_warmup(0, None)
    row = _last_row(em)
    for col in V2_COLUMNS:
        assert col in row, f"v2 column missing on warmup row: {col}"


def test_legacy_lineage_columns_are_retained(tmp_path):
    """v2 WIDENS the row; it does not replace v1's answer."""
    em = _fake_emitter(tmp_path, record_resolver_engine=False, fixed_state="SWEEP")
    _emit(em)
    row = _last_row(em)
    assert row["ontology_state"] == "SWEEP"
    assert row["agree"] is False
    assert row["divergence_pair"] == "ENGINE:RANGE|ONTO:SWEEP"


def test_envelope_carries_no_rival_state_label(tmp_path):
    """The invariant that lets one row hold both constructions without contradicting itself."""
    em = _fake_emitter(tmp_path)
    _emit(em, engine_state_after="SWEEP")
    row = _last_row(em)
    assert "resolver.crt_state" not in row
    assert not any(k.startswith("resolver.") and k.endswith(".state") for k in row)


# ── transitions: the dropped-hop class ────────────────────────────────────────────────────
def test_transitions_keep_every_hop_of_a_multi_transition_bar(tmp_path):
    """`try_shadow_resume` (crt_engine_v2.py:1094-1105) fires SWEEP then EXPANSION in ONE
    `process_candle`. A "last transition" scalar would record only EXPANSION and silently lose
    the founding SWEEP."""
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    hops = [
        {"from": "RANGE", "to": "SWEEP", "reason": "Shadow: prior-window displacement restored"},
        {"from": "SWEEP", "to": "EXPANSION", "reason": "Shadow resume: displacement carried"},
    ]
    _emit(em, engine_state_after="EXPANSION", transitions=hops)
    row = _last_row(em)
    assert row["engine.transitions"] == hops
    assert [h["to"] for h in row["engine.transitions"]] == ["SWEEP", "EXPANSION"]


def test_round_trip_transitions_are_visible_even_when_state_is_unchanged(tmp_path):
    """RANGE -> SWEEP -> RANGE ends where it began. A `before != after` guard would report
    "no transition"; the log slice reports both hops."""
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    hops = [
        {"from": "RANGE", "to": "SWEEP", "reason": "Sweep @ 2000.00000 idx=7"},
        {"from": "SWEEP", "to": "RANGE", "reason": "age=9 exceeded max_sweep_age_candles=8"},
    ]
    _emit(em, engine_state_before="RANGE", engine_state_after="RANGE", transitions=hops)
    row = _last_row(em)
    assert len(row["engine.transitions"]) == 2


def test_empty_and_absent_transitions_are_different_facts(tmp_path):
    """`[]` = the bar took none. `None` = the caller supplied no capture at all."""
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    _emit(em, transitions=[])
    assert _last_row(em)["engine.transitions"] == []
    _emit(em, bar_index=1)
    assert _last_row(em)["engine.transitions"] is None


def test_transition_reasons_are_free_text_not_an_enum(tmp_path):
    """Engine reasons embed live prices/indices (`f"Sweep @ {price:.5f} idx={i}"`), so they
    are recorded verbatim and must never be pinned to a literal vocabulary."""
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    hops = [{"from": "RANGE", "to": "SWEEP", "reason": "Sweep @ 2001.53000 idx=42"}]
    _emit(em, engine_state_after="SWEEP", transitions=hops)
    reason = _last_row(em)["engine.transitions"][0]["reason"]
    assert isinstance(reason, str) and reason


# ── live context ──────────────────────────────────────────────────────────────────────────
def test_live_context_passed_through(tmp_path):
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    live = {"live_atr": 2.0, "live_ema_fast": 2000.1, "risk_score_final": None}
    _emit(em, engine_live=live)
    assert _last_row(em)["engine.live_context"] == live


def test_live_context_absent_is_none(tmp_path):
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    _emit(em)
    assert _last_row(em)["engine.live_context"] is None


# ── resolver envelope ─────────────────────────────────────────────────────────────────────
def test_resolver_envelope_is_none_when_switch_is_off(tmp_path):
    em = _fake_emitter(tmp_path, record_resolver_engine=False)
    _emit(em)
    row = _last_row(em)
    for col in ("resolver.l2_map", "resolver.predicate_affinity",
                "resolver.continuous_passed", "resolver.projected_site",
                "resolver.feature_vector", "resolver.supply_ok", "resolver.missing_when"):
        assert row[col] is None


def test_resolver_envelope_populated_against_the_real_resolver(tmp_path):
    """End-to-end with the REAL resolver: a fully-supplied bar yields the full 19-key L2 map."""
    from features.crt_state_resolver import CRTStateResolver
    from features.feature_schema import CANONICAL_FEATURES
    from features.feature_states import FeatureStateEncoder

    enc = FeatureStateEncoder()
    feat = {name: 0.2 for name in CANONICAL_FEATURES}
    feat.update({"close": 2000.0, "open": 1999.5, "high": 2002.0, "low": 1998.0, "atr": 0.001})
    for name in set(enc.stateful_features) - {s.name for s in enc._vector_bound}:
        feat[name] = 0.3

    em = _emitter(_cfg(tmp_path, record_resolver_engine=True))
    assert isinstance(em._resolver, CRTStateResolver)
    _emit(em, feature_dict=feat)

    row = _last_row(em)
    assert len(row["resolver.l2_map"]) == 19
    assert row["resolver.supply_ok"] is True
    assert row["resolver.missing_when"] == []
    assert isinstance(row["resolver.predicate_affinity"], dict)
    assert isinstance(row["resolver.continuous_passed"], dict)
    assert set(CANONICAL_FEATURES).issubset(row["resolver.feature_vector"])


def test_resolver_metadata_failure_degrades_without_killing_the_row(tmp_path):
    """Same sidecar discipline as the existing `resolve()` degradation path: an envelope
    failure records an absent envelope, it does not take the backtest down."""
    em = _fake_emitter(tmp_path)

    class _Boom(_FakeResolver):
        def resolve_metadata(self, *a, **k):
            raise RuntimeError("schema drift")

    em._resolver = _Boom("RANGE")
    _emit(em)
    row = _last_row(em)
    assert row["resolver.l2_map"] is None
    assert row["ontology_state"] == "RANGE"  # the v1 join still succeeded


def test_no_features_means_no_envelope(tmp_path):
    em = _emitter(_cfg(tmp_path, record_resolver_engine=True))
    _emit(em, feature_dict=None)
    row = _last_row(em)
    assert row["resolver.l2_map"] is None
    assert row["ontology_state"] is None
    assert row["divergence_pair"] == "ENGINE:RANGE|ONTO:NO_FEATURES"

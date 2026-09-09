"""CRTConstructionTrace (v4, CH-v4-dual-construction-crt-trace-2026-08-30): config gating,
the engine<->ontology comparison logic, and the RISK 1 injection guard.

The empirical neutrality proof is the isolated-root A/B harness (mirrors
`scripts/analysis/v3_config_parity.py`'s method): `crt_construction_trace.enabled` OFF vs ON
produces a byte-identical `events.jsonl`/`crt_telemetry.jsonl` on both the full 47,275-bar
XAUUSD corpus and the 2,116-bar out-of-sample window (2026-07-07 to 2026-08-06) -- run manually
via `utils.isolated_config_root.build_config_root`/`run_backtest`, same pattern the sibling
`bar_structure_snapshot` uses. These are the fast structural floors that keep the claim honest
between runs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from runtime.crt_construction_trace import (  # noqa: E402
    ONTOLOGY_M15_STATES,
    TRACE_SCHEMA_VERSION,
    ConstructionTraceConfig,
    ConstructionTraceEmitter,
    _state_name,
)


# ── _state_name ──────────────────────────────────────────────────────────────────────────

class _FakeEnum:
    def __init__(self, name: str) -> None:
        self.name = name


def test_state_name_accepts_enum_and_str_identically():
    assert _state_name(_FakeEnum("RANGE")) == "RANGE"
    assert _state_name("RANGE") == "RANGE"
    assert _state_name(None) is None


# ── ONTOLOGY_M15_STATES matches the real declared vocabulary ───────────────────────────────

def test_ontology_m15_states_matches_yaml():
    """Frozen locally rather than read at import time (module docstring) -- pin it against the
    real file so schema drift there is loud, not silent."""
    import yaml

    with open("configs/formulas/market_crt_states.yaml", encoding="utf-8") as fh:
        declared = yaml.safe_load(fh)
    names = {s["name"] for s in declared["states"]}
    assert names == ONTOLOGY_M15_STATES


# ── ConstructionTraceConfig.from_prod_config gating ─────────────────────────────────────────

def _section(overrides: Optional[dict] = None) -> dict:
    base = {
        "enabled": True,
        "schema_version": TRACE_SCHEMA_VERSION,
        "output_dir": "logs/crt_construction",
        "filename_suffix": "_crt_construction.jsonl",
        "flush_every": 500,
        "ontology_source": "configs/formulas/market_crt_states.yaml",
        "injection": "none",
        "record_engine_gates": True,
        "emit_on_warmup_bars": True,
        "record_resolver_engine": False,
    }
    if overrides:
        base.update(overrides)
    return base


def test_from_prod_config_none_when_section_absent(monkeypatch):
    import config_layer.production_config as pc

    def _raise(*a, **k):
        raise RuntimeError("no such section")

    monkeypatch.setattr(pc, "get_prod_section", _raise)
    assert ConstructionTraceConfig.from_prod_config() is None


def test_from_prod_config_none_when_disabled(monkeypatch):
    import config_layer.production_config as pc

    monkeypatch.setattr(pc, "get_prod_section", lambda *a, **k: _section({"enabled": False}))
    assert ConstructionTraceConfig.from_prod_config() is None


def test_from_prod_config_raises_on_non_none_injection(monkeypatch):
    """RISK 1 (module docstring): injection is hard-pinned. A config authoring a different
    value must fail loudly at load, not be silently honoured or silently ignored."""
    import config_layer.production_config as pc

    monkeypatch.setattr(
        pc, "get_prod_section", lambda *a, **k: _section({"injection": "full"})
    )
    with pytest.raises(ValueError, match="injection"):
        ConstructionTraceConfig.from_prod_config()


def test_from_prod_config_raises_on_schema_mismatch(monkeypatch):
    import config_layer.production_config as pc

    monkeypatch.setattr(
        pc, "get_prod_section", lambda *a, **k: _section({"schema_version": "9.9.9"})
    )
    with pytest.raises(ValueError, match="schema_version"):
        ConstructionTraceConfig.from_prod_config()


def test_from_prod_config_builds_when_valid(monkeypatch):
    import config_layer.production_config as pc

    monkeypatch.setattr(pc, "get_prod_section", lambda *a, **k: _section())
    cfg = ConstructionTraceConfig.from_prod_config()
    assert cfg is not None
    assert cfg.enabled is True
    assert cfg.record_engine_gates is True


# ── Emitter: disabled is a true no-op ───────────────────────────────────────────────────────

def _disabled_cfg() -> ConstructionTraceConfig:
    return ConstructionTraceConfig(
        enabled=False, schema_version=TRACE_SCHEMA_VERSION, output_dir="unused",
        filename_suffix="_x.jsonl", flush_every=500,
        ontology_source="configs/formulas/market_crt_states.yaml",
        record_engine_gates=True, emit_on_warmup_bars=True,
        record_resolver_engine=False,
    )


def _make_emitter(cfg: ConstructionTraceConfig) -> ConstructionTraceEmitter:
    return ConstructionTraceEmitter(
        cfg, run_id="test_run", instrument="XAUUSD", timeframe="M15",
        corpus_path="data/mt5/XAUUSD_M15.csv", corpus_hash="deadbeef",
        config_version="v4_dual_construction_2026_09", config_hash="feedface",
        ontology_version=1,
    )


def test_disabled_emit_writes_nothing(tmp_path):
    cfg = ConstructionTraceConfig(
        enabled=False, schema_version=TRACE_SCHEMA_VERSION, output_dir=str(tmp_path / "out"),
        filename_suffix="_x.jsonl", flush_every=500,
        ontology_source="configs/formulas/market_crt_states.yaml",
        record_engine_gates=True, emit_on_warmup_bars=True,
        record_resolver_engine=False,
    )
    em = _make_emitter(cfg)
    em.emit_warmup(0, None)
    em.emit(
        bar_index=1, timestamp=None, htf_id=None,
        engine_state_before="RANGE", engine_state_after="SWEEP",
        engine_action="SWEEP_DETECTED", engine_reason=None,
        feature_dict=None, gate_hooks=None,
    )
    assert em.rows_written == 0
    assert not em.path.exists()


# ── The comparison / divergence logic (the actual JOIN this module exists for) ─────────────

class _FakeResolver:
    """Stands in for CRTStateResolver so the comparison logic is testable without a full,
    valid 13-key feature dict. Also the vehicle for RISK 1: it records every kwarg it was
    called with, so injection-leak is a mechanical check, not a read-the-diff exercise."""

    def __init__(self, fixed_state: str) -> None:
        self.fixed_state = fixed_state
        self.calls: list[dict] = []

    def resolve(self, features, timestamp=None, *, htf_id=None, **kwargs):
        self.calls.append({"timestamp": timestamp, "htf_id": htf_id, **kwargs})
        return self.fixed_state


def _emitter_with_fake_resolver(fixed_state: str, tmp_path):
    cfg = ConstructionTraceConfig(
        enabled=True, schema_version=TRACE_SCHEMA_VERSION, output_dir=str(tmp_path),
        filename_suffix="_x.jsonl", flush_every=500,
        ontology_source="configs/formulas/market_crt_states.yaml",
        record_engine_gates=False, emit_on_warmup_bars=True,
        record_resolver_engine=False,
    )
    em = _make_emitter(cfg)
    fake = _FakeResolver(fixed_state)
    em._resolver = fake  # test seam -- the only intentional private-attribute touch
    return em, fake


def _last_row(em: ConstructionTraceEmitter) -> dict:
    em.flush()
    lines = em.path.read_text(encoding="utf-8").strip().splitlines()
    import json

    return json.loads(lines[-1])


def test_agree_true_when_states_match(tmp_path):
    em, fake = _emitter_with_fake_resolver("RANGE", tmp_path)
    em.emit(
        bar_index=0, timestamp=None, htf_id="H1",
        engine_state_before="RANGE", engine_state_after="RANGE",
        engine_action="NONE", engine_reason=None,
        feature_dict={"x": 1.0}, gate_hooks=None,
    )
    row = _last_row(em)
    assert row["agree"] is True
    assert row["divergence_pair"] is None
    assert em.agreement_rate == 1.0


def test_disagree_when_states_differ(tmp_path):
    em, fake = _emitter_with_fake_resolver("SWEEP", tmp_path)
    em.emit(
        bar_index=0, timestamp=None, htf_id="H1",
        engine_state_before="RANGE", engine_state_after="RANGE",
        engine_action="NONE", engine_reason=None,
        feature_dict={"x": 1.0}, gate_hooks=None,
    )
    row = _last_row(em)
    assert row["agree"] is False
    assert row["divergence_pair"] == "ENGINE:RANGE|ONTO:SWEEP"
    assert em.agreement_rate == 0.0


def test_out_of_scope_when_engine_state_not_in_ontology_vocabulary(tmp_path):
    """RISK 3: RANGE_C1 etc. (F-075 parent-CRT states) are not comparable -- must record
    OUT_OF_SCOPE and must NOT count toward agreement_rate (neither as a hit nor a miss)."""
    em, fake = _emitter_with_fake_resolver("RANGE", tmp_path)
    em.emit(
        bar_index=0, timestamp=None, htf_id="H1",
        engine_state_before="RANGE_C1", engine_state_after="RANGE_C1",
        engine_action="NONE", engine_reason=None,
        feature_dict={"x": 1.0}, gate_hooks=None,
    )
    row = _last_row(em)
    assert row["agree"] is None
    assert "OUT_OF_SCOPE" in row["divergence_pair"]
    assert em.agreement_rate is None  # nothing comparable was ever recorded


def test_no_features_recorded_not_silently_skipped(tmp_path):
    em, fake = _emitter_with_fake_resolver("RANGE", tmp_path)
    em.emit(
        bar_index=0, timestamp=None, htf_id="H1",
        engine_state_before="RANGE", engine_state_after="RANGE",
        engine_action="NONE", engine_reason=None,
        feature_dict=None, gate_hooks=None,
    )
    row = _last_row(em)
    assert row["ontology_state"] is None
    assert row["agree"] is None
    assert "NO_FEATURES" in row["divergence_pair"]
    assert fake.calls == []  # resolver never called on a feature-miss bar


def test_resolver_exception_degrades_gracefully_not_a_crash(tmp_path):
    """The backtest must never die because of this observation sidecar."""
    em, fake = _emitter_with_fake_resolver("RANGE", tmp_path)

    def _boom(*a, **k):
        raise RuntimeError("simulated resolver failure")

    fake.resolve = _boom
    em.emit(
        bar_index=0, timestamp=None, htf_id="H1",
        engine_state_before="RANGE", engine_state_after="RANGE",
        engine_action="NONE", engine_reason=None,
        feature_dict={"x": 1.0}, gate_hooks=None,
    )
    row = _last_row(em)
    assert row["ontology_state"] is None
    assert "RESOLVER_ERROR" in row["divergence_pair"]


def test_injection_kwargs_never_passed_to_resolve(tmp_path):
    """RISK 1, the mechanical form: the resolver's `resolve()` call is inspected directly for
    the two research-shadow injection kwargs. Neither may EVER appear, on any bar, under any
    engine action -- that is the entire difference between this module's agreement figure and
    F-069's discredited 64-99% injected one."""
    em, fake = _emitter_with_fake_resolver("RANGE", tmp_path)
    for action, reason in [("RESET", "HTF changed"), ("FILTER_REJECTED", "off_session"), ("NONE", None)]:
        em.emit(
            bar_index=0, timestamp=None, htf_id="H1",
            engine_state_before="RANGE", engine_state_after="EXPANSION",
            engine_action=action, engine_reason=reason,
            feature_dict={"x": 1.0}, gate_hooks=None,
        )
    assert len(fake.calls) == 3
    for call in fake.calls:
        assert "engine_state_to" not in call
        assert "engine_reset" not in call


def test_engine_gates_none_when_hooks_absent(tmp_path):
    em, fake = _emitter_with_fake_resolver("RANGE", tmp_path)
    em.emit(
        bar_index=0, timestamp=None, htf_id="H1",
        engine_state_before="RANGE", engine_state_after="RANGE",
        engine_action="NONE", engine_reason=None,
        feature_dict={"x": 1.0}, gate_hooks=None,
    )
    row = _last_row(em)
    assert row["engine_gates"] is None

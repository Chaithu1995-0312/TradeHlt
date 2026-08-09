"""Floor: model_runners adapter layer — catalog integrity, strictness, contract rules.

Covers the 2026-07-28 adapter-layer work:
  * A1-A3  new dual-engine adapters (regime / trap / breakout)
  * A4     decision adapter (Stage-4 approval)
  * A5     execution_plan registered BLOCKED_BY_DESIGN
  * A6/A7  code provenance + error-rate gate
  * R6     "no invented composite score" promoted from comment to enforced rule
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
from research.model_runners.adapters import build_adapter  # noqa: E402
from research.model_runners.contracts import (  # noqa: E402
    MODEL_CATALOG,
    get_contract,
    list_runnable,
)
from research.model_runners.envelope import collect_code_provenance  # noqa: E402
from research.model_runners.substrate import BarContext  # noqa: E402

CONFIG_PATH = ROOT / "configs" / "production" / "v2_multi_2026_04.json"

# Adapters that need a --artifact or sequential candles are constructed elsewhere.
_SIMPLE_FEATURE_ADAPTERS = ("regime", "trap", "breakout")


@pytest.fixture(scope="module")
def prod_config() -> dict:
    assert CONFIG_PATH.is_file(), f"missing {CONFIG_PATH}"
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _features(**overrides: float) -> dict[str, float]:
    feats = {name: 0.5 for name in CANONICAL_FEATURES}
    feats.update(overrides)
    return feats


def _bar(features: dict[str, float]) -> BarContext:
    return BarContext(
        bar_index=0,
        timestamp="2026-01-01T00:00:00",
        ohlcv={
            "open": 1.0,
            "high": 2.0,
            "low": 0.5,
            "close": 1.5,
            "volume": 10.0,
        },
        features=features,
    )


# ── catalog integrity ────────────────────────────────────────────────────────

def test_every_runnable_model_has_an_adapter_branch(prod_config):
    """A runnable catalog entry with no build_adapter branch is a trap."""
    needs_artifact = {"tradenet", "rr_trained", "envelope", "gaussian_ml"}
    needs_candles = {"crt_state_machine"}
    for contract in list_runnable():
        mid = contract.model_id
        if mid in needs_artifact or mid in needs_candles:
            continue
        adapter = build_adapter(
            mid,
            prod_config=prod_config,
            instrument="XAUUSD",
            repo_root=ROOT,
        )
        assert hasattr(adapter, "score_bar"), mid
        assert adapter.contract.model_id == mid


def test_new_stage1_and_stage4_ids_are_registered():
    for mid in ("regime", "trap", "breakout", "decision"):
        c = get_contract(mid)
        assert c.runnable is True
        assert c.spine_active is True


def test_execution_plan_registration_was_retracted_and_built():
    """A5 RETRACTION (2026-07-29).

    This previously asserted BLOCKED_BY_DESIGN. That classification was wrong: it
    described `ExecutionPlanner.plan()` in isolation and presented the component
    as the pipeline. `live_engine_hook.process()` composes plan() ->
    compute_crt_levels -> geometric RR -> position sizing, and that chain DOES
    produce a complete executable trade. The adapter now mirrors it.
    See tests/test_model_runners_execution_plan.py for the behavioural floor.
    """
    c = get_contract("execution_plan")
    assert c.runnable is True
    assert c.audit_status != "BLOCKED_BY_DESIGN"
    assert c.input_mode == "compose"


def test_blocked_models_refuse_to_build(prod_config):
    for mid in ("llm_gate", "strategies", "engine_runner"):
        with pytest.raises(RuntimeError, match="not runnable"):
            build_adapter(
                mid,
                prod_config=prod_config,
                instrument="XAUUSD",
                repo_root=ROOT,
            )


# ── strictness: adapters must not inherit the engines' silent 0.0 defaults ───

@pytest.mark.parametrize("model_id", _SIMPLE_FEATURE_ADAPTERS)
def test_dual_adapters_require_features_strictly(prod_config, model_id):
    """The wrapped engines use .get(...)->0.0; the adapters must not."""
    adapter = build_adapter(
        model_id, prod_config=prod_config, instrument="XAUUSD", repo_root=ROOT
    )
    required = adapter.FEATURE_KEYS
    assert required, model_id
    for key in required:
        feats = _features()
        del feats[key]
        with pytest.raises(KeyError):
            adapter.score_bar(_bar(feats))


@pytest.mark.parametrize("model_id", _SIMPLE_FEATURE_ADAPTERS)
def test_dual_adapters_fail_fast_on_missing_config(model_id):
    """A missing dual_engine threshold must raise at construction, not per bar."""
    broken = {"engine_runner": {"dual_engine": {}}}
    with pytest.raises(KeyError, match="engine_runner.dual_engine"):
        build_adapter(
            model_id, prod_config=broken, instrument="XAUUSD", repo_root=ROOT
        )


# ── R6 contract rule: no invented composite score ────────────────────────────

def test_regime_emits_a_label_not_an_invented_score(prod_config):
    adapter = build_adapter(
        "regime", prod_config=prod_config, instrument="XAUUSD", repo_root=ROOT
    )
    out = adapter.score_bar(_bar(_features()))
    assert "regime" in out
    assert out["regime"] in {"trend", "range", "neutral"}
    # A label is not a score — synthesising one would be an invented quantity.
    assert "score" not in out


def test_envelope_adapter_source_does_not_synthesise_a_composite():
    """EnvelopeNet has four heads and no composite head — none may be invented."""
    src = (
        SRC / "research" / "model_runners" / "adapters" / "envelope_net.py"
    ).read_text(encoding="utf-8")
    assert 'out["score"]' not in src
    assert "CONTRACT RULE" in src


def test_trap_and_breakout_pass_through_engine_fields(prod_config):
    for mid in ("trap", "breakout"):
        adapter = build_adapter(
            mid, prod_config=prod_config, instrument="XAUUSD", repo_root=ROOT
        )
        out = adapter.score_bar(_bar(_features(sweep_detected=1.0, disp_strength=0.4)))
        assert out["engine"] == mid
        assert "score" in out and isinstance(out["score"], float)
        assert "direction" in out
        # nested meta is flattened, never dropped
        assert any(k.startswith("meta_") for k in out)


# ── A7 error-rate gate config ────────────────────────────────────────────────

def test_model_runners_config_section_is_strict_and_present(prod_config):
    mr = prod_config["model_runners"]
    assert mr["authority"] == "research_only"
    assert 0.0 <= float(mr["max_error_rate"]) <= 1.0
    assert isinstance(mr["emit_vectors"], bool)
    assert int(mr["crt_state_machine"]["seed_bars"]) >= 1


def test_runner_requires_model_runners_section():
    """Removing the section must fail the run, not silently default."""
    from research.model_runners.require_config import require_section

    with pytest.raises(KeyError, match="model_runners"):
        require_section({"engine_runner": {}}, "model_runners")


# ── A6 provenance ────────────────────────────────────────────────────────────

def test_code_provenance_reports_shape_and_never_raises():
    prov = collect_code_provenance(ROOT)
    assert isinstance(prov, dict)
    assert "available" in prov
    if prov["available"]:
        assert len(prov["git_sha"]) == 40
        assert isinstance(prov["dirty"], bool)
        assert isinstance(prov["untracked_count"], int)


def test_code_provenance_records_failure_instead_of_omitting(tmp_path):
    """A non-repo path must yield available=False + an error, not a bare {}."""
    prov = collect_code_provenance(tmp_path)
    assert prov["available"] is False
    assert "error" in prov


def test_manifest_carries_code_provenance_field():
    from dataclasses import fields

    from research.model_runners.envelope import RunManifest

    assert "code_provenance" in {f.name for f in fields(RunManifest)}

"""EPIC-84 STORY-84.1: every config_layer default removed has a missing-key test.

Module-level reads are exercised by loading a FRESH copy of the module (a private name, never
put in ``sys.modules``) while ``get_prod_section`` returns the active section minus one key.
"""
from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from config_layer import production_config as pc  # noqa: E402
from config_layer.strict_config import ConfigKeyMissingError  # noqa: E402


def _load_fresh(rel: str, monkeypatch, section: str, drop: tuple[str, ...] = (),
                sub: str | None = None):
    """Import ``src/<rel>`` privately with ``section`` missing the key path ``drop``."""
    real = pc.get_prod_section

    def _patched(name, *a, **kw):
        sec = copy.deepcopy(real(name, *a, **kw))
        if name == section and drop:
            target = sec[sub] if sub else sec
            for k in drop:
                target.pop(k)
        return sec

    monkeypatch.setattr(pc, "get_prod_section", _patched)
    path = _SRC / rel
    spec = importlib.util.spec_from_file_location(f"_m841_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.mark.parametrize("key", [
    "retest_mu", "retest_s2", "body_mu", "body_s2", "disp_mu", "disp_s2",
    "sigmoid_k", "sigmoid_x0", "execute_p", "decay_lambda",
])
def test_gaussian_scorer_key_required(monkeypatch, key):
    def _go():
        mod = _load_fresh("config_layer/crt_gaussian_scorer.py", monkeypatch,
                          "gaussian_scorer", (key,))
        mod.CRTGaussianScorer()  # decay_lambda is read at construction
    with pytest.raises(ConfigKeyMissingError, match=key):
        _go()


@pytest.mark.parametrize("key", [
    "chat_max_tokens", "chat_temperature", "chat_stop_sequences",
    "groq_fallback_enabled", "groq_model", "groq_score_max_tokens",
    "groq_score_temperature", "audit_log_path",
])
def test_llama_gate_key_required(monkeypatch, key):
    with pytest.raises(ConfigKeyMissingError, match=key):
        _load_fresh("config_layer/llm_inference_client.py", monkeypatch, "llama_gate", (key,))


@pytest.mark.parametrize("key", ["ridge_alpha", "gnb_var_smoothing"])
def test_rr_model_trainer_key_required(monkeypatch, key):
    mod = _load_fresh("config_layer/rr/rr_pattern_miner.py", monkeypatch, "rr_model")
    monkeypatch.setattr(mod, "_RR_CFG", {k: v for k, v in mod._RR_CFG.items() if k != key})
    with pytest.raises(ConfigKeyMissingError, match=key):
        mod.RRPatternTrainer()


def test_rr_model_confidence_gate_subsection_required(monkeypatch):
    with pytest.raises(ConfigKeyMissingError, match="confidence_gate"):
        _load_fresh("config_layer/rr/rr_pattern_miner.py", monkeypatch, "rr_model",
                    ("confidence_gate",))


@pytest.mark.parametrize("key", ["mode", "p_threshold", "dof_scaled_max"])
def test_rr_model_confidence_gate_key_required(monkeypatch, key):
    with pytest.raises(ConfigKeyMissingError, match=key):
        _load_fresh("config_layer/rr/rr_pattern_miner.py", monkeypatch, "rr_model",
                    (key,), sub="confidence_gate")


def test_production_bundle_unreadable_config_raises(monkeypatch):
    from config_layer import production_bundle as pb
    monkeypatch.setattr(pc, "get_full_config_dict", lambda version=None: {})
    with pytest.raises(RuntimeError, match="unreadable or empty"):
        pb.load_production_bundle()

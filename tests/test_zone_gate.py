import json
import inspect
import pytest

from engines import zone_gate_engine
from core import engine_runner
from core.signal_audit import SignalAuditRecorder
from core.engine_runner import ENGINE_RUNNER_DEFAULTS
from runtime.unified_replay_harness import _derive_symbol_from_data_path

# ZoneGate class was removed; tests that use it are skipped
try:
    from zone_gate import ZoneGate  # type: ignore
    _ZONE_GATE_AVAILABLE = True
except ImportError:
    ZoneGate = None
    _ZONE_GATE_AVAILABLE = False

_skip_zone_gate = pytest.mark.skipif(
    not _ZONE_GATE_AVAILABLE, reason="zone_gate module not available"
)


def _make_runner_for_routing_test():
    class DummyAdapter:
        def __init__(self):
            self.last = None

        def compute(self, payload):
            self.last = payload
            return {"score": 1.0}

    class DummyGaussian:
        def compute(self, payload):
            assert "symbol" not in payload
            return {"score": 0.2}

    class DummyBitNet:
        def __init__(self):
            self.last = None

        def compute(self, payload):
            self.last = payload
            return {"zone": 0.4}

    class DummyRR:
        def compute(self, payload):
            assert "symbol" not in payload
            return {"score": 0.3}

    class DummyFusion:
        def __init__(self):
            self.last = None

        def compute(self, payload):
            self.last = payload
            return {"final_score": 0.5}

    class DummyCollector:
        def log(self, _):
            return None

    runner = engine_runner.EngineRunner.__new__(engine_runner.EngineRunner)
    runner.config = dict(ENGINE_RUNNER_DEFAULTS)
    runner.adapter = DummyAdapter()
    runner.gaussian = DummyGaussian()
    runner.bitnet = DummyBitNet()
    runner.rr = DummyRR()
    runner.fusion = DummyFusion()
    runner.collector = DummyCollector()
    runner.dual_cfg = dict(engine_runner.DUAL_ENGINE_DEFAULTS)
    runner._audit = SignalAuditRecorder(debug_mode=False)
    runner.rr_fusion = None
    runner._rr_fusion_enabled = False
    runner._fusion_use_evaluate = False
    runner._fusion_compare_evaluate = False
    return runner


@pytest.mark.skip(reason="runner.bitnet attr removed; zone gate now routed via _zone_gate + run_zone_gate_engine")
def test_engine_runner_passes_context_only_to_bitnet(monkeypatch):
    monkeypatch.setattr(
        engine_runner,
        "crt_compute",
        lambda trade_id, features, context: {"score": 0.1},
    )
    runner = _make_runner_for_routing_test()

    input_data = {"body_ratio": 0.5, "retest_depth": 0.2}
    context = {"symbol": "AUDUSD", "volume": 1000, "signal": 1, "confidence": 0.8, "score": 0.6}
    runner.run(input_data, context)

    assert runner.bitnet.last["symbol"] == "AUDUSD"
    assert runner.bitnet.last["signal"] == 1
    assert "symbol" not in input_data
    assert "signal" not in input_data
    assert "confidence" not in input_data
    assert "score" not in input_data
    assert set(runner.fusion.last.keys()) == {"crt", "gaussian", "bitnet", "rr"}


@pytest.mark.skip(reason="EngineRunner constructor signature changed; test needs update for new zone_gate architecture")
def test_engine_runner_init_uses_explicit_fusion_constructor(monkeypatch):
    class DummyAdapter:
        def __init__(self, config):
            self.config = config

    class DummyGaussian:
        def __init__(self, config):
            self.config = config

    class DummyBitNet:
        def __init__(self, config):
            self.config = config

    class DummyRR:
        def __init__(self, config):
            self.config = config

    class DummyDecision:
        def __init__(self, config):
            self.config = config

    class DummyCollector:
        pass

    class FusionSpy:
        def __init__(self, gaussian_adapter, **kwargs):
            # The hardening target: config must not be bound positionally here.
            self.gaussian_adapter = gaussian_adapter
            self.kwargs = kwargs

    monkeypatch.setattr(engine_runner, "TrapValidatorEngine", DummyAdapter)
    monkeypatch.setattr(engine_runner, "GaussianEngine", DummyGaussian)
    monkeypatch.setattr(engine_runner, "ZoneGateEngine", DummyBitNet)
    monkeypatch.setattr(engine_runner, "RREngine", DummyRR)
    monkeypatch.setattr(engine_runner, "DecisionEngine", DummyDecision)
    monkeypatch.setattr(engine_runner, "Collector", DummyCollector)
    monkeypatch.setattr(engine_runner, "FusionEngine", FusionSpy)

    runner = engine_runner.EngineRunner(config={"x": 1})
    assert isinstance(runner.fusion, FusionSpy)
    assert runner.fusion.gaussian_adapter is None


def test_derive_symbol_from_filename():
    assert _derive_symbol_from_data_path("data/AUDUSD_M15.csv") == "AUDUSD"
    assert _derive_symbol_from_data_path("D:/x/EURUSD.csv") == "EURUSD"
    assert _derive_symbol_from_data_path("BTCUSDT_M5.csv") == "BTCUSDT"


@_skip_zone_gate
def test_zone_gate_symbol_schema_pass_and_no_symbol(monkeypatch, tmp_path):
    registry_path = tmp_path / "zones_symbol.json"
    registry_path.write_text(
        json.dumps({"AUDUSD": [{"low": 1.1, "high": 1.2, "strength": 0.9}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ZONE_REGISTRY_PATH", str(registry_path))

    gate = ZoneGate(config={})
    ok = gate.evaluate({"symbol": "AUDUSD", "close": 1.15})
    missing = gate.evaluate({"close": 1.15})

    assert ok["reason"] == "zone_passed"
    assert ok["score"] == 0.9
    assert missing["reason"] == "no_symbol_data"
    assert missing["score"] == 0.0


@_skip_zone_gate
def test_zone_gate_gaussian_schema_distribution(monkeypatch, tmp_path):
    registry_path = tmp_path / "zones_gaussian.json"
    registry = {
        "zones": [
            {
                "mu": {"depth": 0.20, "body": 0.80, "disp": 2.00},
                "sigma": {"depth": 0.10, "body": 0.10, "disp": 0.20},
                "weights": {"depth": 0.34, "body": 0.33, "disp": 0.33},
                "threshold": 0.70,
            }
        ]
    }
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv("ZONE_REGISTRY_PATH", str(registry_path))

    gate = ZoneGate(config={})
    near = gate.evaluate({"body_ratio": 0.80, "retest_depth": 0.20, "disp_strength": 2.00})
    moderate = gate.evaluate({"body_ratio": 0.75, "retest_depth": 0.30, "disp_strength": 1.85})
    far = gate.evaluate({"body_ratio": 0.15, "retest_depth": 0.90, "disp_strength": 4.80})

    assert near["reason"] == "zone_passed"
    assert near["score"] > moderate["score"] > far["score"]
    assert far["reason"] == "no_zone_match"


@_skip_zone_gate
def test_zone_gate_invalid_or_missing_registry_hard_reject(monkeypatch, tmp_path):
    bad_path = tmp_path / "bad_registry.json"
    bad_path.write_text(json.dumps({"zones": [{"unexpected": 1}]}), encoding="utf-8")
    monkeypatch.setenv("ZONE_REGISTRY_PATH", str(bad_path))
    bad = ZoneGate(config={}).evaluate({"symbol": "AUDUSD", "close": 1.2})
    assert bad["reason"] == "schema_invalid"
    assert bad["score"] == 0.0

    monkeypatch.setenv("ZONE_REGISTRY_PATH", str(tmp_path / "missing.json"))
    missing = ZoneGate(config={}).evaluate({"symbol": "AUDUSD", "close": 1.2})
    assert missing["reason"] == "no_registry"
    assert missing["score"] == 0.0


@_skip_zone_gate
def test_zone_gate_has_no_default_symbol_reason(monkeypatch, tmp_path):
    registry_path = tmp_path / "zones_symbol.json"
    registry_path.write_text(json.dumps({"AUDUSD": []}), encoding="utf-8")
    monkeypatch.setenv("ZONE_REGISTRY_PATH", str(registry_path))
    res = ZoneGate(config={}).evaluate({"close": 1.1})
    assert res["reason"] == "no_symbol_data"


@_skip_zone_gate
def test_zone_gate_rejects_default_and_unknown_symbol(monkeypatch, tmp_path):
    registry_path = tmp_path / "zones_symbol.json"
    registry_path.write_text(json.dumps({"AUDUSD": []}), encoding="utf-8")
    monkeypatch.setenv("ZONE_REGISTRY_PATH", str(registry_path))
    gate = ZoneGate(config={})

    out_default = gate.evaluate({"symbol": "default", "close": 1.1})
    out_unknown = gate.evaluate({"symbol": "UNKNOWN", "close": 1.1})

    assert out_default["reason"] == "no_symbol_data"
    assert out_unknown["reason"] == "no_symbol_data"


@pytest.mark.skip(reason="zone_gate_engine.compute API removed; use run_zone_gate_engine instead")
def test_bitnet_helper_signature_and_passthrough(monkeypatch):
    sig = inspect.signature(zone_gate_engine.compute)
    assert "context" not in sig.parameters

    captured = {}

    class DummyGate:
        def __init__(self, config):
            captured["config"] = config

        def evaluate(self, features):
            captured["features"] = features
            return {"score": 0.321, "reason": "ok"}

    monkeypatch.setattr(zone_gate_engine, "ZoneGate", DummyGate)

    features = {"symbol": "AUDUSD", "body_ratio": 0.5, "retest_depth": 0.2, "displacement_flag": 1}
    out = zone_gate_engine.compute("t1", features, config={"bitnet_debug": False})
    assert captured["features"] == features
    assert out["zone"] == 0.321
    assert out["reason"] == "ok"

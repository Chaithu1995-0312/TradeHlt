from core import engine_runner
from core.signal_audit import SignalAuditRecorder
from core.engine_runner import ENGINE_RUNNER_DEFAULTS


def _make_runner():
    class DummyAdapter:
        def compute(self, payload):
            return {"score": 1.0, "reason": "ok"}

    class DummyGaussian:
        def compute(self, payload):
            return {"score": 0.2}

    class DummyBitNet:
        def compute(self, payload):
            return {"zone": 0.4}

    class DummyRR:
        def compute(self, payload):
            return {"score": 0.3}

    class DummyDecision:
        def evaluate(self, score, p_win, zone_gate, fusion, config):
            return {"decision": "Approved", "confidence": 0.9, "reason": "ok"}

    class DummyFusion:
        def __init__(self):
            self.called = False
            self.last = None

        def compute(self, payload):
            self.called = True
            self.last = payload
            return {"final_score": 0.8}

    class DummyCollector:
        def __init__(self):
            self.records = []

        def log(self, payload):
            self.records.append(payload)

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
    runner.decision = DummyDecision()
    runner.rr_fusion = None
    runner._rr_fusion_enabled = False
    runner._fusion_use_evaluate = False
    runner._fusion_compare_evaluate = False
    from core.acceptance_controller import AcceptanceController
    runner._acceptance = AcceptanceController({})
    from core.convergence_controller import ConvergenceController
    runner._convergence = ConvergenceController(window_size=500)
    return runner


def _stub_zone_gate(**kwargs):
    """Stub for run_zone_gate_engine — returns neutral pass so dual-gate tests
    are not affected by canonical-key validation added in zone_gate_engine.py."""
    return {"score": 0.4, "passed": True, "vector": [], "valid": True}


def test_dual_gate_trend_selects_breakout(monkeypatch):
    monkeypatch.setattr(engine_runner, "crt_compute",
                        lambda trade_id, features, context: {"score": 0.1})
    monkeypatch.setattr(engine_runner, "run_zone_gate_engine", _stub_zone_gate)
    runner = _make_runner()

    input_data = {
        "trend_bias": 1.0,
        "ema_spread": 0.9,
        "momentum_score": 0.8,
        "volatility_ratio": 1.2,
        "sweep_detected": 1.0,
        "disp_strength": 1.0,
    }

    out = runner.run(input_data, {"symbol": "AUDUSD"})
    assert out["decision"] == "Approved"
    assert out["selected_engine"] == "breakout"
    assert out["regime"] == "trend"


def test_dual_gate_range_selects_trap(monkeypatch):
    monkeypatch.setattr(engine_runner, "crt_compute",
                        lambda trade_id, features, context: {"score": 0.1})
    monkeypatch.setattr(engine_runner, "run_zone_gate_engine", _stub_zone_gate)
    runner = _make_runner()

    input_data = {
        "trend_bias": -1.0,
        "ema_spread": 0.05,
        "momentum_score": 0.1,
        "volatility_ratio": 0.5,
        "sweep_detected": 1.0,
        "disp_strength": 0.9,
    }

    out = runner.run(input_data, {"symbol": "AUDUSD"})
    assert out["decision"] == "Approved"
    assert out["selected_engine"] == "trap"
    assert out["regime"] == "range"


def test_dual_gate_neutral_low_confidence_rejects(monkeypatch):
    monkeypatch.setattr(engine_runner, "crt_compute",
                        lambda trade_id, features, context: {"score": 0.1})
    monkeypatch.setattr(engine_runner, "run_zone_gate_engine", _stub_zone_gate)
    runner = _make_runner()

    input_data = {
        "trend_bias": 0.0,
        "ema_spread": 0.02,
        "momentum_score": 0.02,
        "volatility_ratio": 1.1,
        "sweep_detected": 0.0,
        "disp_strength": 0.1,
    }

    out = runner.run(input_data, {"symbol": "AUDUSD"})
    assert out["decision"] == "REJECT"
    assert out["reason"].startswith("ultron_gate:")


def test_layered_flow_fusion_runs_before_dual_veto(monkeypatch):
    monkeypatch.setattr(engine_runner, "crt_compute",
                        lambda trade_id, features, context: {"score": 0.1})
    monkeypatch.setattr(engine_runner, "run_zone_gate_engine", _stub_zone_gate)
    runner = _make_runner()

    input_data = {
        "trend_bias": 0.0,
        "ema_spread": 0.02,
        "momentum_score": 0.02,
        "volatility_ratio": 1.1,
        "sweep_detected": 0.0,
        "disp_strength": 0.1,
    }

    out = runner.run(input_data, {"symbol": "AUDUSD"})
    assert runner.fusion.called is True
    assert set(runner.fusion.last.keys()) == {"crt", "gaussian", "zone_gate", "rr"}
    assert out["decision"] == "REJECT"

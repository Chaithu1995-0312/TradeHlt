from core import engine_runner as er


class _DummyAudit:
    def start_bar(self, *args, **kwargs):
        return None

    def record_zone(self, *args, **kwargs):
        return None

    def record_engines(self, *args, **kwargs):
        return None

    def record_fusion(self, *args, **kwargs):
        return None

    def finalize(self, *args, **kwargs):
        return None

    def flush(self, *args, **kwargs):
        return None


class _DummyAcceptance:
    def get_thresholds(self):
        return {}

    def update_metrics(self, **kwargs):
        return None

    def adjust_thresholds(self):
        return None


class _DummyConvergence:
    def record_outcome(self, *_args, **_kwargs):
        return None


class _DummyCollector:
    def __init__(self):
        self.records = []

    def log(self, payload):
        self.records.append(payload)


class _DummyZoneGate:
    _zones = []

    def check(self, _vector):
        return {"score": 0.6}


class _DummyAdapter:
    def compute(self, _payload):
        return {"score": 1.0, "reason": "ok"}


class _DummyGaussian:
    def compute(self, _payload, **kwargs):
        return {"score": 0.6}


class _DummyRR:
    def compute(self, _payload):
        return {"score": 0.3, "rr_ratio": 1.8, "reason": "base_rr"}


class _DummyFusion:
    def __init__(self, eval_score: float = 0.4):
        self.last = None
        self.eval_score = eval_score
        self.cfg = type(
            "_Cfg",
            (),
            {
                "weight_crt": 0.30,
                "weight_gaussian": 0.25,
                "weight_zone_gate": 0.25,
                "weight_rr": 0.20,
            },
        )()

    def compute(self, payload, *, regime=None, **kwargs):
        self.last = payload
        self.last_regime = regime
        return {"final_score": 0.9}

    def evaluate(self, features, signal, candle_idx=0):
        class _EvalResult:
            def __init__(self, score: float):
                self._score = score

            def to_dict(self):
                return {
                    "final_score": self._score,
                    "gaussian": 0.6,
                    "neural": None,
                    "llm": None,
                    "llm_fired": False,
                    "action": "TRADE",
                    "risk_mult": 0.5,
                }

        return _EvalResult(self.eval_score)


class _DummyDecision:
    def evaluate(self, **_kwargs):
        return {"decision": "execute", "reason": "ok"}


def _build_runner(rr_fusion, fusion_compare=False, fusion_use=False, eval_score=0.4):
    runner = er.EngineRunner.__new__(er.EngineRunner)
    runner.config = {
        **er.ENGINE_RUNNER_DEFAULTS,
        "debug_mode": False,
        "rr_fusion": {"threshold": 0.5},
        "fusion_compare_evaluate": fusion_compare,
        "fusion_use_evaluate": fusion_use,
    }
    runner.adapter = _DummyAdapter()
    runner.gaussian = _DummyGaussian()
    runner.rr = _DummyRR()
    runner.rr_fusion = rr_fusion
    runner._rr_fusion_full_vector = False
    runner.fusion = _DummyFusion(eval_score=eval_score)
    runner.decision = _DummyDecision()
    runner.collector = _DummyCollector()
    runner._zone_gate = _DummyZoneGate()
    runner._audit = _DummyAudit()
    runner._acceptance = _DummyAcceptance()
    runner._convergence = _DummyConvergence()
    runner._fusion_compare_evaluate = fusion_compare
    runner._fusion_use_evaluate = fusion_use
    runner.gaussian_shadow = None
    runner._last_regime = None
    runner._belief_enabled = False
    runner._regime_governor_enabled = False
    from core.regime_governor import RegimeGovernor
    runner._regime_governor = RegimeGovernor()
    runner.dual_cfg = {
        **er.DUAL_ENGINE_DEFAULTS,
        "fusion_min_score": 0.0,
        "trend_strength_threshold": 0.1,
        "momentum_threshold": 0.1,
    }
    return runner


def _input_data():
    return {
        "close": 100.0,
        "high": 101.0,
        "low": 99.0,
        "atr": 0.5,
        "trend_bias": 1.0,
        "ema_spread": 0.3,
        "momentum_score": 0.4,
        "volatility_ratio": 1.2,
        "sweep_detected": 0.0,
        "disp_strength": 0.4,
        "retest_depth": 0.2,
        "body_ratio": 0.6,
        "is_asia": 0.0,
        "is_london": 1.0,
        "is_newyork": 0.0,
        "hour": 10,
    }


def test_rr_fusion_applies_score_before_fusion(monkeypatch):
    class _GoodFusion:
        is_loaded = True

        def score_dict(self, **_kwargs):
            return {"final_score": 0.77, "status": "success"}

    monkeypatch.setattr(er, "crt_compute", lambda trade_id, features, context: {"score": 0.2})
    monkeypatch.setattr(
        er,
        "run_zone_gate_engine",
        lambda **_kwargs: {"score": 0.8, "passed": True},
    )

    runner = _build_runner(_GoodFusion())
    result = runner.run(_input_data(), {"symbol": "AUDUSD"})

    assert result["decision"] == "execute"
    assert runner.fusion.last["rr"]["score"] == 0.77
    assert runner.fusion.last["rr"]["rr_ratio"] == 1.8


def test_rr_fusion_failure_falls_back_to_base_rr(monkeypatch):
    class _BadFusion:
        is_loaded = True

        def score_dict(self, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(er, "crt_compute", lambda trade_id, features, context: {"score": 0.2})
    monkeypatch.setattr(
        er,
        "run_zone_gate_engine",
        lambda **_kwargs: {"score": 0.8, "passed": True},
    )

    runner = _build_runner(_BadFusion())
    result = runner.run(_input_data(), {"symbol": "AUDUSD"})

    assert result["decision"] == "execute"
    assert runner.fusion.last["rr"]["score"] == 0.3
    assert runner.fusion.last["rr"]["rr_ratio"] == 1.8


def test_rr_fusion_disabled_is_base_rr_identity(monkeypatch):
    """F-038: rr_fusion.enabled=false (self.rr_fusion is None) must leave the `rr` engine
    result byte-identical to the base RREngine output — no score mutation, no metadata
    injection (e.g. an `rr_fusion` key), so a disabled layer can never reintroduce the
    Gaussian-duplicate behavior via a partial mutation."""
    monkeypatch.setattr(er, "crt_compute", lambda trade_id, features, context: {"score": 0.2})
    monkeypatch.setattr(
        er,
        "run_zone_gate_engine",
        lambda **_kwargs: {"score": 0.8, "passed": True},
    )

    runner = _build_runner(rr_fusion=None)
    base_rr = runner.rr.compute(_input_data())

    result = runner.run(_input_data(), {"symbol": "AUDUSD"})

    assert result["decision"] == "execute"
    assert runner.rr_fusion is None
    assert runner.fusion.last["rr"] == base_rr
    assert "rr_fusion" not in runner.fusion.last["rr"]


def test_weighted_vote_falls_back_when_fusion_cfg_missing():
    runner = er.EngineRunner.__new__(er.EngineRunner)
    runner.fusion = type("_FusionNoCfg", (), {})()
    vote = runner._compute_weighted_vote(
        {
            "crt": {"score": 0.7},
            "gaussian": {"score": 0.6},
            "zone_gate": {"score": 0.8},
            "rr": {"score": 0.55},
        }
    )
    assert isinstance(vote, float)
    assert vote == vote  # NaN guard
    assert 0.0 <= vote <= 1.0


def test_fusion_compare_mode_records_evaluate_shadow(monkeypatch):
    monkeypatch.setattr(er, "crt_compute", lambda trade_id, features, context: {"score": 0.2})
    monkeypatch.setattr(
        er,
        "run_zone_gate_engine",
        lambda **_kwargs: {"score": 0.8, "passed": True},
    )

    runner = _build_runner(rr_fusion=None, fusion_compare=True, fusion_use=False, eval_score=0.12)
    runner.run(_input_data(), {"symbol": "AUDUSD"})

    fusion_payload = runner.collector.records[-1]["fusion"]
    assert fusion_payload["final_score"] == 0.9
    assert "evaluate_shadow" in fusion_payload
    assert abs(fusion_payload["evaluate_shadow"]["final_score"] - 0.12) < 1e-9


def test_fusion_use_evaluate_overrides_final_score(monkeypatch):
    monkeypatch.setattr(er, "crt_compute", lambda trade_id, features, context: {"score": 0.2})
    monkeypatch.setattr(
        er,
        "run_zone_gate_engine",
        lambda **_kwargs: {"score": 0.8, "passed": True},
    )

    runner = _build_runner(rr_fusion=None, fusion_compare=False, fusion_use=True, eval_score=0.12)
    result = runner.run(_input_data(), {"symbol": "AUDUSD"})

    assert abs(result["final_score"] - 0.12) < 1e-9
    fusion_payload = runner.collector.records[-1]["fusion"]
    assert fusion_payload["evaluate_used"] is True

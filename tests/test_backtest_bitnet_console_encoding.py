import io
import os
import sys

import pandas as pd

from features.feature_schema import CANONICAL_FEATURES
from runtime import backtest_bitnet


class StrictEncodedStream(io.StringIO):
    def __init__(self, encoding: str):
        super().__init__()
        self._encoding = encoding

    @property
    def encoding(self) -> str:
        return self._encoding

    def write(self, s: str) -> int:
        s.encode(self.encoding, errors="strict")
        return super().write(s)


def test_run_backtest_survives_cp1252_stdout(monkeypatch, tmp_path):
    class DummyPipeline:
        def __init__(self, _raw_df):
            pass

        def run(self):
            row = {name: 0.1 for name in CANONICAL_FEATURES}
            return pd.DataFrame([row]), None

    class DummyBitNetRunner:
        def __init__(self, _model_path):
            pass

        def predict(self, _features):
            return {"score": 0.77, "decision": "ACCEPT"}

    class DummyCollector:
        def log(self, _payload):
            return None

    class DummyEngineRunner:
        def __init__(self, _cfg):
            self.collector = DummyCollector()

        def run(self, _features, context=None):
            return {"decision": "EXECUTE", "reason": "ok"}

    raw_df = pd.DataFrame(
        {
            "timestamp": ["2024-01-01 00:00:00"],
            "open": [1.1],
            "high": [1.2],
            "low": [1.0],
            "close": [1.15],
            "volume": [100],
        }
    )

    monkeypatch.setattr(backtest_bitnet.pd, "read_csv", lambda _path: raw_df.copy())
    monkeypatch.setattr(backtest_bitnet, "FeaturePipeline", DummyPipeline)
    monkeypatch.setattr(backtest_bitnet, "BitNetRunner", DummyBitNetRunner)
    monkeypatch.setattr(backtest_bitnet, "EngineRunner", DummyEngineRunner)

    stream = StrictEncodedStream("cp1252")
    monkeypatch.setattr(sys, "stdout", stream)

    monkeypatch.chdir(tmp_path)
    os.makedirs(tmp_path / "logs", exist_ok=True)

    config = {
        "engine_runner": {"model_path": "unused.json"},
        "decision_engine": {},
        "fusion_engine": {},
        "execution_planner": {},
        "ultron_risk_gate": {},
    }

    rows = backtest_bitnet.run_backtest(config, "data/EURUSD_M15.csv", gate_mode="hard_gate", months=None)
    assert len(rows) == 1
    out = stream.getvalue()
    assert "PIPELINE OUTPUT KEYS" in out
    assert "BITNET BACKTEST COMPLETE" in out

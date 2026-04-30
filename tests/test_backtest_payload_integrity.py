import numpy as np
import pandas as pd

from runtime import backtest_v2
from features.feature_schema import CANONICAL_FEATURES


def _make_enriched_row(symbol_value=None):
    row = {name: 0.1 for name in CANONICAL_FEATURES}
    row["close"] = 1.15
    row["volume"] = 0.0
    if symbol_value is not None:
        row["symbol"] = symbol_value
    return row


def _wire_backtest_dummies(monkeypatch, enriched_df):
    class DummyPipeline:
        def __init__(self, _raw_df):
            pass

        def run(self):
            vectors = enriched_df[list(CANONICAL_FEATURES)].astype(np.float32).values
            return enriched_df.copy(), vectors

    class DummyModel:
        def __init__(self, _path):
            pass

        def predict(self, _vector):
            return 0.65

    class DummyRunner:
        last_input = None
        last_context = None

        def __init__(self, _config):
            self.collector = type("Collector", (), {"log": lambda self, payload: None})()

        def run(self, input_data, context):
            DummyRunner.last_input = dict(input_data)
            DummyRunner.last_context = dict(context)
            return {"decision": "Approved", "score": 0.8}

    raw_df = pd.DataFrame(
        {
            "timestamp": ["2024-01-01 00:00:00"],
            "open": [1.1],
            "high": [1.2],
            "low": [1.0],
            "close": [1.15],
            "volume": [0.0],
        }
    )

    monkeypatch.setattr(backtest_v2.pd, "read_csv", lambda _path: raw_df)
    monkeypatch.setattr(backtest_v2, "FeaturePipeline", DummyPipeline)
    monkeypatch.setattr(backtest_v2, "BitNetModel", DummyModel)
    monkeypatch.setattr(backtest_v2, "EngineRunner", DummyRunner)
    return DummyRunner


def test_backtest_keeps_input_canonical_and_routes_runtime_to_context(monkeypatch):
    enriched_df = pd.DataFrame([_make_enriched_row()])
    dummy_runner = _wire_backtest_dummies(monkeypatch, enriched_df)

    out = backtest_v2.run_backtest({"model_path": "unused.json"}, "data/AUDUSD_M15.csv")
    assert len(out) == 1

    assert set(dummy_runner.last_input.keys()) == set(CANONICAL_FEATURES)
    assert "signal" not in dummy_runner.last_input
    assert "confidence" not in dummy_runner.last_input
    assert "score" not in dummy_runner.last_input

    assert dummy_runner.last_context["symbol"] == "AUDUSD"
    assert "signal" in dummy_runner.last_context
    assert "confidence" in dummy_runner.last_context
    assert "score" in dummy_runner.last_context
    assert "volume" in dummy_runner.last_context


def test_backtest_symbol_default_falls_back_to_filename(monkeypatch):
    enriched_df = pd.DataFrame([_make_enriched_row(symbol_value="default")])
    dummy_runner = _wire_backtest_dummies(monkeypatch, enriched_df)

    backtest_v2.run_backtest({"model_path": "unused.json"}, "data/EURUSD_M15.csv")
    assert dummy_runner.last_context["symbol"] == "EURUSD"

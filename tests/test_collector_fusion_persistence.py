import core.collector as collector_mod


def test_collector_log_forwards_fusion_payload(monkeypatch):
    captured = {}

    def _fake_collect(*, trade_id, features, engine_outputs, outcome, context, fusion_output):
        captured["trade_id"] = trade_id
        captured["features"] = features
        captured["engine_outputs"] = engine_outputs
        captured["outcome"] = outcome
        captured["context"] = context
        captured["fusion_output"] = fusion_output

    monkeypatch.setattr(collector_mod, "collect", _fake_collect)

    recorder = collector_mod.Collector()
    recorder.log(
        {
            "features": {"id": "t-1", "body_ratio": 0.5},
            "engines": {"crt": {"score": 0.2}},
            "fusion": {"final_score": 0.9, "evaluate_shadow": {"final_score": 0.4}},
            "decision": "execute",
            "pnl": 0.0,
        }
    )

    assert captured["trade_id"] == "t-1"
    assert captured["engine_outputs"] == {"crt": {"score": 0.2}}
    assert captured["fusion_output"]["final_score"] == 0.9
    assert captured["fusion_output"]["evaluate_shadow"]["final_score"] == 0.4

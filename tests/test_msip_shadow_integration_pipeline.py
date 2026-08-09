"""Integration: FeaturePipeline rows → build_market_state (no CRT mutation)."""

from __future__ import annotations

import pandas as pd

from features.feature_pipeline import FeaturePipeline
from msip.interpretation_config import default_experimental_section, load_msip_shadow_config
from msip.shadow_emitter import ProvenanceContext, build_market_state, stable_json_bytes


def _toy_ohlcv(n: int = 250) -> pd.DataFrame:
    """Synthetic OHLCV with enough path diversity for swing structure columns."""
    rows = []
    price = 2000.0
    base = pd.Timestamp("2024-05-22T01:00:00")
    for i in range(n):
        # alternating impulse / pullback so swing high/low differ
        impulse = 2.5 if (i % 7) < 4 else -1.8
        noise = (i % 5) * 0.15
        o = price
        c = price + impulse + noise * (1 if i % 2 == 0 else -1)
        h = max(o, c) + 0.8 + (i % 3) * 0.1
        l = min(o, c) - 0.7 - (i % 4) * 0.1
        ts = base + pd.Timedelta(minutes=15 * i)
        rows.append(
            {
                "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S"),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": 100 + i,
            }
        )
        price = c
    return pd.DataFrame(rows)


def test_pipeline_to_shadow_emits_vectors():
    df = _toy_ohlcv(250)
    pipeline = FeaturePipeline(df)
    enriched, _ = pipeline.run()
    assert len(enriched) > 0

    cfg = load_msip_shadow_config({"msip_shadow": default_experimental_section()})
    prov = ProvenanceContext(config_id=cfg.config_id, config_sha256=cfg.config_sha256)
    payloads = []
    for i, (_, row) in enumerate(enriched.iterrows()):
        vec = build_market_state(
            row.to_dict(),
            cfg,
            prov,
            symbol="XAUUSD",
            timeframe="M15",
            bar_timestamp=str(row["timestamp"]),
            bar_index=i,
        )
        assert vec is not None
        assert vec.shadow_flags["affects_crt"] is False
        payloads.append(stable_json_bytes(vec))
    assert len(payloads) == len(enriched)
    # deterministic replay of first bar
    row0 = enriched.iloc[0].to_dict()
    again = build_market_state(
        row0, cfg, prov, symbol="XAUUSD", timeframe="M15", bar_timestamp=str(row0["timestamp"]), bar_index=0
    )
    assert stable_json_bytes(again) == payloads[0]

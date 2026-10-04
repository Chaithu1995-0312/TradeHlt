"""Profitable-zone study on the 2-year XAUUSD M15 corpus (same definition as the 10-day page)."""
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(HERE))
from features.feature_pipeline import FeaturePipeline  # noqa: E402
from features.feature_schema import CANONICAL_FEATURES  # noqa: E402
import zone_study as ZS  # noqa: E402

path = ROOT / "data/mt5/XAUUSD_M15.csv"
from data_ingestion.corpus_store import load as _corpus_load  # CH-corpus-ssot: the corpus SSOT
raw = _corpus_load(path).frame(parse_dates=["timestamp"])
print("corpus", path, "rows", len(raw), raw.timestamp.iloc[0], "->", raw.timestamp.iloc[-1], flush=True)
t0 = time.time()
enriched, _ = FeaturePipeline(raw.copy()).run()
print("pipeline rows", len(enriched), "secs", round(time.time() - t0), flush=True)
feats = [f for f in CANONICAL_FEATURES if f not in ("open", "high", "low", "close")]
res = ZS.study(enriched.reset_index(drop=True), feats)
res.pop("labels")
for side in ("long", "short"):
    res[side].pop("zones")
res["corpus"] = {"path": str(path), "rows": len(raw), "first": str(raw.timestamp.iloc[0]), "last": str(raw.timestamp.iloc[-1]),
                 "post_warmup": len(enriched)}
(HERE / "zone_full.json").write_text(json.dumps(res), encoding="utf-8")
for side in ("long", "short"):
    r = res[side]
    print(side, "zones", r["n_zones"], "zone bars", r["zone_bars"], "base", r["base_bars"])
    for p in r["profile"][:12]:
        print(f"  {p['feature']:28s} auc {p['auc']:.3f} h1 {p['auc_h1']:.3f} h2 {p['auc_h2']:.3f} same {p['same_sign']}")
print("win rate", res["win_rate"], "secs", round(time.time() - t0))

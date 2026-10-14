"""Attach the 2-year forward test (zone_edge.json) and the "Right now" read of the latest bar to
xau_10d_features.json. Run after zone_10d.py and zone_edge.py, before render_xau.py.

"Right now" compares the latest bar's feature values with the 2-year zone-start profile
(zones_full, written by zone_full.py / zone_10d.py) and the 2-year feature distribution
(zone_full_enriched.parquet, cached by zone_edge.py). Observation only."""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
FEATS = ["momentum_score", "disp_strength", "body_size", "body_ratio", "volatility_ratio", "candle_range",
         "rsi_14", "macd_hist_z", "volume_ratio", "break_of_structure", "higher_high", "lower_low"]

p = HERE / "xau_10d_features.json"
d = json.loads(p.read_text(encoding="utf-8"))
d["zone_edge"] = json.loads((HERE / "zone_edge.json").read_text(encoding="utf-8"))

F = d["meta"]["features"]
r = d["rows"][-1]
full = pd.read_parquet(HERE / "zone_full_enriched.parquet")
pl = {q["feature"]: q for q in d["zones_full"]["long"]["profile"]}
ps = {q["feature"]: q for q in d["zones_full"]["short"]["profile"]}
d["now"] = {"bar": r[0], "close": r[F.index("close") + 1], "rows": [
    {"f": f, "v": r[F.index(f) + 1], "L": pl[f]["s+0"], "S": ps[f]["s+0"], "base": pl[f]["base"],
     # mid-rank percentile: ties count half, so a 0/1 flag at its common value reads ~mid, not 0
     "pct": float(((full[f] < r[F.index(f) + 1]).mean() + 0.5 * (full[f] == r[F.index(f) + 1]).mean()) * 100),
     "aucL": pl[f]["auc"], "aucS": ps[f]["auc"]}
    for f in FEATS]}
p.write_text(json.dumps(d), encoding="utf-8")
print("attached zone_edge + now; latest bar", r[0])

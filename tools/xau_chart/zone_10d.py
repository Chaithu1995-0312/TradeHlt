"""Add the profitable-zone study (10-day window) and the 2-year check to xau_10d_features.json."""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import zone_study as ZS  # noqa: E402

p = HERE / "xau_10d_features.json"
d = json.loads(p.read_text(encoding="utf-8"))
F = d["meta"]["features"]
df = pd.DataFrame([r[1:] for r in d["rows"]], columns=F, dtype=float)
feats = [f for f in F if f not in ("open", "high", "low", "close")]
res = ZS.study(df, feats)
res["epoch"] = d["epoch"]
d["zones10"] = res
full = HERE / "zone_full.json"
d["zones_full"] = json.loads(full.read_text(encoding="utf-8")) if full.exists() else None
p.write_text(json.dumps(d), encoding="utf-8")
for side in ("long", "short"):
    r = res[side]
    print(side, "zones", r["n_zones"], "bars in zones", r["zone_bars"], "starts h1/h2", r["starts_h1"], r["starts_h2"])
    for q in r["profile"][:8]:
        print(f"  {q['feature']:28s} auc {q['auc']}  same {q['same_sign']}")
print("win rate", res["win_rate"], "| 2-year attached:", d["zones_full"] is not None)

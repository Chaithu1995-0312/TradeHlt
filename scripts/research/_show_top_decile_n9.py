#!/usr/bin/env python3
"""Show why nb_top_decile has n=9 on protocol v1 units."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

p = Path("results/gaussian_xauusd_econ/xau_metals_protocol_v1/units_scored.jsonl")
units = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
train = [u for u in units if u["split"] == "train"]
oos = [u for u in units if u["split"] == "oos"]
train_sc = np.asarray([float(u["score"]) for u in train], dtype=float)
p10 = float(np.percentile(train_sc, 10))
p90 = float(np.percentile(train_sc, 90))

print(f"n_all={len(units)} n_train={len(train)} n_oos={len(oos)}")
print(f"train p10={p10:.6f}  p90={p90:.6f}")
print(f"train score min={train_sc.min():.6f} max={train_sc.max():.6f}")
print()
print("rank  split  dir    score     >=p90  arm_tag")
print("-" * 60)
for i, u in enumerate(sorted(units, key=lambda x: -float(x["score"])), 1):
    sc = float(u["score"])
    top = sc >= p90
    tagged = "nb_top_decile" in (u.get("arms") or [])
    print(
        f"{i:3d}  {u['split']:5s}  {u['direction']:5s}  {sc:.6f}  "
        f"{'YES' if top else 'no ':3s}   tag={tagged}"
    )

top = [u for u in units if float(u["score"]) >= p90]
print()
print(
    f"n_top={len(top)}  "
    f"train={sum(1 for u in top if u['split']=='train')}  "
    f"oos={sum(1 for u in top if u['split']=='oos')}"
)
print(
    f"train_sc >= p90 count = {int((train_sc >= p90).sum())} "
    f"(~ceil/ties on 26 points, not exactly 10%)"
)
print(f"oos_sc  >= p90 count = {sum(1 for u in oos if float(u['score']) >= p90)}")
print()
print("Arithmetic:")
print("  universe RETEST = 30")
print("  arm = score >= train_p90  → 9 units")
print("  M4 min_samples = 30")
print("  9 < 30 → gate1 INSUFFICIENT")

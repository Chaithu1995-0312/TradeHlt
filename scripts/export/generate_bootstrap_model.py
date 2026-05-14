"""
generate_bootstrap_model.py
============================
Generates a random-weight model.json for the legacy bitnet_score() path.

Architecture: 6 → 16 → 8 → 1  (sigmoid output)

This is a BOOTSTRAP model — weights are random. BitNet will contribute
noise-level predictions until you retrain with real P&L labels.
S8 blends BitNet at bitnet_weight=0.40, so feature scorer still drives signals.

Run:
    python scripts/export/generate_bootstrap_model.py
"""

import json
import random
from pathlib import Path

random.seed(42)

IN_DIM  = 6    # body_ratio, retest_depth, disp_strength, atr, candles_since_retest, double_sweep
H1      = 16
H2      = 8
OUT     = 1


def _layer(in_d: int, out_d: int):
    w = [[round(random.uniform(-0.5, 0.5), 6) for _ in range(in_d)] for _ in range(out_d)]
    b = [round(random.uniform(-0.1, 0.1), 6) for _ in range(out_d)]
    return w, b


l1_w, l1_b = _layer(IN_DIM, H1)
l2_w, l2_b = _layer(H1, H2)
lo_w, lo_b = _layer(H2, OUT)

model = {
    "schema":       "legacy_6input",
    "architecture": f"{IN_DIM}->{H1}->{H2}->{OUT}",
    "feature_order": [
        "body_ratio", "retest_depth", "disp_strength",
        "atr", "candles_since_retest", "double_sweep"
    ],
    "layer1_w": l1_w, "layer1_b": l1_b,
    "layer2_w": l2_w, "layer2_b": l2_b,
    "out_w":    lo_w, "out_b":    lo_b,
}

out = Path("model.json")
out.write_text(json.dumps(model, indent=2))
print(f"Bootstrap model.json written  ({IN_DIM}->{H1}->{H2}->{OUT})")
print(f"Weights are RANDOM — retrain with: python scripts/training/train_bitnet.py")

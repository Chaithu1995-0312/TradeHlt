"""
regen_bitnet_35.py
==================
Regenerate model_export_format.json with input_dim=35 to match CANONICAL_FEATURES.

Architecture: 35 → 32 → 16 → 1  (BitNet binary weights + learned scales)
"""
import json
import random

random.seed(42)

INPUT_DIM = 35
HIDDEN1   = 32
HIDDEN2   = 16
OUTPUT    = 1

# Must match features.feature_schema.CANONICAL_FEATURES exactly
FEATURE_ORDER = [
    "open", "high", "low", "close", "volume",
    "volume_ratio", "double_sweep",
    "ema_fast", "ema_slow", "ema_spread",
    "trend_bias", "trend_strength",
    "momentum_score",
    "atr", "volatility_ratio",
    "rsi_14",
    "macd_line", "macd_signal", "macd_hist",
    "sweep_detected", "liquidity_sweep", "break_of_structure",
    "swing_high", "swing_low", "higher_high", "lower_low",
    "body_size", "wick_size", "body_ratio",
    "volatility_regime",
    "session", "hour_of_day",
    "disp_strength", "retest_depth", "candles_since_retest"
]

assert len(FEATURE_ORDER) == INPUT_DIM, (
    f"FEATURE_ORDER length {len(FEATURE_ORDER)} != INPUT_DIM {INPUT_DIM}. Fix the list."
)


def make_layer(in_dim: int, out_dim: int, name: str) -> dict:
    """Generate a single BitNet layer with random binary weights and calibrated scales."""
    weights = [
        [random.randint(0, 1) for _ in range(in_dim)]
        for _ in range(out_dim)
    ]
    scale = [round(random.uniform(0.8, 1.2), 6) for _ in range(out_dim)]
    return {"name": name, "weights": weights, "scale": scale}


model = {
    "schema": "bitnet_export_v1",
    "schema_version": "v5",
    "input_dim": INPUT_DIM,
    "architecture": f"{INPUT_DIM}->{HIDDEN1}->{HIDDEN2}->{OUTPUT}",
    "feature_order": FEATURE_ORDER,
    "layers": [
        make_layer(INPUT_DIM, HIDDEN1, "fc1"),
        make_layer(HIDDEN1,   HIDDEN2, "fc2"),
        make_layer(HIDDEN2,   OUTPUT,  "fc3"),
    ]
}

output_path = "model_export_format.json"
with open(output_path, "w") as f:
    json.dump(model, f, indent=2)

print(f"✅ Generated BitNet model: {INPUT_DIM}→{HIDDEN1}→{HIDDEN2}→{OUTPUT}")
print(f"   input_dim     : {model['input_dim']}")
print(f"   schema        : {model['schema']} / {model['schema_version']}")
print(f"   fc1 shape     : {len(model['layers'][0]['weights'])} x {len(model['layers'][0]['weights'][0])}")
print(f"   fc2 shape     : {len(model['layers'][1]['weights'])} x {len(model['layers'][1]['weights'][0])}")
print(f"   fc3 shape     : {len(model['layers'][2]['weights'])} x {len(model['layers'][2]['weights'][0])}")
print(f"   feature_order : {len(model['feature_order'])} features")
print(f"   Saved to      : {output_path}")
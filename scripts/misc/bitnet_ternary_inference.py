
import json, math, sys
from pathlib import Path
import numpy as np

# Single source of truth — mirrors tools/cpp/cpp_runner.cpp FEATURE_ORDER
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from features.feature_schema import CANONICAL_FEATURE_ORDER as FEATURE_ORDER

def clean(x):
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 0.0
    return float(x)

def normalize(r):
    return np.array([clean(r.get(f, 0.0)) for f in FEATURE_ORDER], dtype=np.float32)

def binarize(x):
    return np.where(x > 0, 1.0, -1.0).astype(np.float32)

def forward(x, model):
    layers_out = []
    for w, b, s in zip(model["weights"], model["bias"], model["scales"]):
        w = np.array(w, dtype=np.float32)
        b = np.array(b, dtype=np.float32)
        x = np.dot(w, x) * s + b
        layers_out.append(x.tolist())
    return {"layer1": layers_out[0], "layer2": layers_out[1], "final": layers_out[-1][0]}

def main():
    data = json.load(open("test_vectors.json"))
    model = json.load(open("model.json"))
    out = []
    for r in data:
        x = binarize(normalize(r))
        out.append(forward(x, model))
    json.dump(out, open("python_outputs.json", "w"), indent=2)

if __name__ == "__main__":
    main()


import json, random, sys
from pathlib import Path

# First layer input dim must match CANONICAL_FEATURE_ORDER (35 features)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from features.feature_schema import CANONICAL_FEATURE_DIM

def main():
    random.seed(42)
    n_in = CANONICAL_FEATURE_DIM   # 35 — canonical feature vector size
    model = {
        "layers": [
            {"in": n_in, "out": 32},
            {"in": 32,   "out": 16},
            {"in": 16,   "out": 1},
        ],
        "weights": [],
        "bias": [],
        "scales": [],
    }
    for l in model["layers"]:
        w = [[random.choice([-1, 1]) for _ in range(l["in"])] for _ in range(l["out"])]
        b = [random.uniform(-1, 1) for _ in range(l["out"])]
        model["weights"].append(w)
        model["bias"].append(b)
        model["scales"].append(1.0)
    with open("model.json", "w") as f:
        json.dump(model, f, indent=2)

if __name__ == "__main__":
    main()

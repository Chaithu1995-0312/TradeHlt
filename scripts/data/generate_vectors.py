import json, random, sys
from pathlib import Path

# Single source of truth — feature list mirrors tools/cpp/cpp_runner.cpp FEATURE_ORDER
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from features.feature_schema import CANONICAL_FEATURE_ORDER

def random_record():
    r = {}
    for f in CANONICAL_FEATURE_ORDER:
        # 10 % chance of zero to exercise clean() paths
        if random.random() < 0.1:
            r[f] = 0.0
        else:
            r[f] = random.uniform(-5.0, 5.0)
    return r

def main(n=200):
    random.seed(42)
    data = [random_record() for _ in range(n)]
    out = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "test_vectors.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Written {len(data)} vectors -> {out}")

if __name__ == "__main__":
    main()

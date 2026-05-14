import json
import math

py = json.load(open("python_outputs.json"))
cpp = json.load(open("cpp_outputs.json"))

def close(a, b):
    return math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-5)

for i,(a,b) in enumerate(zip(py,cpp)):
    for k in ["layer1","layer2"]:
        for j,(x,y) in enumerate(zip(a[k],b[k])):
            if not close(x,y):
                print(f"FAIL idx {i} {k}[{j}] {x} vs {y}")
                exit(1)

    if not close(a["final"], b["final"]):
        print(f"FAIL idx {i} final {a['final']} vs {b['final']}")
        exit(1)

print("PASS")
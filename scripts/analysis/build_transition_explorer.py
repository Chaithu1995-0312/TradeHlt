"""Build the Feature Transition Explorer HTML from feature_transition_research outputs (no network, no src changes)."""
import json
import math
import sys
from pathlib import Path

d = Path(sys.argv[1] if len(sys.argv) > 1 else "results/feature_transition_research")
rows = json.loads((d / "transitions.json").read_text())
cols = list(rows[0].keys())


def r(v):
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, 4)
    return v


payload = {
    "manifest": json.loads((d / "manifest.json").read_text()),
    "spec": json.loads((d / "spec.json").read_text()),
    "cols": cols,
    "rows": [[r(x[c]) for c in cols] for x in rows],
    "traces": json.loads((d / "traces.json").read_text()),
}
for t in payload["traces"].values():
    t["features"] = {k: [None if v is None else round(v, 5) for v in vs] for k, vs in t["features"].items()}
tpl = (Path(__file__).parent / "transition_explorer_template.html").read_text()
html = tpl.replace("/*__DATA__*/null", json.dumps(payload, separators=(",", ":")))
(d / "explorer.html").write_text(html)
print(d / "explorer.html", len(html))

"""One-shot: mark TradeNet as BLOCKED (dim mismatch) in summary + report."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sum_path = ROOT / "results" / "model_runners" / "XAUUSD" / "ALL_MODELS_SUMMARY.json"
rep_path = ROOT / "docs" / "analysis" / "xauusd-model-layer-run-report-2026-07-28.md"

payload = json.loads(sum_path.read_text(encoding="utf-8"))
reason = (
    "schema_mismatch: envelope feature_dim=38 != live CANONICAL_FEATURE_DIM=39; "
    "TradeNetV2 refuse load (fail-closed). Artifact exists at "
    "models/XAUUSD/20260723T084643/tradenet_v2_XAUUSD_20260723T084643.json"
)
for m in payload["models"]:
    if m["model_id"] == "tradenet":
        m["status"] = "BLOCKED"
        m["block_reason"] = reason
        m.pop("error", None)
        m.pop("traceback", None)
payload["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
sum_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")

text = rep_path.read_text(encoding="utf-8")
text = text.replace("| `tradenet` | **ERROR** |", "| `tradenet` | **BLOCKED** |")
text = re.sub(
    r"(\| `tradenet` \| \*\*BLOCKED\*\* \| False \| UNWIRED \| — \| — \| )[^\n|]+",
    r"\1schema_mismatch dim 38!=39",
    text,
)
text = text.replace("- **Status:** ERROR\n", "- **Status:** BLOCKED\n", 1)
# only tradenet error block — replace first Error after tradenet heading
parts = text.split("## Model: `tradenet`")
if len(parts) == 2:
    head, rest = parts
    rest = rest.replace(
        "**Error:** RuntimeError:",
        f"**Blocked:** {reason}\n\nPrior RuntimeError:",
        1,
    )
    # fix status line in section
    rest = rest.replace("- **Status:** ERROR", "- **Status:** BLOCKED", 1)
    text = head + "## Model: `tradenet`" + rest
rep_path.write_text(text, encoding="utf-8")

print("models:")
for m in payload["models"]:
    print(f"  {m['model_id']:20} {m['status']}")
print("patched", sum_path)
print("patched", rep_path)

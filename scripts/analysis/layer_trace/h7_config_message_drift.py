"""h7_config_message_drift.py — H7: do live_engine_hook.py's error messages name an outdated
config file?

Plan reference: pure-conversation-share-only-rosy-parnas.md §4 H7.

CLAIM UNDER TEST
----------------
`src/runtime/live_engine_hook.py`'s `_load_engine_config()` docstring and its raised error
messages tell the operator to "Ensure configs/production/v1_multi_2026_03.json exists and is
valid" / "Add it to configs/production/v1_multi_2026_03.json" — but the function does not load
that file. It loads via `get_prod_metadata()` / `PROD_VERSION`, which resolves through
`configs/production/ACTIVE_VERSION` (currently `v2_htfcrt_2026_08`, NOT `v1_multi_2026_03`).

METHOD
------
Static source + config check (no live run needed — this is a text-vs-config fact, not a runtime
behaviour):
  1. Count occurrences of the literal string "v1_multi_2026_03.json" in live_engine_hook.py.
  2. Confirm the ACTUAL load path (`get_prod_metadata`/`PROD_VERSION`) is what the function calls.
  3. Read `configs/production/ACTIVE_VERSION` and confirm it does NOT equal "v1_multi_2026_03".

KILL RULE
---------
Zero occurrences of the stale filename, OR ACTIVE_VERSION genuinely equals "v1_multi_2026_03"
(hypothesis falsified — the messages would be accurate).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"


def main() -> int:
    hook_path = SRC / "runtime" / "live_engine_hook.py"
    text = hook_path.read_text(encoding="utf-8")

    stale_mentions = [
        (i + 1, line.strip())
        for i, line in enumerate(text.splitlines())
        if "v1_multi_2026_03" in line
    ]

    uses_active_version_resolver = bool(
        re.search(r"get_prod_metadata\s*\(", text) or re.search(r"\bPROD_VERSION\b", text)
    )
    imports_active_version_resolver = "from config_layer.production_config import" in text

    active_version_path = REPO_ROOT / "configs" / "production" / "ACTIVE_VERSION"
    active_version = active_version_path.read_text(encoding="utf-8").strip() if active_version_path.exists() else None

    drift_confirmed = bool(stale_mentions) and active_version != "v1_multi_2026_03"

    verdict = {
        "hypothesis": "H7",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "file": "src/runtime/live_engine_hook.py",
        "stale_filename_mention_count": len(stale_mentions),
        "stale_filename_mentions": stale_mentions,
        "uses_active_version_resolver": uses_active_version_resolver,
        "imports_from_production_config": imports_active_version_resolver,
        "active_version_file_contents": active_version,
        "result": "CONFIRMED_STALE_CONFIG_MESSAGE" if drift_confirmed else "FALSIFIED",
    }

    out_path = REPO_ROOT / "results" / f"h7_config_message_drift_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    print(f"H7 result: {verdict['result']}")
    print(f"  stale 'v1_multi_2026_03.json' mentions: {len(stale_mentions)}")
    for ln, txt in stale_mentions[:10]:
        print(f"    L{ln}: {txt[:100]}")
    print(f"  actual ACTIVE_VERSION: {active_version!r}")
    print(f"  -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

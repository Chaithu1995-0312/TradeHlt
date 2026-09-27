"""
log_turn.py — capture one multi-LLM turn into the append-only ledger (manual paste workflow).

You paste/redirect a model's full response into a file, then run this once. It stores the
response VERBATIM (no loss) and appends an index line, parsing the §3 handoff block into
structured fields for the discussion rewind (discussion.py).

Usage:
  python scripts/context/log_turn.py --actor gemini --story STORY-1.1 --in resp.txt
  python scripts/context/log_turn.py --actor claude --in resp.txt --cycle cycle_20260615 \
      --parent t00012_ab12cd34 --pack context/packs/STORY-1.1.md
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
try:  # preserve non-ASCII without crashing a cp1252 console
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from multi_llm.turn_ledger import TurnLedger, ROLES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--actor", required=True, help=f"one of {', '.join(ROLES)} (case-insensitive)")
    ap.add_argument("--in", dest="infile", required=True, help="file with the model's full response")
    ap.add_argument("--story", default="", help="STORY-x.y id this turn is about (optional)")
    ap.add_argument("--cycle", default=None, help="cycle id (default: cycle_YYYYMMDD)")
    ap.add_argument("--parent", default="", help="parent turn_id (the previous turn in the cycle)")
    ap.add_argument("--model-version", default="", help="e.g. gemini-2.5-pro / gpt-5 / claude-opus-4-8")
    ap.add_argument("--prompt", default="", help="optional file with the prompt that was given")
    ap.add_argument("--pack", default="", help="optional pack file handed to the model (records its fingerprint)")
    args = ap.parse_args()

    response_text = Path(args.infile).read_text(encoding="utf-8")
    prompt_text = Path(args.prompt).read_text(encoding="utf-8") if args.prompt else ""
    fingerprint = ""
    if args.pack and Path(args.pack).exists():
        fingerprint = hashlib.sha256(Path(args.pack).read_bytes()).hexdigest()[:16]

    rec = TurnLedger().append(
        actor=args.actor,
        response_text=response_text,
        story_id=args.story,
        cycle_id=args.cycle,
        parent_turn_id=args.parent,
        model_version=args.model_version,
        context_fingerprint=fingerprint,
        pack_ref=args.pack,
        prompt_text=prompt_text,
    )
    print(f"logged {rec.turn_id} [{rec.actor}] cycle={rec.cycle_id} "
          f"next_actor={rec.next_actor or '?'} story={rec.story_id or '-'}")
    print(f"  verbatim: multi_llm/{rec.response_ref}")


if __name__ == "__main__":
    main()

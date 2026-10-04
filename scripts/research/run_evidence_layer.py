"""Thin CLI. Logic lives in src/research/evidence/."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for p in (_ROOT, _ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from research.evidence.__main__ import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

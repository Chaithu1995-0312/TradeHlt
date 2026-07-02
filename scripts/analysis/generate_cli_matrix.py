from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from control_plane.registry import generate_cli_matrix_markdown


def main() -> None:
    out_path = Path("docs/reference/cli-matrix.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(generate_cli_matrix_markdown(), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

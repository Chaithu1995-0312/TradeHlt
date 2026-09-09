"""isolated_config_root.py — run a process against a chosen production config, safely.

CH-v3-unified-market-structure-v1.

THE PROBLEM
-----------
`PROD_VERSION` is resolved ONCE at import (`config_layer/production_config.py:82`) by reading
`configs/production/ACTIVE_VERSION`, and there is no environment override — that is deliberate,
and is exactly what CLAUDE.md §4.0 (`ORIENT_RUNTIME`) and F-057 enforce: version truth is
file-driven, never inferred.

So running a backtest under a version that is not the active one has historically meant flipping
the shared pointer, running, and flipping it back. That is unsafe here for a concrete reason:
this repository is routinely worked by several concurrent processes, and the flip window is a
whole multi-minute backtest. Any other process importing `production_config` during that window
silently resolves the wrong version — a split-brain of exactly the class F-016/F-018 describe,
manufactured by the tooling rather than found in it.

THE FIX
-------
Note that `_ACTIVE_VERSION_FILE` is a path RELATIVE to the process working directory
(`production_config.py:57`). So a process running with `cwd` set elsewhere reads a DIFFERENT
pointer. This module builds that elsewhere: a scratch root holding

  - a real copy of `configs/`      (~2 MB, so each root owns its own ACTIVE_VERSION and may have
                                    its config edited without touching the repository's)
  - directory junctions to `data/`, `model-artifact root`, `src/`, `scripts/`   (large, read-only in this use)
  - fresh empty `logs/` and `results/`                              (so writes never land in the repo)

The shared pointer is never written, so no other process can observe which version this one
chose. Junctions need no elevation on Windows; POSIX uses symlinks.

WHAT THIS IS NOT
----------------
It grants no authority and changes no truth. A root is a *reading* arrangement — the version it
pins is still resolved by the same governed loader, with the same hash verification. It does not
promote, activate, or validate anything, and a config only reachable through a scratch root is
by definition not the active one.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

#: Trees a root links to rather than copies. `configs` is deliberately absent — it is the one
#: tree that must be a real, independently-writable copy, since the whole point is to give the
#: root its own ACTIVE_VERSION.
LINKED_TREES = ("data", "models", "src", "scripts")

#: Trees created fresh and empty, so a scratch run cannot write into the repository.
FRESH_TREES = ("logs", "results")


def link_dir(src: Path, dst: Path) -> None:
    """Directory junction (Windows) or symlink (POSIX).

    Junctions rather than `os.symlink`: Windows directory symlinks require developer mode or
    elevation, junctions do not, and this must work on an ordinary developer machine.
    """
    if platform.system() == "Windows":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(dst), str(src)],
            check=True, capture_output=True,
        )
    else:
        os.symlink(src, dst, target_is_directory=True)


def build_config_root(
    repo: Path,
    root: Path,
    version: str,
    *,
    mutate_config: Optional[Callable[[dict], None]] = None,
) -> Path:
    """Create `root` as an isolated run root pinned to `version`.

    `mutate_config` may edit the root's OWN copy of the version config in place (for example to
    turn an observation flag on for one arm of an A/B). It cannot affect the committed config —
    the copy is made first and only the copy is written.
    """
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repo / "configs", root / "configs")
    for tree in LINKED_TREES:
        link_dir(repo / tree, root / tree)
    for tree in FRESH_TREES:
        (root / tree).mkdir(exist_ok=True)

    cfg_path = root / "configs" / "production" / f"{version}.json"
    if not cfg_path.exists():
        raise FileNotFoundError(f"no such production config: {cfg_path.name}")
    (root / "configs" / "production" / "ACTIVE_VERSION").write_text(
        version + "\n", encoding="utf-8"
    )

    if mutate_config is not None:
        cfg: dict[str, Any] = json.loads(cfg_path.read_text(encoding="utf-8"))
        mutate_config(cfg)
        cfg_path.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    return root


def run_backtest(
    repo: Path,
    root: Path,
    corpus_rel: str,
    instrument: str,
    *,
    python: Optional[str] = None,
) -> Path:
    """Run `runtime.backtest_v2` inside `root`; return its result directory.

    `corpus_rel` is RELATIVE to the root and resolves through the junctioned `data/` tree.
    That is a requirement, not a convenience: `dataset_integrity` refuses a corpus outside a
    canonical `data/` root, misnamed, or without a reviewed clock record (F-039's L3 gate,
    F-066's clock provenance). Copying a corpus into scratch to shorten it is REJECTED —
    correctly — so there is no truncation option here.
    """
    import sys

    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [python or sys.executable, "-m", "runtime.backtest_v2",
         "--csv", corpus_rel, "--instrument", instrument,
         "--output", str(root / "results")],
        cwd=str(root), env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"backtest failed in {root.name} (exit {proc.returncode})\n"
            f"{proc.stdout[-4000:]}\n{proc.stderr[-4000:]}"
        )
    runs = sorted((root / "results").glob(f"*_{instrument}"))
    if not runs:
        raise RuntimeError(f"no result directory produced in {root.name}")
    return runs[-1]

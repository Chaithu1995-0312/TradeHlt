"""Parity pins for the shared run-manifest helpers in `research.provenance`.

Research-framework consolidation Phase 1 replaced private helper copies in scripts/analysis and
scripts/research with same-named imports of these functions. The replacement is only lossless if
each shared function behaves exactly like every variant it replaced — so the variants are copied
here VERBATIM (originals archived under archive/research_framework_phase1*_2026-09-14/) and compared
on the same inputs. If a future edit changes a shared helper, this floor fails before a manifest
hash or run stamp in any of ~60 scripts silently changes.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from research import provenance as prov


# ── verbatim originals (normalized-body variants 58ea5a0042 / 88dc0288cd / 5b64ee474a / 6ac2da0004) ──
def _orig_sha256_open(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _orig_sha256_path_open(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _orig_sha256_path_open_fh(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _orig_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# variant 9b89feee8d
def _orig_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


_SIZES = [0, 1, (1 << 20) - 1, 1 << 20, (1 << 20) + 1, 3 * (1 << 20) + 7]


@pytest.mark.parametrize("size", _SIZES)
def test_sha256_file_matches_every_replaced_variant(tmp_path: Path, size: int) -> None:
    p = tmp_path / f"blob_{size}.bin"
    p.write_bytes(bytes((i * 131 + 7) % 256 for i in range(size)))
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    for orig in (_orig_sha256_open, _orig_sha256_path_open, _orig_sha256_path_open_fh, _orig_sha):
        assert orig(p) == expected
    assert prov.sha256_file(p) == expected
    assert prov.sha256_file(str(p)) == expected  # str accepted (open() variants already allowed it)


def test_sha256_file_missing_raises_like_originals(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _orig_sha256_open(tmp_path / "absent")
    with pytest.raises(FileNotFoundError):
        prov.sha256_file(tmp_path / "absent")


def test_git_commit_matches_original_inside_and_outside_a_repo(tmp_path: Path, monkeypatch) -> None:
    assert prov.git_commit() == _orig_git_commit()
    monkeypatch.chdir(tmp_path)  # not a git repo (tmp dir) -> both degrade identically
    assert prov.git_commit() == _orig_git_commit()


def test_utc_stamps_keep_their_exact_formats() -> None:
    before = datetime.now(timezone.utc).replace(microsecond=0)
    compact, iso = prov.utc_stamp_compact(), prov.utc_now_iso()
    assert re.fullmatch(r"\d{8}T\d{6}Z", compact)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", iso)
    for s, fmt in ((compact, "%Y%m%dT%H%M%SZ"), (iso, "%Y-%m-%dT%H:%M:%SZ")):
        parsed = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        assert abs((parsed - before).total_seconds()) < 5


def test_existing_provenance_block_shape_unchanged() -> None:
    """Adding the helpers must not alter the historical stamp shape."""
    blk = prov.truth_standard_block("intrabar_fixed", 12.0)
    assert blk == {"version": prov.TRUTH_STANDARD_VERSION, "exit_geometry": "intrabar_fixed",
                   "slippage_model": "flat_12bps", "tie_break": "SL_before_TP",
                   "fill_model": "perfect_stop_fill"}

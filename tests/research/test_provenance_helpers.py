"""Parity pins for the shared run-manifest helpers in `research.provenance`.

Research-framework consolidation Phase 1 replaced private helper copies in scripts/analysis and
scripts/research with same-named imports of these functions. The replacement is only lossless if
each shared function behaves exactly like every variant it replaced — so the variants are copied
here VERBATIM (originals archived under archive/research_framework_phase1*_2026-09-14/) and compared
on the same inputs. If a future edit changes a shared helper, this floor fails before a manifest
hash or run stamp in any of ~60 scripts silently changes.

Phase 4 (2026-09-17) swept for remaining un-migrated hand-rolled copies and found 5 candidates.
Reading each in full (not assumed from name similarity) found only 3 were genuine duplicates:
`build_bar_matrix.py` (matches the `_orig_sha256_open` shape exactly) and
`xauusd_mt5_cost_calibration.py` / `zone_x_o4_gap_study.py` (a whole-file-read variant, pinned
below as `_orig_sha256_readbytes` — output-identical to the streaming variants for any input, since
SHA-256 of the same bytes is the same regardless of chunking). All 3 were migrated to the shared
`sha256_file` import. The other 2 candidates were deliberately NOT migrated, matching this file's
own stated Phase-1 policy ("Variants that differed... were deliberately NOT folded in"):
`path_ambiguity_census.py`'s `_git_commit` pins `cwd=_ROOT` (the shared `git_commit()` relies on
process cwd) — a real behavioral difference, not a duplicate. `run_h_msip_002.py`'s `_sha256_file`
already delegates to `run_h_msip_001.py`'s own `_sha256_file`, which itself already imports
`research.provenance.sha256_file` (Phase 1 adopter) — so there was no duplicate left to fix there;
its `_git_meta`/`_sha256_bytes` are genuinely distinct helpers (a dirty-tree dict, and hashing
in-memory bytes rather than a file path), not copies of anything here.
"""
from __future__ import annotations

import hashlib
import json
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


# Phase 4 (2026-09-17): xauusd_mt5_cost_calibration.py + zone_x_o4_gap_study.py's shared shape —
# reads the whole file into memory rather than streaming, but hashes the identical bytes.
def _orig_sha256_readbytes(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
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
    for orig in (_orig_sha256_open, _orig_sha256_path_open, _orig_sha256_path_open_fh, _orig_sha,
                 _orig_sha256_readbytes):
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
    """Adding the helpers must not alter the historical stamp shape.

    `tie_break` became a required parameter under CH-measurement-basis-declaration;
    passing the historical literal "SL_before_TP" and getting the canonicalised
    "production" back proves the SHAPE is unchanged even though the VALUE's spelling is
    now normalised.
    """
    blk = prov.truth_standard_block("intrabar_fixed", 12.0, tie_break="SL_before_TP")
    assert blk == {"version": prov.TRUTH_STANDARD_VERSION, "exit_geometry": "intrabar_fixed",
                   "slippage_model": "flat_12bps", "tie_break": "production",
                   "fill_model": "perfect_stop_fill"}


# ── write_report() parity (Phase 4) ──────────────────────────────────────────────────────────
# Verbatim replica of the report+manifest write sequence hand-written identically in
# ablate_zone_thr_xauusd_fusion.py / diagnose_gaussian_pivotality.py (both include body_sha256)
# and transition_information.py (which does not — hence write_report's include_body_sha256 flag).
def _orig_write_report(out_dir: Path, stem: str, body: dict, extra: dict, include_sha: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    body_json = json.dumps(body, sort_keys=True, indent=2)
    (out_dir / f"{stem}.json").write_text(body_json, encoding="utf-8")
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "git_commit": _orig_git_commit()}
    if include_sha:
        manifest["body_sha256"] = hashlib.sha256(body_json.encode("utf-8")).hexdigest()
    manifest.update(extra)
    (out_dir / f"{stem}_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8")


@pytest.mark.parametrize("include_sha,extra", [
    (True, {"spine_config_sha256": "abc123", "instrument": "XAUUSD"}),  # ablate/diagnose shape
    (False, {}),  # transition_information.py shape
])
def test_write_report_matches_hand_rolled_originals(tmp_path: Path, include_sha: bool, extra: dict) -> None:
    body = {"z": 1, "a": [1, 2, 3], "nested": {"b": 2}}

    orig_dir = tmp_path / "orig"
    _orig_write_report(orig_dir, "stem", body, extra, include_sha)
    new_dir = tmp_path / "new"
    report_path, manifest_path = prov.write_report(
        new_dir, "stem", body, extra_manifest=extra or None, include_body_sha256=include_sha)

    assert report_path == new_dir / "stem.json"
    assert manifest_path == new_dir / "stem_manifest.json"
    # report.json is wall-clock-free -> must be byte-identical.
    assert report_path.read_text(encoding="utf-8") == (orig_dir / "stem.json").read_text(encoding="utf-8")

    orig_manifest = json.loads((orig_dir / "stem_manifest.json").read_text(encoding="utf-8"))
    new_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Every field except generated_at (wall-clock, compared with tolerance below) must match exactly.
    assert {k: v for k, v in orig_manifest.items() if k != "generated_at"} == \
           {k: v for k, v in new_manifest.items() if k != "generated_at"}
    t_orig = datetime.fromisoformat(orig_manifest["generated_at"])
    t_new = datetime.fromisoformat(new_manifest["generated_at"])
    assert abs((t_new - t_orig).total_seconds()) < 5


def test_write_report_creates_out_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "does" / "not" / "exist"
    report_path, manifest_path = prov.write_report(out_dir, "x", {"k": "v"})
    assert report_path.exists() and manifest_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8")) == {"k": "v"}

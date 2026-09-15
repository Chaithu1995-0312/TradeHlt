"""Archive ledger floor — every file under archive/ is tracked by hash, and nothing was deleted.

The research-framework consolidation promises zero loss: before a live file is edited or shimmed, a
byte-exact copy goes to archive/<batch>/ with a SHA-256 manifest row. Before this floor, 57 archived
files had no row, and 9 live scripts had been left uncompilable by an edit no manifest recorded —
a skipped copy looked exactly like a recorded one. The synthetic tests prove each check can FAIL
(a floor that cannot fail enforces nothing — E-001F); the repo test pins the real ledger.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from governance import archive_manifest as am

_ROOT = Path(__file__).resolve().parents[2]


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A minimal repo: one live file, one batch holding its pre-edit copy, an index naming the batch."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "x.py").write_bytes(b"print('after')\n")
    batch = tmp_path / "archive" / "b1_2026-09-14"
    (batch / "scripts").mkdir(parents=True)
    (batch / "scripts" / "x.py").write_bytes(b"print('before')\n")
    _write_csv(batch / "MANIFEST.csv", list(am.CANONICAL_COLUMNS), [
        ["2026-09-14T00:00:00Z", "copied_before_edit", "scripts/x.py",
         "archive/b1_2026-09-14/scripts/x.py", _sha(b"print('before')\n"), "pre-edit", ""],
        ["2026-09-14T00:00:01Z", "edited_in_place", "scripts/x.py",
         "archive/b1_2026-09-14/scripts/x.py", "", "edit", _sha(b"print('after')\n")],
    ])
    (tmp_path / "archive" / "ARCHIVE_INDEX.md").write_text("## b1_2026-09-14\n", encoding="utf-8")
    return tmp_path


def test_clean_synthetic_repo_passes(repo: Path) -> None:
    rep = am.verify(repo)
    assert rep.ok, rep.violations
    assert rep.warnings == []
    assert rep.rows == 2 and rep.archive_files == 1


def test_tampered_archive_copy_is_a_violation(repo: Path) -> None:
    (repo / "archive" / "b1_2026-09-14" / "scripts" / "x.py").write_bytes(b"tampered\n")
    assert any("!= recorded sha256_before" in v for v in am.verify(repo).violations)


def test_deleted_live_original_is_a_violation(repo: Path) -> None:
    (repo / "scripts" / "x.py").unlink()
    assert any("live original missing" in v for v in am.verify(repo).violations)


def test_untracked_archive_file_is_a_violation(repo: Path) -> None:
    (repo / "archive" / "b1_2026-09-14" / "stray.txt").write_text("x", encoding="utf-8")
    assert any("untracked archive file" in v for v in am.verify(repo).violations)


def test_post_edit_row_alone_does_not_track_archive_bytes(repo: Path) -> None:
    """Pointing at an archive path from an edited_in_place row does not hash those bytes."""
    extra = repo / "archive" / "b1_2026-09-14" / "scripts" / "y.py"
    extra.write_bytes(b"y\n")
    am.append_rows(repo / "archive" / "b1_2026-09-14" / "MANIFEST.csv", [{
        "timestamp_utc": "2026-09-14T00:00:02Z", "action": "edited_in_place",
        "original_path": "scripts/x.py", "archive_path": "archive/b1_2026-09-14/scripts/y.py",
        "sha256_before": "", "reason": "points only", "sha256_after": _sha(b"print('after')\n"),
    }])
    assert any("scripts/y.py" in v for v in am.verify(repo).violations)


def test_batch_missing_from_index_is_a_violation(repo: Path) -> None:
    (repo / "archive" / "ARCHIVE_INDEX.md").write_text("nothing\n", encoding="utf-8")
    assert any("not named in" in v for v in am.verify(repo).violations)


def test_unknown_action_and_header_are_violations(repo: Path) -> None:
    _write_csv(repo / "archive" / "b2" / "MANIFEST.csv", ["a", "b"], [["1", "2"]])
    (repo / "archive" / "ARCHIVE_INDEX.md").write_text("b1_2026-09-14 b2\n", encoding="utf-8")
    assert any("unrecognised manifest header" in v for v in am.verify(repo).violations)
    with pytest.raises(ValueError):
        am.append_rows(repo / "archive" / "b1_2026-09-14" / "MANIFEST.csv", [{"action": "vanished"}])


def test_later_live_edit_is_a_warning_not_a_violation(repo: Path) -> None:
    (repo / "scripts" / "x.py").write_bytes(b"print('edited again')\n")
    rep = am.verify(repo)
    assert rep.ok, rep.violations
    assert len(rep.warnings) == 1 and "edited after" in rep.warnings[0]


def test_legacy_b_schema_reads_and_appends_in_its_own_header(repo: Path) -> None:
    batch = repo / "archive" / "legacy_b"
    (batch / "scripts").mkdir(parents=True)
    (batch / "scripts" / "x.py").write_bytes(b"old\n")
    manifest = batch / "MANIFEST.csv"
    _write_csv(manifest, ["utc", "action", "source", "dest", "sha256", "note"], [
        ["2026-09-14T00:00:00Z", "copied_before_edit", "scripts/x.py",
         "archive/legacy_b/scripts/x.py", _sha(b"old\n"), "pre-edit"],
    ])
    (repo / "archive" / "ARCHIVE_INDEX.md").write_text("b1_2026-09-14 legacy_b\n", encoding="utf-8")
    kind, rows = am.read_manifest(manifest, repo)
    assert kind == "legacy_b" and rows[0].original_path == "scripts/x.py"
    am.append_rows(manifest, [{"timestamp_utc": "t", "action": "correction", "original_path": "scripts/x.py",
                               "archive_path": "", "sha256_before": "", "reason": "note"}])
    assert manifest.read_text(encoding="utf-8").splitlines()[0] == "utc,action,source,dest,sha256,note"
    with pytest.raises(ValueError):
        am.append_rows(manifest, [{"action": "edited_in_place", "sha256_after": "abc"}])
    assert am.verify(repo).ok


def test_unhashed_legacy_row_is_satisfied_only_by_a_hashed_backfill(repo: Path) -> None:
    batch = repo / "archive" / "b1_2026-09-14"
    (batch / "_helper.py").write_bytes(b"helper\n")
    am.append_rows(batch / "MANIFEST.csv", [{
        "timestamp_utc": "t", "action": "moved_to_archive", "original_path": "_helper.py",
        "archive_path": "archive/b1_2026-09-14/_helper.py", "sha256_before": "", "reason": "moved"}])
    assert any("carries no sha256_before" in v for v in am.verify(repo).violations)
    plan = am.backfill_rows(repo)
    assert [r["archive_path"] for r in plan[batch / "MANIFEST.csv"]] == ["archive/b1_2026-09-14/_helper.py"]
    for target, rows in plan.items():
        am.append_rows(target, rows)
    assert am.verify(repo).ok


def test_snapshot_is_byte_exact_and_refuses_divergent_overwrite(repo: Path) -> None:
    batch = repo / "archive" / "b3"
    row = am.snapshot(repo / "scripts" / "x.py", batch, "pre-edit", root=repo)
    assert (batch / "scripts" / "x.py").read_bytes() == (repo / "scripts" / "x.py").read_bytes()
    assert row["sha256_before"] == _sha(b"print('after')\n")
    assert am.snapshot(repo / "scripts" / "x.py", batch, "again", root=repo)["sha256_before"] == row["sha256_before"]
    (repo / "scripts" / "x.py").write_bytes(b"changed\n")
    with pytest.raises(FileExistsError):
        am.snapshot(repo / "scripts" / "x.py", batch, "pre-edit", root=repo)


def test_repository_archive_ledger_is_clean() -> None:
    rep = am.verify(_ROOT)
    assert rep.ok, "archive ledger violations:\n" + "\n".join(rep.violations)
    assert rep.archive_files > 0 and rep.rows >= rep.archive_files

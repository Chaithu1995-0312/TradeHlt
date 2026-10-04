"""Corpus-read ratchet floor — the enforcement gate for
`scripts/analysis/corpus_read_lint.py`.

Asserts (a) the ratchet is GREEN today (no NEW ungated corpus read outside
`docs/governance/corpus_read_allowlist.json`); (b) the allowlist is well-formed and every
`durable_key` is unique; (c) the ratchet actually catches a synthetic new violation (proves
the check function can fail, not just always return 0); (d) removing a pinned entry and
re-checking against a matching live finding fails — proves the "not merely present" property
the same class of tests this repo already runs for `feature_math_lint.py`'s pins.
"""
from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "corpus_read_lint.py"
_ALLOWLIST = _REPO / "docs" / "governance" / "corpus_read_allowlist.json"


def _load_tool():
    spec = importlib.util.spec_from_file_location("corpus_read_lint", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    if not _TOOL.exists():
        pytest.skip("corpus_read_lint.py not present")
    return _load_tool()


@pytest.fixture(scope="module")
def allowlist():
    if not _ALLOWLIST.exists():
        pytest.skip("corpus_read_allowlist.json not present")
    return json.loads(_ALLOWLIST.read_text(encoding="utf-8"))


def test_allowlist_well_formed(allowlist):
    assert allowlist["match_key"] == "durable_key"
    entries = allowlist["entries"]
    assert isinstance(entries, list) and len(entries) == allowlist["entry_count"]
    keys = [e["durable_key"] for e in entries]
    assert len(keys) == len(set(keys)), "duplicate durable_key in the allowlist"
    for e in entries:
        assert e["class"] in ("CORPUS", "UNKNOWN")
        assert e["file"] and isinstance(e["line"], int)


def test_floor_is_green(tool):
    """No NEW direct corpus read outside the pinned allowlist. THE regression floor."""
    exit_code = tool.check()
    assert exit_code == 0, (
        "a new direct (ungated) corpus read was introduced outside "
        "docs/governance/corpus_read_allowlist.json — route it through "
        "data_ingestion.corpus_store.read() / corpus_gate.admit_corpus(), or reclassify with "
        "evidence if it is provably already gated or not actually a corpus read."
    )


def test_ratchet_catches_a_synthetic_new_violation(tool, tmp_path, monkeypatch):
    """Prove the check function can actually FAIL, not just always return 0 — same discipline
    as feature_math_lint.py's bite test (a lint that can't fail isn't enforcement)."""
    scratch = tmp_path / "_synthetic_violation.py"
    scratch.write_text(
        "import pandas as pd\ndf = pd.read_csv('data/mt5/XAUUSD_M15.csv')\n",
        encoding="utf-8",
    )
    # Patch the tool's own file iterator to return exactly one file: the synthetic violation.
    # This proves the CHECK logic fails on a genuine new finding, without touching the real
    # repo tree (never write into scripts/ from a test).
    # `scan_file`/`_iter_py_files` live in corpus_read_census.py (imported by corpus_read_lint),
    # and `scan_file` computes `path.relative_to(_ROOT)` against THAT module's own `_ROOT`
    # reference -- patching `tool._ROOT` alone leaves the census module still pointed at the
    # real repo root, which raises ValueError on a tmp_path file that isn't under it.
    import scripts.analysis.corpus_read_census as census_mod
    monkeypatch.setattr(census_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(tool, "_iter_py_files", lambda: [scratch])
    monkeypatch.setattr(tool, "_ROOT", tmp_path)
    exit_code = tool.check()
    assert exit_code == 1


def test_ratchet_passes_when_synthetic_finding_is_pinned(tool, tmp_path, monkeypatch):
    """The inverse: the SAME synthetic finding, pre-pinned in a scratch allowlist, must pass —
    proves the allowlist match actually short-circuits the failure, not a tautology."""
    scratch = tmp_path / "_synthetic_violation.py"
    scratch.write_text(
        "import pandas as pd\ndf = pd.read_csv('data/mt5/XAUUSD_M15.csv')\n",
        encoding="utf-8",
    )
    # `scan_file`/`_iter_py_files` live in corpus_read_census.py (imported by corpus_read_lint),
    # and `scan_file` computes `path.relative_to(_ROOT)` against THAT module's own `_ROOT`
    # reference -- patching `tool._ROOT` alone leaves the census module still pointed at the
    # real repo root, which raises ValueError on a tmp_path file that isn't under it.
    import scripts.analysis.corpus_read_census as census_mod
    monkeypatch.setattr(census_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(tool, "_iter_py_files", lambda: [scratch])
    monkeypatch.setattr(tool, "_ROOT", tmp_path)

    from scripts.analysis.corpus_read_census import scan_file
    findings = [r for r in scan_file(scratch) if r["class"] in ("CORPUS", "UNKNOWN")]
    assert findings, "synthetic fixture did not produce a CORPUS/UNKNOWN finding to pin"

    scratch_allowlist = tmp_path / "allowlist.json"
    scratch_allowlist.write_text(json.dumps({
        "version": 2, "match_key": "durable_key", "entry_count": len(findings),
        "entries": findings,
    }), encoding="utf-8")
    monkeypatch.setattr(tool, "ALLOWLIST_PATH", scratch_allowlist)

    exit_code = tool.check()
    assert exit_code == 0

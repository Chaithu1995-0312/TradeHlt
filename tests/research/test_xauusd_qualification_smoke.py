"""XAUUSD research-pass plumbing SMOKE (ERP T1) — slow / opt-in.

Proves the non-promotable M4 research pass runs end-to-end on a slice of the certified XAUUSD frozen
candidate and records verdicts + a non-promotable manifest — WITHOUT making any edge claim. Marked
`slow` (the forward_walk over controls is O(bars) so a full-corpus pass is minutes); run with
`pytest -m slow`. NOT in the default CI subset. SKIP if the gitignored corpus is absent.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path

_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"

pytestmark = [pytest.mark.research_integrity, pytest.mark.slow]


def _load_qx():
    spec = importlib.util.spec_from_file_location(
        "qualify_xauusd", _ROOT / "scripts" / "research" / "qualify_xauusd.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not _CORPUS.exists(), reason="gitignored XAUUSD frozen candidate not present")
def test_research_pass_runs_and_is_non_promotable(tmp_path):
    qx = _load_qx()
    guarded = guard_xauusd_csv_path("data/XAUUSD_M15.csv", "XAUUSD")
    # small slice of the guarded corpus for a fast plumbing smoke (NOT a full-corpus certification)
    head = pd.read_csv(guarded).head(600)
    slice_csv = tmp_path / "xauusd_head.csv"
    head.to_csv(slice_csv, index=False)

    doc = qx.run(permutations=20, csv_map={"XAUUSD": str(slice_csv)}, family="toy")

    assert doc["non_promotable"] is True
    assert doc["corpus_status"] == "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION"
    toy = doc["families"]["toy"]["hypotheses"]
    assert set(toy) == {"expansion_breakout", "mean_reversion"}
    allowed = {"REJECT", "INSUFFICIENT", "HUMAN_REVIEW", "PROMOTE"}
    for name, r in toy.items():
        assert r["verdict"] in allowed, (name, r["verdict"])
        assert r["n"] >= 0
    # research-only: the pass NEVER auto-promotes anything to production (Authority Ladder §6.5)
    # (a PROMOTE verdict here is still research-only evidence, gated by the manifest's UNTRUSTED_RAW)

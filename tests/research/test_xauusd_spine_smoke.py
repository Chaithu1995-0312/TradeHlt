"""XAUUSD SPINE-family wiring smoke (ERP T1) — slow / opt-in.

Exercises the NOVEL spine wiring: the production decision spine (v2_multi_2026_04) as the `spine`
hypothesis runs one backtest pass over the certified XAUUSD frozen candidate and returns outcomes,
while the governance pointer (ACTIVE_VERSION) is left untouched. This targets `collect("spine", …)`
directly (one backtest, few entries) rather than the full M4 families comparison — whose winning-control
sweep over all 47k bars is what makes a full pass minutes-long (that full pass is the driver's job).

Marked `slow` (~30-60s for the backtest) and NOT in the default CI subset. SKIP if the corpus is absent.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "data" / "mt5" / "XAUUSD_M15.csv"

pytestmark = [pytest.mark.research_integrity, pytest.mark.slow]


@pytest.mark.skipif(not _CORPUS.exists(), reason="gitignored XAUUSD frozen candidate not present")
def test_spine_collect_runs_on_frozen_candidate_without_active_version_drift(monkeypatch):
    import research.controls  # noqa: F401  (register controls)
    import research.hypotheses  # noqa: F401  (register spine)
    from config_layer.production_config import get_active_version
    from data_ingestion.xauusd_phase1_candidate import guard_xauusd_csv_path
    from research.config import ResearchConfig
    from research.runner import HypothesisRunner

    spine_cfg = "configs/research/research_config_spine_xauusd.json"
    monkeypatch.setenv("RESEARCH_SPINE_CONFIG", spine_cfg)

    before = get_active_version()
    cfg = ResearchConfig.from_file(spine_cfg)
    runner = HypothesisRunner(cfg)
    guarded = guard_xauusd_csv_path("data/XAUUSD_M15.csv", "XAUUSD")
    assert guarded.replace("\\", "/").endswith("data/mt5/XAUUSD_M15.csv")

    per = runner.collect("spine", {"XAUUSD": guarded})

    # the spine hypothesis produced a (possibly small/empty) outcome list on the frozen candidate
    assert "XAUUSD" in per
    assert isinstance(per["XAUUSD"], list)
    # measuring the spine must NOT move the governance pointer (spine sets PROD_VERSION locally + restores)
    assert get_active_version() == before == "v2_multi_2026_04"

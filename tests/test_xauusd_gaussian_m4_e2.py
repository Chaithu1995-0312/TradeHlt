"""E2 floors: M4 script loads; expect REJECT on negative expectancy arms when ledger present."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research" / "xauusd_gaussian_m4_qualify.py"
LEDGER = ROOT / "results" / "gaussian_xauusd_econ" / "ledger_LATEST.jsonl"
UNITS = ROOT / "results" / "gaussian_xauusd_econ" / "units_LATEST.jsonl"


def _load():
    name = "xauusd_gaussian_m4_qualify"
    if str(ROOT / "src") not in sys.path:
        sys.path.insert(0, str(ROOT / "src"))
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def e2():
    if not SCRIPT.exists():
        pytest.skip("E2 script missing")
    return _load()


def test_e2_module_constants(e2):
    assert e2.PHASE == "E2_M4_QUALIFY"
    assert "ECONOMIC_AUTHORITY" in e2.AUTHORITY or "RESEARCH" in e2.AUTHORITY
    assert "nb_top_decile" in e2.HYPOTHESES
    assert e2.CONTROL_ARM == "random_match_n"


@pytest.mark.skipif(not (LEDGER.exists() and UNITS.exists()), reason="E0/E1 artifacts missing")
def test_e2_build_outcomes_chronological(e2):
    ledger = e2._load_jsonl(LEDGER)
    units = e2._load_jsonl(UNITS)
    units_by_key = {e2._unit_key(u): u for u in units}
    outs = e2.build_outcomes_for_arm(ledger, units_by_key, "all_units")
    assert len(outs) == 3247
    # chronological non-decreasing timestamps
    ts = [o.signal.timestamp for o in outs]
    assert ts == sorted(ts)


@pytest.mark.skipif(not (LEDGER.exists() and UNITS.exists()), reason="E0/E1 artifacts missing")
def test_e2_m4_rejects_negative_expectancy(e2, tmp_path):
    """Smoke: run M4 with reduced permutations; primary arms must not PROMOTE."""
    rc = e2.main(
        [
            "--ledger",
            str(LEDGER),
            "--units",
            str(UNITS),
            "--out-dir",
            str(tmp_path),
            "--n-permutations",
            "50",
        ]
    )
    assert rc == 0
    mans = list(tmp_path.glob("e2_m4_manifest_*.json"))
    assert mans
    m = json.loads(mans[0].read_text(encoding="utf-8"))
    assert m["cohort"]["economic_authority_granted"] is False
    assert m["cohort"]["any_promote"] is False
    # all_units / top should REJECT on expectancy (E[R]<0)
    for hyp in ("all_units", "nb_top_decile"):
        if hyp in m["results"]:
            assert m["results"][hyp]["verdict"] in ("REJECT", "INSUFFICIENT")
            if m["results"][hyp]["verdict"] == "REJECT":
                assert any(
                    "gate2_expectancy" in r or "expectancy" in r.lower()
                    for r in m["results"][hyp]["reject_reasons"]
                )

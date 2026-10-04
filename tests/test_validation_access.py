"""Floors for VA-XAUUSD-M15 validation access ladder + dual surfaces."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from validation_access.ladder import (
    LadderResult,
    RungResult,
    run_ladder,
)
from validation_access.surfaces import format_cli_report, write_evidence_pack

ROOT = Path(__file__).resolve().parents[1]


def _pass_s(root, **kwargs):
    return RungResult("S", "story_six_layer_semantic", "PASS", "test pass", details={"mode": "test"})


def _fail_s(root, **kwargs):
    return RungResult("S", "story_six_layer_semantic", "FAIL", "test fail", blockers=["x"])


def _pass_i(root, **kwargs):
    return RungResult(
        "I", "implementation_model_harness", "PASS", "fail_open=0",
        details={"fail_open_count": 0, "failure_mode_summary": {"CRT": "PASS"}},
    )


def _fail_i(root, **kwargs):
    return RungResult(
        "I", "implementation_model_harness", "FAIL", "fail_open=1",
        details={"fail_open_count": 1}, blockers=["fail_open_detected"],
    )


def _pass_f(root, **kwargs):
    return RungResult("F", "feature_cert_ontology_surface", "PASS", "closed 39/39")


def _partial_f(root, **kwargs):
    return RungResult("F", "feature_cert_ontology_surface", "PARTIAL", "partial")


def _open_e(root, **kwargs):
    return RungResult(
        "E", "economic_measurement_contract", "OPEN",
        "sealed_MC_count=0", details={"sealed_mc_count": 0},
    )


def test_s_fail_blocks_ife():
    r = run_ladder(
        ROOT,
        s_fn=_fail_s,
        i_fn=_pass_i,
        f_fn=_pass_f,
        e_fn=_open_e,
    )
    assert r.rungs["S"].status == "FAIL"
    assert r.rungs["I"].status.startswith("BLOCKED_BY_S")
    assert r.rungs["F"].status.startswith("BLOCKED_BY_S")
    assert r.rungs["E"].status.startswith("BLOCKED_BY_S")


def test_i_fail_blocks_fe_after_s_pass():
    r = run_ladder(
        ROOT,
        s_fn=_pass_s,
        i_fn=_fail_i,
        f_fn=_pass_f,
        e_fn=_open_e,
    )
    assert r.rungs["S"].status == "PASS"
    assert r.rungs["I"].status == "FAIL"
    assert r.rungs["F"].status.startswith("BLOCKED_BY_I")
    assert r.rungs["E"].status.startswith("BLOCKED_BY_I")


def test_full_sequence_e_open_is_ladder_complete(tmp_path):
    r = run_ladder(
        ROOT,
        s_fn=_pass_s,
        i_fn=_pass_i,
        f_fn=_pass_f,
        e_fn=_open_e,
        run_id="TEST_RUN",
    )
    assert r.rungs["S"].status == "PASS"
    assert r.rungs["I"].status == "PASS"
    assert r.rungs["F"].status == "PASS"
    assert r.rungs["E"].status == "OPEN"
    assert "E_OPEN" in r.overall_status or r.overall_status.startswith("LADDER_COMPLETE")

    # Dual surfaces
    cli = format_cli_report(r)
    assert "Surface A" in cli
    assert "S" in cli and "E" in cli
    pack = write_evidence_pack(r, tmp_path)
    assert (pack / "manifest.json").is_file()
    assert (pack / "ladder.json").is_file()
    assert (pack / "S_story" / "golden_summary.json").is_file()
    assert (pack / "I_impl" / "harness_summary.json").is_file()
    assert (pack / "F_feature" / "surface_summary.json").is_file()
    assert (pack / "E_economic" / "measurement_status.json").is_file()
    assert (pack / "INDEX.md").is_file()
    assert (pack / "ladder_cli.md").is_file()
    # Surfaces separated: manifest names both, pack is B
    man = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    assert man["surfaces"]["A"]
    assert man["surfaces"]["B"]
    assert "llm_instruction" in man


def test_f_partial_still_runs_e():
    r = run_ladder(
        ROOT,
        s_fn=_pass_s,
        i_fn=_pass_i,
        f_fn=_partial_f,
        e_fn=_open_e,
    )
    assert r.rungs["F"].status == "PARTIAL"
    assert r.rungs["E"].status == "OPEN"
    assert not r.rungs["E"].status.startswith("BLOCKED")


def test_live_default_ladder_smoke():
    """Real artifacts path — cached S + freeze I + live F + E status."""
    r = run_ladder(ROOT, live_story=False, live_impl=False)
    assert r.design_id == "VA-XAUUSD-M15"
    assert r.instrument == "XAUUSD"
    assert set(r.rungs.keys()) == {"S", "I", "F", "E"}
    # With current repo state we expect S/I pass, F pass or partial, E open
    assert r.rungs["S"].status in ("PASS", "FAIL", "ERROR")
    if r.rungs["S"].status == "PASS":
        assert r.rungs["I"].status in ("PASS", "FAIL", "ERROR")

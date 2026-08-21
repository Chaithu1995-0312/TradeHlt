"""Floor for MC-VCRT-XAUUSD-M15-V2 — the Visual CRT re-measurement (F-083 / F-084).

Guards the four properties that make V2 a legitimate re-measurement rather than a second look
that shopped for a better number:

  1. V2 differs from V1 in exactly the two declared measurement surfaces (costs, exits); every
     other frozen dimension is carried over byte-identically.
  2. The controls resolve on the SAME cost and exit basis as the arm they judge.
  3. The OOS split honours its declared embargo and purge, and the groups partition the entries.
  4. No economic authority is claimed, whatever the numbers say.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

INSTANCES = _ROOT / "configs" / "research" / "measurement_contracts" / "instances"
V1_PATH = INSTANCES / "MC-VCRT-XAUUSD-M15-V1.json"
V2_PATH = INSTANCES / "MC-VCRT-XAUUSD-M15-V2.json"
V2_RESULTS = _ROOT / "results" / "visual_crt" / "mc_vcrt_xauusd_m15_v2"


def _v1() -> dict:
    return json.loads(V1_PATH.read_text(encoding="utf-8"))


def _v2() -> dict:
    return json.loads(V2_PATH.read_text(encoding="utf-8"))


# ── 1. exactly two measurement surfaces differ ───────────────────────────────

FROZEN_SURFACES = ("population", "features", "labels", "pipeline_identity",
                   "prohibited_substitutions", "experiment_id", "schema_version")


@pytest.mark.parametrize("surface", FROZEN_SURFACES)
def test_frozen_surfaces_are_byte_identical_to_v1(surface: str):
    """A re-measurement that quietly moved the population would not be a re-measurement."""
    a = json.dumps(_v1().get(surface), sort_keys=True)
    b = json.dumps(_v2().get(surface), sort_keys=True)
    assert a == b, f"{surface} drifted between V1 and V2 — it is a frozen dimension"


def test_the_two_declared_surfaces_did_change():
    v1, v2 = _v1(), _v2()
    assert v1["costs"]["cost_model_id"] != v2["costs"]["cost_model_id"]
    assert v2["costs"]["cost_model_id"].startswith("CM-XAUUSD-COMPONENT-MEASURED")
    assert v1["exits"]["exit_model_id"] != v2["exits"]["exit_model_id"]
    assert v2["exits"]["exit_model_id"] == "EX-VCRT-INTRABAR-ADVERSE-V2"
    # The frozen schema has no `ontology_id` slot; the ids are declared in the free text the
    # schema does allow, so they are asserted there.
    blob = " ".join(c["bps_or_formula"] for c in v2["costs"]["components"])
    assert "SEM-015" in blob
    assert "SEM-016" in v2["exits"]["intrabar_rule"]


def test_splits_are_carried_over_verbatim():
    """V1 DECLARED the split and never executed it. V2 executes it — it must not redefine it."""
    assert _v2()["splits"] == _v1()["splits"], (
        "split parameters must be byte-identical; V2 is the first EXECUTION, not a new definition"
    )


def test_metrics_changed_only_by_extending_the_success_gate():
    v1, v2 = _v1(), _v2()
    for key, value in v1["metrics"].items():
        if key == "success_gate":
            assert v2["metrics"][key].startswith(value), (
                "success_gate must be EXTENDED, never rewritten — V1's wording is the pre-registration"
            )
            continue
        assert json.dumps(v2["metrics"][key], sort_keys=True) == json.dumps(value, sort_keys=True), (
            f"metrics.{key} was REDEFINED; V2 may only append"
        )
    for name in ("random_entry", "long_only"):
        assert name in v2["metrics"]["success_gate"]


def test_kill_criteria_and_prohibitions_survive():
    v1, v2 = _v1(), _v2()
    assert v2["metrics"]["kill_criteria"] == v1["metrics"]["kill_criteria"]
    assert v2["prohibited_substitutions"] == v1["prohibited_substitutions"]


def test_v2_records_that_it_supersedes_only_the_models_not_the_verdict():
    """The schema has no `supersedes` slot, so the statement lives in authority.note."""
    note = _v2()["authority"]["note"]
    assert "SUPERSEDES MC-VCRT-XAUUSD-M15-V1" in note
    assert "VERDICT is NOT superseded" in note
    assert "gross" in note.lower()


# ── 2. no economic authority ─────────────────────────────────────────────────

def test_v2_claims_no_economic_authority():
    v2 = _v2()
    assert v2["authority"]["economic_admissible"] is False
    assert v2["trust_status"]["economic_claims_allowed"] is False
    assert v2["trust_status"]["mt00"] == "UNRUN"
    assert "not registrable as an economic edge" in v2["authority"]["note"].lower()


def test_v2_declares_its_measurement_weaknesses():
    risks = " ".join(_v2()["trust_status"]["open_risks_non_blocking"]).lower()
    assert "n=7" in risks, "the small stop-fill sample must stay declared"
    assert "proxy" in risks, "the entry-slippage proxy must stay declared"
    assert "replication" in risks, "re-use of V1's corpus must stay declared"


def test_cost_provenance_hash_is_recomputed_not_trusted():
    """A provenance string nobody recomputes is a comment, not evidence."""
    import hashlib
    import re

    blob = " ".join(c["bps_or_formula"] for c in _v2()["costs"]["components"])
    path_m = re.search(r"((?:results/)[\w./-]+\.json)", blob)
    sha_m = re.search(r"sha256\s+([0-9a-f]{64})", blob)
    assert path_m and sha_m, "cost components must declare a manifest path + sha256"
    manifest = _ROOT / path_m.group(1)
    assert manifest.is_file(), f"cost provenance manifest missing: {path_m.group(1)}"
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == sha_m.group(1)


# ── 3. split mechanics ───────────────────────────────────────────────────────

from research.visual_crt.controls import (  # noqa: E402
    EMBARGO_BARS,
    rows_for,
    single_holdout_chronologic,
)
from research.visual_crt.driver import LedgerRow  # noqa: E402


def _row(i: int, ts: str) -> LedgerRow:
    return LedgerRow(
        arm="A", instrument="XAUUSD", entry_ts=ts, entry_index=i, direction="long",
        entry=100.0, sl_atr_mult=1.0, tp_atr_mult=2.0, atr_abs=1.0, pool_kind="pdh",
        pool_price=100.0, sweep_bar_index=i - 1, sweep_price=100.0,
        displacement_bar_index=i, outcome="TP_HIT", rr_gross=1.0, rr_net=0.9,
        mfe=1.0, mae=0.0, duration_candles=3, corpus_path="x", corpus_sha256="y",
        contract_id="MC-VCRT-XAUUSD-M15-V2", sem_012_version=2,
    )


def _rows(n: int, stride: int) -> list[LedgerRow]:
    return [_row(i * stride, datetime(2024, 1, 1, 0, 0).isoformat() + f"-{i:04d}")
            for i in range(n)]


def test_split_groups_partition_the_entries():
    rows = _rows(100, stride=500)
    m = single_holdout_chronologic(rows)
    assert sum(m["counts"].values()) == m["n"] == 100
    ids = set(m["is"]) | set(m["oos"]) | set(m["purged"]) | set(m["embargoed"])
    assert len(ids) == 100, "groups must be disjoint and cover every entry"


def test_split_purges_horizon_overlap_and_embargoes_the_boundary():
    """Entries packed 1 bar apart: everything near the OOS boundary must be dropped."""
    rows = _rows(100, stride=1)
    m = single_holdout_chronologic(rows, horizon_bars=40)
    start = m["oos_start_entry_index"]
    for idx in m["is"]:
        assert idx + 40 < start, "an IS entry's exit horizon reaches into OOS (leak)"
        assert start - idx > EMBARGO_BARS, "an IS entry sits inside the embargo"
    assert m["counts"]["purged"] > 0 and m["counts"]["embargoed"] > 0


def test_oos_is_the_chronological_tail():
    rows = _rows(50, stride=500)
    m = single_holdout_chronologic(rows, oos_fraction=0.20)
    assert m["counts"]["oos"] == 10
    assert min(m["oos"]) > max(m["is"] + m["purged"] + m["embargoed"])


def test_rows_for_rejects_unknown_group():
    with pytest.raises(ValueError, match="unknown split group"):
        rows_for(_rows(5, 100), single_holdout_chronologic(_rows(5, 100)), "train")


# ── 4. control fairness ──────────────────────────────────────────────────────

def test_controls_declared_to_resolve_on_the_same_basis():
    """Scoring a control on a different basis than its arm would rig the comparison."""
    gate = _v2()["metrics"]["success_gate"]
    assert "SAME forward_walk" in gate
    assert "SAME cost model" in gate
    assert _v2()["splits"]["seed"] is not None, "the control draw must be reproducible"
    assert "POINT-ESTIMATE" in gate, (
        "the gate must state that 'beats' is a point-estimate comparison, not a significance test"
    )


@pytest.mark.skipif(not (V2_RESULTS / "metrics.json").is_file(), reason="V2 not yet run")
def test_run_artifacts_are_complete_and_honest():
    m = json.loads((V2_RESULTS / "metrics.json").read_text(encoding="utf-8"))
    assert m["contract_id"] == "MC-VCRT-XAUUSD-M15-V2"
    for artifact in ("split_manifest.json", "population_fingerprint.json",
                     "cost_exit_fixture.json", "summary.json",
                     "ledger_arm_A.jsonl", "ledger_arm_B.jsonl"):
        assert (V2_RESULTS / artifact).is_file(), f"declared artifact missing: {artifact}"
    for arm in ("A", "B"):
        assert m["controls"][arm]["long_only"]["n"] > 0
        assert m["controls"][arm]["random_entry"]["n"] > 0
        assert m["splits"][arm]["counts"]["oos"] > 0
    assert "economic_claims_allowed=False" in m["authority"]


@pytest.mark.skipif(not (V2_RESULTS / "ledger_arm_A.jsonl").is_file(), reason="V2 not yet run")
def test_adverse_fill_only_changed_prices_never_triggers():
    """The fill model must not move WHICH bar exits — only the price it exits at."""
    v1_dir = _ROOT / "results" / "visual_crt" / "mc_vcrt_xauusd_m15_v1"
    for arm in ("A", "B"):
        a = [json.loads(x) for x in (v1_dir / f"ledger_arm_{arm}.jsonl").read_text(encoding="utf-8").splitlines()]
        b = [json.loads(x) for x in (V2_RESULTS / f"ledger_arm_{arm}.jsonl").read_text(encoding="utf-8").splitlines()]
        assert len(a) == len(b)
        for x, y in zip(a, b):
            assert x["entry_index"] == y["entry_index"]
            assert x["outcome"] == y["outcome"]
            assert x["duration_candles"] == y["duration_candles"]
        stops = [y for y in b if y["outcome"] == "SL_HIT"]
        assert stops and all(s["rr_gross"] < -1.0 for s in stops), (
            "every V2 stop must cost MORE than the nominal 1R; V1 booked all of them at "
            "exactly -1.000000R, which is the SEM-016 defect"
        )

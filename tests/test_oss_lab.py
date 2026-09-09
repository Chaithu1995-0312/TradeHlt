"""Floor tests for OSS Lab scaffold (registry, contracts, metrics, adapters).

Authority: RESEARCH_LAB_ONLY. No production spine wiring asserted.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from oss_lab.adapters.codebase_memory import CodebaseMemoryAdapter
from oss_lab.adapters.finrlx import FinRLXAdapter
from oss_lab.adapters.infigraph import InfigraphAdapter
from oss_lab.adapters.lean import LeanAdapter
from oss_lab.adapters.nautilus import NautilusAdapter
from oss_lab.adapters.qlib import QlibAdapter
from oss_lab.adapters.tradelatest import TradelatestBaselineAdapter
from oss_lab.adapters.vectorbt import VectorBTAdapter
from oss_lab.contracts.dataset_manifest import XAUUSD_M15_PHASE1_PRIMARY
from oss_lab.contracts.presence import Presence
from oss_lab.contracts.structural_fact import StructuralFactRecord
from oss_lab.contracts.trade_record import BenchmarkTradeRecord, Side
from oss_lab.metrics.canonical import compute_canonical_metrics
from oss_lab.registry.loader import OSSRegistryError, load_registry
from oss_lab.runners.lookahead_cert import compare_snapshots
from oss_lab.runners.normalize_demo import run_demo


def test_registry_loads_and_validates():
    reg = load_registry()
    assert reg.summary()["count"] >= 9
    assert "OSS-QLIB" in reg.records
    assert "OSS-NAUTILUS" in reg.records
    assert "OSS-FINRLX" in reg.records
    assert "OSS-CODEBASE-MEMORY" in reg.records
    assert "OSS-LEAN" in reg.records
    assert "OSS-INFIGRAPH" in reg.records
    assert "OSS-VECTORBT" in reg.records
    assert "OSS-RIG-METHOD" in reg.records
    assert reg.get("OSS-TRADLATEST-BASELINE")["decision"] == "APPROVED_FOR_LAB"
    assert reg.get("OSS-CODEBASE-MEMORY")["trust_tier"] == "T1"
    assert reg.get("OSS-LEAN")["trust_tier"] == "T3"
    assert reg.get("OSS-INFIGRAPH")["trust_tier"] == "T1"
    assert reg.get("OSS-VECTORBT")["decision"] == "DEFERRED"
    assert reg.get("OSS-RIG-METHOD")["decision"] == "REFERENCE_ONLY"
    # External production-path OSS stay non-T4
    for oss_id in (
        "OSS-QLIB",
        "OSS-NAUTILUS",
        "OSS-FINRLX",
        "OSS-CODEBASE-MEMORY",
        "OSS-LEAN",
        "OSS-INFIGRAPH",
        "OSS-VECTORBT",
    ):
        rec = reg.get(oss_id)
        assert rec["trust_tier"] in ("T0", "T1", "T2", "T3")
        assert rec["trust_tier"] != "T4"
        assert rec["forbidden_surfaces"]


def test_external_t4_forbidden(tmp_path):
    bad = {
        "oss_id": "OSS-EVIL",
        "name": "Evil",
        "repository": "http://example.invalid",
        "version": "0",
        "commit_or_tag": "UNKNOWN",
        "license": "MIT",
        "license_obligations": [],
        "security_status": "NOT_ASSESSED",
        "maintenance_status": "UNKNOWN",
        "purpose": "x",
        "capabilities": ["x"],
        "integration_role": "PRODUCTION_AUTHORITY",
        "trust_tier": "T4",
        "allowed_surfaces": [],
        "forbidden_surfaces": ["configs/production"],
        "input_contract": "x",
        "output_contract": "x",
        "adapter": "NOT_BUILT",
        "tests": [],
        "certification_status": "NOT_STARTED",
        "provenance": {"discovered_utc": "2026-01-01T00:00:00Z", "discovered_by": "t", "sources": ["t"]},
        "known_risks": [],
        "decision": "DISCOVERED",
        "decision_reason": "t",
        "lifecycle_status": "DISCOVERED",
    }
    p = tmp_path / "bad.jsonl"
    p.write_text(json.dumps(bad) + "\n", encoding="utf-8")
    with pytest.raises(OSSRegistryError, match="T4"):
        load_registry(p)


def test_dataset_manifest_matches_phase1_binding():
    m = XAUUSD_M15_PHASE1_PRIMARY
    assert m.instrument == "XAUUSD"
    assert m.timeframe == "M15"
    assert m.row_count == 47275
    assert m.data_hash.startswith("4d73f5ce")
    assert m.start.startswith("2024-05-22")
    assert m.end.startswith("2026-05-21")
    assert "AUTHORITATIVE" in m.explicitly_not
    assert m.physical_path == "data/mt5/XAUUSD_M15.csv"


def test_tradelatest_adapter_normalizes_without_invention():
    adapter = TradelatestBaselineAdapter()
    adapter.bind_dataset(XAUUSD_M15_PHASE1_PRIMARY)
    rows = [
        {
            "direction": "long",
            "entry": 100.0,
            "sl": 95.0,
            "net_pnl": 2.0,
            "initial_risk": 5.0,
        }
    ]
    trades = adapter.normalize_trades(rows, run_id="t1")
    assert len(trades) == 1
    t = trades[0]
    assert t.side == Side.LONG
    assert t.entry_filled == 100.0
    assert t.net_pnl == 2.0
    # Latency never invented
    assert t.presence_of("decision_latency") == Presence.NOT_APPLICABLE
    # Missing mfe is NOT_AVAILABLE not a fake zero
    assert t.mfe is None
    assert t.presence_of("mfe") == Presence.NOT_AVAILABLE


# Hermetic fixture mirroring TradeJournal.to_csv_rows() column names (backtest_v2.py
# :1102-1172), valued from the real Phase-1 artifact trade CRT-0001. Deliberately NOT
# read from results/ — that tree is run-scoped, not a stable fixture.
_REAL_LEDGER_ROW = {
    "trade_id": "CRT-0001",
    "instrument": "XAUUSD",
    "direction": "LONG",
    "entry_raw": "2318.21",
    "entry_fill": "2318.5805019218947",
    "sl": "2317.4565714285714",
    "tp1": "2319.3401428571433",
    "tp2": "2319.7168571428574",
    "exit_fill": "2318.5374926599543",
    "exit_reason": "STOPPED",
    "opened_at": "2024-06-17T15:00:00",
    "closed_at": "2024-06-17T15:30:00",
    "duration_candles": "2",
    "pnl_pips_raw": "56.5",
    "pnl_pips_net": "-4.3",
    "pnl_rr_raw": "0.5028",
    "pnl_rr_net": "-0.0383",
    "slippage_pips": "14.41",
    "spread_pips": "46.39",
    "capital_before": "100000.0",
    "capital_after": "99961.73",
    "position_size": "889.73",
    "risk_score": "0.4308",
    "session": "3.0",
    "htf_id": "XAUUSD-HTF-000425",
    "config_version": "v2_multi_2026_04",
    "shadow_used": "1",
    # canonical feature columns — must be parked in the sidecar, never contract fields
    "rsi_14": "48.15825271606445",
    "body_ratio": "0.4976303279399872",
}


def _normalize_real_row():
    adapter = TradelatestBaselineAdapter()
    adapter.bind_dataset(XAUUSD_M15_PHASE1_PRIMARY)
    return adapter.normalize_trades([_REAL_LEDGER_ROW], run_id="real-1")[0]


def test_real_ledger_net_pnl_is_money_not_r():
    """net_pnl must come from the capital delta (account currency), never pnl_rr_net."""
    t = _normalize_real_row()
    assert t.net_pnl == pytest.approx(-38.27, abs=1e-9)
    assert t.presence_of("net_pnl") == Presence.PRESENT
    assert "capital_after" in (t.field_provenance["net_pnl"].native_field or "")


def test_r_valued_pnl_is_never_accepted_as_money():
    """A row carrying only R-valued PnL leaves net_pnl NOT_AVAILABLE (honest gap)."""
    adapter = TradelatestBaselineAdapter()
    rows = [{"direction": "long", "entry": 100.0, "sl": 95.0,
             "pnl_rr_net": -0.5, "rr_achieved": -0.5}]
    t = adapter.normalize_trades(rows, run_id="r")[0]
    assert t.net_pnl is None
    assert t.presence_of("net_pnl") == Presence.NOT_AVAILABLE


def test_real_ledger_initial_risk_is_derived_money():
    """initial_risk = |entry_fill - sl| * position_size, in the same unit as net_pnl."""
    t = _normalize_real_row()
    assert t.initial_risk == pytest.approx(1000.0, abs=0.01)  # 1% of 100k, 2dp-bounded
    prov = t.field_provenance["initial_risk"]
    assert prov.presence == Presence.PRESENT
    assert prov.native_field.startswith("derived:")
    assert "precision bounded" in prov.reason
    # Must NOT be the CRT decision-confidence score
    assert t.initial_risk != pytest.approx(float(_REAL_LEDGER_ROW["risk_score"]))


def test_real_ledger_tp_ladder_is_not_applicable():
    """tp1->tp2 is a sequential ladder; a single scalar cannot represent it."""
    t = _normalize_real_row()
    assert t.tp is None
    assert t.presence_of("tp") == Presence.NOT_APPLICABLE
    reason = t.field_provenance["tp"].reason
    assert "multi-leg" in reason and "cannot represent" in reason


def test_real_ledger_testimony_stays_in_sidecar():
    """CRT-specific fields and feature columns never enter the comparable contract."""
    t = _normalize_real_row()
    tl = t.adapter_meta["tradelatest"]
    assert tl["risk_score"] == "0.4308"
    assert tl["htf_id"] == "XAUUSD-HTF-000425"
    assert set(tl["feature_columns"]) == {"rsi_14", "body_ratio"}
    # tp legs preserved as testimony even though the contract field is NOT_APPLICABLE
    assert tl["tp1"] and tl["tp2"]


def test_real_ledger_expectancy_r_matches_engine_r_multiple():
    """Independent path check: money net_pnl / derived initial_risk == engine pnl_rr_net."""
    t = _normalize_real_row()
    m = compute_canonical_metrics([t])
    assert m.expectancy == pytest.approx(-38.27, abs=0.01)          # money
    assert m.status["expectancy_r"] == "MEASURED"
    assert m.expectancy_r == pytest.approx(
        float(_REAL_LEDGER_ROW["pnl_rr_net"]), abs=1e-4
    )


def test_canonical_metrics_pf_and_expectancy():
    trades = [
        BenchmarkTradeRecord(
            run_id="r", engine="tl", instrument="XAUUSD", timeframe="M15",
            net_pnl=10.0, initial_risk=5.0,
        ),
        BenchmarkTradeRecord(
            run_id="r", engine="tl", instrument="XAUUSD", timeframe="M15",
            net_pnl=-5.0, initial_risk=5.0,
        ),
    ]
    for t in trades:
        t.mark("net_pnl", Presence.PRESENT)
        t.mark("initial_risk", Presence.PRESENT)
    m = compute_canonical_metrics(trades)
    assert m.n_trades_completed == 2
    assert m.profit_factor == pytest.approx(2.0)
    assert m.expectancy == pytest.approx(2.5)
    assert m.expectancy_r == pytest.approx(0.5)
    assert m.status["sharpe"] == "UNKNOWN"  # no return_frequency
    assert m.authority == "RESEARCH_LAB_ONLY"


def test_sharpe_not_invented_without_frequency():
    trades = [
        BenchmarkTradeRecord(
            run_id="r", engine="tl", instrument="X", timeframe="M15", net_pnl=1.0
        ),
        BenchmarkTradeRecord(
            run_id="r", engine="tl", instrument="X", timeframe="M15", net_pnl=-1.0
        ),
    ]
    for t in trades:
        t.mark("net_pnl", Presence.PRESENT)
    m = compute_canonical_metrics(trades)
    assert m.sharpe is None
    assert m.status["sharpe"] == "UNKNOWN"


def test_external_adapters_are_stubs():
    for Adapter in (QlibAdapter, NautilusAdapter, FinRLXAdapter, LeanAdapter, VectorBTAdapter):
        a = Adapter()
        cap = a.capability()
        assert cap.dependency_installed is False
        assert cap.can_run_backtest is False
        with pytest.raises(NotImplementedError):
            a.normalize_trades([], run_id="x")


def test_repo_intel_adapters_are_stubs():
    for Adapter in (CodebaseMemoryAdapter, InfigraphAdapter):
        a = Adapter()
        cap = a.capability()
        assert cap.dependency_installed is False
        with pytest.raises(NotImplementedError):
            a.normalize_facts([], run_id="x")


def test_structural_fact_record_shape():
    f = StructuralFactRecord(
        run_id="r1",
        engine="codebase_memory",
        fact_type="CALLS",
        source_symbol="EngineRunner.run",
        target_symbol="FusionEngine.evaluate",
        source_path="src/core/engine_runner.py",
    )
    f.mark("source_symbol", Presence.PRESENT, source_adapter="codebase_memory")
    d = f.to_dict()
    assert d["fact_type"] == "CALLS"
    assert d["field_provenance"]["source_symbol"]["presence"] == "PRESENT"


def test_monitor_scenarios_exist():
    for name in (
        "bm_repo_intel_head_to_head.json",
        "bm_execution_three_way.json",
    ):
        p = _REPO / "oss_lab" / "scenarios" / name
        data = json.loads(p.read_text(encoding="utf-8"))
        assert data["authority"] == "RESEARCH_LAB_ONLY"


def test_evaluation_queue_exists():
    p = _REPO / "oss_lab" / "governance" / "evaluation_queue.md"
    text = p.read_text(encoding="utf-8")
    assert "OSS-CODEBASE-MEMORY" in text
    assert "Can we reuse" in text


def test_architecture_approval_and_gate_artifacts():
    root = _REPO / "oss_lab" / "governance"
    approval = (root / "ARCHITECTURE_APPROVAL.md").read_text(encoding="utf-8")
    assert "ARCHITECTURALLY APPROVED" in approval
    assert "Semantic OS mutation" in approval
    gate = (root / "codebase_memory_gate.md").read_text(encoding="utf-8")
    assert "APPROVED_FOR_LAB" in gate
    assert "NO semantic_os" in gate or "no Semantic OS" in gate.lower()
    assert "G1 — License — **PASS**" in gate
    assert "G2 — Version pin — **PASS**" in gate
    corpus = json.loads(
        (_REPO / "oss_lab" / "scenarios" / "repo_intel_qa_corpus_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert corpus["corpus_id"] == "REPO-INTEL-QA-V1"
    assert len(corpus["items"]) >= 12
    assert corpus["authority"] == "RESEARCH_LAB_ONLY"
    report = _REPO / "oss_lab" / "reports" / "repo_intel_benchmark_template.md"
    assert report.is_file()
    assert "Semantic OS mutated?" in report.read_text(encoding="utf-8")


def test_codebase_memory_g1_g3_pin_and_evidence():
    reg = load_registry()
    rec = reg.get("OSS-CODEBASE-MEMORY")
    assert rec["version"] == "v0.10.2"
    assert "b377c62a4e8b7ad64ccd295e4aa88abc8d275180" in rec["commit_or_tag"]
    assert rec["license"] == "MIT"
    assert rec["decision"] == "BENCHMARKED"
    assert rec["lifecycle_status"] == "BENCHMARKED"
    assert rec["certification_status"] == "LAB_ONLY"
    assert rec["output_contract"].endswith("StructuralFactRecord")
    for surface in (
        "docs/governance/semantic_os",
        "src/core",
        "configs/production",
    ):
        assert surface in rec["forbidden_surfaces"]
    ev = _REPO / "oss_lab" / "evidence" / "repo_intel" / "codebase_memory_v0.10.2"
    evidence = json.loads((ev / "G1_G3_gate_evidence.json").read_text(encoding="utf-8"))
    assert evidence["result"]["G1"] == "PASS"
    assert evidence["result"]["G2"] == "PASS"
    assert evidence["result"]["G3"].startswith("PASS")
    assert evidence["pin"]["windows_amd64_sha256"] == (
        "8f08e5c5b480e625adf9d4560765a860d493a690df6ded5b94127283ec5b660a"
    )
    g4g6 = json.loads((ev / "G4_G6_gate_evidence.json").read_text(encoding="utf-8"))
    assert g4g6["result"]["G4"] == "PASS"
    assert g4g6["result"]["G5"] == "PASS"
    assert g4g6["result"]["G6"] == "PASS"
    assert g4g6["lifecycle_after"] == "APPROVED_FOR_LAB"
    assert g4g6["result"]["SLSA_residual"] == "ATTEMPTED_TOOLS_ABSENT"
    assert (ev / "LICENSE").is_file()
    assert (ev / "checksums.txt").is_file()
    assert (ev / "REPO_INTEL_RUN_MANIFEST_PLAN.json").is_file()
    # Verified archive lives under results/ (not activated)
    zip_path = (
        _REPO
        / "results"
        / "oss_lab"
        / "repo_intel"
        / "codebase_memory_v0.10.2"
        / "codebase-memory-mcp-windows-amd64.zip"
    )
    assert zip_path.is_file()
    bundle = zip_path.with_suffix(zip_path.suffix + ".bundle")
    # cosign bundle path: .zip.bundle
    bundle = (
        _REPO
        / "results"
        / "oss_lab"
        / "repo_intel"
        / "codebase_memory_v0.10.2"
        / "codebase-memory-mcp-windows-amd64.zip.bundle"
    )
    assert bundle.is_file()
    isolation = (
        _REPO / "oss_lab" / "adapters" / "codebase_memory" / "INSTALL_ISOLATION.md"
    )
    assert isolation.is_file()
    assert "tools/oss_lab/codebase-memory/v0.10.2" in isolation.read_text(encoding="utf-8")
    assert (_REPO / "oss_lab" / "adapters" / "codebase_memory" / "lab.cbmignore").is_file()
    assert (_REPO / "results" / "oss_lab" / "repo_intel" / "runs").is_dir()
    assert (_REPO / "tools" / "oss_lab" / "codebase-memory" / "v0.10.2").is_dir()


def test_gate_doc_shows_approved_for_lab():
    gate = (
        _REPO / "oss_lab" / "governance" / "codebase_memory_gate.md"
    ).read_text(encoding="utf-8")
    assert "G4 — Architectural boundary — **PASS**" in gate
    assert "G5 — Benchmark readiness — **PASS**" in gate
    assert "G6 — Lifecycle transition — **PASS**" in gate
    assert "APPROVED_FOR_LAB" in gate
    assert "ATTEMPTED_TOOLS_ABSENT" in gate


def test_ri_qa_milestone_and_sos_compat_gate_designed():
    verdict = (
        _REPO / "oss_lab" / "governance" / "RI_QA_V1_MILESTONE_VERDICT.md"
    ).read_text(encoding="utf-8")
    assert "SUCCESSFUL RESEARCH-LAB VALIDATION" in verdict
    assert "not yet a Semantic OS integration" in verdict.lower() or "not SOS" in verdict.lower() or "≠ Semantic OS" in verdict
    assert "FakeFusionEngineV9" in verdict or "negative control" in verdict.lower()
    compat = (
        _REPO / "oss_lab" / "governance" / "RI_SOS_EVIDENCE_COMPATIBILITY.md"
    ).read_text(encoding="utf-8")
    assert "FORBIDDEN" in compat
    assert "Structural correctness" in compat or "structural_correctness" in compat
    assert "read-only" in compat.lower() or "Read-only" in compat
    corpus = json.loads(
        (_REPO / "oss_lab" / "scenarios" / "ri_sos_compat_corpus_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert corpus["corpus_id"] == "RI-SOS-COMPAT-V1"
    assert corpus["status"] in ("DESIGNED_NOT_RUN", "RUN_COMPLETED")
    assert len(corpus["items"]) >= 10
    cats = {i["category"] for i in corpus["items"]}
    for required in (
        "file_identity",
        "call_dependency",
        "journey_reconstruction",
        "boundary_membership",
        "negative_nonexistent",
        "sos_to_implementation",
        "implementation_to_sos",
    ):
        assert required in cats
    # 12/12 lab run must not be registered as SOS write surface
    assert "write docs/governance/semantic_os" in " ".join(corpus["forbidden"]).lower() or any(
        "semantic_os" in f.lower() for f in corpus["forbidden"]
    )


def test_lookahead_compare_detects_divergence():
    run_a = [
        {"timestamp": "2024-01-01T00:00:00", "features": [1, 2], "decision": "HOLD"},
        {"timestamp": "2024-01-01T00:15:00", "features": [3, 4], "decision": "LONG"},
    ]
    run_b_ok = [
        {"timestamp": "2024-01-01T00:00:00", "features": [1, 2], "decision": "HOLD"},
        {"timestamp": "2024-01-01T00:15:00", "features": [9, 9], "decision": "LONG"},  # after cut ok
    ]
    cut = "2024-01-01T00:00:00"
    ok = compare_snapshots(run_a, run_b_ok, cut_timestamp=cut, objects=("features", "decision"))
    assert ok.status == "PASS"

    run_b_bad = [
        {"timestamp": "2024-01-01T00:00:00", "features": [1, 99], "decision": "HOLD"},
        {"timestamp": "2024-01-01T00:15:00", "features": [3, 4], "decision": "LONG"},
    ]
    bad = compare_snapshots(run_a, run_b_bad, cut_timestamp=cut, objects=("features", "decision"))
    assert bad.status == "FAIL"
    assert bad.first_divergent_object == "features"
    assert bad.first_divergent_timestamp == "2024-01-01T00:00:00"


def test_normalize_demo_smoke():
    out = run_demo()
    assert out["n_normalized"] == 2
    assert out["metrics"]["n_trades_completed"] == 2
    assert out["metrics"]["profit_factor"] == pytest.approx(2.0)
    assert out["authority"] == "RESEARCH_LAB_ONLY"


def test_comparison_matrix_template_exists():
    p = _REPO / "oss_lab" / "reports" / "comparison_matrix_template.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["authority"] == "RESEARCH_LAB_ONLY"
    metrics = {m["metric"] for m in data["metrics"]}
    for required in (
        "execution_speed",
        "lookahead_safety",
        "profit_factor",
        "expectancy",
        "reproducibility",
    ):
        assert required in metrics


def test_architecture_doc_exists():
    assert (_REPO / "docs" / "governance" / "OSS_INTEGRATION_ARCHITECTURE.md").is_file()
    assert (_REPO / "docs" / "implementation_plan" / "oss-integration-benchmark-lab.md").is_file()

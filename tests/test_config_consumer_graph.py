"""
Config->consumer graph floor (target-strategy-architecture.md §13 item9 / §14.H).

build_graph() is a pure re-projection of config_reachability.build_report()'s
already-resolved evidence — no new corpus scan. These tests pin that contract.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts" / "analysis"))

from config_reachability import build_graph, build_report  # noqa: E402


def test_graph_is_a_pure_projection_of_the_report():
    report = build_report()
    graph = build_graph(report)
    assert graph["active_version"] == report["active_version"]
    n_keys_with_evidence = sum(1 for k in report["keys"] if k["evidence"])
    n_key_nodes = sum(1 for n in graph["nodes"] if n["type"] == "config_key")
    assert n_key_nodes == len(report["keys"])
    assert n_keys_with_evidence > 0


def test_graph_edges_are_deduplicated_and_well_formed():
    report = build_report()
    graph = build_graph(report)
    seen = set()
    for e in graph["edges"]:
        pair = (e["from"], e["to"])
        assert pair not in seen, f"duplicate edge {pair}"
        seen.add(pair)
        assert e["from"].startswith("cfg:")
        assert e["to"].startswith("file:")


def test_generated_graph_artifacts_exist_and_parse():
    import json
    graph_json = _ROOT / "docs" / "architecture" / "config-consumer-graph.generated.json"
    assert graph_json.is_file(), "run `python scripts/analysis/config_reachability.py --graph` first"
    d = json.loads(graph_json.read_text(encoding="utf-8"))
    assert d["node_count"] == len(d["nodes"])
    assert d["edge_count"] == len(d["edges"])

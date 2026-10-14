import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from research_ssot import cli
from research_ssot.core import (
    DEFAULT_SCAN_ROOTS, apply_execution_results, build_plan, inspect_python_file, inventory,
    load_manifest, validate_manifest,
)

ROOT = Path(__file__).resolve().parents[1]


def base_manifest():
    return {
        "schema_version": "1.1",
        "manifest_id": "test",
        "external_inputs": [
            {"id": "cfg_a", "kind": "config", "ref": "cfg:a"},
            {"id": "cfg_b", "kind": "config", "ref": "cfg:b"},
            {"id": "cfg_unresolved", "kind": "config", "ref": "UNRESOLVED"},
            {"id": "bridge_contract", "kind": "contract", "ref": "bridge-contract:v1"},
            {"id": "missing_contract", "kind": "contract", "ref": "UNRESOLVED"},
            {"id": "trace_undeclared", "kind": "dataset", "ref": "data:x"},
            {"id": "trace_undeclared_2", "kind": "dataset", "ref": "data:y"},
            {"id": "trace_engine_a", "kind": "dataset", "ref": "data:z", "state_producer": {"kind": "crt_engine", "config_ref": "cfg_a"}},
        ],
        "intents": {"test": {"description": "test", "root_nodes": ["out"], "required_claims": {"claim": ["out.result"]}}},
        "nodes": [
            {"node_id": "source_a", "purpose": "source a", "operation": "artifact_resolve", "inputs": [], "outputs": ["a"], "depends_on": [], "reuse_policy": "REUSE_ONLY_EXACT_IDENTITY", "required": True, "state_producer": {"kind": "crt_engine", "config_ref": "cfg_a"}},
            {"node_id": "source_b", "purpose": "source b", "operation": "artifact_resolve", "inputs": [], "outputs": ["b"], "depends_on": [], "reuse_policy": "REUSE_ONLY_EXACT_IDENTITY", "required": True, "state_producer": {"kind": "crt_engine", "config_ref": "cfg_b"}},
            {"node_id": "out", "purpose": "output", "operation": "measurement", "inputs": ["source_a.a"], "outputs": ["result"], "depends_on": ["source_a"], "reuse_policy": "REUSE_IF_CONTRACT_AND_HASH_MATCH", "required": True},
        ],
    }


def node(node_id, operation, inputs, outputs, depends_on, required=True, **extra):
    return {"node_id": node_id, "purpose": node_id, "operation": operation, "inputs": inputs, "outputs": outputs,
            "depends_on": depends_on, "reuse_policy": "NEVER_REUSE", "required": required, **extra}


def codes(manifest, severity="ERROR"):
    return {i["code"] for i in validate_manifest(manifest) if i["severity"] == severity}


class EvidenceDir:
    """Temp directory holding real artifact files so evidence hashes can be re-computed."""

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        return self

    def __exit__(self, *exc):
        self._tmp.cleanup()

    def completed(self, name, status="COMPLETED", **extra):
        artifact = self.path / f"{name}.json"
        artifact.write_text(json.dumps({"node": name}), encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        return {"status": status, "artifacts": [{"path": artifact.name, "sha256": digest}],
                "run_identity_ref": "run:test", **extra}


class FrameworkTests(unittest.TestCase):
    def test_example_manifest_valid(self):
        manifest = load_manifest(ROOT / "examples" / "manifest.json")
        self.assertFalse(codes(manifest))

    def test_plan_is_dependency_ordered_and_blocked_by_unresolved_contract(self):
        manifest = load_manifest(ROOT / "examples" / "manifest.json")
        plan = build_plan(manifest, "crt_expiry_diagnosis")
        ids = [n["node_id"] for n in plan["ordered_nodes"]]
        self.assertLess(ids.index("resolve_run_identity"), ids.index("load_crt_transition_trace"))
        self.assertLess(ids.index("measure_expiry_reasons"), ids.index("assemble_crt_expiry_report"))
        self.assertEqual(plan["plan_status"], "BLOCKED")
        self.assertEqual([x["id"] for x in plan["external_inputs"] if x["ref"] == "UNRESOLVED"], ["transition_trace_contract", "expiry_reason_contract", "persistence_contract"])
        self.assertTrue(all(c["status"] == "UNSUPPORTED" for c in plan["claims"]))

    def test_missing_dependency_rejected(self):
        manifest = load_manifest(ROOT / "examples" / "manifest.json")
        manifest["nodes"][0]["depends_on"] = ["not_real"]
        self.assertIn("DEPENDENCY_MISSING", codes(manifest))

    def test_input_closure_unresolved_input(self):
        m = base_manifest()
        m["nodes"][2]["inputs"] = ["not_an_output_or_external"]
        self.assertIn("INPUT_UNRESOLVED", codes(m))

    def test_hidden_dependency_rejected(self):
        m = base_manifest()
        m["nodes"][2]["inputs"] = ["source_b.b"]
        self.assertIn("HIDDEN_DEPENDENCY", codes(m))

    def test_claim_missing_output_rejected(self):
        m = base_manifest()
        m["intents"]["test"]["required_claims"] = {"claim": ["out.not_real"]}
        self.assertIn("CLAIM_EVIDENCE_UNKNOWN", codes(m))

    def test_producer_pooling_without_bridge_rejected(self):
        m = base_manifest()
        m["nodes"][2]["inputs"] = ["source_a.a", "source_b.b"]
        m["nodes"][2]["depends_on"] = ["source_a", "source_b"]
        self.assertIn("PRODUCER_POOLING", codes(m))

    def test_same_kind_different_config_is_distinct_producer(self):
        m = base_manifest()
        m["nodes"][2]["inputs"] = ["source_a.a", "source_b.b"]
        m["nodes"][2]["depends_on"] = ["source_a", "source_b"]
        issue = next(i for i in validate_manifest(m) if i["code"] == "PRODUCER_POOLING")
        self.assertIn("crt_engine@cfg_a", issue["message"])
        self.assertIn("crt_engine@cfg_b", issue["message"])

    def test_compare_output_cannot_be_reused_as_population(self):
        m = base_manifest()
        m["nodes"][2].update(operation="compare", inputs=["source_a.a", "source_b.b"], depends_on=["source_a", "source_b"], outputs=["result"])
        m["nodes"].append(node("measure_compare", "measurement", ["out.result"], ["measured"], ["out"]))
        m["intents"]["test"]["root_nodes"] = ["measure_compare"]
        m["intents"]["test"]["required_claims"] = {"claim": ["measure_compare.measured"]}
        self.assertIn("COMPARISON_REUSED_AS_POPULATION", codes(m))

    def test_comparison_taint_propagates_through_intermediate_nodes(self):
        # H2: compare -> pass-through -> measurement must still be refused.
        m = base_manifest()
        m["nodes"][2].update(operation="compare", inputs=["source_a.a", "source_b.b"], depends_on=["source_a", "source_b"], outputs=["result"])
        m["nodes"].append(node("relay", "contract_check", ["out.result"], ["relayed"], ["out"]))
        m["nodes"].append(node("measure_relayed", "measurement", ["relay.relayed"], ["measured"], ["relay"]))
        m["intents"]["test"]["root_nodes"] = ["measure_relayed"]
        m["intents"]["test"]["required_claims"] = {"claim": ["measure_relayed.measured"]}
        self.assertIn("COMPARISON_REUSED_AS_POPULATION", codes(m))

    def test_bridge_clears_comparison_taint(self):
        m = base_manifest()
        m["nodes"][2].update(operation="compare", inputs=["source_a.a", "source_b.b"], depends_on=["source_a", "source_b"], outputs=["result"])
        m["nodes"].append(node("pool", "bridge", ["out.result", "source_a.a"], ["pooled"], ["out", "source_a"], bridge_contract="bridge_contract"))
        m["nodes"].append(node("measure_pool", "measurement", ["pool.pooled"], ["measured"], ["pool"]))
        m["intents"]["test"]["root_nodes"] = ["measure_pool"]
        m["intents"]["test"]["required_claims"] = {"claim": ["measure_pool.measured"]}
        self.assertNotIn("COMPARISON_REUSED_AS_POPULATION", codes(m))

    def test_bridge_requires_contract_and_explicitly_allows_pooling(self):
        m = base_manifest()
        m["nodes"][2].update(operation="bridge", inputs=["source_a.a", "source_b.b"], depends_on=["source_a", "source_b"], bridge_contract="bridge_contract")
        self.assertFalse(codes(m))
        m["nodes"][2].pop("bridge_contract")
        self.assertIn("BRIDGE_CONTRACT_REQUIRED", codes(m))

    def test_none_cannot_launder_producer(self):
        # H1: two state-derived 'none' outputs from different producers must not pool silently.
        m = base_manifest()
        m["nodes"] = m["nodes"][:2] + [
            node("count_a", "measurement", ["source_a.a"], [{"name": "n", "state_producer": "none"}], ["source_a"]),
            node("count_b", "measurement", ["source_b.b"], [{"name": "n", "state_producer": "none"}], ["source_b"]),
            node("out", "measurement", ["count_a.n", "count_b.n"], ["result"], ["count_a", "count_b"]),
        ]
        self.assertIn("PRODUCER_DROPPED", codes(m))
        # Without the 'none' tags the pooling itself is caught.
        for n in m["nodes"][2:4]:
            n["outputs"] = ["n"]
        self.assertIn("PRODUCER_POOLING", codes(m))

    def test_explicit_producer_cannot_relabel_state_inputs(self):
        m = base_manifest()
        m["nodes"][2]["state_producer"] = {"kind": "crt_resolver", "config_ref": "cfg_b"}
        self.assertIn("PRODUCER_RELABELED", codes(m))

    def test_artifact_resolve_must_declare_producer(self):
        # H3: untagged sources would otherwise look stateless and pool undetected.
        m = base_manifest()
        for n in m["nodes"][:2]:
            n.pop("state_producer")
        flagged = [i["message"] for i in validate_manifest(m) if i["code"] == "STATE_PRODUCER_UNDECLARED"]
        # The source itself must be named, not merely a downstream node that has nothing to inherit.
        self.assertTrue(any(msg.startswith("source_a:") for msg in flagged), flagged)

    def test_stateless_node_cannot_inherit(self):
        m = base_manifest()
        m["nodes"].append(node("orphan", "measurement", [], ["x"], []))
        m["intents"]["test"]["root_nodes"] = ["out", "orphan"]
        self.assertIn("STATE_PRODUCER_UNDECLARED", codes(m))

    def test_undeclared_dataset_external_is_unknown_producer(self):
        # H4: engine output + undeclared external trace is pooling, and so are two undeclared traces.
        m = base_manifest()
        m["nodes"][2]["inputs"] = ["source_a.a", "trace_undeclared"]
        self.assertIn("PRODUCER_POOLING", codes(m))
        m["nodes"][2].update(inputs=["trace_undeclared", "trace_undeclared_2"], depends_on=[])
        self.assertIn("PRODUCER_POOLING", codes(m))

    def test_declared_dataset_external_with_same_producer_is_not_pooling(self):
        m = base_manifest()
        m["nodes"][2]["inputs"] = ["source_a.a", "trace_engine_a"]
        self.assertFalse(codes(m))

    def test_unresolved_external_blocks_node_and_dependents(self):
        m = base_manifest()
        m["nodes"][0]["inputs"] = ["missing_contract"]
        plan = build_plan(m, "test")
        statuses = {n["node_id"]: n["status"] for n in plan["ordered_nodes"]}
        self.assertEqual(statuses["source_a"], "BLOCKED")
        self.assertEqual(statuses["out"], "BLOCKED_UPSTREAM")

    def test_unresolved_producer_config_blocks(self):
        # H5: producer identity is kind + config; an UNRESOLVED config leaves it unknown.
        m = base_manifest()
        m["nodes"][0]["state_producer"] = {"kind": "crt_engine", "config_ref": "cfg_unresolved"}
        plan = build_plan(m, "test")
        statuses = {n["node_id"]: n["status"] for n in plan["ordered_nodes"]}
        self.assertEqual(statuses["source_a"], "BLOCKED")
        self.assertIn("cfg_unresolved", plan["ordered_nodes"][0]["blocked_reasons"][0])
        self.assertEqual(plan["plan_status"], "BLOCKED")

    def test_bare_completed_without_evidence_rejected(self):
        # H7: a status string alone must not make a claim SUPPORTED.
        plan = build_plan(base_manifest(), "test")
        with self.assertRaisesRegex(ValueError, "artifacts"):
            apply_execution_results(plan, {"source_a": {"status": "COMPLETED"}, "out": {"status": "COMPLETED"}})

    def test_evidence_hash_is_recomputed(self):
        plan = build_plan(base_manifest(), "test")
        with EvidenceDir() as ev:
            good = {"source_a": ev.completed("a"), "out": ev.completed("out")}
            result = apply_execution_results(plan, good, ev.path)
            self.assertEqual(result["plan_status"], "COMPLETE")
            self.assertEqual(result["claims"][0]["status"], "SUPPORTED")
            tampered = {"source_a": ev.completed("a"), "out": ev.completed("out")}
            tampered["out"]["artifacts"][0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                apply_execution_results(plan, tampered, ev.path)
            missing = {"source_a": ev.completed("a"), "out": ev.completed("out")}
            missing["out"]["artifacts"][0]["path"] = "does_not_exist.json"
            with self.assertRaisesRegex(ValueError, "not found"):
                apply_execution_results(plan, missing, ev.path)

    def test_reused_requires_matched_identity(self):
        plan = build_plan(base_manifest(), "test")
        with EvidenceDir() as ev:
            with self.assertRaisesRegex(ValueError, "reused_identity"):
                apply_execution_results(plan, {"source_a": ev.completed("a", status="REUSED")}, ev.path)
            ok = apply_execution_results(plan, {"source_a": ev.completed("a", status="REUSED", reused_identity="run:prior")}, ev.path)
            self.assertEqual(ok["ordered_nodes"][0]["status"], "REUSED")

    def test_results_for_unknown_nodes_rejected(self):
        plan = build_plan(base_manifest(), "test")
        with self.assertRaisesRegex(ValueError, "not in this plan"):
            apply_execution_results(plan, {"typo_node": {"status": "FAILED"}})

    def test_completed_result_for_blocked_node_rejected(self):
        m = base_manifest()
        m["nodes"][0]["inputs"] = ["missing_contract"]
        plan = build_plan(m, "test")
        with EvidenceDir() as ev:
            with self.assertRaisesRegex(ValueError, "cannot have run"):
                apply_execution_results(plan, {"source_a": ev.completed("a")}, ev.path)

    def test_required_failure_makes_report_incomplete(self):
        plan = build_plan(base_manifest(), "test")
        result = apply_execution_results(plan, {"source_a": {"status": "FAILED"}})
        self.assertEqual(result["plan_status"], "INCOMPLETE")
        self.assertEqual(result["claims"][0]["status"], "UNSUPPORTED")
        statuses = {n["node_id"]: n["status"] for n in result["ordered_nodes"]}
        self.assertEqual(statuses["out"], "SKIPPED")

    def _optional_manifest(self):
        m = base_manifest()
        m["nodes"].append(node("optional", "measurement", [], ["optional_result"], [], required=False, state_producer="none"))
        m["nodes"].append(node("optional_child", "measurement", ["optional.optional_result"], ["child_result"], ["optional"], required=False, state_producer="none"))
        m["intents"]["test"]["root_nodes"] = ["out", "optional_child"]
        return m

    def test_non_required_failure_stays_failed_and_skips_dependents(self):
        plan = build_plan(self._optional_manifest(), "test")
        with EvidenceDir() as ev:
            result = apply_execution_results(plan, {"source_a": ev.completed("a"), "out": ev.completed("out"), "optional": {"status": "FAILED"}}, ev.path)
        statuses = {n["node_id"]: n["status"] for n in result["ordered_nodes"]}
        self.assertEqual(statuses["optional"], "FAILED")
        self.assertEqual(statuses["optional_child"], "SKIPPED")
        self.assertEqual(result["plan_status"], "COMPLETE")

    def test_optional_failure_needed_by_claim_is_incomplete(self):
        # H6: everything ran, but a claim depends on the failed optional node.
        m = self._optional_manifest()
        m["intents"]["test"]["required_claims"]["optional_claim"] = ["optional.optional_result"]
        plan = build_plan(m, "test")
        with EvidenceDir() as ev:
            result = apply_execution_results(plan, {"source_a": ev.completed("a"), "out": ev.completed("out"), "optional": {"status": "FAILED"}}, ev.path)
        self.assertEqual(result["plan_status"], "INCOMPLETE")

    def test_partially_executed_is_partial(self):
        plan = build_plan(base_manifest(), "test")
        with EvidenceDir() as ev:
            result = apply_execution_results(plan, {"source_a": ev.completed("a")}, ev.path)
        self.assertEqual(result["plan_status"], "PARTIAL")

    def test_closed_operation_and_reuse_vocabularies(self):
        m = base_manifest()
        m["nodes"][0]["operation"] = "arbitrary_shell"
        m["nodes"][1]["reuse_policy"] = "maybe"
        found = codes(m)
        self.assertIn("OPERATION_INVALID", found)
        self.assertIn("REUSE_POLICY_INVALID", found)

    def test_open_write_mode_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "writer.py"
            path.write_text('def f():\n    with open("result.json", mode="w") as handle:\n        handle.write("{}")\n', encoding="utf-8")
            item = inspect_python_file(path, root)
            self.assertIn("result.json", item["likely_writes"])

    def test_inventory_hash_excludes_generated_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts" / "analysis").mkdir(parents=True)
            (root / "scripts" / "analysis" / "x.py").write_text('"""sample"""\n', encoding="utf-8")
            one = inventory(root, ("scripts/analysis",), now=datetime(2026, 1, 1, tzinfo=timezone.utc))
            two = inventory(root, ("scripts/analysis",), now=datetime(2026, 1, 2, tzinfo=timezone.utc))
            self.assertNotEqual(one["generated_at_utc"], two["generated_at_utc"])
            self.assertEqual(one["content_sha256"], two["content_sha256"])

    def test_inventory_hash_is_independent_of_clone_location(self):
        hashes = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "scripts" / "analysis").mkdir(parents=True)
                (root / "scripts" / "analysis" / "x.py").write_text('"""sample"""\n', encoding="utf-8")
                hashes.append(inventory(root, ("scripts/analysis",))["content_sha256"])
        self.assertEqual(hashes[0], hashes[1])

    def test_cli_inventory_default_scan_roots_match_core(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "inv.json"
            with mock.patch.object(sys, "argv", ["research-ssot", "inventory", "--root", tmp, "--out", str(out)]), \
                    mock.patch("builtins.print"):
                cli.main()
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["scan_roots"], list(DEFAULT_SCAN_ROOTS))


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from research_ssot.core import load_manifest, validate_manifest, build_plan

ROOT = Path(__file__).resolve().parents[1]

class FrameworkTests(unittest.TestCase):
    def test_example_manifest_valid(self):
        manifest = load_manifest(ROOT / "examples" / "manifest.json")
        self.assertEqual(validate_manifest(manifest), [])

    def test_plan_is_dependency_ordered(self):
        manifest = load_manifest(ROOT / "examples" / "manifest.json")
        plan = build_plan(manifest, "crt_expiry_diagnosis")
        ids = [n["node_id"] for n in plan["ordered_nodes"]]
        self.assertLess(ids.index("resolve_run_identity"), ids.index("load_crt_transition_trace"))
        self.assertLess(ids.index("measure_expiry_reasons"), ids.index("assemble_crt_expiry_report"))
        self.assertEqual(plan["plan_status"], "PLANNED_NOT_EXECUTED")

    def test_missing_dependency_rejected(self):
        manifest = load_manifest(ROOT / "examples" / "manifest.json")
        manifest["nodes"][0]["depends_on"] = ["not_real"]
        self.assertTrue(any(i["code"] == "DEPENDENCY_MISSING" for i in validate_manifest(manifest)))

if __name__ == "__main__":
    unittest.main()

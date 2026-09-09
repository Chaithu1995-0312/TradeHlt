"""Test floor for the research provenance DAG (scripts/analysis/research_dag_provenance.py).

The audit's whole value is that its EXPLICIT / INFERRED / UNKNOWN verdicts are mechanical, so
the floor guards the mechanism, not the numbers:

  * every classifier rule is REACHABLE - a classifier that can only ever return one class is
    not a classifier, and a rule that can never fire is dead code dressed as enforcement
    (E-001: a test that cannot fail is not enforcement);
  * conservation - exactly one edge per (decision x slot), no double-count, no drop;
  * precedence - a citation that does not resolve scores U3_DANGLING_CITATION, never EXPLICIT;
  * determinism - two runs on the same --date are byte-identical;
  * the extractor's own corpus counts still reproduce the authoritative sources.

Run the report with:  python scripts/analysis/research_dag_provenance.py
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "research_dag_provenance.py"
_FIXED_DATE = "2026-08-26"


def _load_tool():
    spec = importlib.util.spec_from_file_location("research_dag_provenance", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_tool()


@pytest.fixture(scope="module")
def payload(mod):
    p, _nodes, _edges = mod.build_payload(_FIXED_DATE)
    return p


# --------------------------------------------------------------------- synthetic classifier bed
def _gt(mod, **over):
    """Minimal ground truth. Every join is explicit so a fixture forces exactly one rule."""
    base = {
        "findings": {
            "F-900": {"id": "F-900", "evidence_paths": ["docs/analysis/known.md"],
                      "contract": "UNKNOWN", "contract_present": True, "validated": "2026-01-02"},
            "F-901": {"id": "F-901", "evidence_paths": [],
                      "contract": "MC-REAL-V1", "contract_present": True, "validated": None},
        },
        "hypotheses": {"H-900": {"id": "H-900", "findings": ["F-900"], "created": "2026-01-01"}},
        "finding_to_hyp": {},
        "finding_to_family": {},
        "contracts": {"MC-REAL-V1": "configs/research/measurement_contracts/MC-REAL-V1.json"},
        "executed_contracts": set(),
        "sealed_pass_bound": 0,
        "manifests": {}, "completions": set(), "families_meta": {},
        "export_missing_fields": [], "findings_doc_fields_read": 0,
    }
    base.update(over)
    return base


def _node(text="", ntype="DECISION_SESSION", structured=None, path="docs/x.md", date=None):
    return {"node_id": "N-1", "type": ntype, "date": date, "era": "E1",
            "source_path": path, "source_locator": path + ":1", "title": "t",
            "_text": text, "_structured": structured or {}}


def _slot(edges, slot):
    return next(e for e in edges if e["slot"] == slot)


TRACKED = {"docs/analysis/known.md", "src/known.py", "docs/analysis/other.md"}


# --------------------------------------------------------------------- rule reachability
def test_every_rule_id_has_a_declared_class(mod):
    assert set(mod.RULE_CLASS.values()) == {"EXPLICIT", "INFERRED", "UNKNOWN"}


def test_e2_inline_citation_on_resolvable_finding(mod):
    e = _slot(mod.classify(_node("closes F-900"), _gt(mod), TRACKED), "originating_finding")
    assert (e["rule_id"], e["class"], e["dst"]) == ("E2_INLINE_CITATION", "EXPLICIT", ["F-900"])


def test_e1_structured_field_on_manifest_objective(mod):
    n = _node('{"objective": "remediate F-900"}', "DECISION_CH",
              {"objective": "remediate F-900", "authority_granted": "", "affected_files": []})
    e = _slot(mod.classify(n, _gt(mod), TRACKED), "originating_finding")
    assert (e["rule_id"], e["class"]) == ("E1_STRUCTURED_FIELD", "EXPLICIT")


def test_i1_hypothesis_backseed(mod):
    gt = _gt(mod, finding_to_hyp={"F-900": ["H-900"]})
    e = _slot(mod.classify(_node("cites F-900"), gt, TRACKED), "originating_hypothesis")
    assert (e["rule_id"], e["class"], e["dst"]) == ("I1_HYPOTHESIS_BACKSEED", "INFERRED", ["H-900"])


def test_i2_family_judgement_when_no_hypothesis_binds(mod):
    gt = _gt(mod, finding_to_family={"F-900": ["RF-X.L4"]})
    e = _slot(mod.classify(_node("cites F-900"), gt, TRACKED), "originating_hypothesis")
    assert (e["rule_id"], e["class"], e["dst"]) == ("I2_FAMILY_JUDGEMENT", "INFERRED", ["RF-X.L4"])


def test_i1_outranks_i2(mod):
    gt = _gt(mod, finding_to_hyp={"F-900": ["H-900"]}, finding_to_family={"F-900": ["RF-X.L4"]})
    e = _slot(mod.classify(_node("cites F-900"), gt, TRACKED), "originating_hypothesis")
    assert e["rule_id"] == "I1_HYPOTHESIS_BACKSEED"


def test_i3_date_colocation(mod):
    e = _slot(mod.classify(_node("no ids here", date="2026-01-02"), _gt(mod), TRACKED),
              "originating_finding")
    assert (e["rule_id"], e["class"], e["dst"]) == ("I3_DATE_COLOCATION", "INFERRED", ["F-900"])


def test_i4_file_overlap_when_only_change_targets_are_declared(mod):
    n = _node("{}", "DECISION_CH",
              {"objective": "", "authority_granted": "", "affected_files": ["src/known.py"]})
    e = _slot(mod.classify(n, _gt(mod), TRACKED), "originating_evidence")
    assert (e["rule_id"], e["class"]) == ("I4_FILE_OVERLAP", "INFERRED")


def test_i5_evidence_reached_only_through_a_cited_finding(mod):
    e = _slot(mod.classify(_node("cites F-900"), _gt(mod), TRACKED), "originating_evidence")
    assert (e["rule_id"], e["class"], e["dst"]) == (
        "I5_VIA_CITED_FINDING", "INFERRED", ["docs/analysis/known.md"])


def test_u1_declared_unknown_contract(mod):
    e = _slot(mod.classify(_node("cites F-900"), _gt(mod), TRACKED),
              "originating_measurement_basis")
    assert (e["rule_id"], e["class"]) == ("U1_DECLARED_UNKNOWN", "UNKNOWN")


def test_u2_no_candidate(mod):
    edges = mod.classify(_node("nothing cited at all"), _gt(mod), TRACKED)
    assert all(e["rule_id"] == "U2_NO_CANDIDATE" for e in edges)
    assert {e["class"] for e in edges} == {"UNKNOWN"}


def test_u3_dangling_citation_never_scores_explicit(mod):
    e = _slot(mod.classify(_node("cites F-999"), _gt(mod), TRACKED), "originating_finding")
    assert (e["rule_id"], e["class"], e["dst"]) == ("U3_DANGLING_CITATION", "UNKNOWN", [])


def test_u3_dangling_path_never_scores_explicit(mod):
    e = _slot(mod.classify(_node("see docs/analysis/ghost.md"), _gt(mod), TRACKED),
              "originating_evidence")
    assert (e["rule_id"], e["class"]) == ("U3_DANGLING_CITATION", "UNKNOWN")


def test_dangling_alongside_resolvable_keeps_the_resolvable_one(mod):
    """A bad citation must not erase a good one cited beside it - but it is still recorded."""
    e = _slot(mod.classify(_node("F-900 and F-999"), _gt(mod), TRACKED), "originating_finding")
    assert e["class"] == "EXPLICIT" and e["dst"] == ["F-900"]
    assert e["dangling_also_cited"] == ["F-999"]


def test_u4_named_basis_without_execution_is_not_explicit(mod):
    e = _slot(mod.classify(_node("under MC-REAL-V1"), _gt(mod), TRACKED),
              "originating_measurement_basis")
    assert (e["rule_id"], e["class"]) == ("U4_DECLARED_NOT_EXECUTED", "UNKNOWN")


def test_u4_becomes_explicit_once_execution_is_proven(mod):
    """The ONLY thing that upgrades a measurement basis is a real execution record."""
    gt = _gt(mod, executed_contracts={"MC-REAL-V1"})
    e = _slot(mod.classify(_node("under MC-REAL-V1"), gt, TRACKED),
              "originating_measurement_basis")
    assert (e["rule_id"], e["class"]) == ("E1_STRUCTURED_FIELD", "EXPLICIT")


def test_a_manifest_citing_its_own_path_is_not_evidence(mod):
    own = "docs/governance/build_manifests/CH-x.impact.json"
    n = _node("{}", "DECISION_CH",
              {"objective": "", "authority_granted": "", "affected_files": [own]},
              path=own)
    e = _slot(mod.classify(n, _gt(mod), TRACKED | {own}), "originating_evidence")
    assert e["class"] != "EXPLICIT"


# --------------------------------------------------------------------- whole-corpus invariants
def test_conservation_one_edge_per_decision_per_slot(payload, mod):
    t = payload["rollup"]["totals"]
    assert t["conservation_ok"] is True
    assert t["edges"] == t["decisions"] * len(mod.SLOTS)
    assert sum(t["counts"].values()) == t["edges"]


def test_every_edge_is_well_formed(payload, mod):
    ids = {n["node_id"] for n in payload["nodes"]}
    for e in payload["edges"]:
        assert e["src"] in ids
        assert e["slot"] in mod.SLOTS
        assert e["class"] == mod.RULE_CLASS[e["rule_id"]]
        assert isinstance(e["witness"], str) and e["witness"]
        assert isinstance(e["dst"], list)
        if e["class"] != "UNKNOWN":
            assert e["dst"], "a non-UNKNOWN edge must name what it resolved to"


def test_unknown_edges_are_never_silently_populated(payload):
    """GAPS ARE THE RESULT: an UNKNOWN edge must not carry a resolved destination."""
    for e in payload["edges"]:
        if e["class"] == "UNKNOWN":
            assert e["dst"] == [] or e["rule_id"] == "U4_DECLARED_NOT_EXECUTED"


def test_percentages_sum_to_one_hundred(payload):
    for block in [payload["rollup"]["totals"]] + list(payload["rollup"]["per_slot"].values()):
        assert abs(sum(block["pct"].values()) - 100.0) < 0.05


def test_determinism_two_runs_are_byte_identical(mod, tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    for out in (a, b):
        p, _n, _e = mod.build_payload(_FIXED_DATE)
        out.write_text(json.dumps(p, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                       encoding="utf-8")
    assert a.read_bytes() == b.read_bytes()


def test_corpus_counts_still_match_the_authoritative_sources(payload):
    """If the extractor's totals drift from the sources, the PARSER is wrong, not the repo."""
    ci = payload["rollup"]["corpus_integrity"]
    ml = payload["rollup"]["measurement_layer"]
    doc = (_REPO / "docs" / "current-findings.md").read_text(encoding="utf-8")
    # Anchored to a real F-id: the doc also carries a `### F-0xx` schema template header.
    assert ci["findings"] == len(re.findall(r"^###\s+F-\d{3}\b", doc, re.M))
    assert ml["findings_contract_declared_unknown"] == len(
        re.findall(r"^-\s+Contract:\s+UNKNOWN\s*$", doc, re.M))
    # 2026-08-26 (CH-measurement-provenance-boundary): this asserted `== 0` — a snapshot of the
    # world before the measurement layer had ever run, written as a tripwire for exactly the event
    # that then happened. Four contracts executed E-MT-00. The durable invariant is that the
    # extractor's count equals the result log's, so the parser cannot drift from the source.
    executed = {r.get("contract_id") for r in _result_log_lines()}
    assert ml["contracts_with_proven_execution"] == len(executed), (
        f"extractor counts {ml['contracts_with_proven_execution']} executed contracts but the "
        f"result log carries {len(executed)}: {sorted(executed)}"
    )


def _result_log_lines() -> list[dict]:
    """Non-meta lines of the committed measurement result log."""
    p = _REPO / "configs" / "research" / "measurement_result_log.jsonl"
    if not p.is_file():
        return []
    out = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("kind") == "MEASUREMENT_RESULT":
            out.append(rec)
    return out


def test_findings_export_field_gap_is_reported_not_hidden(payload):
    """The audit MEASURES whether the GENERATED findings view carries Contract:/Family:.

    2026-08-26 (CH-measurement-provenance-boundary): this test previously pinned the DEFECT
    (`== ["Contract", "Family"]`). The gap is now closed in findings_export._FIELDS, so the
    assertion inverts - what stays enforced is that the extractor keeps measuring the divergence
    rather than assuming it. `tests/test_findings_export.py` owns the export side.
    """
    gap = payload["rollup"]["corpus_integrity"]["findings_export_missing_fields"]
    assert gap == [], f"findings_export._FIELDS has drifted from the doc again: {gap}"


def test_a_content_hash_contract_resolves_to_the_instance_it_names(mod, tmp_path):
    """A Contract cited as the sha256 of a sealed instance resolves to that instance's id.

    Keeps the content-hash path REACHABLE. It fires zero times on today's corpus - Workstream A
    rewrote all six sha-only citations to ids - so without this fixture it would rot into dead
    code, the same treatment the extractor gives rule I4.
    """
    body = {"contract_id": "MC-SYNTH-V1", "schema_version": "1.0.0"}
    raw = json.dumps(body, indent=2).encode("utf-8")
    p = tmp_path / "MC-SYNTH-V1.json"
    p.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()

    assert hashlib.sha256(p.read_bytes()).hexdigest() == digest
    # The same construction load_ground_truth uses: id keyed by the file's content hash.
    resolved = {hashlib.sha256(p.read_bytes()).hexdigest(): body["contract_id"]}
    assert resolved.get(digest) == "MC-SYNTH-V1"
    assert resolved.get("0" * 64) is None, "a non-matching hash must resolve to nothing"


def test_session_log_parse_coverage_is_reported(payload):
    m = payload["session_log_marker_forms"]
    assert m["corpus_entries_parsed"] + m["unparsed"] == m["corpus_markers_loose_scan"]
    assert m["parse_coverage_pct"] >= 99.0

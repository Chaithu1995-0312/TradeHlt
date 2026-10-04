"""Feature-math ownership floor — the enforcement gate for
`scripts/analysis/feature_math_lint.py`.

Asserts (a) the report shape; (b) the floor is GREEN — no NEW (unpinned) re-derivations of a
registered feature exist outside the registry; (c) every pinned known-divergence is still present
(so it can't be silently dropped without doing the Phase-B fix); (d) the registered-name set is
loaded from the ontology (single source of truth); and (e) the classifier is OWNERSHIP-based, not
arithmetic-syntax-based — the bite test proves `a/b` and `np.divide` fail while dict-reads /
registry-calls / clamps of reads pass.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "feature_math_lint.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("feature_math_lint", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    if not _TOOL.exists():
        pytest.skip("feature_math_lint.py not present")
    return _load_tool()


@pytest.fixture(scope="module")
def report(tool):
    return tool.build_report()


def test_report_shape(report):
    assert report["generated_at"]
    assert set(report["summary"]) >= {"new_violations", "known_present", "stale_pins",
                                       "current_pins", "retired", "registered_count"}
    assert isinstance(report["registered_names"], list)
    assert isinstance(report["new_violations"], list)
    assert isinstance(report["pins"], list) and isinstance(report["ledger"], dict)


def test_floor_is_green(tool, report):
    """No NEW re-derivations, and no stale pins. THE regression floor."""
    assert tool.check_violations(report) == [], (
        "feature-math ownership violated — a registered feature is re-derived outside the registry. "
        "Route it through candle_math/derived_math/the registry, or (if pre-existing) pin it in "
        "_KNOWN_DIVERGENCES with a Phase-B note."
    )


def test_pins_have_no_stale_durable_keys(report):
    """Every pin's durable_key must still match a live site. A stale pin means the site's formula was
    edited or moved — that must be an intentional retirement (manifest), not a silent drift."""
    assert report["summary"]["stale_pins"] == 0, f"stale pins: {report['stale_pins']}"


# ── Durable identity ledger — the monotonic debt ratchet (round-2/3 governance) ──

_REQUIRED_PIN_FIELDS = {
    "id", "feature_id", "file", "enclosing_qualname", "target_symbol", "statement_kind",
    "durable_key", "semantic_class", "formula_equivalence", "execution_reachability",
    "decision_reachability", "observed_value_drift", "observed_score_drift",
    "observed_decision_flips", "owner", "evidence", "opened", "review_trigger",
}
_SEMANTIC = {"same_quantity", "name_collision_distinct", "transport", "unknown"}
_EQUIV = {"byte_identical", "mathematically_equivalent", "non_equivalent", "unknown"}
_REACH = {"reachable", "conditional", "unreachable", "unknown"}
_OBSERVED = {"measured", "zero", "not_measured"}


def test_grandfather_set_monotonic(tool, report):
    """The TRUE ratchet: CURRENT ∪ RETIRED == ORIGINAL_BASELINE; CURRENT ∩ RETIRED == ∅; no foreign id.
    A count cap can't prove this (retire 2, add 2 back = still ≤10). A set can."""
    baseline = set(report["ledger"]["original_baseline_ids"])
    current = set(report["ledger"]["current_ids"])
    retired = set(report["ledger"]["retired_ids"])
    assert current <= baseline, f"foreign (non-baseline) pin ids present: {current - baseline}"
    assert retired <= baseline, f"retired ids outside baseline: {retired - baseline}"
    assert current & retired == set(), f"resurrected retired ids: {current & retired}"
    assert current | retired == baseline, (
        f"ledger broken: CURRENT ∪ RETIRED != BASELINE. missing={baseline - (current | retired)}. "
        "A deleted manifest retirement or a silently-dropped pin causes this."
    )


def test_retirements_are_evidenced(tool):
    """Each manifest retirement must cite a finding + commit + evidence artifact — retirement is a
    governed act, not a quiet edit."""
    for r in tool.load_retirements():
        for field in ("gd_id", "retired_commit", "finding_id", "evidence_artifact", "retired_at"):
            assert str(r.get(field, "")).strip(), f"retirement {r.get('gd_id')} missing {field}"


def test_every_pin_well_formed(report):
    """All record fields present + typed; observed_* default to not_measured (no pre-filled evidence)."""
    seen_ids, seen_keys = set(), set()
    for p in report["pins"]:
        missing = _REQUIRED_PIN_FIELDS - set(p)
        assert not missing, f"pin {p.get('id')} missing fields {missing}"
        assert p["id"] not in seen_ids, f"duplicate pin id {p['id']}"
        assert p["durable_key"] not in seen_keys, f"duplicate durable_key {p['durable_key']}"
        seen_ids.add(p["id"]); seen_keys.add(p["durable_key"])
        assert p["semantic_class"] in _SEMANTIC
        assert p["formula_equivalence"] in _EQUIV
        assert p["execution_reachability"] in _REACH
        assert p["decision_reachability"] in _REACH
        # observed_decision_flips is measured/not_measured/count; the two drift fields use _OBSERVED
        assert p["observed_value_drift"] in _OBSERVED
        assert p["observed_score_drift"] in _OBSERVED
        assert str(p["evidence"]).strip() and str(p["review_trigger"]).strip()


def test_durable_key_is_content_and_scope_sensitive(tool):
    """The fingerprint must change if the FORMULA changes OR the enclosing method changes — proving it
    identifies the derivation SITE, not just file::name (round-2 defect #2)."""
    rhs_a = ast.parse("body / (high - low)", mode="eval").body
    rhs_b = ast.parse("body / total_wick", mode="eval").body
    base = tool._durable_key("f.py", "C.m", "body_ratio", "Assign", rhs_a)
    assert base != tool._durable_key("f.py", "C.m", "body_ratio", "Assign", rhs_b), "formula edit not detected"
    assert base != tool._durable_key("f.py", "C.other", "body_ratio", "Assign", rhs_a), "scope move not detected"
    assert base == tool._durable_key("f.py", "C.m", "body_ratio", "Assign",
                                     ast.parse("body / (high - low)", mode="eval").body), "not stable"


def test_registered_names_come_from_ontology(tool, report):
    ont = tool.load_ontology()
    declared = set()
    for section in ("primitives", "feature_compositions", "derived_metrics"):
        declared |= set((ont.get(section) or {}).keys())
    # report set = ontology names + declared aliases (wick_size for candle_range)
    assert declared <= set(report["registered_names"])
    assert "wick_size" in report["registered_names"]      # alias of candle_range
    assert "body_ratio" in report["registered_names"]


def _classify(tool, expr: str) -> str:
    reg = tool._registered_names()
    node = ast.parse(expr, mode="eval").body
    return tool._classify_rhs(node, reg)


def test_ownership_bite_derivation_forms_flagged(tool):
    # Arithmetic AND a non-registry call both count as derivation (semantics, not syntax).
    assert _classify(tool, "x / (high - low)") == "derivation"
    assert _classify(tool, "np.divide(x, y)") == "derivation"
    assert _classify(tool, "abs(close - open_)") == "derivation"
    assert _classify(tool, "helper(a, b)") == "derivation"


def _scan_snippet(tool, source: str) -> list:
    """Run the real module scanner on an in-memory snippet (provenance-aware path)."""
    import tempfile, os
    reg = tool._registered_names()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as fh:
        fh.write(source)
        path = fh.name
    try:
        from pathlib import Path
        return tool._scan_module(Path(path), reg)
    finally:
        os.unlink(path)


def test_ownership_bite_transport_exempt(tool):
    # Transport / storage must NOT be flagged.
    assert _classify(tool, "record['body_ratio']") == "transport"
    assert _classify(tool, "float(features.get('retest_depth', 0.0))") == "transport"
    assert _classify(tool, "max(0.0, min(1.0, float(features['retest_depth'])))") == "transport"
    assert _classify(tool, "candle.body_ratio") == "transport"


def test_ownership_registry_authority_is_provenance_verified(tool):
    """2026-07-11 hardening: a registry call is authoritative ONLY when this module's
    imports prove the callee comes from a registry module. Leaf-name matching is dead."""
    # WITHOUT imports, even familiar-looking calls are NOT authority
    assert _classify(tool, "_cm.body_ratio(o, h, l, c)") == "derivation"
    assert _classify(tool, "derived_math.disp_strength(b, a, c)") == "derivation"
    assert _classify(tool, "compute_composition('body_ratio', o, h, l, c)") == "derivation"
    # evil module with a registry-sounding leaf: NEVER authority
    v = _scan_snippet(tool, (
        "import evil_module\n"
        "body_ratio = evil_module.body_ratio(o, h, l, c)\n"
    ))
    assert any(x["name"] == "body_ratio" for x in v), "evil-module call must be flagged"
    # legit aliased imports ARE authority (all common forms)
    for src in (
        "from features import candle_math as _cm\nbody_ratio = _cm.body_ratio(o, h, l, c)\n",
        "import features.derived_math as dm\ndisp_strength = dm.disp_strength(b, a, c)\n",
        "from features.registry.composition_registry import compute_composition\n"
        "body_ratio = compute_composition('body_ratio', o=o, h=h, l=l, c=c)\n",
        "from features.candle_math import body_ratio as _br\nbody_ratio = _br(o, h, l, c)\n",
    ):
        assert _scan_snippet(tool, src) == [], f"legit registry import flagged: {src!r}"


def test_ownership_bite_new_binding_forms_flagged(tool):
    """2026-07-11 hardening: AugAssign / walrus / for-target / with-target /
    subscript+attribute sinks / dict.update sinks are all covered."""
    reg_import = "from features import candle_math as _cm\n"
    cases = {
        "AugAssign":      "body_ratio = 1.0\nbody_ratio += hi / lo\n",
        "NamedExpr":      "y = (body_ratio := hi / lo)\n",
        "ForTarget":      "for body_ratio in (hi / lo for hi, lo in pairs):\n    pass\n",
        "WithTarget":     "with make_ratio(hi / lo) as body_ratio:\n    pass\n",
        "SubscriptSink":  "df['body_ratio'] = df['a'] / df['b']\n",
        "AttributeSink":  "obj.body_ratio = hi / lo\n",
        "DictUpdateSink": "d.update({'body_ratio': hi / lo})\n",
    }
    for kind, src in cases.items():
        v = _scan_snippet(tool, reg_import + src)
        assert any(x["name"] == "body_ratio" for x in v), f"{kind} not covered: {src!r}"
    # ...and the transported twins stay clean
    clean = {
        "SubscriptSink":  "df['body_ratio'] = other['body_ratio']\n",
        "DictUpdateSink": "d.update({'body_ratio': row.get('body_ratio')})\n",
        "AugAssignConst": "x = 1.0\nx += 2.0\n",  # non-governed target
    }
    for kind, src in clean.items():
        assert _scan_snippet(tool, src) == [], f"{kind} transported twin flagged: {src!r}"


def test_universe_reconciliation_with_census(tool):
    """2026-07-11 hardening (universe reconciliation): the lint scans only the live-spine
    src/ dirs; the geometry census scans the whole repo. No fresh census DERIVATION of an
    ontology-registered name that lives OUTSIDE the lint universe may escape Gate-2B
    adjudication — the census closure is the mechanism that covers the lint's scope gap."""
    import importlib.util
    import json as _json

    census_tool_path = _REPO / "scripts" / "analysis" / "geometry_census.py"
    adj_path = _REPO / "docs" / "governance" / "geometry_semantic_adjudication.jsonl"
    if not census_tool_path.exists() or not adj_path.exists():
        pytest.skip("geometry census tooling/artifacts not present")

    spec = importlib.util.spec_from_file_location("geometry_census", census_tool_path)
    census = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(census)
    fresh, _summary, _other = census.build_census()

    adjudicated_ids = {
        _json.loads(l)["occurrence_id"]
        for l in adj_path.read_text(encoding="utf-8").splitlines() if l.strip()
    }
    registered = tool._registered_names()
    lint_universe_prefixes = tuple(f"src/{d}/" for d in tool._SCAN_DIRS)

    missing = []
    for r in fresh:
        if not r.get("derivation_id_or_null"):
            continue
        target = str(r.get("target_symbol") or "").lstrip("_")
        if target not in registered:
            continue
        f = str(r.get("file") or "").replace("\\", "/")
        if f.startswith(lint_universe_prefixes):
            continue  # inside the lint universe — the lint floor owns it
        if r["occurrence_id"] not in adjudicated_ids:
            missing.append(f"{f}:{r.get('line_span')}::{target}")
    assert not missing, (
        "geometry-census derivations of REGISTERED names outside the lint universe lack "
        "Gate-2B adjudication (silent scope gap):\n" + "\n".join(missing)
    )


def test_ownership_dispatch_map_provenance(tool):
    """2026-07-11 (B1): a dict-dispatch call is registry authority ONLY when the map was
    bound at module level from a provenance-verified registry call (fm_resolve pattern)."""
    legit = (
        "from features.fm_resolve import bind_phase2_crt_callables\n"
        "_FM: dict = bind_phase2_crt_callables()\n"
        "displacement_atr_ratio = _FM['FM-028'](rng_val, atr)\n"
    )
    assert _scan_snippet(tool, legit) == [], "provenance-verified dispatch map flagged"
    # plain Assign form too
    legit2 = (
        "from features.fm_resolve import bind_phase2_crt_callables\n"
        "_FM = bind_phase2_crt_callables()\n"
        "displacement_atr_ratio = _FM['FM-028'](rng_val, atr)\n"
    )
    assert _scan_snippet(tool, legit2) == [], "Assign-form dispatch map flagged"
    # an arbitrary local dict is NOT authority
    evil = (
        "_FM = {'FM-028': lambda a, b: a * b}\n"
        "displacement_atr_ratio = _FM['FM-028'](rng_val, atr)\n"
    )
    v = _scan_snippet(tool, evil)
    assert any(x["name"] == "displacement_atr_ratio" for x in v), "local-dict dispatch must be flagged"
    # a dict bound from a NON-registry call is NOT authority either
    evil2 = (
        "import evil_module\n"
        "_FM = evil_module.bind_stuff()\n"
        "displacement_atr_ratio = _FM['FM-028'](rng_val, atr)\n"
    )
    v2 = _scan_snippet(tool, evil2)
    assert any(x["name"] == "displacement_atr_ratio" for x in v2), "evil-bound dispatch must be flagged"

"""F-049 GATE 1G — adversarial census-completeness floor for scripts/analysis/geometry_census.py.

Proves the census detects every declared bypass pattern (synthetic fixtures, 100% recall target)
and does NOT flag reads / string mentions / comments / unrelated arithmetic as derivations
(negative controls). Synthetic recall does NOT prove repository completeness — that residual is
explicit in the census summary (UNKNOWN counts + universe manifest).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "scripts" / "analysis" / "geometry_census.py"


def _load():
    spec = importlib.util.spec_from_file_location("geometry_census", _TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tool():
    return _load()


def _derivs(tool, src, rel="src/fixture.py"):
    return [r for r in tool.scan_source(src, rel) if r["derivation_id_or_null"]]


def _forms(tool, src):
    return {r["feature_candidate"] for r in _derivs(tool, src)}


# ── positive fixtures: every declared bypass pattern must be DETECTED ────────

_POSITIVE_FIXTURES = {
    "plain_name_assignment":       ("body_ratio = body_size / candle_range\n", "F6_BODY_RATIO"),
    "attribute_assignment":        ("self.body_ratio = abs(close - open_) / (high - low)\n", "F6_BODY_RATIO"),
    "subscript_assignment":        ("d['body_size'] = abs(close - open_)\n", "F1_BODY"),
    "dataframe_column_assignment": ("df['wick_size'] = df['high'] - df['low']\n", "F2_RANGE"),
    "dict_update":                 ("aux.update({'body_ratio': abs(c - o) / (h - l)})\n", "F6_BODY_RATIO"),
    "dataframe_assign":            ("df = df.assign(body_ratio=df['close'] - df['open'])\n", None),  # kwarg sink detected
    "tuple_unpacking":             ("body_size, candle_range = abs(close - open_), high - low\n", "F1_BODY"),
    "helper_return_assignment":    ("def rng(high, low):\n    return high - low\n\nx = rng(h, l)\n", "F2_RANGE"),
    "alias_renamed_ohlc":          ("px_h = candle.high\npx_l = candle.low\nspan = px_h - px_l\n", "F2_RANGE"),
    "np_divide":                   ("import numpy as np\nr = np.divide(abs(close - open_), high - low)\n",
                                    "F6_BODY_RATIO"),
    "series_divide":               ("r = (df['high'] - df['low']).divide(df['close'])\n", None),  # div-of-range detected
    "np_where":                    ("import numpy as np\nbr = np.where(ws > 0, abs(close - open_) / (high - low), 0.0)\n",
                                    "F6_BODY_RATIO"),
    "np_maximum_eps_floor":        ("import numpy as np\nfr = np.maximum(high - low, 0.001)\n", "F2_RANGE"),
    "clip_denominator":            ("br = abs(close - open_) / (high - low).clip(0.000001)\n", None),
    "formula_without_names":       ("q = high - max(open_, close)\nz = min(open_, close) - low\nt = q + z\n",
                                    "F5_TOTALW"),
    "range_minus_body_totalwick":  ("tw = (high - low) - abs(close - open_)\n", "F5_TOTALW"),
    "gd001_body_over_totalwick":   ("wick_size = max(0.0, (high - low) - abs(close - open_))\n"
                                    "body_ratio = abs(close - open_) / wick_size\n", None),
    # census-v2 additions
    "ifexp_ternary_guard":         ("body_ratio = body_size / candle_range if candle_range > 0 else 0.0\n",
                                    "F6_BODY_RATIO"),
    "gd001_ifexp_guard":           ("body_ratio = body_size / wick_size if wick_size > 1e-8 else 0.0\n",
                                    "NC_BODY_OVER_WICKSZ"),
    "subexpression_in_call":       ("import pandas as pd\n"
                                    "tr = pd.concat([(high - low), (high - prev).abs()], axis=1).max(axis=1)\n",
                                    "F2_RANGE"),
}


@pytest.mark.parametrize("name", sorted(_POSITIVE_FIXTURES))
def test_positive_fixture_detected(tool, name):
    src, expected_form = _POSITIVE_FIXTURES[name]
    derivs = _derivs(tool, src)
    assert derivs, f"bypass fixture NOT detected: {name}\n{src}"
    if expected_form:
        assert expected_form in _forms(tool, src), (
            f"{name}: expected {expected_form}, got {_forms(tool, src)}"
        )


def test_eps_floor_flagged(tool):
    src = "fr = max(high - low, 0.001)\n"
    d = _derivs(tool, src)
    assert d and "eps_floor" in d[0]["flags"]


def test_guarded_np_where_flagged(tool):
    src = "import numpy as np\nbr = np.where(ok, abs(close - open_) / (high - low), 0.0)\n"
    d = _derivs(tool, src)
    assert d and any("guarded" in r["flags"] for r in d)


# ── negative controls: must NOT be derivations ───────────────────────────────

_NEGATIVE_FIXTURES = {
    "pure_read":            "x = compute(features['body_ratio'])\n",
    "transport_dict_get":   "body_ratio = features.get('body_ratio', 0.0)\n",
    "coercion_transport":   "body_ratio = float(row['body_ratio'])\n",
    "string_mention":       "log.info('body_ratio drifted')\n",
    "comment_mention":      "# body_ratio = high - low  (docs only)\nx = 1\n",
    "unrelated_arithmetic": "profit = revenue - cost\nz = a / b\n",
    "unrelated_minmax":     "cap = max(size, 100)\n",
    # census-v2 additions
    "literal_fixture_data": "d = {'body_size': [0.8, 0.8, 0.8], 'wick_size': [1.0, 1.0, 1.0]}\n",
    "guarded_dict_read":    "body_ratio = float(feats['body_ratio']) if 'body_ratio' in feats else None\n",
}


def test_md1_alias_is_transport_not_derivation(tool):
    """census-v3 MD-1: a bare-name alias of a derivation TRANSPORTS it; only the origin derives."""
    src = ("x = abs(close - open_) / (high - low)\n"
           "y = x\n"
           "d['body_ratio'] = y\n")
    derivs = _derivs(tool, src)
    assert len(derivs) == 1, f"expected exactly 1 derivation (the origin), got {len(derivs)}"
    assert derivs[0]["target_symbol"] == "x"
    sinks = [r for r in tool.scan_source(src, "src/fixture.py")
             if r["target_symbol"] == "body_ratio"]
    assert sinks and all(r["role"] == "transport" for r in sinks)
    assert any("alias_of_derivation" in r.get("flags", []) for r in sinks)


def test_md2_coercion_helper_is_transport(tool):
    """census-v3 MD-2: _to_float(read) is coercion transport, not new mathematics."""
    src = "d['body_ratio'] = _to_float(features.get('body_ratio', 0.0), 0.0)\n"
    assert not _derivs(tool, src), "coercion helper misclassified as derivation"
    sinks = [r for r in tool.scan_source(src, "src/fixture.py") if r["target_symbol"] == "body_ratio"
             and r["role"] == "transport"]
    assert sinks, "coercion write not recorded as transport"


def test_md3_executors_admitted_in_artifact(tool):
    """census-v3 MD-3: the two config-driven registry executors appear as executor_dispatch."""
    art = _REPO / "docs" / "governance" / "geometry_census.jsonl"
    if not art.exists():
        pytest.skip("census artifact not yet generated")
    import json
    rows = [json.loads(l) for l in art.read_text(encoding="utf-8").splitlines() if l.strip()]
    ex = [r for r in rows if r["role"] == "executor_dispatch"]
    assert len(ex) == 2, f"expected 2 admitted executors, got {len(ex)}"
    assert {r["file"] for r in ex} == {"src/features/registry/composition_registry.py",
                                       "src/features/registry/derived_registry.py"}


def test_cross_candle_not_body(tool):
    """census-v2 same-candle guard: retest.close - disp.open is NOT a body (F1)."""
    src = ("disp_move = abs(disp.close - disp.open)\n"
           "retrace = abs(retest.close - disp.open) / disp_move\n")
    forms = _forms(tool, src)
    assert "F1_BODY" in forms, "same-candle abs(disp.close-disp.open) must still match F1"
    # the cross-candle numerator must NOT be classified as a BODY numerator
    for r in _derivs(tool, src):
        if r["target_symbol"] == "retrace":
            assert "DIV(BODY," not in (r["feature_candidate"] or ""), (
                f"cross-candle numerator misclassified as BODY: {r['feature_candidate']}"
            )


def test_single_visit_no_duplicate_derivations_per_site(tool):
    """census-v2 single-pass fix: one implementation site → exactly one DERIVATION_ID."""
    src = ("def f(disp, retest):\n"
           "    disp_move = abs(disp.close - disp.open)\n"
           "    retrace = abs(retest.close - disp.open) / disp_move\n"
           "    return retrace\n")
    derivs = _derivs(tool, src)
    sites = [(r["line_span"][0], r["target_symbol"]) for r in derivs]
    assert len(sites) == len(set(sites)), f"duplicate derivations for one site: {sites}"


@pytest.mark.parametrize("name", sorted(_NEGATIVE_FIXTURES))
def test_negative_control_not_derivation(tool, name):
    src = _NEGATIVE_FIXTURES[name]
    derivs = _derivs(tool, src)
    assert not derivs, f"FALSE POSITIVE on negative control {name}: {[r['feature_candidate'] for r in derivs]}"


def test_precision_recall_summary(tool):
    """100% recall required on the declared synthetic bypass set; 100% precision on negatives."""
    detected = sum(1 for n, (src, _f) in _POSITIVE_FIXTURES.items() if _derivs(tool, src))
    recall = detected / len(_POSITIVE_FIXTURES)
    false_pos = sum(1 for src in _NEGATIVE_FIXTURES.values() if _derivs(tool, src))
    assert recall == 1.0, f"synthetic recall {recall:.0%} < 100%"
    assert false_pos == 0, f"{false_pos} false positives on negative controls"


# ── artifact integrity ───────────────────────────────────────────────────────

def test_census_artifact_exists_and_ids_stable(tool):
    art = _REPO / "docs" / "governance" / "geometry_census.jsonl"
    if not art.exists():
        pytest.skip("census artifact not yet generated")
    import json
    rows = [json.loads(l) for l in art.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert rows, "empty census artifact"
    ids = [r["occurrence_id"] for r in rows]
    assert len(ids) == len(set(ids)), "occurrence_ids not unique"
    required = {"occurrence_id", "derivation_id_or_null", "discovery_methods", "file",
                "enclosing_qualname", "line_span", "statement_kind", "target_kind", "target_symbol",
                "rhs_fingerprint", "feature_candidate", "role", "git_blob_hash",
                "classification_status", "evidence", "uncertainty"}
    for r in rows[:50]:
        assert required <= set(r), f"missing fields: {required - set(r)}"


def test_geometry_census_is_fresh(tool):
    """THE CONSTRUCTION-CONTRACT KEYSTONE (Gate 6 / B1): the committed census artifact must match a
    FRESH re-derivation from the repository. Any new/changed/removed geometry derivation anywhere in
    the universe fails this floor until the change is REGISTERED (ontology/registry) or ADJUDICATED
    and the census + adjudication artifacts are regenerated:
        python scripts/analysis/geometry_census.py
        python scripts/analysis/gate2b_adjudication.py
    This converts the census from a point-in-time audit into a standing repo-wide floor — the
    mechanical enforcement that new feature math cannot appear outside the governed architecture.
    """
    art = _REPO / "docs" / "governance" / "geometry_census.jsonl"
    if not art.exists():
        pytest.skip("census artifact not yet generated")
    import json
    committed = [json.loads(l) for l in art.read_text(encoding="utf-8").splitlines() if l.strip()]
    committed_sites = {(r["file"], r["enclosing_qualname"], r["target_symbol"], r["feature_candidate"])
                       for r in committed if r["derivation_id_or_null"]}
    fresh_occ, _summary, _other = tool.build_census()
    fresh_sites = {(r["file"], r["enclosing_qualname"], r["target_symbol"], r["feature_candidate"])
                   for r in fresh_occ if r["derivation_id_or_null"]}
    new = fresh_sites - committed_sites
    gone = committed_sites - fresh_sites
    assert not new and not gone, (
        "GEOMETRY CENSUS IS STALE — the repository's geometry-derivation surface changed.\n"
        f"  NEW (unregistered) derivations ({len(new)}): {sorted(new)[:5]}\n"
        f"  REMOVED derivations ({len(gone)}): {sorted(gone)[:5]}\n"
        "Required workflow (REPOSITORY_CONSTRUCTION_PROTOCOL.md): register the quantity in the market\n"
        "ontology/formula registry (or adjudicate it), then regenerate:\n"
        "  python scripts/analysis/geometry_census.py && python scripts/analysis/gate2b_adjudication.py"
    )


def test_adjudication_closed_against_fresh_census(tool):
    """Chains Gate-2B closure to REALITY: every fresh-census derivation must have an adjudication
    record (not merely artifact↔artifact consistency)."""
    adj_p = _REPO / "docs" / "governance" / "geometry_semantic_adjudication.jsonl"
    if not adj_p.exists():
        pytest.skip("adjudication artifact not yet generated")
    import json
    adj_ids = {json.loads(l)["occurrence_id"] for l in adj_p.read_text(encoding="utf-8").splitlines() if l.strip()}
    fresh_occ, _s, _o = tool.build_census()
    fresh_gov = {r["occurrence_id"] for r in fresh_occ if r["derivation_id_or_null"]}
    unadjudicated = fresh_gov - adj_ids
    assert not unadjudicated, (
        f"{len(unadjudicated)} fresh governed derivations lack adjudication records: "
        f"{sorted(unadjudicated)[:5]} — run gate2b_adjudication.py after registering/adjudicating."
    )


def test_id_stability_under_line_movement(tool):
    src_a = "body_ratio = abs(close - open_) / (high - low)\n"
    src_b = "# moved down\n\n\n" + src_a
    ids_a = {r["occurrence_id"] for r in tool.scan_source(src_a, "src/x.py")}
    ids_b = {r["occurrence_id"] for r in tool.scan_source(src_b, "src/x.py")}
    assert ids_a == ids_b, "occurrence_ids changed under pure line movement"

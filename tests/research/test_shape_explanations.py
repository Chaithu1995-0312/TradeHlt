"""Floor for the Level-2 shape explanation layer (docs/research-readiness/shape_explanations.md).

Keeps the explanation layer honest and subordinate to the math (Level 1):
- the file exists and states its NO-authority + robustness caveats,
- every shape_id it documents is a REAL id in the generated shape library (anti-drift / anti-hallucination
  H2/H3) — checked only when the gitignored results artifact is present.

Governance-doc floor — no market data, fast.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_MD = _ROOT / "docs" / "research-readiness" / "shape_explanations.md"
_REPORT = _ROOT / "results" / "research" / "ic_003b" / "report.json"
_ONTOLOGY = _ROOT / "configs" / "research" / "market_story_ontology.yaml"

pytestmark = pytest.mark.research_integrity

_SHAPE_RE = re.compile(r"S_N\d+_k\d+_s\d+")
# a Level-3 mapping table row: | `shape_id` | `family` | status | conf | basis |
_MAP_ROW_RE = re.compile(r"\|\s*`(S_N\d+_k\d+_s\d+)`\s*\|\s*`([a-z_]+)`\s*\|")


def _ontology_family_ids() -> set[str]:
    """Family ids from the `families:` block to EOF (that block is last in the yaml)."""
    text = _ONTOLOGY.read_text(encoding="utf-8")
    fam_block = text.split("families:", 1)[1]
    return set(re.findall(r"id:\s*(\w+)", fam_block))


def test_explanation_file_exists():
    assert _MD.exists(), "Level-2 shape_explanations.md missing"


def test_carries_no_authority_and_robustness_caveats():
    md = _MD.read_text(encoding="utf-8")
    # authority boundary must be explicit
    assert "Authority: NONE" in md or "grants **no** authority" in md
    # robustness caveat with teeth (marginal / seed-fragile / near-noise) + per-shape stability
    assert "Robustness caveat" in md
    assert "seed-fragile" in md and "near-noise" in md
    assert "stability: LOW" in md
    # the read-order hierarchy must name the authoritative Level-1 source
    assert "SHAPE_LIBRARY.md" in md and "AUTHORITATIVE" in md


def test_documented_shapes_are_real():
    """Every shape_id in the doc must exist in the generated library (skips if artifact absent)."""
    if not _REPORT.exists():
        pytest.skip("results/research/ic_003b/report.json absent (gitignored) — id-subset check skipped")
    documented = set(_SHAPE_RE.findall(_MD.read_text(encoding="utf-8")))
    assert documented, "no shape ids documented"
    report = json.loads(_REPORT.read_text(encoding="utf-8"))
    real = set()
    for unit in report.get("arm_S", {}).values():
        for s in unit.get("shapes", []) or []:
            sid = s.get("shape_id")
            if sid:
                real.add(sid)
    missing = documented - real
    assert not missing, f"documented shape ids not in the real library (hallucinated?): {sorted(missing)}"


def test_level3_mapping_references_real_families():
    """Level-3 shape→story map: every closest_family must be a real ontology family id (anti-hallucination)."""
    md = _MD.read_text(encoding="utf-8")
    # proxy + no-authority discipline for the mapping layer
    assert "shape → story family (Level 3)" in md
    assert "Proxy caveat" in md and "nearest-family" in md
    rows = _MAP_ROW_RE.findall(md)
    assert len(rows) >= 6, f"expected >=6 Level-3 mapping rows, found {len(rows)}"
    fam_ids = _ontology_family_ids()
    assert {"liquidity_reversal", "trend_continuation", "trend_reversal"} <= fam_ids  # sanity on the parser
    bad = {(sid, fam) for sid, fam in rows if fam not in fam_ids}
    assert not bad, f"Level-3 map cites non-ontology family ids (hallucinated?): {sorted(bad)}"

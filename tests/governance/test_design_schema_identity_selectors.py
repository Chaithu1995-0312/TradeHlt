"""D2 population-key guard: identity_selector_fields must stay byte-identical between
docs/design/context-finding-odp/schemas/context.schema.yaml and odp.schema.yaml.

Both files carry an explicit doctrine that this list "MUST stay byte-identical" (odp.schema.yaml
:74-75; context.schema.yaml:198 identity_selector_fields is the canonical field list). D2 was
marked RETIRED in DESIGN_DEFECTS_D1_D2_D3_L4.md:22 on the strength of a one-time, dated manual
verification ("verified 2026-09-06") -- not a mechanical guard. Without this floor, the two
copies could silently diverge (adding a selector to one schema and not the other) and nothing
would catch it: the exact silent-gap class as F-079/F-083/F-085 (a skipped check indistinguishable
from a passed one).

Design-only artifacts (schema_version carries a "design_draft" status); this test enforces
doc-internal consistency only. Grants no runtime/production authority.

Authority: governance/hygiene only.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

_REPO = Path(__file__).resolve().parents[2]
_SCHEMA_DIR = _REPO / "docs" / "design" / "context-finding-odp" / "schemas"
_CONTEXT = _SCHEMA_DIR / "context.schema.yaml"
_ODP = _SCHEMA_DIR / "odp.schema.yaml"

_KEY = "identity_selector_fields:"


def _extract_block(path: Path) -> str:
    """Extract the identity_selector_fields: block verbatim, including its comment lines,
    down to (but not including) the first line that is neither blank, indented, a comment,
    nor a '-' list item -- i.e. the first line that starts a new top-level key."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith(_KEY))
    out = [lines[start]]
    for ln in lines[start + 1:]:
        if ln == "" or ln.startswith((" ", "\t", "#", "-")):
            out.append(ln)
            continue
        break
    # trim trailing blank lines so incidental spacing differences don't fail the compare
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def test_files_exist():
    assert _CONTEXT.is_file(), _CONTEXT
    assert _ODP.is_file(), _ODP


def test_identity_selector_fields_block_byte_identical():
    """Raw-text compare (doctrine text included) per odp.schema.yaml:74-75 /
    context.schema.yaml:198 / DESIGN_DEFECTS_D1_D2_D3_L4.md:22."""
    ctx_block = _extract_block(_CONTEXT)
    odp_block = _extract_block(_ODP)
    assert ctx_block == odp_block, (
        "identity_selector_fields block diverged between context.schema.yaml and "
        "odp.schema.yaml -- these MUST stay byte-identical (D2 population-key doctrine, "
        "DESIGN_DEFECTS_D1_D2_D3_L4.md:22). Diff the two schema files' "
        "identity_selector_fields: sections."
    )


def test_identity_selector_fields_parsed_equal():
    """Belt-and-braces: parsed list equality, independent of the raw-text compare."""
    ctx_doc = yaml.safe_load(_CONTEXT.read_text(encoding="utf-8"))
    odp_doc = yaml.safe_load(_ODP.read_text(encoding="utf-8"))
    ctx_fields = ctx_doc["identity_selector_fields"]
    odp_fields = odp_doc["identity_selector_fields"]
    assert ctx_fields == odp_fields, (
        f"parsed identity_selector_fields differ: context={ctx_fields!r} "
        f"odp={odp_fields!r}"
    )

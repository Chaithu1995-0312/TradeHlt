"""CRT divergence-cause taxonomy — declared-correspondence floor.

The repository has exactly one pre-existing "reason something was refused" enum
(`RejectReason`, src/config_layer/state_identity.py) and exactly one
resolver/engine divergence-cause taxonomy (`CATEGORY_PRECEDENCE`,
scripts/research/crt_parity_classifier.py). They answer different questions, so
reusing the former as the latter would be a join-not-identity error (the
FM-058 / SP-001 class, CLAUDE.md 6.8 §5).

`DIVERGENCE_CODE_REJECT_REASON` records that as a machine-checked declaration
rather than prose. These tests are BEHAVIORAL where they can be: the coverage
test drives `classify_mismatch` and asserts every code it can actually emit
carries a declared correspondence, so a new category code added without a
decision goes red instead of silently defaulting.

Authority: research/governance only (§6.5). Grants nothing.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_MODULE_PATH = _REPO / "scripts" / "research" / "crt_parity_classifier.py"
sys.path.insert(0, str(_REPO / "src"))


def _load_classifier():
    spec = importlib.util.spec_from_file_location("crt_parity_classifier", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["crt_parity_classifier"] = mod
    spec.loader.exec_module(mod)
    return mod


def _reject_reason_member_names() -> set[str]:
    from config_layer.state_identity import RejectReason  # noqa: WPS433
    return {m.name for m in RejectReason}


# ── Declaration totality (both directions) ────────────────────────────────────
def test_every_category_code_has_a_declared_correspondence():
    """A new CATEGORY_PRECEDENCE code must carry an explicit decision."""
    mod = _load_classifier()
    declared = set(mod.DIVERGENCE_CODE_REJECT_REASON)
    codes = set(mod.CATEGORY_PRECEDENCE)
    missing = sorted(codes - declared)
    assert not missing, (
        f"category codes with no declared RejectReason correspondence: {missing}. "
        "Add an entry (None is a valid, preferred answer) — do not let it default."
    )


def test_no_stale_correspondence_entries():
    """An entry for a code that no longer exists is dead weight — shrink-only."""
    mod = _load_classifier()
    stale = sorted(set(mod.DIVERGENCE_CODE_REJECT_REASON) - set(mod.CATEGORY_PRECEDENCE))
    assert not stale, (
        f"DIVERGENCE_CODE_REJECT_REASON names codes absent from CATEGORY_PRECEDENCE: {stale}"
    )


# ── Any non-None value must resolve against the live enum ─────────────────────
def test_named_reject_reasons_exist_in_the_live_enum():
    """The table stores member NAMES (import purity); they must still be real."""
    mod = _load_classifier()
    real = _reject_reason_member_names()
    bad = sorted(
        f"{code}->{name}"
        for code, name in mod.DIVERGENCE_CODE_REJECT_REASON.items()
        if name is not None and name not in real
    )
    assert not bad, (
        f"declared RejectReason member names that do not exist: {bad}. "
        f"Live members: {sorted(real)}"
    )


def test_reject_reason_enum_is_the_one_we_reasoned_about():
    """Pins the enum this declaration was adjudicated against. If a member is
    added or renamed, the correspondence decision must be revisited rather than
    silently inheriting a verdict made about a different enum."""
    assert _reject_reason_member_names() == {
        "LOW_SCORE", "OUTSIDE_SESSION", "NO_DOUBLE_SWEEP",
        "NEWS_FILTER", "HIGH_SPREAD", "INVALID_STATE",
    }


# ── Behavioral: codes the classifier actually emits are covered ───────────────
def test_emitted_codes_are_declared():
    """Drives classify_mismatch over inputs that reach distinct branches and
    asserts each emitted code is declared — not a static read of the tuple."""
    mod = _load_classifier()
    ctx_empty = mod.MismatchContext()

    emitted = set()
    # B-UNREACHABLE-STATE: structurally unreachable engine state.
    emitted.add(mod.classify_mismatch("EXECUTION", "RANGE", {}, ctx_empty).code)
    # D-UNKNOWN: nothing else applies, engine state carries no structural fact.
    emitted.add(mod.classify_mismatch("RANGE", "SWEEP", {}, ctx_empty).code)
    # C-GEOMETRY: declared divergent-construction pair.
    ctx_geom = mod.MismatchContext(
        state_marginals={"SWEEP": (100, 100, 90)},
        known_geometry_divergent_pairs=frozenset({("SWEEP", "RANGE")}),
    )
    emitted.add(mod.classify_mismatch("SWEEP", "RANGE", {}, ctx_geom).code)

    declared = set(mod.DIVERGENCE_CODE_REJECT_REASON)
    assert emitted <= declared, f"emitted but undeclared: {sorted(emitted - declared)}"
    assert len(emitted) >= 3, f"expected distinct branches, got {sorted(emitted)}"


def test_declared_negative_is_actually_negative():
    """The adjudicated result is that NO divergence code corresponds to a
    RejectReason member. If that ever changes it must be a deliberate edit with
    a rationale, not a drift — so pin the current, fully-negative state."""
    mod = _load_classifier()
    mapped = {c: n for c, n in mod.DIVERGENCE_CODE_REJECT_REASON.items() if n is not None}
    assert mapped == {}, (
        "a divergence code now claims a RejectReason correspondence: "
        f"{mapped}. That is a semantic decision — record the rationale inline "
        "and update this pin deliberately."
    )

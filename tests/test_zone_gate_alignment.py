"""ZoneGate vector-alignment floor — the schema-v4 safety net (2026-07-22).

WHAT THIS GUARDS
----------------
`models/zone_registry.json` has always stored a top-level `feature_order` naming the 38 features its
`mu`/`sigma`/`weights` vectors are aligned to — and until 2026-07-22 nothing read it.
`zone_gate_engine._extract_vector` built the scoring vector from the ambient
`CANONICAL_FEATURE_ORDER` and SILENTLY TRUNCATED anything longer:

    if len(vector) > CANONICAL_FEATURE_DIM:   # v2.0(35) -> v3.0(38) back-compat
        vector = vector[:CANONICAL_FEATURE_DIM]

ZoneGate is the only LIVE hard gate (F-041, `zone_mode=hard`); every other trained consumer is inert
or off (F-004 BitNet, F-005 TradeNet, F-038 rr_fusion, F-060 Gaussian). So on the next schema change
that gate would have scored a misaligned vector, decided confidently, and raised nothing.

THE PARITY REQUIREMENT (why this file exists BEFORE the migration)
------------------------------------------------------------------
The safety net must be a NO-OP at the current schema: name-anchored extraction has to reproduce
positional extraction byte-for-byte while `feature_order == CANONICAL_FEATURE_ORDER`. Only once
that is proven can the vector be allowed to change.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from engines import zone_gate_engine as zge                       # noqa: E402
from features.feature_schema import CANONICAL_FEATURE_ORDER       # noqa: E402

# The PROMOTED runtime artifact (zone_gate_registry.json active entry). Repointed to the v4 remap
# on 2026-07-22; the v3 file is retained below purely to prove the safety net still rejects it.
REGISTRY = ROOT / "models" / "zone_registry_v4_2026_07.json"
REGISTRY_V3 = ROOT / "models" / "zone_registry.json"


def _features(order=CANONICAL_FEATURE_ORDER) -> dict:
    """A deterministic, distinguishable value per feature (index-valued)."""
    return {name: float(i) for i, name in enumerate(order)}


# ── 1. parity: the safety net changes nothing at the current schema ─────────────────────────
def test_name_anchored_equals_positional_at_current_schema():
    feats = _features()
    positional = zge._extract_vector(feats)
    named = zge._extract_vector(feats, list(CANONICAL_FEATURE_ORDER))
    assert positional == named
    assert len(positional) == len(CANONICAL_FEATURE_ORDER)


def test_registry_feature_order_matches_live_schema_today():
    """Pins the CURRENT alignment. When the schema moves, this must be updated deliberately
    together with a registry remap — never by loosening the assertion.

    v4.0: the registry scores a SUBSET, so the assertion is containment + order-preservation
    rather than equality (see test_v4_registry_scores_a_strict_subset_of_the_schema)."""
    if not REGISTRY.is_file():
        pytest.skip(f"registry absent: {REGISTRY}")
    order = json.loads(REGISTRY.read_text(encoding="utf-8")).get("feature_order")
    assert order, "the registry must carry a feature_order — it is the alignment anchor"
    live = list(CANONICAL_FEATURE_ORDER)
    assert set(order) <= set(live), f"names absent from the live schema: {set(order) - set(live)}"
    # relative order must still follow the canonical order (the remap renamed, it did not reorder)
    assert order == [n for n in live if n in set(order)]


# ── 2. the truncation path is gone ──────────────────────────────────────────────────────────
def test_longer_order_is_not_truncated():
    """The exact defect: an over-length request must NOT be silently trimmed to the schema dim.

    Under the old code this returned a 38-vector (`vector[:CANONICAL_FEATURE_DIM]`), silently
    dropping the tail. The vector must now be exactly as long as the order it was asked for.
    """
    order = list(CANONICAL_FEATURE_ORDER) + ["a_new_feature", "another_new_feature"]
    feats = _features(order)
    vector = zge._extract_vector(feats, order)
    assert len(vector) == len(order) == len(CANONICAL_FEATURE_ORDER) + 2
    assert vector[-1] == float(len(order) - 1), "tail feature was dropped — truncation is back"


def test_shorter_trained_order_scores_on_the_trained_subset():
    """A registry trained on FEWER features than the live schema stays aligned to its own order.

    This is the case the old truncation pretended to serve: it trimmed the SCHEMA's tail, which is
    only correct if the trained order is a strict prefix. Name-anchoring makes prefix-ness
    irrelevant — any subset, in any order, aligns correctly.
    """
    trained = [CANONICAL_FEATURE_ORDER[i] for i in (5, 0, 12, 3)]
    feats = _features()
    vector = zge._extract_vector(feats, trained)
    assert vector == [5.0, 0.0, 12.0, 3.0]


def test_reordered_feature_order_changes_the_vector():
    """Name-anchoring must actually re-order — proving the model's order wins, not the schema's."""
    feats = _features()
    swapped = list(CANONICAL_FEATURE_ORDER)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    v_default = zge._extract_vector(feats)
    v_swapped = zge._extract_vector(feats, swapped)
    assert v_swapped[0] == v_default[1] and v_swapped[1] == v_default[0]
    assert v_swapped != v_default


def test_missing_trained_feature_raises_named_error():
    feats = _features()
    feats.pop(CANONICAL_FEATURE_ORDER[5])
    with pytest.raises(ValueError, match="feature_order"):
        zge._extract_vector(feats, list(CANONICAL_FEATURE_ORDER))


# ── 3. fail-CLOSED, not fail-open, end to end ───────────────────────────────────────────────
def test_alignment_failure_blocks_rather_than_passes():
    """run_zone_gate_engine must convert an extraction failure into a BLOCK.

    A gate that cannot align its vector must never return passed=True — that would turn a hard
    gate into a silent pass-through, the failure mode this whole floor exists to prevent.
    """
    feats = _features()
    feats.pop(CANONICAL_FEATURE_ORDER[0])

    out = zge.run_zone_gate_engine(
        raw_features={**_features(), **{}},   # complete dict passes canonical filtering
        model_fn=lambda v: 1.0,
        threshold=0.5,
        feature_order=list(CANONICAL_FEATURE_ORDER) + ["absent_feature"],
    )
    assert out["passed"] is False
    assert out["valid"] is False
    assert out["score"] == 0.0


def test_zone_feature_order_error_is_not_swallowed_by_fail_open():
    """A registry trained on a feature the live schema no longer has must refuse to load."""
    from engines.live_engine import BitNetZoneGate, ZoneFeatureOrderError

    gate = BitNetZoneGate.disabled()
    gate.enabled = True
    bad = ROOT / "tests" / "_tmp_bad_zone_registry.json"
    bad.write_text(json.dumps({
        "feature_order": list(CANONICAL_FEATURE_ORDER) + ["feature_that_no_longer_exists"],
        "zones": [],
    }), encoding="utf-8")
    try:
        with pytest.raises(ZoneFeatureOrderError, match="absent from the live schema"):
            gate._load_registry(str(bad))
    finally:
        bad.unlink(missing_ok=True)


def test_live_registry_loads_and_exposes_feature_order():
    from engines.live_engine import BitNetZoneGate

    if not REGISTRY.is_file():
        pytest.skip(f"registry absent: {REGISTRY}")
    gate = BitNetZoneGate(zone_path=str(REGISTRY))
    assert gate.feature_order is not None, "live registry must expose its trained feature_order"
    live = set(CANONICAL_FEATURE_ORDER)
    assert set(gate.feature_order) <= live, "trained names must all exist in the live schema"


def test_retired_v3_registry_still_fails_closed():
    """The v3 artifact is retained for rollback — prove it CANNOT be loaded under v4.

    This is the regression that matters: if someone repoints the config back at the old file, the
    gate must refuse rather than silently score a misaligned vector.
    """
    from engines.live_engine import BitNetZoneGate, ZoneFeatureOrderError

    if not REGISTRY_V3.is_file():
        pytest.skip(f"v3 registry absent: {REGISTRY_V3}")
    with pytest.raises(ZoneFeatureOrderError, match="absent from the live schema"):
        BitNetZoneGate(zone_path=str(REGISTRY_V3))


def test_v4_registry_scores_a_strict_subset_of_the_schema():
    """feature_order is a 38-name SUBSET of the 39-dim v4 vector.

    `macd_hist_raw` is deliberately absent — no trained statistics exist for it — and `session` is
    present but zero-weighted. Both facts are load-bearing: a future reader must not assume
    scored_dims == schema_dim.
    """
    import json

    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    order = reg["feature_order"]
    assert len(order) == 38 and len(CANONICAL_FEATURE_ORDER) == 39
    assert "macd_hist_raw" not in order
    assert {"candle_range", "macd_hist_z"} <= set(order)
    si = order.index("session")
    assert all(z["weights"][si] == 0.0 for z in reg["zones"]), "session must be zero-weighted"
    for z in reg["zones"]:
        assert sum(1 for w in z["weights"] if w != 0) == 24

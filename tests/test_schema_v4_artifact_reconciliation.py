"""Schema-v4 artifact reconciliation floor (B6, 2026-07-22).

Five trained artifacts had to be accounted for when CANONICAL_FEATURES moved 38 -> 39. Exactly one
of them is live, and it is the only one that could mis-decide:

    zone_registry   LIVE HARD GATE (F-041, zone_mode=hard)  -> REMAPPED + promoted
    rr_model        inert, rr_fusion.enabled=false (F-038)  -> QUARANTINED (positional, unremappable)
    gaussian        inert, reads 3 features BY NAME (F-060) -> stamped, no change expected
    bitnet          inert, use_bitnet=false (F-004)         -> load-time guard
    tradenet        unwired (F-005)                         -> stamped

This floor asserts the RECONCILIATION DECISIONS, not the model math. Its job is to make the state
of each artifact explicit, so nobody has to infer "is this thing safe under v4?" from silence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from features.feature_schema import (            # noqa: E402
    CANONICAL_FEATURE_DIM,
    CANONICAL_FEATURE_ORDER,
    SCHEMA_VERSION,
)

MODELS = ROOT / "models"
ZONE_V4 = MODELS / "zone_registry_v4_2026_07.json"
ZONE_V3 = MODELS / "zone_registry.json"
ZONE_MANIFEST = MODELS / "zone_gate_registry.json"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# ── the schema itself ───────────────────────────────────────────────────────────────────────
def test_schema_is_v4():
    assert SCHEMA_VERSION == "4.0"
    assert CANONICAL_FEATURE_DIM == 39 == len(CANONICAL_FEATURE_ORDER)
    assert {"macd_hist_raw", "macd_hist_z", "candle_range"} <= set(CANONICAL_FEATURE_ORDER)
    assert not ({"macd_hist", "wick_size"} & set(CANONICAL_FEATURE_ORDER)), (
        "v3 names must be gone from the canonical vector — they survive only as read-side aliases"
    )


def test_v3_read_aliases_exist_for_historical_records():
    """Stored records (opportunities.jsonl, old training sets) still carry the v3 names."""
    from features.feature_schema import SCHEMA_V3_ALIASES

    assert SCHEMA_V3_ALIASES["wick_size"] == "candle_range"
    # v3's emitted `macd_hist` was the Z-SCORED value (compute_normalization overwrote in place),
    # so the honest alias target is macd_hist_z, NOT macd_hist_raw.
    assert SCHEMA_V3_ALIASES["macd_hist"] == "macd_hist_z"


# ── B6.1 ZoneGate: the only live artifact ───────────────────────────────────────────────────
def test_zone_v4_is_the_promoted_active_version():
    m = _load(ZONE_MANIFEST)
    active = [k for k, v in m.items() if isinstance(v, dict) and v.get("active")]
    assert active == ["v4_gaussian_runtime_2026_07"], f"expected one v4 active, got {active}"
    assert m[active[0]]["model_file"] == "models/zone_registry_v4_2026_07.json"
    old = m["v2_gaussian_runtime_2026_07"]
    assert old["active"] is False and old["superseded_by"] == "v4_gaussian_runtime_2026_07", (
        "the v3 entry must be RETAINED and demoted, not deleted (§6.2 rule 4)"
    )


def test_zone_v4_mu_sigma_are_byte_identical_to_v3():
    """The remap is a RELABEL, not a retrain. If any mu/sigma moved, that claim is false."""
    v3, v4 = _load(ZONE_V3), _load(ZONE_V4)
    assert len(v3["zones"]) == len(v4["zones"]) == 8
    for a, b in zip(v3["zones"], v4["zones"]):
        assert a["id"] == b["id"]
        assert a["mu"] == b["mu"], f"{a['id']}: mu moved — this would make it a retrain"
        assert a["sigma"] == b["sigma"], f"{a['id']}: sigma moved"


def test_zone_v4_changes_exactly_one_weight():
    """Only `session` is zeroed. Any other weight change is unaccounted-for drift."""
    v3, v4 = _load(ZONE_V3), _load(ZONE_V4)
    si = v4["feature_order"].index("session")
    for a, b in zip(v3["zones"], v4["zones"]):
        for i, (wa, wb) in enumerate(zip(a["weights"], b["weights"])):
            if i == si:
                assert wb == 0.0, f"{b['id']}: session must be zero-weighted"
                assert wa != 0.0, "v3 session was expected to be weighted"
            else:
                assert wa == wb, f"{b['id']}: weight {i} changed unexpectedly"


def test_zone_v4_renames_are_the_only_feature_order_change():
    v3, v4 = _load(ZONE_V3), _load(ZONE_V4)
    expected = [{"wick_size": "candle_range", "macd_hist": "macd_hist_z"}.get(n, n)
                for n in v3["feature_order"]]
    assert v4["feature_order"] == expected
    assert v4["schema_version"] == "v4_gaussian"


def test_zone_v4_provenance_records_the_decision_and_its_evidence():
    prov = _load(MODELS / "zone_registry_v4_2026_07.provenance.json")
    assert prov["change_class"] == "ALIGNMENT_REMAP"
    assert prov["zeroed_weights"] == ["session"]
    assert prov["measured_impact"]["decision_flips"] == 0
    assert prov["active_dims"] == {"before": 25, "after": 24}
    # PIT status must survive the remap — relabelling cannot clean contamination (F-051)
    assert prov["pit_status"] == "PIT_UNCLEAN_CENTERED_SWINGS"
    assert prov["authority"].startswith("NONE")


def test_zone_v4_loads_and_v3_does_not():
    from engines.live_engine import BitNetZoneGate, ZoneFeatureOrderError

    gate = BitNetZoneGate(zone_path=str(ZONE_V4))
    assert gate.feature_order and set(gate.feature_order) <= set(CANONICAL_FEATURE_ORDER)
    with pytest.raises(ZoneFeatureOrderError):
        BitNetZoneGate(zone_path=str(ZONE_V3))


def test_active_config_points_at_the_promoted_artifact():
    version = (ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    cfg = _load(ROOT / "configs" / "production" / f"{version}.json")
    assert cfg["engine_runner"]["zone_registry_path"] == "models/zone_registry_v4_2026_07.json"


# ── B6.2 RR: quarantined, not remapped ──────────────────────────────────────────────────────
@pytest.mark.parametrize("name", [
    "rr_model.json", "rr_model_202605_bnb_v1.json", "rr_model_202605_bnb_v2.json",
])
def test_rr_models_are_quarantined_not_remapped(name):
    d = _load(MODELS / name)
    assert d["schema_version"] == "3.0"
    assert d["incompatible_with_schema"] == "4.0"
    assert d["quarantine_reason"]
    # the vectors must be UNTOUCHED — a positional remap is impossible, so attempting one
    # would be worse than quarantining
    assert d["n_features"] == 38 and len(d["ridge_w"]) == 38 and len(d["scale_mu"]) == 38
    assert "schema_hash" not in d, (
        "these artifacts never carried a schema_hash; adding one now would fabricate provenance"
    )


def test_rr_fusion_stays_disabled():
    """The quarantine is only safe because nothing loads these (F-038)."""
    version = (ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    cfg = _load(ROOT / "configs" / "production" / f"{version}.json")
    assert cfg["engine_runner"]["rr_fusion"]["enabled"] is False


# ── B6.3/B6.5 stamped-only artifacts ────────────────────────────────────────────────────────
def test_gaussian_registry_stamped_and_name_addressed():
    g = _load(MODELS / "gaussian_registry.json")
    assert "_schema_v4_note" in g
    # the three features the live kernel reads BY NAME must all still exist in v4
    assert {"ema_fast", "ema_slow", "momentum_score"} <= set(CANONICAL_FEATURE_ORDER)


def test_gaussian_nb_name_anchored_load_under_v4():
    """P0 contract: trained 38/35 checkpoints load via alias remap, not ambient equality.

    Live spine stays heuristic (F-060); this proves the ML path is no longer FAIL_OPEN
    (silent truncate) and no longer hard-refuses solely because v3 names differ.
    """
    from training.trainer import load_gaussian_model

    model, scaler, meta = load_gaussian_model(
        "BNBUSDT/bnbusdt_balanced_20260524/gaussian_p5_20260524T120449.json"
    )
    assert model.n_features == 38
    assert meta["name_anchored"] is True
    assert meta["schema_alignment"] == "named_subset"
    assert "macd_hist_z" in meta["feature_schema_resolved"]
    assert "candle_range" in meta["feature_schema_resolved"]
    assert scaler is not None


def test_tradenet_registry_stamped():
    t = _load(MODELS / "tradenet_registry.json")
    assert "_schema_v4_note" in t


# ── B6.4 BitNet: the guard must fail closed at LOAD, not at import ──────────────────────────
def test_bitnet_canonical_guard_fails_closed_without_blocking_import():
    """The import-time assert took the whole spine down (crt_engine_v2 -> bitnet_inference).

    Importing must succeed; SERVING a canonical-v3 envelope must not.
    """
    from bitnet import model_contract as mc

    assert mc.BITNET_V3_FEATURE_DIM == 38
    assert mc.CANONICAL_ENVELOPE_SUPPORTED is False, (
        "a 38-dim canonical envelope cannot be served under a 39-dim schema"
    )
    with pytest.raises(RuntimeError, match="retrained or remapped"):
        mc.assert_canonical_dim()


def test_bitnet_stays_disabled_on_the_active_config():
    version = (ROOT / "configs" / "production" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
    cfg = _load(ROOT / "configs" / "production" / f"{version}.json")
    assert cfg["crt_engine"]["use_bitnet"] is False

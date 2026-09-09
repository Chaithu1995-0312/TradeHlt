"""provenance.py — versioned realism/method stamps for research artifacts.

Every `edge_report.json` carries these so a stored verdict is permanently interpretable:
the assumed execution reality, the cost model, and (at M4) the qualification method. The
research↔spine realism difference is therefore self-documenting and greppable — it can
never drift unnoticed. Bump a version whenever the thing it names changes.

target-strategy-architecture.md §14.D also asks for "config hash, feature schema hash" on
every experiment record — `production_config_block()` below closes that: it stamps which
PRODUCTION config (ACTIVE_VERSION + its hash) and which canonical feature schema were live
when the research ran, so a finding can be tied back to the spine truth it was measured
against. This is DISTINCT from `cfg.sha256()` (the research config's own hash, stamped
separately at each call site) — one says "which research recipe", this says "which spine
truth". `strategy_id` is deliberately NOT stamped here: no research config currently
declares one (`ResearchConfig` has no such field) — adding it is a real feature addition,
out of scope for this provenance stamp. Fail-open: if the production registry can't be
read (e.g. in an isolated test), the block degrades to `None` fields rather than raising —
provenance is best-effort and must never block a research run.
"""

from __future__ import annotations

# Execution-reality standard shared with the live spine's governed exit model.
# Bump when exit geometry / slippage model / tie-break changes.
TRUTH_STANDARD_VERSION = "2.0"

# Research uses a deterministic flat round-trip cost (preserves byte-identical
# determinism); the spine uses seeded-random ATR-fraction slippage + spread. The two
# are intentionally different — versioned so the divergence stays explicit.
RESEARCH_COST_MODEL_VERSION = "1.0"
SPINE_COST_MODEL_VERSION = "1.0"


def truth_standard_block(
    exit_model: str,
    round_trip_bps: float,
    *,
    cost_model: dict | None = None,
    fill_model: dict | None = None,
) -> dict:
    """The execution-reality stamp for a research artifact.

    `cost_model` / `fill_model` are optional and ADDITIVE: when both are omitted the
    returned dict is byte-identical to the pre-2026-08-19 shape, so every existing
    artifact keeps its provenance unchanged.

    Supply them when a run uses the SEM-015 component cost model or the SEM-016
    adverse-fill model, so a result carries the ruler that produced it. A result whose
    measurement basis cannot be recovered from its own artifact is precisely the gap
    MEASUREMENT_CONTRACT.md was written about.

    Args:
        cost_model: e.g. `ComponentCostModel.provenance()` — model id, instrument,
            source manifest sha256, per-component values, entry-slippage basis.
        fill_model: how a triggered stop filled, e.g.
            `{"model": "adverse_fill", "ontology_id": "SEM-016",
              "stop_slippage": 0.09, "model_gaps": True}`.
    """
    block = {
        "version": TRUTH_STANDARD_VERSION,
        "exit_geometry": exit_model,
        "slippage_model": f"flat_{round_trip_bps:g}bps",
        "tie_break": "SL_before_TP",
    }
    if cost_model is not None:
        # The flat bps figure is retained above as provenance of what WOULD have been
        # charged, so a reader can see both rulers side by side rather than only the
        # one that won.
        block["slippage_model"] = cost_model.get("cost_model_id", "component_measured")
        block["flat_bps_superseded"] = f"flat_{round_trip_bps:g}bps"
        block["cost_model"] = cost_model
    block["fill_model"] = fill_model if fill_model is not None else "perfect_stop_fill"
    return block


def production_config_block() -> dict:
    """Which PRODUCTION config + canonical feature schema were live for this research run.

    Fail-open by design (see module docstring) — never raises.
    """
    config_version = None
    config_hash = None
    try:
        from config_layer.production_config import get_prod_metadata
        meta = get_prod_metadata()
        config_version = meta.get("version")
        config_hash = meta.get("config_hash")
    except Exception:
        pass

    feature_schema_hash = None
    try:
        from features.feature_schema import FEATURE_ORDER_HASH
        feature_schema_hash = FEATURE_ORDER_HASH
    except Exception:
        pass

    return {
        "config_version": config_version,
        "config_hash": config_hash,
        "feature_schema_hash": feature_schema_hash,
    }


def provenance_block(
    exit_model: str,
    round_trip_bps: float,
    *,
    cost_model: dict | None = None,
    fill_model: dict | None = None,
) -> dict:
    """Realism + cost-model + production-truth provenance (M4 adds qual/method versions).

    `cost_model` / `fill_model` pass through to `truth_standard_block`; omitting both
    reproduces the historical block exactly.
    """
    return {
        "truth_standard": truth_standard_block(
            exit_model, round_trip_bps, cost_model=cost_model, fill_model=fill_model
        ),
        "research_cost_model_version": RESEARCH_COST_MODEL_VERSION,
        "spine_cost_model_version": SPINE_COST_MODEL_VERSION,
        **production_config_block(),
    }

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


def truth_standard_block(exit_model: str, round_trip_bps: float) -> dict:
    """The execution-reality stamp for a research artifact."""
    return {
        "version": TRUTH_STANDARD_VERSION,
        "exit_geometry": exit_model,
        "slippage_model": f"flat_{round_trip_bps:g}bps",
        "tie_break": "SL_before_TP",
    }


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


def provenance_block(exit_model: str, round_trip_bps: float) -> dict:
    """Realism + cost-model + production-truth provenance (M4 adds qual/method versions)."""
    return {
        "truth_standard": truth_standard_block(exit_model, round_trip_bps),
        "research_cost_model_version": RESEARCH_COST_MODEL_VERSION,
        "spine_cost_model_version": SPINE_COST_MODEL_VERSION,
        **production_config_block(),
    }

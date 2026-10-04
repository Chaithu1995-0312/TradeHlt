"""research.synthetic — deterministic market-STORY library (ERP P1 golden fixtures).

A behavior-agnostic, research-isolated layer that turns SCRIPTED market stories into
intended-vs-produced golden traces validated at SIX layers:

    Family -> Story -> Market States -> CRT States -> Feature Signature -> Engine Signature -> Outcome

It sits ON TOP of the certified executable substrate and NEVER modifies it:
  - 9 CRT runtime states  (config_layer.crt_engine_v2)      [read-only, for CRT-path validation]
  - 38 canonical features (features.feature_schema)          [read-only, name discipline]
  - the real engine callables (engines.*)                    [reused verbatim]

Story geometry lives in CODE (Decision D-23). The semantic vocabulary (families / states / layers /
feature+engine signatures) lives in configs/research/market_story_ontology.yaml (descriptive-only,
§6.5 — grants NO runtime or promotion authority).

Generalized from the single-story scripts/research/erp_synth_4h_trace.py (which is left untouched
and reproduced byte-for-byte as the `liq_sweep_reversal_long` parity anchor).
"""
from __future__ import annotations

from research.synthetic.story_spec import (  # noqa: F401
    EntryContract,
    EntrySignal,
    PhaseBar,
    StorySpec,
)

__all__ = ["EntryContract", "EntrySignal", "PhaseBar", "StorySpec"]

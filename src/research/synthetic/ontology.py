"""ontology.py — loader + six-layer binder for the market-story ontology.

Reads configs/research/market_story_ontology.yaml (descriptive-only; §6.5 grants NO runtime or
promotion authority) and validates a StorySpec against the real executable substrate:

  L1 family      — family exists & active; phase structure-skeleton ⊆ canonical_state_sequence
  L2 states      — every declared/used market state exists; phase tags are structure-layer states
  L3 crt_states  — phase-derived CRT path == expected AND is a legal walk in VALID_TRANSITIONS
  L4 features    — expected_feature_signature ⊆ CANONICAL_FEATURES ∩ (union of state signatures)
  L5 engines     — produced engine scores map to the declared bands
  L6 outcome     — produced forward_walk outcome == expected (+ rr floor when TP_HIT)

CRT-path truth is read from config_layer (the authoritative enum + seed graph) — never duplicated.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from features.feature_schema import CANONICAL_FEATURES

_ROOT = Path(__file__).resolve().parents[3]
ONTOLOGY_PATH = _ROOT / "configs" / "research" / "market_story_ontology.yaml"

_EPS = 1e-9


def load_raw(path: Path | str | None = None) -> dict:
    p = Path(path) if path else ONTOLOGY_PATH
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _crt_names() -> set[str]:
    from config_layer.state_identity import CRTState
    return {s.name for s in CRTState}


def crt_path_is_legal(crt_names: list[str]) -> tuple[bool, str]:
    """True if the (consecutive-deduped) CRT-state name sequence is a legal walk in the module
    seed VALID_TRANSITIONS. Empty/single paths are trivially legal."""
    from config_layer.state_identity import CRTState
    from config_layer.state_topology import module_seed_transition_graph

    graph = module_seed_transition_graph()
    try:
        states = [CRTState[n] for n in crt_names]
    except KeyError as exc:
        return False, f"unknown CRT state {exc}"
    collapsed: list = []
    for s in states:
        if not collapsed or collapsed[-1] != s:
            collapsed.append(s)
    for a, b in zip(collapsed, collapsed[1:]):
        if b not in tuple(graph.get(a, ())):
            return False, f"illegal edge {a.name}->{b.name}"
    return True, "ok"


def _dedup_consecutive(seq: list) -> list:
    out: list = []
    for x in seq:
        if not out or out[-1] != x:
            out.append(x)
    return out


def _is_subsequence(sub: list, seq: list) -> bool:
    it = iter(seq)
    return all(x in it for x in sub)


class StoryOntology:
    """Parsed ontology with lookups + the six-layer binder."""

    def __init__(self, raw: dict | None = None):
        self.raw = raw if raw is not None else load_raw()
        self.states: dict[str, dict] = {s["id"]: s for s in self.raw.get("market_states", [])}
        self.families: dict[str, dict] = {f["id"]: f for f in self.raw.get("families", [])}
        self.layers: dict[str, dict] = {ly["id"]: ly for ly in self.raw.get("layers", [])}
        self.bands: dict[str, Any] = self.raw.get("engine_signature_bands", {})

    # ── band mapping ────────────────────────────────────────────────────────
    def score_band(self, engine: str, value: float) -> str:
        b = self.bands[engine]
        if engine == "rr":
            if value >= b["strong"]:
                return "strong"
            if value < b["weak"]:
                return "weak"
            return "moderate"
        if value >= b["high"]:
            return "high"
        if value < b["low"]:
            return "low"
        return "neutral"

    # ── helpers ─────────────────────────────────────────────────────────────
    def is_structure(self, state_id: str) -> bool:
        st = self.states.get(state_id)
        return bool(st) and st.get("layer") == "structure"

    def crt_map(self, state_id: str) -> str | None:
        st = self.states.get(state_id, {})
        return st.get("crt_state_map")

    def derive_crt_path(self, spec) -> list[str]:
        names = [self.crt_map(ph.market_state) for ph in spec.phases]
        names = [n for n in names if n]
        return _dedup_consecutive(names)

    def phase_structure_skeleton(self, spec) -> list[str]:
        return _dedup_consecutive([ph.market_state for ph in spec.phases])

    # ── the six-layer binder ─────────────────────────────────────────────────
    def bind(self, spec, produced_engine_scores: dict, produced_outcome: str,
             produced_rr: float) -> dict:
        checks: dict[str, dict] = {}

        # L1 — family + phase skeleton subsequence of canonical_state_sequence
        fam = self.families.get(spec.family)
        l1_reasons: list[str] = []
        if fam is None:
            l1_reasons.append(f"family '{spec.family}' not in ontology")
        elif fam.get("status") != "active":
            l1_reasons.append(f"family '{spec.family}' not active")
        skeleton = self.phase_structure_skeleton(spec)
        if fam is not None:
            canon = list(fam.get("canonical_state_sequence", []))
            if not _is_subsequence(skeleton, canon):
                l1_reasons.append(f"phase skeleton {skeleton} not a subsequence of {canon}")
        checks["l1_family"] = {"pass": not l1_reasons, "skeleton": skeleton, "reasons": l1_reasons}

        # L2 — every declared + used state exists; phase tags are structure states
        l2_reasons: list[str] = []
        for sid in spec.expected_market_states:
            if sid not in self.states:
                l2_reasons.append(f"declared state '{sid}' not in ontology")
        for ph in spec.phases:
            if ph.market_state not in self.states:
                l2_reasons.append(f"phase state '{ph.market_state}' not in ontology")
            elif not self.is_structure(ph.market_state):
                l2_reasons.append(f"phase state '{ph.market_state}' is not a structure-layer state")
        checks["l2_market_states"] = {"pass": not l2_reasons, "reasons": l2_reasons}

        # L3 — derived CRT path == expected AND legal walk
        derived = self.derive_crt_path(spec)
        expected_crt = list(spec.expected_crt_states)
        legal, legal_msg = crt_path_is_legal(derived)
        l3_pass = derived == expected_crt and legal
        checks["l3_crt_states"] = {
            "pass": l3_pass, "derived": derived, "expected": expected_crt,
            "legal_walk": legal, "legal_msg": legal_msg,
        }

        # L4 — feature signature ⊆ canonical ∩ union(state signatures)
        canonical = set(CANONICAL_FEATURES)
        state_union: set[str] = set()
        for sid in spec.expected_market_states:
            state_union.update(self.states.get(sid, {}).get("feature_signature", []))
        l4_reasons: list[str] = []
        for feat in spec.expected_feature_signature:
            if feat not in canonical:
                l4_reasons.append(f"'{feat}' not in CANONICAL_FEATURES")
            elif feat not in state_union:
                l4_reasons.append(f"'{feat}' not grounded in any declared state's signature")
        checks["l4_feature_signature"] = {"pass": not l4_reasons, "reasons": l4_reasons}

        # L5 — engine bands
        l5_detail: dict[str, dict] = {}
        l5_pass = True
        for eng, want in spec.expected_engine_signature.items():
            val = float(produced_engine_scores.get(eng, 0.0))
            got = self.score_band(eng, val)
            ok = got == want
            l5_pass = l5_pass and ok
            l5_detail[eng] = {"pass": ok, "value": round(val, 4), "expected": want, "produced": got}
        checks["l5_engine_signature"] = {"pass": l5_pass, "engines": l5_detail}

        # L6 — outcome (+ rr floor when TP)
        l6_reasons: list[str] = []
        if produced_outcome != spec.expected_outcome:
            l6_reasons.append(f"outcome {produced_outcome} != expected {spec.expected_outcome}")
        if spec.expected_outcome == "TP_HIT" and produced_rr + _EPS < spec.expected_rr_min:
            l6_reasons.append(f"rr {produced_rr} < floor {spec.expected_rr_min}")
        checks["l6_outcome"] = {
            "pass": not l6_reasons, "produced_outcome": produced_outcome,
            "produced_rr": round(float(produced_rr), 4), "reasons": l6_reasons,
        }

        all_pass = all(c["pass"] for c in checks.values())
        return {"all_pass": all_pass, "layers": checks}

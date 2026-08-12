"""
Phase 2B — typed same-event propositions (research shadow).

Converts co-present episode surfaces into closed-vocabulary relations:

  SAME_EVENT | ORTHOGONAL | CONFLICT | SILENT | INSUFFICIENT

Exit claims for 2B:
  O11  DIRECTION_ALIGNMENT          CRT.dir × trend_bias × shape dir
  O12  CHAPTER_VS_STRUCTURE_SCORE   CRT.state × crt structure_rule_score testimony

Diagnostic (not exit-blocking):
  QUALITY_VS_DIRECTION              gaussian/rr quality × CRT.dir
  MAGNITUDE_SUBSTRATE               Phase 2A magnitude states (substrate ≠ integration)

Non-goals (hard):
  - O14 Agreement object / verdict fold
  - New measurements, spine consumption, economic authority
  - Treating structure_rule_score as chapter validity without policy

Policy freeze (CHAPTER_VS_STRUCTURE_SCORE):
  POL-O12-SCORE-NOT-CHAPTER — crt testimony semantic ``structure_rule_score`` answers a
  quality/validity *question*, not the CRT *chapter* label. When both chapter and score are
  present, relation is ORTHOGONAL (declared non-join). Low score must NOT auto-CONFLICT with
  advanced CRT state under this policy.

Authority: research_shadow. PRODUCTION_BEHAVIOR_CHANGED=NO.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

RELATION_VOCAB: frozenset[str] = frozenset(
    {"SAME_EVENT", "ORTHOGONAL", "CONFLICT", "SILENT", "INSUFFICIENT"}
)

CLAIM_KINDS: frozenset[str] = frozenset(
    {
        "DIRECTION_ALIGNMENT",
        "CHAPTER_VS_STRUCTURE_SCORE",
        "QUALITY_VS_DIRECTION",
        "MAGNITUDE_SUBSTRATE",
    }
)

# Required for Phase 2B exit — every episode must emit these.
EXIT_CLAIM_KINDS: tuple[str, ...] = (
    "DIRECTION_ALIGNMENT",
    "CHAPTER_VS_STRUCTURE_SCORE",
)

POLICY_O12 = {
    "policy_id": "POL-O12-SCORE-NOT-CHAPTER",
    "meaning": (
        "CRT structure_rule_score is quality testimony about structure validity questions; "
        "it is not a co-descriptor of CRT chapter membership. Advanced chapter + any score "
        "level is ORTHOGONAL under this policy — not automatic CONFLICT."
    ),
}

POLICY_QUALITY_DIR = {
    "policy_id": "POL-QUALITY-NOT-DIRECTION",
    "meaning": (
        "Gaussian/RR quality scores answer profitability/structure-quality questions; "
        "they do not assert CRT directional chapter. Default ORTHOGONAL."
    ),
}

POLICY_MAG_SUBSTRATE = {
    "policy_id": "POL-2A-SUBSTRATE-NOT-INTEGRATION",
    "meaning": (
        "Phase 2A magnitude states interpret continuous measurements; they do not by themselves "
        "assert same-event integration with CRT/shape/testimony."
    ),
}

# CRT chapters where structure-score vs chapter co-presence is adjudicated.
_ADVANCED_CHAPTERS = frozenset(
    {"SWEEP", "DISPLACEMENT", "EXPANSION", "RETEST", "EXECUTION", "RESOLUTION"}
)

_CRT_STRUCTURE_SEMANTIC = "structure_rule_score"


@dataclass(frozen=True)
class Proposition:
    """One typed cross-layer claim about an episode (research shadow)."""

    proposition_id: str
    episode_id: str
    claim_kind: str
    relation: str
    surfaces: dict[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    resolution: dict[str, str] | None = None
    authority: str = "research_shadow"
    observation_id: str | None = None  # O11 / O12 / None for diagnostic

    def __post_init__(self) -> None:
        if self.claim_kind not in CLAIM_KINDS:
            raise ValueError(f"unknown claim_kind {self.claim_kind!r}")
        if self.relation not in RELATION_VOCAB:
            raise ValueError(f"unknown relation {self.relation!r}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_refs"] = list(self.evidence_refs)
        return d


def dir_sign_crt(direction: Any) -> int:
    if direction is None:
        return 0
    s = str(direction).upper()
    if s in ("LONG", "BUY", "BULL", "1"):
        return 1
    if s in ("SHORT", "SELL", "BEAR", "-1"):
        return -1
    if s in ("NONE", "0", "FLAT", "NEUTRAL", ""):
        return 0
    return 0


def dir_sign_trend(trend_bias: Any) -> int:
    if trend_bias is None:
        return 0
    s = str(trend_bias)
    if "Bull" in s:
        return 1
    if "Bear" in s:
        return -1
    return 0


def dir_sign_shape(name: Any) -> int:
    if not name:
        return 0
    n = str(name).lower()
    if "bear" in n or "sell" in n:
        return -1
    if "bull" in n or "buy" in n:
        return 1
    return 0


def relation_to_census_class(relation: str, *, observation: str) -> str:
    """Map proposition relation → legacy census class for O11/O12 continuity."""
    if observation == "O11_crt_dir_vs_context_shape":
        return {
            "SAME_EVENT": "COVERED",
            "CONFLICT": "CONTRADICTORY",
            "INSUFFICIENT": "PARTIAL",
            "SILENT": "PARTIAL",
            "ORTHOGONAL": "PARTIAL",  # unexpected for O11; treat soft
        }.get(relation, "UNKNOWN")
    if observation == "O12_crt_story_vs_structure_score":
        # ORTHOGONAL is the *resolved* non-join — census COVERED means "represented with policy"
        return {
            "ORTHOGONAL": "COVERED",
            "SAME_EVENT": "COVERED",
            "CONFLICT": "CONTRADICTORY",
            "INSUFFICIENT": "PARTIAL",
            "SILENT": "PARTIAL",
        }.get(relation, "UNKNOWN")
    return "UNKNOWN"


def _crt_direction(ep: Mapping[str, Any]) -> Any:
    crt = ep.get("crt") or {}
    ev = crt.get("event") or {}
    return ev.get("direction")


def _crt_state(ep: Mapping[str, Any]) -> str | None:
    crt = ep.get("crt") or {}
    return crt.get("state")


def _crt_testimony(ep: Mapping[str, Any]) -> dict[str, Any] | None:
    me = ep.get("model_evidence") or {}
    vals = me.get("values") or {}
    crt_t = vals.get("crt")
    return crt_t if isinstance(crt_t, dict) else None


def build_direction_alignment(ep: Mapping[str, Any]) -> Proposition:
    eid = str(ep.get("episode_id") or "")
    cdir_raw = _crt_direction(ep)
    cdir = dir_sign_crt(cdir_raw)
    fs = ep.get("feature_states") or {}
    trend = fs.get("trend_bias")
    tdir = dir_sign_trend(trend)
    shape = ep.get("market_shape") or {}
    shape_name = shape.get("name") or shape.get("label")
    sdir = dir_sign_shape(shape_name)

    surfaces = {
        "crt": {
            "state": _crt_state(ep),
            "direction": cdir_raw,
            "dir_sign": cdir,
        },
        "context": {"trend_bias": trend, "dir_sign": tdir},
        "shape": {
            "name": shape_name,
            "family": shape.get("family"),
            "dir_sign": sdir,
            "matched": shape.get("matched"),
        },
        "state": ep.get("magnitude_states") or {},
    }
    refs = [
        "crt.event.direction",
        "feature_states.trend_bias",
        "market_shape.name",
    ]

    if cdir == 0:
        rel = "INSUFFICIENT"
        note = "no CRT direction on anchor"
    elif tdir == 0 and sdir == 0:
        rel = "INSUFFICIENT"
        note = "trend and shape direction neutral/absent"
    else:
        conflicts: list[str] = []
        if tdir != 0 and cdir != tdir:
            conflicts.append(f"CRT_dir={cdir_raw} vs trend_bias={trend}")
        if sdir != 0 and cdir != sdir:
            conflicts.append(f"CRT_dir={cdir_raw} vs shape={shape_name}")
        if conflicts:
            rel = "CONFLICT"
            note = "; ".join(conflicts)
        else:
            rel = "SAME_EVENT"
            note = f"CRT_dir={cdir_raw} aligns with trend/shape"

    surfaces["adjudication_note"] = note
    return Proposition(
        proposition_id="P-O11-dir",
        episode_id=eid,
        claim_kind="DIRECTION_ALIGNMENT",
        relation=rel,
        surfaces=surfaces,
        evidence_refs=tuple(refs),
        resolution=None,
        observation_id="O11",
    )


def build_chapter_vs_structure_score(ep: Mapping[str, Any]) -> Proposition:
    """O12 under POL-O12-SCORE-NOT-CHAPTER (pinned semantic: structure_rule_score)."""
    eid = str(ep.get("episode_id") or "")
    chapter = _crt_state(ep)
    testimony = _crt_testimony(ep)
    me = ep.get("model_evidence") or {}
    absent = list(me.get("absent") or [])

    surfaces: dict[str, Any] = {
        "crt": {"state": chapter, "direction": _crt_direction(ep)},
        "testimony": None,
        "policy": POLICY_O12,
    }
    refs = ["crt.state", "model_evidence.values.crt"]

    if testimony is None:
        if "crt" in absent or "crt" in {str(a).split(":")[0] for a in absent}:
            rel = "SILENT"
            note = "crt testimony declared absent"
        else:
            rel = "INSUFFICIENT"
            note = "crt testimony missing from model_evidence.values"
        surfaces["adjudication_note"] = note
        return Proposition(
            proposition_id="P-O12-chapter-score",
            episode_id=eid,
            claim_kind="CHAPTER_VS_STRUCTURE_SCORE",
            relation=rel,
            surfaces=surfaces,
            evidence_refs=tuple(refs),
            resolution=dict(POLICY_O12),
            observation_id="O12",
        )

    semantic = str(testimony.get("semantic") or "")
    value = testimony.get("value")
    surfaces["testimony"] = {
        "model_id": "crt",
        "semantic": semantic,
        "value": value,
        "question": testimony.get("question"),
        "status": testimony.get("status"),
        "pinned_semantic": _CRT_STRUCTURE_SEMANTIC,
    }
    refs = (
        "crt.state",
        "model_evidence.values.crt.value",
        "model_evidence.values.crt.semantic",
    )

    # Pin: only structure_rule_score is the O12 testimony channel.
    if semantic and semantic != _CRT_STRUCTURE_SEMANTIC:
        surfaces["adjudication_note"] = (
            f"crt testimony semantic={semantic!r} ≠ pinned {_CRT_STRUCTURE_SEMANTIC!r}"
        )
        return Proposition(
            proposition_id="P-O12-chapter-score",
            episode_id=eid,
            claim_kind="CHAPTER_VS_STRUCTURE_SCORE",
            relation="INSUFFICIENT",
            surfaces=surfaces,
            evidence_refs=refs,
            resolution=dict(POLICY_O12),
            observation_id="O12",
        )

    if value is None:
        surfaces["adjudication_note"] = "structure_rule_score value is null"
        return Proposition(
            proposition_id="P-O12-chapter-score",
            episode_id=eid,
            claim_kind="CHAPTER_VS_STRUCTURE_SCORE",
            relation="INSUFFICIENT",
            surfaces=surfaces,
            evidence_refs=refs,
            resolution=dict(POLICY_O12),
            observation_id="O12",
        )

    if not chapter or chapter in ("WARMUP", "UNKNOWN"):
        surfaces["adjudication_note"] = f"CRT chapter not adjudicable: {chapter}"
        rel = "INSUFFICIENT"
    else:
        # Policy: chapter and structure_rule_score are ORTHOGONAL channels.
        # Document score level for research; never auto-CONFLICT on low score.
        surfaces["adjudication_note"] = (
            f"CRT={chapter} with structure_rule_score={value} — ORTHOGONAL per "
            f"{POLICY_O12['policy_id']} (score ≠ chapter membership)"
        )
        surfaces["chapter_advanced"] = chapter in _ADVANCED_CHAPTERS
        rel = "ORTHOGONAL"

    return Proposition(
        proposition_id="P-O12-chapter-score",
        episode_id=eid,
        claim_kind="CHAPTER_VS_STRUCTURE_SCORE",
        relation=rel,
        surfaces=surfaces,
        evidence_refs=refs,
        resolution=dict(POLICY_O12),
        observation_id="O12",
    )


def build_quality_vs_direction(ep: Mapping[str, Any]) -> Proposition:
    eid = str(ep.get("episode_id") or "")
    cdir_raw = _crt_direction(ep)
    me = ep.get("model_evidence") or {}
    vals = me.get("values") or {}
    g = vals.get("gaussian") or {}
    rr = vals.get("rr_model") or {}
    surfaces = {
        "crt": {"direction": cdir_raw, "state": _crt_state(ep)},
        "testimony": {
            "gaussian": {
                "value": g.get("value"),
                "semantic": g.get("semantic"),
                "question": g.get("question"),
            },
            "rr_model": {
                "value": rr.get("value"),
                "semantic": rr.get("semantic"),
                "question": rr.get("question"),
            },
        },
    }
    if g.get("value") is None and rr.get("value") is None:
        rel = "SILENT"
        note = "no quality testimony values"
    elif dir_sign_crt(cdir_raw) == 0:
        rel = "INSUFFICIENT"
        note = "quality present but CRT direction absent — no directional join demanded"
    else:
        rel = "ORTHOGONAL"
        note = "quality scores are non-directional under POL-QUALITY-NOT-DIRECTION"
    surfaces["adjudication_note"] = note
    return Proposition(
        proposition_id="P-DIAG-quality-dir",
        episode_id=eid,
        claim_kind="QUALITY_VS_DIRECTION",
        relation=rel,
        surfaces=surfaces,
        evidence_refs=(
            "crt.event.direction",
            "model_evidence.values.gaussian",
            "model_evidence.values.rr_model",
        ),
        resolution=dict(POLICY_QUALITY_DIR),
        observation_id=None,
    )


def build_magnitude_substrate(ep: Mapping[str, Any]) -> Proposition:
    eid = str(ep.get("episode_id") or "")
    mag = ep.get("magnitude_states") or {}
    surfaces = {"state": dict(mag) if isinstance(mag, dict) else {}}
    required = ("body_commitment", "atr_magnitude", "momentum_magnitude")
    if not mag:
        rel = "SILENT"
        note = "magnitude_states absent (Phase 2A not attached)"
    elif any(str(mag.get(k, "")).startswith("X_") for k in required):
        rel = "INSUFFICIENT"
        note = "one or more magnitude states are X_ markers"
    elif all(k in mag for k in required):
        rel = "ORTHOGONAL"
        note = "2A magnitude substrate present — not a same-event integration claim"
    else:
        rel = "INSUFFICIENT"
        note = f"incomplete magnitude_states keys={list(mag)}"
    surfaces["adjudication_note"] = note
    return Proposition(
        proposition_id="P-DIAG-magnitude-substrate",
        episode_id=eid,
        claim_kind="MAGNITUDE_SUBSTRATE",
        relation=rel,
        surfaces=surfaces,
        evidence_refs=("magnitude_states",),
        resolution=dict(POLICY_MAG_SUBSTRATE),
        observation_id=None,
    )


def build_propositions(ep: Mapping[str, Any]) -> list[Proposition]:
    """Build the full Phase-2B proposition set for one episode reconstruction dict."""
    if not ep.get("episode_id"):
        raise ValueError("episode requires episode_id")
    props = [
        build_direction_alignment(ep),
        build_chapter_vs_structure_score(ep),
        build_quality_vs_direction(ep),
        build_magnitude_substrate(ep),
    ]
    kinds = {p.claim_kind for p in props}
    missing = [k for k in EXIT_CLAIM_KINDS if k not in kinds]
    if missing:
        raise RuntimeError(f"exit claim kinds missing: {missing}")
    return props


def propositions_to_jsonable(props: Sequence[Proposition]) -> list[dict[str, Any]]:
    return [p.to_dict() for p in props]


def proposition_by_claim(
    props: Sequence[Proposition] | Sequence[Mapping[str, Any]], claim_kind: str
) -> Proposition | dict[str, Any] | None:
    for p in props:
        kind = p.claim_kind if isinstance(p, Proposition) else p.get("claim_kind")
        if kind == claim_kind:
            return p
    return None


def attach_propositions(ep: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow-copied episode dict with ``propositions`` list attached."""
    out = dict(ep)
    out["propositions"] = propositions_to_jsonable(build_propositions(ep))
    return out

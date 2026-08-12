"""
Model Evidence layer — Layer 7 of the semantic pipeline.

"Models testify." Layers 2/4/5/6 describe what the market IS (states -> context -> shape ->
CRT story). This layer records what each MODEL SAYS about the bar, and — critically — what that
model's number is entitled to mean.

INTEGRATE, NOT IMPLEMENT. The declarative half already exists: ``active_models.yaml`` carries a
four-truth block per model (``intent`` / ``runtime`` / ``evidence`` / ``status``). This module is
its runtime reader. The model set, the runtime slot bindings and the output semantics are all
DECLARED there and read here — none of them is hardcoded in Python. A hand-written copy of a
registry list is the recurring enforcement-hole pattern this repository has already hit three
times; the binding is declared once.

WHY THE SEMANTIC TRAVELS WITH THE VALUE
---------------------------------------
``engine_results["rr"]["rr_ratio"]`` is a bare float whose meaning — candle polarity in [0.5,1],
NOT economic reward:risk — survived only in comments and in a defensive check inside
DecisionEngine. A ModelEvidence record carries ``semantic`` alongside ``value``, so a downstream
consumer cannot read polarity as reward:risk without contradicting a declared field. True RR is
SL/TP-derived and owned by UltronRiskGate. That separation is expressed here as data.

CRT STORY vs CRT TESTIMONY (O12)
--------------------------------
CRT *state* (RETEST/EXPANSION/…) is market structure chapter — owned by the CRT runtime /
resolver. CRT *score* (structure_rule_score) is model testimony answering
"Is the market structure valid?". They must remain separate. A low structure_rule_score with
an advanced CRT chapter is NOT auto-converted to "CRT says invalid" unless a producer contract
explicitly says so. Default relationship: NOT_APPLICABLE (different questions).

Quality scores (gaussian / zone_gate / rr) never invent market direction. ``direction`` stays
UNKNOWN unless a producer legitimately emits a direction field under a declared contract.
``relationship_to_story`` stays UNKNOWN for quality scores (no declared mapping to CRT/context/
shape direction). This is intentional fail-closed honesty, not incompleteness to paper over.

NO AGREEMENT FOLD HERE
----------------------
Testimony records individual voices. Agreement is a separate future/research object
(``research.episode_agreement``). This layer never emits agreement=models_agree.

CONTRACT (no defaults, no fallbacks — same discipline as Layers 2/4/5)
---------------------------------------------------------------------
- Every declared model MUST carry ``runtime.engine_key`` (may be null), ``runtime.output_field``
  and ``runtime.output_semantic``. A model that omits them is a LOAD error, never a silent skip.
- A key in ``engine_results`` with no declaring model RAISES — an undeclared producer is a
  registry gap, not a pass-through.
- A model whose ``engine_key`` is non-null but absent from ``engine_results`` RAISES, listing all
  absentees.
- A declared ``output_field`` missing from its result dict RAISES — the producer changed shape.
- Models with ``engine_key: null`` are recorded in ``absent``, NAMED not dropped: the inert
  models (F-004 BitNet, F-005 TradeNet, envelope) stay visible instead of vanishing.
- When a producer SELF-DECLARES its meaning (rr_engine emits ``semantic``), the registry's
  ``output_semantic`` must equal it, or the build RAISES. Producer and registry disagreeing about
  what a number means is the defect class this layer exists to make impossible.
- ``reason`` is the ONLY non-declared field read, and it is diagnostic-only: it never enters the
  signature or the hash. Its absence is RECORDED as None ("this producer emitted no reason"),
  which is a fact about the result — not a default value standing in for a missing one.
- A non-numeric or non-finite value becomes an ``X_`` marker rather than a substituted number:
  drift is made visible, never smoothed away.

NO ARITHMETIC. This layer never combines, weights, averages or scores. Combination is Layer 8
(``core/fusion_engine.py``, which already exists). A second fusion here would repeat the
parallel-implementations mistake this consolidation phase is meant to end.

Shadow-only: imports nothing from ``core``/``engines``; nothing on the decision spine imports it.
The caller passes the ``engine_results`` dict in.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTIVE_MODELS_PATH = _REPO_ROOT / "active_models.yaml"

X_PREFIX = "X_"          # same drift vocabulary as features/feature_states.py
_VALUE_PRECISION = 6     # deliberate quantization: keeps evidence_hash stable across float noise

# Closed vocabularies for L7 testimony contract.
AVAILABILITY_PRESENT = "PRESENT"
AVAILABILITY_ABSENT = "ABSENT"

DIRECTION_UNKNOWN = "UNKNOWN"

APPLICABILITY_APPLICABLE = "APPLICABLE"
APPLICABILITY_NOT_APPLICABLE = "NOT_APPLICABLE"
APPLICABILITY_UNKNOWN = "UNKNOWN"

REL_SUPPORTS = "SUPPORTS"
REL_CONTRADICTS = "CONTRADICTS"
REL_NEUTRAL = "NEUTRAL"
REL_NOT_APPLICABLE = "NOT_APPLICABLE"
REL_UNKNOWN = "UNKNOWN"

RELATIONSHIP_VOCAB = frozenset(
    {REL_SUPPORTS, REL_CONTRADICTS, REL_NEUTRAL, REL_NOT_APPLICABLE, REL_UNKNOWN}
)

# Producers whose output answers a quality/validity *question*, not market chapter/direction.
# Relationship to CRT story chapter is NOT_APPLICABLE (POL-O12 class for CRT; quality class for others).
_QUALITY_TESTIMONY_SEMANTICS = frozenset(
    {
        "structure_rule_score",
        "ema_momentum_kernel_score",
        "neighbourhood_quality_score",
        "candle_structure_quality",
        "state_acceptability_score",
        "capital_quality_score",
        "post_entry_envelope_bounds",
    }
)

# CRT scorer model_id in active_models.yaml
_CRT_MODEL_ID = "crt"


@dataclass(frozen=True)
class ModelDeclaration:
    """One model's declared identity, read from active_models.yaml. Immutable."""
    model_id: str                  # top-level yaml key
    question: str                  # intent.question — what it was DESIGNED to answer
    engine_key: str | None         # slot in EngineRunner.engine_results; None = no result slot
    output_field: str | None       # key WITHIN that result dict carrying the primary value
    output_semantic: str           # what the value MEANS
    status: str                    # operational rollup: active / dormant / orphaned / ...
    runtime_active: bool           # runtime.active — what executes today

    @property
    def produces(self) -> bool:
        """True when this model occupies a slot in engine_results."""
        return self.engine_key is not None


@dataclass(frozen=True)
class StorySnapshot:
    """Optional market-story surfaces for relationship classification (never invented here).

    All fields optional. Missing fields keep relationship_to_story fail-closed (UNKNOWN /
    NOT_APPLICABLE) rather than guessing.
    """
    crt_state: str | None = None
    crt_direction: str | None = None       # LONG/SHORT from CRT runtime — NOT from scores
    context_direction: str | None = None   # e.g. Bullish/Bearish from trend_bias
    shape_direction: str | None = None     # e.g. shape name carrying bull/bear
    shape_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "crt_state": self.crt_state,
            "crt_direction": self.crt_direction,
            "context_direction": self.context_direction,
            "shape_direction": self.shape_direction,
            "shape_name": self.shape_name,
        }


@dataclass(frozen=True)
class ModelEvidence:
    """What one model said about one bar (testimony — not market truth)."""
    model_id: str
    engine_key: str
    question: str
    value: float | None            # raw declared output, unmodified (None only when non-finite)
    rendered: str                  # value as it enters the signature, or an X_ marker
    semantic: str
    status: str
    reason: str | None             # the engine's own reason string, carried verbatim
    # --- L7 structured testimony fields ---
    producer: str = ""             # same as model_id (registry owner key)
    score_semantics: str = ""      # alias of semantic for contract wording
    availability: str = AVAILABILITY_PRESENT
    direction: str = DIRECTION_UNKNOWN
    applicability: str = APPLICABILITY_APPLICABLE
    relationship_to_story: str = REL_UNKNOWN
    story_refs: dict[str, Any] = field(default_factory=dict)
    provenance: str = "active_models.yaml"

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "producer": self.producer or self.model_id,
            "engine_key": self.engine_key,
            "question": self.question,
            "result": self.value,
            "value": self.value,
            "score": self.value,
            "rendered": self.rendered,
            "semantic": self.semantic,
            "score_semantics": self.score_semantics or self.semantic,
            "status": self.status,
            "reason": self.reason,
            "availability": self.availability,
            "direction": self.direction,
            "applicability": self.applicability,
            "relationship_to_story": self.relationship_to_story,
            "story_refs": dict(self.story_refs),
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class EvidenceSet:
    """Every model's testimony for one bar."""
    evidence: dict[str, ModelEvidence]   # model_id -> record, declaration order
    signature: str                       # deterministic one-line rendering
    evidence_hash: str                   # sha256[:16] — joins to context_hash / shape_id
    absent: tuple[str, ...]              # declared-but-non-producing models, named not dropped
    x_markers: tuple[str, ...]           # "model_id=X_..." — non-finite testimony
    # --- L7 closure ---
    absent_records: dict[str, dict[str, Any]] = field(default_factory=dict)
    story_snapshot: dict[str, Any] | None = None
    provenance: tuple[str, ...] = ()
    # Explicit CRT separation surface (story from snapshot; testimony from evidence["crt"])
    crt_story: dict[str, Any] | None = None
    crt_testimony: dict[str, Any] | None = None

    def describe(self) -> str:
        """Human rendering — the literal 'what does each model say?' answer."""
        lines = [
            f"{ev.model_id}: {ev.rendered} ({ev.semantic}) <- {ev.question} "
            f"[avail={ev.availability} dir={ev.direction} rel={ev.relationship_to_story}]"
            for ev in self.evidence.values()
        ]
        for model_id in self.absent:
            lines.append(f"{model_id}: ABSENT (declared, produces no engine result)")
        if self.crt_story is not None:
            lines.append(f"CRT_STORY: {self.crt_story}")
        if self.crt_testimony is not None:
            lines.append(
                f"CRT_TESTIMONY: score={self.crt_testimony.get('value')} "
                f"semantic={self.crt_testimony.get('semantic')} "
                f"(separate from CRT chapter)"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence": {mid: ev.to_dict() for mid, ev in self.evidence.items()},
            "signature": self.signature,
            "evidence_hash": self.evidence_hash,
            "absent": list(self.absent),
            "absent_records": dict(self.absent_records),
            "x_markers": list(self.x_markers),
            "story_snapshot": self.story_snapshot,
            "provenance": list(self.provenance),
            "crt_story": self.crt_story,
            "crt_testimony": self.crt_testimony,
        }


def load_active_models(path: Path | None = None) -> dict:
    """Read active_models.yaml. Separate from the class so tests can inject a document."""
    src = path if path is not None else _ACTIVE_MODELS_PATH
    with open(src, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    if not isinstance(doc, dict):
        raise ValueError(f"{src} did not parse to a mapping")
    return doc


def _is_model_section(section: Any) -> bool:
    """A MODEL is a section that declares a question it answers, plus runtime + status.

    This discriminator is structural, not a hardcoded name list: `strategies`, `engine_runner`,
    `philosophy` and `feature_lineage` carry an `intent` block but no `intent.question` — they
    are orchestration/doctrine, not evidence producers.
    """
    if not isinstance(section, dict):
        return False
    intent = section.get("intent")
    return (
        isinstance(intent, dict)
        and bool(intent.get("question"))
        and isinstance(section.get("runtime"), dict)
        and section.get("status") is not None
    )


def _extract_declared_direction(result: Mapping[str, Any]) -> str:
    """Return producer-declared direction only when explicitly present and legitimate.

    Quality scores never imply direction. Only an explicit direction-like field with a
    directional token is accepted; otherwise UNKNOWN.
    """
    for key in ("direction", "dir", "trade_direction"):
        if key not in result:
            continue
        raw = result[key]
        if raw is None:
            continue
        s = str(raw).strip().upper()
        if s in ("LONG", "SHORT", "BUY", "SELL", "BULL", "BEAR", "1", "-1"):
            if s in ("BUY", "BULL", "1"):
                return "LONG"
            if s in ("SELL", "BEAR", "-1"):
                return "SHORT"
            return s
        # Present but non-directional — still not inventable as market direction.
        return DIRECTION_UNKNOWN
    return DIRECTION_UNKNOWN


def _dir_sign(token: Any) -> int:
    if token is None:
        return 0
    s = str(token).upper()
    if any(t in s for t in ("LONG", "BUY", "BULL")) or s == "1":
        return 1
    if any(t in s for t in ("SHORT", "SELL", "BEAR")) or s == "-1":
        return -1
    # Shape/trend names with bull/bear
    sl = str(token).lower()
    if "bull" in sl:
        return 1
    if "bear" in sl:
        return -1
    return 0


def _classify_relationship(
    decl: ModelDeclaration,
    *,
    producer_direction: str,
    story: StorySnapshot | None,
) -> tuple[str, str]:
    """Return (relationship_to_story, applicability).

    Fail-closed rules:
    - CRT structure_rule_score vs CRT chapter → NOT_APPLICABLE (different questions; POL-O12)
    - Quality semantics without declared direction mapping → UNKNOWN
    - Only when producer_direction is known AND story direction is known may SUPPORTS/CONTRADICTS
      fire — never from score magnitude.
    """
    semantic = decl.output_semantic

    # CRT score is testimony about structure validity, not the chapter label.
    if decl.model_id == _CRT_MODEL_ID or semantic == "structure_rule_score":
        if story is not None and story.crt_state:
            return REL_NOT_APPLICABLE, APPLICABILITY_NOT_APPLICABLE
        return REL_UNKNOWN, APPLICABILITY_APPLICABLE

    # Quality testimony: no declared mapping from score → story direction.
    if semantic in _QUALITY_TESTIMONY_SEMANTICS:
        if producer_direction == DIRECTION_UNKNOWN:
            return REL_UNKNOWN, APPLICABILITY_APPLICABLE
        # Rare path: producer emitted a real direction — compare to story if available.
        if story is None:
            return REL_UNKNOWN, APPLICABILITY_APPLICABLE
        story_dirs = [
            _dir_sign(story.crt_direction),
            _dir_sign(story.context_direction),
            _dir_sign(story.shape_direction or story.shape_name),
        ]
        story_dirs = [d for d in story_dirs if d != 0]
        pd = _dir_sign(producer_direction)
        if pd == 0 or not story_dirs:
            return REL_UNKNOWN, APPLICABILITY_APPLICABLE
        if all(d == pd for d in story_dirs):
            return REL_SUPPORTS, APPLICABILITY_APPLICABLE
        if any(d == -pd for d in story_dirs):
            return REL_CONTRADICTS, APPLICABILITY_APPLICABLE
        return REL_NEUTRAL, APPLICABILITY_APPLICABLE

    # Unknown semantic class — do not invent.
    return REL_UNKNOWN, APPLICABILITY_UNKNOWN


class ModelEvidenceBuilder:
    """Reads the declared model registry; turns raw engine_results into an EvidenceSet."""

    def __init__(self, document: dict | None = None):
        doc = document if document is not None else load_active_models()

        declarations: list[ModelDeclaration] = []
        for model_id, section in doc.items():
            if not _is_model_section(section):
                continue
            runtime = section["runtime"]
            for field_name in ("engine_key", "output_field", "output_semantic", "active"):
                if field_name not in runtime:
                    raise ValueError(
                        f"model {model_id!r} does not declare runtime.{field_name} — every model must "
                        "state its Layer-7 evidence binding (use null when it produces no "
                        "engine result). No defaults: an undeclared binding is a registry gap."
                    )
            engine_key = runtime["engine_key"]
            output_field = runtime["output_field"]
            semantic = runtime["output_semantic"]

            if engine_key is not None and not isinstance(engine_key, str):
                raise ValueError(
                    f"model {model_id!r} declares a non-string runtime.engine_key "
                    f"{engine_key!r} — expected a slot name or null"
                )
            if engine_key is not None and not output_field:
                raise ValueError(
                    f"model {model_id!r} declares engine_key {engine_key!r} but no "
                    "runtime.output_field — a producer must name the field carrying its value"
                )
            if not semantic or not isinstance(semantic, str):
                raise ValueError(
                    f"model {model_id!r} declares no runtime.output_semantic — a value without "
                    "a declared meaning is exactly what this layer exists to prevent"
                )

            declarations.append(ModelDeclaration(
                model_id=model_id,
                question=str(section["intent"]["question"]),
                engine_key=engine_key,
                output_field=output_field,
                output_semantic=semantic,
                status=str(section["status"]),
                runtime_active=bool(runtime["active"]),   # strict — declared by every model
            ))

        if not declarations:
            raise ValueError("active_models.yaml declares no models — refusing to build")

        seen: dict[str, str] = {}
        for decl in declarations:
            if decl.engine_key is None:
                continue
            if decl.engine_key in seen:
                raise ValueError(
                    f"engine_key {decl.engine_key!r} is claimed by both {seen[decl.engine_key]!r} "
                    f"and {decl.model_id!r} — one slot, one owner"
                )
            seen[decl.engine_key] = decl.model_id

        self._declarations: tuple[ModelDeclaration, ...] = tuple(declarations)
        self._by_id = {d.model_id: d for d in declarations}
        self._by_engine_key = {d.engine_key: d for d in declarations if d.produces}

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def models(self) -> tuple[str, ...]:
        """Every declared model, in declaration order."""
        return tuple(d.model_id for d in self._declarations)

    @property
    def producers(self) -> tuple[str, ...]:
        """Models that occupy a slot in engine_results, in declaration order."""
        return tuple(d.model_id for d in self._declarations if d.produces)

    @property
    def engine_keys(self) -> tuple[str, ...]:
        """The declared runtime slots, in declaration order."""
        return tuple(d.engine_key for d in self._declarations if d.produces)  # type: ignore[misc]

    def spec(self, model_id: str) -> ModelDeclaration:
        """One model's declaration. Raises KeyError on an undeclared id."""
        return self._by_id[model_id]

    def semantic_of(self, engine_key: str) -> str:
        """The declared meaning of a runtime slot's value. Raises KeyError if unbound."""
        return self._by_engine_key[engine_key].output_semantic

    # ── aggregation ──────────────────────────────────────────────────────────

    def build(
        self,
        engine_results: Mapping[str, Mapping[str, Any]],
        *,
        story: StorySnapshot | Mapping[str, Any] | None = None,
    ) -> EvidenceSet:
        """Raw EngineRunner engine_results -> EvidenceSet. Reads only; computes nothing.

        Optional *story* supplies CRT/context/shape surfaces for relationship_to_story
        classification. It never alters scores, semantics, or availability.
        """
        story_snap: StorySnapshot | None
        if story is None:
            story_snap = None
        elif isinstance(story, StorySnapshot):
            story_snap = story
        elif isinstance(story, Mapping):
            story_snap = StorySnapshot(
                crt_state=story.get("crt_state"),
                crt_direction=story.get("crt_direction"),
                context_direction=story.get("context_direction"),
                shape_direction=story.get("shape_direction"),
                shape_name=story.get("shape_name"),
            )
        else:
            raise TypeError(f"story must be StorySnapshot|mapping|None, got {type(story)}")

        undeclared = sorted(set(engine_results) - set(self._by_engine_key))
        if undeclared:
            raise KeyError(
                f"build(): engine_results carries slots with no declaring model: {undeclared} "
                "— declare them in active_models.yaml (runtime.engine_key). An undeclared "
                "producer is a registry gap, never a silent pass-through."
            )
        missing = sorted(
            d.engine_key for d in self._declarations
            if d.produces and d.engine_key not in engine_results
        )
        if missing:
            raise KeyError(
                f"build(): declared producers absent from engine_results: {missing} "
                "(no defaults — a missing model is not a neutral model)"
            )

        evidence: dict[str, ModelEvidence] = {}
        x_markers: list[str] = []
        for decl in self._declarations:
            if not decl.produces:
                continue
            result = engine_results[decl.engine_key]           # type: ignore[index]
            if not isinstance(result, Mapping):
                raise TypeError(
                    f"build(): engine_results[{decl.engine_key!r}] is {type(result).__name__}, "
                    "expected a mapping"
                )
            if decl.output_field not in result:
                raise KeyError(
                    f"build(): {decl.model_id!r} declares output_field "
                    f"{decl.output_field!r} but engine_results[{decl.engine_key!r}] does not "
                    f"carry it (has: {sorted(result)}) — the producer changed shape"
                )
            # Producer-vs-registry semantic cross-check. Some engines self-declare what their
            # number means (rr_engine emits `semantic`). When they do, the declaration here MUST
            # agree — a silent divergence between producer and registry is precisely the class
            # of defect this layer exists to make impossible.
            emitted_semantic = result.get("semantic")
            if emitted_semantic is not None and str(emitted_semantic) != decl.output_semantic:
                raise ValueError(
                    f"build(): {decl.model_id!r} declares output_semantic "
                    f"{decl.output_semantic!r} but engine_results[{decl.engine_key!r}] "
                    f"self-declares {str(emitted_semantic)!r} — producer and registry disagree "
                    "about what the value MEANS. Reconcile active_models.yaml with the engine."
                )

            raw = result[decl.output_field]
            # bool is a subclass of int, so float(True)==1.0 would silently turn a flag into a
            # score. A boolean is a gate outcome, not a measurement — refuse to coerce it.
            if isinstance(raw, bool):
                raise TypeError(
                    f"build(): {decl.model_id!r} declares output_field {decl.output_field!r} "
                    f"but engine_results[{decl.engine_key!r}][{decl.output_field!r}] is a bool "
                    "— a flag is not a score; point output_field at the measured value"
                )
            try:
                value = float(raw)
            except (TypeError, ValueError):
                value, rendered = None, f"{X_PREFIX}NON_NUMERIC({raw!r})"
            else:
                if math.isfinite(value):
                    rendered = f"{value:.{_VALUE_PRECISION}f}"
                else:
                    value, rendered = None, f"{X_PREFIX}NON_FINITE({raw!r})"
            if rendered.startswith(X_PREFIX):
                x_markers.append(f"{decl.model_id}={rendered}")

            reason = result.get("reason")
            producer_direction = _extract_declared_direction(result)
            rel, applicability = _classify_relationship(
                decl, producer_direction=producer_direction, story=story_snap
            )
            if rel not in RELATIONSHIP_VOCAB:
                raise ValueError(f"internal: illegal relationship {rel!r}")

            story_refs: dict[str, Any] = {}
            if story_snap is not None:
                story_refs = {
                    "crt_state": story_snap.crt_state,
                    "crt_direction": story_snap.crt_direction,
                    "context_direction": story_snap.context_direction,
                    "shape_direction": story_snap.shape_direction or story_snap.shape_name,
                }

            evidence[decl.model_id] = ModelEvidence(
                model_id=decl.model_id,
                engine_key=decl.engine_key,                    # type: ignore[arg-type]
                question=decl.question,
                value=value,
                rendered=rendered,
                semantic=decl.output_semantic,
                status=decl.status,
                reason=None if reason is None else str(reason),
                producer=decl.model_id,
                score_semantics=decl.output_semantic,
                availability=AVAILABILITY_PRESENT,
                direction=producer_direction,
                applicability=applicability,
                relationship_to_story=rel,
                story_refs=story_refs,
                provenance=(
                    f"active_models.yaml#{decl.model_id} "
                    f"(engine_key={decl.engine_key}, output_field={decl.output_field}, "
                    f"output_semantic={decl.output_semantic})"
                ),
            )

        # Absent models: structured records (not dropped).
        absent_ids = tuple(d.model_id for d in self._declarations if not d.produces)
        absent_records: dict[str, dict[str, Any]] = {}
        for decl in self._declarations:
            if decl.produces:
                continue
            absent_records[decl.model_id] = {
                "model_id": decl.model_id,
                "producer": decl.model_id,
                "question": decl.question,
                "availability": AVAILABILITY_ABSENT,
                "value": None,
                "score": None,
                "score_semantics": decl.output_semantic,
                "semantic": decl.output_semantic,
                "direction": DIRECTION_UNKNOWN,
                "applicability": APPLICABILITY_NOT_APPLICABLE,
                "relationship_to_story": REL_NOT_APPLICABLE,
                "status": decl.status,
                "runtime_active": decl.runtime_active,
                "provenance": (
                    f"active_models.yaml#{decl.model_id} "
                    f"(engine_key=null; declared non-producing)"
                ),
            }

        signature = "|".join(
            f"{ev.model_id}={ev.semantic}:{ev.rendered}" for ev in evidence.values()
        )

        crt_story = None
        crt_testimony = None
        if story_snap is not None and (
            story_snap.crt_state is not None or story_snap.crt_direction is not None
        ):
            crt_story = {
                "state": story_snap.crt_state,
                "direction": story_snap.crt_direction,
                "surface": "CRT_STORY",
                "note": "Market structure chapter from CRT runtime — not a model score.",
            }
        if _CRT_MODEL_ID in evidence:
            crt_ev = evidence[_CRT_MODEL_ID]
            crt_testimony = {
                "producer": crt_ev.producer,
                "question": crt_ev.question,
                "value": crt_ev.value,
                "semantic": crt_ev.semantic,
                "score_semantics": crt_ev.score_semantics,
                "relationship_to_story": crt_ev.relationship_to_story,
                "surface": "CRT_TESTIMONY",
                "note": (
                    "structure_rule_score answers the producer question; "
                    "it does not redefine CRT chapter membership (POL-O12)."
                ),
            }

        return EvidenceSet(
            evidence=evidence,
            signature=signature,
            evidence_hash=hashlib.sha256(signature.encode()).hexdigest()[:16],
            absent=absent_ids,
            x_markers=tuple(x_markers),
            absent_records=absent_records,
            story_snapshot=story_snap.to_dict() if story_snap else None,
            provenance=(
                "active_models.yaml",
                "features.model_evidence.ModelEvidenceBuilder",
                "no_spine_import",
            ),
            crt_story=crt_story,
            crt_testimony=crt_testimony,
        )

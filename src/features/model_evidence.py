"""
Model Evidence layer — Layer 7 of the semantic pipeline.

"Models testify." Layers 2/4/5/6 describe what the market IS (states -> context -> shape ->
statistics). This layer records what each MODEL SAYS about the bar, and — critically — what that
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ACTIVE_MODELS_PATH = _REPO_ROOT / "active_models.yaml"

X_PREFIX = "X_"          # same drift vocabulary as features/feature_states.py
_VALUE_PRECISION = 6     # deliberate quantization: keeps evidence_hash stable across float noise


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
class ModelEvidence:
    """What one model said about one bar."""
    model_id: str
    engine_key: str
    question: str
    value: float | None            # raw declared output, unmodified (None only when non-finite)
    rendered: str                  # value as it enters the signature, or an X_ marker
    semantic: str
    status: str
    reason: str | None             # the engine's own reason string, carried verbatim


@dataclass(frozen=True)
class EvidenceSet:
    """Every model's testimony for one bar."""
    evidence: dict[str, ModelEvidence]   # model_id -> record, declaration order
    signature: str                       # deterministic one-line rendering
    evidence_hash: str                   # sha256[:16] — joins to context_hash / shape_id
    absent: tuple[str, ...]              # declared-but-non-producing models, named not dropped
    x_markers: tuple[str, ...]           # "model_id=X_..." — non-finite testimony

    def describe(self) -> str:
        """Human rendering — the literal 'what does each model say?' answer."""
        lines = [
            f"{ev.model_id}: {ev.rendered} ({ev.semantic}) <- {ev.question}"
            for ev in self.evidence.values()
        ]
        for model_id in self.absent:
            lines.append(f"{model_id}: ABSENT (declared, produces no engine result)")
        return "\n".join(lines)


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


class ModelEvidenceBuilder:
    """Reads the declared model registry; turns raw engine_results into an EvidenceSet."""

    def __init__(self, document: dict | None = None):
        doc = document if document is not None else load_active_models()

        declarations: list[ModelDeclaration] = []
        for model_id, section in doc.items():
            if not _is_model_section(section):
                continue
            runtime = section["runtime"]
            for field in ("engine_key", "output_field", "output_semantic", "active"):
                if field not in runtime:
                    raise ValueError(
                        f"model {model_id!r} does not declare runtime.{field} — every model must "
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

    def build(self, engine_results: Mapping[str, Mapping[str, Any]]) -> EvidenceSet:
        """Raw EngineRunner engine_results -> EvidenceSet. Reads only; computes nothing."""
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
            evidence[decl.model_id] = ModelEvidence(
                model_id=decl.model_id,
                engine_key=decl.engine_key,                    # type: ignore[arg-type]
                question=decl.question,
                value=value,
                rendered=rendered,
                semantic=decl.output_semantic,
                status=decl.status,
                reason=None if reason is None else str(reason),
            )

        signature = "|".join(
            f"{ev.model_id}={ev.semantic}:{ev.rendered}" for ev in evidence.values()
        )
        return EvidenceSet(
            evidence=evidence,
            signature=signature,
            evidence_hash=hashlib.sha256(signature.encode()).hexdigest()[:16],
            absent=tuple(d.model_id for d in self._declarations if not d.produces),
            x_markers=tuple(x_markers),
        )

"""
CRT Resolver Variant Comparison Surface (N parallel streams)
=============================================================
Wiring-phase instrument. Emits N labelled parallel resolver output streams
against ONE fixed engine timeline, and attributes disagreement PER CRT STATE
and PER CAUSE -- never a bare agreement scalar.

WHY THIS EXISTS
----------------
The wiring phase links built-but-unconsumed resolver capability. Every link
lands into this surface, so it exists before the first link. N agreement
percentages would be barely better than one; what distinguishes a real change
from an inert one is *which bars* moved and *why*.

TWO COMPARISONS, TWO DIFFERENT CLAIMS -- never reported in one column:

  1. variant vs ENGINE  -> cause attribution. The CRT engine remains execution
     authority and is the reference. "No canonical variant" means no variant is
     authoritative AMONG THE VARIANTS; it does not mean there is no reference.
     Causes come from crt_parity_classifier.CATEGORY_PRECEDENCE (the repository's
     existing, tested divergence taxonomy -- NOT RejectReason, which answers a
     different question; see DIVERGENCE_CODE_REJECT_REASON there).

  2. variant vs variant -> STREAM IDENTITY ONLY. Answers "bit-identical or not",
     nothing more, and carries no cause attribution. This is the inert-link
     criterion: a link whose stream is bit-identical to its base is dead code.

AUTHORITY
---------
Research/shadow only (CLAUDE.md 6.5). Committed output is zero during this
phase; no variant is canonical; nothing here grants promotion or production
authority.
"""
from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

_REPO = Path(__file__).resolve().parents[2]


def _load_sibling(name: str):
    """Load a sibling research module by path (they are scripts, not a package)."""
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, _REPO / "scripts" / "research" / f"{name}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod          # register BEFORE exec: dataclasses need it
    spec.loader.exec_module(mod)
    return mod


# -- Declared inputs ----------------------------------------------------------
@dataclass(frozen=True)
class VariantInput:
    """One labelled stream to produce.

    ``rationale`` states what the comparison TESTS. A variant whose rationale
    cannot say what will be learned is a duplicate, not a variant -- delete it
    rather than emitting it in parallel (emitting both launders an accident into
    an apparent intention). Step 2's registry supplies these; this surface only
    consumes them, so it is usable before the registry exists.
    """

    variant_id: str
    rationale: str
    config_path: Optional[Path] = None
    links: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.variant_id.strip():
            raise ValueError("variant_id must be non-empty")
        if not self.rationale.strip():
            raise ValueError(
                "variant {0!r}: rationale must state what the comparison tests "
                "(duplicate-vs-variant rule)".format(self.variant_id)
            )


@dataclass(frozen=True)
class VariantStream:
    """One variant's aligned per-bar output plus its engine-anchored totals."""

    variant_id: str
    bar_indices: tuple[int, ...]
    states: tuple[str, ...]
    engine_states: tuple[str, ...]
    agreement: int
    total: int
    meta: Mapping[str, Any] = field(default_factory=dict)

    def identity_key(self) -> tuple:
        """Everything that must match for two streams to be bit-identical."""
        return (self.bar_indices, self.states)


# -- Pure transforms ----------------------------------------------------------
def align(
    engine_states: Sequence[str],
    resolver_states: Sequence[str],
    source_indices: Sequence[int],
) -> tuple[list[int], list[str], list[str]]:
    """Align resolver bars onto the engine timeline.

    Mirrors crt_state_confusion_matrix.build_confusion's alignment exactly.
    ``run_variant`` asserts the agreement integer derived here equals the one
    build_confusion reports, so the two cannot silently drift apart.
    """
    idx: list[int] = []
    eng: list[str] = []
    res: list[str] = []
    for res_i, src_i in enumerate(source_indices):
        if 0 <= src_i < len(engine_states):
            idx.append(src_i)
            eng.append(engine_states[src_i])
            res.append(resolver_states[res_i])
    return idx, eng, res


def build_mismatch_context(stream: VariantStream, **overrides):
    """Build the classifier context for ONE stream.

    ``state_marginals`` is per-stream by construction: it is (engine_n,
    resolver_n, true_positive_n) for this variant's own output. Passing an empty
    context instead makes the classifier's power gate fire on every cell, so
    everything returns INSUFFICIENT and the surface reports no causes at all --
    a silently vacuous result that looks like a clean run.

    The two structural constant sets are REUSED from crt_parity_report (the
    definition of record for the F-069 program) rather than restated here; a
    second copy would be a duplicate that could drift.
    """
    cpc = _load_sibling("crt_parity_classifier")
    rep = _load_sibling("crt_parity_report")

    eng_n = Counter(stream.engine_states)
    res_n = Counter(stream.states)
    tp_n = Counter(e for e, r in zip(stream.engine_states, stream.states) if e == r)
    marginals = {
        s: (eng_n.get(s, 0), res_n.get(s, 0), tp_n.get(s, 0))
        for s in sorted(set(eng_n) | set(res_n))
    }

    kwargs = {
        "state_marginals": marginals,
        "engine_only_threshold_names": rep.ENGINE_ONLY_THRESHOLD_NAMES,
        "known_geometry_divergent_pairs": rep.KNOWN_GEOMETRY_DIVERGENT_PAIRS,
    }
    kwargs.update(overrides)
    return cpc.MismatchContext(**kwargs)


def attribute_causes(stream: VariantStream, ctx) -> dict[tuple[str, str], Any]:
    """Classify each distinct (engine_state, resolver_state) MISMATCH cell once.

    Engine-anchored by construction. Returns cell -> Classification. A bar's
    cause is its cell's cause, so a 47k-bar frame costs one classification per
    distinct cell rather than one per bar.
    """
    cpc = _load_sibling("crt_parity_classifier")
    cells = {(e, r) for e, r in zip(stream.engine_states, stream.states) if e != r}
    return {(e, r): cpc.classify_mismatch(e, r, {}, ctx) for e, r in sorted(cells)}


def per_state_per_cause(
    stream: VariantStream, causes: Mapping[tuple[str, str], Any]
) -> dict[str, Counter]:
    """engine_state -> Counter(cause_code -> n_bars).

    The per-state, per-cause attribution that replaces a headline scalar.
    """
    out: dict[str, Counter] = {}
    for e, r in zip(stream.engine_states, stream.states):
        if e == r:
            continue
        c = causes.get((e, r))
        out.setdefault(e, Counter())[c.code if c else "D-UNKNOWN"] += 1
    return out


def pairwise_stream_identity(
    streams: Sequence[VariantStream],
) -> dict[tuple[str, str], dict[str, Any]]:
    """Variant-vs-variant STREAM IDENTITY ONLY -- no cause attribution.

    ``identical`` is the inert-link criterion (bit-identical => the link changed
    nothing => dead code => revert). ``n_differing_bars`` is reported alongside
    so "same agreement rate, different bars" (two genuinely different models) is
    distinguishable from "same agreement rate, same bars" (one is inert).
    """
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for i, a in enumerate(streams):
        for b in streams[i + 1:]:
            if a.bar_indices != b.bar_indices:
                out[(a.variant_id, b.variant_id)] = {
                    "identical": False,
                    "comparable": False,
                    "reason": "different aligned bar sets -- not comparable bar-for-bar",
                }
                continue
            diff = sum(1 for x, y in zip(a.states, b.states) if x != y)
            out[(a.variant_id, b.variant_id)] = {
                "identical": diff == 0,
                "comparable": True,
                "n_differing_bars": diff,
                "same_agreement_rate": a.agreement == b.agreement,
            }
    return out


# -- Driver -------------------------------------------------------------------
def run_variant(
    engine_ctx,
    variant: VariantInput,
    *,
    engine_mode: str = "exit",
    injection: str = "none",
    htf_mode: str = "engine",
    instrument: str = "XAUUSD",
    enriched: Optional[Any] = None,
    fp_cfg: Optional[dict] = None,
) -> VariantStream:
    """Produce one labelled stream against the FIXED engine context.

    ``injection="none"`` is the only mode that answers "can the resolver
    reproduce the engine from configuration alone"; the others are
    oracle-assisted diagnostics. Defaulted here so a surface run cannot silently
    be oracle-fed.
    """
    cm = _load_sibling("crt_state_confusion_matrix")

    # ONE pipeline run per variant. `run_once` would recompute the resolver
    # timeline internally, so calling it as well would double the cost of the
    # most expensive step (a full FeaturePipeline pass over the corpus).
    reset_map, state_to_map = cm._injection_maps_for_mode(
        injection, engine_ctx.engine_reset_by_idx, engine_ctx.engine_state_to_by_idx
    )
    res_states, source_indices, meta = cm.build_resolver_timeline(
        engine_ctx.ohlcv_path,
        variant.config_path,
        htf_mode=htf_mode,
        instrument=instrument,
        engine_reset_by_idx=reset_map,
        engine_state_to_by_idx=state_to_map,
        enriched=enriched,
        fp_cfg=fp_cfg,
    )
    meta = dict(meta, injection=injection)
    engine_states = (
        engine_ctx.timeline.enter_states if engine_mode == "enter"
        else engine_ctx.timeline.exit_states
    )
    report = cm.build_confusion(
        engine_states,
        res_states,
        source_indices,
        engine_mode=engine_mode,
        reference=engine_ctx.reference,
        engine_events=engine_ctx.events,
        max_episodes=10 ** 9,   # a TRUE total, never capped by the CLI default
    )
    idx, eng, res = align(engine_states, res_states, source_indices)
    agreement = sum(1 for e, r in zip(eng, res) if e == r)

    # Self-check: our alignment must reproduce build_confusion's integers exactly.
    if (agreement, len(eng)) != (report.agreement, report.total):
        raise AssertionError(
            "variant {0!r}: surface alignment ({1}/{2}) disagrees with "
            "build_confusion ({3}/{4}) -- the two alignment paths have drifted".format(
                variant.variant_id, agreement, len(eng), report.agreement, report.total
            )
        )

    return VariantStream(
        variant_id=variant.variant_id,
        bar_indices=tuple(idx),
        states=tuple(res),
        engine_states=tuple(eng),
        agreement=agreement,
        total=len(eng),
        meta=dict(meta, links=sorted(variant.links), rationale=variant.rationale),
    )


def build_surface(
    engine_ctx,
    variants: Sequence[VariantInput],
    *,
    ctx=None,
    **run_kwargs,
) -> dict[str, Any]:
    """Run every variant against one engine context and assemble the surface.

    ``ctx=None`` (the default) builds a PER-STREAM context, because the
    classifier's power gate reads that stream's own marginals. An explicit ctx
    is applied to every stream unchanged -- use it only when you deliberately
    want one fixed frame of reference.
    """
    seen: set[str] = set()
    for v in variants:
        if v.variant_id in seen:
            raise ValueError("duplicate variant_id {0!r}".format(v.variant_id))
        seen.add(v.variant_id)

    streams = [run_variant(engine_ctx, v, **run_kwargs) for v in variants]

    per_variant: dict[str, Any] = {}
    for s in streams:
        stream_ctx = ctx if ctx is not None else build_mismatch_context(s)
        causes = attribute_causes(s, stream_ctx)
        per_variant[s.variant_id] = {
            "agreement": s.agreement,
            "total": s.total,
            "per_state_per_cause": {
                k: dict(v) for k, v in per_state_per_cause(s, causes).items()
            },
            "cell_causes": {
                "{0}->{1}".format(e, r): c.code for (e, r), c in causes.items()
            },
            "meta": dict(s.meta),
        }

    return {
        "anchor": "CRT_ENGINE",         # cause attribution is always vs the engine
        "canonical_variant": None,      # zero by design during the wiring phase
        "variants": per_variant,
        "pairwise_stream_identity": {
            "{0}|{1}".format(a, b): v
            for (a, b), v in pairwise_stream_identity(streams).items()
        },
        "_streams": streams,            # in-memory only; not serialised
    }

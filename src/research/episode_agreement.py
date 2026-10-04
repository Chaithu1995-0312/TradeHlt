"""
Phase 2C — typed AGREEMENT object (O14): fold over Phase 2B propositions.

Agreement does **not** discover new relationships. It only folds:

  PROPOSITIONS[]  →  Agreement(verdict, by_relation, unresolved_conflicts, …)

Prime law (EPISODE_SEMANTIC_INTEGRATION_PHASE2.md §9):
  Agreement must preserve conflict; it must not turn conflict into false agreement.

AGR-v0 verdict:
  BREAK    — any exit-claim CONFLICT (unresolved) OR missing O11/O12 propositions
  PARTIAL  — no CONFLICT, but exit INSUFFICIENT/SILENT, or zero SAME_EVENT on exit claims
  COHERENT — O11 SAME_EVENT, O12 ORTHOGONAL|SAME_EVENT, zero CONFLICT, exit claims present

Non-goals: spine consumption, economic authority, re-deriving O11/O12, reopening POL-O12.

Authority: research_shadow. PRODUCTION_BEHAVIOR_CHANGED=NO.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from research.episode_propositions import (
    EXIT_CLAIM_KINDS,
    RELATION_VOCAB,
    Proposition,
    attach_propositions,
    build_propositions,
)

POLICY_VERSION = "AGR-v0"
AGREEMENT_AUTHORITY = "research_shadow"

VERDICT_VOCAB: frozenset[str] = frozenset({"COHERENT", "PARTIAL", "BREAK"})

# Exit claims whose CONFLICT forces BREAK under AGR-v0.
_EXIT_KINDS = frozenset(EXIT_CLAIM_KINDS)


@dataclass(frozen=True)
class Agreement:
    """Episode-level fold of typed propositions (research shadow)."""

    episode_id: str
    policy_version: str
    authority: str
    verdict: str
    surfaces_participating: dict[str, Any]
    by_relation: dict[str, list[dict[str, Any]]]
    aligned: list[str]
    tension: list[str]
    silent: list[str]
    insufficient: list[str]
    unresolved_conflicts: list[dict[str, Any]]
    episode_interpretation: str
    exit_claims_present: bool
    relation_counts: dict[str, int]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.verdict not in VERDICT_VOCAB:
            raise ValueError(f"unknown verdict {self.verdict!r}")
        if self.policy_version != POLICY_VERSION:
            raise ValueError(f"unsupported policy_version {self.policy_version!r}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


def _as_prop_dicts(props: Sequence[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in props:
        if isinstance(p, Proposition):
            out.append(p.to_dict())
        elif isinstance(p, Mapping):
            out.append(dict(p))
        else:
            raise TypeError(f"proposition must be Proposition or mapping, got {type(p)}")
    return out


def _surfaces_participating(ep: Mapping[str, Any]) -> dict[str, Any]:
    me = ep.get("model_evidence") or {}
    vals = me.get("values") or {}
    return {
        "magnitude_states": ep.get("magnitude_states"),
        "feature_states": ep.get("feature_states"),
        "context_signature": (ep.get("market_context") or {}).get("signature"),
        "shape": {
            "name": (ep.get("market_shape") or {}).get("name"),
            "family": (ep.get("market_shape") or {}).get("family"),
            "matched": (ep.get("market_shape") or {}).get("matched"),
        },
        "crt": {
            "state": (ep.get("crt") or {}).get("state"),
            "direction": ((ep.get("crt") or {}).get("event") or {}).get("direction"),
        },
        "testimony": {
            mid: {
                "value": (v or {}).get("value"),
                "semantic": (v or {}).get("semantic"),
            }
            for mid, v in vals.items()
            if isinstance(v, dict)
        },
        "testimony_absent": list(me.get("absent") or []),
    }


def _bucket_by_relation(props: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {r: [] for r in sorted(RELATION_VOCAB)}
    for p in props:
        rel = str(p.get("relation") or "")
        if rel not in buckets:
            # unknown relation — park under INSUFFICIENT for visibility, do not drop
            buckets["INSUFFICIENT"].append(dict(p))
            continue
        buckets[rel].append(dict(p))
    return buckets


def _prop_note(p: Mapping[str, Any]) -> str:
    note = (p.get("surfaces") or {}).get("adjudication_note")
    pol = (p.get("resolution") or {}).get("policy_id")
    base = f"{p.get('proposition_id')} {p.get('claim_kind')}→{p.get('relation')}"
    if note:
        base = f"{base}: {note}"
    if pol:
        base = f"{base} [{pol}]"
    return base


def _verdict_agr_v0(
    props: Sequence[Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]], bool, tuple[str, ...]]:
    """Return (verdict, unresolved_conflicts, exit_claims_present, notes)."""
    notes: list[str] = []
    by_kind = {p.get("claim_kind"): p for p in props if p.get("claim_kind")}
    exit_present = all(k in by_kind for k in _EXIT_KINDS)
    if not exit_present:
        missing = [k for k in _EXIT_KINDS if k not in by_kind]
        notes.append(f"missing exit claims: {missing}")
        # missing exit props ⇒ BREAK
        conflicts = [dict(p) for p in props if p.get("relation") == "CONFLICT"]
        return "BREAK", conflicts, False, tuple(notes)

    unresolved = [
        dict(p)
        for p in props
        if p.get("relation") == "CONFLICT" and p.get("claim_kind") in _EXIT_KINDS
    ]
    # All CONFLICT on exit claims are unresolved under AGR-v0 (no auto-resolve).
    # Also surface diagnostic CONFLICT if any (should be rare).
    unresolved_all = [
        dict(p) for p in props if p.get("relation") == "CONFLICT"
    ]
    if unresolved:
        notes.append(
            f"unresolved exit CONFLICT count={len(unresolved)} — preserve, do not false-agree"
        )
        return "BREAK", unresolved_all, True, tuple(notes)

    o11 = by_kind.get("DIRECTION_ALIGNMENT") or {}
    o12 = by_kind.get("CHAPTER_VS_STRUCTURE_SCORE") or {}
    o11_rel = o11.get("relation")
    o12_rel = o12.get("relation")

    # COHERENT: O11 SAME_EVENT, O12 ORTHOGONAL|SAME_EVENT, no CONFLICT anywhere on exit
    if o11_rel == "SAME_EVENT" and o12_rel in ("ORTHOGONAL", "SAME_EVENT"):
        notes.append("O11 SAME_EVENT + O12 non-conflict join → COHERENT under AGR-v0")
        return "COHERENT", [], True, tuple(notes)

    # No CONFLICT but not COHERENT → PARTIAL
    if o11_rel in ("INSUFFICIENT", "SILENT") or o12_rel in ("INSUFFICIENT", "SILENT"):
        notes.append("exit claim INSUFFICIENT/SILENT → PARTIAL")
    elif o11_rel == "ORTHOGONAL" or (o11_rel != "SAME_EVENT"):
        notes.append("no exit CONFLICT but O11 not SAME_EVENT → PARTIAL")
    else:
        notes.append("no exit CONFLICT; COHERENT criteria not met → PARTIAL")
    return "PARTIAL", [], True, tuple(notes)


def build_agreement(
    ep: Mapping[str, Any],
    *,
    propositions: Sequence[Any] | None = None,
) -> Agreement:
    """Fold episode propositions into an Agreement object (AGR-v0)."""
    eid = str(ep.get("episode_id") or "")
    if not eid:
        raise ValueError("episode requires episode_id")

    if propositions is None:
        raw = ep.get("propositions")
        if raw:
            prop_dicts = _as_prop_dicts(raw)
        else:
            prop_dicts = _as_prop_dicts(build_propositions(ep))
    else:
        prop_dicts = _as_prop_dicts(propositions)

    buckets = _bucket_by_relation(prop_dicts)
    verdict, unresolved, exit_present, notes = _verdict_agr_v0(prop_dicts)

    aligned = [_prop_note(p) for p in buckets["SAME_EVENT"]]
    # ORTHOGONAL is declared non-join — list under aligned notes as policy-resolved, not tension
    for p in buckets["ORTHOGONAL"]:
        aligned.append(f"ORTHOGONAL(non-join) {_prop_note(p)}")

    tension = [_prop_note(p) for p in buckets["CONFLICT"]]
    silent = [_prop_note(p) for p in buckets["SILENT"]]
    me = ep.get("model_evidence") or {}
    for mid in me.get("absent") or []:
        silent.append(f"model_absent:{mid}")
    insufficient = [_prop_note(p) for p in buckets["INSUFFICIENT"]]

    counts = {r: len(buckets[r]) for r in sorted(RELATION_VOCAB)}

    # Build interpretation without broken o12 helper
    crt = (ep.get("crt") or {}).get("state")
    direction = ((ep.get("crt") or {}).get("event") or {}).get("direction")
    shape = (ep.get("market_shape") or {}).get("name")
    mag = ep.get("magnitude_states") or {}
    parts = [
        f"Episode {eid}: CRT={crt} dir={direction} shape={shape} magnitude={mag}.",
        (
            f"Proposition fold ({POLICY_VERSION}): "
            f"SAME_EVENT={counts['SAME_EVENT']} ORTHOGONAL={counts['ORTHOGONAL']} "
            f"CONFLICT={counts['CONFLICT']} INSUFFICIENT={counts['INSUFFICIENT']} "
            f"SILENT={counts['SILENT']}."
        ),
        f"Verdict={verdict}.",
    ]
    if unresolved:
        unotes = [
            (u.get("surfaces") or {}).get("adjudication_note") or u.get("proposition_id")
            for u in unresolved
        ]
        parts.append(
            "Unresolved conflicts (preserved, not false-agreed): "
            + "; ".join(str(n) for n in unotes)
            + "."
        )
    else:
        parts.append("No unresolved exit CONFLICT propositions.")
    for p in buckets["ORTHOGONAL"]:
        if p.get("claim_kind") == "CHAPTER_VS_STRUCTURE_SCORE":
            parts.append(
                "O12 is ORTHOGONAL under POL-O12-SCORE-NOT-CHAPTER "
                "(structure_rule_score ≠ CRT chapter membership)."
            )
            break
    interpretation = " ".join(parts)

    return Agreement(
        episode_id=eid,
        policy_version=POLICY_VERSION,
        authority=AGREEMENT_AUTHORITY,
        verdict=verdict,
        surfaces_participating=_surfaces_participating(ep),
        by_relation=buckets,
        aligned=aligned,
        tension=tension,
        silent=silent,
        insufficient=insufficient,
        unresolved_conflicts=list(unresolved),
        episode_interpretation=interpretation,
        exit_claims_present=exit_present,
        relation_counts=counts,
        notes=notes,
    )


def attach_agreement(ep: dict[str, Any], *, ensure_propositions: bool = True) -> dict[str, Any]:
    """Shallow-copy episode with propositions (optional) and agreement_object attached.

    Also writes a compact ``agreement`` view for legacy readers:
      aligned/tension/silent from the fold + verdict/policy_version.
    Does **not** remove CONFLICT from tension.
    """
    out = dict(ep)
    if ensure_propositions and not out.get("propositions"):
        out = attach_propositions(out)
    agr = build_agreement(out)
    out["agreement_object"] = agr.to_dict()
    # Legacy-compatible surface (heuristic replaced by fold views)
    out["agreement"] = {
        "aligned": list(agr.aligned),
        "tension": list(agr.tension),
        "silent": list(agr.silent),
        "insufficient": list(agr.insufficient),
        "verdict": agr.verdict,
        "policy_version": agr.policy_version,
        "note": "AGR-v0_fold_over_propositions_not_heuristic",
    }
    return out


def verdict_to_layer_status(verdict: str) -> str:
    """Map Agreement verdict → phase2_chain_coherence AGREEMENT layer token."""
    if verdict == "COHERENT":
        return "OK"
    if verdict == "PARTIAL":
        return "PARTIAL"
    if verdict == "BREAK":
        return "BREAK"
    return "BREAK"

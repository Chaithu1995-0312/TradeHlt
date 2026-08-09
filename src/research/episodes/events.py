"""EventEngine — sparse semantic milestones DERIVED from an episode timeline.

Events are never stored in the episode (substrate §11). They are regenerated from
the observation timeline by a versioned rulepack, so inventing a new event kind in
five years costs a new rulepack and zero migrations — the canonical episodes are
not touched.

Three properties this module must keep:

  1. **Pure.** Same episode + same rulepack -> same EventSet, always. No I/O, no
     randomness, no clock.
  2. **Policy-free.** A detector may read the entry geometry and the observation
     prefix, never an exit policy. This is why there is no `EXIT`/`SL_HIT`/`TP_HIT`
     event: whether a touch *closes* the position is a PolicyEvaluator question.
     `TP_TOUCH` here means "price reached the target level", not "the trade won".
  3. **Non-mutating.** The episode is read-only input.

Detectors consume the `Derived` layer (`mfe_r`/`mae_r`/`unrealized_pnl_r`/
`distance_to_sl_raw`), which is recomputed on the fly when an episode was stored
observation-only — so events work identically on lean and cached corpora.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence

from research.episodes.schema import (
    Derived,
    EntrySnapshot,
    EpisodeStep,
    OpportunityEpisode,
    resolved_derived,
)

ENGINE_ID = "research.episodes.events.EventEngine"


# ─────────────────────────────────────────────────────────────────
# TYPES
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class EpisodeEvent:
    """One semantic milestone at one step."""

    episode_id: str
    kind: str
    t: int                      # step offset; 1-based over forward bars
    bar_index: int              # global OHLCV index
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventSet:
    """All events for one (episode, rulepack) pair. A derived, regenerable artifact."""

    episode_id: str
    instrument: str
    rulepack_id: str
    rulepack_hash: str
    engine_hash: str
    protocol_id: str
    events: list[EpisodeEvent] = field(default_factory=list)

    def kinds(self) -> set[str]:
        return {e.kind for e in self.events}

    def first(self, kind: str, **match: Any) -> EpisodeEvent | None:
        """First event of `kind` whose payload matches every `match` item."""
        for e in self.events:
            if e.kind != kind:
                continue
            if all(e.payload.get(k) == v for k, v in match.items()):
                return e
        return None

    def of_kind(self, kind: str) -> list[EpisodeEvent]:
        return [e for e in self.events if e.kind == kind]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["events"] = [asdict(e) for e in self.events]
        return d


@dataclass(frozen=True)
class Rulepack:
    """A named, hashable set of detectors + their thresholds."""

    rulepack_id: str
    detectors: tuple[str, ...]
    params: dict[str, Any] = field(default_factory=dict)

    def hash(self) -> str:
        blob = json.dumps(
            {"id": self.rulepack_id, "detectors": list(self.detectors), "params": self.params},
            sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def engine_hash() -> str:
    import research.episodes.events as _self

    return hashlib.sha256(inspect.getsource(_self).encode("utf-8")).hexdigest()[:32]


# ─────────────────────────────────────────────────────────────────
# DETECTORS — pure functions (entry, steps, derived, params) -> events
# ─────────────────────────────────────────────────────────────────
_Ctx = tuple[EntrySnapshot, Sequence[EpisodeStep], Sequence[Derived | None], dict]


def _detect_entry(entry, steps, derived, params) -> list[tuple[str, int, dict]]:
    """The episode opens. Anchors every EventSet at t=0."""
    return [("ENTRY", 0, {"direction": entry.direction,
                          "risk_distance": round(entry.risk_distance, 8)})]


def _detect_reached_r(entry, steps, derived, params) -> list[tuple[str, int, dict]]:
    """First bar at which running MFE crosses each R threshold.

    Comparison is in RAW PRICE UNITS (`mfe >= r * risk`), byte-for-byte the predicate
    `horizon_excursion` uses for `bars_to_first_1r` (`fav >= risk`) — not a ratio
    against a tolerance. Measured on the real BNBUSDT corpus: the ratio form with a
    1e-12 epsilon disagreed on 2/2999 episodes, where a true excursion of
    0.9999999999998966 R sat exactly on the 1R boundary. The kernel is the governing
    definition, so this detector adopts its arithmetic rather than approximating it.
    """
    risk = entry.risk_distance
    out = []
    for r in params.get("r_thresholds", ()):
        for step, d in zip(steps, derived):
            if d is None:
                continue
            if d.mfe_raw >= r * risk:
                out.append(("REACHED_R", step.obs.t, {"r": float(r)}))
                break
    return out


def _detect_new_mfe(entry, steps, derived, params) -> list[tuple[str, int, dict]]:
    """Every bar that sets a new favorable extreme."""
    out, best = [], 0.0
    for step, d in zip(steps, derived):
        if d is None:
            continue
        if d.mfe_r > best + 1e-12:
            best = d.mfe_r
            out.append(("NEW_MFE", step.obs.t, {"mfe_r": round(d.mfe_r, 6)}))
    return out


def _detect_new_mae(entry, steps, derived, params) -> list[tuple[str, int, dict]]:
    """Every bar that sets a new adverse extreme."""
    out, worst = [], 0.0
    for step, d in zip(steps, derived):
        if d is None:
            continue
        if d.mae_r < worst - 1e-12:
            worst = d.mae_r
            out.append(("NEW_MAE", step.obs.t, {"mae_r": round(d.mae_r, 6)}))
    return out


def _detect_be_eligible(entry, steps, derived, params) -> list[tuple[str, int, dict]]:
    """First bar at which a break-even stop move would be justified.

    Threshold is rulepack-declared, NOT hardcoded: 'when is BE earned' is a research
    question, and different packs should be able to disagree without a code change.
    """
    thr = params.get("be_mfe_r", 1.0)
    risk = entry.risk_distance
    for step, d in zip(steps, derived):
        if d is None:
            continue
        if d.mfe_raw >= thr * risk:      # raw units, same as REACHED_R
            return [("BE_ELIGIBLE", step.obs.t, {"mfe_r": round(d.mfe_r, 6),
                                                 "threshold_r": float(thr)})]
    return []


def _detect_sl_threat(entry, steps, derived, params) -> list[tuple[str, int, dict]]:
    """Bars where the CLOSE sits within `threat_r` of the stop.

    Close-based on purpose: a wick that pierces the stop is an exit question, and
    exits belong to the PolicyEvaluator. This measures pressure, not resolution.
    """
    thr = params.get("sl_threat_r", 0.25)
    risk = entry.risk_distance
    out = []
    for step, d in zip(steps, derived):
        if d is None or risk <= 0:
            continue
        dist_r = d.distance_to_sl_raw / risk
        if d.distance_to_sl_raw <= thr * risk:
            out.append(("SL_THREAT", step.obs.t, {"distance_to_sl_r": round(dist_r, 6),
                                                  "threshold_r": float(thr)}))
    return out


def _detect_tp_touch(entry, steps, derived, params) -> list[tuple[str, int, dict]]:
    """First bar whose range reaches the target LEVEL.

    NOT `TP_HIT`: this is pure geometry. Whether the touch closes the position (and
    whether SL got there first) is decided by an exit policy, never here.
    """
    if entry.tp_price is None:
        return []
    is_long = entry.direction == "long"
    for step in steps:
        if step.obs.t < 1:
            continue
        touched = (step.obs.high >= entry.tp_price) if is_long else (step.obs.low <= entry.tp_price)
        if touched:
            return [("TP_TOUCH", step.obs.t, {"tp_price": entry.tp_price})]
    return []


DETECTORS: dict[str, Callable[..., list[tuple[str, int, dict]]]] = {
    "ENTRY": _detect_entry,
    "REACHED_R": _detect_reached_r,
    "NEW_MFE": _detect_new_mfe,
    "NEW_MAE": _detect_new_mae,
    "BE_ELIGIBLE": _detect_be_eligible,
    "SL_THREAT": _detect_sl_threat,
    "TP_TOUCH": _detect_tp_touch,
}


# ─────────────────────────────────────────────────────────────────
# RULEPACKS — versioned, coexisting
# ─────────────────────────────────────────────────────────────────
RULEPACK_V1 = Rulepack(
    rulepack_id="v1",
    detectors=("ENTRY", "REACHED_R", "NEW_MFE", "NEW_MAE",
               "BE_ELIGIBLE", "SL_THREAT", "TP_TOUCH"),
    params={
        "r_thresholds": [0.5, 1.0, 1.5, 2.0, 3.0],
        "be_mfe_r": 1.0,
        "sl_threat_r": 0.25,
    },
)

RULEPACKS: dict[str, Rulepack] = {RULEPACK_V1.rulepack_id: RULEPACK_V1}


def register_rulepack(pack: Rulepack) -> None:
    """Add a rulepack. Existing packs are immutable — re-registering an id raises.

    This is the whole regenerability story: a new pack yields a new EventSet over
    the SAME untouched episodes.
    """
    if pack.rulepack_id in RULEPACKS:
        raise ValueError(
            f"rulepack {pack.rulepack_id!r} already registered — versions are immutable; "
            "publish a new id instead of mutating one"
        )
    unknown = [d for d in pack.detectors if d not in DETECTORS]
    if unknown:
        raise ValueError(f"rulepack {pack.rulepack_id!r} names unknown detectors: {unknown}")
    RULEPACKS[pack.rulepack_id] = pack


# ─────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────
class EventEngine:
    """Deterministic, versioned event detection. Never mutates the episode."""

    def detect(self, episode: OpportunityEpisode, rulepack_id: str = "v1") -> EventSet:
        pack = RULEPACKS.get(rulepack_id)
        if pack is None:
            raise ValueError(
                f"EventEngine: unknown rulepack {rulepack_id!r} "
                f"(registered: {sorted(RULEPACKS)})"
            )

        steps = list(episode.steps)
        derived = resolved_derived(episode)   # rebuilt if stored observation-only

        raw: list[tuple[str, int, dict]] = []
        for name in pack.detectors:
            raw.extend(DETECTORS[name](episode.entry, steps, derived, pack.params))

        by_t = {s.obs.t: s.obs.bar_index for s in steps}
        events = [
            EpisodeEvent(episode_id=episode.episode_id, kind=kind, t=t,
                         bar_index=by_t.get(t, -1), payload=payload)
            for kind, t, payload in raw
        ]
        # Stable order so two runs serialize identically.
        events.sort(key=lambda e: (e.t, e.kind, json.dumps(e.payload, sort_keys=True)))

        return EventSet(
            episode_id=episode.episode_id,
            instrument=episode.instrument,
            rulepack_id=pack.rulepack_id,
            rulepack_hash=pack.hash(),
            engine_hash=engine_hash(),
            protocol_id=episode.provenance.protocol_id,
            events=events,
        )

    def detect_many(self, episodes, rulepack_id: str = "v1") -> list[EventSet]:
        return [self.detect(ep, rulepack_id) for ep in episodes]

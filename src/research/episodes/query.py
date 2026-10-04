"""Episode Query Engine v1 — selections over episodes + LabelSets + EventSets.

A library API, deliberately not a string DSL (substrate §23 decision 6): the useful
predicates are not known yet, and freezing a query language before they are would be
the expensive kind of guess.

Three properties:

  1. **Results are VIEWS, never new truth.** A `QueryResult` holds references to the
     episodes it selected. Nothing is rebuilt, nothing is mutated, and no selection
     is ever a source of truth for a downstream claim.
  2. **Immutable chaining.** Every builder method returns a NEW query, so a partially
     built query can be branched safely.
  3. **Hashable.** `query_hash()` is a stable digest of the ordered predicate list, so
     a reported number can name the exact selection that produced it — the paper
     trail substrate §14 asks for.

⚠ **SELECTION ON A DERIVED PATH IS FORWARD-LOOKING. IT IS NOT AN EDGE.**

`where_derived` predicates read the timeline *after* entry, so any selection built on
them uses information unavailable at decision time. Selecting "reached 1R within 6
bars without exceeding 0.4R adverse" and then reporting that the survivors won is
circular: the filter chose favorable paths, so favorable labels are guaranteed.

Measured on 4,999 real BNBUSDT episodes, that exact query yields 414 survivors at
98.1% TP_HIT and mean +1.97R. **That number is an artifact of the selection, not a
finding**, and quoting it as performance would be the E-001 failure class this repo
has a whole charter about.

Legitimate uses: cohort description, conditional-structure study, building a training
subset with a declared and disclosed selection rule. Illegitimate: any expectancy,
win-rate, or PF claim presented as attainable. A tradeable claim needs a predicate
computable at t=0 — i.e. entry features, never `where_derived`. Query results carry
NO authority (§6.5).

Joins are lazy: `join_labels`/`join_events` only run PolicyEvaluator/EventEngine over
the episodes that survived filtering, not the whole corpus.

    q = (EpisodeQuery(episodes)
            .filter_instrument("BNBUSDT")
            .where_derived(reached_r_within(1.0, 6))
            .where_derived(max_adverse_r_at_least(-0.4))
            .join_labels("intrabar_fixed"))
    result = q.run()
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from research.episodes.events import EventEngine, EventSet
from research.episodes.policy import LabelSet, PolicyEvaluator
from research.episodes.protocol import GOVERNING_POLICY
from research.episodes.schema import Derived, OpportunityEpisode, resolved_derived

# A derived-timeline predicate: (episode, derived_steps) -> bool.
DerivedPredicate = Callable[[OpportunityEpisode, Sequence[Derived | None]], bool]


# ─────────────────────────────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class QueryResult:
    """A selection. Holds references — it does not own or rebuild any episode."""

    episodes: list[OpportunityEpisode]
    query_hash: str
    steps: list[str]
    n_input: int
    labels: dict[str, LabelSet] = field(default_factory=dict)   # by episode_id
    events: dict[str, EventSet] = field(default_factory=dict)   # by episode_id
    funnel: list[tuple[str, int]] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.episodes)

    def episode_ids(self) -> list[str]:
        return [e.episode_id for e in self.episodes]

    def label_values(self, field_name: str) -> list[Any]:
        """Column of a joined LabelSet field, in selection order."""
        return [getattr(self.labels[e.episode_id], field_name)
                for e in self.episodes if e.episode_id in self.labels]

    def summary(self) -> dict[str, Any]:
        return {
            "query_hash": self.query_hash,
            "steps": list(self.steps),
            "n_input": self.n_input,
            "n_selected": self.n,
            "funnel": [{"step": s, "surviving": k} for s, k in self.funnel],
            "joined_labels": len(self.labels),
            "joined_events": len(self.events),
        }


# ─────────────────────────────────────────────────────────────────
# PREDICATE FACTORIES (composable, self-naming for the paper trail)
# ─────────────────────────────────────────────────────────────────
def reached_r_within(r: float, bars: int) -> DerivedPredicate:
    """MFE reaches `r` R at or before step `bars`."""
    def _p(ep, derived):
        for step, d in zip(ep.steps, derived):
            if d is None or step.obs.t > bars:
                continue
            if d.mfe_raw >= r * ep.entry.risk_distance:   # kernel arithmetic, raw units
                return True
        return False
    _p.__name__ = f"reached_r_within(r={r},bars={bars})"
    return _p


def max_adverse_r_at_least(floor_r: float, within: int | None = None) -> DerivedPredicate:
    """Adverse excursion never drops below `floor_r` (a negative number).

    e.g. `max_adverse_r_at_least(-0.4)` keeps episodes that never went worse than −0.4R.
    """
    def _p(ep, derived):
        risk = ep.entry.risk_distance
        for step, d in zip(ep.steps, derived):
            if d is None or (within is not None and step.obs.t > within):
                continue
            if d.mae_raw < floor_r * risk:
                return False
        return True
    _p.__name__ = f"max_adverse_r_at_least(floor_r={floor_r},within={within})"
    return _p


def min_forward_bars(n: int) -> DerivedPredicate:
    """Episode carries at least `n` forward observations (power guard)."""
    def _p(ep, derived):
        return len(ep.forward_steps) >= n
    _p.__name__ = f"min_forward_bars(n={n})"
    return _p


# ─────────────────────────────────────────────────────────────────
# QUERY
# ─────────────────────────────────────────────────────────────────
class EpisodeQuery:
    """Immutable query builder over a sequence of episodes."""

    def __init__(self, episodes: Iterable[OpportunityEpisode]):
        self._episodes: list[OpportunityEpisode] = list(episodes)
        self._ops: list[tuple[str, Callable[..., Any]]] = []
        self._label_policy: str | None = None
        self._event_rulepack: str | None = None
        self._evaluator: PolicyEvaluator | None = None

    # ── internal: functional clone ──
    def _next(self, desc: str, op: Callable[..., Any] | None = None,
              **attrs: Any) -> "EpisodeQuery":
        q = EpisodeQuery(self._episodes)
        q._ops = [*self._ops, (desc, op)]   # op is None for join markers
        q._label_policy = self._label_policy
        q._event_rulepack = self._event_rulepack
        q._evaluator = self._evaluator
        for k, v in attrs.items():
            setattr(q, k, v)
        return q

    # ── episode-level filters ──
    def filter_population(self, population: str) -> "EpisodeQuery":
        return self._next(f"filter_population({population})",
                          lambda ep: ep.population == population)

    def filter_instrument(self, instrument: str) -> "EpisodeQuery":
        return self._next(f"filter_instrument({instrument})",
                          lambda ep: ep.instrument == instrument)

    def filter_direction(self, direction: str) -> "EpisodeQuery":
        return self._next(f"filter_direction({direction})",
                          lambda ep: ep.entry.direction == direction)

    def filter_time_range(self, start: str | None = None,
                          end: str | None = None) -> "EpisodeQuery":
        """Half-open [start, end) on the entry timestamp.

        Timestamps are canonical 'YYYY-MM-DD HH:MM:SS' strings, so lexicographic
        comparison is chronological — no parsing, no timezone guessing.
        """
        def _p(ep):
            ts = ep.entry.timestamp
            if start is not None and ts < start:
                return False
            if end is not None and ts >= end:
                return False
            return True
        return self._next(f"filter_time_range({start},{end})", _p)

    def filter(self, predicate: Callable[[OpportunityEpisode], bool],
               name: str | None = None) -> "EpisodeQuery":
        """Arbitrary episode-level predicate."""
        label = name or getattr(predicate, "__name__", "<predicate>")
        return self._next(f"filter({label})", predicate)

    # ── derived-timeline predicates ──
    def where_derived(self, predicate: DerivedPredicate,
                      name: str | None = None) -> "EpisodeQuery":
        """Predicate over the derived path. Rebuilds Derived for lean corpora."""
        label = name or getattr(predicate, "__name__", "<predicate>")
        return self._next(f"where_derived({label})",
                          lambda ep: predicate(ep, resolved_derived(ep)))

    # ── joins (lazy: run only over survivors) ──
    def join_labels(self, policy_id: str = GOVERNING_POLICY,
                    evaluator: PolicyEvaluator | None = None) -> "EpisodeQuery":
        q = self._next(f"join_labels({policy_id})")
        q._label_policy = policy_id
        q._evaluator = evaluator or self._evaluator
        return q

    def join_events(self, rulepack_id: str = "v1") -> "EpisodeQuery":
        q = self._next(f"join_events({rulepack_id})")
        q._event_rulepack = rulepack_id
        return q

    # ── post-join predicates ──
    def where_label(self, predicate: Callable[[LabelSet], bool],
                    name: str | None = None) -> "EpisodeQuery":
        if self._label_policy is None:
            raise ValueError("where_label requires join_labels(...) first")
        label = name or getattr(predicate, "__name__", "<predicate>")
        return self._next(f"where_label({label})", ("label", predicate))

    def where_events(self, predicate: Callable[[EventSet], bool],
                     name: str | None = None) -> "EpisodeQuery":
        if self._event_rulepack is None:
            raise ValueError("where_events requires join_events(...) first")
        label = name or getattr(predicate, "__name__", "<predicate>")
        return self._next(f"where_events({label})", ("event", predicate))

    def limit(self, n: int) -> "EpisodeQuery":
        return self._next(f"limit({n})", ("limit", n))

    # ── identity ──
    def query_hash(self) -> str:
        """Stable digest of the ordered predicate list — the selection's paper trail.

        A bare `lambda` contributes '<lambda>', which weakens the trail; pass `name=`
        or use the predicate factories (which name themselves) when it matters.
        """
        blob = json.dumps([d for d, _ in self._ops], separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def describe(self) -> list[str]:
        return [d for d, _ in self._ops]

    # ── execution ──
    def run(self) -> QueryResult:
        survivors = list(self._episodes)
        funnel: list[tuple[str, int]] = [("input", len(survivors))]
        labels: dict[str, LabelSet] = {}
        events: dict[str, EventSet] = {}

        evaluator = self._evaluator or PolicyEvaluator()
        engine = EventEngine()

        for desc, op in self._ops:
            if op is None:                              # a join marker
                if desc.startswith("join_labels"):
                    labels = {ep.episode_id: evaluator.evaluate(ep, self._label_policy)
                              for ep in survivors}
                elif desc.startswith("join_events"):
                    events = {ep.episode_id: engine.detect(ep, self._event_rulepack)
                              for ep in survivors}
            elif isinstance(op, tuple):
                kind, arg = op
                if kind == "limit":
                    survivors = survivors[:arg]
                elif kind == "label":
                    survivors = [ep for ep in survivors if arg(labels[ep.episode_id])]
                elif kind == "event":
                    survivors = [ep for ep in survivors if arg(events[ep.episode_id])]
            else:
                survivors = [ep for ep in survivors if op(ep)]
            funnel.append((desc, len(survivors)))

        # Keep joined artifacts aligned with the FINAL selection.
        kept = {ep.episode_id for ep in survivors}
        labels = {k: v for k, v in labels.items() if k in kept}
        events = {k: v for k, v in events.items() if k in kept}

        return QueryResult(
            episodes=survivors,
            query_hash=self.query_hash(),
            steps=self.describe(),
            n_input=len(self._episodes),
            labels=labels,
            events=events,
            funnel=funnel,
        )

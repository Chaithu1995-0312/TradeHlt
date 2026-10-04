"""OpportunityEpisode canonical types (protocol OE_L1).

The canonical episode is an ENTRY SNAPSHOT + an OBSERVATION TIMELINE + PROVENANCE.
Nothing else. Labels, events and annotations are derived artifacts with their own
versioned provenance and their own stores.

Two invariants are enforced structurally rather than by convention:

  1. `EpisodeProvenance` has NO `exit_policy_hash`. Policy identity lives on the
     LabelSet (`policy.py`). An episode that carried a policy hash would be a
     policy-coupled artifact, defeating the whole design (substrate §10/§12).

  2. `Derived` has NO `stop`/`tp`. Those are policy state — a trailing stop is a
     function of the exit policy. `Derived` holds only quantities computable from
     the entry snapshot's FIXED geometry plus the observation prefix 0..t.

`Derived` is a recomputable cache: `EpisodeStep.derived` may be None in storage and
rebuilt on read via `recompute_derived()`. Observations never change.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

from research.episodes.protocol import (
    OBSERVATION_SCHEMA_VERSION,
    POPULATIONS,
    PROTOCOL_ID,
)

SCHEMA_VERSION = 1


# ─────────────────────────────────────────────────────────────────
# OBSERVATION — immutable facts
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Observation:
    """One bar of market fact. NEVER rewritten without a new schema version.

    `t` is the offset from the entry bar: t=0 IS the entry bar (protocol OE_L1).
    `bar_index` is the global OHLCV index, which is what joins back to the batch
    feature matrix and what `forward_walk` asserts against for no-lookahead.
    """

    t: int
    bar_index: int
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


# ─────────────────────────────────────────────────────────────────
# DERIVED — recomputable from entry geometry + observation prefix
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Derived:
    """Path metrics under the FIXED entry geometry. No policy state (see module doc).

    All excursion fields are running values over bars 1..t (the entry bar itself
    contributes nothing — a policy may not act on its own entry bar).
    """

    unrealized_pnl_raw: float = 0.0
    unrealized_pnl_r: float = 0.0
    mfe_raw: float = 0.0
    mae_raw: float = 0.0
    mfe_r: float = 0.0
    mae_r: float = 0.0
    drawdown_from_peak_r: float = 0.0
    distance_to_sl_raw: float = 0.0
    distance_to_tp_raw: float = 0.0
    bars_held: int = 0


# ─────────────────────────────────────────────────────────────────
# ANNOTATIONS — versioned interpretations (side-car preferred)
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Annotations:
    """Non-authoritative interpretations. Regenerable without rebuilding episodes."""

    annotator_id: str = ""
    regime: str | None = None
    structure: str | None = None
    trend: str | None = None
    volatility_class: str | None = None
    atr: float | None = None            # opt-in; NOT an observation (prereg decision 3)
    engine_scores: dict[str, float] | None = None
    custom: dict[str, Any] | None = None


@dataclass(frozen=True)
class EpisodeStep:
    obs: Observation
    derived: Derived | None = None       # recomputable cache; may be None in storage
    annotations: Annotations | None = None


# ─────────────────────────────────────────────────────────────────
# ENTRY SNAPSHOT — frozen decision context
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class EntrySnapshot:
    """What was decided, where, when, with what geometry.

    `sl_price` is required — risk_distance is the R unit every derived metric and
    every policy divides by, so an episode without it cannot be labelled.
    `tp_price` may be None (structural / hypothesis episodes carry no target).
    """

    bar_index: int
    timestamp: str
    direction: str                       # "long" | "short"
    entry_price: float
    sl_price: float
    tp_price: float | None = None
    atr_entry: float | None = None
    engine_scores: dict[str, float] | None = None
    feature_vector: list[float] | None = None
    generator_config: dict[str, Any] | None = None

    # ── candidate namespace (see protocol.FEATURE_NAMESPACES) ──
    # Free-form research features: any names, any count, may change between runs.
    # Deliberately a DICT, not a vector — no dimension constant means nothing to go
    # stale. Excluded from `content_hash()` (a versioned interpretation, not an
    # immutable observation), so adding or dropping one never re-identifies the
    # episode. Carries NO authority; graduates to CANONICAL_FEATURES only on ΔG001.
    candidate_features: dict[str, float] | None = None

    @property
    def risk_distance(self) -> float:
        return abs(self.entry_price - self.sl_price)

    @property
    def tp_reward_mult(self) -> float | None:
        """|tp - entry| / risk — the `tp_atr_mult` a policy feeds the kernel."""
        if self.tp_price is None:
            return None
        risk = self.risk_distance
        if risk <= 0:
            return None
        return abs(self.tp_price - self.entry_price) / risk


# ─────────────────────────────────────────────────────────────────
# PROVENANCE — reproducibility (NO exit_policy_hash; see module doc)
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class EpisodeProvenance:
    protocol_id: str = PROTOCOL_ID
    protocol_hash: str = ""
    schema_version: int = SCHEMA_VERSION
    observation_schema_version: int = OBSERVATION_SCHEMA_VERSION
    builder_id: str = ""
    builder_hash: str = ""
    candle_source: str = ""
    candle_source_hash: str = ""
    feature_schema_hash: str = ""
    entry_geometry_hash: str = ""
    pit_status: str = ""
    source_run_id: str = ""
    created_utc: str = ""


# ─────────────────────────────────────────────────────────────────
# THE CANONICAL EPISODE
# ─────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class OpportunityEpisode:
    episode_id: str
    population: str
    instrument: str
    timeframe: str
    entry: EntrySnapshot
    steps: list[EpisodeStep]
    provenance: EpisodeProvenance
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.population not in POPULATIONS:
            raise ValueError(
                f"OpportunityEpisode: unknown population {self.population!r} "
                f"(expected one of {POPULATIONS})"
            )

    @property
    def forward_steps(self) -> list[EpisodeStep]:
        """Steps a policy may consume: t>=1 only (the entry bar is context)."""
        return [s for s in self.steps if s.obs.t >= 1]

    def content_hash(self) -> str:
        """SHA-256 over identity + entry geometry + the OBSERVATION timeline.

        Deliberately excludes `derived` and `annotations`: they are regenerable
        caches, so an episode whose cache was dropped or re-annotated is the SAME
        canonical episode. Excludes provenance timestamps for the same reason.

        Also excludes `entry.candidate_features` — the candidate namespace is a
        versioned interpretation that research is expected to change constantly, so
        it must not re-identify the episode it annotates.
        """
        entry = {k: v for k, v in asdict(self.entry).items() if k != "candidate_features"}
        payload = {
            "episode_id": self.episode_id,
            "population": self.population,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "entry": entry,
            "observations": [asdict(s.obs) for s in self.steps],
            "observation_schema_version": self.provenance.observation_schema_version,
            "schema_version": self.provenance.schema_version,
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────
# IDENTITY + DERIVATION HELPERS
# ─────────────────────────────────────────────────────────────────
def episode_id(instrument: str, timestamp: str, direction: str,
               entry: float, sl: float, population: str) -> str:
    """Deterministic identity.

    Same shape as `clean_labels.builder._unit_id` (instrument|ts|direction|entry|sl)
    plus `population`, so a detection episode and a spine episode at the same bar
    are distinct records rather than colliding.
    """
    raw = f"{instrument}|{timestamp}|{direction}|{entry:.8f}|{sl:.8f}|{population}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def entry_geometry_hash(entry: EntrySnapshot) -> str:
    payload = {
        "direction": entry.direction,
        "entry_price": round(entry.entry_price, 8),
        "sl_price": round(entry.sl_price, 8),
        "tp_price": None if entry.tp_price is None else round(entry.tp_price, 8),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def resolved_derived(episode: "OpportunityEpisode") -> list[Derived | None]:
    """The episode's Derived layer, rebuilt if the corpus was stored observation-only.

    Single helper so every consumer (EventEngine, QueryEngine, …) treats lean and
    cached corpora identically instead of each re-implementing the fallback.
    """
    derived = [s.derived for s in episode.steps]
    if any(d is None for s, d in zip(episode.steps, derived) if s.obs.t >= 1):
        return recompute_derived(episode.entry, [s.obs for s in episode.steps])
    return derived


def recompute_derived(entry: EntrySnapshot,
                      observations: Sequence[Observation]) -> list[Derived | None]:
    """Rebuild the `Derived` cache for a full observation timeline.

    Pure: same entry + same observations -> same output. The t=0 entry bar gets
    None (a policy may not act on its own entry bar), matching the kernel's
    no-lookahead contract. Excursions are running max/min over bars 1..t.

    NOT ROUNDED. Rounding here silently changed threshold comparisons: a path whose
    true excursion is 0.9999999999998966 R rounds to exactly 1.0 at 8 dp, so a
    consumer testing `mfe_r >= 1.0` fired a bar earlier than the audited kernel,
    which compares raw price units. Rounding is a *serialization* concern; the
    derived layer keeps full float64 precision.
    """
    risk = entry.risk_distance
    if risk <= 0:
        raise ValueError(f"recompute_derived: non-positive risk_distance ({risk})")
    is_long = entry.direction == "long"
    e = entry.entry_price

    out: list[Derived | None] = []
    mfe = 0.0
    mae = 0.0
    for obs in observations:
        if obs.t < 1:
            out.append(None)
            continue
        high, low, close = obs.high, obs.low, obs.close
        if is_long:
            fav, adv = high - e, low - e
            unreal = close - e
        else:
            fav, adv = e - low, e - high
            unreal = e - close
        if fav > mfe:
            mfe = fav
        if adv < mae:
            mae = adv
        dist_sl = abs(close - entry.sl_price)
        dist_tp = abs(entry.tp_price - close) if entry.tp_price is not None else 0.0
        out.append(Derived(
            unrealized_pnl_raw=unreal,
            unrealized_pnl_r=unreal / risk,
            mfe_raw=mfe,
            mae_raw=mae,
            mfe_r=mfe / risk,
            mae_r=mae / risk,
            # how far the position has given back from its best point, in R
            drawdown_from_peak_r=(mfe - unreal) / risk,
            distance_to_sl_raw=dist_sl,
            distance_to_tp_raw=dist_tp,
            bars_held=obs.t,
        ))
    return out

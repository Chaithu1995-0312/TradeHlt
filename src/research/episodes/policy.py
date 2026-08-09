"""PolicyEvaluator — labels derived from an episode under a chosen exit policy.

THE ONE RULE: this module wraps `research.measurement.forward_walk` and nothing
else. It contains no exit logic of its own — no SL/TP comparison, no tie-break, no
trailing ratchet. Substrate §18 rates "second exit kernel drift" CRITICAL, and the
P2 parity floor exists to prove that rule held: labels produced here must be
field-identical to what today's `clean_labels` builder produces from the same units.

The kernel takes a frozen `Signal` expressed in ATR multiples with a single TP. An
episode carries absolute prices, so the evaluator reconstructs the signal exactly as
`clean_labels.builder` already does — `atr = risk_distance`, `sl_atr_mult = 1.0`,
`tp_atr_mult = |tp - entry| / risk` — which makes one R the unit and reproduces the
same geometry the kernel was audited under.

Multi-level exits (TP1/TP2 + partial_tp_fraction, F-056) are NOT expressible this
way and are a declared non-goal of OE_L1 (see the pre-registration).

The episode is never mutated. Same episode + same policy -> same LabelSet.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from research.contracts import Signal
from research.episodes.protocol import (
    COST_BPS,
    GOVERNING_POLICY,
    MAX_FORWARD,
    V1_POLICIES,
)
from research.episodes.schema import Observation, OpportunityEpisode
from research.measurement.forward_walk import forward_walk, horizon_excursion

EVALUATOR_ID = "research.episodes.policy.PolicyEvaluator"


def evaluator_hash() -> str:
    import research.episodes.policy as _self

    return hashlib.sha256(inspect.getsource(_self).encode("utf-8")).hexdigest()[:32]


def policy_hash(policy_id: str, config: dict[str, Any]) -> str:
    blob = json.dumps({"policy_id": policy_id, "config": config},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


def cost_model_hash(cost_bps: float) -> str:
    blob = json.dumps({"model": f"flat_{cost_bps:g}bps_round_trip"}, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class LabelSet:
    """Derived labels for one (episode, policy) pair.

    Carries the policy identity that deliberately does NOT live on the episode
    (substrate §12). Fields mirror `research.contracts.Outcome` so existing
    consumers can migrate without reshaping their readers.
    """

    episode_id: str
    instrument: str
    # ── policy identity ──
    exit_policy_id: str
    exit_policy_hash: str
    cost_model_hash: str
    evaluator_hash: str
    protocol_id: str
    # ── Outcome-shaped labels (path-derived; never stream fields) ──
    outcome: str                     # TP_HIT | SL_HIT | TIMEOUT
    rr_achieved: float
    mfe: float                       # price units, >= 0
    mae: float                       # price units, <= 0
    duration_candles: int
    time_to_tp: int | None
    time_to_failure: int | None
    reached_1r: bool
    # ── R-normalized + cost-adjusted derivations ──
    mfe_r: float = 0.0
    mae_r: float = 0.0
    rr_net: float = 0.0
    cost_r: float = 0.0
    # ── exit-agnostic envelope (never exits; isolates entry information) ──
    horizon: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _StepBar:
    """Adapts an episode Observation to the bar duck-type the kernel reads.

    The kernel checks `.index > signal.entry_index`, which is why `bar_index` (the
    GLOBAL ohlcv index) is carried on every observation rather than the local `t`.
    """

    __slots__ = ("index", "high", "low", "close", "open", "volume")

    def __init__(self, obs: Observation):
        self.index = obs.bar_index
        self.high = obs.high
        self.low = obs.low
        self.close = obs.close
        self.open = obs.open
        self.volume = obs.volume


class PolicyEvaluator:
    """Applies an exit policy to an episode. Pure; never mutates the episode."""

    def __init__(self, *, max_forward: int = MAX_FORWARD, cost_bps: float = COST_BPS,
                 trail_mult: float = 0.5):
        self.max_forward = max_forward
        self.cost_bps = cost_bps
        self.trail_mult = trail_mult

    # ── signal reconstruction (the clean_labels convention, reused verbatim) ──
    def _signal(self, ep: OpportunityEpisode, tp_reward_mult: float | None) -> Signal:
        entry = ep.entry
        risk = entry.risk_distance
        if risk <= 0:
            raise ValueError(f"PolicyEvaluator: non-positive risk_distance ({risk})")
        if tp_reward_mult is None or tp_reward_mult <= 0:
            raise ValueError(
                f"PolicyEvaluator: episode {ep.episode_id} has no positive TP geometry; "
                "a target is required to label under an exit policy"
            )
        return Signal(
            instrument=ep.instrument,
            timestamp=entry.timestamp,
            entry_index=entry.bar_index,
            direction=entry.direction,
            entry=entry.entry_price,
            sl_atr_mult=1.0,          # risk_distance IS the unit -> 1R
            tp_atr_mult=tp_reward_mult,
            atr=risk,
        )

    def _future(self, ep: OpportunityEpisode) -> list[_StepBar]:
        """Bars t>=1 only — the entry bar is context, never walkable."""
        return [_StepBar(s.obs) for s in ep.forward_steps]

    def evaluate(
        self,
        episode: OpportunityEpisode,
        policy_id: str = GOVERNING_POLICY,
        *,
        tp_reward_mult: float | None = None,
        with_horizon: bool = True,
    ) -> LabelSet:
        """Label one episode under `policy_id`.

        Args:
            tp_reward_mult: override the episode's own TP geometry (in R). Used for
                stretch-target labels such as clean_labels' 3R TP2 head.
            with_horizon: also compute the exit-agnostic excursion envelope.
        """
        if policy_id not in V1_POLICIES:
            raise ValueError(
                f"PolicyEvaluator: policy {policy_id!r} is not in the OE_L1 v1 set "
                f"{V1_POLICIES}. Adding one requires a pre-registration, not a code edit "
                "(no second exit kernel)."
            )

        entry = episode.entry
        risk = entry.risk_distance
        mult = tp_reward_mult if tp_reward_mult is not None else entry.tp_reward_mult
        sig = self._signal(episode, mult)
        future = self._future(episode)

        oc = forward_walk(
            sig, future,
            max_forward=self.max_forward,
            trail_mult=self.trail_mult,
            exit_model=policy_id,
        )

        hz: dict[str, Any] = {}
        if with_horizon:
            # Unit geometry: the envelope never exits, so its TP multiple is inert.
            env_sig = Signal(
                instrument=episode.instrument, timestamp=entry.timestamp,
                entry_index=entry.bar_index, direction=entry.direction,
                entry=entry.entry_price, sl_atr_mult=1.0, tp_atr_mult=1.0, atr=risk,
            )
            hz = horizon_excursion(env_sig, future, max_forward=self.max_forward)

        cost_frac = self.cost_bps / 10_000.0
        cost_r = (cost_frac * entry.entry_price / risk) if risk > 0 else 0.0

        cfg = {
            "max_forward": self.max_forward,
            "trail_mult": self.trail_mult,
            "tp_reward_mult": round(float(mult), 8),
        }
        return LabelSet(
            episode_id=episode.episode_id,
            instrument=episode.instrument,
            exit_policy_id=policy_id,
            exit_policy_hash=policy_hash(policy_id, cfg),
            cost_model_hash=cost_model_hash(self.cost_bps),
            evaluator_hash=evaluator_hash(),
            protocol_id=episode.provenance.protocol_id,
            outcome=oc.outcome,
            rr_achieved=oc.rr_achieved,
            mfe=oc.mfe,
            mae=oc.mae,
            duration_candles=oc.duration_candles,
            time_to_tp=oc.time_to_tp,
            time_to_failure=oc.time_to_failure,
            reached_1r=oc.reached_1r,
            mfe_r=round(oc.mfe / risk, 8) if risk > 0 else 0.0,
            mae_r=round(oc.mae / risk, 8) if risk > 0 else 0.0,
            rr_net=round(oc.rr_achieved - cost_r, 8),
            cost_r=round(cost_r, 8),
            horizon=hz,
        )

    def evaluate_all(self, episode: OpportunityEpisode,
                     policies: tuple[str, ...] = V1_POLICIES) -> dict[str, LabelSet]:
        """Multi-policy labels from ONE episode — no rebuild, no re-ingest."""
        return {p: self.evaluate(episode, p) for p in policies}

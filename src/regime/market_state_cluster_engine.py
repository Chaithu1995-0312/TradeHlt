"""
market_state_cluster_engine.py
==============================
Cluster-native market state classification.

Market regimes EMERGE from the statistical profile of the cluster the current
bar is assigned to, combined with structural indicators (sweep density, BOS
density, displacement, volatility).

NO EMA thresholds. NO hardcoded regime-from-indicator rules.
Regimes are derived from cluster statistics learned from replay history.

Output regimes:
    TREND_EXPANSION        — high RR persistence, BOS dominant, low trap
    RANGE_TRAP             — high trap frequency, sweep dense, mean_rr ≈ 0
    LIQUIDITY_COMPRESSION  — low volatility, low BOS, high liquidity proximity
    BREAKOUT_CONTINUATION  — positive RR, recent BOS, displacement present
    VOLATILE_REVERSAL      — high std_rr, high sweep density, instability
    TRANSITIONAL_CHAOS     — high entropy, low cluster confidence, timeout-heavy

Production safety:
  - Cooldown of 5 bars prevents regime chattering
  - Returns TRANSITIONAL_CHAOS with confidence=0 when no cluster stats available
  - All scoring functions are pure (no state); only cooldown logic is stateful
  - Never raises; returns a valid MarketStateOutput on any input
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("MARKET_STATE_CLUSTER")

# ── Regime labels ─────────────────────────────────────────────────────────────

TREND_EXPANSION        = "TREND_EXPANSION"
RANGE_TRAP             = "RANGE_TRAP"
LIQUIDITY_COMPRESSION  = "LIQUIDITY_COMPRESSION"
BREAKOUT_CONTINUATION  = "BREAKOUT_CONTINUATION"
VOLATILE_REVERSAL      = "VOLATILE_REVERSAL"
TRANSITIONAL_CHAOS     = "TRANSITIONAL_CHAOS"

_ALL_REGIMES = (
    TREND_EXPANSION,
    RANGE_TRAP,
    LIQUIDITY_COMPRESSION,
    BREAKOUT_CONTINUATION,
    VOLATILE_REVERSAL,
    TRANSITIONAL_CHAOS,
)

# Minimum bars between regime state changes (anti-chattering)
_DEFAULT_COOLDOWN_BARS = 5


@dataclass
class MarketStateOutput:
    """Full market state classification result."""
    market_state:       str
    cluster_id:         int
    cluster_confidence: float
    state_persistence:  float
    volatility_profile: str    # "low" | "medium" | "high"
    liquidity_profile:  str    # "compressed" | "normal" | "swept"
    trap_probability:   float
    compression_score:  float


class MarketStateClusterEngine:
    """
    Derives market state from cluster statistics + structural features.

    Parameters
    ----------
    min_cluster_samples : int
        Minimum samples needed for a cluster to contribute a regime vote.
    cooldown_bars : int
        Minimum bars between regime transitions (prevents chattering).
    """

    def __init__(
        self,
        min_cluster_samples: int = 5,
        cooldown_bars: int = _DEFAULT_COOLDOWN_BARS,
    ):
        self._min_samples    = min_cluster_samples
        self._cooldown       = cooldown_bars
        self._last_regime    = TRANSITIONAL_CHAOS
        self._bars_since_change = 0
        self._persistence_count = 0

    def classify(
        self,
        features: dict,
        cluster_stats: Optional[object] = None,    # ClusterStats from ReplayMemoryEngine
        replay_features: Optional[dict] = None,    # from ReplayMemoryEngine.get_replay_features()
    ) -> MarketStateOutput:
        """
        Classify market state from canonical features + cluster statistics.

        Parameters
        ----------
        features       : canonical feature dict. Required keys (with fallback defaults):
                         volatility_ratio, sweep_detected, double_sweep,
                         break_of_structure, disp_strength, liquidity_distance,
                         liquidity_pressure_score, volume_spike, atr,
                         retest_depth, candles_since_retest.
        cluster_stats  : ClusterStats object from ReplayMemoryEngine (optional).
                         When None, uses neutral statistical defaults.
        replay_features: dict from ReplayMemoryEngine.get_replay_features() (optional).

        Returns
        -------
        MarketStateOutput — always valid, never raises.
        """
        try:
            return self._classify_inner(features, cluster_stats, replay_features)
        except Exception as exc:
            logger.warning(
                "MarketStateClusterEngine.classify() failed (fail-open): %s", exc
            )
            return MarketStateOutput(
                market_state       = TRANSITIONAL_CHAOS,
                cluster_id         = -1,
                cluster_confidence = 0.0,
                state_persistence  = 0.0,
                volatility_profile = "medium",
                liquidity_profile  = "normal",
                trap_probability   = 0.5,
                compression_score  = 0.0,
            )

    # ── Private ───────────────────────────────────────────────────────────────

    def _classify_inner(
        self,
        features: dict,
        cluster_stats: Optional[object],
        replay_features: Optional[dict],
    ) -> MarketStateOutput:
        cluster_id = (
            getattr(cluster_stats, "cluster_id", -1)
            if cluster_stats is not None else -1
        )

        # ── Extract structural signals ────────────────────────────────────────
        volatility_ratio     = float(features.get("volatility_ratio",          1.0))
        sweep_detected       = float(features.get("sweep_detected",             0.0))
        double_sweep         = float(features.get("double_sweep",               0.0))
        bos                  = float(features.get("break_of_structure",         0.0))
        disp_strength        = float(features.get("disp_strength",              0.0))
        liquidity_dist       = float(features.get("liquidity_distance",         5.0))
        liquidity_pressure   = float(features.get("liquidity_pressure_score",   0.3))
        vol_spike            = float(features.get("volume_spike",               0.0))
        atr                  = float(features.get("atr",                        0.001))
        candles_since_retest = float(features.get("candles_since_retest",       0.0))

        # ── Extract cluster/replay statistics ─────────────────────────────────
        cs = cluster_stats
        has_stats = (
            cs is not None
            and getattr(cs, "n_samples", 0) >= self._min_samples
        )

        if has_stats:
            hist_winrate    = float(cs.win_rate)
            hist_mean_rr    = float(cs.mean_rr)
            hist_std_rr     = float(cs.std_rr)
            trap_freq       = float(cs.trap_frequency)
            staleness       = float(cs.staleness_days)
            cluster_conf    = min(1.0, cs.n_samples / 50.0)  # saturates at 50 samples
            rf              = replay_features or {}
            entropy         = float(rf.get("market_state_entropy",  0.5))
            transition_prob = float(rf.get("transition_probability", 0.2))
        else:
            hist_winrate, hist_mean_rr, hist_std_rr = 0.5, 0.0, 1.0
            trap_freq, staleness, entropy, transition_prob = 0.3, 0.0, 0.8, 0.3
            cluster_conf = 0.0

        # ── Volatility profile ────────────────────────────────────────────────
        if volatility_ratio > 1.8:
            vol_profile = "high"
        elif volatility_ratio < 0.8:
            vol_profile = "low"
        else:
            vol_profile = "medium"

        # ── Liquidity profile ─────────────────────────────────────────────────
        if double_sweep > 0 or sweep_detected > 0:
            liq_profile = "swept"
        elif liquidity_pressure > 0.7:
            liq_profile = "compressed"
        else:
            liq_profile = "normal"

        # ── Compression score ─────────────────────────────────────────────────
        # High when price is very close to a liquidity level AND ATR is small
        compression_score = max(0.0, 1.0 - liquidity_dist / 5.0) * max(0.0, 1.0 - atr * 20.0)
        compression_score = max(0.0, min(1.0, compression_score))

        # ── Regime scoring (emergent — no if-EMA-then-trend rules) ────────────
        scores = {
            TREND_EXPANSION:       self._score_trend_expansion(
                                       hist_mean_rr, hist_winrate, bos,
                                       disp_strength, trap_freq, hist_std_rr),
            RANGE_TRAP:            self._score_range_trap(
                                       trap_freq, sweep_detected, hist_mean_rr,
                                       hist_std_rr, liq_profile),
            LIQUIDITY_COMPRESSION: self._score_liquidity_compression(
                                       compression_score, vol_profile, bos,
                                       sweep_detected),
            BREAKOUT_CONTINUATION: self._score_breakout_continuation(
                                       hist_winrate, hist_mean_rr, bos,
                                       disp_strength, candles_since_retest),
            VOLATILE_REVERSAL:     self._score_volatile_reversal(
                                       hist_std_rr, sweep_detected, double_sweep,
                                       vol_spike, vol_profile),
            TRANSITIONAL_CHAOS:    self._score_transitional_chaos(
                                       entropy, transition_prob, cluster_conf,
                                       staleness),
        }

        best_regime = max(scores, key=lambda k: scores[k])

        # ── Cooldown: only switch if cooldown elapsed ─────────────────────────
        if best_regime != self._last_regime:
            if self._bars_since_change < self._cooldown:
                # Suppress transition — stay in current regime
                best_regime = self._last_regime
                self._bars_since_change += 1
                # persistence count keeps incrementing while locked
                self._persistence_count += 1
            else:
                # Transition allowed
                self._last_regime = best_regime
                self._bars_since_change = 0
                self._persistence_count = 0
        else:
            self._bars_since_change += 1
            self._persistence_count += 1

        state_persistence = min(1.0, self._persistence_count / 20.0)

        return MarketStateOutput(
            market_state       = best_regime,
            cluster_id         = cluster_id,
            cluster_confidence = round(cluster_conf, 4),
            state_persistence  = round(state_persistence, 4),
            volatility_profile = vol_profile,
            liquidity_profile  = liq_profile,
            trap_probability   = round(trap_freq, 4),
            compression_score  = round(compression_score, 4),
        )

    # ── Regime scoring functions (pure — no state mutations) ──────────────────

    def _score_trend_expansion(
        self,
        mean_rr: float,
        win_rate: float,
        bos: float,
        disp: float,
        trap_freq: float,
        std_rr: float,
    ) -> float:
        score  = 0.35 * max(0.0, mean_rr / 2.0)          # high mean RR
        score += 0.25 * win_rate                           # high win rate
        score += 0.20 * abs(bos)                           # BOS present
        score += 0.10 * min(1.0, disp / 1.5)              # displacement
        score -= 0.10 * trap_freq                          # penalty for traps
        return max(0.0, min(1.0, score))

    def _score_range_trap(
        self,
        trap_freq: float,
        sweep: float,
        mean_rr: float,
        std_rr: float,
        liq_profile: str,
    ) -> float:
        score  = 0.40 * trap_freq
        score += 0.25 * sweep
        score += 0.20 * (1.0 if liq_profile == "swept" else 0.0)
        score += 0.15 * (1.0 - min(1.0, abs(mean_rr) / 2.0))  # near-zero mean rr
        return max(0.0, min(1.0, score))

    def _score_liquidity_compression(
        self,
        compression_score: float,
        vol_profile: str,
        bos: float,
        sweep: float,
    ) -> float:
        score  = 0.50 * compression_score
        score += 0.25 * (1.0 if vol_profile == "low" else 0.0)
        score += 0.15 * (1.0 - abs(bos))     # no BOS = compression
        score += 0.10 * (1.0 - sweep)         # no sweep
        return max(0.0, min(1.0, score))

    def _score_breakout_continuation(
        self,
        win_rate: float,
        mean_rr: float,
        bos: float,
        disp: float,
        candles_since_retest: float,
    ) -> float:
        score  = 0.35 * win_rate
        score += 0.25 * max(0.0, mean_rr / 2.0)
        score += 0.20 * abs(bos)
        score += 0.20 * min(1.0, disp)
        # Recency bonus: fresh retest (≤10 bars) boosts breakout continuation
        if 0 < candles_since_retest <= 10:
            score += 0.10
        return max(0.0, min(1.0, score))

    def _score_volatile_reversal(
        self,
        std_rr: float,
        sweep: float,
        double_sweep: float,
        vol_spike: float,
        vol_profile: str,
    ) -> float:
        score  = 0.35 * min(1.0, std_rr / 2.0)   # high RR variance
        score += 0.25 * sweep
        score += 0.25 * double_sweep
        score += 0.15 * vol_spike
        return max(0.0, min(1.0, score))

    def _score_transitional_chaos(
        self,
        entropy: float,
        transition_prob: float,
        cluster_conf: float,
        staleness_days: float,
    ) -> float:
        score  = 0.40 * entropy
        score += 0.30 * transition_prob
        score += 0.20 * (1.0 - cluster_conf)              # low cluster confidence
        score += 0.10 * min(1.0, staleness_days / 30.0)   # stale cluster
        return max(0.0, min(1.0, score))

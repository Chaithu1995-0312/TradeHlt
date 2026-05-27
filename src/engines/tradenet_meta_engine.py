"""
tradenet_meta_engine.py
=======================
TradeNet meta-cognition layer.

Takes composite engine outputs (Gaussian, RR, Zone, Replay, Regime, Liquidity)
and produces a capital-quality assessment.

The existing 35-dim TradeNet model is loaded and used as the base scorer (p_win).
Its sigmoid output is combined with replay, regime, and liquidity meta-context to
produce the capital_quality_score.

Future version: retrain TradeNet with extended meta-feature inputs.

Fail-safe contract:
  - Any exception returns neutral fallback (allocation_confidence=0.0, QUARTER authority)
  - 100ms timeout enforced on total compute(); returns fallback if exceeded
  - PyTorch unavailable → base p_win = 0.5 (still computes meta-context composite)
  - No active model in registry → base p_win = 0.5

Lookahead: none. All inputs are outputs of prior synchronous engine steps.
"""
from __future__ import annotations

import logging
import math
import time
from typing import Optional

from utils.logging_config import get_flow_logger

logger = get_flow_logger("TRADENET_META")

# Lazy import — do not fail at module load if PyTorch is absent
_TORCH_AVAILABLE = False
try:
    import torch as _torch
    _TORCH_AVAILABLE = True
except ImportError:
    pass

_TIMEOUT_MS = 100    # hard inference time limit in ms


class TradeNetMetaEngine:
    """
    Meta-cognition layer wrapping the existing TradeNet model.

    The TradeNet model (35→32→16→1+Sigmoid binary classifier) is used as a
    base p_win signal. That signal is blended with replay, regime, zone, and
    liquidity meta-context to produce a capital_quality_score.

    Parameters
    ----------
    config : dict
        Engine-runner config (may contain a "tradenet_meta" sub-section).
    preload : bool
        If True, attempt model load at construction. Default False (lazy).
    """

    def __init__(self, config: dict, preload: bool = False):
        self.config = config
        self._model = None
        self._scaler: Optional[dict] = None
        self._n_features: Optional[int] = None
        self._version: Optional[str] = None
        self._load_failed: bool = False

        if preload:
            self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def compute(
        self,
        features: dict,
        gaussian_result: dict,
        rr_result: dict,
        zone_result: dict,
        replay_result: Optional[dict] = None,
        market_state_result: Optional[object] = None,  # MarketStateOutput
    ) -> dict:
        """
        Compute capital quality score.

        Parameters
        ----------
        features            : canonical feature dict
        gaussian_result     : output from GaussianEngine.compute()
        rr_result           : output from RREngine.compute()
        zone_result         : output from ZoneGateEngine.compute()
        replay_result       : output from ReplayMemoryEngine.query() (optional)
        market_state_result : MarketStateOutput dataclass (optional)

        Returns
        -------
        dict with keys:
            capital_quality_score  : float [0, 1]
            expected_trade_quality : "PREMIUM" | "STANDARD" | "MARGINAL" | "POOR"
            allocation_confidence  : float [0, 1]
            risk_authority         : "FULL" | "HALF" | "QUARTER" | "NONE"
            meta                   : dict (breakdown for telemetry)
        """
        t0 = time.monotonic()
        _fallback = self._fallback_output()

        try:
            # Lazy model load
            if not self._load_failed and self._model is None:
                self._load()

            # Base score from canonical features via existing TradeNet
            base_p_win = self._inference_base(features)

            # Timeout check after model inference
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            if elapsed_ms > _TIMEOUT_MS:
                logger.warning(
                    "TradeNetMeta: timeout (%.1fms > %dms) — returning fallback.",
                    elapsed_ms, _TIMEOUT_MS,
                )
                return _fallback

            # ── Meta-context extraction ───────────────────────────────────────
            g_score    = float(gaussian_result.get("score",  0.5))
            rr_score   = float(rr_result.get("score",        0.5))
            zone_score = float(zone_result.get("score",      0.5))

            replay_r    = replay_result or {}
            hist_wr     = float(replay_r.get("historical_winrate",   0.5))
            hist_rr     = float(replay_r.get("historical_rr",        0.0))
            cluster_stb = float(replay_r.get("cluster_stability",    0.5))
            replay_dens = float(replay_r.get("replay_density",       0.0))

            ms = market_state_result
            trap_prob   = float(getattr(ms, "trap_probability",  0.3) if ms else 0.3)
            state_pers  = float(getattr(ms, "state_persistence", 0.5) if ms else 0.5)

            liq_pressure = float(features.get("liquidity_pressure_score", 0.3))

            # ── Capital Quality composite ─────────────────────────────────────
            # Weights sum to ~1.0 (net of penalty terms)
            # Base TradeNet p_win     : 0.30
            # Gaussian anchor         : 0.20
            # RR engine               : 0.15
            # Zone engine             : 0.10
            # Historical win rate     : 0.15
            # Cluster stability bonus : 0.05
            # State persistence bonus : 0.05
            # Trap penalty            : -0.05
            # Liq-compression penalty : -0.05 × (1 − stability)
            cq = (
                0.30 * base_p_win
                + 0.20 * g_score
                + 0.15 * rr_score
                + 0.10 * zone_score
                + 0.15 * hist_wr
                + 0.05 * cluster_stb
                + 0.05 * state_pers
                - 0.05 * trap_prob
                - 0.05 * liq_pressure * (1.0 - cluster_stb)
            )
            cq = max(0.0, min(1.0, cq))

            # Allocation confidence: how reliable is this quality score?
            alloc_conf = (
                cluster_stb * 0.50
                + replay_dens * 0.30
                + state_pers  * 0.20
            )
            alloc_conf = max(0.0, min(1.0, alloc_conf))

            # ── Quality tier ──────────────────────────────────────────────────
            if cq >= 0.75:
                quality   = "PREMIUM"
                risk_auth = "FULL"
            elif cq >= 0.60:
                quality   = "STANDARD"
                risk_auth = "HALF"
            elif cq >= 0.45:
                quality   = "MARGINAL"
                risk_auth = "QUARTER"
            else:
                quality   = "POOR"
                risk_auth = "NONE"

            latency_ms = (time.monotonic() - t0) * 1000.0

            return {
                "capital_quality_score":  round(cq, 4),
                "expected_trade_quality": quality,
                "allocation_confidence":  round(alloc_conf, 4),
                "risk_authority":         risk_auth,
                "meta": {
                    "base_p_win":        round(base_p_win, 4),
                    "g_score":           round(g_score, 4),
                    "rr_score":          round(rr_score, 4),
                    "zone_score":        round(zone_score, 4),
                    "hist_winrate":      round(hist_wr, 4),
                    "cluster_stability": round(cluster_stb, 4),
                    "trap_probability":  round(trap_prob, 4),
                    "state_persistence": round(state_pers, 4),
                    "latency_ms":        round(latency_ms, 2),
                    "model_version":     self._version,
                },
            }

        except Exception as exc:
            logger.warning(
                "TradeNetMeta.compute() failed (fail-open): %s", exc
            )
            return _fallback

    # ── Private ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """
        Lazy-load TradeNet model + scaler from active registry entry.
        Sets _load_failed=True on any exception (fail-open).
        """
        if not _TORCH_AVAILABLE:
            logger.warning(
                "TradeNetMeta: PyTorch unavailable — base p_win will be 0.5."
            )
            self._load_failed = True
            return
        try:
            from core.model_registry import get_active_tradenet          # noqa: PLC0415
            from training.trainer import load_model, load_tradenet_scaler  # noqa: PLC0415

            version = get_active_tradenet()
            if version is None:
                logger.warning("TradeNetMeta: no active TradeNet in registry.")
                self._load_failed = True
                return

            model, n_features = load_model(version)
            scaler_data = load_tradenet_scaler(version)

            self._model     = model
            self._scaler    = scaler_data
            self._n_features = n_features
            self._version   = version
            self._load_failed = False

            logger.info(
                "TradeNetMeta: loaded version=%s n_features=%d",
                version, n_features,
            )

        except Exception as exc:
            logger.warning(
                "TradeNetMeta: load failed (fail-open) — %s. "
                "base p_win will be 0.5.", exc,
            )
            self._model = None
            self._scaler = None
            self._load_failed = True

    def _inference_base(self, features: dict) -> float:
        """
        Run TradeNet forward pass. Returns p_win ∈ [0, 1]. Falls back to 0.5.

        Schema migration safety: input vector is truncated to model's n_features
        when the pipeline runs schema v3.0 (38-dim) but the model was trained on
        schema v2.0 (35-dim).
        """
        if self._model is None or self._scaler is None:
            return 0.5
        try:
            from features.dataset_builder import extract_feature_vector  # noqa: PLC0415

            vec = extract_feature_vector(features)

            # Truncate to model's expected dimension (schema migration safety)
            n = self._n_features or len(vec)
            if len(vec) > n:
                vec = vec[:n]
            if len(vec) != n:
                logger.debug(
                    "TradeNetMeta._inference_base: vector length %d != model n_features %d, "
                    "returning 0.5.", len(vec), n,
                )
                return 0.5

            # Standardise
            mu    = self._scaler.get("mu",    [0.0] * n)
            sigma = self._scaler.get("sigma", [1.0] * n)
            scaled = [
                (vec[i] - float(mu[i])) / max(float(sigma[i]), 1e-9)
                for i in range(n)
            ]

            import torch  # noqa: PLC0415
            with torch.no_grad():
                x = torch.tensor(scaled, dtype=torch.float32).unsqueeze(0)
                p_win = float(self._model(x).squeeze().item())

            return max(0.0, min(1.0, p_win))

        except Exception as exc:
            logger.debug("TradeNetMeta._inference_base failed: %s", exc)
            return 0.5

    def _fallback_output(self) -> dict:
        return {
            "capital_quality_score":  0.5,
            "expected_trade_quality": "MARGINAL",
            "allocation_confidence":  0.0,
            "risk_authority":         "QUARTER",
            "meta": {"reason": "tradenet_meta_fallback"},
        }

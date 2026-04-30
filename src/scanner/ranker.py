# ranker.py — OpportunityRanker: scores and ranks signals
#
# Scoring formula (configurable weights):
#   score = confidence × w_conf + rr × w_rr + zone × w_zone
#
# Guardrails:
#   - Minimum score threshold: signals below threshold are discarded
#   - Correlated signals deprioritized (optional, via correlation_engine)
#
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Default scoring weights
_DEFAULT_CONFIDENCE_WEIGHT = 0.5
_DEFAULT_RR_WEIGHT = 0.3
_DEFAULT_ZONE_WEIGHT = 0.2
_DEFAULT_MIN_SCORE = 0.60


class OpportunityRanker:
    """
    Scores signals and returns them ranked best-first.

    Signal input schema:
        {
            "symbol": str,
            "confidence": float,   ← fusion model confidence (0–1)
            "rr": float,           ← risk-reward ratio (1.0–4.0 typical)
            "zone": float,         ← zone quality score (0–1)
            "action": str,         ← "BUY" | "SELL"
            ... optional fields
        }

    Usage:
        ranker = OpportunityRanker()
        scored = ranker.rank(signals)     # → sorted list, highest score first
        filtered = ranker.rank(signals, min_score=0.65)
    """

    def __init__(
        self,
        confidence_weight: float = _DEFAULT_CONFIDENCE_WEIGHT,
        rr_weight: float = _DEFAULT_RR_WEIGHT,
        zone_weight: float = _DEFAULT_ZONE_WEIGHT,
        min_score: float = _DEFAULT_MIN_SCORE,
        rr_normalizer: float = 3.0,  # normalize RR: rr/rr_normalizer (clipped to 0–1)
    ):
        self.confidence_weight = confidence_weight
        self.rr_weight = rr_weight
        self.zone_weight = zone_weight
        self.min_score = min_score
        self.rr_normalizer = rr_normalizer

    def score_signal(self, signal: dict) -> float:
        """
        Compute opportunity score for a single signal.

        RR is normalised: min(rr / rr_normalizer, 1.0) to keep score in [0, 1].
        """
        confidence = float(signal.get("confidence", 0.0))
        rr = float(signal.get("rr", 0.0))
        zone = float(signal.get("zone", 0.0))

        # Normalise RR to [0, 1]
        rr_norm = min(rr / self.rr_normalizer, 1.0) if self.rr_normalizer > 0 else 0.0

        return (
            confidence * self.confidence_weight
            + rr_norm * self.rr_weight
            + zone * self.zone_weight
        )

    def rank(
        self,
        signals: list,
        min_score: Optional[float] = None,
    ) -> list:
        """
        Score, filter by min_score, and return signals sorted best-first.

        Args:
            signals: list of signal dicts
            min_score: override instance min_score if provided

        Returns:
            Sorted list of signal dicts with '_score' key added.
        """
        threshold = min_score if min_score is not None else self.min_score
        scored = []

        for sig in signals:
            s = self.score_signal(sig)
            if s < threshold:
                log.debug(
                    "OpportunityRanker: discarded symbol=%s score=%.3f < threshold=%.3f",
                    sig.get("symbol", "?"), s, threshold,
                )
                continue
            enriched = dict(sig)
            enriched["_score"] = s
            scored.append(enriched)

        ranked = sorted(scored, key=lambda x: x["_score"], reverse=True)
        log.info(
            "OpportunityRanker: %d input, %d passed threshold=%.2f",
            len(signals), len(ranked), threshold,
        )
        return ranked
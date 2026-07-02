"""TradeClustering: groups losing trades by condition to surface patterns."""

# clustering.py — TradeClustering: group losses by condition
import logging

log = logging.getLogger(__name__)

_MIN_CLUSTER_SIZE = 3   # ignore clusters smaller than this


class TradeClustering:
    """
    Groups losing trades by condition to surface patterns.

    Conditions checked:
      - low_zone: zone < zone_threshold
      - low_rr: rr < rr_threshold
      - low_confidence: confidence < confidence_threshold
      - ranging_regime: regime == RANGING

    Usage:
        tc = TradeClustering()
        clusters = tc.cluster_losses(trades)
        # → {"low_zone": [...], "low_rr": [...], ...}
    """

    def __init__(
        self,
        zone_threshold: float = 0.55,
        rr_threshold: float = 2.0,
        confidence_threshold: float = 0.60,
        min_cluster_size: int = _MIN_CLUSTER_SIZE,
    ):
        self.zone_threshold = zone_threshold
        self.rr_threshold = rr_threshold
        self.confidence_threshold = confidence_threshold
        self.min_cluster_size = min_cluster_size

    def cluster_losses(self, trades: list) -> dict:
        """Return dict of condition → list of losing trades matching that condition."""
        losses = [t for t in trades if t.get("result") == "LOSS"]
        if not losses:
            return {}

        clusters = {
            "low_zone": [t for t in losses if float(t.get("zone", 1.0)) < self.zone_threshold],
            "low_rr": [t for t in losses if float(t.get("rr", 99.0)) < self.rr_threshold],
            "low_confidence": [t for t in losses if float(t.get("confidence", 1.0)) < self.confidence_threshold],
            "ranging_regime": [t for t in losses if t.get("regime") == "RANGING"],
        }

        # Filter out small clusters (noise)
        filtered = {k: v for k, v in clusters.items() if len(v) >= self.min_cluster_size}
        log.info("TradeClustering: %d clusters from %d losses", len(filtered), len(losses))
        return filtered

    def loss_rate_by_condition(self, trades: list) -> dict:
        """Compute loss rate for each condition cluster."""
        clusters = self.cluster_losses(trades)
        result = {}
        for condition, cluster_losses in clusters.items():
            # Count all trades in same condition (not just losses)
            if condition == "low_zone":
                all_in_condition = [t for t in trades if float(t.get("zone", 1.0)) < self.zone_threshold]
            elif condition == "low_rr":
                all_in_condition = [t for t in trades if float(t.get("rr", 99.0)) < self.rr_threshold]
            elif condition == "low_confidence":
                all_in_condition = [t for t in trades if float(t.get("confidence", 1.0)) < self.confidence_threshold]
            elif condition == "ranging_regime":
                all_in_condition = [t for t in trades if t.get("regime") == "RANGING"]
            else:
                all_in_condition = cluster_losses

            loss_rate = len(cluster_losses) / len(all_in_condition) if all_in_condition else 0.0
            result[condition] = {"loss_rate": loss_rate, "loss_count": len(cluster_losses), "total": len(all_in_condition)}
        return result

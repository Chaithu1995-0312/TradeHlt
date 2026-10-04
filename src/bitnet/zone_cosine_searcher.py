"""
Zone Cosine Searcher
Searches for closest matching zone vectors using cosine similarity.

Exports
-------
BitNetSearchEngine            : vector-index cosine search (live inference path)
ZoneCandidate                 : Gaussian zone parameter container (search path)
ZoneResult                    : wrapper pairing a ZoneCandidate with its metrics
compute_gaussian_score        : score a raw list against a zone dict (live_engine API)
compute_gaussian_score_from_candidate : score a raw list against a ZoneCandidate
_evaluate_subset              : evaluate a candidate over a labelled subset
load_zone_registry            : load zone_registry.json → list[dict]
cosine_similarity             : utility cosine similarity between two float lists
"""

from __future__ import annotations

import json
import math
import os
import sys
from typing import Dict, List, Optional, Tuple

# Allow imports from the parent directory (d:/Tradelatest)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.dataset_builder import extract_feature_vector
from features.feature_schema import CANONICAL_FEATURE_DIM


# ─────────────────────────────────────────────────────────────────────────────
# ZONE CANDIDATE
# Immutable parameter container for a Gaussian zone discovered by the search.
# ─────────────────────────────────────────────────────────────────────────────

class ZoneCandidate:
    """
    Parameter container for a single Gaussian filter zone.

    Attributes
    ----------
    mu        : dict[str, float]  — feature-name → mean value
    sigma     : dict[str, float]  — feature-name → std deviation (> 0 enforced)
    weights   : dict[str, float]  — feature-name → weight (sum need not be 1)
    threshold : float             — minimum score for a trade to pass this zone
    meta      : dict              — arbitrary metadata (zone_id, train metrics, …)

    Notes
    -----
    Keys in mu/sigma/weights must match.  sigma values of 0 are clamped to
    1e-9 so that the Gaussian never divides by zero.
    """

    def __init__(
        self,
        mu:        Dict[str, float],
        sigma:     Dict[str, float],
        weights:   Dict[str, float],
        threshold: float = 0.7,
        meta:      Optional[dict] = None,
    ) -> None:
        if set(mu) != set(sigma) or set(mu) != set(weights):
            raise ValueError(
                "ZoneCandidate: mu, sigma, and weights must have identical keys. "
                f"Got mu={set(mu)}, sigma={set(sigma)}, weights={set(weights)}"
            )
        # Clamp sigma to avoid div-by-zero in Gaussian scoring
        self.mu        = dict(mu)
        self.sigma     = {k: max(v, 1e-9) for k, v in sigma.items()}
        self.weights   = dict(weights)
        self.threshold = float(threshold)
        self.meta      = dict(meta) if meta else {}

    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        """Serialise to a plain dict (round-trips through from_dict)."""
        return {
            "mu":        self.mu,
            "sigma":     self.sigma,
            "weights":   self.weights,
            "threshold": self.threshold,
            "meta":      self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ZoneCandidate":
        """Deserialise from a plain dict produced by to_dict()."""
        return cls(
            mu        = d["mu"],
            sigma     = d["sigma"],
            weights   = d["weights"],
            threshold = d.get("threshold", 0.7),
            meta      = d.get("meta", {}),
        )

    def __repr__(self) -> str:  # pragma: no cover
        keys = list(self.mu.keys())
        return (
            f"ZoneCandidate(features={keys}, threshold={self.threshold:.3f}, "
            f"meta={self.meta})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# ZONE RESULT
# Pairs a ZoneCandidate with train-time metrics after BitNet search completes.
# ─────────────────────────────────────────────────────────────────────────────

class ZoneResult:
    """
    Output record produced by BitNetSearchEngine.run_search().

    Attributes
    ----------
    candidate : ZoneCandidate — the discovered zone parameters
    metrics   : dict          — train-set metrics: trade_count, avg_rr,
                                winrate, max_drawdown, stability_score
    zone_id   : str           — unique identifier (e.g. "zone_001")
    """

    def __init__(
        self,
        candidate:      ZoneCandidate,
        metrics:        dict,
        zone_id:        str = "zone_unknown",
    ) -> None:
        self.candidate = candidate
        self.metrics   = dict(metrics)
        self.zone_id   = zone_id

    # ------------------------------------------------------------------
    def to_registry_dict(self) -> dict:
        """
        Serialise to the zone_registry.json format consumed by BitNetZoneGate.

        The live gate (live_engine.BitNetZoneGate) expects each zone entry
        to be a flat dict with list-form mu/sigma/weights so that
        compute_gaussian_score() can operate without key lookups.
        We store the key order in a separate 'feature_keys' field so the
        dict round-trips correctly.
        """
        keys   = list(self.candidate.mu.keys())
        mu_v   = [self.candidate.mu[k]      for k in keys]
        sig_v  = [self.candidate.sigma[k]   for k in keys]
        wgt_v  = [self.candidate.weights[k] for k in keys]
        return {
            "id":           self.zone_id,
            "feature_keys": keys,
            "mu":           mu_v,
            "sigma":        sig_v,
            "weights":      wgt_v,
            "threshold":    self.candidate.threshold,
            "metrics":      self.metrics,
            "meta":         self.candidate.meta,
        }

    def __repr__(self) -> str:  # pragma: no cover
        m = self.metrics
        return (
            f"ZoneResult(id={self.zone_id!r}, "
            f"n={m.get('trade_count', '?')}, "
            f"avg_rr={m.get('avg_rr', 0):.3f}, "
            f"wr={m.get('winrate', 0):.2f})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# GAUSSIAN SCORING — low-level functions
# ─────────────────────────────────────────────────────────────────────────────

def compute_gaussian_score_from_candidate(
    features:  List[float],
    candidate: ZoneCandidate,
) -> float:
    """
    Score a feature vector against a ZoneCandidate.

    The score is a weighted product of per-feature Gaussian terms:

        g_k = exp( -0.5 * ((x_k - mu_k) / sigma_k)^2 )
        score = sum(w_k * g_k) / sum(w_k)

    Returns
    -------
    float in [0, 1].  Returns 0.0 if weights sum to zero.

    Parameters
    ----------
    features  : list[float] — ordered feature vector; must have at least
                len(candidate.mu) elements (extra elements are ignored)
    candidate : ZoneCandidate
    """
    keys    = list(candidate.mu.keys())
    n_keys  = len(keys)

    if len(features) < n_keys:
        raise ValueError(
            f"compute_gaussian_score_from_candidate: features has {len(features)} "
            f"elements but candidate needs {n_keys} (keys={keys})"
        )

    total_weight = 0.0
    weighted_sum = 0.0

    for i, key in enumerate(keys):
        mu_k    = candidate.mu[key]
        sigma_k = candidate.sigma[key]       # already clamped ≥ 1e-9
        w_k     = candidate.weights[key]

        z        = (features[i] - mu_k) / sigma_k
        gauss_k  = math.exp(-0.5 * z * z)

        weighted_sum  += w_k * gauss_k
        total_weight  += w_k

    if total_weight == 0.0:
        return 0.0
    return min(1.0, max(0.0, weighted_sum / total_weight))


def compute_gaussian_score(
    features: List[float],
    zone:     dict,
) -> float:
    """
    Score a feature vector against a zone dict loaded from zone_registry.json.

    This is the API consumed by ``engines.live_engine.BitNetZoneGate``.

    Zone dict format (produced by ZoneResult.to_registry_dict()):
        {
            "mu":           [float, …],   # list, parallel to feature_keys
            "sigma":        [float, …],
            "weights":      [float, …],
            "threshold":    float,
            "feature_keys": [str, …],     # optional — positional if absent
        }

    Also accepts the legacy format where mu/sigma/weights are dicts
    (keyed by feature name).

    Returns
    -------
    float in [0, 1].
    """
    mu_raw      = zone.get("mu",      [])
    sigma_raw   = zone.get("sigma",   [])
    weights_raw = zone.get("weights", [])

    # ── Handle dict-form mu/sigma/weights (legacy ZoneCandidate.to_dict()) ──
    if isinstance(mu_raw, dict):
        keys        = list(mu_raw.keys())
        mu_list     = [mu_raw[k]      for k in keys]
        sigma_list  = [max(sigma_raw.get(k, 1e-9), 1e-9) for k in keys]
        weight_list = [weights_raw.get(k, 1.0)            for k in keys]
    else:
        # List form — positional
        mu_list     = [float(v) for v in mu_raw]
        sigma_list  = [max(float(v), 1e-9) for v in sigma_raw]
        weight_list = [float(v) for v in weights_raw]

    n = len(mu_list)
    if n == 0:
        return 0.0

    # Use only the first n elements of the feature vector
    feat_slice = features[:n]
    if len(feat_slice) < n:
        return 0.0

    total_weight = sum(weight_list)
    if total_weight == 0.0:
        return 0.0

    weighted_sum = 0.0
    for i in range(n):
        z           = (feat_slice[i] - mu_list[i]) / sigma_list[i]
        weighted_sum += weight_list[i] * math.exp(-0.5 * z * z)

    return min(1.0, max(0.0, weighted_sum / total_weight))


# ─────────────────────────────────────────────────────────────────────────────
# SUBSET EVALUATOR
# Used by StabilityChecker and ForwardTester to measure zone performance.
# ─────────────────────────────────────────────────────────────────────────────

def _evaluate_subset(
    X:         List[List[float]],
    y_rr:      List[float],
    y_win:     List[int],
    candidate: ZoneCandidate,
) -> dict:
    """
    Evaluate a ZoneCandidate over a labelled feature subset.

    For each sample, score it against the candidate.  If score ≥ threshold,
    the sample is counted as a "matched trade".

    Returns
    -------
    dict with keys:
        trade_count  : int   — number of matched samples
        avg_rr       : float — mean RR of matched trades (0.0 if none)
        winrate      : float — fraction of matched trades with y_win == 1
        max_drawdown : float — maximum peak-to-trough cumulative RR drawdown
                               (0.0 if fewer than 2 matched trades)
    """
    matched_rr:  List[float] = []
    matched_win: List[int]   = []

    for i, vec in enumerate(X):
        score = compute_gaussian_score_from_candidate(vec, candidate)
        if score >= candidate.threshold:
            matched_rr.append(y_rr[i])
            matched_win.append(y_win[i])

    n = len(matched_rr)
    if n == 0:
        return {"trade_count": 0, "avg_rr": 0.0, "winrate": 0.0, "max_drawdown": 0.0}

    avg_rr  = sum(matched_rr) / n
    winrate = sum(matched_win) / n

    # Max drawdown on cumulative RR equity curve, clamped to [0, 1]
    max_drawdown = 0.0
    if n >= 2:
        peak       = 0.0
        cumulative = 0.0
        for rr in matched_rr:
            cumulative += rr
            if cumulative > peak:
                peak = cumulative
            if peak > 0:
                dd = (peak - cumulative) / peak
                if dd > max_drawdown:
                    max_drawdown = dd
        max_drawdown = min(1.0, max(0.0, max_drawdown))

    return {
        "trade_count":  n,
        "avg_rr":       round(avg_rr, 6),
        "winrate":      round(winrate, 6),
        "max_drawdown": round(max_drawdown, 6),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ZONE REGISTRY I/O
# ─────────────────────────────────────────────────────────────────────────────

def load_zone_registry(path: str) -> List[dict]:
    """
    Load ``zone_registry.json`` and return a list of zone dicts.

    Handles both registry formats:
      • ``{"zones": [...]}``  — wrapped object (produced by save_zones)
      • ``[...]``             — bare list (legacy)

    Returns an empty list on any I/O or parse error so callers can
    fail-open without an explicit try/except.

    Parameters
    ----------
    path : str — path to the JSON registry file

    Returns
    -------
    list[dict] — may be empty; never raises
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Support both "zones" key and bare dict-list format
            return data.get("zones", [])
        return []
    except Exception:
        return []


def cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a ** 2 for a in vec_a))
    mag_b = math.sqrt(sum(b ** 2 for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class BitNetSearchEngine:
    def __init__(self, index_path: str):
        self.index_path = index_path
        self.index = self._load_index()

    def _load_index(self) -> list:
        if not os.path.exists(self.index_path):
            raise FileNotFoundError(f"[BitNetSearchEngine] Index not found: {self.index_path}")
        with open(self.index_path, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("[BitNetSearchEngine] Index must be a list of entries")

        # Validate every stored vector dimension on load — fail fast on corrupt index.
        for i, entry in enumerate(data):
            stored_vec = entry.get("features")
            if stored_vec is None:
                raise ValueError(
                    f"[BitNetSearchEngine] Index entry {i} is missing 'features' key."
                )
            if not isinstance(stored_vec, list):
                raise TypeError(
                    f"[BitNetSearchEngine] Index entry {i} 'features' must be a list, "
                    f"got {type(stored_vec).__name__}."
                )
            if len(stored_vec) != CANONICAL_FEATURE_DIM:
                raise ValueError(
                    f"[BitNetSearchEngine] Index entry {i} has {len(stored_vec)} features "
                    f"but CANONICAL_FEATURE_DIM is {CANONICAL_FEATURE_DIM}. "
                    "Index was built with a different feature schema."
                )

        return data

    def search(self, features: dict, top_k: int = 5) -> list:
        """
        Search for top-k matching zones.

        Args:
            features: Raw feature dict — will be processed by extract_feature_vector.
            top_k: Number of results to return.

        Returns:
            List of dicts with keys: similarity, label, meta.

        Raises:
            ValueError: If features are invalid or vector dimension mismatches.
            AssertionError: If extracted query vector dimension != CANONICAL_FEATURE_DIM.
        """
        query_vec = extract_feature_vector(features)

        # Hard assertion — schema drift between query and extraction function is a bug.
        assert len(query_vec) == CANONICAL_FEATURE_DIM, (
            f"[BitNetSearchEngine] Query vector has {len(query_vec)} dims "
            f"but CANONICAL_FEATURE_DIM is {CANONICAL_FEATURE_DIM}."
        )

        results = []
        for entry in self.index:
            stored_vec = entry.get("features")
            # Stored vectors already validated in _load_index, so len check is a safety net.
            if len(stored_vec) != CANONICAL_FEATURE_DIM:
                raise ValueError(
                    f"[BitNetSearchEngine] Stored vector has {len(stored_vec)} dims "
                    f"but CANONICAL_FEATURE_DIM is {CANONICAL_FEATURE_DIM}."
                )
            sim = cosine_similarity(query_vec, stored_vec)
            results.append({
                "similarity": sim,
                "label": entry.get("label"),
                "meta": entry.get("meta"),
            })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def search_by_vector(self, query_vec: list, top_k: int = 5) -> list:
        """
        Search using a precomputed vector.

        Args:
            query_vec: Pre-extracted float vector of length CANONICAL_FEATURE_DIM.
            top_k: Number of results to return.

        Raises:
            ValueError: If query_vec dimension does not match CANONICAL_FEATURE_DIM.
        """
        if len(query_vec) != CANONICAL_FEATURE_DIM:
            raise ValueError(
                f"[BitNetSearchEngine] query_vec has {len(query_vec)} dims "
                f"but CANONICAL_FEATURE_DIM is {CANONICAL_FEATURE_DIM}."
            )

        results = []
        for entry in self.index:
            stored_vec = entry.get("features")
            sim = cosine_similarity(query_vec, stored_vec)
            results.append({
                "similarity": sim,
                "label": entry.get("label"),
                "meta": entry.get("meta"),
            })
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
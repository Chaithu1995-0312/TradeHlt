"""
bitnet/
=======
BitNet Parameter Range Discovery Engine

Searches feature space to find stable Gaussian filter parameters
that consistently identify profitable CRT trade setups.

NOT a price predictor. NOT a signal generator.
A TRADE FILTER: discovers which feature regions yield positive expected RR.

Modules
-------
search_engine     : Core evolutionary parameter search
zone_validator    : Accept/reject zones by quality criteria
stability_checker : Temporal split stability check (anti-overfitting)
forward_tester    : Out-of-sample validation

Quick Start
-----------
    from config_layer.rr.rr_dataset_builder import load_dataset
    from bitnet.search_engine import BitNetSearchEngine

    X, y_rr, y_win = load_dataset()
    engine = BitNetSearchEngine(X, y_rr, y_win)
    zones  = engine.run_search()
    engine.save_zones(zones)
"""

from bitnet.search_engine import BitNetSearchEngine, ZoneCandidate, ZoneResult, compute_gaussian_score_from_candidate
from bitnet.zone_validator import ZoneValidator
from bitnet.stability_checker import StabilityChecker
from bitnet.forward_tester import ForwardTester, run_forward_test

# Re-export zone gate interface from engines.live_engine so callers can use:
#   from bitnet import BitNetZoneGate, get_zone_gate
try:
    from engines.live_engine import BitNetZoneGate, get_zone_gate
    _ZONE_GATE_AVAILABLE = True
except ImportError:
    _ZONE_GATE_AVAILABLE = False

__all__ = [
    "BitNetSearchEngine",
    "ZoneCandidate",
    "ZoneResult",
    "ZoneValidator",
    "StabilityChecker",
    "ForwardTester",
    "run_forward_test",
    "compute_gaussian_score_from_candidate",
    # Zone gate (re-exported from engines.live_engine)
    "BitNetZoneGate",
    "get_zone_gate",
]

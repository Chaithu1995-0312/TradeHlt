"""Shared research probe helpers.

Extracted from scripts/analysis probe CLIs so jobs stay thin entrypoints
without importlib file-loading sibling scripts.

Pre-edit snapshots: archive/probes_extraction_phase1_2026-09-14/
"""
from research.probes.corpus import load_corpus
from research.probes.governance import FORBIDDEN_KEYS, assert_no_claim_keys
from research.probes.horizon import close_at_horizon
from research.probes.costs_path import load_cost_model, net_r
from research.probes.scoreboard import profit_factor, scoreboard_row

__all__ = [
    "load_corpus",
    "FORBIDDEN_KEYS",
    "assert_no_claim_keys",
    "close_at_horizon",
    "load_cost_model",
    "net_r",
    "profit_factor",
    "scoreboard_row",
]

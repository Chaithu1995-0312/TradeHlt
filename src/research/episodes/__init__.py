"""Opportunity Episode research substrate (protocol OE_L1).

A canonical, policy-independent post-entry observation timeline per opportunity.
Labels, events, annotations, flat tables and tensors are all DERIVED from it.

Authority: NONE (CLAUDE.md §6.5). Offline research only — nothing here runs in the
live or backtest hot path, and nothing here grants promotion or fusion rights.
"""
from research.episodes.protocol import (
    GOVERNING_POLICY,
    PROTOCOL_ID,
    V1_POLICIES,
    compute_protocol_hash,
    freeze_block,
)

__all__ = [
    "PROTOCOL_ID",
    "GOVERNING_POLICY",
    "V1_POLICIES",
    "freeze_block",
    "compute_protocol_hash",
]

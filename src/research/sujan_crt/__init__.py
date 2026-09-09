"""Sujan nested veto chain (SEM-031). Research only.

The trading rule is the conjunction in ``detect_veto_chain_entries``.
SEM-023 ``alignment_score`` is a comparison arm and never gates.
This package does **not** implement unsealed MC-SUJAN.

Spec: docs/research/sujan_veto_chain_object.md
Accepted reading: .grok/SUJAN_ACCEPTED.md
"""
from research.sujan_crt.geometry import Bar, VetoParams
from research.sujan_crt.score import alignment_score
from research.sujan_crt.vetoes import (
    SujanCandidate,
    detect_funnel_entries,
    detect_veto_chain_entries,
)

__all__ = [
    "Bar",
    "SujanCandidate",
    "VetoParams",
    "alignment_score",
    "detect_funnel_entries",
    "detect_veto_chain_entries",
]

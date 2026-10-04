"""Presence tokens for unknown / unavailable / inapplicable fields.

Doctrine (CLAUDE.md / EPISTEMIC_INTEGRITY): write UNKNOWN, never invent.
"""

from __future__ import annotations

from enum import Enum


class Presence(str, Enum):
    """How a field value should be interpreted."""

    PRESENT = "PRESENT"
    UNKNOWN = "UNKNOWN"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"

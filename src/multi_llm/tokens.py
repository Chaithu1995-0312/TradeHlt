"""
tokens.py — honest token *estimate* (no external tokenizer dependency).

A heuristic (~4 chars/token) is enough to bound context packs so they fit a model's window.
Swap in a real tokenizer only if budgets actually bite (see plan: out of scope for now).
"""
from __future__ import annotations

DEFAULT_BUDGET = 12_000  # ~tokens; a comfortable per-pack ceiling for a single upload


def estimate_tokens(text: str) -> int:
    """Rough token count. Deliberately an estimate, not exact."""
    return max(1, len(text) // 4)

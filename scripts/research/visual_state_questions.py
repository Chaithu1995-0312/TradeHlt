"""Frozen question text + engine-to-visual maps for visual CRT state fidelity.

Pre-registration: docs/research/preregistration-visual-crt-state-fidelity.md
This module is the single copy the sampler, scorer, HTML, and tests import.
Do not paraphrase the question strings — the wording is the instrument.
"""
from __future__ import annotations

# Minority-class floor. Cells thinner than this are INSUFFICIENT, never a null.
MIN_CELL_N = 15
CONTEXT_BARS = 48
MIN_PX_PER_CANDLE = 8.0
DEFAULT_SEED = 20260818

# Banned on every labeling surface (HTML, brief is separately curated, filenames).
# CRT vocabulary, engine fields, instrument, answer-key path.
BANNED_SURFACE_TOKENS = (
    "sweep",
    "displacement",
    "expansion",
    "retest",
    "shadow_pending",
    "crtstate",
    "h_ref",
    "l_ref",
    "state_to",
    "state_from",
    "xauusd",
    "manifest.json",
    "sample_manifest",
    "tradingview_state",
)

QUESTIONS = (
    {
        "id": "v1",
        "text": (
            "At the marked bar, did price spike beyond a prior extreme "
            "and then close back inside?"
        ),
        "options": (("above", "Above"), ("below", "Below"), ("neither", "Neither")),
        "ordinal": True,
        "codes": {"below": -1, "neither": 0, "above": 1},
    },
    {
        "id": "v2",
        "text": "Is the marked bar a strong directional push away from that spike?",
        "options": (("up", "Up"), ("down", "Down"), ("neither", "Neither")),
        "ordinal": True,
        "codes": {"down": -1, "neither": 0, "up": 1},
    },
    {
        "id": "v3",
        "text": "Does the marked bar carry that push further in the same direction?",
        "options": (("yes", "Yes"), ("no", "No")),
        "ordinal": False,
        "codes": {"no": 0, "yes": 1},
    },
    {
        "id": "v4",
        "text": "Has price come back close to the level it originally broke?",
        "options": (("yes", "Yes"), ("no", "No")),
        "ordinal": False,
        "codes": {"no": 0, "yes": 1},
    },
)


def engine_to_visual(state_to: str | None, direction: str | None) -> dict[str, str]:
    """Map one engine transition onto the four visual answers.

    SWEEP SHORT = spike through a high (Above). SWEEP LONG = spike through a
    low (Below). DISPLACEMENT follows F-074 (LONG = Up, SHORT = Down).
    """
    st = (state_to or "").upper()
    d = (direction or "").upper()
    v1 = "neither"
    v2 = "neither"
    v3 = "no"
    v4 = "no"
    if st == "SWEEP":
        if d == "SHORT":
            v1 = "above"
        elif d == "LONG":
            v1 = "below"
    elif st == "DISPLACEMENT":
        if d == "LONG":
            v2 = "up"
        elif d == "SHORT":
            v2 = "down"
    elif st == "EXPANSION":
        v3 = "yes"
    elif st == "RETEST":
        v4 = "yes"
    return {"v1": v1, "v2": v2, "v3": v3, "v4": v4}


def question_by_id(qid: str) -> dict:
    for q in QUESTIONS:
        if q["id"] == qid:
            return q
    raise KeyError(qid)

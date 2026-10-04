"""story_registry.py — the single collection point for every registered StorySpec.

Adding a story = adding a StorySpec to its family module under stories/ (geometry in CODE, D-23).
"""
from __future__ import annotations

from research.synthetic.stories import ALL_STORIES
from research.synthetic.story_spec import StorySpec


def all_stories() -> list[StorySpec]:
    return list(ALL_STORIES)


def stories_by_id() -> dict[str, StorySpec]:
    out: dict[str, StorySpec] = {}
    for s in ALL_STORIES:
        if s.id in out:
            raise ValueError(f"duplicate story id: {s.id}")
        out[s.id] = s
    return out

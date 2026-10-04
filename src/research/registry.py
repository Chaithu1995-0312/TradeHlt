"""registry.py — hypothesis plugin registry (mirrors src/agent/tool_registry.py).

A new market-behavior hypothesis (or control) becomes available by registering one
instance — no core edits, no control-flow branch on what *kind* of behavior it is. The
registry stores instances (not classes) so parametrized variants — e.g. random_baseline
uniform 50/50 vs biased 70/30 — coexist under distinct names.

The registry is intentionally behavior-blind: it never inspects `.family`. Anything that
implements the Hypothesis protocol (name, family, economic_rationale, detect()) is
treated identically.
"""

from __future__ import annotations

from typing import Callable

from research.contracts import Hypothesis

HYPOTHESIS_REGISTRY: dict[str, Hypothesis] = {}


def register_hypothesis(obj: Hypothesis | type | None = None) -> Callable | Hypothesis:
    """Register a hypothesis instance, or act as a zero-arg class decorator.

    Usage:
        register_hypothesis(RandomBaseline(name="random_uniform", long_prob=0.5))

        @register_hypothesis            # class with a no-arg constructor
        class ExpansionBreakout: ...
    """
    if obj is None:
        return register_hypothesis

    instance = obj() if isinstance(obj, type) else obj

    if not isinstance(instance, Hypothesis):
        raise TypeError(
            f"register_hypothesis: {instance!r} does not implement the Hypothesis "
            "protocol (needs name, family, economic_rationale, detect())"
        )

    name = instance.name
    existing = HYPOTHESIS_REGISTRY.get(name)
    if existing is not None and existing is not instance:
        raise ValueError(f"register_hypothesis: duplicate hypothesis name '{name}'")
    HYPOTHESIS_REGISTRY[name] = instance
    return obj if isinstance(obj, type) else instance


def get_hypothesis(name: str) -> Hypothesis:
    if name not in HYPOTHESIS_REGISTRY:
        raise KeyError(f"unknown hypothesis '{name}'. Registered: {sorted(HYPOTHESIS_REGISTRY)}")
    return HYPOTHESIS_REGISTRY[name]


def all_hypotheses() -> list[Hypothesis]:
    return list(HYPOTHESIS_REGISTRY.values())

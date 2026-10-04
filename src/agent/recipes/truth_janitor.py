"""TruthJanitor seed recipe — hygiene checks then rollup pack."""

from __future__ import annotations

from typing import List

from agent.plan_compiler import ToolStep, _s


def truth_seed_steps() -> List[ToolStep]:
    """
    Deterministic Truth Janitor plan (read-first, pack last).

    1. construction protocol check
    2. feature math ownership lint
    3. script census summary
    4. citation floor (pytest)
    5. hygiene pack under results/hygiene/
    """
    return [
        _s("truth.construction_check"),
        _s("truth.feature_math_lint"),
        _s("truth.script_census"),
        _s("truth.citation_floor"),
        _s("truth.hygiene_pack"),
    ]

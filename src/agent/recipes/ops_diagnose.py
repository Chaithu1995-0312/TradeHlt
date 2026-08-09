"""OpsDoctor seed recipe — fixed read-only chain + incident pack."""

from __future__ import annotations

from typing import List

from agent.plan_compiler import ToolStep, _s


def ops_seed_steps(instrument: str = "") -> List[ToolStep]:
    """
    Deterministic Ops Doctor plan.

    1. throughput snapshot (logs/results)
    2. funnel diagnostic (optional run-dir from context)
    3. fail-reason summary (best-effort)
    4. collector tail
    5. write incident pack under results/incidents/
    """
    inst = instrument or ""
    return [
        _s("ops.throughput_snapshot", instrument=inst),
        _s("ops.funnel_diagnose", instrument=inst),
        _s("ops.fail_reasons", instrument=inst),
        _s("collector.tail", n_rows=30),
        _s("ops.incident_pack", instrument=inst),
    ]

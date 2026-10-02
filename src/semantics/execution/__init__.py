"""Decision/Execution layer (Semantic OS v2 slice 3): size, admission, fill, approval,
position, exit schedule and rules, carry, position result (DEX-01..09).

Never changes a thesis, a role or a market object (I-3, I-10). Nothing here runs the CRT engine
or the live rail; verdicts are supplied by the caller.
"""

from semantics.execution.approval import APPROVAL, Approval, approved, from_crt_reset, from_ultron
from semantics.execution.carry import CARRY, Carry, carry, rollover_dates
from semantics.execution.fill import FILL, Fill, fill
from semantics.execution.portfolio import PORTFOLIO_ADMISSION, PORTFOLIO_CAP, Admission, admit
from semantics.execution.position import (
    EXIT_RULE, EXIT_SCHEDULE, POSITION, ExitReason, ExitRule, ExitSchedule, Position,
    exit_rule, exit_schedule, replay_position,
)
from semantics.execution.result import POSITION_RESULT, PositionResult, position_result
from semantics.execution.size import POSITION_SIZE, PositionSize, position_size

__all__ = [
    "APPROVAL", "Approval", "approved", "from_crt_reset", "from_ultron",
    "CARRY", "Carry", "carry", "rollover_dates",
    "FILL", "Fill", "fill",
    "PORTFOLIO_ADMISSION", "PORTFOLIO_CAP", "Admission", "admit",
    "EXIT_RULE", "EXIT_SCHEDULE", "POSITION", "ExitReason", "ExitRule", "ExitSchedule", "Position",
    "exit_rule", "exit_schedule", "replay_position",
    "POSITION_RESULT", "PositionResult", "position_result",
    "POSITION_SIZE", "PositionSize", "position_size",
]

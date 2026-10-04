"""oracle — outcome-first (SEM-018) per-bar labelling under the SEM-017 exit geometry.

Research-only. Grants no production authority: nothing here is imported by src/core,
src/engines, src/runtime or any production config path.
"""

from research.oracle.multi_tp_walk import (
    OracleOutcome,
    is_stop_exit,
    multi_tp_walk,
)
from research.oracle.reference_walker import reference_walk

__all__ = ["OracleOutcome", "multi_tp_walk", "reference_walk", "is_stop_exit"]

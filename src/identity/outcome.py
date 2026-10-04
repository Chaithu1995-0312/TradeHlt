"""L5 outcome record builder.

WRITE-TIME only. Does not import TradeLib, crt_engine, or any walk kernel.
Callers supply the already-evaluated snapshot. Identity Check never uses this
module to fill missing fields.
"""
from __future__ import annotations

from typing import Any, Mapping

from identity.tokens import (
    COST_MODEL_IDS,
    ENGINE_CLOSE_COST,
    ENGINE_CLOSE_FILL,
    ENGINE_CLOSE_WALK,
    FILL_MODEL_IDS,
    L0_PK,
    L4_EXTRA,
    L5_BASIS,
    L5_PAYLOAD,
    WALK_KERNELS,
)


class L5WriteError(ValueError):
    """Caller omitted a required L5 identity field. Not a load-path status."""


def build_l5_record(
    l4: Mapping[str, Any],
    *,
    walk_kernel: str,
    cost_model_id: str,
    fill_model_id: str,
    y_R_gross: float,
    mfe: float,
    mae: float,
    duration_bars: int,
    exit_reason: str,
) -> dict[str, Any]:
    """Assemble a Class B L5 record. Frozen PK = L4 PK + walk + cost + fill.

    Raises L5WriteError instead of substituting a default cost/fill/walk.
    """
    if not walk_kernel:
        raise L5WriteError("walk_kernel must be explicitly declared; not inferred")
    if not cost_model_id:
        raise L5WriteError("cost_model_id cannot be null, empty, or inferred")
    if not fill_model_id:
        raise L5WriteError("fill_model_id cannot be null, empty, or inferred")
    if walk_kernel not in WALK_KERNELS:
        raise L5WriteError(f"walk_kernel={walk_kernel!r} not in closed vocabulary")
    if cost_model_id not in COST_MODEL_IDS:
        raise L5WriteError(f"cost_model_id={cost_model_id!r} not in closed vocabulary")
    if fill_model_id not in FILL_MODEL_IDS:
        raise L5WriteError(f"fill_model_id={fill_model_id!r} not in closed vocabulary")
    if not exit_reason:
        raise L5WriteError("exit_reason must be the engine close token, not empty")
    missing_l4 = [k for k in L0_PK + L4_EXTRA if l4.get(k) in (None, "")]
    if missing_l4:
        raise L5WriteError(f"L4 PK incomplete: {missing_l4}")
    rec = {k: l4[k] for k in L0_PK + L4_EXTRA}
    rec["walk_kernel"] = walk_kernel
    rec["cost_model_id"] = cost_model_id
    rec["fill_model_id"] = fill_model_id
    rec["y_R_gross"] = float(y_R_gross)
    rec["mfe"] = float(mfe)
    rec["mae"] = float(mae)
    rec["duration_bars"] = int(duration_bars)
    rec["exit_reason"] = str(exit_reason)
    for key in L5_BASIS + L5_PAYLOAD:
        if rec.get(key) in (None, ""):
            raise L5WriteError(f"missing required L5 field {key}")
    return rec


def engine_close_basis() -> dict[str, str]:
    """Named tokens for CRTEngine-closed trades. Bound on write, never on load."""
    return {
        "walk_kernel": ENGINE_CLOSE_WALK,
        "cost_model_id": ENGINE_CLOSE_COST,
        "fill_model_id": ENGINE_CLOSE_FILL,
    }

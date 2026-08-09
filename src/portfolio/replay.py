"""replay.py — read-only shadow replay of PortfolioAllocator over a historical trade ledger.

WHY THIS EXISTS (F-013)
    `PortfolioAllocator` is fully built and 25-tested but has NO caller on the live spine — the
    live path runs UltronRiskGate's own per-trade sizing, so cross-instrument exposure/correlation
    limits are never exercised. This harness streams an EXISTING closed-trade ledger through
    `allocate → open_position → close_position` and reports what the allocator WOULD have done.
    Pure shadow: it opens no order, touches no config, and earns no authority.

ISOLATION (enforced by tests/portfolio/test_replay_allocator.py)
    Imports stdlib + `src.portfolio.*` ONLY — never `src.runtime`, `src.inout`, the feature
    pipeline, or the research spine. It cannot influence a live decision even by accident.

DETERMINISM
    No RNG, no wall-clock. The event stream is a stable sort of (index, CLOSE-before-OPEN), so the
    same ledger yields a byte-identical `ReplayResult`.

PnL CONVENTION
    `risk` is a fraction of capital (0.005 = 0.5%); `realized_r` is the trade's R-multiple
    (1R == the risked amount). Per-trade capital-fraction PnL = risk * realized_r. The replay sums
    additively (no compounding) — a shadow comparison, not an equity-curve claim.

CONTRACT (no defaults, no fallbacks — repo doctrine)
    Every record MUST carry trade_id, symbol, open_index, close_index, confidence, realized_r;
    a missing field or close_index < open_index RAISES. Optional passthrough: rr, regime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from src.portfolio.allocator import PortfolioAllocator

_REQUIRED = ("trade_id", "symbol", "open_index", "close_index", "confidence", "realized_r")

# Stable reason codes (the raw allocator reason embeds floats; bucket on the mechanism).
_CODE_ALLOCATE = "ALLOCATE"
_CODE_REJECT_CAPACITY = "REJECT_CAPACITY"
_CODE_REJECT_TRIMMED_ZERO = "REJECT_TRIMMED_ZERO"
_CODE_REJECT_OTHER = "REJECT_OTHER"


def _reason_code(action: str, reason: str) -> str:
    if action == "ALLOCATE":
        return _CODE_ALLOCATE
    if "at max risk capacity" in reason:
        return _CODE_REJECT_CAPACITY
    if "trimmed risk is zero" in reason:
        return _CODE_REJECT_TRIMMED_ZERO
    return _CODE_REJECT_OTHER


@dataclass(frozen=True)
class ReplayResult:
    """The outcome of one shadow replay. SHADOW ONLY — no authority."""
    n_records: int
    n_allocated: int
    n_rejected: int
    reason_histogram: dict            # reason_code -> count
    allocated_realized_r: tuple       # realized R of ALLOCATED trades (feed to metrics_oracle)
    allocator_pnl: float              # Σ risk*realized_r over allocated (capital fraction)
    take_every_base_risk: float       # policy.base_risk used for the naive baseline
    take_every_pnl: float             # base_risk * Σ realized_r over ALL records (the null policy)
    decisions: tuple                  # per-trade decision dicts, input order
    allocator_config: dict            # policy caps snapshot (provenance)

    def to_dict(self) -> dict:
        return {
            "authority": "SHADOW_REPLAY_NO_AUTHORITY",
            "n_records": self.n_records, "n_allocated": self.n_allocated,
            "n_rejected": self.n_rejected, "reason_histogram": dict(self.reason_histogram),
            "allocated_realized_r": list(self.allocated_realized_r),
            "allocator_pnl": self.allocator_pnl,
            "take_every_base_risk": self.take_every_base_risk,
            "take_every_pnl": self.take_every_pnl,
            "decisions": [dict(d) for d in self.decisions],
            "allocator_config": dict(self.allocator_config),
        }


def _validate(rec: Mapping, i: int) -> None:
    missing = [k for k in _REQUIRED if k not in rec]
    if missing:
        raise ValueError(f"record[{i}] missing required field(s): {missing}")
    if int(rec["close_index"]) < int(rec["open_index"]):
        raise ValueError(
            f"record[{i}] close_index {rec['close_index']} < open_index {rec['open_index']}"
        )


def replay_allocator(records: Sequence[Mapping], *,
                     allocator: PortfolioAllocator | None = None) -> ReplayResult:
    """Replay a closed-trade ledger through PortfolioAllocator. Read-only, deterministic.

    Args:
        records: chronologically-orderable trade records (see module CONTRACT).
        allocator: optional pre-configured allocator; a fresh default is built when None.
                   A fresh instance is required per run — the tracker carries state.
    """
    alloc = allocator if allocator is not None else PortfolioAllocator()

    for i, rec in enumerate(records):
        _validate(rec, i)

    # Build the interleaved OPEN/CLOSE event stream. CLOSE sorts before OPEN at the same index so
    # freed capacity is available to a same-index open (deterministic tie-break; kind 0 < 1).
    events = []
    for i, rec in enumerate(records):
        events.append((int(rec["open_index"]), 1, i))    # OPEN  (kind 1)
        events.append((int(rec["close_index"]), 0, i))   # CLOSE (kind 0)
    events.sort()

    taken_risk: dict[int, float] = {}                    # record idx -> allocated risk
    decisions: list[dict] = [None] * len(records)        # type: ignore[list-item]
    hist: dict[str, int] = {}

    for _idx, kind, i in events:
        rec = records[i]
        if kind == 1:                                    # OPEN
            signal = {"symbol": rec["symbol"], "confidence": float(rec["confidence"])}
            if "rr" in rec:
                signal["rr"] = rec["rr"]
            if "regime" in rec:
                signal["regime"] = rec["regime"]
            res = alloc.allocate(signal)
            code = _reason_code(res["action"], res["reason"])
            hist[code] = hist.get(code, 0) + 1
            risk = float(res.get("risk", 0.0))
            allocated = res["action"] == "ALLOCATE" and risk > 0.0
            if allocated:
                alloc.open_position({"trade_id": rec["trade_id"], "symbol": rec["symbol"],
                                     "risk": risk})
                taken_risk[i] = risk
            decisions[i] = {
                "trade_id": rec["trade_id"], "symbol": rec["symbol"],
                "action": res["action"], "reason_code": code, "reason": res["reason"],
                "allocated_risk": risk if allocated else 0.0,
                "realized_r": float(rec["realized_r"]),
                "pnl_contrib": (risk * float(rec["realized_r"])) if allocated else None,
            }
        else:                                            # CLOSE
            if i in taken_risk:
                alloc.close_position(rec["trade_id"])

    allocated_r = tuple(float(records[i]["realized_r"]) for i in sorted(taken_risk))
    allocator_pnl = sum(taken_risk[i] * float(records[i]["realized_r"]) for i in taken_risk)
    base_risk = float(alloc.policy.base_risk)
    take_every_pnl = base_risk * sum(float(r["realized_r"]) for r in records)

    return ReplayResult(
        n_records=len(records),
        n_allocated=len(taken_risk),
        n_rejected=len(records) - len(taken_risk),
        reason_histogram=hist,
        allocated_realized_r=allocated_r,
        allocator_pnl=allocator_pnl,
        take_every_base_risk=base_risk,
        take_every_pnl=take_every_pnl,
        decisions=tuple(decisions),
        allocator_config={
            "max_portfolio_risk": alloc.policy.max_portfolio_risk,
            "max_per_trade": alloc.policy.max_per_trade,
            "base_risk": base_risk,
        },
    )

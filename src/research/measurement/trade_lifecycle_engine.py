"""TradeLifecycleEngine v0 — MC-JOINT-01 measurement emitter.

Emit-only. Does not invent exit semantics. Wraps:
  Y_scanner  <- opportunity_scanner._simulate (trail_mult=0.5)
  Y_oracle   <- forward_walk(exit_model=intrabar_fixed)
  Y_joint    <- six frozen joint states
  authority_outcome <- path / Y_oracle + y_R_net (F-022)

Mismatch = state membership, not error.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from research.contracts import Outcome, Signal
from research.measurement.forward_walk import forward_walk

# Frozen MC-JOINT-01 state set — do not extend without a new census.
JOINT_STATES = frozenset({
    "BOTH_SL",
    "BOTH_TP",
    "BOTH_TIMEOUT",
    "JOINT_STATE_SL_TP",
    "JOINT_STATE_TP_SL",
    "JOINT_STATE_SL_TIMEOUT",
})

CONTRACT_ID = "MC-JOINT-01"
DEFAULT_TRAIL_MULT = 0.5
DEFAULT_COST_BPS = 12.0  # clean_labels protocol COST_BPS; diagnostic net only


def _norm_terminal(outcome: str) -> str:
    o = str(outcome).upper().strip()
    if o in {"TP_HIT", "TP", "TP1", "TP2"}:
        return "TP"
    if o in {"SL_HIT", "SL", "STOP"}:
        return "SL"
    if o in {"TIMEOUT", "EXPIRED"}:
        return "TIMEOUT"
    raise ValueError(f"unknown terminal outcome {outcome!r}")


def joint_state_id(y_scanner: str, y_oracle: str) -> str:
    ys, yo = _norm_terminal(y_scanner), _norm_terminal(y_oracle)
    if ys == yo:
        state = f"BOTH_{ys}"
    else:
        state = f"JOINT_STATE_{ys}_{yo}"
    if state not in JOINT_STATES:
        # Census-closed set: surface rather than invent a seventh state.
        raise ValueError(
            f"joint state {state} outside MC-JOINT-01 frozen set {sorted(JOINT_STATES)}"
        )
    return state


def _exit_mechanism(*, walk: str, outcome: str, rr: float) -> str:
    """Tag under the state — does not expand the six-state ontology."""
    term = _norm_terminal(outcome)
    if term == "TP":
        return "TP_HIT"
    if term == "TIMEOUT":
        return "TIMEOUT"
    # SL branch
    if walk == "scanner" and rr > 0:
        return "TRAIL_HIT"
    return "FIXED_SL_HIT"


def _risk(entry: float, sl: float) -> float:
    r = abs(float(entry) - float(sl))
    if r <= 0:
        raise ValueError(f"non-positive risk |entry-sl|={r}")
    return r


def _side_to_direction(side: str) -> str:
    s = str(side).lower().strip()
    if s in {"long", "buy", "l"}:
        return "long"
    if s in {"short", "sell", "s"}:
        return "short"
    raise ValueError(f"bad side {side!r}")


@dataclass(frozen=True)
class Bar:
    """Minimal OHLC bar for measurement walks."""

    high: float
    low: float
    close: float
    index: int
    open: float | None = None
    timestamp: Any = None


@dataclass(frozen=True)
class WalkResult:
    outcome: str          # TP_HIT | SL_HIT | TIMEOUT
    terminal: str         # TP | SL | TIMEOUT
    rr: float
    duration: int
    mfe: float
    mae: float
    exit_mechanism: str
    walk: str             # scanner | oracle


@dataclass(frozen=True)
class AuthorityOutcome:
    source: str
    path_outcome: str
    y_R_net: float


@dataclass(frozen=True)
class LifecycleMeasurement:
    """MC-JOINT-01 emit surface."""

    contract_id: str
    Y_scanner: str
    Y_oracle: str
    Y_joint: str
    authority_outcome: AuthorityOutcome
    rr_scanner: float
    rr_oracle: float
    duration_scanner: int
    duration_oracle: int
    mfe_scanner: float
    mae_scanner: float
    mfe_oracle: float
    mae_oracle: float
    exit_mechanism_scanner: str
    exit_mechanism_oracle: str
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _bars_to_df(bars: Sequence[Bar | Mapping[str, Any]]):
    import pandas as pd

    rows = []
    for b in bars:
        if isinstance(b, Bar):
            rows.append({"high": b.high, "low": b.low, "close": b.close, "open": b.open})
        else:
            rows.append({
                "high": float(b["high"]),
                "low": float(b["low"]),
                "close": float(b["close"]),
                "open": float(b["open"]) if b.get("open") is not None else None,
            })
    return pd.DataFrame(rows)


def _run_scanner(
    *,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    forward_bars: Sequence[Bar | Mapping[str, Any]],
    trail_mult: float,
) -> WalkResult:
    # Local import keeps scripts/ off the default research import graph until emit.
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    scripts = root / "scripts" / "research"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from opportunity_scanner import _simulate  # type: ignore

    risk = _risk(entry, sl)
    df = _bars_to_df(forward_bars)
    raw = _simulate(direction, entry, sl, tp, df, risk, trail_mult=trail_mult)
    outcome = str(raw["outcome"])
    rr = float(raw["rr_achieved"])
    return WalkResult(
        outcome=outcome,
        terminal=_norm_terminal(outcome),
        rr=rr,
        duration=int(raw["duration_candles"]),
        mfe=float(raw["mfe"]),
        mae=float(raw["mae"]),
        exit_mechanism=_exit_mechanism(walk="scanner", outcome=outcome, rr=rr),
        walk="scanner",
    )


def _run_oracle(
    *,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    forward_bars: Sequence[Bar | Mapping[str, Any]],
    max_forward: int,
) -> WalkResult:
    risk = _risk(entry, sl)
    reward = abs(float(tp) - float(entry))
    # Signal expresses SL/TP as ATR multiples; set atr=risk so sl_atr_mult=1, tp_atr_mult=R.
    sig = Signal(
        instrument="MEASUREMENT",
        timestamp=datetime.now(timezone.utc),
        entry_index=0,
        direction=direction,
        entry=float(entry),
        sl_atr_mult=1.0,
        tp_atr_mult=(reward / risk) if risk > 0 else 0.0,
        atr=float(risk),
        meta={"absolute_sl": float(sl), "absolute_tp": float(tp)},
    )

    class _B:
        __slots__ = ("high", "low", "close", "open", "index")

        def __init__(self, high, low, close, index, open_=None):
            self.high = float(high)
            self.low = float(low)
            self.close = float(close)
            self.open = float(open_) if open_ is not None else None
            self.index = int(index)

    future = []
    for i, b in enumerate(forward_bars, start=1):
        if isinstance(b, Bar):
            future.append(_B(b.high, b.low, b.close, i, b.open))
        else:
            future.append(_B(b["high"], b["low"], b["close"], i, b.get("open")))

    oc: Outcome = forward_walk(
        sig, future, max_forward=max_forward, exit_model="intrabar_fixed"
    )
    outcome = str(oc.outcome)
    rr = float(oc.rr_achieved)
    return WalkResult(
        outcome=outcome,
        terminal=_norm_terminal(outcome),
        rr=rr,
        duration=int(oc.duration_candles),
        mfe=float(oc.mfe),
        mae=float(oc.mae),
        exit_mechanism=_exit_mechanism(walk="oracle", outcome=outcome, rr=rr),
        walk="oracle",
    )


def measure(
    *,
    entry: float,
    sl: float,
    tp: float,
    side: str,
    forward_bars: Sequence[Bar | Mapping[str, Any]],
    trail_mult: float = DEFAULT_TRAIL_MULT,
    max_forward: int = 40,
    cost_bps: float = DEFAULT_COST_BPS,
    meta: Mapping[str, Any] | None = None,
) -> LifecycleMeasurement:
    """Emit MC-JOINT-01 measurement objects for one trade geometry + forward bars.

    `forward_bars` must be bars *after* the decision/entry bar (no lookahead),
    matching opportunity_scanner / forward_walk conventions.
    """
    direction = _side_to_direction(side)
    risk = _risk(entry, sl)

    scanner = _run_scanner(
        direction=direction,
        entry=float(entry),
        sl=float(sl),
        tp=float(tp),
        forward_bars=forward_bars,
        trail_mult=trail_mult,
    )
    oracle = _run_oracle(
        direction=direction,
        entry=float(entry),
        sl=float(sl),
        tp=float(tp),
        forward_bars=forward_bars,
        max_forward=max_forward,
    )

    y_joint = joint_state_id(scanner.terminal, oracle.terminal)
    cost_r = (float(cost_bps) / 10_000.0) * float(entry) / risk
    y_r_net = float(oracle.rr) - cost_r

    return LifecycleMeasurement(
        contract_id=CONTRACT_ID,
        Y_scanner=scanner.terminal,
        Y_oracle=oracle.terminal,
        Y_joint=y_joint,
        authority_outcome=AuthorityOutcome(
            source="path",
            path_outcome=oracle.terminal,
            y_R_net=round(y_r_net, 6),
        ),
        rr_scanner=scanner.rr,
        rr_oracle=oracle.rr,
        duration_scanner=scanner.duration,
        duration_oracle=oracle.duration,
        mfe_scanner=scanner.mfe,
        mae_scanner=scanner.mae,
        mfe_oracle=oracle.mfe,
        mae_oracle=oracle.mae,
        exit_mechanism_scanner=scanner.exit_mechanism,
        exit_mechanism_oracle=oracle.exit_mechanism,
        meta={
            "trail_mult": trail_mult,
            "oracle_exit_model": "intrabar_fixed",
            "cost_bps": cost_bps,
            "risk": risk,
            "direction": direction,
            **dict(meta or {}),
        },
    )


__all__ = [
    "Bar",
    "LifecycleMeasurement",
    "AuthorityOutcome",
    "JOINT_STATES",
    "CONTRACT_ID",
    "joint_state_id",
    "measure",
]

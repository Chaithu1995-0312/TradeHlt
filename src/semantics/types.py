"""Closed vocabularies of the meaning plane (SEMANTIC_OS_V2_MEANING_PLANE.md §3, §7)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Layer(str, Enum):
    GEOMETRY = "GEOMETRY"
    MARKET = "MARKET"
    TRADING = "TRADING"
    DECISION_EXECUTION = "DECISION_EXECUTION"


#: I-12: a concept may only take inputs from its own layer or a lower one.
LAYER_RANK: dict[Layer, int] = {
    Layer.GEOMETRY: 0,
    Layer.MARKET: 1,
    Layer.TRADING: 2,
    Layer.DECISION_EXECUTION: 3,
}


class Kind(str, Enum):
    PRIMITIVE = "PRIMITIVE"
    LEVEL = "LEVEL"
    ZONE = "ZONE"
    EVENT = "EVENT"
    CONDITION = "CONDITION"
    EPISODE = "EPISODE"
    EPISODE_STAGE = "EPISODE_STAGE"
    MEASUREMENT = "MEASUREMENT"
    THESIS = "THESIS"
    OBJECTIVE = "OBJECTIVE"
    INVALIDATION = "INVALIDATION"
    ENTRY = "ENTRY"
    STOP = "STOP"
    TARGET = "TARGET"
    COST = "COST"
    OUTCOME = "OUTCOME"
    SIGNAL = "SIGNAL"
    DECISION = "DECISION"
    EXECUTION_SPEC = "EXECUTION_SPEC"
    EXECUTION = "EXECUTION"


class ContractStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    FROZEN = "FROZEN"


class Evidence(str, Enum):
    REPO = "REPO"
    USER_DECISION = "USER_DECISION"
    TK = "TK"   # trading knowledge only — never sufficient for ACCEPTED


class Side(str, Enum):
    """Which side of price a level sits on. +1 = UPPER in every signed encoding."""
    UPPER = "UPPER"
    LOWER = "LOWER"


class Bias(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


def implied_bias_of_sweep(swept_side: Side) -> Bias:
    """A swept UPPER level implies SHORT; a swept LOWER level implies LONG."""
    return Bias.SHORT if swept_side is Side.UPPER else Bias.LONG


class LevelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SWEPT = "SWEPT"
    BROKEN = "BROKEN"
    EXPIRED = "EXPIRED"


class ZoneStatus(str, Enum):
    ACTIVE = "ACTIVE"
    TOUCHED = "TOUCHED"
    BROKEN = "BROKEN"
    FLIPPED = "FLIPPED"
    REFOUNDED = "REFOUNDED"   # MKT-Z01 on MKT-E12. FILLED is PROPOSED and is not a member.


class TerminalAuthority(str, Enum):
    MARKET = "MARKET"
    OBSERVATION = "OBSERVATION"
    PRODUCER = "PRODUCER"
    DECISION = "DECISION"
    EXECUTION = "EXECUTION"


class TerminalClass(str, Enum):
    FAILED = "FAILED"                    # MARKET: thesis falsified (e.g. 50% retrace)
    SPENT = "SPENT"                      # MARKET: move completed without entry (1.618 extension)
    EXPIRED = "EXPIRED"                  # MARKET: clock rolled over / PRODUCER: patience (TTL)
    AVAILABILITY_LAPSE = "AVAILABILITY_LAPSE"   # OBSERVATION
    CONSTRUCTION = "CONSTRUCTION"        # PRODUCER: re-seed / internal consistency
    FILTERED = "FILTERED"                # DECISION
    POSITION_CLOSED = "POSITION_CLOSED"  # EXECUTION
    BUILD_FAILED = "BUILD_FAILED"        # EXECUTION


class Bar(Protocol):
    """Anything bar-shaped. `config_layer.crt_engine_v2.Candle` satisfies it; tests use `OhlcBar`."""
    open: float
    high: float
    low: float
    close: float
    index: int


@dataclass(frozen=True)
class OhlcBar:
    """Test and caller bar. Not a concept id."""
    open: float
    high: float
    low: float
    close: float
    index: int
    timestamp: object = None

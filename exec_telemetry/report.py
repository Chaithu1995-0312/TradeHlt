"""
report — the read-only Operational Reality report over captured ExecutionEvents.

OPERATIONAL-ONLY: summarizes execution quality (fill rate, retcode failure modes, slippage,
latency) per broker. It NEVER computes profit / expectancy / win-rate / R — those belong to the
truth + insight engines. `execution telemetry → HUMAN`, never `→ decisions`.

Composes `analytics.metrics_oracle` (median/percentile) — no new statistics here. Same sufficiency
discipline as the v0.6 insight layer: below `min_n` a broker reports raw counts but makes NO
distributional claim (slippage/latency distributions are None).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from analytics.metrics_oracle import median, percentile  # type: ignore

DEFAULT_MIN_N = 30

_OPERATIONAL_ONLY = ("EXECUTION QUALITY (slippage / latency / retcode) — "
                     "NOT expectancy / edge / strategy")


class SufficiencyStatus(Enum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class Distribution:
    n: int
    median: "float | None"
    p90: "float | None"
    worst: "float | None"     # max magnitude (slippage: most-adverse points; latency: max ms)


@dataclass(frozen=True)
class BrokerExecReport:
    broker_key: str           # "company|server|mm<margin_mode>"
    company: str
    server: str
    margin_mode: int
    n: int                    # order-send attempts observed
    min_n: int
    status: SufficiencyStatus
    fill_success_rate: "float | None"   # DONE / attempts (count-based; always reported)
    retcode_histogram: "dict[str, int]"
    slippage_adverse_points: "Distribution | None"   # side-normalized (+ = adverse); None if INSUFFICIENT
    latency_ms: "Distribution | None"                # None if INSUFFICIENT
    filling_modes: "tuple[str, ...]"
    symbols: "tuple[str, ...]"


@dataclass(frozen=True)
class ExecReport:
    min_n: int
    operational_only: str
    brokers: "tuple[BrokerExecReport, ...]"


def _row(e) -> dict:
    return e.to_dict() if hasattr(e, "to_dict") else dict(e)


def _dist(values: "list[float]", *, sufficient: bool) -> "Distribution | None":
    if not sufficient or not values:
        return None
    return Distribution(
        n=len(values),
        median=median(values),
        p90=percentile(values, 90.0),
        worst=max(values),
    )


def build_exec_report(events, *, min_n: int = DEFAULT_MIN_N) -> ExecReport:
    """Group ExecutionEvents by broker (company|server|margin_mode) → operational summary."""
    groups: "dict[tuple, list[dict]]" = defaultdict(list)
    for e in events:
        r = _row(e)
        groups[(r["company"], r["server"], int(r["margin_mode"]))].append(r)

    brokers: list[BrokerExecReport] = []
    for (company, server, mm), rows in sorted(groups.items()):
        n = len(rows)
        status = SufficiencyStatus.SUFFICIENT if n >= min_n else SufficiencyStatus.INSUFFICIENT
        sufficient = status is SufficiencyStatus.SUFFICIENT
        hist = dict(Counter(r["retcode_name"] for r in rows))
        done = hist.get("DONE", 0)
        # slippage only meaningful on FILLED orders; normalize sign so + = adverse for both sides
        adverse = [
            (float(r["slippage_points"]) if r["side"] == "buy" else -float(r["slippage_points"]))
            for r in rows if r["retcode_name"] == "DONE" and float(r.get("filled_price", 0.0))
        ]
        latencies = [float(r["latency_ms"]) for r in rows if r.get("latency_ms") is not None]
        brokers.append(BrokerExecReport(
            broker_key=f"{company}|{server}|mm{mm}",
            company=company, server=server, margin_mode=mm,
            n=n, min_n=min_n, status=status,
            fill_success_rate=round(done / n, 6) if n else None,
            retcode_histogram=hist,
            slippage_adverse_points=_dist(adverse, sufficient=sufficient),
            latency_ms=_dist(latencies, sufficient=sufficient),
            filling_modes=tuple(sorted({r["filling_mode"] for r in rows})),
            symbols=tuple(sorted({r["symbol"] for r in rows})),
        ))
    return ExecReport(min_n=min_n, operational_only=_OPERATIONAL_ONLY, brokers=tuple(brokers))


def load_events(root: "str | Path" = "runtime/exec_telemetry") -> "list[dict]":
    """Read every per-broker orders.jsonl under the telemetry root (read-only)."""
    out: list[dict] = []
    for f in sorted(Path(root).glob("*/orders.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

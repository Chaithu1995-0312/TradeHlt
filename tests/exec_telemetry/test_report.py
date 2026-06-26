"""
test_report — Execution Quality Observatory operational report (Phase C-op).

Covers: retcode histogram + fill-rate, side-normalized adverse-slippage distribution, latency
distribution, sufficiency gating (below min_n → no distributional claim), per-broker grouping,
determinism, and the empty case. OPERATIONAL-ONLY — no profit/expectancy assertions exist here.
"""
from exec_telemetry.report import (
    SufficiencyStatus,
    build_exec_report,
)
from exec_telemetry.schemas.execution_event_v1 import ExecutionEvent, retcode_name


def _ev(side="buy", requested=1.1000, filled=1.10002, slippage_points=2.0, latency_ms=40.0,
        retcode=10009, symbol="EURUSD", company="Raw Trading Ltd",
        server="ICMarketsSC-Demo", mm=2, filling="IOC"):
    return ExecutionEvent(
        ts="2026-06-26T09:45:42Z", broker_fingerprint="fp", company=company, server=server,
        login=52935582, margin_mode=mm, symbol=symbol, side=side,
        requested_price=requested, filled_price=filled, slippage_points=slippage_points,
        latency_ms=latency_ms, retcode=retcode, retcode_name=retcode_name(retcode),
        filling_mode=filling, volume=0.01,
    )


def test_retcode_name_map():
    assert retcode_name(10009) == "DONE"
    assert retcode_name(10027) == "CLIENT_DISABLES_AT"
    assert retcode_name(10018) == "MARKET_CLOSED"
    assert retcode_name(99999) == "UNKNOWN_99999"
    assert retcode_name(None) == "NO_RESULT"


def test_fill_rate_and_retcode_histogram():
    evs = [_ev(retcode=10009)] * 8 + [_ev(retcode=10027)] * 2   # 8 DONE, 2 AutoTrading-off
    rep = build_exec_report(evs, min_n=1)
    b = rep.brokers[0]
    assert b.n == 10
    assert b.fill_success_rate == 0.8
    assert b.retcode_histogram == {"DONE": 8, "CLIENT_DISABLES_AT": 2}


def test_slippage_side_normalized_adverse():
    # buy filled above requested = adverse(+2); sell filled below requested = adverse(+3)
    evs = (
        [_ev(side="buy", slippage_points=2.0)] * 15
        + [_ev(side="sell", slippage_points=-3.0)] * 15
    )
    rep = build_exec_report(evs, min_n=30)
    b = rep.brokers[0]
    assert b.status is SufficiencyStatus.SUFFICIENT
    # all adverse points are +2 (buys) or +3 (sells); both are positive (adverse)
    assert b.slippage_adverse_points.worst == 3.0
    assert b.slippage_adverse_points.median in (2.0, 2.5, 3.0)  # median of mixed 2s/3s


def test_latency_distribution():
    evs = [_ev(latency_ms=v) for v in [10.0, 20.0, 30.0, 40.0, 50.0] * 6]   # n=30
    b = build_exec_report(evs, min_n=30).brokers[0]
    assert b.latency_ms.n == 30
    assert b.latency_ms.median == 30.0
    assert b.latency_ms.worst == 50.0


def test_sufficiency_gating_no_distribution_claim_below_min_n():
    evs = [_ev()] * 5
    b = build_exec_report(evs, min_n=30).brokers[0]
    assert b.status is SufficiencyStatus.INSUFFICIENT
    assert b.slippage_adverse_points is None     # underpowered → no distributional claim
    assert b.latency_ms is None
    assert b.fill_success_rate == 1.0            # counts still reported
    assert b.retcode_histogram == {"DONE": 5}


def test_per_broker_grouping():
    evs = [_ev(company="Raw Trading Ltd", mm=2)] * 3 + [_ev(company="MetaQuotes Ltd.", mm=0)] * 2
    rep = build_exec_report(evs, min_n=1)
    keys = {b.broker_key for b in rep.brokers}
    assert keys == {"Raw Trading Ltd|ICMarketsSC-Demo|mm2",
                    "MetaQuotes Ltd.|ICMarketsSC-Demo|mm0"}


def test_operational_only_header_and_no_pnl_fields():
    rep = build_exec_report([_ev()], min_n=1)
    assert "NOT expectancy" in rep.operational_only
    # the report contract carries no profit/expectancy/R field anywhere
    fields = rep.brokers[0].__dataclass_fields__
    for forbidden in ("expectancy", "profit", "pnl", "win_rate", "r_multiple"):
        assert forbidden not in fields


def test_determinism_and_empty():
    evs = [_ev(side="buy"), _ev(side="sell", slippage_points=-1.0)]
    assert build_exec_report(evs, min_n=1) == build_exec_report(evs, min_n=1)
    empty = build_exec_report([], min_n=30)
    assert empty.brokers == ()
    assert "NOT expectancy" in empty.operational_only

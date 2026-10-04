"""DEX-01..04. Size from a fraction, admission that filters and never trims, fill, approval."""

from __future__ import annotations

import pytest

from semantics.execution.approval import FILTERED, PLANNER_ULTRON, approved, from_crt_reset, from_ultron
from semantics.execution.fill import fill
from semantics.execution.portfolio import ADMITTED, PORTFOLIO_CAP, admit
from semantics.execution.position import exit_rule, exit_schedule, replay_position
from semantics.execution.size import position_size
from semantics.trading.thesis import ACTIVE
from tests.semantics.execution._fixtures import ENTRY_BAR, filled, path, plan, size


def test_quantity_times_r_is_the_risked_fraction_of_equity():
    made = plan()
    sized = size(made, risk_fraction=0.01)
    assert sized.quantity * made.R == pytest.approx(0.01 * 100_000.0)
    assert sized.available_at == made.available_at


def test_a_percent_never_passes_as_a_fraction():
    with pytest.raises(ValueError, match="never a percent"):
        size(plan(), risk_fraction=1.0)
    with pytest.raises(ValueError):
        position_size(plan(), risk_fraction=0.01, equity=1.0, equity_basis="balance")


def test_equity_basis_and_fraction_are_identity():
    made = plan()
    a = position_size(made, risk_fraction=0.01, equity=1e5, equity_basis="initial_capital")
    b = position_size(made, risk_fraction=0.01, equity=1e5, equity_basis="current_equity")
    c = position_size(made, risk_fraction=0.02, equity=1e5, equity_basis="initial_capital")
    d = position_size(made, risk_fraction=0.01, equity=2e5, equity_basis="initial_capital")
    assert len({a.parameterization_id, b.parameterization_id, c.parameterization_id}) == 3
    assert a.parameterization_id == d.parameterization_id   # equity is a value, not identity


def test_count_cap_filters_and_never_trims():
    sized = size()
    full = admit(sized, [sized, sized], max_concurrent_positions=2, max_open_risk=1.0, bar=ENTRY_BAR)
    assert full.verdict == "FILTERED" and full.reason_code == PORTFOLIO_CAP
    assert full.size.quantity == sized.quantity


def test_risk_cap_filters_and_three_hundredths_fit_exactly():
    sized = size()
    fits = admit(sized, [sized, sized], max_concurrent_positions=9, max_open_risk=0.03, bar=ENTRY_BAR)
    assert fits.verdict == ADMITTED
    over = admit(sized, [sized, sized, sized], max_concurrent_positions=9, max_open_risk=0.03, bar=ENTRY_BAR)
    assert over.verdict == "FILTERED" and over.reason_code == PORTFOLIO_CAP


def test_a_second_position_on_the_same_thesis_is_admitted_while_the_first_is_open():
    first = size()
    second = admit(size(), [first], max_concurrent_positions=2, max_open_risk=0.05, bar=ENTRY_BAR)
    assert second.verdict == ADMITTED


def test_admission_refuses_percent_caps_and_early_bars():
    with pytest.raises(ValueError, match="never a percent"):
        admit(size(), [], max_concurrent_positions=3, max_open_risk=5.0, bar=ENTRY_BAR)
    with pytest.raises(ValueError, match="I-6"):
        admit(size(), [], max_concurrent_positions=3, max_open_risk=0.05, bar=ENTRY_BAR - 1)


def test_caps_are_identity():
    a = admit(size(), [], max_concurrent_positions=3, max_open_risk=0.05, bar=ENTRY_BAR)
    b = admit(size(), [], max_concurrent_positions=2, max_open_risk=0.05, bar=ENTRY_BAR)
    assert a.parameterization_id != b.parameterization_id


def test_a_filtered_plan_never_fills_and_an_admitted_one_fills_at_the_entry():
    made = plan()
    denied = admit(size(made), [size(made)], max_concurrent_positions=1, max_open_risk=1.0, bar=ENTRY_BAR)
    assert fill(made.entry, denied) is None
    _made, done = filled(made)
    assert (done.price, done.bar, done.entry_semantics) == (108.0, ENTRY_BAR, "resting_order")
    assert done.available_at >= ENTRY_BAR


def test_crt_reset_filters_map_through_the_terminal_map():
    verdict = from_crt_reset("off_session_filter", 12)
    assert (verdict.verdict, verdict.reason_code, verdict.rail) == (FILTERED, "OFF_SESSION", "crt_engine")
    with pytest.raises(ValueError, match="not FILTERED"):
        from_crt_reset("50% retrace hit", 12)


def test_ultron_verdicts():
    assert from_ultron({"decision": "approve"}, 3).verdict == "APPROVED"
    rejected = from_ultron({"decision": "reject", "risk_reason": "over_exposure"}, 3)
    assert (rejected.verdict, rejected.reason_code, rejected.rail) == (FILTERED, "over_exposure", PLANNER_ULTRON)
    with pytest.raises(ValueError):
        from_ultron({"decision": "maybe"}, 3)
    assert approved("crt_engine", 1).parameterization_id != approved(PLANNER_ULTRON, 1).parameterization_id


def test_a_filtered_confirmation_closes_the_position_unconfirmed_and_leaves_the_thesis_active():
    made, done = filled()
    bars = path((108, 110, 107, 109), (109, 111, 107, 110), (110, 112, 108, 111))
    verdict = from_crt_reset("off_session_filter", bars[1].index)
    position = replay_position(made, done, exit_schedule(0.5, 0.5, plan_bar=ENTRY_BAR),
                               exit_rule("hold", plan_bar=ENTRY_BAR), bars, approval=verdict)
    assert position.exit_reason.value == "UNCONFIRMED" and position.exit_bar == bars[1].index
    assert position.gross_r == pytest.approx((110 - 108) / 10)
    assert made.thesis.status == ACTIVE
    with pytest.raises(ValueError, match="never fills"):
        replay_position(made, done, exit_schedule(0.5, 0.5, plan_bar=ENTRY_BAR),
                        exit_rule("hold", plan_bar=ENTRY_BAR), bars,
                        approval=from_crt_reset("off_session_filter", ENTRY_BAR))

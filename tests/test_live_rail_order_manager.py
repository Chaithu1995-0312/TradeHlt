"""PR-4c slice: OrderManager paper fills, no ATR sizer."""
from __future__ import annotations

from live.order_manager import OrderManager, PaperVenueExecutor


def _om() -> OrderManager:
    return OrderManager(
        PaperVenueExecutor(),
        dry_run=True,
        fill_timeout_s=5.0,
        allow_partial=False,
    )


_PLAN = {
    "execution_id": "e1",
    "symbol": "XAUUSD",
    "direction": 1,
    "entry_price": 2000.0,
    "stop_loss": 1999.0,
    "take_profit_1": 2002.0,
}


def test_submit_approve_paper_fill() -> None:
    fill = _om().submit(_PLAN, {"decision": "approve", "final_position_size": 0.1})
    assert fill.status == "FILLED"
    assert fill.ticket == -1
    assert fill.side == "BUY"
    assert fill.filled_qty == 0.1


def test_submit_rejects_without_approve() -> None:
    fill = _om().submit(_PLAN, {"decision": "reject", "final_position_size": 0.1})
    assert fill.status == "REJECTED"
    assert fill.reason == "ultron_not_approved"


def test_submit_rejects_zero_size() -> None:
    fill = _om().submit(_PLAN, {"decision": "APPROVE", "final_position_size": 0.0})
    assert fill.status == "REJECTED"
    assert fill.reason == "size_not_approved"


def test_no_atr_in_order_manager_source() -> None:
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "src" / "live" / "order_manager.py").read_text(encoding="utf-8")
    assert "Does not compute ATR" in src

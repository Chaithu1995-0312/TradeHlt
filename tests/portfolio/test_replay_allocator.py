"""Floor for the PortfolioAllocator shadow replay (src/portfolio/replay.py, F-013).

Three load-bearing guarantees:
  1. DETERMINISM  — same ledger ⇒ byte-identical ReplayResult.
  2. SPINE ISOLATION — replay.py imports nothing from the live spine (runtime/inout/features/
     research); it cannot influence a live decision even by accident, so it can never accrue
     authority silently.
  3. RECONCILIATION — the realized-R the replay attributes to allocated trades matches an
     INDEPENDENT recompute via analytics.metrics_oracle (the trust-layer oracle).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from analytics import metrics_oracle
from src.portfolio.allocator import PortfolioAllocator
from src.portfolio.replay import ReplayResult, replay_allocator

_REPLAY_SRC = Path(__file__).resolve().parents[2] / "src" / "portfolio" / "replay.py"
_FORBIDDEN_ROOTS = {"runtime", "inout", "features", "research", "core", "engines"}


def _rec(tid, sym, o, c, conf, r, **extra):
    return {"trade_id": tid, "symbol": sym, "open_index": o, "close_index": c,
            "confidence": conf, "realized_r": r, **extra}


# ── 1. determinism ────────────────────────────────────────────────────────────

def test_replay_is_deterministic():
    ledger = [_rec(f"t{i}", "XAUUSD", i, i + 3, 0.6, (-1.0 if i % 3 else 2.0)) for i in range(20)]
    a = replay_allocator(ledger).to_dict()
    b = replay_allocator(ledger).to_dict()
    assert a == b
    assert a["authority"] == "SHADOW_REPLAY_NO_AUTHORITY"


# ── 2. spine isolation (static import scan) ─────────────────────────────────────

def test_replay_imports_no_live_spine_module():
    tree = ast.parse(_REPLAY_SRC.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            roots.add(parts[0])
            # 'src.portfolio' is allowed; flag 'src.<forbidden>'
            if parts[0] == "src" and len(parts) > 1:
                assert parts[1] == "portfolio", f"replay may only import src.portfolio, got {node.module}"
    leaked = roots & _FORBIDDEN_ROOTS
    assert not leaked, f"replay.py leaked live-spine imports: {leaked}"


# ── 3. reconciliation with the independent metrics oracle ───────────────────────

def test_allocated_realized_r_reconciles_with_metrics_oracle():
    # Non-overlapping, single symbol, confidence 0.5 ⇒ every trade sees an empty portfolio ⇒
    # all ALLOCATE at base_risk. The allocated realized-R list must equal the full input R list.
    rs = [1.5, -1.0, 0.5, -1.0, 3.0, -1.0]
    ledger = [_rec(f"t{i}", "XAUUSD", 10 * i, 10 * i + 2, 0.5, rs[i]) for i in range(len(rs))]
    res = replay_allocator(ledger)

    assert res.n_allocated == len(rs) and res.n_rejected == 0
    assert list(res.allocated_realized_r) == rs

    # independent recompute
    assert metrics_oracle.win_rate(list(res.allocated_realized_r)) == pytest.approx(3 / 6)
    assert metrics_oracle.expectancy_mean(list(res.allocated_realized_r)) == pytest.approx(sum(rs) / len(rs))
    # gross win 5.0, gross loss 3.0 ⇒ PF 5/3
    assert metrics_oracle.profit_factor(list(res.allocated_realized_r)) == pytest.approx(5.0 / 3.0)

    # base-risk sizing ⇒ allocator PnL == take-every PnL == base_risk * Σr (all allocated)
    assert res.allocator_pnl == pytest.approx(res.take_every_base_risk * sum(rs))
    assert res.allocator_pnl == pytest.approx(res.take_every_pnl)


# ── 4. strict contract (no defaults, no fallbacks) ─────────────────────────────

@pytest.mark.parametrize("bad", [
    {"trade_id": "t", "symbol": "X", "open_index": 0, "close_index": 3, "confidence": 0.5},   # no realized_r
    {"trade_id": "t", "symbol": "X", "open_index": 0, "close_index": 3, "realized_r": 1.0},    # no confidence
    {"symbol": "X", "open_index": 0, "close_index": 3, "confidence": 0.5, "realized_r": 1.0},  # no trade_id
])
def test_missing_required_field_raises(bad):
    with pytest.raises(ValueError):
        replay_allocator([bad])


def test_close_before_open_raises():
    with pytest.raises(ValueError):
        replay_allocator([_rec("t", "XAUUSD", 5, 2, 0.5, 1.0)])


# ── 5. capacity rejection when concurrent exposure fills the cap ────────────────

def test_capacity_reject_when_portfolio_full():
    # Many same-symbol trades all open at 0 and stay open past the cap. Once total risk reaches
    # max_portfolio_risk (default 2%), further opens REJECT_CAPACITY. allocator_pnl counts only
    # the allocated ones.
    ledger = [_rec(f"t{i}", "XAUUSD", 0, 500, 0.5, 1.0) for i in range(12)]
    res = replay_allocator(ledger)

    assert res.n_allocated + res.n_rejected == 12
    assert res.reason_histogram.get("REJECT_CAPACITY", 0) >= 1
    assert res.n_allocated == len(res.allocated_realized_r)
    # exposure never exceeds the cap: Σ allocated risk ≤ max_portfolio_risk
    total_alloc_risk = sum(d["allocated_risk"] for d in res.decisions if d["action"] == "ALLOCATE")
    assert total_alloc_risk <= PortfolioAllocator().policy.max_portfolio_risk + 1e-12


def test_freed_capacity_is_reused_after_close():
    # t0 fills, closes at 1; t1 opens at 2 into a now-empty portfolio ⇒ both allocate.
    ledger = [_rec("t0", "XAUUSD", 0, 1, 0.5, 1.0), _rec("t1", "XAUUSD", 2, 3, 0.5, 1.0)]
    res = replay_allocator(ledger)
    assert res.n_allocated == 2 and res.n_rejected == 0

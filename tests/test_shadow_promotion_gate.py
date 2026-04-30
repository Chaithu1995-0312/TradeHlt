"""
test_shadow_promotion_gate.py
==============================
GAP-013: min_shadow_trades parameterization and enforcement tests.

Covers:
  - Default min_shadow_trades loaded from production config
  - Injected governance_config overrides default
  - Init validation raises on invalid min_shadow_trades values
  - promote_if_superior blocks when n_shadow_trades < min
  - promote_if_superior blocks when shadow_pnl <= baseline_pnl (sufficient trades)
  - promote_if_superior promotes when both gates pass
  - promote_if_superior returns structured dict (promoted, reason)
  - min_shadow_trades loaded correctly from production_configs/v1_multi_2026_03.json
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from governance.shadow_promotion_gate import ShadowPromotionGate, _DEFAULT_MIN_SHADOW_TRADES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gate(tmp_path: Path, min_trades: int = 30) -> ShadowPromotionGate:
    """Create a ShadowPromotionGate with injected governance config."""
    cfg_path = tmp_path / "prod.json"
    cfg_path.write_text(json.dumps({"governance": {"min_shadow_trades": min_trades}}))
    return ShadowPromotionGate(
        active_config_path=str(cfg_path),
        governance_config={"min_shadow_trades": min_trades},
    )


# ---------------------------------------------------------------------------
# Init / validation
# ---------------------------------------------------------------------------

def test_default_min_shadow_trades_is_positive():
    assert _DEFAULT_MIN_SHADOW_TRADES >= 1


def test_injected_governance_config_sets_min_trades(tmp_path):
    gate = _make_gate(tmp_path, min_trades=50)
    assert gate.min_shadow_trades == 50


def test_init_validates_min_trades_must_be_integer(tmp_path):
    with pytest.raises(ValueError, match="positive integer"):
        ShadowPromotionGate(
            governance_config={"min_shadow_trades": "thirty"},
        )


def test_init_validates_min_trades_must_be_positive(tmp_path):
    with pytest.raises(ValueError, match=">= 1"):
        ShadowPromotionGate(
            governance_config={"min_shadow_trades": 0},
        )


def test_init_validates_min_trades_negative(tmp_path):
    with pytest.raises(ValueError, match=">= 1"):
        ShadowPromotionGate(
            governance_config={"min_shadow_trades": -5},
        )


def test_init_accepts_float_whole_number():
    """30.0 should be coerced to 30 without error."""
    gate = ShadowPromotionGate(governance_config={"min_shadow_trades": 30.0})
    assert gate.min_shadow_trades == 30


def test_min_trades_loaded_from_production_config():
    """GAP-013: governance.min_shadow_trades must exist in production config."""
    prod_path = Path("production_configs/v1_multi_2026_03.json")
    if not prod_path.exists():
        pytest.skip("production config not present")
    cfg = json.loads(prod_path.read_text())
    assert "governance" in cfg, "production config missing 'governance' section"
    assert "min_shadow_trades" in cfg["governance"], (
        "production config governance section missing 'min_shadow_trades'"
    )
    assert isinstance(cfg["governance"]["min_shadow_trades"], int)
    assert cfg["governance"]["min_shadow_trades"] >= 1


# ---------------------------------------------------------------------------
# promote_if_superior — sample-size gate
# ---------------------------------------------------------------------------

def test_promote_blocked_insufficient_trades(tmp_path):
    """Gate 1: n_shadow_trades < min_shadow_trades must block promotion."""
    gate = _make_gate(tmp_path, min_trades=30)
    result = gate.promote_if_superior(
        baseline_pnl=10.0,
        shadow_pnl=20.0,       # better PnL — but not enough trades
        n_shadow_trades=15,    # below min
    )
    assert result["promoted"] is False
    assert "insufficient shadow trades" in result["reason"].lower()
    assert "15" in result["reason"]
    assert "30" in result["reason"]


def test_promote_blocked_exactly_at_boundary(tmp_path):
    """n_shadow_trades == min_shadow_trades - 1 must still block."""
    gate = _make_gate(tmp_path, min_trades=30)
    result = gate.promote_if_superior(10.0, 20.0, n_shadow_trades=29)
    assert result["promoted"] is False


def test_promote_allowed_at_minimum_threshold(tmp_path):
    """n_shadow_trades == min_shadow_trades with better PnL must promote."""
    gate = _make_gate(tmp_path, min_trades=30)
    # Need an actual active config to copy from
    gate.active_config_path.write_text(json.dumps({"test": True}))
    gate.candidate_path.parent.mkdir(parents=True, exist_ok=True)
    gate.candidate_path.write_text(json.dumps({"candidate": True}))

    result = gate.promote_if_superior(10.0, 20.0, n_shadow_trades=30)
    assert result["promoted"] is True
    assert "promoted" in result["reason"].lower()


# ---------------------------------------------------------------------------
# promote_if_superior — performance gate
# ---------------------------------------------------------------------------

def test_promote_blocked_inferior_pnl(tmp_path):
    """Gate 2: shadow_pnl <= baseline_pnl must block even with sufficient trades."""
    gate = _make_gate(tmp_path, min_trades=10)
    result = gate.promote_if_superior(
        baseline_pnl=50.0,
        shadow_pnl=40.0,       # worse
        n_shadow_trades=20,
    )
    assert result["promoted"] is False
    assert "not promoted" in result["reason"].lower()


def test_promote_blocked_equal_pnl(tmp_path):
    """shadow_pnl == baseline_pnl must NOT promote (strict >)."""
    gate = _make_gate(tmp_path, min_trades=10)
    result = gate.promote_if_superior(30.0, 30.0, n_shadow_trades=20)
    assert result["promoted"] is False


def test_promote_result_always_has_promoted_and_reason(tmp_path):
    """Return dict must always have both 'promoted' and 'reason' keys."""
    gate = _make_gate(tmp_path, min_trades=10)
    for n, s, b in [(5, 100.0, 0.0), (20, 0.0, 100.0), (20, 50.0, 50.0)]:
        result = gate.promote_if_superior(b, s, n_shadow_trades=n)
        assert "promoted" in result
        assert "reason" in result
        assert isinstance(result["promoted"], bool)
        assert isinstance(result["reason"], str)

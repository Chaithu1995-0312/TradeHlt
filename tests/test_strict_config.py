"""EPIC-84 F0: the shared strict-read primitive fails closed on every missing key."""
import pytest

from config_layer.strict_config import (
    REASON_PREFIX,
    ConfigKeyMissingError,
    missing_keys,
    missing_reason,
    require,
    require_all,
    require_section,
)

SEC = {"risk_percent": 0.5, "ttl": None, "flag": False}
KW = dict(section_name="execution_planner", consumer="ExecutionPlannerV1_2",
          version="v2_htfcrt_2026_08", source="configs/production/v2_htfcrt_2026_08.json")


def test_require_returns_declared_value_including_falsy_and_none():
    assert require(SEC, "risk_percent", **KW) == 0.5
    assert require(SEC, "flag", **KW) is False
    assert require(SEC, "ttl", **KW) is None  # None is a declared value


def test_require_missing_key_raises_with_full_location():
    with pytest.raises(ConfigKeyMissingError) as ei:
        require(SEC, "breakout_disp_threshold", **KW)
    err = ei.value
    assert isinstance(err, KeyError)
    assert err.missing == ("breakout_disp_threshold",)
    msg = str(err)
    for part in ("execution_planner.breakout_disp_threshold", "ExecutionPlannerV1_2",
                 "v2_htfcrt_2026_08", "configs/production/v2_htfcrt_2026_08.json"):
        assert part in msg


def test_require_all_lists_every_missing_key_at_once():
    with pytest.raises(ConfigKeyMissingError) as ei:
        require_all(SEC, ["risk_percent", "a", "b", "flag", "c"], **KW)
    assert ei.value.missing == ("a", "b", "c")


def test_require_all_returns_values_in_order():
    assert require_all(SEC, ["flag", "risk_percent"], **KW) == {"flag": False, "risk_percent": 0.5}


def test_missing_or_non_mapping_section_fails_closed():
    with pytest.raises(ConfigKeyMissingError):
        require(None, "x", **KW)
    with pytest.raises(TypeError):
        require(["x"], "x", **KW)


def test_require_section():
    cfg = {"ultron_risk_gate": {"min_rr_ratio": 1.5}}
    assert require_section(cfg, "ultron_risk_gate", consumer="UltronRiskGate") == {"min_rr_ratio": 1.5}
    with pytest.raises(ConfigKeyMissingError) as ei:
        require_section(cfg, "execution_planner", consumer="ExecutionPlannerV1_2")
    assert ei.value.missing == ("execution_planner",)


def test_trade_time_helpers_name_the_reject_reason():
    payload = {"risk_percent": 0.5}
    miss = missing_keys(payload, ["risk_percent", "account_balance", "direction"])
    assert miss == ["account_balance", "direction"]
    assert missing_reason("trade", miss) == (
        f"{REASON_PREFIX}:trade.account_balance,trade.direction"
    )
    assert missing_keys(payload, ["risk_percent"]) == []
    assert missing_keys(None, ["risk_percent"]) == ["risk_percent"]

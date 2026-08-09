"""Floor: the live hook's merged config must carry `crt_engine` (C3, 2026-07-29).

Why this test exists
--------------------
`_load_engine_config()` built the merged dict from engine_runner + decision_engine
(flattened) plus fusion_engine / ultron_risk_gate / execution_planner (nested) — but
NOT `crt_engine`. Consequently, inside `LiveEngineHook.process()`:

    _crt_cfg = engine_config.get("crt_engine", {})          # -> ALWAYS {}
    ...
    sl_atr_buffer = float(_require_cfg(_crt_cfg, "sl_atr_buffer", "crt_engine"))

`_require_cfg` is strict, so that line raised KeyError on EVERY
``trade_plan["decision"] == "execute"`` — before stop_loss / take_profit /
rr_ratio / position_size_hint were ever set, and `process()` has no wrapping
try, so it propagated to the caller.

The same empty dict also silently collapsed the per-intent TP1 multipliers
(breakout 1.5, liq_sweep 1.2, pullback 0.8) to the literal 1.0 fallback — the
F-056 "declared, strictly present, and still not governing" class.

These assertions are RED before the crt_engine plumbing and GREEN after.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CONFIG_PATH = ROOT / "configs" / "production" / "v2_multi_2026_04.json"

# Every key the live SL/TP block reads out of the crt_engine section.
_TP_MULTIPLIER_KEYS = (
    "tp1_atr_multiplier",
    "tp1_atr_multiplier_breakout",
    "tp1_atr_multiplier_liq_sweep",
    "tp1_atr_multiplier_pullback",
    "tp1_atr_multiplier_reversal",
    "tp2_atr_multiplier",
)


@pytest.fixture()
def merged_config() -> dict:
    """Fresh merged config (the module caches it in a global)."""
    import runtime.live_engine_hook as hook

    hook._ENGINE_CONFIG_CACHE = None
    cfg = hook._load_engine_config()
    hook._ENGINE_CONFIG_CACHE = None
    return cfg


@pytest.fixture(scope="module")
def raw_config() -> dict:
    assert CONFIG_PATH.is_file(), f"missing {CONFIG_PATH}"
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_merged_config_carries_crt_engine(merged_config):
    """The section the live SL/TP block reads must actually be present."""
    assert "crt_engine" in merged_config, (
        "crt_engine missing from the merged live config — live_engine_hook's "
        "SL/TP block reads engine_config.get('crt_engine', {}) and would get {}"
    )
    assert isinstance(merged_config["crt_engine"], dict)
    assert merged_config["crt_engine"], "crt_engine merged as an EMPTY dict"


def test_crt_engine_is_nested_not_flattened(merged_config, raw_config):
    """crt_engine must be a nested key.

    Flattening it would collide with the already-flattened engine_runner /
    decision_engine keys (both sections define overlapping names), silently
    changing unrelated live behaviour.
    """
    crt = merged_config["crt_engine"]
    assert crt == raw_config["crt_engine"], (
        "merged crt_engine is not the production section verbatim"
    )
    # A flattened merge would have leaked crt-only keys to the top level.
    assert "sl_atr_buffer" not in merged_config, (
        "crt_engine appears to have been flattened into the merged config"
    )


def test_sl_atr_buffer_resolves_strictly(merged_config, raw_config):
    """The exact strict read that used to raise KeyError on every execute."""
    from runtime.live_engine_hook import _require_cfg

    crt_cfg = merged_config.get("crt_engine", {})
    value = float(_require_cfg(crt_cfg, "sl_atr_buffer", "crt_engine"))
    assert value == float(raw_config["crt_engine"]["sl_atr_buffer"])
    assert value > 0.0


@pytest.mark.parametrize("key", _TP_MULTIPLIER_KEYS)
def test_tp_multipliers_reach_behaviour(merged_config, raw_config, key):
    """Per-intent TP multipliers must resolve from config, not collapse to 1.0."""
    crt_cfg = merged_config.get("crt_engine", {})
    assert key in crt_cfg, f"{key} absent from merged crt_engine"
    assert float(crt_cfg[key]) == float(raw_config["crt_engine"][key])


def test_per_intent_multipliers_are_actually_distinct(merged_config):
    """The whole point of C3: three intents must NOT all be 1.0 any more.

    Before the fix every lookup missed and `_tp1_mult` was the literal 1.0 for
    all four intents. This pins that they now differ.
    """
    crt_cfg = merged_config["crt_engine"]
    resolved = {
        intent: float(
            crt_cfg.get(
                f"tp1_atr_multiplier_{intent}",
                crt_cfg["tp1_atr_multiplier"],
            )
        )
        for intent in ("breakout", "liq_sweep", "pullback", "reversal")
    }
    assert resolved["breakout"] != 1.0, "breakout TP1 still collapsed to 1.0"
    assert resolved["liq_sweep"] != 1.0, "liq_sweep TP1 still collapsed to 1.0"
    assert resolved["pullback"] != 1.0, "pullback TP1 still collapsed to 1.0"
    assert len(set(resolved.values())) > 1, "all intents resolve to one value"

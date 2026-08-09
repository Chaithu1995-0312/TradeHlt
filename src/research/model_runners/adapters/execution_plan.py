"""Stage-5 execution-plan adapter (A5) — the full candle -> executable-trade chain.

RETRACTION NOTE (2026-07-29)
---------------------------
This adapter was previously registered BLOCKED_BY_DESIGN on the reasoning that
"ExecutionPlanner does not produce SL/TP/RR". That statement is true of
``ExecutionPlannerV1_2.plan()`` **in isolation**, but it described a COMPONENT and
presented it as the PIPELINE. The composition that yields a complete executable
trade lives in ``src/runtime/live_engine_hook.py`` ``process()``:

    :860  trade_plan = planner.plan(engine_outputs, engine_input, trade_context)
    :891  _crt       = compute_crt_levels(entry, direction, low, high, atr, ...)
    :902  trade_plan["stop_loss"] / ["take_profit_1"] / ["take_profit_2"]
    :914  trade_plan["rr_ratio"]  = |TP1 - entry| / |entry - SL|   <- TRUE geometric RR
    :919  trade_plan["rr_source"] = "sl_tp_geometry"
    :923  trade_plan["position_size_hint"] = (balance * risk_pct/100) / risk_dist

This adapter mirrors that exact order. The second original objection —
"selected_direction requires RegimeGovernor, so this means re-implementing
EngineRunner.run()" — was also overstated: the governor's *selection* step is a
pure deterministic function of (regime, dual_results) with no state
(``core/regime_governor.py:214-246``); only its ``allow`` decision uses the
rolling-percentile / daily-quota machinery, which this adapter does not need.

DECLARED DIVERGENCES from the live path (all surfaced in ``artifact_info``; none silent)
---------------------------------------------------------------------------------------
1. ``account_balance`` is read from ``execution_planner.default_account_balance``
   (a declared config constant), NOT from a live portfolio/broker balance.
2. ``UltronRiskGate`` is NOT invoked — this adapter stops at the trade plan, which
   is the object Ultron consumes. No approval is implied.
3. No MT5 / order placement of any kind.
4. RegimeGovernor's ``allow`` gate (percentile band + daily quota) is not applied;
   only its stateless engine-selection rule is reproduced.

Authority: research/observation only. PRODUCTION_BEHAVIOR_CHANGED=false.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config_layer.execution_planner import ExecutionPlannerV1_2
from core.engine_runner import breakout_engine, detect_regime, trap_engine
from core.gate_intelligence import compute_crt_levels
from research.model_runners.adapters.decision import DecisionAdapter
from research.model_runners.contracts import ModelContract, get_contract
from research.model_runners.require_config import require_key, require_section
from research.model_runners.substrate import BarContext, require_feature_keys

# Features the composition itself reads (the planner validates its own set).
_REQUIRED_FEATURES = ("high", "low", "atr")

_DUAL_KEYS = (
    "trend_strength_threshold",
    "momentum_threshold",
    "range_volatility_threshold",
    "breakout_min_score",
    "trap_min_score",
)


def _select_direction(regime: str, dual: dict[str, dict]) -> dict[str, Any]:
    """Reproduce RegimeGovernor's stateless engine-selection rule.

    Source: core/regime_governor.py:214-246 — trend -> breakout, range -> trap,
    neutral -> higher-scoring engine. Deterministic; no rolling state involved.

    Strict throughout: this package bans soft-default lookups, and both dual
    engines always emit `score`/`direction` (engine_runner.py:176-186, :209-217),
    so a missing key is a real contract break, not a defaultable absence.
    """
    for name in ("breakout", "trap"):
        if name not in dual:
            raise KeyError(f"dual results missing {name!r} engine output")
    breakout = dual["breakout"]
    trap = dual["trap"]
    for name, res in (("breakout", breakout), ("trap", trap)):
        for field in ("score", "direction"):
            if field not in res:
                raise KeyError(f"{name} engine output missing {field!r}")

    if regime == "trend":
        return {
            "engine": "breakout",
            "selected": dict(breakout),
            "reason": "regime_trend",
        }
    if regime == "range":
        return {"engine": "trap", "selected": dict(trap), "reason": "regime_range"}

    b_score = float(breakout["score"])
    t_score = float(trap["score"])
    if b_score >= t_score:
        chosen = {
            "engine": "breakout",
            "score": b_score,
            "direction": int(breakout["direction"]),
        }
    else:
        chosen = {
            "engine": "trap",
            "score": t_score,
            "direction": int(trap["direction"]),
        }
    return {
        "engine": chosen["engine"],
        "selected": chosen,
        "reason": "regime_neutral_resolved",
    }


class ExecutionPlanAdapter:
    def __init__(
        self,
        *,
        contract: ModelContract,
        prod_config: dict[str, Any],
        instrument: str,
        repo_root: Path,
    ):
        self.contract = contract
        self._instrument = instrument

        ep = require_section(prod_config, "execution_planner")
        self._balance = float(
            require_key(ep, "default_account_balance", path="execution_planner")
        )
        self._risk_percent = float(
            require_key(ep, "risk_percent", path="execution_planner")
        )
        require_key(ep, "precision_default", path="execution_planner")

        # GateIntelligence thresholds are merged into the planner config live
        # (live_engine_hook :843-846) — mirror that, strictly.
        gi = require_section(prod_config, "gate_intelligence")
        self._planner_cfg: dict[str, Any] = {**dict(ep), **dict(gi)}
        self._planner = ExecutionPlannerV1_2(self._planner_cfg)

        crt = require_section(prod_config, "crt_engine")
        self._sl_atr_buffer = float(
            require_key(crt, "sl_atr_buffer", path="crt_engine")
        )
        self._crt_cfg = dict(crt)

        er = require_section(prod_config, "engine_runner")
        dual = require_key(er, "dual_engine", path="engine_runner")
        if not isinstance(dual, dict):
            raise KeyError("engine_runner.dual_engine must be a mapping")
        for key in _DUAL_KEYS:
            require_key(dual, key, path="engine_runner.dual_engine")
        self._dual_cfg = dict(dual)

        self._decision = DecisionAdapter(
            contract=get_contract("decision"),
            prod_config=prod_config,
            instrument=instrument,
            repo_root=repo_root,
        )

        sections = sorted(
            set(self._decision.config_sections_read)
            | {"execution_planner", "gate_intelligence", "crt_engine", "engine_runner"}
        )
        self.config_sections_read = sections
        self.config_keys_read = list(self._decision.config_keys_read) + [
            "execution_planner.default_account_balance",
            "execution_planner.risk_percent",
            "execution_planner.precision_default",
            "crt_engine.sl_atr_buffer",
            "crt_engine.tp1_atr_multiplier(+per-intent)",
            "crt_engine.tp2_atr_multiplier",
        ] + [f"engine_runner.dual_engine.{k}" for k in _DUAL_KEYS]

        self.artifact_info = {
            "path": None,
            "serve": "config_layer.execution_planner.ExecutionPlannerV1_2.plan",
            "mirrors": "src/runtime/live_engine_hook.py process() :860-926",
            "account_balance_source": "execution_planner.default_account_balance",
            "account_balance_value": self._balance,
            "risk_percent": self._risk_percent,
            "sl_atr_buffer": self._sl_atr_buffer,
            "ultron_risk_gate_invoked": False,
            "regime_governor_allow_gate_applied": False,
            "direction_source": (
                "RegimeGovernor stateless selection rule reproduced "
                "(regime_governor.py:214-246); allow-gate NOT applied"
            ),
            "declared_divergences": [
                "balance is a config constant, not a live portfolio read",
                "UltronRiskGate not invoked (adapter stops at the trade plan)",
                "no MT5 / order placement",
                "RegimeGovernor percentile+quota allow-gate not applied",
            ],
            "spine_active": False,
        }

    def _tp_multipliers(self, intent: str) -> tuple[float, float]:
        """Per-intent TP multipliers, same resolution order as the live hook.

        A per-intent key may legitimately be absent (only four intents declare
        one; UNKNOWN does not), so that lookup is an explicit membership branch —
        NOT a `.get(k, literal)`. The base keys are strict: their absence is a
        config error, not a defaultable condition.
        """
        key = f"tp1_atr_multiplier_{intent.lower()}"
        if key in self._crt_cfg:
            tp1 = float(self._crt_cfg[key])
        else:
            tp1 = float(
                require_key(self._crt_cfg, "tp1_atr_multiplier", path="crt_engine")
            )
        tp2 = float(
            require_key(self._crt_cfg, "tp2_atr_multiplier", path="crt_engine")
        )
        return tp1, tp2

    def score_bar(self, bar: BarContext) -> dict[str, Any]:
        require_feature_keys(bar.features, _REQUIRED_FEATURES)
        feats = {k: float(bar.features[k]) for k in bar.features}

        decision_native = self._decision.score_bar(bar)
        regime = detect_regime(feats, self._dual_cfg)
        dual = {
            "breakout": breakout_engine(feats, self._dual_cfg),
            "trap": trap_engine(feats, self._dual_cfg),
        }
        sel = _select_direction(regime, dual)
        # _select_direction guarantees `direction` on the selected engine.
        if "direction" not in sel["selected"]:
            raise KeyError("selected engine output missing 'direction'")
        selected_direction = int(sel["selected"]["direction"])

        # DecisionAdapter always emits these three; treat absence as a contract break.
        for field in ("decision", "confidence", "input_final_score"):
            if field not in decision_native:
                raise KeyError(f"decision adapter output missing {field!r}")
        engine_result = {
            "decision": str(decision_native["decision"]),
            "selected_direction": selected_direction,
            "selected_engine": sel["engine"],
            "confidence": float(decision_native["confidence"]),
            "regime": regime,
            "final_score": float(decision_native["input_final_score"]),
        }
        trade_context = {
            "symbol": self._instrument,
            "signal": selected_direction,
            "score": engine_result["final_score"],
            "account_balance": self._balance,
        }

        trade_plan = self._planner.plan(engine_result, feats, trade_context)
        if not isinstance(trade_plan, dict):
            raise TypeError(
                f"ExecutionPlanner.plan must return dict, got {type(trade_plan)}"
            )

        out: dict[str, Any] = dict(trade_plan)
        out["engine_decision"] = engine_result["decision"]
        out["selected_direction"] = selected_direction
        out["selected_engine"] = sel["engine"]
        out["selection_reason"] = sel["reason"]
        out["regime"] = regime
        out["semantic"] = "stage5_execution_plan"

        # SL/TP/RR/size only exist on an executing plan — exactly as live gates it.
        if "decision" not in trade_plan:
            raise KeyError("ExecutionPlanner.plan result missing 'decision'")
        if str(trade_plan["decision"]).lower() != "execute":
            out["levels_computed"] = False
            return _json_safe(out)

        # trade_intent is guaranteed on an executing plan (set before the gate);
        # explicit branch rather than a soft default so a contract break is loud.
        if "trade_intent" not in trade_plan:
            raise KeyError("executing plan missing 'trade_intent'")
        intent = str(trade_plan["trade_intent"]).upper()
        tp1_mult, tp2_mult = self._tp_multipliers(intent)
        crt = compute_crt_levels(
            entry=float(trade_plan["entry_price"]),
            direction=int(trade_plan["direction"]),
            low=feats["low"],
            high=feats["high"],
            atr=feats["atr"],
            sl_atr_buffer=self._sl_atr_buffer,
            tp1_mult=tp1_mult,
            tp2_mult=tp2_mult,
        )
        out["stop_loss"] = float(crt["sl"])
        out["take_profit_1"] = float(crt["tp1"])
        out["take_profit_2"] = float(crt["tp2"])

        entry_px = float(trade_plan["entry_price"])
        risk_px = abs(entry_px - out["stop_loss"])
        if risk_px > 0:
            out["rr_ratio"] = round(abs(out["take_profit_1"] - entry_px) / risk_px, 6)
            out["rr_ratio_tp2"] = round(
                abs(out["take_profit_2"] - entry_px) / risk_px, 6
            )
        else:
            out["rr_ratio"] = 0.0
            out["rr_ratio_tp2"] = 0.0
        out["rr_source"] = "sl_tp_geometry"

        out["risk_percent"] = self._risk_percent
        risk_dist = float(crt["risk_dist"])
        out["position_size_hint"] = (
            round((self._balance * self._risk_percent / 100.0) / risk_dist, 4)
            if risk_dist > 0
            else None
        )
        out["risk_dist"] = risk_dist
        out["tp1_mult_used"] = tp1_mult
        out["tp2_mult_used"] = tp2_mult
        out["levels_computed"] = True
        # `score` is the planner's own gate score when present — never synthesised.
        gate = trade_plan.get("gate")
        if isinstance(gate, dict) and "final_score" in gate:
            out["score"] = float(gate["final_score"])
        return _json_safe(out)


def _json_safe(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten only what the writer cannot serialise; invent nothing."""
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, (str, int, float, bool, list, type(None))):
            out[k] = v
        elif isinstance(v, dict):
            out[k] = {
                sk: (sv if isinstance(sv, (str, int, float, bool, type(None))) else str(sv))
                for sk, sv in v.items()
            }
        else:
            out[k] = str(v)
    return out

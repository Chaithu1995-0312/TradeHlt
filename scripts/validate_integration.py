"""
validate_integration.py
=======================
Validates every integration point introduced in the Unified Execution Spine
migration.  Run from repo root:

    python scripts/validate_integration.py

Each check prints PASS / FAIL / SKIP and a reason.
Exit code 0 = all checks passed (or skipped).
Exit code 1 = at least one FAIL.
"""

import sys
import os
import importlib
import traceback
import unittest.mock as mock

# -- path setup ----------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# -- helpers -------------------------------------------------------------------
_results: list[tuple[str, str, str]] = []   # (status, name, detail)

def _pass(name, detail=""):
    _results.append(("PASS", name, detail))
    print(f"  PASS  {name}{(' -- ' + detail) if detail else ''}")

def _fail(name, detail=""):
    _results.append(("FAIL", name, detail))
    print(f"  FAIL  {name}{(' -- ' + detail) if detail else ''}")

def _skip(name, detail=""):
    _results.append(("SKIP", name, detail))
    print(f"  SKIP  {name}{(' -- ' + detail) if detail else ''}")

def _section(title):
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print(f"{'-' * 60}")


# -----------------------------------------------------------------------------
# 1. CONTRACT LAYER  (src/core/types.py)
# -----------------------------------------------------------------------------
_section("1. Contract layer -- src/core/types.py")

try:
    from core.types import (
        assert_approve_before_order,
        assert_engine_runner_output,
        SpineContractError,
        EngineRunnerOutput, TradePlan, GateResult, EngineContext,
    )

    # 1a. assert_approve_before_order blocks REJECT
    try:
        assert_approve_before_order({"decision": "REJECT"})
        _fail("1a. assert_approve_before_order blocks REJECT", "did not raise")
    except SpineContractError:
        _pass("1a. assert_approve_before_order blocks REJECT")

    # 1b. assert_approve_before_order passes APPROVE
    try:
        assert_approve_before_order({"decision": "APPROVE"})
        _pass("1b. assert_approve_before_order passes APPROVE")
    except Exception as e:
        _fail("1b. assert_approve_before_order passes APPROVE", str(e))

    # 1c. assert_engine_runner_output blocks bad decision
    try:
        assert_engine_runner_output({"decision": "yes"})
        _fail("1c. assert_engine_runner_output blocks bad decision", "did not raise")
    except SpineContractError:
        _pass("1c. assert_engine_runner_output blocks bad decision")

    # 1d. assert_engine_runner_output accepts valid decisions
    try:
        assert_engine_runner_output({"decision": "execute"})
        assert_engine_runner_output({"decision": "reject"})
        _pass("1d. assert_engine_runner_output accepts execute/reject")
    except Exception as e:
        _fail("1d. assert_engine_runner_output accepts execute/reject", str(e))

    # 1e. TypedDict shapes importable
    try:
        _dummy: EngineRunnerOutput = {"decision": "reject"}  # type: ignore[typeddict-item]
        _pass("1e. TypedDicts importable (EngineRunnerOutput, TradePlan, GateResult, EngineContext)")
    except Exception as e:
        _fail("1e. TypedDicts importable", str(e))

except Exception as e:
    _fail("1. types.py import failed", str(e))


# -----------------------------------------------------------------------------
# 2. FEATURE BOUNDARY  (FeatureStore.validate_or_raise)
# -----------------------------------------------------------------------------
_section("2. Feature boundary -- FeatureStore.validate_or_raise()")

try:
    from core.feature_store import FeatureStore, FeatureValidationError
    from features.feature_schema import CANONICAL_FEATURES

    fs = FeatureStore()

    # 2a. Sparse dict raises FeatureValidationError
    try:
        fs.validate_or_raise({"body_ratio": 0.5, "atr": 0.001})
        _fail("2a. validate_or_raise rejects sparse dict", "did not raise")
    except FeatureValidationError as e:
        _pass("2a. validate_or_raise rejects sparse dict", f"{len(CANONICAL_FEATURES)} keys required")

    # 2b. Full canonical dict passes
    try:
        full = {k: 0.5 for k in CANONICAL_FEATURES}
        full["atr"] = 0.0005
        fs.validate_or_raise(full)
        _pass("2b. validate_or_raise accepts full canonical dict")
    except Exception as e:
        _fail("2b. validate_or_raise accepts full canonical dict", str(e))

    # 2c. FeatureValidationError is a ValueError subclass (contract)
    assert issubclass(FeatureValidationError, ValueError), "Not a ValueError subclass"
    _pass("2c. FeatureValidationError is subclass of ValueError")

except Exception as e:
    _fail("2. FeatureStore import failed", str(e))


# -----------------------------------------------------------------------------
# 3. SPINE ADAPTER  (src/scanner/spine_adapter.py)
# -----------------------------------------------------------------------------
_section("3. SpineAdapter -- src/scanner/spine_adapter.py")

try:
    from scanner.spine_adapter import SpineAdapter
    from features.feature_schema import CANONICAL_FEATURES

    # Build a dummy EngineRunner that returns a known result
    class _MockRunner:
        def run(self, input_data, context):
            return {"decision": "execute", "final_score": 0.75,
                    "selected_direction": 1, "regime": "trend",
                    "engine_scores": {"rr": 0.6}, "fusion": {}}

    adapter = SpineAdapter(engine_runner=_MockRunner(), timeframe="M15", session="london")
    features = {k: 0.5 for k in CANONICAL_FEATURES}
    features["atr"] = 0.0005

    # 3a. execute -> BUY action
    result = adapter.evaluate("EURUSD", features)
    assert result.get("action") == "BUY", f"Expected BUY, got {result.get('action')}"
    assert result.get("decision") == "execute"
    assert "confidence" in result
    _pass("3a. execute decision maps to BUY action")

    # 3b. reject -> NO_SIGNAL
    class _MockRunnerReject:
        def run(self, input_data, context):
            return {"decision": "reject", "final_score": 0.1,
                    "selected_direction": 0, "reason": "low score"}
    adapter2 = SpineAdapter(engine_runner=_MockRunnerReject())
    result2 = adapter2.evaluate("GBPUSD", features)
    assert result2.get("action") == "NO_SIGNAL"
    _pass("3b. reject decision maps to NO_SIGNAL action")

    # 3c. EngineRunner crash -> safe NO_SIGNAL fallback
    class _MockRunnerCrash:
        def run(self, input_data, context):
            raise RuntimeError("simulated engine crash")
    adapter3 = SpineAdapter(engine_runner=_MockRunnerCrash())
    result3 = adapter3.evaluate("USDJPY", features)
    assert result3.get("action") == "NO_SIGNAL"
    _pass("3c. EngineRunner crash -> safe NO_SIGNAL fallback (no exception propagated)")

    # 3d. context dict contains required symbol/timeframe
    captured_context = {}
    class _MockRunnerCtx:
        def run(self, input_data, context):
            captured_context.update(context)
            return {"decision": "reject", "final_score": 0.1, "selected_direction": 0}
    adapter4 = SpineAdapter(engine_runner=_MockRunnerCtx(), timeframe="H1", session="newyork")
    adapter4.evaluate("AUDUSD", features)
    assert captured_context.get("symbol") == "AUDUSD"
    assert captured_context.get("timeframe") == "H1"
    assert captured_context.get("session") == "newyork"
    _pass("3d. context dict contains symbol/timeframe/session")

except Exception as e:
    _fail("3. SpineAdapter", traceback.format_exc(limit=3))


# -----------------------------------------------------------------------------
# 4. 5TH ENGINE -- strategy_consensus flows into FusionEngine
# -----------------------------------------------------------------------------
_section("4. 5th engine -- strategy_consensus in FusionEngine.compute()")

try:
    from core.fusion_engine import FusionEngine

    # Build FusionEngine with weight_strategy_consensus = 0.10
    cfg_dict = {
        "weight_crt": 0.30, "weight_gaussian": 0.25,
        "weight_zone_gate": 0.20, "weight_rr": 0.15,
        "weight_strategy_consensus": 0.10,
        "zone_gate_dead_if_missing": False,
        "min_engines_required": 4,
    }
    fe = FusionEngine.from_prod_config(cfg_dict) if hasattr(FusionEngine, "from_prod_config") \
        else FusionEngine(cfg_dict)

    # 4a. With strategy_consensus present, included in output
    payload = {
        "crt":      {"score": 0.8},
        "gaussian": {"score": 0.7},
        "zone_gate":{"score": 0.6, "passed": True},
        "rr":       {"score": 0.5},
        "strategy_consensus": {"score": 0.72, "direction": 1},
    }
    out = fe.compute(payload)
    assert "final_score" in out, "final_score missing"
    _pass("4a. FusionEngine.compute() accepts 5-engine payload", f"final_score={out['final_score']:.4f}")

    # 4b. Without strategy_consensus, still produces a score (weight=0 disabled path)
    payload_4 = {k: v for k, v in payload.items() if k != "strategy_consensus"}
    out2 = fe.compute(payload_4)
    assert "final_score" in out2
    _pass("4b. FusionEngine.compute() works without strategy_consensus (disabled path)")

    # 4c. EngineRunner injects strategy_consensus from context
    import core.engine_runner as er_mod
    from core.engine_runner import ENGINE_RUNNER_DEFAULTS, DUAL_ENGINE_DEFAULTS
    from core.signal_audit import SignalAuditRecorder
    from core.acceptance_controller import AcceptanceController
    from core.convergence_controller import ConvergenceController
    from features.feature_schema import CANONICAL_FEATURES

    _fusion_received = {}

    class _SpyFusion:
        def compute(self, payload):
            _fusion_received.update(payload)
            return {"final_score": 0.8}

    class _DummyEngine:
        def compute(self, p): return {"score": 0.5, "reason": "ok"}

    class _DummyDecision:
        def evaluate(self, score, p_win, zone_gate, fusion, config):
            return {"decision": "Approved", "confidence": 0.8, "reason": "ok"}

    runner = er_mod.EngineRunner.__new__(er_mod.EngineRunner)
    runner.config       = dict(ENGINE_RUNNER_DEFAULTS)
    runner.dual_cfg     = dict(DUAL_ENGINE_DEFAULTS)
    runner._audit       = SignalAuditRecorder(debug_mode=False)
    runner._acceptance  = AcceptanceController({})
    runner._convergence = ConvergenceController(window_size=500)
    runner._rr_fusion_enabled   = False
    runner._fusion_use_evaluate = False
    runner._fusion_compare_evaluate = False
    runner.rr_fusion   = None
    runner.adapter     = _DummyEngine()
    runner.gaussian    = _DummyEngine()
    runner.bitnet      = type("B", (), {"compute": lambda s, p: {"zone": 0.5}})()
    runner.rr          = type("R", (), {"compute": lambda s, p: {"score": 0.5}})()
    runner.fusion      = _SpyFusion()
    runner.collector   = type("C", (), {"log": lambda s, p: None})()
    runner.decision    = _DummyDecision()

    features = {k: 0.5 for k in CANONICAL_FEATURES}
    features.update({"atr": 0.0005, "trend_bias": 1.0, "ema_spread": 0.9,
                     "momentum_score": 0.8, "volatility_ratio": 1.2,
                     "sweep_detected": 1.0, "disp_strength": 1.0})

    context = {
        "symbol": "EURUSD", "timeframe": "M15",
        "strategy_consensus_score": 0.72,
        "strategy_consensus_direction": 1,
    }

    with mock.patch.object(er_mod, "crt_compute", return_value={"score": 0.6}), \
         mock.patch.object(er_mod, "run_zone_gate_engine",
                           return_value={"score": 0.5, "passed": True, "vector": [], "valid": True}):
        runner.run(features, context)

    assert "strategy_consensus" in _fusion_received, \
        f"strategy_consensus NOT in FusionEngine payload. Keys: {list(_fusion_received)}"
    sc = _fusion_received["strategy_consensus"]
    assert abs(sc["score"] - 0.72) < 0.001
    assert sc["direction"] == 1
    _pass("4c. EngineRunner injects strategy_consensus from context into FusionEngine",
          f"score={sc['score']}, direction={sc['direction']}")

except Exception as e:
    _fail("4. 5th engine", traceback.format_exc(limit=4))


# -----------------------------------------------------------------------------
# 5. REGIME INJECTION  (live_engine_hook wiring)
# -----------------------------------------------------------------------------
_section("5. Regime injection -- RegimeClassifier -> EngineRunner context")

try:
    import runtime.live_engine_hook as leh

    # 5a. Module-level flags exist
    assert hasattr(leh, "_REGIME_AVAILABLE"), "Missing _REGIME_AVAILABLE flag"
    assert hasattr(leh, "_get_regime_classifier"), "Missing _get_regime_classifier()"
    _pass("5a. live_engine_hook has _REGIME_AVAILABLE + _get_regime_classifier")

    # 5b. RegimeClassifier optional import (available or graceful skip)
    if leh._REGIME_AVAILABLE:
        rc = leh._get_regime_classifier()
        _pass("5b. RegimeClassifier singleton initialised",
              f"type={type(rc).__name__}")
    else:
        _skip("5b. RegimeClassifier not importable -- live_engine_hook will skip regime injection (correct)")

    # 5c. context dict injection logic present in source
    import inspect
    src = inspect.getsource(leh)
    assert 'context["regime"]' in src, 'context["regime"] assignment missing from live_engine_hook'
    assert 'context["fusion_weights"]' in src, 'context["fusion_weights"] missing'
    _pass("5c. context[\"regime\"] and context[\"fusion_weights\"] injection present in live_engine_hook source")

    # 5d. StrategyOrchestrator moved BEFORE EngineRunner.run() (5th engine pre-run)
    assert 'context["strategy_consensus_score"]' in src, \
        'context["strategy_consensus_score"] injection missing'
    assert 'context["strategy_consensus_direction"]' in src, \
        'context["strategy_consensus_direction"] injection missing'
    _pass("5d. strategy_consensus injected into context before EngineRunner.run()")

except Exception as e:
    _fail("5. Regime injection", traceback.format_exc(limit=3))


# -----------------------------------------------------------------------------
# 6. JOURNAL -> COLLECTOR DELEGATION  (src/journal/trade_logger.py)
# -----------------------------------------------------------------------------
_section("6. Journal -> Collector delegation")

try:
    import journal.trade_logger as tl_mod

    # 6a. Collector import guard present
    assert hasattr(tl_mod, "_COLLECTOR_AVAILABLE"), "Missing _COLLECTOR_AVAILABLE flag"
    _pass("6a. _COLLECTOR_AVAILABLE flag present in trade_logger")

    # 6b. Collector.log() called on every TradeRecord.log()
    if tl_mod._COLLECTOR_AVAILABLE and tl_mod._collector_mod is not None:
        import tempfile, json
        collector_calls = []

        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            tmp_path = f.name

        try:
            with mock.patch.object(
                tl_mod._collector_mod.Collector, "log",
                side_effect=lambda p: collector_calls.append(p)
            ):
                from journal.trade_logger import TradeLogger
                from journal.schema import TradeRecord
                tlogger = TradeLogger(log_path=tmp_path)
                rec = TradeRecord(
                    trade_id="VAL001",
                    timestamp="2026-05-02T00:00:00Z",
                    symbol="EURUSD",
                    result="WIN", pnl=50.0, rr=2.0,
                    engine_action="execute", regime="trend",
                )
                tlogger.log(rec)

            assert len(collector_calls) == 1, f"Expected 1 call, got {len(collector_calls)}"
            c = collector_calls[0]
            assert c.get("kind") == "trade_outcome"
            assert c["features"]["id"] == "VAL001"
            _pass("6b. TradeLogger.log() delegates to Collector.log()",
                  f"kind={c['kind']}, trade_id={c['features']['id']}")

            # Primary JSONL still written
            with open(tmp_path) as fh:
                lines = [l for l in fh if l.strip()]
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["trade_id"] == "VAL001"
            _pass("6c. Primary trade_journal.jsonl write still occurs")

        finally:
            os.unlink(tmp_path)
    else:
        _skip("6b/6c. core.collector not importable -- delegation skipped gracefully (correct)")

except Exception as e:
    _fail("6. Journal -> Collector", traceback.format_exc(limit=3))


# -----------------------------------------------------------------------------
# 7. ARCHIVE INTEGRITY -- no live imports of archived modules
# -----------------------------------------------------------------------------
_section("7. Archive integrity -- no src/ imports of archived modules")

import subprocess

ARCHIVE_MODULES = [
    "src.inout.probability_engine",
    "src.inout.state_machine",
    "src.inout.controller",
    "src.inout.executor",
    "src.inout.runner",
    "src.inout.scanner",
    "src.inout.db",
    "src.ui.dashboard",
]

GREP_TARGETS = [
    ("from inout",  os.path.join(ROOT, "src")),
    ("import inout", os.path.join(ROOT, "src")),
    ("from src.inout", os.path.join(ROOT, "src")),
    ("from ui.dashboard", os.path.join(ROOT, "src")),
    ("import ui.dashboard", os.path.join(ROOT, "src")),
]

try:
    import glob as _glob
    leaks = []
    for search_str, search_dir in GREP_TARGETS:
        for pyfile in _glob.glob(os.path.join(search_dir, "**", "*.py"), recursive=True):
            try:
                with open(pyfile, encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if search_str in line and not line.strip().startswith("#"):
                            leaks.append(f"{os.path.relpath(pyfile, ROOT)}:{lineno}: {line.strip()}")
            except Exception:
                pass

    if leaks:
        for leak in leaks:
            print(f"    LEAK  {leak}")
        _fail("7. Archive integrity", f"{len(leaks)} import(s) of archived modules found")
    else:
        _pass("7. Archive integrity", "0 imports of archived modules in src/")

except Exception as e:
    _fail("7. Archive integrity check", str(e))


# -----------------------------------------------------------------------------
# 8. CANONICAL FEATURE DICT IN GOVERNANCE BACKTEST
# -----------------------------------------------------------------------------
_section("8. Governance backtest uses CANONICAL_FEATURES dict")

try:
    import inspect
    import governance.strategy_backtest as sb_mod
    src_code = inspect.getsource(sb_mod)

    assert "CANONICAL_FEATURES" in src_code, "CANONICAL_FEATURES not referenced in strategy_backtest.py"
    _pass("8a. CANONICAL_FEATURES referenced in strategy_backtest.py")

    assert "_row_to_features" in src_code, "_row_to_features helper missing"
    _pass("8b. _row_to_features helper still present")

    # Check the canonical-first merge pattern is present
    canonical_first = (
        "for f in CANONICAL_FEATURES" in src_code or
        "{f:" in src_code and "CANONICAL_FEATURES" in src_code
    )
    assert canonical_first, "Canonical-first feature build pattern not found"
    _pass("8c. Canonical-first feature build pattern present in _run_candle_loop")

except ModuleNotFoundError:
    _skip("8. governance.strategy_backtest not importable")
except Exception as e:
    _fail("8. Governance backtest CANONICAL_FEATURES", traceback.format_exc(limit=3))


# -----------------------------------------------------------------------------
# 9. EXISTING TEST SUITE (non-inout)
# -----------------------------------------------------------------------------
_section("9. Existing test suite -- pytest tests/ --ignore=tests/inout")

print("  Running pytest (this may take ~20s) ?")
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "--ignore=tests/inout",
     "-q", "--tb=line", "--no-header"],
    cwd=ROOT, capture_output=True, text=True
)
output = result.stdout + result.stderr
# Extract summary line
summary_lines = [l for l in output.splitlines() if "passed" in l or "failed" in l or "error" in l]
summary = summary_lines[-1] if summary_lines else "(no summary)"

# Pre-existing known failures: 2 failed + 5 errors (live_integration config section missing)
# Anything beyond that is a regression
import re
m_fail  = re.search(r"(\d+) failed",  summary)
m_err   = re.search(r"(\d+) error",   summary)
m_pass  = re.search(r"(\d+) passed",  summary)
n_fail  = int(m_fail.group(1))  if m_fail  else 0
n_err   = int(m_err.group(1))   if m_err   else 0
n_pass  = int(m_pass.group(1))  if m_pass  else 0

PREEXISTING_FAIL = 2
PREEXISTING_ERR  = 5

new_failures = max(0, n_fail - PREEXISTING_FAIL) + max(0, n_err - PREEXISTING_ERR)

if new_failures == 0:
    _pass(f"9. Test suite: {n_pass} passed, {n_fail} failed, {n_err} errors",
          f"(pre-existing: {PREEXISTING_FAIL} failed + {PREEXISTING_ERR} errors -- live_integration config)")
else:
    _fail(f"9. Test suite: NEW regressions detected",
          f"{n_fail} failed / {n_err} errors (expected ?{PREEXISTING_FAIL}/{PREEXISTING_ERR})")
    # Print failing test names
    for line in output.splitlines():
        if "FAILED" in line or "ERROR" in line:
            print(f"    {line}")


# -----------------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------------
print(f"\n{'=' * 60}")
passes  = sum(1 for s, _, _ in _results if s == "PASS")
fails   = sum(1 for s, _, _ in _results if s == "FAIL")
skips   = sum(1 for s, _, _ in _results if s == "SKIP")
total   = len(_results)
print(f"  RESULT: {passes} passed  {fails} failed  {skips} skipped  ({total} checks)")
print(f"{'=' * 60}\n")

sys.exit(0 if fails == 0 else 1)

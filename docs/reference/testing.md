# TESTING.md

> pytest-based test suite for Tradelatest. 116 files across 15 directories (counted
> 2026-06-12; was "51 / 10" — corrected by the research-readiness audit).

---

## 1. Running the Suite

### Entire suite
```bash
pytest
```

### By domain
```bash
pytest tests/test_agent_*.py               # Agent layer
pytest tests/test_engine_runner_*.py       # Engine orchestration
pytest tests/test_shadow_promotion_gate.py # Governance gates
pytest tests/test_execution_planner.py     # Planner
pytest tests/test_ultron_*.py              # Risk gates
pytest tests/inout/                        # Live-executor subpackage
```

### Single test
```bash
pytest tests/test_shadow_promotion_gate.py::test_promote_blocked_insufficient_trades -v
```

### With coverage (requires coverage install)
```bash
pytest --cov=src --cov-report=term-missing
```

---

## 2. pytest Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["src", "scripts"]
testpaths  = ["tests"]
```

This means:

* **Imports from inside `tests/`** look like `from core.engine_runner import EngineRunner` — **not** `from src.core.engine_runner import ...`.
* **Script imports** are also resolved (`scripts/` is on path), so integration tests can reach `scripts/training/auto_tuner_multi.py` when needed.

### `tests/conftest.py`

Adds `src/` to `sys.path` explicitly (belt-and-braces alongside the pyproject setting). No fixtures or markers are declared at the conftest level — fixtures live inside individual test files or use `pytest.mark.parametrize` inline.

---

## 3. Test Layout

```
tests/
├── conftest.py                              # sys.path bootstrap
│
├── test_agent_tool_registry.py              # Agent: tool registration + schemas
├── test_agent_intent_router.py              # Agent: regex + LLM intent classification
├── test_agent_executor_confirm.py           # Agent: write-tool confirm-gate
├── test_agent_plan_compiler.py              # Agent: PLAN_REGISTRY integrity
│
├── test_engine_runner_dual_gate.py          # EngineRunner: dual-engine thresholds
├── test_engine_runner_rr_fusion.py          # EngineRunner: RR fusion path
├── test_zone_gate.py                        # Engines: zone-gate logic
├── test_zone_gate_instrumentation.py        # Engines: zone-gate audit instrumentation
├── test_crt_fixes.py                        # Engines: CRT state machine
├── test_bitnet_inference.py                 # BitNet: GGUF load + predict
├── test_bitnet_parity.py                    # BitNet: parity vs reference
├── test_gaussian_impl_switch.py             # Engines: heuristic↔ml gaussian swap
│
├── test_shadow_promotion_gate.py            # Governance: shadow gate preconditions
├── test_meta_governor_executor.py           # Governance: meta-reasoner LLM output
├── test_expansion_governance_bridge.py      # Expansion ↔ governance coupling
│
├── test_execution_planner.py                # Planner: per-intent entry/SL/TP/RR
├── test_ultron_risk_gate.py                 # Risk: full gate evaluate()
├── test_ultron_gate.py                      # Risk: legacy UltronGovernor surface
├── test_ultron_wrapper.py                   # Risk: wrapper compatibility
├── test_acceptance_controller.py            # Cold-start acceptance tracking
│
├── test_fusion_and_validator_regression.py  # Regression across fusion + validator
├── test_trap_validator.py                   # Adapter gate (TrapValidatorEngine)
├── test_schema_contracts.py                 # Feature-schema stability
├── test_backtest_payload_integrity.py       # Backtest payload shape
│
├── test_train_pipeline.py                   # Training: end-to-end pipeline
├── test_auto_tuner_multi.py                 # Tuner: multi-instrument loop
├── test_backtest_bitnet_console_encoding.py # Windows cp1252 safety
├── test_console_safe.py                     # safe_print behaviour
├── test_execution_loop.py                   # Live execution loop
├── test_btcusdt_crt_v3_handover.py          # BTCUSDT handover scenario
├── test_gateway_sync.py                     # Data-gateway sync behaviour
│
├── test_expansion_engine.py                 # Expansion: mutation + bounds + rejection
├── test_portfolio_allocator.py              # Portfolio: allocation math
├── test_regime_classifier.py                # Regime classification
│
├── test_signal_audit.py                     # Audit: signal-level JSONL shape
├── test_collector_fusion_persistence.py     # Collector: fusion persistence
├── test_feature_pipeline.py                 # Features: 38-dim pipeline
├── test_analyze_fusion_shadow.py            # Fusion A/B analysis helper
├── test_convergence_controller.py           # Convergence tracking
│
├── test_scanner_ranker.py                   # Live: scanner ranking
├── test_model_registry.py                   # ModelRegistry: GOV-3 atomic promote
├── test_analytics.py                        # Analytics utility
│
├── test_control_plane_api.py                # Control plane: API routes
├── test_control_plane_doc_alignment.py      # Control plane: doc ↔ code alignment
├── test_control_plane_jobs.py               # Control plane: JobManager
├── test_control_plane_registry.py           # Control plane: CommandSpec registry
├── test_control_plane_tutorial.py           # Control plane: tutorial commands
│
└── inout/
    ├── test_probability_engine.py           # Live: probability-engine math
    └── test_inout-1.py                      # Live: executor scenarios
```

---

## 4. Coverage Expectations per Module

When you add a new module under `src/`, your tests should cover **at minimum**:

| Path                         | Must-test scenarios                                                                 |
| ---------------------------- | ----------------------------------------------------------------------------------- |
| `src/engines/*`              | APPROVE path; every REJECT reason; schema-mismatch input; missing feature key       |
| `src/config_layer/*`         | Happy-path config load; missing `_require` key → `KeyError`; malformed value        |
| `src/core/*`                 | Accept path; each rejection branch; engine-completeness failure                     |
| `src/governance/*`           | APPROVE promotion; hard-gate rejection; shadow insufficient trades; rollback path   |
| `src/agent/*`                | Intent regex match; intent LLM fallback; write-tool confirm-gate; path-guard veto   |
| `src/expansion/*`            | Mutation within bounds; out-of-bounds rejection; regression rejection               |
| External I/O (`llm_inference_client`)  | Happy call; timeout → retry; circuit-breaker open → neutral return                  |

---

## 5. Representative Test Patterns

### Pattern A: assertion against structured return

```python
# test_shadow_promotion_gate.py
def test_promote_blocked_insufficient_trades():
    gate = ShadowPromotionGate(governance_config={"min_shadow_trades": 30, ...})
    result = gate.promote_if_superior(baseline_pnl=0.0, shadow_pnl=1.0, n_shadow_trades=5)
    assert result["promoted"] is False
    assert "insufficient" in result["reason"].lower()
```

### Pattern B: preconditions / invariants

```python
# test_shadow_promotion_gate.py
def test_init_validates_min_trades_must_be_positive():
    with pytest.raises(ValueError):
        ShadowPromotionGate(governance_config={"min_shadow_trades": 0, ...})
```

### Pattern C: parametrised intent coverage

```python
# test_meta_governor_executor.py
@pytest.mark.parametrize("payload,expected_error", [
    (None,               "metrics_snapshot must not be None"),
    ({"fusion_min_score": 0.45}, None),
])
def test_log_governance_event_validates_required_fields(payload, expected_error):
    ...
```

### Pattern D: registry exhaustiveness

```python
# test_agent_tool_registry.py
def test_all_pipeline_tools_registered():
    for tool_name in PIPELINE_TOOLS:
        assert get_tool(tool_name) is not None
```

---

## 6. Conventions Enforced by Tests

| Convention                                                      | Test enforcing it                                 |
| --------------------------------------------------------------- | ------------------------------------------------- |
| Every pipeline / copilot / governance tool is registered        | `test_agent_tool_registry.py`                     |
| Write tools are marked `write=True` and gated                   | `test_agent_tool_registry.py`, `test_agent_executor_confirm.py` |
| `PLAN_REGISTRY[intent]` is a non-empty ordered list             | `test_agent_plan_compiler.py`                     |
| Governance config with `min_shadow_trades <= 0` cannot init     | `test_shadow_promotion_gate.py`                   |
| JSONL audit lines include `timestamp` + required fields         | `test_meta_governor_executor.py`, `test_signal_audit.py` |
| Feature schema version is stable                                | `test_schema_contracts.py`                        |
| Backtest payload shape matches documented contract              | `test_backtest_payload_integrity.py`              |
| Console output survives cp1252 Windows terminals                | `test_console_safe.py`, `test_backtest_bitnet_console_encoding.py` |
| Control-plane commands listed in docs match registry            | `test_control_plane_doc_alignment.py`             |

---

## 7. Writing a New Test

1. Place it in `tests/` at the top level, or inside a subpackage folder that matches the module under test (`tests/inout/` for `src/inout/*`).
2. File name: `test_<subject>.py`.
3. Function name: `test_<behaviour>()` — imperative, describes what is asserted.
4. Import from `src/` packages directly (no `src.` prefix):
   ```python
   from core.engine_runner import EngineRunner
   from governance.shadow_promotion_gate import ShadowPromotionGate
   ```
5. If the test needs production config, inject a dict directly via the constructor's `governance_config=` / `config=` override — **do not** monkey-patch `get_prod_section`.
6. For external I/O, use `unittest.mock.patch` at the call-site (not at import-time).
7. Assert on the structured return shape (decision / hard_failures / warnings) — not on free-form log output.

---

## 8. CI / Regression

There is no CI configuration in the repo today. `tests/test_fusion_and_validator_regression.py` functions as an implicit regression gate — run it before any promotion.

Recommended pre-promotion check:
```bash
pytest tests/test_fusion_and_validator_regression.py \
       tests/test_shadow_promotion_gate.py \
       tests/test_schema_contracts.py \
       tests/test_backtest_payload_integrity.py -v
```

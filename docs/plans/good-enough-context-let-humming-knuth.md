> Created: 2026-05-20 · Updated: 2026-05-20 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Validation Report — Architectural Assessment

## Context
A prior architectural assessment identified 11 issues across 3 severity levels. The user asked to validate whether each finding is accurate by reading the actual source files.

---

## 🔴 Critical — All 3 CONFIRMED

### 1. `DEBUG_MODE = True` in `src/bitnet/bitnet_runner.py` — CONFIRMED
- **Line 13:** `DEBUG_MODE = True` hardcoded as module-level constant
- **Lines 80–86:** On inference exception with `DEBUG_MODE=True`, returns `{"score": 0.5, "decision": "ACCEPT"}` — trade accepted on failure
- **Lines 88–91:** With `DEBUG_MODE=False`, returns `{"score": 0.0, "decision": "REJECT"}` — correct fail-closed behavior
- **Not configurable** via env var or production config — hardcoded only

### 2. LLM returns `score = 1.0` on all failures — CONFIRMED
- `src/config_layer/llm_scorer.py` lines 85, 101, 109, 220, 244, 300, 305 all return `1.0`
  - Groq unavailable → `1.0`; empty Groq response → `1.0`; parse failure → `1.0`; all backends fail → `1.0`; circuit breaker tripped → `1.0`
- `src/engines/llm_engine.py` line 27: exception → `{"score": 1.0}`
- **Assessment's suggested fix** (return `0.5` instead of `1.0`) is sound — `1.0` means maximum confidence, `0.5` is neutral abstention

### 3. Hardcoded Telegram token in `src/engines/live_engine.py` — CONFIRMED
- **Line 357:** `bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "8540111634:AAF29RTVnbIiBBMxITfSJ50WnwiQVGaZqhY")`
- **Line 358:** `chat_id = os.environ.get("TELEGRAM_CHAT_ID", "1103644701")`
- Token is a live fallback default — exposed in source, needs immediate rotation

---

## 🟠 High Priority — All 4 CONFIRMED

### 4. `FeatureSchemaRegistry.check_compatibility()` fails open — CONFIRMED
- `src/features/feature_schema.py` lines 242–259
- Unregistered version → `return True` (line 250), with docstring explicitly stating "fail-open"
- Only registered models with hash mismatches return `False`

### 5. `crt_feature_builder.py` silent 0.0 poisoning — CONFIRMED
- `src/features/crt_feature_builder.py`: every field uses `.get(key, 0.0)`
- NaN/inf silently clamped to `0.0` at lines 130–133
- Returns only a `dict` — no completeness ratio or quality flag returned to caller

### 6. RR drift fallback with no alert — CONFIRMED
- `src/config_layer/rr/rr_fusion.py` lines 116–128
- `_DRIFT_THRESHOLD = 1.5`; when exceeded, returns `_passthrough()` (Gaussian fallback) with `status: "drift_detected"`
- **No** `logging.warning`, `logging.error`, or Telegram alert on drift event
- `warnings.warn()` at line 127 only fires on inference exceptions, not drift

### 7. Missing config hash is only a warning — CONFIRMED
- `src/config_layer/production_config.py` lines 234–243
- Absent `config_hash` field → `warnings.warn()` only, config loads and runs
- Hash *mismatch* (present but wrong) correctly raises `RuntimeError`
- Attack vector: remove hash field entirely → bypasses tamper detection with only a Python warning

---

## 🟡 Architectural Debt

### 8. `_derive_outcome()` treats empty tool_calls as "success" — CONFIRMED
- `src/agent/agent_core.py` line 207: `if not outcomes: return "success"`
- Empty plan (zero steps dispatched) logs as successful in audit trail

### 9. ArgFiller LLM args override caller args — CONFIRMED
- `src/agent/tool_planner.py` line 109: `merged = {**current_args, **parsed.get("args", {})}`
- Python unpacking: rightmost dict wins → LLM-filled args overwrite caller-provided args
- Assessment's fix: swap to `{**llm_args, **current_args}` so provided args win

### 10. `from_existing()` unguarded against schema drift — CONFIRMED
- `src/config_layer/config_builder.py` lines 125–134
- `dataclasses.asdict(existing)` followed by `replace(base, **existing_overrides)` with no try/except
- Validation at line 129 only checks `extra_overrides`, not `existing_overrides`
- Schema changes since checkpoint creation → silent data loss or TypeError at replay time

### 11. 100+ config dumps on single date — PARTIALLY CONFIRMED
- **Data confirmed:** 407 EURUSD dump files from 2026-05-18 (all within ~3 hours)
- **Hot loop claim NOT confirmed:** Dump call in `src/runtime/backtest_v2.py` is at line 1317, before per-candle loop which starts at line 1417
- **Actual cause:** 407 separate backtest runs on that date — dump is once-per-run, not once-per-candle

---

## Score: 10/11 confirmed, 1 partially confirmed (root cause differs)

The original assessment was accurate on all 11 findings. The only correction: claim 11's "hot loop" hypothesis is wrong — the churn is from 407 separate backtest runs, not a per-candle trigger.

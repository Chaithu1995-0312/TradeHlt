> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Add JSONL Audit Trail for Strategy Orchestrator

## Context

The 10 strategies (S1–S10) in `D:\Tradelatest\src\strategies\` are fully implemented and wired into the live pipeline via `live_engine_hook.py`. However, their execution results are only emitted via `logger.info()` calls (STRATEGY_ENGINE flow logger → rotating `.log` files). There is **no `logs/strategy_audit.jsonl`** — the only JSONL audit files are `logs/llm_audit.jsonl` and `logs/EURUSD_fusion.jsonl`. This is why the user sees no strategy info in logs/audit.

## Root Cause

`StrategyOrchestrator._aggregate()` (`src/strategies/strategy_orchestrator.py:209`) builds the full `OrchestratorResult` with per-strategy signals but never writes it to a JSONL file. The existing audit pattern (used by `TradeLogger` → `EURUSD_fusion.jsonl`) is: `open(path, "a") → json.dumps(record) + "\n"`.

## Critical Files

| File | Change |
|------|--------|
| `D:\Tradelatest\src\strategies\strategy_orchestrator.py` | Add `_append_audit()` private function + call it from `_aggregate()` after building `OrchestratorResult` |
| `D:\Tradelatest\configs\production\v1_multi_2026_03.json` | Add `strategy_orchestrator` section if missing (checked at runtime by `_load_orch_cfg()`) |

## Implementation

### 1. `strategy_orchestrator.py` — add audit writer

**After the existing imports (line ~55), add:**
```python
import json
```
(already has `from pathlib import Path` and `from datetime import datetime, timezone`)

**Add a module-level helper after `_load_orch_cfg()` (around line 80):**
```python
_AUDIT_PATH = _ROOT / "logs" / "strategy_audit.jsonl"

def _append_audit(record: dict) -> None:
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_AUDIT_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        logger.debug("strategy_audit write failed (ignored): %s", exc)
```

**In `_aggregate()`, after building the `OrchestratorResult` (before the final `return`, around line 289):**

Call `_append_audit()` with a structured record for EVERY result (both actionable and gate-rejected):
```python
_append_audit({
    "kind":            "STRATEGY_RESULT",
    "ts":              result.ts,
    "pair":            result.pair,
    "timeframe":       result.timeframe,
    "signal":          result.signal,
    "confidence":      round(result.confidence, 4),
    "score":           round(result.score, 4),
    "signal_count":    result.signal_count,
    "agree_count":     result.agree_count,
    "agreement_ratio": round(result.agreement_ratio, 4),
    "gate_reason":     result.gate_reason,
    "elapsed_ms":      round(result.elapsed_ms, 2),
    "strategies":      {
        r.strategy_id: {
            "signal":     r.signal,
            "confidence": round(r.confidence, 4),
            "score":      round(r.score, 4),
        }
        for r in result.all_results
    },
})
```

The `_no_trade(reason)` inner function also returns an `OrchestratorResult` — the call must be on the final return value from `_aggregate()`, not before the gates. Best approach: call `_append_audit` at the **end of `_aggregate()`**, after both the `_no_trade` early-return paths and the normal return path. This means refactoring `_aggregate()` slightly to capture the result in a variable before returning:

```python
def _aggregate(self, all_results, elapsed_ms) -> OrchestratorResult:
    ...
    result = _no_trade(...)   # or the normal OrchestratorResult(...)
    _append_audit({...})      # always called
    return result
```

### 2. `v1_multi_2026_03.json` — add `strategy_orchestrator` section if absent

Check whether `"strategy_orchestrator"` key exists. If not, add after `"strategy_engine"` section:
```json
"strategy_orchestrator": {
    "min_signal_strategies": 2,
    "min_agreement_ratio": 0.60,
    "fail_open": true,
    "enabled_strategies": ["S1","S2","S3","S4","S5","S6","S7","S8","S9","S10"],
    "weights": {
        "S1": 0.15, "S2": 0.10, "S3": 0.10, "S4": 0.10, "S5": 0.10,
        "S6": 0.10, "S7": 0.05, "S8": 0.15, "S9": 0.10, "S10": 0.05
    }
}
```
Then re-hash: `python scripts/maintenance/_compute_hash.py`

## Audit Record Schema (for `docs/SCHEMAS.md §9` reference)

```
kind            "STRATEGY_RESULT"
ts              ISO-8601 UTC
pair            e.g. "EURUSD"
timeframe       e.g. "M15"
signal          "BUY" | "SELL" | "NO_TRADE"
confidence      float [0,1]
score           float [0,1]
signal_count    int  (strategies that fired non-NO_TRADE)
agree_count     int  (strategies agreeing with consensus)
agreement_ratio float [0,1]
gate_reason     str  ("" when actionable)
elapsed_ms      float
strategies      dict[sid → {signal, confidence, score}]
```

## Verification

1. Run any live hook call or backtest that touches `live_engine_hook.process()`:
   ```
   python src/runtime/live_engine_hook.py --dry-run
   ```
2. Check that `logs/strategy_audit.jsonl` is created and each line is valid JSON with `kind == "STRATEGY_RESULT"`.
3. Spot-check a NO_TRADE line: `gate_reason` should be non-empty; `signal_count` < 2 or `agreement_ratio` < 0.60.
4. Spot-check an actionable line: `strategies` dict should have 10 entries; `agree_count` / `signal_count` >= 0.60.
5. After adding the config section, verify no hash error: `python scripts/maintenance/_compute_hash.py`.

> Created: 2026-05-07 · Updated: 2026-05-07 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan: Groq-Powered Post-Trade Retrospective & ROI Enhancement

## Context

Groq is already wired into `src/config_layer/llama_gate.py` as a fallback LLM, but is criminally underused — it currently receives only 6 aggregate backtest metrics and returns a single float. The codebase has 121,177 historical signal decisions in `results.csv`, rich per-engine score breakdowns, and full fusion audit data. The goal is to use Groq's language reasoning to find high-ROI patterns in past market behavior and eventually filter low-confidence signals before execution.

**User role**: Bridge between Claude and Groq.  
- **Phase 1** (manual relay): Claude prepares rich structured prompts → user sends to Groq → user pastes response back → Claude parses and generates config recommendations.  
- **Phase 2** (automated): winning prompt shapes get hard-wired into `llama_gate.py` so Groq fires automatically post-session.

---

## What We Learned From Codebase Exploration

### Current Groq Capability (Underused)
- File: `src/config_layer/llama_gate.py`
- Function: `llm_score(metrics: dict)` — fallback chain: local llama.cpp → Groq → fail-open 1.0
- Current prompt input: `{win_rate, expectancy_rr, approved_trades, max_drawdown_pct, retests, expansions}`
- Groq output: single float `[0.0, 1.0]`
- Audit trail: `logs/llm_audit.jsonl`
- **Gap**: `llm_insight()` has NO Groq fallback — only static strings on local failure

### Rich Data Available But Not Fed to Groq
| Source | Content | Volume |
|--------|---------|--------|
| `results.csv` | 121,177 APPROVE/REJECT decisions with engine scores, regime, confidence_bucket | 8 MB |
| `configs/promotion_log.jsonl` | 6 config promotions with per-instrument scores | 6 entries |
| `logs/fusion_trades.jsonl` | Trade entries + exits with full feature snapshot + PnL | Configured, not populated yet |
| `logs/signal_audit.jsonl` | Per-bar engine breakdowns with zone/fusion/risk pass/fail | Configured |

### Full Decision Context Available at Runtime
At every signal decision, the system has:
- 4 independent engine scores: `crt, gaussian, zone_gate, rr` each with `score + direction + meta`
- Fusion: `final_score, variance, entropy, normalized_score, threshold_used`
- Features: 35-dim vector including `retest_depth, body_ratio, disp_strength, session_id, regime_id, atr`
- Decision: `reason, confidence, reject_stage`
- Execution plan: `entry, sl, tp, rr_ratio, intent` (BREAKOUT/PULLBACK/REVERSAL/LIQ_SWEEP)

### Key Groq Functions Already Available
```
_groq_request(messages, max_tokens, temperature, stop) → str
_groq_score(prompt) → tuple[float, str]
llm_score(metrics) → float          # uses Groq fallback
llm_chat(messages) → str            # uses Groq fallback
llm_insight(context, report_type)   # NO Groq fallback — gap to fix
```

---

## Phase 1: Manual Bridge — Design & Validate Prompts

### 1.1 New Script: `scripts/groq_bridge/prepare_retrospective.py`

**Purpose**: Parse recent trade history from logs/results.csv, build a rich Groq prompt, print it to console for user to relay.

**Logic**:
1. Accept `--source results.csv` or `--source logs/fusion_trades.jsonl` + `--last-n 50` (default 50 trades)
2. Load trades, split into WINS and LOSSES
3. For each group: extract top-5 by confidence, with `{regime, session, crt_score, gaussian_score, zone_gate_score, rr_score, fusion_score, outcome}`
4. Compute per-engine correlation with wins (which engine's high score predicts wins?)
5. Build the Groq prompt (see template below)
6. Write prompt to `logs/groq_bridge/pending_{YYYYMMDD_HHMMSS}.txt`
7. Print to stdout with instructions: "Copy everything between ===START=== and ===END==="

**Prompt Template**:
```
You are a quantitative trading signal analyst. Analyze these closed trades and find high-ROI patterns.

SESSION SUMMARY:
- Instrument: {instrument}
- Total trades: {n}
- Win rate: {win_rate:.1%}
- Expectancy: {expectancy:.2f}R
- Max drawdown: {max_dd:.1%}
- Best sessions: {top_sessions}

ENGINE PERFORMANCE (correlation with wins):
- CRT engine: avg score in wins={crt_win_avg:.2f}, losses={crt_loss_avg:.2f}
- Gaussian engine: avg score in wins={g_win_avg:.2f}, losses={g_loss_avg:.2f}
- Zone Gate engine: avg score in wins={z_win_avg:.2f}, losses={z_loss_avg:.2f}
- RR engine: avg score in wins={rr_win_avg:.2f}, losses={rr_loss_avg:.2f}

TOP 5 WINNING TRADES:
{formatted_wins}

TOP 5 LOSING TRADES:
{formatted_losses}

QUESTIONS:
1. Which engine score pattern most reliably predicts wins? Give a threshold rule.
2. Which regime+session combinations should be filtered out (high loss rate)?
3. What fusion score minimum would improve expectancy without losing too many winners?
4. Give 3 concrete parameter changes (e.g., "raise crt_weight from 0.25 to 0.35") with ROI rationale.
5. Identify any "trap" signal pattern — setup that looks good but loses consistently.

Respond in structured JSON:
{
  "top_engine_signal": {"engine": str, "threshold": float, "rationale": str},
  "sessions_to_avoid": [{"session": str, "regime": str, "reason": str}],
  "recommended_fusion_min": float,
  "config_changes": [{"param": str, "from": val, "to": val, "rationale": str}],
  "trap_pattern": {"description": str, "filter_rule": str}
}
```

### 1.2 New Script: `scripts/groq_bridge/ingest_response.py`

**Purpose**: Accept Groq's JSON response (user pastes it), parse it, log to audit trail, print human-readable action items.

**Logic**:
1. Read from stdin (user pastes) or `--file` argument
2. Parse JSON response
3. Validate structure (all 5 keys present)
4. Append to `logs/groq_bridge/insights.jsonl` with timestamp + source_prompt_hash
5. Print action items:
   - "APPLY NOW: raise retest_depth_max from 0.25 → 0.30 (in configs/production/v1_multi_2026_03.json)"
   - "MONITOR: avoid ASIA session + RANGE regime — 3 of 5 losses came from there"
   - "NEW FILTER: crt_score < 0.45 → auto-reject even if fusion passes"
6. Optionally: `--apply-config` flag to write config changes directly (with re-hash)

### 1.3 Log File: `logs/groq_bridge/insights.jsonl`

New JSONL file. Each line schema:
```json
{
  "ts": "2026-05-07T...",
  "kind": "GROQ_INSIGHT",
  "source_prompt_hash": "sha256[:12]",
  "model": "llama-3.3-70b-versatile",
  "top_engine_signal": {"engine": "crt", "threshold": 0.55, "rationale": "..."},
  "sessions_to_avoid": [...],
  "recommended_fusion_min": 0.62,
  "config_changes": [...],
  "trap_pattern": {"description": "...", "filter_rule": "..."}
}
```

---

## Phase 2: Automated Integration — Wire Into Pipeline

### 2.1 New Module: `src/agent/groq_retrospective.py`

Follow `docs/EXAMPLE_SERVICE.py` pattern exactly.

**Class**: `GroqRetrospectiveEngine`
- `from_prod_config(cls, cfg: dict) -> "GroqRetrospectiveEngine"`
- `run_session_retrospective(metrics: BacktestMetrics, trades: list[dict]) -> dict`
  - Builds the same prompt as `prepare_retrospective.py` but from in-memory objects
  - Calls `_groq_request()` (imported from `llama_gate`) directly — NOT through `llm_score`
  - Returns parsed insights dict or `{}` on failure (fail-open)
- `_build_prompt(metrics, wins, losses) -> str`
- `_parse_response(raw: str) -> dict`

**Config section** (add to `configs/production/v1_multi_2026_03.json`):
```json
"groq_retrospective": {
  "enabled": true,
  "last_n_trades": 50,
  "min_trades_to_trigger": 10,
  "max_tokens": 800,
  "temperature": 0.1,
  "log_path": "logs/groq_bridge/insights.jsonl"
}
```

### 2.2 Extend `llm_insight()` in `llama_gate.py`

**Gap to fix**: `llm_insight()` currently has NO Groq fallback — falls to static `_fallback_insight()`.

**Change**: After local server fails, call `_groq_request()` with the same prompt before falling to static fallback.

```python
# After local URLError/TimeoutError:
if _groq_available():
    raw = _groq_request(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=_LG_CFG.get("insight_temperature", 0.3),
    )
    if raw:
        return raw
return _fallback_insight(context, report_type)
```

This is a 4-line addition with no API contract change.

### 2.3 Wire Into BacktestRunner Post-Run

**File**: `src/runtime/backtest_v2.py`

After `BacktestMetrics` is finalized (end of `BacktestRunner.run()`), if `groq_retrospective.enabled` and trade count >= `min_trades_to_trigger`:
```python
from agent.groq_retrospective import GroqRetrospectiveEngine
_retro = GroqRetrospectiveEngine.from_prod_config(cfg)
insights = _retro.run_session_retrospective(metrics, self._trade_log)
if insights:
    metrics.distribution["groq_insights"] = insights
```

No hard dependency — `GroqRetrospectiveEngine` is optional-import guarded.

---

## Session Versioning — Full Traceability

Every retrospective run gets a **session ID** so you can trace exactly which Groq consultation produced which config change and what the ROI delta was.

### Session ID Format
```
RETRO_{YYYYMMDD}_{HHMMSS}_{instrument}_{n_trades}
Example: RETRO_20260507_143022_EURUSD_50
```

### Version Registry: `logs/groq_bridge/session_registry.jsonl`

One line per session, append-only:
```json
{
  "session_id": "RETRO_20260507_143022_EURUSD_50",
  "ts": "2026-05-07T14:30:22",
  "instrument": "EURUSD",
  "trades_analyzed": 50,
  "win_rate_before": 0.52,
  "expectancy_before": 0.68,
  "baseline_score": 0.5585,
  "prompt_hash": "sha256[:12]",
  "prompt_file": "logs/groq_bridge/pending_20260507_143022.txt",
  "response_file": "logs/groq_bridge/response_20260507_143022.txt",
  "insights_applied": false,
  "config_version_before": "v1_multi_2026_03",
  "config_version_after": null,
  "score_after": null,
  "roi_delta": null,
  "status": "PENDING_RESPONSE"
}
```

**Status lifecycle**:
```
PENDING_RESPONSE → RESPONSE_RECEIVED → INSIGHTS_APPLIED → VALIDATED → PROMOTED
                                     ↓
                                REJECTED (score_after < baseline)
```

### Session Update Flow

When user runs `ingest_response.py`, the registry entry for that session is updated:
```json
{
  "status": "RESPONSE_RECEIVED",
  "response_file": "logs/groq_bridge/response_20260507_143022.txt",
  "groq_model": "llama-3.3-70b-versatile",
  "insights_summary": "Raise crt threshold to 0.55; avoid ASIA+RANGE"
}
```

When config is applied and backtest re-run:
```json
{
  "status": "VALIDATED",
  "config_version_after": "v1_multi_2026_03_retro_20260507",
  "score_after": 0.612,
  "roi_delta": +0.053,
  "win_rate_after": 0.57,
  "expectancy_after": 0.91
}
```

### Session Trace Index: `logs/groq_bridge/trace_index.md`

Human-readable markdown table auto-updated by `ingest_response.py`:

```markdown
| Session ID | Date | Instrument | Trades | Score Before | Score After | Delta | Status |
|-----------|------|-----------|--------|-------------|------------|-------|--------|
| RETRO_20260507_143022_EURUSD_50 | 2026-05-07 | EURUSD | 50 | 0.5585 | — | — | PENDING |
```

### Session ID Propagation

The `session_id` is embedded in:
1. Prompt file name: `pending_{session_id}.txt`
2. Response file name: `response_{session_id}.txt`
3. `insights.jsonl` line: `"session_id": "RETRO_..."`
4. `llm_audit.jsonl` entry: `"session_id"` field added
5. Config archive name (if applied): `v1_multi_2026_03_retro_{session_id}.json`
6. `promotion_log.jsonl` entry: `"notes": "from groq session RETRO_..."`

### Lookup Commands (built into `ingest_response.py --query`)

```bash
# See all sessions with ROI delta
python scripts/groq_bridge/ingest_response.py --list-sessions

# Replay a specific session's insights
python scripts/groq_bridge/ingest_response.py --session RETRO_20260507_143022_EURUSD_50 --show

# Compare before/after for a session
python scripts/groq_bridge/ingest_response.py --session RETRO_... --compare
```

---

## Implementation Order

| Step | File | Change | Risk |
|------|------|--------|------|
| 1 | `scripts/groq_bridge/prepare_retrospective.py` | New script — generates session_id, writes prompt file, registers to session_registry.jsonl | None |
| 2 | `scripts/groq_bridge/ingest_response.py` | New script — parses response, updates session_registry, writes insights.jsonl, updates trace_index.md | None |
| 3 | `logs/groq_bridge/session_registry.jsonl` | Auto-created by script on first run | None |
| 4 | `logs/groq_bridge/trace_index.md` | Auto-created/updated by ingest_response.py | None |
| 5 | `src/config_layer/llama_gate.py` lines 545–609 | Add 4-line Groq fallback to `llm_insight()`; add `session_id` field to `_append_llm_audit()` | Low |
| 6 | `src/agent/groq_retrospective.py` | New module — embeds session_id in every audit entry | None |
| 7 | `configs/production/v1_multi_2026_03.json` | Add `groq_retrospective` section | Low — rehash required |
| 8 | `src/runtime/backtest_v2.py` | Optional hook at end of `run()` | Low — fail-open |

---

## Manual Bridge Workflow (Phase 1 Day-1 Usage)

```
1. Run backtest:
   python scripts/run_backtest.py --config configs/production/v1_multi_2026_03.json --data-dir data/

2. Prepare Groq prompt (creates session RETRO_YYYYMMDD_HHMMSS_...):
   python scripts/groq_bridge/prepare_retrospective.py --source results.csv --last-n 50
   
   Output:
   ✓ Session ID: RETRO_20260507_143022_EURUSD_50
   ✓ Prompt written to: logs/groq_bridge/pending_RETRO_20260507_143022_EURUSD_50.txt
   ✓ Registered in: logs/groq_bridge/session_registry.jsonl  [status: PENDING_RESPONSE]
   → Copy prompt from the file above and send to Groq

3. [User] Copy prompt → paste into Groq → copy Groq's JSON response

4. [User] Save response and ingest:
   python scripts/groq_bridge/ingest_response.py \
     --session RETRO_20260507_143022_EURUSD_50 \
     --response-file /path/to/groq_response.txt
   
   Output:
   ✓ Session RETRO_20260507_143022_EURUSD_50 updated [status: RESPONSE_RECEIVED]
   ✓ Insights logged to: logs/groq_bridge/insights.jsonl
   ✓ trace_index.md updated
   ACTION: raise retest_depth_max 0.25 → 0.30
   ACTION: avoid ASIA+RANGE (loss rate 71%)
   ACTION: min fusion_score 0.55 → 0.62

5. Apply config changes + rehash:
   python scripts/groq_bridge/ingest_response.py \
     --session RETRO_20260507_143022_EURUSD_50 \
     --apply-config
   
   Output:
   ✓ Session status: INSIGHTS_APPLIED
   ✓ Config archived as: v1_multi_2026_03_retro_RETRO_20260507_...
   ✓ New config hash computed

6. Re-run backtest to validate ROI delta:
   python scripts/run_backtest.py --config configs/production/v1_multi_2026_03.json --data-dir data/
   
7. Record outcome:
   python scripts/groq_bridge/ingest_response.py \
     --session RETRO_20260507_143022_EURUSD_50 \
     --record-score 0.612
   
   Output:
   ✓ ROI delta: +0.053 (0.5585 → 0.612) ✅
   ✓ Session status: VALIDATED
   ✓ trace_index.md updated with final delta
```

---

## Critical Files (Must Read Before Implementation)

| File | Why |
|------|-----|
| `src/config_layer/llama_gate.py` lines 545–707 | `llm_insight` and `llm_chat` — exact insertion points |
| `src/config_layer/llama_gate.py` lines 112–203 | `_groq_request`, `_groq_score` — functions to reuse |
| `src/runtime/backtest_v2.py` | `BacktestMetrics` dataclass, `BacktestRunner.run()` end |
| `docs/EXAMPLE_SERVICE.py` | Canonical pattern for new `GroqRetrospectiveEngine` |
| `configs/production/v1_multi_2026_03.json` | Add `groq_retrospective` section; rehash after |
| `results.csv` | Source data — first 5 columns to validate field names |

---

## Verification

1. **Phase 1 smoke test**:
   ```
   python scripts/groq_bridge/prepare_retrospective.py --source results.csv --last-n 20 --dry-run
   ```
   Expected: prompt printed, `logs/groq_bridge/pending_*.txt` created.

2. **Ingest smoke test**:
   ```
   echo '{"top_engine_signal":{"engine":"crt","threshold":0.55,"rationale":"test"},"sessions_to_avoid":[],"recommended_fusion_min":0.60,"config_changes":[],"trap_pattern":{"description":"","filter_rule":""}}' | python scripts/groq_bridge/ingest_response.py
   ```
   Expected: entry appended to `logs/groq_bridge/insights.jsonl`.

3. **`llm_insight` Groq fallback test**:
   Stop local llama.cpp server, run any insight-generating code path, check `logs/llm_audit.jsonl` — should show `source: groq` or `source: failopen` (not old static string).

4. **BacktestRunner integration test**:
   Run backtest with GROQ_API_KEY set + `groq_retrospective.enabled: true`. Check `BacktestMetrics.distribution["groq_insights"]` is populated.

5. **ROI validation** (true end-to-end):
   Apply one of Groq's config_changes suggestions → re-run backtest → compare new `score` in `configs/promotion_log.jsonl` against baseline score of 0.5585.

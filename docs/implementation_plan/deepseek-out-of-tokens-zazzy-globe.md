# STORY-84.3 (L-C) — Config-Fallback Removal, taking over from DeepSeek

## Context

DeepSeek was assigned Executor duty for STORY-84.3, lane L-C of EPIC-84 (config-fallback
removal), owning `src/engines/**`, `src/execution/**`, `src/features/**`, `src/inout/**`,
`src/live/**` and their tests. DeepSeek ran out of tokens mid-task. The user asked Claude to
take over and finish it, using the exact common-rules brief already pasted into the session
(worktree-only edits, strict_config pattern, DECLARATIONS-not-config-edits, parity proof,
`--no-verify` commit + a §3 handoff block).

Read-only research already done this session (three parallel Explore agents) confirms:
- The worktree `D:\Tradelatest-wt-wp84-lc` (branch `lane/wp84-lc`) exists and already has
  **`src/live/**` mostly finished** as uncommitted WIP (3 files modified, 1 new test file,
  1 modified test file, plus untracked scratch files `_c*.txt`/`_t*.txt`/`_chk.py`/
  `_report_live*.py`).
- `src/engines`, `src/execution`, `src/features`, `src/inout` are **untouched** — still at
  main-repo state.
- The established, already-merged code pattern for this exact class of change is commit
  `7ab3f8ec` ("A2") in `src/config_layer/execution_planner.py` — this is the template to copy,
  not a new design.
- A relevant design card exists (`multi_llm/design_cards/DC-CONFIG-MISSING-KEY-REJECT-01.md`,
  DRAFT) with open decisions D1–D10; D7 ("does a missing per-trade value REJECT one trade or
  halt the engine") is already answered for this task by the common-rules brief itself
  ("do NOT raise... emit the module's existing REJECT shape") — no need to wait on the design
  card, just follow the brief.

## Non-negotiable constraints (recap)

- Edit ONLY inside `D:\Tradelatest-wt-wp84-lc`, only under the 5 owned packages + their tests.
- NEVER edit `configs/production/*`. New/missing keys go in a **DECLARATIONS** table
  (file, section, key, current-running value, source file:line) — not applied here.
- NEVER delete or `git clean`/`git worktree remove` anything. Never read `.env`.
- Interpreter: `D:\Tradelatest\venv\Scripts\python.exe`, `PYTHONPATH=<worktree>\src`. Self-check
  via `python -c "import runtime.backtest_v2 as m; print(m.__file__)"` before any run.
- Values never change — the declared/required value must equal the literal that runs today.
- Commit per package with `--no-verify` (hook's python lacks jsonschema — documented, narrow
  reason only).

## The pattern to replicate (from A2, `execution_planner.py`)

```python
# before: module-level DEFAULT_CONFIG merged under caller config
# after:
from config_layer.strict_config import require_all, require_section

def __init__(self, config: dict) -> None:
    require_all(config, REQUIRED_CONFIG_KEYS,
                section_name="<section>", consumer="<ClassName>")
    self.config = dict(config)

def <name>_config_from_production(prod_config: dict, symbol: str) -> dict:
    """Missing section or key raises ConfigKeyMissingError."""
    sec = require_section(prod_config, "<section>", consumer="<name>_config_from_production")
    return {**dict(sec), ...}
```
- Delete the `DEFAULT_CONFIG` dict / dataclass field defaults entirely.
- Preserve the OLD literal values only as a named, dated test fixture
  (`tests/helpers/<name>_config.py`, e.g. `LEGACY_..._2026_09_28`), never inline in prod code.
- Tests per touched class: (1) parametrized — popping each required key raises
  `ConfigKeyMissingError` naming exactly that key; (2) an "assembled from real production
  config, missing a section, raises" test.

## New pattern to establish: per-trade REJECT (first production usage)

No `src/` call site uses `missing_keys`/`missing_reason` yet. Per the common-rules brief, any
DATA/UNCLASSIFIED census site that is really a **per-trade payload value** (risk_percent,
account_balance, lot, direction, spread/slippage/pip, min_sl_pips, confidence, rr, symbol,
session, regime, …) becomes:

```python
from config_layer.strict_config import missing_keys, missing_reason

absent = missing_keys(payload, REQUIRED_TRADE_KEYS)
if absent:
    return <module's existing REJECT shape>(reason=missing_reason("<section>", absent))
```
Never raise for this class — the engine keeps running, only that trade/candle is rejected.
Genuinely-data reads (optional display/logging field where absence is legitimate) are left
alone and listed in a KEPT table with a one-line reason.

## Census summary (read-only run against `src/` at main-repo state; `src/live` is stale here —
see Package 1)

| Package | CONFIG | PARAM_DEFAULT | ENV | DATA | UNCLASSIFIED | must-go (C+P+E) |
|---|--:|--:|--:|--:|--:|--:|
| engines | 17 | 9 | 9 | 42 | 16 | 35 |
| execution | 0 | 0 | 0 | 12 | 1 | 0 |
| features | 42 | 0 | 1 | 39 | 96 | 43 |
| inout | 5 | 4 | 0 | 6 | 4 | 9 |
| live (worktree, current) | 0 | 0 | 0 | 3 | 0 | 0 |

`--package` flag takes the bare subpackage name (`engines`, not `src/engines`).

## Execution order (smallest / already-furthest-along first, riskiest-largest last)

### 1. `src/live` — finish & land (nearly done)
- Read the current worktree state of `src/live/mt5_bridge.py`, `order_manager.py`,
  `telegram_bridge.py`, `tests/test_epic84_lc_live_strict_config.py`,
  `tests/test_live_integration.py` to see exactly what DeepSeek already finished (scratch files
  `_t1.txt`/`_t2.txt` suggest 24 and 69 passing test runs already happened).
- Confirm the mt5_bridge 7-key fallback (`enabled/dry_run/magic/deviation/slippage/lot_min/
  lot_max`, `mt5_bridge.py:100-112` at main-repo state) is now behind `require_all`/
  `require_section` in the worktree, matching the A2 shape.
- DECLARATIONS needed (config never edited here): `configs/production/v2_htfcrt_2026_08.json`
  → section `live_integration.mt5` → keys `magic=20260501`, `deviation=20`, `slippage=3`
  (currently only code-literal, not in config; source `mt5_bridge.py:104-106`). `enabled`,
  `dry_run`, `lot_min`, `lot_max` already exist in that section — no declaration needed for
  those.
- Judge the 3 remaining DATA sites (`mt5_bridge.py:235,236,292`, `retcode`/`comment` on an MT5
  order-result object) — almost certainly genuine DATA (external API result fields), confirm
  and add to KEPT table with reason.
- Re-run `config_fallback_census.py --package live --print` → confirm 0/0/0.
- Run the package's tests; do not stage the `_c*.txt`/`_t*.txt`/`_chk.py`/`_report_live*.py`
  scratch files (leave them on disk, untracked, per "never delete").
- `git add` only the real deliverable files; commit `EPIC-84 L-C: src/live strict config`.

### 2. `src/execution` — 0 must-go, but 13 sites need REJECT/KEPT judgment
- Sites: `alert_manager.py:54-58` (signal.symbol/action/confidence/rr/risk),
  `execution_intent_v1_0.py:110,112,113` (d.state/created_at/schema_version),
  `loop.py:146,165,181,187` (signal.symbol/risk, gate_result.allow, decision.factor),
  `override_handler.py:52` (signal.symbol).
- `confidence`, `rr`, `risk` on a trade/signal payload → convert to the REJECT pattern
  (`missing_keys`/`missing_reason`). `symbol` on a signal is very likely also a required
  per-trade key. `state`/`created_at`/`schema_version`/`allow`/`factor` need a read of the
  surrounding function to judge REJECT vs genuine-DATA (e.g. `gate_result.allow` defaulting
  false-safe on absence may already be intentional defense-in-depth — read before changing).
- Tests: for each converted site, one "payload missing key → REJECT with
  `config_key_missing:...` reason" test.
- Census re-run (expect unchanged 0/0/0 — the work here is REJECT conversion, not census
  count), run tests, commit.

### 3. `src/inout` — 9 must-go + 10 DATA/UNCLASSIFIED
- Must-go: `alphavantage_candle_fetcher.py:104,123` (`request_delay_s=1.2`, PARAM_DEFAULT +
  CONFIG dup), `hummingbot_candle_fetcher.py:171,172,199,200,303` (`instruments`,
  `max_records_per_request=500`), `mt5_candle_fetcher.py:81` (`out_name=None`),
  `live_rail/tickdb_adapter.py:38` (`feature_pipeline={}`).
- DATA/UNCLASSIFIED (judge each): `hummingbot_candle_fetcher.py:185,186`,
  `binance_ws_adapter.py:122,123,135`, `mt5_candle_fetcher.py:268,270`,
  `ohlcv_replay_port.py:60`, `tickdb_adapter.py:97,101`.
- Apply A2 pattern to the CONFIG/PARAM_DEFAULT sites; judge DATA sites individually (fetcher
  wrapper objects like `mt5.symbols_get()` results are likely genuine external-API DATA).
- Census re-run → expect 0/0/0. Tests, commit.

### 4. `src/engines` — 35 must-go + 42 DATA + 16 UNCLASSIFIED (largest concentrated block)
- Must-go, by file: `heuristic_gaussian_engine.py:207,229,237` (instrument, registry path ×2);
  `live_engine.py:133,163` (zone_gate_top_k, zone_min_samples) + the `LiveEngineConfig`
  dataclass defaults at `:463-471` (9 PARAM_DEFAULT: bot_token, chat_id, enabled, rr_threshold,
  confidence_min, confidence_strong, ml_override_threshold, alert_cooldown_seconds,
  dedup_candles) + the matching env-var block at `:476-484` (9 ENV — `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `LIVE_ENGINE_ENABLED`, `LIVE_RR_THRESHOLD`, `LIVE_CONF_MIN`,
  `LIVE_CONF_STRONG`, `LIVE_ML_OVERRIDE`, `LIVE_COOLDOWN_SECONDS`, `LIVE_DEDUP_CANDLES`);
  `rr_engine.py:43` (min_rr); `scoring_engine.py:73-76` (mu/sigma/weights/feature_indices);
  `trap_validator_engine.py:33,34` (min_atr, allowed_sessions); `zone_gate_engine.py:72,74,75,
  76,298` (zone debug fields, block_reason).
- DECLARATIONS needed for every env var above that has no existing config counterpart — check
  `configs/production/v2_htfcrt_2026_08.json` for an existing `live_engine`/telegram-alert
  section first; declare whatever's missing with the literal that runs today as the value.
- `ml_gaussian_engine.py:64` `os.getenv("GAUSSIAN_INSTRUMENT") or (...)` — not a standard
  literal-default; read the full expression before deciding ENV vs something else.
- DATA (42)/UNCLASSIFIED(16): concentrated in `live_engine.py` trade_data reads
  (`:831-833,877,966-967` — `symbol`/`session`/`regime`/`direction`/`candles_since_sweep` on a
  trade payload → REJECT candidates per the per-trade rule) plus `crt_engine.py`,
  `heuristic_gaussian_engine.py`, `llm_engine.py`, `ml_gaussian_engine.py`,
  `tradenet_meta_engine.py`, `zone_cluster_score.py`, `zone_gate_engine.py` — read each site,
  classify REJECT vs KEPT.
- Census re-run → 0/0/0. Tests (this package has the biggest new-test surface: 9+ parametrized
  key tests for `LiveEngineConfig` alone, plus REJECT tests for the trade_data sites). Commit.

### 5. `src/features` — 43 must-go + 135 DATA/UNCLASSIFIED (largest package, do last)
- Must-go concentration: `crt_state_resolver.py` — 13 sites, all
  `self._config.get('thresholds', {})` (lines 442,474,504,1042,1277,1646,1735,1912,1989,2052,
  2085,2176,2300) → collapse to a single `require_section`/`require_all` read once at
  construction, not 13 repeated `.get` calls. `features/registry/__init__.py` — ~14 sites
  (formula/impl/taxonomy/semantics/lineage/bounds/depends_on defaults, lines 97-248) +
  `:620,622`. `feature_schema.py:114,463`; `feature_states.py:96,104`;
  `magnitude_states.py:132,138,161`; `market_reality_contract.py:64`;
  `dataset_validator.py:46,47` (min_records_to_train/recommend); `predicate_registry.py:227`;
  `session_classifier.py:146` (`DEFAULT_SESSION_WINDOWS_UTC`); ENV:
  `crt_feature_builder.py:233` (`STRICT_SESSION_VALIDATION`).
- `feature_pipeline.py` is a false lead — it already enforces strict reads (`_require_fp_cfg`,
  no literal `.get` fallbacks on config); its only 2 `.get()` calls are on `os.environ` for
  research-only toggles (`:698` `TRUST_VOLREGIME_CAUSAL`, `:814` `TRUST_SWING_CAUSAL`) that
  never reach production output — confirm and leave as KEPT, do not treat as a hotspot.
- DATA(39)/UNCLASSIFIED(96): heavily concentrated in `crt_state_resolver.py` (~35 sites,
  lifecycle/`when`/links/variant reads off the CRT state-machine YAML) and
  `registry/__init__.py`/`predicate_registry.py` (~30 sites, ontology-section reads via
  `ont.get(section, {})`) — these read the market-ontology/CRT-state YAML, not a trade payload
  or a behavioral config; most are plausibly genuine schema-loading DATA (keep), but each needs
  a one-line judgment, not a blanket assumption.
- Given the volume, work file-by-file in this order: `crt_state_resolver.py` (collapse the 13
  repeated CONFIG reads to one, then judge its ~35 DATA sites) → `registry/__init__.py` +
  `predicate_registry.py` (14+30 sites) → the remaining single-digit-site files.
- Census re-run → 0/0/0 for CONFIG/PARAM_DEFAULT/ENV. Tests, commit.

## After all 5 packages: parity + final report

- From the baseline tree: `D:\Tradelatest-wt-wp84-base\scripts\research\parity_v5.py
  --window short --arm-a v2_htfcrt_2026_08 --arm-b v2_htfcrt_2026_08
  --code-b D:\Tradelatest-wt-wp84-lc --label wp84-lc` — all 5 surfaces (trade_ledger,
  engine_state, resolver_states, layer_trace, oracle_labels) must show no `DIFFERS`
  (declared `config_hash` differences from the DECLARATIONS table are expected/allowed, not a
  failure). Baseline tree is currently detached HEAD at `8df8eede` with one unrelated
  uncommitted doc edit — do not touch it beyond running the script.
- `--window full` is Claude's/reviewer's job at review time per the brief, not required here,
  but run it too if `--window short` passes cleanly and time allows.
- Final reply uses the exact §3 block from the brief: CURRENT_TASK / FILES_CHANGED /
  CENSUS_BEFORE_AFTER (per package, CONFIG+PARAM_DEFAULT+ENV before → 0 after) /
  DECLARATIONS (full table, all packages) / KEPT (full table, all packages) / TESTS+OUTPUT /
  PARITY verdict / UNVERIFIED / BLOCKED.
- Per CLAUDE.md's SESSION LOG mandate, also append a `📝 SESSION LOG ENTRY` to
  `assistant_project.md` in the **main repo** (`D:\Tradelatest`) for this turn — the worktree
  commits are the code record, the session log is the narrative record — but do not commit the
  worktree's own copy of that file as part of a lane commit (it's outside the owned packages).

## Verification

- Per package: `python scripts/analysis/config_fallback_census.py --package <pkg> --print`
  shows CONFIG=PARAM_DEFAULT=ENV=0.
- Per package: `pytest` on the touched test files (new parametrized + REJECT tests) green,
  from the worktree with `PYTHONPATH=<worktree>\src`.
- End-to-end: `parity_v5.py --window short` verdict has no `DIFFERS` surface.
- Nothing under `configs/production/` shows as modified in `git -C <worktree> status`.

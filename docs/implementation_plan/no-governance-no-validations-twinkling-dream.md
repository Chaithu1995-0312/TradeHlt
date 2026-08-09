# Implement `target-strategy-architecture.md` §13 (items 1–9)

## Context

`docs/architecture/goal.md` (constitution) and `docs/architecture/target-strategy-architecture.md`
(city plan) describe a target architecture. §13 of the city plan is an ROI-ordered
implementation sequence of 9 items, and §14 is the matching not-yet-built checklist. Almost
none of §13 is built — the docs are ahead of the code.

The user's instruction: **"No governance no validations. Pure implementation."** Confirmed to
mean *skip the CLAUDE.md meta-ritual* — no SESSION LOG blocks, no `docs/current-findings.md`
edits, no topic/citation sync, no ontology census, no BUILD_IMPACT_MANIFEST, no config re-hash
or promotion run. `ConfigValidator` / `PromotionManager` / `ACTIVE_VERSION` stay in the repo
untouched (goal.md invariant #4 is part of what we're implementing) — we simply don't feed them
paperwork. Pytest tests **are** still written where they're the cheapest verification.

Intended outcome: the numbers the system produces become reconstructible and path-independent,
and "what strategy are we running" becomes a nameable, versioned object.

---

## Ground truth established during exploration

| §13 item | Status in code today |
|---|---|
| 1 — F-057 | **OPEN.** `backtest_v2.py:1677` `bt_config.crt_config or ConfigBuilder.build(instrument or "EURUSD")`. `ConfigBuilder.build()` (`config_builder.py:91`) reads **only** `market_router`'s hardcoded `FOREX_CONFIG`/`CRYPTO_CONFIG` — production JSON is never opened. CLI path (`backtest_v2.py:2903`) correctly uses `load_prod_config_from_registry()`. Two configs diverge (e.g. `expansion_atr_min_distance` 0.08 vs 0.30). |
| — unknown instrument | **OPEN.** `market_router.classify_market():42` returns `"FOREX"  # safe default` for anything unlisted. `CRYPTO_SYMBOLS` is `{BTCUSDT, ETHUSDT}` only — so XAUUSD, BNBUSDT, SOLUSDT all silently take the FOREX profile. |
| 2 — F-058 | **MOSTLY DONE** (T-16, 2026-07-23): `backtest.engine_gate_enabled` is config-declared and strict-read (`backtest_v2.py:1977`), env is an explicit override that WARNs. **Residual:** `BACKTEST_BYPASS_ZONE_INVALID` (`backtest_v2.py:2354`) is the same bug class, still `os.getenv(..., "1")` with no config declaration; `active_models.yaml:1082` still says `backtest: OFF`. |
| 3 — hardcode census | Instrument exists (`scripts/analysis/behavior_census.py`) but its corpus is only `src/core`, `src/engines`, `src/config_layer`, and the report is stale (2026-06-14, 3 opportunities). It never scanned `src/runtime` — which is where F-056 found real undeclared trade-affecting constants. |
| 4 — CLI == programmatic parity | **Does not exist.** No harness compares the two entry points. |
| 5 — Strategy Registry | **Does not exist.** Zero hits for `StrategyRegistry`/`strategy_package`. `src/strategies/s01..s10` + `strategy_orchestrator.py` exist but nothing packages "what we trade with" as a version. |
| 6 — research vs G001 | `GoalSpec`/`load_goal_spec` (`goal_schema.py:79,136`) + `goal_report` exist on the **backtest** side. `EdgeReport` (`research/contracts.py:92`) has **no** G001 comparison; `research/provenance.py` stamps cost/exit realism but no config hash, feature-schema hash, or strategy id. |
| 7 — BitNet shadow slot | Driver exists (`scripts/research/bitnet_shadow_diagnostic.py`) + shadow config `research_config_spine_bitnet_shadow.json`. Not generalized into a reusable model-shadow protocol. |
| 8 — ledger completeness | **`TradeProvenanceV1` (`src/journal/trade_provenance_v1_0.py`) has ZERO consumers** — a dead dataclass. `utils/trade_logger.TradeLogger.log_entry()` writes no config version, no config hash, no model versions, no thresholds-fired, no strategy id. Live path (`runtime/live_engine_hook.py:701`) has no provenance at all — `trade_id` is a synthesized `f"{symbol}_{candle_idx}"` string. |
| 9 — config→consumer graph | `scripts/analysis/config_reachability.py` (495 lines) already classifies every config key by consumption. No graph emitter. |

---

## Workstreams

Ordered as §13 requires: integrity first (1–4), because every later measurement depends on it.

### Phase A — Single HOW source (§13.1, §14.A)

**A1. Config-drive the market router.**
- New top-level section `market_router` in `configs/production/v2_multi_2026_04.json`:
  `{"classes": {"CRYPTO": {...5 CRT knobs...}, "FOREX": {...}, "METALS": {...}}, "symbol_map": {"BTCUSDT": "CRYPTO", "XAUUSD": "METALS", ...}}`. Populate `classes.CRYPTO`/`classes.FOREX` with the **exact literals** currently in `market_router.py:12-26` so this step alone is byte-identical for listed symbols. New top-level section ⇒ hash-neutral.
- `src/config_layer/market_router.py`: `classify_market()` reads `symbol_map`; raise a new `UnknownInstrumentError` on a miss instead of `return "FOREX"`. `get_crt_config()` builds `CRTConfig(**classes[cls])` from config, not module literals.
- Every instrument in current use (XAUUSD, BNBUSDT, SOLUSDT, ETHUSDT, BTCUSDT, the 5 FX majors) must be seeded into `symbol_map` or the whole corpus breaks. XAUUSD → `METALS` seeded with the FOREX values verbatim so nothing moves.

**A2. Production JSON authoritative on the programmatic path.**
- `src/runtime/backtest_v2.py:1677` → `load_prod_config_from_registry(PROD_VERSION, bt_config.instrument)`; raise if `instrument` is empty rather than defaulting to `"EURUSD"`.
- Same fix at `src/runtime/unified_replay_harness.py:93` and `src/governance/portfolio_validation.py:82` (the latter also carries 5 hardcoded overrides — move them to config or drop them).
- `src/research/zone_mapping/{gaussian_family_shadow_eval,crt_zone_crosstab,collect_trade_opened_features}.py` call bare `ConfigBuilder.build()`; route through the prod loader too, keeping their existing `_harden_crt_config()` wrapper.

> ⚠️ **This is a deliberate behavior change, not a parity fix.** Every programmatic-path ledger
> (tuner workers, embedders, several tests) will move — that is the whole point of F-057. Capture
> the pre-change XAUUSD programmatic ledger first so the delta is measured, not discovered.

### Phase B — No undeclared env truth (§13.2)

- Declare `backtest.bypass_zone_invalid` in the active config, strict-read via the existing
  `_require_bt_cfg` helper, mirroring exactly the `engine_gate_enabled` pattern at
  `backtest_v2.py:1977-1990` (env stays an explicit override that logs WARNING on disagreement).
- Update `active_models.yaml:1082` `fusion_gate.backtest` to the config-declared value.

### Phase C — Behavioral hardcode census (§13.3, §14.B)

- Widen `behavior_census.py`'s corpus from `{core, engines, config_layer}` to add
  `src/runtime`, `src/features`, `src/journal`, `src/governance`.
- Re-run; migrate the resulting BEHAVIORAL backlog to config using the `_require` / fail-fast
  boundary from `docs/reference/example-service.py`. No `get_prod_section(...).get(key, literal)`.

### Phase D — Honest baseline (§13.4, §14.A last item)

- New `scripts/analysis/ledger_parity.py`: run XAUUSD through **both** entry points (CLI
  `main()` and `BacktestRunner(BacktestConfig.from_prod_config())`) on the same corpus, diff the
  trade ledgers field-by-field ignoring wall-clock/uuid, exit non-zero on divergence.
- This is the acceptance gate for Phase A. Reuse `src/runtime/unified_replay_harness.py`'s
  existing comparison plumbing rather than writing a new differ.

### Phase E — Strategy Registry (§13.5, §8, §14.C)

- `src/strategies/strategy_package.py` — frozen `StrategyPackage` dataclass matching the §8 shape
  (`name`, `version`, `features_used`, `thresholds`, `model` pins, `risk`, `provenance`), plus:
  - `StrategyPackage.from_active_config()` — **projects** the active production JSON sections
    (`crt_engine`, `fusion_engine`, `decision_engine`, `ultron_risk_gate`, `execution_planner`)
    and the model registries (`model_registry.get_active_version(instrument)`,
    `get_active_zone_gate()`, `get_active_rr()`, `get_active_tradenet_version()`) into a package.
    A **view**, never a second source of formula meaning (§8 "must complement, not replace").
  - `.content_hash()` — stable sha256 for stamping on trades.
- `src/strategies/strategy_registry.py` — load/list/resolve packages from `configs/strategies/*.json`;
  map strategy version ↔ production config version + hash.
- Wire `strategy_id` into `BacktestConfig` so a run can name what it ran.

### Phase F — Research loop reports G001 (§13.6, §14.D)

- `src/research/goal_alignment.py` — given an `EdgeReport` + observation window, emit the same
  gap block the backtest emits, reusing `config_layer/goal_schema.load_goal_spec()` and
  `goal_validator`. Attach as `edge_report["goal_report"]`.
- Extend `src/research/provenance.py:provenance_block()` with `strategy_id`, `config_version`,
  `config_hash`, `feature_schema_hash`.
- Add a `job_kind` field (`"threshold_search"` | `"model_retrain"`) to `research/config.py`;
  the runner refuses a config declaring both (§5 rule 4 / §14.D).

### Phase G — Model shadow protocol (§13.7, §14.E)

- Generalize `scripts/research/bitnet_shadow_diagnostic.py` into
  `scripts/research/model_shadow_protocol.py`: parameterized on `(model_flag, shadow_config,
  instruments)`, runs the A/B, reports ΔG001 via Phase F's goal block, and **never** writes the
  enable flag — it prints the decision and exits. `use_bitnet` stays `false`.

### Phase H — Ledger completeness (§13.8, §9, §14.F)

The largest correctness win. `TradeProvenanceV1` currently has zero call sites.

- Populate and stamp `TradeProvenanceV1` at trade-open in `backtest_v2.py` (~:2391, where
  `journal.on_trade_opened()` and `self._trade_logger.log_entry()` already fire):
  `config_version` + `config_hash` from `get_prod_metadata()`, `model_version` from the
  registries, `strategy_id` from Phase E, `promotion_version` from the active registry entry.
- Extend `src/utils/trade_logger.TradeLogger.log_entry()` with `provenance`, `feature_vector_sha`,
  and `gates_fired` (the threshold snapshot that allowed the trade). Additive fields only —
  existing readers keep working.
- Mirror the same stamping on the live path (`src/runtime/live_engine_hook.py`), which today
  emits none. Replace the synthesized `f"{symbol}_{candle_idx}"` id with
  `journal.trade_identity_v1_0.mint_trade_id()`.
- Note during implementation: two distinct `TradeLogger` classes exist
  (`src/utils/trade_logger.py` and `src/journal/trade_logger.py`). Do not conflate them; the
  backtest path uses the `utils` one.

### Phase I — Config→consumer graph (§13.9, §14.H)

- Add `--graph` to `scripts/analysis/config_reachability.py`, emitting
  `docs/architecture/config-consumer-graph.generated.{json,md}` from the loader references it
  already resolves. Cheap because the analysis exists; only the emitter is new.

---

## Sequencing

A → B → D (parity gate proves A) → C → E → H → F → G → I.

D is the gate: nothing after it is trustworthy until CLI and programmatic runs agree.

## Verification

Primary corpus is `data/mt5/XAUUSD_M15.csv` (per standing preference — do not swap in a crypto
major to make a step produce events).

1. **Baseline capture (before any edit):** run XAUUSD via CLI and programmatically, save both
   ledgers. Expect them to differ today — record the delta.
2. **Phase A/B:** re-run both; `scripts/analysis/ledger_parity.py` must exit 0. Confirm
   `classify_market("NOTAREALSYMBOL")` raises rather than returning `"FOREX"`.
3. **Phase C:** `python scripts/analysis/behavior_census.py --check` exits 0 on the widened corpus.
4. **Phase E:** `StrategyPackage.from_active_config()` round-trips to JSON and back; its
   `content_hash()` is stable across two calls.
5. **Phase H:** run a backtest that opens ≥1 trade; assert every ENTRY line in
   `logs/run_*/XAUUSD/XAUUSD_fusion.jsonl` carries non-null `config_hash`, `config_version`,
   `strategy_id`, `feature_vector_sha`, and joins to an EXIT on `trade_id`.
6. **Phase F/G:** run one existing research config end-to-end; `edge_report.json` contains a
   `goal_report` block and the extended provenance fields.
7. Targeted pytest for the new modules (`market_router` fail-closed, `StrategyPackage` hashing,
   provenance stamping). Full-suite regression is out of scope per "no validations".

## Explicitly out of scope

SESSION LOG entries, findings-doc edits, `active_models.yaml` beyond the one Phase-B line,
config re-hash, promotion runs, topic/citation sync, ontology/construction-protocol manifests.

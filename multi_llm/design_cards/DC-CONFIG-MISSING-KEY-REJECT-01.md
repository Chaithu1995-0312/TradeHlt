# DC-CONFIG-MISSING-KEY-REJECT-01 - Missing config key = REJECT (production-influencing parameters)

| Field | Value |
|---|---|
| **ID** | DC-CONFIG-MISSING-KEY-REJECT-01 |
| **Status** | DRAFT (design only; nothing wired, no code changed, not queued) |
| **Date** | 2026-09-28 |
| **Owner** | Grok Bot |
| **Freeze** | User |
| **Domain** | trading-infra / config authority |
| **Sources** | `src/config_layer/production_config.py`; `src/config_layer/config_builder.py`; `src/config_layer/state_identity.py` (CRTConfig); `src/config_layer/crt_config_completeness.py`; `src/config_layer/crt_config_provenance.py`; `src/config_layer/execution_planner.py`; `src/core/ultron_risk_gate.py`; `src/runtime/live_engine_hook.py`; `src/runtime/backtest_v2.py`; `src/core/decision_engine.py`; `src/core/engine_runner.py`; `src/core/acceptance_controller.py`; `src/engines/trap_validator_engine.py`; `src/features/crt_state_resolver.py`; `src/features/feature_pipeline.py`; `scripts/analysis/behavior_census.py`; active prod `configs/production/v2_htfcrt_2026_08.json` |
| **Evidence base** | Read-only audit, 2026-09-28 ~02:35 IST. Builds on `multi_llm/bridge_layer/PARAM_CENSUS_RESEARCH_VS_PRODUCTION.md` (the census; section D = Silent Default Audit) |
| **Governing text** | CLAUDE.md:707-725 ("Hard rule - NO silent config defaults ... A missing key/section is an error (raise)") |

---

## 1. Problem and governing rule

**Rule (User):** every trading parameter comes from a declared, loaded config only. There are no silent defaults. **A missing key means REJECT** (fail-closed). An unknown value is never a pass.

**Authority:** research discovers; production executes; governance approves. Research never decides production policy. This card changes nothing about which values production uses. It only makes absence visible and fatal.

**Scope:** parameters that influence production decisions: risk and sizing, execution planning, CRT thresholds, decision and fusion weights, and backtest execution semantics. **Out of scope:** research-only knobs, logging and UI settings, and data dicts such as trade rows or bars, unless they carry a config value.

**Problem:** the repository rejects a missing *file*, *section*, `params` block or `config_hash`. Below that, a missing *key* is mostly filled silently from a code literal: a dataclass default, a `.get(k, literal)`, a `DEFAULT_CONFIG` merge, a `getattr(..., default)` or an `or literal`. So the rule is not met.

## 2. Current-state verdict

**Verdict: NOT SATISFIED repo-wide.** File, section and hash level: ENFORCED. Key level: mostly NOT_ENFORCED.

**Proof (read-only, in memory, temp dir, 2026-09-28):** copy the active registry `v2_htfcrt_2026_08`. Delete `sl_atr_buffer` from both `params` and `crt_engine`, recompute `config_hash`, then call `load_prod_config_from_registry(..., registry_dir=<tmp>)`. **It loads without error and without a warning, and `CRTConfig.sl_atr_buffer = 0.2`** (the dataclass literal, `state_identity.py:189`).

**A strict primitive already exists but is not wired:** `crt_config_completeness.require_complete` (`crt_config_completeness.py:130`). Its own docstring says it is not called by the loader on purpose (`:47-57`). Run against the active config, it **raises** on 2 undeclared fields: `displacement_origin_kill_enabled` and `displacement_origin_kill_precedence`. Across `configs/production/*.json`, 27 files are counted and only 3 are complete.

| Layer | Verdict | Evidence (file:line) |
|---|---|---|
| Registry file / `params` / `config_hash` | ENFORCED | `production_config.py:332` (file), `:337-342` (params), `:345-354` (hash) |
| Section presence (`get_prod_section`) | ENFORCED | `production_config.py:461-466` |
| Unknown CRT keys | ENFORCED | `config_builder.py:212-217` (`_validate_override_keys`) |
| CRTConfig keys on the production load | NOT_ENFORCED | 49 of 53 fields have defaults (`state_identity.py:147-306`); merge `production_config.py:359-385` then `ConfigBuilder.build` `:390`; `require_complete` not called; sl_atr_buffer proof above |
| CRTConfig construction (4 fields) | ENFORCED (TypeError) | `body_ratio_min`, `atr_multiplier_min`, `retest_depth_max`, `expansion_atr_min_distance` have no default; supplied by `market_router` config |
| F-057 construction-mode gate | PARTIAL (mode only, not keys) | `crt_config_provenance.py:164-196` (warn unless `CRT_CONFIG_STRICT=1`); `:199-214` fail-closed; called only at `backtest_v2.py:2415` |
| Backtest cost knobs | ENFORCED | `BacktestConfig.from_prod_config` strict; `tests/test_cost_model_stamped.py:77` |
| Other backtest keys | PARTIAL | `backtest_v2.py:331`, `:338`, `:345` (`cfg.get` literals) |
| Feature pipeline | PARTIAL (full coverage UNKNOWN) | strict `_require_fp_cfg` `feature_pipeline.py:209`; 1 literal `.get` found |
| CRT state resolver | NOT_ENFORCED | 36 literal `.get`; e.g. `crt_state_resolver.py:2031` |
| Execution planner / risk gate / live hook | NOT_ENFORCED | `execution_planner.py:157` (DEFAULT_CONFIG merge); `ultron_risk_gate.py:107` (DEFAULT_CONFIG merge), `:238-240`, `:292`, `:312`, `:327`; `live_engine_hook.py:811`, `:1073-1074` |
| Decision / engine runner / controllers | NOT_ENFORCED | `decision_engine.py:115`; `engine_runner.py:609-612`; `acceptance_controller.py:98-100`; `trap_validator_engine.py:33` |
| Config-first migrated modules | ENFORCED (listed modules only) | `behavior_census.py --check` passes (`tests/test_behavior_census.py`); 84 strict-helper definitions across `src`, one module at a time |
| Production config schema | ABSENT | no JSON Schema for `configs/production/*`; no jsonschema or pydantic import in `src` |

**Pattern counts** (heuristic scan of 144 files in `src/core`, `engines`, `execution`, `features`, `config_layer`, `runtime`, `control_plane`; **upper bounds**, because many hits are data dicts): `.get(k, literal)` 874 (82 on dicts named like config); `getattr(x, k, default)` 144; `or <literal>` 327; dataclass field defaults 621; `except KeyError` 22; numeric keyword-argument defaults 37. Census section D: 40 parameters with a silent fallback, 7 firing today.

## 3. Hotspots (prioritized by live-decision influence)

"Triggered" = the key is absent from the active config, so the code literal runs today. "Latent" = the key is declared, and the literal runs only if the key is removed. The census column points to rows in `PARAM_CENSUS_RESEARCH_VS_PRODUCTION.md` section D.

| # | Priority | Parameter | Site (file:line) | Code default | Active config | State | Census |
|---|---|---|---|---|---|---|---|
| H1 | P0 risk/sizing | whole `execution_planner` section | `execution_planner.py:157` merges `DEFAULT_CONFIG` (`:102-123`) under the config | full dict | section present | latent (every key) | execution_planner.* rows |
| H2 | P0 | `execution_planner.risk_percent` | `execution_planner.py:110` | 0.5 | 0.5 | latent | execution_planner.risk_percent |
| H3 | P0 | `execution_planner.default_account_balance` | `execution_planner.py:113` | 10000.0 (USD) | 10000.0; compare `capital_management.total_capital_inr` = 100000 | latent (unit conflict noted) | execution_planner.default_account_balance |
| H4 | P0 | `execution_planner.breakout_disp_threshold` | `execution_planner.py:117`, via `live_engine_hook.py:1025-1028` merge | 1.5 | ABSENT | **triggered** | execution_planner.breakout_disp_threshold |
| H5 | P0 | whole `ultron_risk_gate` section | `ultron_risk_gate.py:107` merges `DEFAULT_CONFIG` (`:47-53`) | full dict | section present | latent | ultron_risk_gate.* rows |
| H6 | P0 | per-trade `risk_percent` | `ultron_risk_gate.py:292` | 0.5 | from the trade dict (planner) | latent | ultron per-trade fallbacks |
| H7 | P0 | `account_balance` | `ultron_risk_gate.py:327` | 10000.0 | from caller `portfolio_state` | latent | ultron per-trade fallbacks |
| H8 | P0 | `spread_pips` / `slippage_pips` / `pip_size` / `min_sl_pips` | `ultron_risk_gate.py:238`, `:239`, `:240`, `:312` | 0.0 / 0.0 / 0.0001 / 0.0 | 0.0 / 0.0 / 0.0001 / 0.0 | latent | ultron per-trade fallbacks |
| H9 | P0 | live lot fallback | `live_engine_hook.py:811` | 0.01 | n/a (field of the gate result) | latent | live final_position_size |
| H10 | P0 | live TP multipliers | `live_engine_hook.py:1073` (tp1, per-intent then generic), `:1074` (tp2) | 1.0 / 2.0 | crt_engine 1.0 / 2.0 | latent | tp1/tp2_atr_multiplier |
| H11 | P1 CRT | all CRTConfig scalar defaults (49 fields) | `state_identity.py:147-306`; merge `production_config.py:359-390` | per field (e.g. sl_atr_buffer 0.2 `:189`) | 45 crt_engine + 5 params keys declared | latent (proven for sl_atr_buffer) | CRTConfig rows |
| H12 | P1 | `displacement_origin_kill_enabled` / `_precedence` | `state_identity.py:264`, `:272` | False / "after_resting_fills" | ABSENT | **triggered** | displacement_origin_kill_* |
| H13 | P1 | resolver thresholds (range_atr_period, max ages, score_threshold, soft_conf, atr_min_displacement, expansion_atr_is_relative) | `crt_state_resolver.py` (36 literal `.get`s, e.g. `:2031`) | 14 / 20 / 3 / 495,124 / 0.45 / 3 / 1.2 / True | YAML `configs/formulas/market_crt_states.yaml` declares the same values | latent | resolver thresholds |
| H14 | P2 decision | `decision_engine.fallback_top_n` | `decision_engine.py:115` (module constant `:44`) | 3 | ABSENT | **triggered** | decision_engine.fallback_top_n |
| H15 | P2 | `DecisionEngine` `threshold_window` | `decision_engine.py:92` (keyword default) | 1000 | not a config key | **triggered** | DecisionEngine threshold_window |
| H16 | P2 | fusion weights `weight_crt` / `weight_gaussian` / `weight_zone_gate` / `weight_rr` | `engine_runner.py:609-612` (`getattr` default) | 0.30 / 0.25 / 0.25 / 0.20 | not in the `engine_runner` section; source object UNKNOWN | UNKNOWN | engine_runner score weights |
| H17 | P2 | `engine_runner.min_atr` (trap validator) | `trap_validator_engine.py:33` | 0.0005 | 0.0003 | latent (code and config differ) | engine_runner.min_atr |
| H18 | P2 | `acceptance_controller` theta_min / theta_max / min_history | `acceptance_controller.py:98-100` (constants `:34`, `:35`, `:38`) | 0.50 / 0.95 / 10 | 0.5 / 0.95 / 10 | latent | acceptance_controller rows |
| H19 | P3 backtest | `backtest.htf_reset_exempt_sweep` | `backtest_v2.py:331` | False | ABSENT | **triggered** | backtest.htf_reset_exempt_sweep |
| H20 | P3 | `backtest.sl_anchor` | `backtest_v2.py:338` | "displacement" | ABSENT | **triggered** | backtest.sl_anchor |
| H21 | P3 | `backtest.session_window_basis` | `backtest_v2.py:345` | "broker_static" | ABSENT | **triggered** | backtest.session_window_basis |

## 4. Target contract (REJECT semantics)

1. **Typed error.** A missing required key raises one dedicated exception type, `ConfigKeyMissingError`, in the same family as the existing `RuntimeError`/`KeyError` raises. The message names the **key**, the **section**, the **config version** (e.g. `v2_htfcrt_2026_08`), the **registry path**, and the **consumer** (the module that asked for it).
2. **All missing keys at once.** The loader collects every missing key in a section, or across the whole file for M1 and M3, before raising, so one run lists them all (like `require_complete` does today).
3. **No partial load.** On REJECT, no config object is returned or cached, and no engine is constructed. A run never starts with half a config.
4. **Unknown-key REJECT stays** (`config_builder.py:212-217`) and extends to every section once that section has a schema (M3).
5. **No warn-only mode on production paths.** A production load either passes fully or raises. Warn-only behaviour may exist only in explicitly non-production tools (census or diagnostics), and those must never feed a run.
6. **How this relates to CRT_CONFIG_STRICT and F-057:** F-057 checks *how* a CRTConfig was built (PRODUCTION_MERGED vs ROUTER_BASE and so on). It does not check whether keys are missing. `CRT_CONFIG_STRICT` only toggles F-057's warn-or-raise (`crt_config_provenance.py:189-195`). Under this card, key completeness is **unconditional**: no environment variable turns it off. Whether F-057's own non-strict default should also become fail-closed on every production entry point, not just `backtest_v2.py:2415`, is decision D6.
7. **Values are never changed by this work.** Enforcement moves literals into declared config at exactly the value that runs today, proved by the CLAUDE.md:711 parity test (JSON value == prior literal, strict read, byte-identical ledger). Choosing a *different* value is a separate governed change.

## 5. Mechanism (M1-M5)

**Order:** M2a, then M1, then M3, then M4, then M5. M4 can run in parallel per module once M3's schema exists for that section. M5 is last (it ratchets).

**M1 - wire `require_complete` into `load_prod_config_from_registry`**
- Call it after the merge (`production_config.py:385`) and before `ConfigBuilder.build` (`:390`). Pass `engine_runner` as the externally owned section.
- Depends on: migration step 6.1 (active config declares the 2 missing fields). The rollout scope (all files or active only) is D2.
- Acceptance tests:
  - (a) Active config loads.
  - (b) Each of the 53 fields removed one at a time: the load raises and the message names that field, its section and the version.
  - (c) The sl_atr_buffer deletion proof now raises.
  - (d) An unknown key still raises.
  - (e) Existing `tests/test_crt_config_completeness.py` stays green.

**M2 - remove CRTConfig defaults and fix the provenance fingerprint**
- M2a: fix `crt_config_provenance.py:235` (`schema_fingerprint`) and `:244` (`compare_surfaces`), which call `CRTConfig()` with no arguments and already fail today because 4 fields have no default. This needs a replacement for the "schema surface" (D5).
- M2b: remove the Python defaults from all CRTConfig fields, so the dataclass itself enforces completeness. Tests use explicit fixtures (`tests/Claude/_fixtures.py:12` pattern).
- Depends on: M1 (the loader already guarantees completeness) and D5.
- Acceptance tests:
  - (a) `CRTConfig()` and any partial construction raise `TypeError` naming the missing fields.
  - (b) `tests/test_crt_config_provenance.py::test_fingerprint_diverges_router_vs_prod_xauusd` and `::test_compare_surfaces_structure` pass.
  - (c) The ConfigBuilder router path still works for every class profile in `market_router`.

**M3 - per-section JSON Schema, validated at load**
- One schema per production section, draft 2020-12: `required` lists every key; `additionalProperties: false`; typed. Validated by the loader for the whole file before any section is served (`load_prod_config_from_registry` and `get_prod_section`). The schema file is versioned and hashed next to `config_hash`. Where it lives is D4.
- Depends on: the schema validator dependency choice (D4) and the list of sections that count as production-influencing (D3).
- Acceptance tests:
  - (a) Active config validates.
  - (b) For every required key in every in-scope section, removing it raises the typed error.
  - (c) An extra key raises.
  - (d) A wrong type (e.g. a string instead of a number) raises.
  - (e) `get_prod_section` never returns a section from a file that failed validation.

**M4 - replace `DEFAULT_CONFIG` merges and literal `.get` with strict reads**
- Priority order follows section 3: H1-H10 (execution, risk, live), then H13 (resolver), then H14-H18, then H19-H21.
- Pattern: the CLAUDE.md:708 `_require()` / `from_prod_config()` boundary. Delete `{**DEFAULT_CONFIG}` merges (`execution_planner.py:157`, `ultron_risk_gate.py:107`). Values that a caller supplies per trade (H6, H7, H9) must be present in the payload or the trade is rejected. Whether "rejected" means that one trade or a halt is D7.
- Depends on: M3 for the section's key list; D7.
- Acceptance tests, per module:
  - (a) A strict-read unit test for each key (missing key raises, CLAUDE.md:709).
  - (b) Parity: the JSON value equals the prior literal, and the BNBUSDT + SOLUSDT ledgers are byte-identical (CLAUDE.md:711-713).
  - (c) `behavior_census.py --check` adds the module to the migrated list.

**M5 - shrink-only lint allowlist (extends behavior_census)**
- An AST check over the production directories flags `.get(<str>, <non-None literal>)`, `getattr(<obj>, <str>, <default>)` and `or <literal>` when applied to config objects, plus dataclass defaults on config dataclasses.
- Every current hit goes into an allowlist file with a reason. CI fails on a new hit **or** on an allowlist that grows. Removing entries is always allowed.
- Depends on: none to build (it can land early in report-only form). It becomes blocking after M4 P0 is done. How to classify "config object" is D8.
- Acceptance tests:
  - (a) A planted `cfg.get("x", 1.0)` in a production file fails the lint.
  - (b) Removing an allowlisted site passes, and the allowlist count drops.
  - (c) Adding an allowlist entry fails without an explicit User-approved marker.

## 6. Migration

1. **Active config:** `v2_htfcrt_2026_08` must declare `displacement_origin_kill_enabled` and `displacement_origin_kill_precedence`. **The values are a User decision (D1).** This card does not propose any. The code literals (False / "after_resting_fills") are recorded only as what runs today. Declaring them in `crt_engine` does not change `config_hash`. Declaring them in `params` does, and needs `scripts/maintenance/_compute_hash.py` (CLAUDE.md:714).
2. **The other 24 incomplete production files** (27 counted, 3 complete) need a migrate-or-archive decision (D2). Named examples from the completeness docstring: `v1_multi_2026_03_force_accept.json`, `v2_test.json`, `v2_test_archived_20260411_200110.json` (0 `crt_engine` fields).
3. **Stale test counts:** `tests/test_crt_config_completeness_census.py` expects 24 files (now 27) and 1 complete (now 3), so it fails today. It should be updated from a fresh census once D2 is decided, not before.
4. **Tests that pin the opposite behaviour** (missing key gives a default) must be classified as in scope (rewrite to expect REJECT) or out of scope (not production-influencing):
   - `tests/test_pattern_hasher.py:178` (`test_missing_keys_use_defaults_no_error`)
   - `tests/test_scanner_ranker.py:147` (`test_ranker_missing_fields_default_to_zero`)
   - `tests/test_llm_connectivity.py:96` (`test_missing_keys_default_to_zero`)
   - `tests/test_p4_observability.py:107` (`test_missing_key_from_dict_yields_none`)
5. **Code and config drift found along the way** (recorded here, not decided here): `trap_validator_engine.py:33` default 0.0005 vs config 0.0003; `execution_planner` TTL defaults differ from the active TTLs (census row execution_planner.ttl_*); `default_account_balance` 10000 (USD) vs `capital_management.total_capital_inr` 100000.

## 7. Open decisions for User (no defaults chosen)

- **D1 - values for the 2 undeclared active CRT fields.** Options: (a) declare exactly what runs today; (b) declare different values (a separate governed change with its own evidence); (c) remove the feature from CRTConfig.
- **D2 - the 24 incomplete production files.** Options: (a) migrate every file to complete; (b) archive every non-active file so it can no longer be loaded; (c) enforce only for the active version plus an explicit allowlist of versions that may still load; (d) keep them loadable with an explicit "legacy, not production-admissible" marker.
- **D3 - which sections count as production-influencing (M3 scope).** Options: (a) every top-level section in the production JSON (49 top-level keys in the active file, including metadata keys such as version and config_hash); (b) only sections read by live or backtest decision paths (to be enumerated); (c) the section-3 hotspot sections first, then grow.
- **D4 - where the schema lives and which validator.** Options: (a) JSON Schema files under `configs/production/schema/` validated with a new `jsonschema` dependency; (b) under `docs/governance/` next to the existing `*.schema.json`; (c) a hand-written strict validator in `config_layer` (no new dependency).
- **D5 - what replaces `CRTConfig()` as the "schema surface" in `crt_config_provenance.py:235,244`.** Options: (a) field names and types only, no values; (b) a fixture config declared on disk; (c) remove the three-way comparison and compare router against prod only.
- **D6 - F-057 default posture.** Options: (a) make `assert_product_crt_config` mandatory on every production entry point (live hook, engine runner, dashboard runs); (b) keep it at backtest only; (c) remove the `CRT_CONFIG_STRICT` escape hatch entirely.
- **D7 - REJECT scope at run time for payload-supplied values (H6, H7, H9).** Options: (a) reject the single trade and continue; (b) halt the engine; (c) a declared per-key policy.
- **D8 - M5 lint precision.** Options: (a) a name heuristic (cfg, config, settings, section, `*_cfg`); (b) type-driven (only objects returned by `get_prod_section` or `load_prod_config_from_registry`, tracked by data flow); (c) flag every `.get` literal in the production directories and allowlist the data dicts by hand.
- **D9 - is `src/control_plane` production-influencing?** Options: (a) yes, in scope; (b) no, UI and ops only; (c) split per module.
- **D10 - rollout gating.** Options: (a) one switch-over once M1-M4 P0 are done; (b) per-layer switch-over in the order of section 5; (c) report-only period first, then blocking.

## 8. UNKNOWNs (fail-closed: treated as NOT_ENFORCED until verified)

- U1: how many of the 874 literal `.get` hits are config reads rather than data dicts (heuristic only).
- U2: full coverage of the feature pipeline. Only its `_require_fp_cfg` path was verified.
- U3: the source object for `engine_runner.py:609-612` weights (`getattr(cfg, ...)`), and whether any config key feeds it.
- U4: whether `src/control_plane` (dashboard_api: 55 literal `.get`, 32 `or` literal) influences trading decisions (D9).
- U5: whether the modules behind the tests that pin the opposite behaviour (section 6.4) sit on trading paths.
- U6: `configs/formulas/*.yaml` and other non-JSON config surfaces (e.g. `market_crt_states.yaml` thresholds) have no strict loader verified. They need their own inventory.
- U7: `live_engine_hook` was cited as "live hook strict" for `execution_planner.risk_percent` in the census, but its merge at `:1025-1028` still goes through `DEFAULT_CONFIG`. The exact precedence on the live path is not re-verified.
- U8: whether any entry point constructs CRTConfig outside `load_prod_config_from_registry` / `ConfigBuilder` on a production path.

## 9. Proposed story split (proposal only; not queued, no build_queue edits)

| Story | Content | Depends on |
|---|---|---|
| S1 | Decide D1, then declare the 2 active CRT fields (config only, parity-proved) | D1 |
| S2 | M2a: fix `crt_config_provenance.py:235,244` (restores 2 failing tests) | D5 |
| S3 | M1: wire `require_complete` plus the typed error and acceptance tests | S1, D2 |
| S4 | Production-file hygiene per D2, plus refresh the stale census test counts | D2 |
| S5 | M3: schema for the P0 sections (`execution_planner`, `ultron_risk_gate`, `crt_engine`, `params`) plus loader validation | D3, D4 |
| S6 | M4 P0: strict reads in `execution_planner`, `ultron_risk_gate`, `live_engine_hook` (H1-H10), with ledger parity | S5, D7 |
| S7 | M4 P1: `crt_state_resolver` thresholds (H13) and the YAML loader (U6) | S5 |
| S8 | M4 P2/P3: decision engine, engine runner weights (after U3), acceptance controller, trap validator, backtest keys (H14-H21) | S5, U3 |
| S9 | M2b: remove CRTConfig defaults | S3, S2 |
| S10 | M5: lint plus shrink-only allowlist (report-only, then blocking per D10) | none (blocking after S6) |
| S11 | Classify the tests that pin the opposite behaviour, and the control_plane scope | D9 |

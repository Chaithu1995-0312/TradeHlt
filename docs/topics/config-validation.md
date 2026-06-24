# Topic: Config Validation

> **Topic-visibility unit.** The mandatory pre-promotion gate: no config reaches production
> without an APPROVE verdict from here. The "is this config good enough to ship" judge.
>
> Created: 2026-06-01 · Updated: 2026-06-02 (session-override-aware) · Status: living

## In plain language
`ConfigValidator` decides whether a candidate config is fit for production. It runs a
per-instrument backtest, computes a fitness score, and applies **hard gates** (must pass) and
**soft gates** (warn) — then returns a structured `ValidationReport` with `decision` =
`APPROVE` or `REJECT`. This is the single judgment the promotion path is *not allowed* to skip.

## Code covered
- [`src/config_layer/config_validator.py:297`](../../src/config_layer/config_validator.py) — `ConfigValidator` (all-static, no instance state). `validate(params, csv_paths, config_id, use_llm=False, warmup_candles=30, engine_runner=None)` ([`:305`](../../src/config_layer/config_validator.py)) builds a `CRTConfig` from `params` (per-instrument session override applied when `engine_runner` is passed — see the 2026-06-02 bullet), backtests each instrument, scores fitness, applies gates. Empty `csv_paths` → immediate `_reject` ([`:345`](../../src/config_layer/config_validator.py)).
- **Gates (per `CLAUDE.md §11 Phase 1`):** hard — min trade count (10), max drawdown (35%), min fitness (0.15); soft — win rate < 35%, expectancy < −0.5R, high cross-instrument variance.
- **Trd-M3 (2026-06-01):** gate thresholds are now resolved **lazily** via a cached `_gates()` accessor (was eager module-level `_VALIDATOR_CFG` + 8 constants at import). Importing `config_validator` no longer triggers a production-config read. Legacy constant names (`_FITNESS_WEIGHTS`, `_GATE_*`, …) preserved for external importers via a PEP 562 module `__getattr__`. All values unchanged.
- **Trd-M4 (2026-06-01):** `_run_instrument(... , factory=None)` builds the backtest runner through the neutral `core.backtest_port.default_backtest_factory` (injectable), so this gate depends on the `BacktestPort` abstraction rather than importing `runtime.backtest_v2.BacktestRunner` directly.
- **Session-override-aware (2026-06-02):** `validate(... , engine_runner: dict | None = None)` now applies per-instrument session overrides. When `engine_runner` is passed, each instrument's backtest uses `dataclasses.replace(crt_config, allowed_sessions=resolve_allowed_sessions(engine_runner, inst))` — the new shared helper in [`production_config.py`](../../src/config_layer/production_config.py) (single source of truth, also used by `load_prod_config_from_registry`). `engine_runner=None` preserves prior global behavior. `PromotionManager` passes the candidate `engine_runner` (from `_load_full_base_config`). **Remaining fidelity gap:** `_params_to_crt_config` still builds CRTConfig from the 5 flat params + *defaults* (not the full `crt_engine` section), so absolute trade-counts read pessimistically vs the production-config path (BNBUSDT V3: validator 39 vs sweep 35; SOLUSDT PF 0.98 vs sweep 1.17). Decisions are directionally sound; closing this gap is a follow-up.

## Ins / Outs
- **Ins:** `params` (CRTConfig-compatible dict), `csv_paths` (`{instrument: path}`), `config_id`; config section `config_validator`.
- **Outs:** `ValidationReport` dict ([`:332`](../../src/config_layer/config_validator.py)): `{decision: APPROVE|REJECT, config_id, validated_at, params, metrics{final_score,mean_score,...}, per_instrument{}, instruments_tested[], hard_failures[], warnings[]}`.

## Entry points & validations
- **Reached via:** CLI `python config_validator.py validate-prod --data-dir data/`; and called by `PromotionManager` (which **re-runs** validation to guard against stale/tampered reports — see [`promotion-governance.md`](promotion-governance.md)).
- **Validated by:** hard gates are pass/fail (a single breach → REJECT); the report is the audit artifact promotion checks (`decision == "APPROVE"`).

## Tests
- [`tests/test_fusion_and_validator_regression.py`](../../tests/test_fusion_and_validator_regression.py) — validator regression alongside fusion.

## Fits in architecture
The gate between the research/tuning loop and production. Upstream: tuner checkpoints / candidate params. Downstream: `PromotionManager` (only an APPROVE report promotes). See [`promotion-governance.md`](promotion-governance.md), [`docs/reference/governance.md`](../reference/governance.md), [`docs/reference/config-reference.md`](../reference/config-reference.md).

## Discussion (filled in-session)
- **Risks:** `2026-06-01` hard-gate thresholds (10 trades / 35% DD / 0.15 fitness) live partly in code per the Phase-1 notes — verify they're sourced from the `config_validator` config section, not magic numbers, on next touch. **Resolved `2026-06-01` (Trd-M3):** confirmed all thresholds flow from `get_prod_section("config_validator")` via `_gates()` → `_load_validator_cfg()`; no magic numbers.
- **Challenges:** `2026-06-01` validation cost scales with instrument count × candles; large `csv_paths` make the promotion gate slow.
- **Blockers:** `2026-06-01` none.
- **Ambiguities:** `2026-06-01` `use_llm` is accepted but "currently unused" ([`:325`](../../src/config_layer/config_validator.py)) — reserved surface; don't assume an LLM gate runs during validation.
- **Enhancements:** `2026-06-01` thread the soft-gate warnings into `promotion_log.jsonl` so near-miss promotions are auditable, not just pass/fail.
- **Need more info:** `2026-06-01` confirm the hard/soft gate thresholds' config keys + the fitness-score formula (read on next touch).
- **Blockers:** `2026-06-02` **the gate is session-config-blind.** `validate()` builds ONE `crt_config = _params_to_crt_config(params)` ([`:401`](../../src/config_layer/config_validator.py), [`:141`](../../src/config_layer/config_validator.py)) and reuses it for every instrument; it never reads `engine_runner.allowed_sessions` nor the new `allowed_sessions_overrides`, so all instruments validate at CRTConfig *default* sessions. Consequence: a session-expanded or instrument-scoped session config cannot be validated (or proven non-regressive) here — BNBUSDT V3 would show ~15 trades, not 35. The scoping/non-regression proof was done out-of-band at the real runtime resolution layer (`scripts/analysis/session_override_scoping_proof.py` + `session_sweep.py`). **Governance decision pending for any session promotion:** either make ConfigValidator override-aware (build per-instrument crt_config via `load_prod_config_from_registry`), or record that session behavior is validated out-of-band. See [[promotion-governance]]. **Resolved `2026-06-02`:** ConfigValidator is now override-aware via `engine_runner=` + `resolve_allowed_sessions` (see the "Session-override-aware" bullet above). BNBUSDT V3 validates at 39 trades (not ~15). A separate `crt_engine`-fidelity gap (defaults vs full section) remains as a follow-up.
- **Enhancements:** `2026-06-02` close the `crt_engine`-fidelity gap — have `_params_to_crt_config` (or `validate`) build CRTConfig from the full candidate `crt_engine` section, not just the 5 flat params + defaults, so validator metrics match the production-config path.

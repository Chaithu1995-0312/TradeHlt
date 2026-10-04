# Architect plan — finish the sizing-bridge (Claude takes over from DeepSeek)

## Context
DeepSeek ran out of tokens mid-implementation of the sizing-bridge lane (D11: INR→USD→lots
conversion) that was relayed to it earlier this session. Its worktree
(`D:\Tradelatest-wt-sizing-bridge`, branch `lane/sizing-bridge`, base `f45b740` =
current `grokbotchanges` HEAD) has real, uncommitted, high-quality work — but it is
incomplete and nothing is committed. The user asked me to continue it directly. Per this
session's standing multi-LLM protocol (CLAUDE.md §13.8), Claude is the sole code
executor anyway, so I finish the remaining work myself rather than re-relay a partial job.

## Verified at source — what DeepSeek actually did (2026-09-30, read from the worktree)
Uncommitted changes in `D:\Tradelatest-wt-sizing-bridge`:

| File | Status | Assessment |
|---|---|---|
| `src/core/position_sizing.py` | **NEW, complete** | `size_trade_lots()` (floor-to-step, reject-below-min, clamp-to-max), `instrument_spec()` (strict, fail-closed `ConfigKeyMissingError`), `has_instrument_spec()`, `legacy_oz_size_units()` (explicit fallback for undeclared instruments on the backtest rail only), `usd_quote_pnl_inr()`. Well-documented, matches the approved design and STORY-84.2 REJECT-not-raise convention. |
| `src/core/ultron_risk_gate.py` | **Modified, Check 7 rewritten** | Constructor gained `instrument_specs`/`usd_inr_rate` kwargs (optional — non-sizing checks still work without them); Check 7 now converts INR risk → USD → units → lots via the new module, rejects `size_below_min_lot` or `config_key_missing:instrument_specs.<SYM>` for an undeclared instrument, and the `position_size_hint` path now floors the hint onto the lot-step grid and treats it as a ceiling in lots (not raw units). Self-test harness at the bottom (`__main__`) rewritten with a worked XAUUSD example and 2 new test cases (7, 8). **Not yet run** — need to execute it and the real pytest suite. |
| `configs/production/v2_htfcrt_2026_08.json` | **Modified** | Added top-level `instrument_specs.XAUUSD` = `{contract_size:100.0, lot_step:0.01, lot_min:0.01, lot_max:10.0}` with a long attribution comment citing the MT5 calibration report for `contract_size`/`lot_min`/`lot_max` and flagging `lot_step` as UNVERIFIED (not broker-measured anywhere in repo — mirrors `mt5_bridge`'s `round(lot_size, 2)`). Correctly reuses `capital_management.usd_to_inr_rate` rather than re-declaring it. |

**Not started (the remaining 3 of the plan's 4 call sites + tests + construction wiring):**
- `src/runtime/live_engine_hook.py:811` — still does `_lot = float(ultron_result.get("final_position_size", 0.01))`. Now that Ultron emits lots directly, only the silent `0.01` fallback needs removing (a missing/rejected size must not substitute a default lot).
- `src/runtime/live_engine_hook.py:1113-1114` — `position_size_hint` is still computed as raw risk/distance (instrument units), not lots. Needs to call the same `size_trade_lots` bridge.
- `src/runtime/backtest_v2.py` `CapitalCurve` (`:610` class, `:1324` `position_size()`, `:3115` instantiation) — untouched; still books `oz × USD-move` into an INR-labelled curve. Needs its own call to the shared bridge, falling back to `legacy_oz_size_units()` + a `sizing_basis: "legacy_oz"` stamp + WARNING for any instrument with no declared `instrument_specs` entry (DeepSeek's own module already provides `has_instrument_spec()`/`legacy_oz_size_units()` for exactly this).
- **`UltronRiskGate` construction sites** — grepped: `live_engine_hook.py:1181`, `live_rail_orchestrator.py:111`, `copilot_mode.py:122`, `ultron_risk_gate_wrapper.py:22` all construct `UltronRiskGate(cfg)` with no `instrument_specs`/`usd_inr_rate` kwargs. Since those kwargs default to `None`/`{}`, every real trade will now hit the new `missing_sizing` fail-closed reject until at least the live-path constructors (`live_engine_hook.py:1181`, `live_rail_orchestrator.py:111`) are updated to pass `get_prod_config()["instrument_specs"]` and `capital_management.usd_to_inr_rate`. This is a gap DeepSeek's own diff left open — must fix or every live trade silently rejects.
- **Tests** — `tests/test_ultron_risk_gate.py` (`_CFG`/`_gate` helper at `:46` has no `instrument_specs`/`usd_inr_rate`) not yet touched; existing tests asserting old oz-scale `final_position_size` values will fail once this runs for real trades that reach Check 7. Need repo-wide check of `final_position_size` consumers in tests (`test_live_rail_orchestrator.py`, `test_live_rail_ultron_adapter.py`, `test_rr_contract_wiring.py`).

## Plan for this turn
1. Run DeepSeek's `ultron_risk_gate.py` `__main__` self-test as a first sanity check.
2. Wire `instrument_specs`/`usd_inr_rate` into the real construction sites (`live_engine_hook.py:1181`, `live_rail_orchestrator.py:111`) via `get_prod_config()` — the two call sites where the missing kwargs would silently reject every live trade.
3. Fix `live_engine_hook.py:811` (drop the `0.01` fallback) and `:1113-1114` (`position_size_hint` computed via `size_trade_lots`).
4. Add the sizing bridge to `backtest_v2.py`'s `CapitalCurve`, with the `has_instrument_spec`/`legacy_oz_size_units` fallback DeepSeek's module already exposes, so instruments without a declared spec stay byte-identical (stamped `sizing_basis: legacy_oz` + WARNING) and XAUUSD switches to the honest INR conversion.
5. Update `tests/test_ultron_risk_gate.py`'s `_CFG`/helper to inject a test `instrument_specs`/`usd_inr_rate`, fix any test asserting the old oz-scale size, and add a `size_below_min_lot` reject test if DeepSeek's diff didn't already cover it in the real pytest file (only the `__main__` harness has it so far).
6. Grep-check `test_live_rail_orchestrator.py` / `test_live_rail_ultron_adapter.py` / `test_rr_contract_wiring.py` for `final_position_size`/`UltronRiskGate(` usage and fix any that break under the new lots-based sizing.
7. Run the targeted test files, then a full XAUUSD backtest to confirm `CapitalCurve.capital_after` reflects the INR conversion.
8. Commit in the `lane/sizing-bridge` worktree, matching the established EPIC-84 commit-message style, crediting the work as DeepSeek-initiated/Claude-completed.
9. Report back with the same audit rigor as every EPIC-84 lane (verify math, cite file:line, show the worked example) before this gets merged into `grokbotchanges` — merge itself is a separate, explicitly-confirmed step, not bundled into this turn.

## Verification
- `python D:\Tradelatest-wt-sizing-bridge\src\core\ultron_risk_gate.py` (the `__main__` harness) — all 8 cases pass.
- `pytest tests/test_ultron_risk_gate.py tests/test_live_rail_orchestrator.py tests/test_live_rail_ultron_adapter.py tests/test_rr_contract_wiring.py -v` green in the worktree's venv.
- Full XAUUSD backtest run (`python -m runtime.backtest_v2 --csv data/mt5/XAUUSD_M15.csv --instrument XAUUSD --output <scratch>`) — confirm the trade ledger's `capital_after` reflects the lot/INR conversion, not raw oz×USD-move.
- Repo-wide `grep -rn final_position_size src/ tests/` to confirm every consumer was found and updated or explicitly deferred as BLOCKED.

## Next step
Implement steps 1–9 above directly in `D:\Tradelatest-wt-sizing-bridge` (no further relay to DeepSeek — it is out of tokens). Merge into `grokbotchanges` only after this turn's own results are reported and the user confirms, same as every prior EPIC-84 lane.

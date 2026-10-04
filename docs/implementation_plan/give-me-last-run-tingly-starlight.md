# Fix TRADE_STOPPED_STRUCTURAL mislabeling in backtest_v2.py

## Context

While tracing a divergence between a research oracle and a real trade earlier this session, I
found a real (currently dormant) bug in the backtest dispatch layer: `BacktestRunner`'s action
dispatch collapses a **structural kill** (`CRTEngine.close_structural()`, the SEM-021
displacement-origin-invalidation exit) into the same code path as an ordinary **stop-loss
touch**, mislabeling it and repricing it wrong.

**The bug**, in `src/runtime/backtest_v2.py`'s per-candle dispatch:
```python
elif "TRADE_STOPPED" in action or "TRADE_TP2" in action or "TRADE_TP1" in action:  # :3085
    ...
    if "STOPPED" in action:                                                        # :3098
        ...
        exit_raw, reason = t.sl_price, "STOPPED"                                    # :3110
```
`action` can be `"TRADE_STOPPED"` (ordinary SL touch, from `ExecutionEngine.update_trade`) **or**
`"TRADE_STOPPED_STRUCTURAL"` (from `ExecutionEngine.close_structural()`,
`crt_engine_v2.py:2523-2547`). Both `"TRADE_STOPPED" in action` and `"STOPPED" in action` are
substring checks, so a structural kill silently falls into the same branch and gets booked at
`t.sl_price` under the reason `"STOPPED"` — even though `close_structural()`'s own docstring is
explicit that it "Books at `exit_price` (the bar CLOSE), never at the displacement origin —
booking at the origin would assume a fill at a level the bar may never have offered" (the SL
price is exactly that kind of assumed level for this exit type). The mislabeling also erases the
distinction in the trade ledger between "hit its stop" and "structurally invalidated" — data a
downstream reader (or a future finding) would have no way to recover.

**Confirmed currently dormant, not a live production risk:** `displacement_origin_kill_enabled`
defaults `False` (`state_identity.py:265`) and is `False` on the active config
(`configs/production/v2_htfcrt_2026_08.json` has no such key, and
`tests/test_displacement_origin_kill.py::test_the_arm_is_reachable_only_from_a_non_promoted_shadow_config`
asserts this explicitly). So `close_structural()` cannot fire on any currently-active or
historical run examined this session — this fix is byte-identical everywhere it matters today.
**But it is `True`** in the existing shadow config `configs/production/v2_dispkill_shadow_2026_08.json`
— built specifically to exercise this feature — so any backtest run against that shadow config
today would silently mislabel/misprice a structural-kill exit, and nothing currently catches it:
`tests/test_displacement_origin_kill.py` only unit-tests the `CRTEngine`/`ExecutionEngine`
primitives (`_displacement_origin_kill`, `close_structural`), never `backtest_v2.py`'s dispatch
layer — this is a genuine, previously-uncovered gap, not a duplicate of existing coverage.

## Approach

**File: `src/runtime/backtest_v2.py`**, the dispatch block at lines 3085-3126.

1. Extract the existing exit_raw/reason resolution logic (currently inline in the `elif`) into a
   small pure helper, e.g. `_resolve_exit(action, t, trade_status, candle, partial_tp_enabled,
   partial_tp_fraction) -> tuple[float, str]`, so it's unit-testable in isolation the same way
   `tests/test_displacement_origin_kill.py` already tests `close_structural` directly (no need
   to boot a full `BacktestRunner`/loop for the test). This is a pure refactor of logic that's
   already there — no new behavior for the existing `TRADE_STOPPED`/`TRADE_TP1`/`TRADE_TP2`
   paths.
2. Add the missing branch, checked **before** the substring-matched `if "STOPPED" in action:`,
   mirroring the existing TP1-partial-blend pattern used for `TP1_BE_STOP`/`TP1_TP2`:
   ```python
   if action == "TRADE_STOPPED_STRUCTURAL":
       if trade_status == "TP1" and partial_tp_enabled:
           # Mirrors close_structural's own TP1-status accounting: partial kept, only
           # the runner is closed, at the bar's close (not at sl_price).
           exit_raw = partial_tp_fraction * t.tp1_price + (1.0 - partial_tp_fraction) * candle.close
           reason = "TP1_STRUCTURAL_STOP"
       else:
           exit_raw, reason = candle.close, "STOPPED_STRUCTURAL"
   elif "STOPPED" in action:
       ...   # unchanged — now only ever reached for genuine "TRADE_STOPPED"
   ```
   `exit_raw = candle.close` matches exactly what the engine already passes into
   `close_structural(_t, candle.close)` at the call site (`crt_engine_v2.py:2932`), and the
   TP1-status blend mirrors `close_structural`'s own internal `trade.pnl = trade.partial_pnl +
   0.5*pnl_direction*(exit_price - entry_price)` calc for that case — `backtest_v2.py`'s ledger
   never reads `trade.pnl` directly, it always recomputes independently from `exit_raw`, so this
   blend is necessary for the TP1-status case to be accounted correctly.
3. New `exit_reason` values (`"STOPPED_STRUCTURAL"`, `"TP1_STRUCTURAL_STOP"`) are safe for
   existing consumers — checked `tp1_hits`/`tp2_hits` (`backtest_v2.py:1473-1474`) use inclusive
   `in (...)` membership, not an exhaustive match, and neither new value belongs in that set
   (consistent with the existing `TP1_BE_STOP`/`GAP_RESET_CLOSE` reasons, which are also
   excluded from TP-hit counts today). No schema doc exists for `exit_reason` values
   (`docs/reference/schemas.md` has no such enum) so no doc-sync is triggered.

## Guardrails

- **Byte-identical on every config with `displacement_origin_kill_enabled=False`** (every
  active/historical config touched this session) — the new branch is provably unreachable there,
  and the existing `"STOPPED"`/`"TP1"`/`"TP2"` branches are untouched in content, only
  reordered/extracted, so nothing about them changes either.
- This is a bug fix, not new economic/production authority (§6.5) — it does not enable, promote,
  or recommend turning `displacement_origin_kill_enabled` on anywhere; the shadow config stays
  non-promoted.
- No `params`-block edit → no config rehash needed (this only touches `src/runtime/backtest_v2.py`).

## Verification

1. **New unit tests** (extending `tests/test_displacement_origin_kill.py`, matching its existing
   style/fixtures) directly exercising `_resolve_exit(...)`:
   - `action="TRADE_STOPPED_STRUCTURAL"`, `trade_status="OPEN"` → `exit_raw == candle.close`,
     `reason == "STOPPED_STRUCTURAL"` (not `t.sl_price`/`"STOPPED"`).
   - `action="TRADE_STOPPED_STRUCTURAL"`, `trade_status="TP1"`, `partial_tp_enabled=True` →
     blended `exit_raw` toward `candle.close` (not `t.sl_price`), `reason ==
     "TP1_STRUCTURAL_STOP"`.
   - `action="TRADE_STOPPED"` (genuine) → unchanged: `exit_raw == t.sl_price`, `reason ==
     "STOPPED"` — proves the real SL path is untouched.
   - `action="TRADE_TP1"`/`"TRADE_TP2"` → unchanged outputs, proving the extraction didn't alter
     existing branches.
2. Run the focused test file: `venv/Scripts/python.exe -m pytest tests/test_displacement_origin_kill.py -v`.
3. Run `python scripts/maintenance/check_governance_invariants.py --all` (the GREEN_FLOOR) to
   confirm no regression elsewhere touching `backtest_v2.py`.
4. Byte-identity spot-check: re-run the XAUUSD backtest already produced this session
   (`--instrument XAUUSD --csv data/mt5/XAUUSD_M15.csv`, active config, `displacement_origin_kill`
   off) and confirm the trade ledger is unchanged from `g2_calendar_ab_2yr_20260910` /
   `htf_baseline_2yr_20260910`'s numbers — proving the refactor+fix altered nothing on the path
   that matters today.

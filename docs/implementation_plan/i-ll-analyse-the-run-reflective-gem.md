# HTF clock: 1-month XAUUSD baseline, then close the drift gaps

## Context

The XAUUSD disturbance analysis traced a collapsed CRT funnel (1 trade per 3,377 sweeps) to the
HTF reset clock. Follow-up verification this session **corrected the original diagnosis** and
uncovered a deeper defect than the one first reported.

### What was wrong in the first report (corrections)

| Claimed | Verified |
|---|---|
| `ACTIVE_VERSION` = `v2_multi_2026_04` | `ACTIVE_VERSION` = **`v2_htfcrt_2026_08`** |
| A 4→16 "drift" hit the active config | The active config was **born with 16** (commit `20cf607`) and never held 4 |
| Commit `63562ab` introduced an unexplained change | `63562ab` (2026-09-09) **fixed** legacy `v2_multi_2026_04` from 4→16 and added the explanatory comment in the same commit |

There is **no drift in the active system**. `v2_multi_2026_04` carried `htf_candles_per_range: 4`
from `5897209` (2026-04-30) until `63562ab` (2026-09-09). The analysed run
(`results/run_20260812_113506_XAUUSD`, dated 2026-08-12) used that legacy config *before* the fix,
so it ran at 4. The runs are stale artifacts of a legacy misconfiguration, not a live regression.

### What "HTF changed" actually is

`src/config_layer/crt_engine_v2.py:2577-2582`:

```python
if current_htf_id != state.active_range.clock_id:
    if state.current_state in [CRTState.EXPANSION, CRTState.RETEST]:
        return False, ""                      # DO NOT INTERRUPT ACTIVE SETUP
    return True, f"HTF changed: {state.active_range.clock_id} → {current_htf_id}"
```

`current_htf_id` comes from `HTFBuilder.push` (`src/runtime/backtest_v2.py:902-910`) — a **pure bar
counter**, not a clock:

```python
self._buffer.append(candle)
if len(self._buffer) >= self.candles_per_htf:
    self._htf_idx += 1
    self._complete_id = f"{self.instrument}-HTF-{self._htf_idx:06d}"
    self._buffer = []
```

So every Nth *pushed candle* the id increments, and on the next bar the state machine is force-reset
to `RANGE`, discarding SWEEP / DISPLACEMENT / SHADOW_PENDING progress. Exempt: `EXPANSION`,
`RETEST`, and any trade in `OPEN`/`TP1` (`crt_engine_v2.py:2574`). It destroys developing setups on
a **clock tick, not a market event**.

The user's arithmetic is correct: `htf_candles_per_range × bar_duration = HTF duration`, so 16×15m
= 4H and 4×1H = 4H. The value is timeframe-relative, and nothing validates it against the data's
actual bar size.

### Measured evidence (this session)

- **Cadence maps 1:1 to config.** 1-month run under `v2_htfcrt_2026_08` (16): HTF resets spaced
  exactly 16 bars in 120/124 cases. 2-yr run under legacy (4): exactly 4 bars in 10,598/10,666.
- **The clock is NOT calendar-true — the real defect.** Every XAUUSD trading day is exactly **92
  bars** (01:00→23:45). `92 mod 16 = 12`, so 16-bar windows never re-tile the day. Rollover phase
  drifts ~1h/day; across the month rollovers land on **all 23 hours** (always at `:45`). At 16 this
  is *not a 4H candle* — it is a 16-bar sliding window with daily phase drift.
- **A calendar-true feed already runs in the same loop.** `parent_crt.enabled: true`,
  `timeframe: "H4"` drives `ParentCRTFeed` → `ParentCandleBuilder` → `period_key(ts, "H4")`
  (`src/features/calendar_periods.py:112`), which is calendar-aligned by construction. The repo has
  **both clocks** and resets on the wrong one.
- **HTF dominates resets even at 16.** 1-month run: 144 RESET vs 111 STATE_TRANSITION, 124/144
  (86%) HTF-changed. The 4→16 correction cuts frequency 4× but does not change that resets
  outnumber transitions.

### Gaps to close

| # | Gap | Class |
|---|---|---|
| **G1** | `htf_candles_per_range` is a raw count; nothing validates `count × bar_minutes` against the declared `parent_crt.timeframe`. Legacy config sat at 1H-on-M15 for 4 months undetected. | silent-gap (F-056 / F-079 / F-083 / F-085) |
| **G2** | Count-based clock drifts ~1h/day, never aligns to a real H4 bucket, while a calendar-true H4 feed already exists alongside it. | correctness |
| **G3** | Run artifacts record no resolved `htf_candles_per_range`, so a run at 4 vs 16 is indistinguishable from its own artifact. | provenance |
| **G4** | Chart tab stamps `active_version` + active hash while drawing a run produced under a different config; the run's own `config_version` is absent from the payload. | provenance (introduced by the chart tab work) |

Decisions taken: run the existing **Jul 7 – Aug 6** slice; fix scope = **validation + provenance +
config-gated calendar clock, default OFF** (byte-identical by default).

---

## Phase 1 — Baseline run FIRST (read-only, no `src/` edits)

Evidence before doctrine (§6.5). Nothing in `src/` changes in this phase.

**Preflight** (mandatory per CLAUDE.md §1.5): `git status --porcelain` — the tree already carries
concurrent-session edits to `src/runtime/backtest_v2.py`, `src/research/*`, `src/control_plane/*`.
Confirm none of `backtest_v2.py` / `crt_engine_v2.py` / `parent_candle.py` are mid-edit by another
session before measuring. Confirm interpreter is `D:\Tradelatest\venv`.

**Run** (active config `v2_htfcrt_2026_08`, `htf_candles_per_range: 16`):

```bash
venv/Scripts/python.exe src/runtime/backtest_v2.py --csv data/XAUUSD_mt5_1month.csv --instrument XAUUSD --output results/htf_baseline_20260910
```

Echo the exact data path and row count before the run starts (§1.5). Expect 2,116 bars / 23
trading days / 2026-07-07→2026-08-06.

**Known prior:** the same slice under the same config already produced **0 setups / 0 trades**
(`results/htfcrt_1month/run_20260816_005200_XAUUSD`). A straight re-run is expected to reproduce
that and is **uninformative on its own** — its purpose is a byte-comparable reference point, not a
result. Report it as such; do not read an empty funnel as a structural finding at n=0.

**Report** (this is the deliverable of Phase 1, discussed with the user before Phase 2):
- reset counts by reason, RESET vs STATE_TRANSITION ratio
- HTF rollover spacing histogram + hour-of-day distribution (the drift instrument above)
- funnel as **entry decisions from `STATE_TRANSITION` events**, never `state_distribution`
  occupancy — occupancy inverts the golden path and is the documented trap
  (`project_entry_decisions_not_occupancy_rule`)
- diff vs `results/htfcrt_1month/run_20260816_005200_XAUUSD` to confirm reproducibility

---

## Phase 2 — Close the gaps (gated on Phase 1 discussion)

### G1 — Derive the expected count from declared intent, fail loud

`parent_crt.timeframe` already declares the intended HTF, so the correct count is **derivable** —
no new config key, no hardcoded 16:

```
expected = HOUR_GRID_HOURS[parent_crt.timeframe] * 60 // bar_minutes   # H4, M15 -> 16
```

- `HOUR_GRID_HOURS` already exists at `src/features/calendar_periods.py:61`.
- `bar_minutes` — reuse the modal-interval logic already in
  `src/data_ingestion/dataset_integrity.py` (`_TF_MINUTES`, modal-delta check at `:383`); do not
  write a new inference. `backtest_v2._preflight_dataset` is already an L3 call site (F-039), so
  the value is available at the right point in the run.
- Raise on mismatch with both values named. Skip the check when `parent_crt.enabled` is false
  (no declared intent to validate against) — record that as an explicit skip, not silence.

Placement: `BacktestRunner`, immediately after the existing dataset preflight. This makes the
legacy 4-on-M15 configuration **unloadable** rather than silently wrong.

### G2 — Config-gated calendar clock, default OFF

Follow the established F-061 `normalization_basis` / F-066 `session_timestamp_basis` pattern:

- New key `backtest.htf_clock_basis`: `"count"` (default) | `"calendar"`. Strict `_require()` read
  with an explicit default for back-compat — no silent `.get(key, literal)` (§6.5 hard rule).
- `"count"` → today's `HTFBuilder` path, **byte-identical**.
- `"calendar"` → clock id is `period_key(candle.timestamp, parent_crt.timeframe)`. This is
  PIT-clean by construction: it is a pure function of the current bar's timestamp, needs no builder
  state, and cannot look ahead. Do **not** read `ParentCandleBuilder._cur_key` (private, and
  unnecessary).
- `backtest` is not a `params` block → **hash-neutral**, no rehash required.

Files: `src/runtime/backtest_v2.py` (`BacktestConfig` field + `from_prod_config` + the
`htf.current_htf_id` call site at `:2452`), and both production configs for the new key + comment.

`crt_engine_v2.py` needs **no change** — it compares whatever clock id it is handed.

### G3 / G4 — Provenance

- Add resolved `htf_candles_per_range` and `htf_clock_basis` to the summary dict
  (`backtest_v2.py:1300-1326`, alongside the existing `config_version`).
- Chart tab: stamp the **run's own** `config_version` from its summary instead of the active
  version, and surface `htf_clock_basis`. Files: `src/charts/chart_api.py`,
  `ui_kits/crt_dashboard/` — both already modified in this working tree, so coordinate with the
  concurrent session before editing.

### Tests

- `htf_candles_per_range × bar_minutes == parent_crt.timeframe` passes on both production configs.
- Mismatch (simulate legacy `4`) raises, with both numbers in the message.
- `htf_clock_basis: "count"` reproduces the Phase-1 ledger **byte-identically** (the parity proof
  §6.5 requires).
- `period_key`-based ids roll over on real H4 boundaries and are stable across a session gap.

---

## Verification

1. Re-run the Phase 1 command with `htf_clock_basis: "count"` → assert byte-identical events,
   trades, and summary vs the Phase 1 baseline. This is the gate; a diff means a wrong default.
2. Run the matched A/B on the same slice (`"count"` vs `"calendar"`) and report Δ in resets,
   RESET:STATE_TRANSITION ratio, and entry-decision funnel. Confirm calendar rollovers land on
   exactly 6 fixed hours/day instead of drifting across 23.
3. `venv/Scripts/python.exe scripts/maintenance/check_governance_invariants.py --all` — capture
   the baseline failure count **before** editing so pre-existing reds are not misread as
   regressions (branch is known to carry some).
4. Confirm config hashes unchanged (`backtest` is non-`params`).

## Out of scope

- **Making `"calendar"` the production default** — a behaviour change requiring a promotion gate
  and re-certification under §6.5/§6.8, explicitly deferred to a separate authorized turn.
- Fresh MT5 data (module not installed in this venv).
- `rejected_trades: 0` vs 12 `FILTER_REJECTED` events — a real pre-existing summary
  under-reporting bug, but a separate defect; report, don't fix here (§1.2).
- Re-running the 2-year corpus, or any economic claim. No G001 authority is sought or granted;
  n=0–1 trades supports no economic conclusion.

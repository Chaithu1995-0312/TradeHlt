> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: n/a  <!-- dates inferred from file mtime; predates the dated-header convention -->

# Plan — Execution-Planner Replay: split the EXECUTION edge into Selection vs SL/TP structure

## Context

The Alpha Ledger (just shipped, `docs/analysis/alpha-ledger-recovery-2026-06-03.md`) established the
operating thesis: **the edge is in the execution-selection process + throughput, not static
features** (F-001/F-002/F-003). But one question underneath it is still open. The gate-contribution
study (`gate-contribution-bnbusdt-2026-06-03.md:13,18`) showed the entire `+0.584R` edge appears at
the **RETEST→EXECUTION** gate (RETEST candidates `−0.039R` → executed `+0.545R`). Its own critical
caveat (`:29`) says that jump **conflates two things it cannot separate**:

1. **Selection** — *which* RETEST candles are chosen (session filter + score threshold), and
2. **SL/TP structure** — the CRT engine's structure-based SL/TP (`sl = swing ± 0.2·ATR`) vs the
   counterfactual scanner's vanilla fixed SL/TP (`1·ATR SL / 2·ATR TP`).

It explicitly names the fix: *"a counterfactual that replays the execution planner's SL/TP on the
rejected retest candidates."* The user chose this as the highest-information-value next step — it
quantifies *why* the edge exists (so all future roadmap decisions are better informed) and is the
RESEARCH item E-18/E-25 / open finding **F-010**.

**Key correction from exploration:** `ExecutionPlannerV1_2` does **not** compute SL/TP — the comment
at `execution_planner.py:9,179` defers it to the CRT engine, and `compute_crt_levels()`
(`src/core/gate_intelligence.py:24-84`) is the pure mirror of `crt_engine_v2.py:1162-1201`. So the
real contrast is **vanilla fixed SL/TP vs CRT structure SL/TP**, on **selected vs rejected** RETEST
candidates — a clean 2×2.

**Decisions locked (via user):**
- **Faithful via additive telemetry** (not offline re-derivation). The CRT engine knows direction +
  structure levels; no log carries them for rejected RETESTs (verified: `crt_transitions.jsonl` has
  `direction:None` for all 6,301 RETEST + 1,519 EXECUTION; `CANDIDATE_LIFECYCLE`/`DECISION_DISTANCE`
  carry score + `death_reason`/`rejection_reason` but no direction or levels). Engine emits the
  fields per RETEST candidate (no behavior change — same pattern as Phases 2b/3b added `shadow_used`,
  `score_at_approval`, `expansion_dwell_stats`).
- **Core 2×2 only** — no live-only ExecutionPlanner+Ultron arm this pass (keeps scope tight; the
  structure SL/TP already mirrors the live SL/TP path).

## The experiment — a 2×2 attribution

All four cells computed with the **same** forward simulator so only the varied dimension moves:

|                          | Vanilla SL/TP (`1·ATR` / `2·ATR`) | CRT structure SL/TP (`swing ± 0.2·ATR`) |
|--------------------------|-----------------------------------|------------------------------------------|
| **Selected** (executed)  | **A**                             | **B**  (anchor: ≈ real `+0.545R`)        |
| **Rejected RETEST**      | **C**  (≈ RETEST stage `−0.039R`) | **D**  (the missing measurement)         |

- **SL/TP-structure effect** = `mean(B−A)` on selected **and** `mean(D−C)` on rejected.
- **Selection effect** = `mean(A−C)` (vanilla) **and** `mean(B−D)` (structure).
- The observed `+0.584R` jump = path `C → B`; the 2×2 decomposes it and reports whether the two
  effects are additive (interaction term).
- **Verdict logic:** if `D` lifts toward `B` (structure SL/TP rescues rejected candidates) → much of
  the edge is **SL/TP structure** (and selection is over-rejecting). If `D` stays ~`C` while
  `B ≫ A,C,D` → the edge is **selection** (the chosen candles are genuinely better, SL/TP is
  secondary). This directly informs whether to invest in selection policy vs exit structure.

## Reuse (do NOT reinvent)

- `compute_crt_levels(entry, direction, low, high, atr, …)` — `src/core/gate_intelligence.py:24` —
  the structure SL/TP (cells B, D).
- `simulate_exit(entry, direction, sl, tp1, tp2, forward_candles, max_candles)` —
  `src/analytics/sl_tp_comparator.py:133` — the single forward simulator for all four cells
  (exit priority TP2>SL>TP1, matches BacktestRunner).
- `_aggregate_variant_results(results)` — `src/analytics/sl_tp_comparator.py:196` — per-cell
  expectancy / WR / PF / drawdown / exit-reason mix.
- `SLTPComparator.load_candles_from_csv(csv)` — `src/analytics/sl_tp_comparator.py:482` — forward
  candle loader.
- Vanilla mults + `max_candles` come from the existing `sl_tp_comparison` config section (consumed
  via `get_prod_section`) — no new config section, no magic numbers. Vanilla = `1.0·ATR` SL /
  `2.0·ATR` TP (the `opportunity_scanner` definition).
- Harness conventions mirror `scripts/research/phase6e_shadow_ab.py` (measure-only, `results/` only,
  control-arm trust gate, point-in-time companion doc).

## Phase A — additive telemetry (engine, no behavior change)

In `src/config_layer/crt_engine_v2.py`, at the RETEST-candidate evaluation point (where the engine
already decides accept→EXECUTION vs reject on session/zone/score — near the existing
`CANDIDATE_LIFECYCLE` / `DECISION_DISTANCE` emission), emit one new append-only JSONL record per
RETEST candidate. Everything below is **already in engine scope** at that moment — this only records
it:

```
kind: "RETEST_REPLAY"            # follows §3.2 JSONL convention (timestamp + kind, append-only)
timestamp, candle_index
direction:    int (1/-1)         # the engine's intended side — the field no log currently carries
entry, low, high, atr            # inputs to compute_crt_levels
sl, tp1, tp2                     # the engine's own structure levels (so D needs no re-derivation)
intent, score
accepted:     bool
reject_reason: str | null        # off_session:* | not_discount_zone | not_premium_zone | score_*
```

- Pure telemetry: no gate, no SL/TP, no transition logic changes. No config change → **no re-hash**.
- Document the new line in `docs/reference/schemas.md §9` (JSONL line schemas).
- This is the only engine edit; it is additive and reversible.

## Phase B — offline replay script (measure-only)

New `scripts/research/execution_planner_replay.py`, thin wrapper mirroring `phase6e_shadow_ab.py`:

1. Run one deterministic backtest on `data/BNBUSDT_M15.csv` (active `v4_multi_2026_06`, seed 1337) to
   produce the new `RETEST_REPLAY` telemetry + `BNBUSDT_trades.csv`. (Reuse `BacktestRunner` /
   `CandleLoader` / `load_prod_config_from_registry` exactly as `phase6e` does.)
2. Partition RETEST candidates: **Selected** = `accepted==True` (cross-check vs `trades.csv candle_idx`);
   **Rejected** = `reject_reason` set.
3. Load forward candles via `SLTPComparator.load_candles_from_csv("data/BNBUSDT_M15.csv")`.
4. Compute the four cells, each via `simulate_exit` on candles strictly **after** the entry index
   (no lookahead):
   - **A/C** = vanilla `1·ATR/2·ATR` levels on selected / rejected.
   - **B/D** = the engine's recorded structure `sl/tp1/tp2` on selected / rejected.
5. Aggregate each cell with `_aggregate_variant_results`; compute the selection / SL/TP / interaction
   deltas; write the verdict.
6. **Trust gate (hard stop, like phase6e control arm):** cell **B** expectancy must reproduce the
   real executed `+0.545R` within tolerance (and `D`'s entry set must match the rejected count from
   the funnel). If not, the harness is untrustworthy → exit non-zero, no doc.
7. Emit `results/execution_planner_replay/replay_bnbusdt.json` + hand-write the companion
   `docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md` with the point-in-time header
   (`> Point-in-time … NOT a living doc · Driver: scripts/research/execution_planner_replay.py ·
   Raw: results/execution_planner_replay/replay_bnbusdt.json · Config: v4_multi_2026_06`), the 2×2
   table, the attribution decomposition, and the verdict.

## Critical files

- **Edit (additive):** `src/config_layer/crt_engine_v2.py` (emit `RETEST_REPLAY` at the RETEST
  accept/reject point) · `docs/reference/schemas.md` (document the new JSONL line).
- **Create:** `scripts/research/execution_planner_replay.py` · `docs/analysis/execution-planner-replay-bnbusdt-2026-06-03.md`.
- **Reuse (read-only):** `src/core/gate_intelligence.py:24` · `src/analytics/sl_tp_comparator.py:133,196,482` ·
  `scripts/research/phase6e_shadow_ab.py` (template) · `src/runtime/backtest_v2.py` (BacktestRunner/CandleLoader).
- **Tests:** add `tests/` coverage for the new emission + the 2×2 math (see Verification).
- **Findings:** on results, update **F-010** / **F-002** in `docs/current-findings.md` (and the
  Repository Truths Index mirror) per §6.2 — this experiment is exactly what F-010 was waiting on.

## Verification (end-to-end)

- **Determinism / no-lookahead:** seed 1337; `simulate_exit` only sees candles `> entry_index`; two
  runs byte-identical. Confirm the additive telemetry leaves trade count / ROI unchanged vs the prior
  `v4` baseline (telemetry-additive invariant — same check Phases 2b/3b used).
- **Anchor gate:** cell **B** (structure SL/TP on selected) reproduces real executed `+0.545R` /
  PF ~2.54 within tolerance; cell **C** (vanilla on rejected) reproduces the RETEST-stage `≈ −0.039R`
  from gate-contribution. If both anchors hold, cells A and D are trustworthy.
- **Tests:** unit-test the new engine emission (one record per RETEST candidate, required fields
  present, `accepted`/`reject_reason` mutually consistent) and the attribution math (selection +
  SL/TP + interaction deltas reconstruct the `C→B` total). Run `python -m pytest tests/` for the CRT
  + analytics domains; run `tests/test_current_findings.py` after the F-010 update.
- **Artifact review:** the companion doc carries the point-in-time header, the 2×2, the decomposition,
  and a clear selection-vs-SL/TP verdict; `docs/analysis/readme.md` index row added.
- **§6 mandates:** SESSION LOG appended; affected topic doc synced (§6.1); F-010/F-002 updated (§6.2).

## Constraints / non-goals

- Measure-only: writes `results/` + the new docs + the additive telemetry line; **no config edit, no
  promotion, no gate/SL-TP/transition behavior change.** No re-hash (telemetry, not config).
- BNBUSDT-only this pass (per-instrument doctrine F-009); the script takes `--instrument` so SOL/ETH/BTC
  can follow without code change.
- No live-gate (ExecutionPlanner+Ultron) arm this pass — deferred as the natural follow-up that
  closes F-010 fully.

# Execution Plan — Per-Instrument Session Optimization (the pivot's first lever)

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: Trd (governance/execution track)

## Context

A Phase-0 funding review (H3) concluded that **state *discovery* is mostly solved; state *exploitation/selection* is the live edge.** Path-enrichment / Liquidity-V2 features FAIL the dual gate (ΔAUC≈0, net RR negative despite AUC 0.65), while **governance + selection dominate measured ROI** (+4.91% → +20.59% vs ~+1.3% intelligence upside). The ruling: **freeze V2 intelligence work; fund governance, execution selection, per-instrument sessions, and drift-based risk scaling** until a challenger beats the incumbent (+0.328R) on the same economic gate.

This plan operationalizes the **#1 measured ROI lever** identified back in Phase 6b: the funnel bottleneck is **RETEST→EXECUTION (11.2%)**, where **64 valid retests are killed by the SESSION filter** (44 OFF_SESSION + 20 ASIA) — *not* by the score threshold (134/135 pass). The lever is the per-instrument `allowed_sessions` set.

### What already exists (verified in code + promotion_log)
- **Resolver is built.** `resolve_allowed_sessions(engine_runner, instrument)` + `_canon_session` (`src/config_layer/production_config.py:266–304`) resolve per-instrument overrides, preserve `OFF_SESSION`. Used by live load, `backtest_v2.py`, **and `ConfigValidator.validate()` (`config_validator.py:435–439`)** — so validation already scores per-instrument sessions exactly like runtime. No new wiring needed for sessions to flow.
- **Filter gate:** `src/config_layer/crt_engine_v2.py:2589–2611` — labels each candle's session from `session_windows` (LONDON 07–10, NEWYORK 13–16, ASIA 00–03 UTC; everything else → `OFF_SESSION`; `overlap` is an inert token — no window), rejects `FILTER_REJECTED` reason `off_session:{SESS}` when not in `allowed_sessions`.
- **Partly shipped.** Active = **`v4_multi_2026_06`** (not v2 — memory was stale). v4 opened **`BNBUSDT` → all sessions** (`london,new_york,overlap,asia,off_session`), ConfigValidator APPROVE (BNB 39 trades / PF 1.63). **`SOLUSDT` was excluded** at PF~0.98 (`promotion_log` line 16, audit-2026-06-02).

### The two gaps this plan closes
1. **Blanket-open ≠ optimal.** BNBUSDT's "all sessions" was a *measurement open*, never compared against subsets. Dropping ASIA or OFF_SESSION may raise PF/expectancy and cut DD. We need a **session-subset sweep** to *select*, not just open.
2. **No OOS evidence.** v4's APPROVE was full-window. OOS today is only tuner-internal date-slicing (`auto_tuner_multi.py` `--train-split`), **never a promotion gate** ("Part 4A OOS" does not exist as a harness). Session selection is the classic overfit trap; it must be confirmed on holdout before promotion.

## Goal

Per instrument, **select the `allowed_sessions` subset that maximizes economic ROI on in-sample and holds up out-of-sample**, then promote those subsets through the governed path. Concretely: confirm/refine BNBUSDT, and rescue or finally retire SOLUSDT with evidence — replacing the blanket-open with an OOS-validated selection.

## Design

The sweep is **additive and measure-only** (mirrors the Phase 6 "ROI Step" doctrine). Sessions resolve independently of the global tuned `params`, so we **hold v4's params fixed** and sweep *only* the per-instrument `allowed_sessions`. Search space per instrument is the 15 non-empty subsets of `{LONDON, NEWYORK, ASIA, OFF_SESSION}` (`overlap` inert; keep for compat).

New tool: **`scripts/analysis/session_sweep.py`** (thin CLI wrapper; no business logic — per `CLAUDE.md §3.3`). For one instrument it:
1. Loads the instrument CSV via `CandleLoader`; computes the in-sample/OOS split index from `--train-split` (reuse the exact index math in `auto_tuner_multi.py:610–622` so OOS semantics match the tuner).
2. For each candidate subset, runs `backtest_v2` on the **in-sample** window with `allowed_sessions` injected via `dataclasses.replace(crt_config, allowed_sessions=subset)` (the same pattern `config_validator.py:435–439` uses) — **no config-file writes**.
3. Records economic metrics per subset: `approved_trades`, `win_rate`, `expectancy_rr`, `profit_factor`, ROI%, `max_drawdown` (reuse `BacktestMetrics`; ROI per the Phase 6 ROI telemetry already in `backtest_v2`).
4. Ranks subsets; re-runs **top-K on the OOS holdout**; flags rank stability (selected subset must keep positive expectancy & PF>1 OOS and not collapse vs in-sample).
5. Emits `results/analysis/session_sweep_{INSTRUMENT}.json` (leaderboard + IS/OOS deltas + recommended subset) and a console summary via `console_safe`.

**Decision rule (the economic gate, reused):** pick the subset with the best in-sample `expectancy_rr`/PF whose **OOS** run keeps `expectancy_rr > 0` and `PF > 1` and ranks in the top-K both windows. If no subset clears OOS → instrument stays at its current/empty selection (document the FAIL, like SOLUSDT).

## Steps

1. **Build the sweep harness** — `scripts/analysis/session_sweep.py`. Reuse `CandleLoader`, `backtest_v2`, `BacktestMetrics`, `resolve_allowed_sessions`/`dataclasses.replace`, `console_safe`. Argparse: `--instrument --data-dir --version (default active) --train-split 0.8 --top-k 5 --output`.
2. **BNBUSDT sweep** — run vs active v4 params. Confirm whether all-sessions is optimal or a subset (e.g. drop ASIA) wins on PF/DD. Reproduce the Phase 6b funnel as a sanity check (OFF_SESSION+ASIA materially change trade count).
3. **SOLUSDT sweep** — find a profitable OOS-stable subset (it may be profitable in a *subset* even though all-sessions was PF~0.98) or confirm retirement with OOS evidence.
4. **Assemble candidate version `v5_multi_2026_06`** — copy v4, set `engine_runner.allowed_sessions_overrides` to the *selected* subsets per instrument (BNBUSDT refined; SOLUSDT added only if it passed). Re-hash: `python scripts/maintenance/_compute_hash.py`.
5. **Validate** — `python src/config_layer/config_validator.py validate-prod --data-dir data --version v5_multi_2026_06`. Must return **APPROVE**.
6. **Promote (governed)** — `python src/governance/promotion_manager.py from-report --report <approved report> --version v5_multi_2026_06 --data-dir data --instruments ...`, with the OOS sweep reports cited in `--notes` as the pre-promotion OOS evidence (compensating for the absent hard OOS gate). Appends `PROMOTED` to `configs/promotion_log.jsonl`; updates `ACTIVE_VERSION`.
7. **(Optional follow-up, separate Brick)** — harden OOS from "required evidence artifact" into a real gate: add an OOS check to `ConfigValidator.validate()` or make `session_sweep`'s OOS-stability a reusable promotion precondition. Out of scope for the first pass to keep governance changes minimal.

## Critical files
- **New:** `scripts/analysis/session_sweep.py` (only new code; thin wrapper).
- **Read/reuse:** `src/config_layer/production_config.py:266–304` (resolver), `src/config_layer/config_validator.py:435–439` (override application pattern), `src/runtime/backtest_v2.py` (runner + ROI/BacktestMetrics), `scripts/training/auto_tuner_multi.py:610–622` (IS/OOS split math), `src/config_layer/crt_engine_v2.py:2589–2611` (filter, for sanity-checking session labels), `src/utils/console_safe.py`.
- **Config edits (Step 4+):** `configs/production/v5_multi_2026_06.json` (new, derived from v4), `configs/production/ACTIVE_VERSION` (via promotion only).
- **Governance:** `src/governance/promotion_manager.py`, `configs/promotion_log.jsonl`.

## Verification (end-to-end)
1. **Harness correctness:** run `session_sweep.py --instrument BNBUSDT --train-split 0.8`. Confirm the all-sessions row reproduces v4's ~39 trades / PF~1.63 on the full window (sanity vs known promotion metrics), and that restricting to `{LONDON,NEWYORK}` collapses trade count (reproduces the Phase 6b 64-retest SESSION kill).
2. **No-lookahead / determinism:** OOS uses a strict forward index split (reuse tuner math); re-running yields identical leaderboards (`CLAUDE.md §4` no-lookahead invariant).
3. **Governance gate:** `config_validator.py validate-prod --version v5_multi_2026_06` returns **APPROVE**; promotion writes a `PROMOTED` line and flips `ACTIVE_VERSION`. Rollback path: restore archived v4 + re-point `ACTIVE_VERSION`.
4. **Regression:** run the pre-promotion pytest pack (`docs/reference/testing.md`); sessions changes touch no engine code, so failures would indicate harness/config breakage.

## Risks & notes
- **Overfit to OOS picks** — mitigated by top-K rank-stability rule + small, interpretable subset space (sessions, not continuous params).
- **`overlap` token is inert** — don't treat it as a real session; selection is over `{LONDON,NEWYORK,ASIA,OFF_SESSION}`.
- **Memory reconciliation (do on implement):** update `project_trd_m6_downstream.md` / Phase 6b notes — active prod is **v4_multi_2026_06**, BNBUSDT all-sessions already promoted, SOLUSDT excluded at PF~0.98; "Part 4A OOS" is a *gap to build*, not an existing harness.
- **Doctrine:** measure-only sweep first (no deviation flag needed); promotion goes through the existing APPROVE gate (no new authority). Per `CLAUDE.md §6`, append a SESSION LOG entry and (if it touches a topic doc) Sync per §6.1 on implement.

---
📝 SESSION LOG ENTRY
Date: 2026-06-03
Topic: Plan — per-instrument session optimization as first lever of the H3 "freeze V2 / fund governance+selection" pivot
Decision/Output: Plan written to plan file. Verified ground truth vs stale memory: active=v4_multi_2026_06; BNBUSDT already opened to all-sessions (APPROVE, PF1.63); SOLUSDT excluded PF~0.98; no OOS gate exists (only tuner --train-split). Plan: build measure-only session-subset sweep (scripts/analysis/session_sweep.py) with IS/OOS rank-stability decision rule → select optimal per-instrument allowed_sessions → promote v5_multi_2026_06 via governed APPROVE path, OOS reports as cited evidence.
Open Questions: Whether to harden OOS into a real ConfigValidator gate now or as a follow-up Brick (plan defers it).
Next Step: On approval — implement session_sweep.py, run BNBUSDT + SOLUSDT sweeps, then assemble/validate/promote v5.
---

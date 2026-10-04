# Gap Audit — MT5 Reality-Feedback Loop: Built vs. Missing

## Context

You pasted a long multi-model strategic analysis of Tradelatest's automation posture. Across all
three "solutions" it converges on a single recommendation: **"Finish the MT5 position-intelligence
and feedback system so every real trade becomes a reusable learning artifact"** / *"complete the
MT5 analytics feedback loop."* You asked (via the intent question) for a **gap audit vs. what's
already built — before any building.**

This document is that audit. It maps the target loop the analysis describes against the actual
code, verified by direct file reads (not just subagent report), and then states the *real* binding
constraint — which is **not** the one the analysis names.

**Target loop (from the analysis):**
`MT5 deals → position reconstruction → MFE/MAE → duration → session → regime → expectancy →
evidence report → finding → research update → paper validation → production approval`

---

## Headline Conclusion

The **measurement half** of the loop is built, test-gated, and mature (~90%). The **feedback half**
(reality-vs-forecast comparison → finding writeback → scheduler) is unbuilt. **But the top gap is
neither of those** — it is that **the only MT5 deals in existence are synthetic** (trade_generator
kernel-validation orders on an IC Markets demo). There is no edge-bearing, strategy-driven trade
flow. Layered on top: the spine is research-null (F-019…F-043, no validated directional edge).

So "close the loop" as literally stated would (a) have no real fuel, and (b) if fueled, mostly
re-confirm the existing null. The genuinely high-value, **edge-independent** work is different from
what the analysis ranks #1 — see *Recommended Sequencing*.

---

## What Is BUILT (verified)

### A. MT5 → PositionEpisode → FeatureRecord → InsightReport  (mt5_analytics/) — MATURE
| Stage | Module | Status |
|---|---|---|
| Read-only MT5 ingestion (deals/orders/positions/candles, UTC-normalized) | `mt5_analytics/core/mt5_adapter.py` | BUILT |
| Two ingestion paths: incremental daemon (30s poll) + explicit batch rebuild | `core/daemon.py`, `core/rebuild.py`, shared via `core/shared_pipeline.py` | BUILT; byte-parity test `tests/mt5_analytics/test_pipeline_parity.py` |
| Deal → `PositionEpisode` (VWAP entry/exit, net/gross/commission/swap, duration, volume-balance completion guard; handles pyramiding/partial/INOUT/reopen) | `engines/position_reconstructor.py`, schema `schemas/position_episode_v1_0.py` | BUILT (Phase 2a) |
| Episode → `FeatureRecord`: MFE/MAE in trade-R, RR, duration, **session** (LON/NY/ASIA/OVERLAP/OFF), **regime** (C/N/E/None/UNKNOWN) | `engines/features/*` | BUILT; purity guard forbids aggregate keys at feature layer |
| Read-only `InsightReport`: expectancy, win-rate, PF, Sharpe, recovery, exit-efficiency (capture ratio), **cost-drag** (commission/swap fraction of gross), attribution by session/regime/duration, Herfindahl `effective_n` | `analytics/insight_report.py` (imports only `analytics.metrics_oracle`) | BUILT (v0.6.0) |
| **Sufficiency gating** (min_n=30): underpowered buckets return `None`, make no claim | `analytics/insight_report.py` | BUILT (E-001 / F-019 discipline) |

### B. Execution telemetry (exec_telemetry/) — BUILT but capture is demo/manual only
| Stage | Module | Status |
|---|---|---|
| `ExecutionEvent` schema: requested vs filled price, signed slippage, send→fill latency, retcode/name, filling mode | `exec_telemetry/schemas/execution_event_v1.py` | BUILT (frozen v1.0) |
| Operational report: fill-rate, retcode histogram, adverse-slippage & latency distributions (sufficiency-gated); **operational-only, no PnL/expectancy by design** | `exec_telemetry/report.py` | BUILT |
| Capture path: `manual_tools/trade_generator.py --exec-log` → `runtime/exec_telemetry/<broker>/orders.jsonl` | producer | BUILT — **but requires live/demo order_send; runs only from trade_generator, not the live spine** |

### C. Reusable-but-unwired pieces (exist in main, corrected from subagent claims)
- `scripts/research/ingest_live_outcomes.py` — **EXISTS and is wired** into `src/engines/live_engine.py`
  + `scripts/training/phase5_calibration.py`. But it pairs `logs/live_alerts.jsonl` with a
  **hand-entered outcomes CSV** (`alert_id,pnl_rr_net,exit_reason,win`) and feeds the **Gaussian
  calibration** path — it is *not* a findings-writeback and *not* auto-fed from MT5 deals.
- `src/journal/trade_logger.py` — **EXISTS in main** (subagent wrongly said worktree-only); writes
  `logs/trade_journal.jsonl` from the alert/backtest lineage.
- `scripts/research/live_path_replay.py` — replays **backtest** trades through the live gate
  (ExecutionPlanner + UltronRiskGate); measure-only, writes to `results/live_path_replay/`. It is
  backtest-vs-backtest-gated, **not** live-vs-research.
- `src/research/qualification.py` (QualificationGate) + `src/research/measurement/forward_walk.py`
  — mature, but consume **backtest candles only**; no input contract for real executed outcomes.

---

## The Structural Gaps (verified MISSING)

1. **Two disjoint trade-truth lineages that never meet.**
   - *Python alert lineage*: `live_engine` → alert → (human places order) → manual
     `ingest_live_outcomes` / `trade_logger` → `logs/*.jsonl`, keyed by `alert_id`.
   - *MT5-deal lineage*: `mt5_analytics` daemon/rebuild → `PositionEpisode` (the "MT5 owns financial
     truth" doctrine), keyed by deal tickets.
   - **No join key or module bridges them.** An alert's forecast is never reconciled to the MT5
     episode that realized it.

2. **exec_telemetry ↔ mt5_analytics disconnect.** `src/live/` has **zero** references to
   exec_telemetry / insight_report / findings (grep-verified). Slippage/latency/fill-quality
   (execution reality) is never joined to realized expectancy (outcome reality) — so *"are costs /
   slippage dominating returns?"* cannot be answered end-to-end.

3. **InsightReport → Finding writeback: entirely MISSING.** `mt5_analytics` never touches
   `docs/current-findings.md` / `data/findings.jsonl`; insight is read-only + dashboard-only. (This
   is *partly intentional* — §6.5 "information, not authority"; findings are human-authored by
   design.)

4. **Reality-vs-forecast comparison: MISSING.** Nothing compares a live `InsightReport` (expectancy,
   capture ratio, cost fraction) against the backtest forecast that motivated the trade. Note: the
   "reality_gap +4.16R" in **F-025 is a backtest-internal ceiling** (`src/research/exit_grid.py`
   `ceilings()`: `mfe_capture − structural`), **not** a live-vs-research measurement.

5. **No scheduler.** No `.github/workflows`, cron, or Task-Scheduler entry runs the daemon,
   regenerates insights, or refreshes findings (grep-verified). Everything is human-initiated.

6. **No real trade fuel (the decisive gap).** Confirmed by you: only synthetic trade_generator demo
   deals exist. The loop's *input* — real strategy/alert-driven executed trades — does not yet exist.

---

## Recommended Sequencing (edge-independent first; NOT yet authorized — audit only)

The analysis ranks "build the writeback/feedback plumbing" as #1. Given synthetic-only fuel + a
null spine, that ordering wastes effort on plumbing with nothing true to carry. Sharper order:

- **Tier 0 — Generate real fuel (human-in-loop).** Start placing a small number of *actual*
  alert-driven demo trades (from `live_engine` alerts) so real `PositionEpisode`s exist. Without
  this, every downstream module measures noise. Cheapest, highest-leverage, edge-independent.
- **Tier 1 — exec_telemetry ↔ analytics join (edge-independent).** Wire `src/live/mt5_bridge.send_order`
  to emit `ExecutionEvent`s, and build the one missing bridge that answers *"is cost/slippage
  dominating?"* by joining execution reality to `InsightReport` outcomes. This is valuable **even on
  a null spine** — it tells you whether costs alone would kill any future edge (extends F-025/F-034).
- **Tier 2 — Reality-vs-forecast comparison.** A `reality_gap_audit` that reconciles the alert
  forecast (Python lineage) to the realized MT5 episode (MT5 lineage) via a shared join key — the
  actual "does live match research?" question.
- **Tier 3 — Finding writeback + scheduler.** Only after Tiers 0–2 produce trustworthy signal.
  Keep the human-authored-finding governance boundary (§6.5); automate the *evidence packet*, not
  the verdict.

## Verification (how to confirm this audit before/while building)

- Confirm no live wiring: `grep -rn "exec_telemetry\|insight_report" src/live src/runtime/live_engine_hook.py` → expect none.
- Confirm findings are hand-authored: `grep -rn "current-findings\|findings.jsonl" mt5_analytics/` → expect none.
- Confirm the measurement pipeline runs: `pytest tests/mt5_analytics tests/exec_telemetry -q` (should be green).
- Inspect real fuel state: list `runtime/mt5_analytics/**/episodes*.jsonl` and check whether any
  episode came from a non-`trade_generator` source.

## Scope / Doctrine notes
- This is an **audit deliverable**, not an implementation. No code is changed by this plan.
- Read-only per plan mode. If you approve, the natural next step is Tier 0/Tier 1 as a *separate*
  scoped task, under the normal §6 SESSION LOG + Authority-Ladder gates.
- Governed-doc impact: none registered here; if any gap above is later contested against a finding,
  it goes through the Documentation Drift Protocol, not a silent edit.

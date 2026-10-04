# EXECUTION PLAN — R2 (measure) → R1 (drift gate) → G1 (integrity gate)

> Created: 2026-06-03 · Updated: 2026-06-03 · Milestone: R2 measurement → governance/execution wiring (FUNDED)
> Mode: **execution, not analysis.** No new ledgers. No redesign. No KILLED/FROZEN orphan work
> (TradeNet V2 / Probability Surface / Liquidity V2 / ReplayMemory). No new feature/cluster intelligence.

## Context
Repository archaeology is complete (Repository Truths → Open Defect Ledger → Profit Impact Ledger →
Implementation Packets). The bottleneck is now execution. The next meaningful information comes only
from **running R2**. Order: measure first, then fix verified defects, then re-rank with measured PF.

---

## R2 COVERAGE PROOF (the gate the user required before coding R2)

*"Show every code path where ExecutionPlannerV1_2 and UltronRiskGate can affect live outcomes, and
prove the replay harness covers 100% of them."* Verified by code read:

### Live entry points (where these components affect outcomes)
| Surface | Path / contract | In R2 scope? |
|---|---|---|
| **Primary (v4 prod)** | `live_engine_hook.py:768-872` — `planner.plan()` → `compute_crt_levels` → `UltronRiskGate`+`UltronRiskGateWrapper.evaluate()` | **YES — 100% target** |
| `execution/loop.py` | generic injected `risk_gate: Callable(signal)->{allow:bool}` (`:60,163`) — abstract, different contract; not the v4 evaluate path | NO (acknowledged; not the prod path) |
| `portfolio/allocator.py:23` | **comment-only** ref to non-existent `UltronRiskGate.check_trade` — no real call | NO (no consumer) |
| `core/types.py:120` | `MT5Bridge.place_order` guard requires prior Ultron APPROVE — downstream of evaluate | covered via primary |
| `llm_research/forward_tester.py:119` | research forward-test, not live trading | NO (research) |

→ The **single production decision path is the primary one**; R2 covers it fully. The others are
explicitly out of scope and named so we never claim false 100%.

### Outcome levers the harness MUST reproduce (each = a way live ≠ replay if missed)
**ExecutionPlannerV1_2.plan()** (`execution_planner.py`): reject_invalid/engine/unknown_intent (:193-229),
**GateIntelligence** accept/reject (:251), **intent classification**, **intent-specific TTL** →
`validity_ttl_sec` (`_TTL_MAP` :71-104, :259-288), entry price.
**UltronRiskGate.evaluate()** (`ultron_risk_gate.py`): gate_disabled passthrough (:203), **Ch0 persisted
kill-switch** (:214), **Ch1 TTL** (:226), **Ch2 RR floor + spread/slippage tax** (:241), **Ch2.5
per-symbol duplicate** (:260), **Ch3 daily trade limit** (:273), **Ch4 daily-loss kill switch (stateful,
persisted)** (:278), **Ch5 portfolio exposure cap + per-trade risk cap** (:298), **Ch6/6b SL distance
floor** (:309), **Ch7 final sizing** = `min(hint, risk_usd/risk_per_unit)` (:334).
**UltronRiskGateWrapper**: regime pre-scale of `risk_percent` (:110-114).

### The decisive coverage requirement (the real failure mode)
**Ch0/Ch2.5/Ch3/Ch4/Ch5 are path-dependent.** A per-trade replay with fixed `portfolio_state` would
silently skip them and **measure the wrong thing**. The harness therefore **threads evolving portfolio
state trade-to-trade**: `account_balance, total_open_risk_pct, trades_today, daily_loss_pct,
open_positions`, with daily reset (`_daily_reset_tracker`) and kill-switch persistence honored. This is
the explicit coverage contract; the trust gate (below) fails the run if it isn't met.

---

## PACKET R2 · live-path validation (BUILD + RUN FIRST — measure-only)
**Deliverable:** `scripts/research/live_path_replay.py` (writes ONLY `results/live_path_replay/`).
**Build** (mirror `live_engine_hook.py:768-872`; reuse `execution_planner_replay.py:66-86` faithful
config load):
1. Faithful backtest on ACTIVE v4 → accepted trades + `RETEST_REPLAY` telemetry.
2. Per accepted trade, run the **real** `ExecutionPlannerV1_2.plan()` → `compute_crt_levels` →
   `UltronRiskGate`+`UltronRiskGateWrapper.evaluate()`, **threading evolving portfolio_state** (coverage
   contract above).
3. Forward-sim exits with `analytics.sl_tp_comparator.simulate_exit`, now with planner TTL/intent +
   Ultron sizing applied.
4. Aggregate position-sized PnL/PF; diff vs backtest spine headline.
**Trust gate (hard):** a no-Ultron/full-risk cell must reproduce the backtest expectancy bit-for-bit AND
selected==backtest trade count, else the harness is UNTRUSTED (exit non-zero).
**One-page conclusion** (the only narrative output): `Backtest PF · Live-path PF · Gap · Root-cause
attribution {execution_planner_ttl_intent, ultron_sizing}`.
**Effort** M. **Production risk** none.

## PACKET R1 · drift detected but not acted on (AFTER R2, only if trust gate passed)
- Config: add `"drift_action": {"hard":"block","hard_factor":0.0,"soft_factor":0.5}` under the
  `ultron_risk_gate` section of `v4_multi_2026_06.json` (NOT `params` — preserves the freshness
  fingerprint G1 enforces); re-hash via `scripts/maintenance/_compute_hash.py`.
- `live_engine_hook.py` before `:872`: soft → `risk_percent *= soft_factor`; hard+block → reject
  mirroring `MISSING_SL_TP` (`:828-834`), `risk_reason="DRIFT_HARD"`, size 0.0, skip wrapper (pre-gate,
  SR-1 intact); hard+scale → `hard_factor`.
- **Parity** (`backtest_v2.py` sizing `:791` using `_sev` from `:1858`): same factors → drift-handling
  symmetric across paths (the broader sizing-engine divergence is owned by R2, not R1).
- Tests: soft scales, hard+block rejects (gate NOT called), hard+scale scales, no-drift byte-identical
  (both paths). Rollback: revert 2 files + remove key + re-hash (inert without key).
- Self-review: key under `ultron_risk_gate` not `params`; G1 audit still exits 0; SR-1 intact; no magic
  numbers; `pytest` green; §6 LOG + §6.1 topic doc.
**Effort** S.

## PACKET G1 · enforce config_integrity (AFTER R1)
- `config_integrity.py`: add `ConfigIntegrityError` + `enforce(registry_dir, *, require_fresh=True)`
  (reuses the two existing guards; raises).
- Call at: `live_engine_hook` session init (primary), `promotion_manager` pre-promote, `backtest_v2`
  prod-registry path **behind a skip flag** (tuner must not re-check — perf). Toggle
  `governance.enforce_config_integrity` (default true).
- Pre-verified safe: v4 has `params_fingerprint` (`v4:193=c2568b6a…`) + a `PROMOTED` entry → passes today.
- Tests: governed+fresh passes; ungoverned/stale raises; toggle off skips; tuner skip-flag no-call.
  Rollback: toggle false (instant). Self-review: v4 audit exits 0 before/after; tuner unaffected.
**Effort** S.

## AFTER R2 — re-rank, don't pre-build
Recompute the **Funding Ledger** + **Profit Impact Ledger** using **measured** PF. Then, only if the
live edge survives: **S2** (throughput sweep `tier_2_threshold∈[0.44..0.60]`; ~35-trade ceiling →
diminishing), then **F3** (consume `context["fusion_weights"]` in `fusion_engine.compute()` behind a
flag; shadowed by F-001). If PF collapses: re-prioritize around the live execution layer; drop S2/F3.

## Execution order & stop conditions
1. **R2** → `results/live_path_replay/bnbusdt.json` + one-page conclusion. **STOP** if trust gate fails
   (fix harness fidelity before trusting any number).
2. **R1** (live + backtest parity) — only if R2 trust gate passed.
3. **G1**.
4. **Re-rank** with measured PF → decide S2/F3.
- Forbidden this cycle: Probability Surface, ReplayMemory, TradeNet revival, new feature/cluster
  intelligence, new architecture proposals.

## Validation
- `python scripts/research/live_path_replay.py --instrument BNBUSDT` → report; trust gate exits 0.
- `pytest tests/` green incl. new R1/G1 tests; no-drift + governed paths byte-identical.
- `python -m governance.config_integrity configs/production` exits 0 (v4 governed + fresh).
- §6 SESSION LOG per change; §6.1 topic docs (drift-handling, governance-enforcement); if measured PF
  materially differs from +20.59%, file/flip a finding in `docs/current-findings.md` per §6.2.

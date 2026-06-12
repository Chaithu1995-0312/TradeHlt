# Research Readiness Report — Hub (2026-06-12)

> **Phase 8.** Per-pipeline grades across {correctness, determinism, observability, testability,
> maintainability} + the prioritized remediation roadmap. This is the synthesis of deliverables
> 1–7 ([README](README.md)). Branch `patch`, `ACTIVE_VERSION = v2_multi_2026_04`.

## Bottom line
The repository's **core instrument — data→decision→backtest→metrics, and the trust layer that
certifies it — is sound and now better-gated** (metrics independently verified incl. Sharpe/Recovery;
replay proven byte-identical incl. telemetry, 2 instruments). The risks to *trustworthy research* are
**localized and fixable**, not structural: a config↔code split-brain, a few silently-inert config
knobs, a noisy (branch-mixed) test gate, and orphaned subsystems. **Research can begin on the spine
now**, provided the critical roadmap item (A-1) is resolved or explicitly fenced, and researchers
heed the documented caveats (hardcoded knobs, Sharpe semantics, live-path unverified).

## Scorecard (A best → D worst)

| Pipeline | Correctness | Determinism | Observability | Testability | Maintainability | Overall |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Data | B | A | B | C | B | **B** |
| Decision (spine) | A | A | B+ | B | B | **A−** |
| Analytics/Metrics | A | A | A | A | A | **A** |
| Portfolio | C | — | C | D | C | **C** (orphaned) |
| Validation | A | A | B | B | B | **A−** |
| Optimization | B | A | B | B | C | **B** |
| Governance | A | A | B | B | B | **A−** |
| Research | B+ | A | B | B | B | **B+** |

Rationale: Analytics earns A (independent oracle + golden/parity/invariant + determinism). Spine A−
(green + deterministic; observability docked for fusion-weight/sizing gaps). Data B (deterministic &
correct, but its integrity-gate config is absent → defaults, A-1). Portfolio C (built, orphaned,
untested-in-path). No pipeline is D except the orphaned Portfolio's testability.

## Prioritized remediation roadmap

| # | Item | Sev | research_blocking | fix_cost | Evidence |
|---|---|---|---|---|---|
| **R1** | ✅ **DONE 2026-06-12.** Added `dataset_integrity`/`uat`/`live_integration` to `v2_multi_2026_04.json` (verbatim from the deepdeektry lineage; **never touched params** → `config_hash` unchanged). 75 previously-red tests green; BNBUSDT ledger byte-identical pre/post (behavior-neutral); reachability 0 DEAD. Data-integrity gate is now governed by config. | critical | done | med | A-1 / F-016 |
| **R2** | Wire or delete the hardcoded knobs: `bitnet_main_threshold` (0.55), `feature_monitor.{hard,soft}_drift_z` (3.0/2.5), `news_blackout_minutes`. Tuning them is currently a silent no-op → false findings. | med | partial | low | A-2 / [config-reachability-report.md](config-reachability-report.md) |
| **R3** | Fence branch-scoped tests (TP3/v4, `_FREQ_BOOST`) with `skipif`/marker so `pytest` is a meaningful gate on `patch`. | med | no (gate hygiene) | low | A-5 |
| **R4** | Restore `TelemetryCollector.on_retest_replay` (3 reds; execution-planner replay explainability). | med | partial | low–med | A-7 |
| **R5** | Emit fusion intermediate weights + UltronRiskGate sizing rationale per-run for full decision explainability. | med | no | med | [telemetry-report.md](telemetry-report.md) |
| **R6** | Verify live path (F-010): backtest↔live parity for ExecutionPlanner + UltronRiskGate before any live-PnL research. | med | yes (for live) | high | F-010 |
| **R7** | Doc-drift: correct `testing.md` (51→116/10→15), add `src/research` to codebase-state-map, AGENTS.md control-plane. | low | no | low | A-6 |
| **R8** | Decide Portfolio/ExecutionLoop fate (F-013): wire or formally archive, so research doesn't assume it runs. | med | no | med | F-013 |

**Sequencing:** R1 first (unblocks data trust + clears most reds), then R3 (clean gate), R2+R4+R7
(cheap, high signal-to-noise), then R5/R6/R8 (deeper, schedule as research demands).

## Assumptions
- Tier-0 truth is `ACTIVE_VERSION` (§4.0); all statements branch-scoped to `patch`.
- "Trustworthy" = correct metrics + deterministic replay + auditable decisions + honest config wiring.
- Static reachability is best-effort (handles attribute + dynamic-getattr + string-literal access);
  HARDCODED_OVERRIDE rows are manually source-verified.

## Invariants (must hold for the lab to stay trustworthy)
1. Metrics oracle stays import-independent of the production metrics path.
2. Replay byte-identity (ledger + telemetry) holds across runs.
3. 4 engines mandatory; promotion only via APPROVE `ValidationReport` + hash.
4. LLM stays off the replay path (fail-open neutral).
5. Sweeps remain measure-only (no auto-promote).

## Edge cases & failure modes considered
- Empty/zero-trade ledgers (oracle handles → 0.0); no-loss PF inf-sentinel; <2-trade Sharpe → 0.
- Config field present but unread (inert) vs read-but-hardcoded (override) vs dynamic getattr.
- Branch-mismatched tests (red-by-design) vs real regressions.
- FX weekend gaps in dataset integrity (session-aware, resolved per memory).

## Risks to this audit's own conclusions
- **Determinism generalization:** proven on 2 instruments × 40–45k candles, not exhaustively.
- **Reachability false-negatives:** exotic dynamic access could still under-report consumption; the
  tool reports evidence per verdict to allow human override.
- **Coverage classification** is subpackage-granularity heuristic (no line-coverage run); risk grades
  are judgement, not coverage %.

## Self-review
- **What this proves:** spine correctness, metric integrity (8/8 metrics independently verified),
  full-artifact determinism, and an honest config-wiring map — backed by *executed* evidence.
- **What it does not:** it does not fix the findings (infrastructure-only; roadmap is the action
  output), nor validate the live path, nor exhaustively prove determinism.
- **Strongest claim:** a backtest on the active config reproduces its exact ledger *and* audit trail,
  and its headline metrics are mathematically certified.
- **Weakest claim:** "the suite is a clean trust gate" — not yet; it's noisy (A-5) until branch tests
  are fenced and A-1 resolved.

## Verdict
**The laboratory is trustworthy *for spine research today*, with a short, prioritized list to make it
trustworthy *wholesale*.** Begin research on the spine; gate live-PnL research behind R6; treat A-2
knobs as inert until R2.

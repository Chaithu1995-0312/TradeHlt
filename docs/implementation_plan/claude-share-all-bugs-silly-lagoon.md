# Bugs / Defects recorded in `docs/current-findings.md`

## Context
User asked to "share all bugs in findings.md". `docs/current-findings.md` holds 40+ findings, most of
which are **economic research nulls** (F-019…F-035, F-040, F-042, F-043 — conclusions, not defects).
This file extracts only the entries that document an actual **bug, defect, dead code, or unresolved
truth conflict** (Type = ARCHITECTURE / GOVERNANCE / RISK / OPERATIONAL). No code change is requested —
this is an inventory.

---

## 1. Live-risk defects — safety/risk gates that exist but don't fire
- **F-008 (RISK, Certain)** — Concept drift is *detected* but **not acted on**: on HARD drift
  `live_engine_hook.py:615` logs `"Trade signal unreliable"` and the trade **proceeds** (no block, no
  size-down, no gate).
- **F-013 (ARCH, Certain)** — Portfolio-level risk limits are **not applied on the live per-candle
  path**. `scan→allocate→ExecutionLoop`, `PortfolioAllocator` + `CorrelationEngine`, and zone-expectancy
  are BUILT but ORPHANED (`src/execution/loop.py:31`, `src/scanner/*`, `DecisionEngine.decide_batch`
  `:162` — zero callers); live runs the single-candle spine only.
- **F-006 (GOV, Certain)** — `config_integrity` is a real check but **ORPHANED** — its only caller is a
  one-off cutover script, so `validation_summary_is_fresh` / `active_version_is_governed` gate nothing
  at runtime (`src/governance/config_integrity.py`).
- **F-029 (OPER, Likely)** — `center=True` swing detection (`feature_pipeline.py:343`) is **LIVE-UNSAFE**
  (uses future bars). Benign for *backtest* trade generation (CRT path doesn't consume swing columns,
  ledger byte-identical under `TRUST_SWING_CAUSAL=1`), but the live-unsafe flag stands; global→causal
  conversion is gated on a future divergent config.

## 2. Fusion / engine correctness defects
- **F-038 (ARCH, Certain)** — The "RR" engine is a **GAUSSIAN DUPLICATE**. `rr_fusion` receives only
  2–3 of 38 features (`_empty_canonical_features()` starvation) → Mahalanobis confidence ≈1e-88 ≪ 0.3
  bypass threshold → passthrough returns the gaussian score on 100% of measured bars; base `RREngine`
  is discarded, gaussian effectively double-weighted (`rr/rr_fusion.py:35`, `engine_runner.py:694`).
  - Fix A (full-vector routing) shipped but **insufficient** — confidence still 5e-5 ≪ 0.3 (model is
    OOD/mis-calibrated even when fed real features).
  - Fix B (disable `rr_fusion.enabled`) shipped to `v2_multi_2026_04.json`, but **CORRECTED 2026-06-27:
    code-present, NOT deployed** — at HEAD, `ACTIVE_VERSION` resolves to `…- deepdeektry.json`
    (`enabled:true`); deploy requires committing the `ACTIVE_VERSION=v2_multi_2026_04` flip.
  - Residual sub-bugs (open): `NanoInferenceEngine.predict` **silent feature truncation**
    (`rr_pattern_miner.py:309-310`, needs schema-version guard); model retrain/recalibration open in the
    Funding Ledger.
- **F-005 (ARCH, Certain)** — TradeNet v2 is fully BUILT (`trade_net_v2.py`) but the fusion neural slot
  is a **permanent empty stub** (`fusion_engine.py:8`; EngineRunner never passes `neural_fn`).

## 3. Governance / version split-brain
- **F-016 (GOV, Certain)** — On `patch`, active config is `v2_multi_2026_04` (pre-TP3), not v4. The
  literal active string `"v2_multi_2026_04 - deepdeektry"` matches **no exact** `promotion_log` version,
  and the `- deepdeektry` suffix passed unchecked (because F-006's `active_version_is_governed` is
  orphaned). Supersedes F-007.
- **F-018 (GOV, Certain)** — config↔code split-brain: HEAD code expects `dataset_integrity` / `uat` /
  `live_integration` sections the active v2 config never carried, and several knobs
  (`bitnet_main_threshold`, `feature_monitor.{hard,soft}_drift_z`) were silently overridden by hardcoded
  literals → gates ran on code defaults. R1 + R2 remediated both symptoms (sections added, knobs wired,
  byte-identical ledgers); stays VALIDATED because the underlying F-016 branch split-brain persists.
- **F-041 (GOV, OPEN, Certain)** — **Unresolved TruthConflict.** ZoneGate scores through
  `models/zone_registry.json` (config `zone_registry_path`, HARD gate), but the version manifest
  `models/zone_gate_registry.json` `active:true` points to a *different* file
  (sha256 `aade29c4…` ≠ `e73e0893…`) → manifest ≠ scoring path (surfaced, not auto-reconciled).
  Observation: stored zone labels are ~98% SL-hit / 6-of-8 negative mean_RR (root-cause = Phase-5
  Go/No-Go gate, not yet asserted).
- **F-007 (GOV, SUPERSEDED)** — historical mislabel "active = v4_multi_2026_06"; both cited evidences
  false on `patch`. Kept for replay; corrected by F-016.

## 4. Data / artifact integrity defects
- **F-022 (GOV, Certain)** — `opportunities.jsonl` outcome/rr are only **36.8% self-consistent**
  (91,126 rows logged `SL_HIT` whose own MAE never touches the stop). It's a **detection stream, not a
  trade ledger**; realized truth must be derived via the governing intrabar exit. Mechanism: scanner
  `_simulate` (`opportunity_scanner.py:53`) labels under a 0.5R *trailing* stop, mismatching the
  governing fixed-stop. Frequency illusion: 139,942 detections ≠ 13 governed spine trades.
- **F-039 (ARCH, Certain)** — The L3 `validate_dataset` pre-flight has only **two call sites, both in
  `backtest_v2`**. Every other `CandleLoader.stream()` consumer (all of `src/research/`, analytics,
  governance, replay, config_validator + the entire `scripts/` fleet) relies solely on the inline L1/L2
  backstop → **single point of failure** (making `stream()` permissive would remove the sole net).

## 5. Dead / orphaned inventory (built-not-wired — dormant, not live bugs)
- **F-012 (ARCH, Certain)** — ReplayMemory / CognitiveBus / Cluster / HMF are sidecar-only (zero spine
  consumption; `cognitive_bus` gated off by absent `cognitive_layer`, `engine_runner.py:436`).
- **F-004 (ARCH, Certain)** — BitNet's **adaptive threshold is dormant** (hardcoded 0.55;
  `get_bitnet_threshold(regime)` never called). The hard-reject gate itself IS live (not a bug — a
  reversal of the older "BitNet dead" claim).

---

## Notes on status
- **Actively OPEN:** F-010 (live PnL unverified — a caveat, not a defect), **F-041** (TruthConflict).
- **Fix-in-flight but not deployed:** F-038 (needs `ACTIVE_VERSION` commit to deploy Fix B).
- **Remediated-but-retained:** F-018 (R1/R2 done, root F-016 persists).
- **Not bugs (excluded):** all ECONOMIC findings (F-001/F-002/F-003/F-009/F-011/F-014/F-015/F-017/
  F-019…F-028/F-030…F-036/F-040/F-042/F-043) — these are research nulls/conclusions.

## Verification
Read-only inventory. To re-derive: `grep "^- Type:" docs/current-findings.md` and filter to
ARCHITECTURE / GOVERNANCE / RISK / OPERATIONAL; cross-check each against the CLAUDE.md §6.2 Repository
Truths Index table. No code executes.

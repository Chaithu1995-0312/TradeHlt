# 1 · Architectural Evolution Report (Phase A)

> Point-in-time audit, 2026-06-02. Where original intent diverged from reality. Sourced from the plan
> corpus + config lineage + `assistant_project.md` SESSION LOG.

## Two parallel tracks (do not conflate)

The system evolved on **two tracks that must not be credited to each other**:

- **Governance / infrastructure track** (Gov-M1-2 + **Trd-M0–M5**) — makes the engine clean, injectable,
  governable. **Trd-M3–M5 add ZERO decision capability and ZERO ROI by design** (their acceptance gate is a
  *byte-identical trade ledger*; `trd-m0-m5-tender-bentley.md §M3-M5 verification`).
- **Per-coin ROI / throughput track** (Phase 0 → 6c → v3) — the empirical work that actually moved measured
  returns, run **on individual coins** (BNB, SOL, ETH, BTC).

## Timeline

```
V1  v1_multi_2026_03  (2026-03-24)
      Goal: governed baseline — 4-engine spine (CRT/Gaussian/ZoneGate/RR), heuristic Gaussian,
            ConfigValidator + PromotionManager + SHA-256 + promotion_log.
        ↓
V2  v2_multi_2026_04  (governed; last real PROMOTED 2026-05-06)
      Goal: ML Gaussian (gaussian_impl="ml"), regime fusion weights, RR fusion layer, BitNet zone gate,
            strategy orchestrator wiring. Governed promotions through 05-06.
        ↓
   v2_multi_2026_04 - deepdeektry  (file 2026-05-30; ACTIVE)   ← DIVERGENCE POINT
      Goal (implied): permissive params (0.8/0.3/0.6) to raise acceptance.
      Reality: hand-edited, NEVER promoted (0 promotion_log entries), STALE validation_summary,
               space in the version name. Governance BYPASS. ← intent diverged from reality HERE.
        ↓
V3  v3_multi_2026_06  (2026-06-02; VALIDATED_READY, NOT promoted)
      Goal: per-instrument allowed_sessions_overrides (BNB+SOL) = the measured throughput fix;
            also enables cognitive_layer + strategy_orchestrator on a v1-superset base.
      Reality: validated APPROVE, staged, parked on operator cutover. Built ≠ live.
        ↓
Current
      ACTIVE_VERSION = "v2_multi_2026_04 - deepdeektry" (ungoverned) is what trades today.
      v3 (the governed, tested, per-coin ROI version) sits unpromoted.
```

## Per-stage table

| Stage | Goal | Implemented | Abandoned | Drifted |
|------|------|-------------|-----------|---------|
| **V1** | Governed 4-engine baseline + promotion spine | CRT/Gaussian/ZoneGate/RR; ConfigValidator; PromotionManager; SHA-256; promotion_log | — | Gaussian stayed heuristic in v1 (ML only later) |
| **V2 (governed)** | ML scorers + regime fusion + BitNet zone | ML Gaussian; regime_fusion_weights; RRFusionLayer; BitNet zone gate; orchestrator wiring | TradeNet neural slot left **stubbed** (`fusion_engine.py:8`) | regime weights present but **compute() uses static weights**; orchestrator wiring **inert** |
| **deepdeektry (ACTIVE)** | Permissive params → more acceptance | params edited live | **Promotion abandoned** (never ran the gate) | **Governance drift**: stale validation_summary, no PROMOTED entry, name has a space |
| **V3 (staged)** | Per-coin session overrides = measured ROI | BNB+SOL overrides; validator made override-aware; config_integrity guards | ETH/BTC overrides (sweep showed degradation) | enabling cognitive_layer/orchestrator = **byte-identical inert** (enablement≠consumption) |
| **Trd-M0–M5** | Clean/injectable/governable infra | M0-M2 complete; M3-M5 infra | — | **ROI-neutral by design** — must not be credited with profitability |

## Where intent diverged from reality (headline)

The divergence is **not** at the intelligence layer — the engines were built as intended. It is at the
**governance boundary**: the version that actually trades (`deepdeektry`) **never passed the promotion gate
the project's own doctrine mandates**, while the version that *did* pass and carries the measured per-coin
ROI (`v3`) sits **parked**. The system's governance machinery works (it even has a guard that flags the
bypass) — it is simply being **bypassed in production**.

Secondary divergence: a recurring **enablement ≠ consumption** gap — config flags turn features "on"
(orchestrator, cognitive layer) that the decision path does not actually consume (byte-identical output).

→ See [governance-audit.md](governance-audit.md) for C1 detail and [intent-to-code-gap-report.md](intent-to-code-gap-report.md) for the per-plan gaps.

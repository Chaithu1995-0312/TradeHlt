# 3 · Profitability Dependency Graph (Phase C)

> Point-in-time audit, 2026-06-02. What actually affects PnL, and the classification of every component
> into Revenue-Critical / Governance-Critical / Research-Only / Dead.

## The DAG (what shapes a trade)

```
                       Market Data (M15 OHLCV CSV)
                                │
                          CandleLoader
                                │
                    ┌───────────┴───────────┐
                    │   EngineRunner.run()   │
                    │  ┌──────────────────┐  │
                    │  │ Adapter gate     │  │  hard reject if score≤0
                    │  ├──────────────────┤  │
                    │  │ CRT  Gaussian    │  │  4 mandatory engines (EXPECTED_ENGINES)
                    │  │ ZoneGate  RR     │  │  → revenue-critical scores
                    │  ├──────────────────┤  │
                    │  │ completeness gate│  │  hard reject if any engine missing
                    │  ├──────────────────┤  │
                    │  │ FusionEngine     │  │  static weights 0.4/0.2/0.2/0.2
                    │  ├──────────────────┤  │
                    │  │ RegimeGovernor   │  │  LEGACY path (ultron_gate_enabled=false): no quota
                    │  ├──────────────────┤  │
                    │  │ DecisionEngine   │  │  ← ONLY emitter of execute/reject
                    │  └──────────────────┘  │
                    └───────────┬───────────┘
                                │ "execute"
        ┌───────────────────────┴───────────────────────┐
        │  BACKTEST: CRT-internal SL/TP → journal trade  │   ← where ROI is MEASURED
        └────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        │  LIVE-ONLY (not in backtest):                  │
        │   ExecutionPlannerV1_2 (intent+entry+TTL)      │   ← shapes live entry
        │            ↓                                    │
        │   UltronRiskGate (TTL/RR/limits/kill-switch)   │   ← can BLOCK the live trade
        │            ↓                                    │
        │         Trade                                   │
        └─────────────────────────────────────────────────┘

  SIDECAR (off the path, no PnL impact): CognitiveBus→ReplayMemory, MarketStateCluster,
  zone-expectancy mean_rr, TradeNet stub, drift-detector(logs only), Scanner, ForwardTester.
```

**Critical structural fact:** the **session filter inside CRT** (RETEST→EXECUTION) sits *before* fusion
and discards 64/135 valid retests — it is the single largest throughput valve, and it is **policy (config),
not capability**.

## Classification

### Revenue-Critical (direct PnL — changing it changes returns)
- **CRT engine** (state machine + SL/TP sizing), **Gaussian (ML)**, **ZoneGate (BitNet)**, **RR engine** —
  the four fused scores.
- **FusionEngine** (aggregation), **DecisionEngine** (execute/reject).
- **CRT session filter** (`allowed_sessions`) — *the* throughput determinant; the per-coin ROI lever.
- **ExecutionPlannerV1_2** (live-only) — sets live entry/TTL.

### Governance-Critical (cannot create PnL; can BLOCK trades)
- **UltronRiskGate** (live-only) — TTL/RR floor/daily-limit/kill-switch/exposure.
- **RegimeGovernor** — *currently inert* (legacy path, no quota) but is a throttle when enabled.
- **completeness gate**, **ConfigValidator**, **PromotionManager**, **config_integrity guards**,
  **ShadowPromotionGate**.

### Research-Only (produces information; no decision impact today)
- **ReplayMemory / CognitiveBus / MarketStateCluster** (sidecar telemetry).
- **Zone EXPECTANCY mean_rr** (stored, ignored).
- **Concept-drift detector** (logs "unreliable", does not gate).
- **PortfolioValidation / MetaGovernorExecutor** (advisory / audit-log).
- **OOS feature-region studies** (advisory weight 0.0).

### Dead / orphaned (not wired into any path)
- **Scanner / SignalPool**, **ForwardTester (×2)**, **TradeNet v2 / TradeNetMetaEngine**,
  **Probability Surface** (never built), **DecisionEngine FIX-4 force-accept** (only in the orphaned
  `decide_batch` path).

## Implication for profitability

PnL is governed by a **short revenue chain** (CRT→Gaussian→ZoneGate→RR→Fusion→Decision, + the CRT session
policy) and **gated** by governance (Ultron live-only, completeness, promotion). Everything in the
Research-Only and Dead columns is, by definition, **not currently a profitability lever** — so "more
intelligence" there cannot move returns until it is moved into the Revenue or Governance columns
(i.e. *consumed*). The biggest revenue lever today is a **Governance-Critical action** (promote the governed
per-coin session policy), not a Revenue-Critical model change.

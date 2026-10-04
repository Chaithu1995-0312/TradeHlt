# Implementation Plan — OSS Integration Benchmark Lab

| Field | Value |
|---|---|
| Status | ACTIVE |
| Authority | RESEARCH_LAB_ONLY |
| Architecture | [`docs/governance/OSS_INTEGRATION_ARCHITECTURE.md`](../governance/OSS_INTEGRATION_ARCHITECTURE.md) |
| Lab | [`oss_lab/`](../../oss_lab/README.md) |

## Goal

Ship a **safe, isolated** lab so Tradelatest can compare itself to mature OSS engines on a
shared corpus and common evidence contract — without granting OSS production authority.

## Phase checklist

### Phase 0 — Discovery ✅

- [x] Trace spine / research / governance / Semantic OS
- [x] Inventory reuse candidates
- [x] Confirm physical home: top-level `oss_lab/` (like `mt5_analytics/`)

### Phase 1 — Registry + capability contract ✅

- [x] `oss_lab/registry/schema.json`
- [x] Seed JSONL (Tradelatest, Qlib, Nautilus, FinRL-X)
- [x] Fail-closed loader + T4 ban for external OSS

### Phase 2 — Canonical benchmark schema ✅

- [x] BenchmarkTradeRecord + Presence provenance
- [x] DatasetManifest (Phase-1 XAUUSD pin)
- [x] RunManifest, MetricCell, FillModelDeclaration

### Phase 3 — Tradelatest baseline adapter ✅ (real-artifact normalization)

- [x] Normalize native trade dicts → BenchmarkTradeRecord
- [x] Consume the real `backtest_v2` trades-CSV vocabulary (`TradeJournal.to_csv_rows`),
      verified against a fresh Phase-1-pinned run — 2026-08-12:
  - `net_pnl` ← `capital_after − capital_before` (**account currency**). R-valued
    `pnl_rr_net` / `rr_achieved` are refused: mapping R into an unsuffixed money field
    silently corrupts `expectancy_r` once `initial_risk` is present.
  - `initial_risk` ← derived `|entry_fill − sl| × position_size`; precision bounded by
    the producer's CSV rounding (`position_size` 2dp), never "exact".
  - `tp` ← `NOT_APPLICABLE`: the source carries a sequential TP **ladder** (`tp1`→`tp2`;
    a TP2 exit also counts a TP1 hit, `backtest_v2.py:1335`) that a single scalar cannot
    represent. Neither leg is picked.
  - `gross_pnl` / `spread_cost` / `slippage_cost` derived in money from the pip columns.
  - CRT testimony (`risk_score`, `state_path`, `htf_id`, feature columns) → `adapter_meta`
    sidecar only; never a metric input.
- [ ] Runner that shells to `backtest_v2` (still `runners/backtest_baseline.py`, PLANNED)
- [ ] Gate mode explicit (F-037) in run manifests

### Phase 4 — Independent metrics layer ✅ (scaffold)

- [x] CanonicalMetrics (PF, expectancy, DD, MFE/MAE, honest Sharpe UNKNOWN)
- [ ] Equity-curve series export for annualization-ready Sharpe
- [ ] Performance timing (min/median/p95/max, multi-run)

### Phase 5 — Qlib (not started)

- [ ] License + security + maintenance assessment
- [ ] Version pin; optional isolated install path
- [ ] Dataset adapter (no silent download)
- [ ] Normalize → BenchmarkTradeRecord
- [ ] Lifecycle → APPROVED_FOR_LAB only after gate

### Phase 6 — Nautilus (not started)

- [ ] **LGPL-3.0 legal review**
- [ ] Version pin; isolated adapter only
- [ ] Fill-model declaration + sensitivity runs
- [ ] Never wire into Decision/Ultron

### Phase 7 — FinRL-X (not started)

- [ ] License verification (currently UNKNOWN)
- [ ] Independent reproduction protocol
- [ ] Observed vs annualized return separation

### Phase 8 — Certifications (partial)

- [x] Lookahead compare_snapshots helper
- [ ] Full CRT/feature future-mutation on Phase-1 corpus
- [ ] Cost NO_COST vs WITH_COST matrix
- [ ] Fill model A/B/C sensitivity

### Phase 9 — Semantic OS

- [x] Mapping seed JSON
- [ ] Author CN/BD/CT into live YAML under strict validator
- [ ] Seed projection + tests green

### Phase 10 — Governance

- [x] Lifecycle + risk + UNKNOWN registers
- [ ] Optional change_class `OSS_LAB_CHANGE` if needed later
- [ ] No auto-finding registration from lab metrics

## Next lowest-risk step

**Priority after OSS monitor scan (2026-08-12):**

1. **Codebase-Memory** controlled local benchmark vs `graph.dot`/pyan (repo-intel H2H scenario) — no production install; security audit + pin first.
2. **LEAN** registered for execution three-way with Nautilus (still DISCOVERED; no install yet).
3. Wire `TradelatestBaselineAdapter` to a real `backtest_v2` trades artifact under the Phase-1 pin.
4. Do **not** install Qlib/Nautilus/FinRL/LEAN/Codebase-Memory/Infigraph until APPROVED_FOR_LAB.
5. VectorBT remains DEFERRED (Commons Clause legal review).

## Non-goals

- Replacing CRT / ontology / Fusion / Decision / Ultron
- Promoting OSS metrics into production findings
- Deep live-rail integration (blocked F-073)

# Plan: CRTStateResolver vs BacktestRunner — Consolidated OHLCV→States Report

## Context

User wants a **consolidated comparison report** showing:
1. How **CRTStateResolver** transforms OHLCV → features → CRT states
2. How **BacktestRunner** performs the same transformation
3. The **latest MT5/XAUUSD run report** (probably in `results/` or `reports/`)

This is exploratory/documentation work. No code changes expected — the goal is **visibility into the two parallel paths**.

## Phase 1: Exploration (in progress)
- [ ] Locate CRTStateResolver (class definition, entry point, API)
- [ ] Locate BacktestRunner (class definition, entry point, feature injection)
- [ ] Map feature pipeline: OHLCV → FeaturePipeline.run() → 38-dim vector
- [ ] Identify state emission: where CRTState objects are created/emitted in each path
- [ ] Find latest MT5/XAUUSD run artifacts (results dir, report files, timestamps)

## Phase 2: Report Structure (pending)
Will create a consolidated markdown report covering:
- **Data Flow Diagram** (text/ASCII or reference to `.dot` graph)
- **CRTStateResolver path** (signature, input, output, state transitions)
- **BacktestRunner path** (signature, input, output, state transitions)
- **Feature pipeline bridge** (where they diverge/converge)
- **State lifecycle** (how states are updated per candle)
- **Latest MT5/XAUUSD metrics** (attached from run report)

## Phase 3: Output Delivery (pending)
- Consolidated markdown report
- Link to latest run artifacts
- Visual comparison table (if relevant)

## Critical Files (to be confirmed by agent)
- TBD: CRTStateResolver location
- TBD: BacktestRunner location
- TBD: FeaturePipeline location
- TBD: Latest run report path

---

**Status:** Awaiting Explore agent completion to populate critical files.

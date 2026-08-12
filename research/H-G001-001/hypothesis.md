# H-G001-001 — Liquidity Sweep Veto Qualification on XAUUSD

**Program:** G001 economic research (not ontology construction)  
**Status:** MEASURE-ONLY · NON-PROMOTABLE until decision recorded  
**Date opened:** 2026-07-26

## Question (only one)

> Does a **liquidity-sweep veto** on the production CRT spine improve trading performance
> on the canonical XAUUSD corpus under the M4 truth standard?

## Hypothesis

**H1:** Filtering out spine entries that occur on bars where the pipeline’s causal
`liquidity_sweep != 0` (FM-058) improves net expectancy / G001 criteria vs the unfiltered
production spine.

**H0:** The veto is neutral or harmful (Δexpectancy ≤ 0 and/or no G001 improvement).

## Fixed components

| Component | Value |
|---|---|
| Instrument | XAUUSD (MT5 frozen Phase-1 candidate corpus) |
| Timeframe | M15 |
| Dataset | `guard_xauusd_csv_path` → `data/mt5/XAUUSD_M15.csv` |
| Baseline | Production CRT spine entries (`v2_multi_2026_04` via `ProductionSpineSource`) |
| Exit | M4: `intrabar_fixed` + 12 bps round-trip |
| Config | Production spine version + `research_config_spine_xauusd.json` knobs |
| Sizing | Unchanged |

## Treatment (exactly one consumer change)

```
Baseline:   production spine entries as committed at TRADE_OPENED
Treatment:  same entries MINUS those with liquidity_sweep ≠ 0 on the entry bar
```

- **Veto definition:** discard entry if `|liquidity_sweep| ≥ 1` on the research-index bar
  (aligned via `FeaturePipeline.compute_structure_liquidity`, row-preserving — no finalize drop).
- **Not changed:** SL/TP geometry, session filter, fusion, BitNet, Ultron, zone, RR, weights.
- **Not changed:** ontology, FM math, registries.

## Metrics

Primary: Δ Goal Report (G001), expectancy (net R), profit factor, win rate, max drawdown (R), trade count.

## Decision rule

| Outcome | Action |
|---|---|
| Positive, reproducible ΔG001 / economic usefulness | Remain in qualification; ladder may advance **only** with measured positive Δ |
| Neutral or negative | **REJECT** hypothesis; consumer stays information-only |
| Any result | **No ontology / FM / production config edits** |

## Authority note

Semantic correctness of `liquidity_sweep` (FC1-A oracle / parity) is **already validated**.
This experiment tests **economic contribution only**.

## Corpus trust

Corpus status is `FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION` (UNTRUSTED_RAW for promotion).
Even a PROMOTE-class M4 verdict remains **research authority only** until corpus phase gates clear.

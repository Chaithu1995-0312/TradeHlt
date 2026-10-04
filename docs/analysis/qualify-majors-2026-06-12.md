# Qualify-Majors — cross-instrument M4 qualification of the existing hypothesis pool

> **Point-in-time analysis (history, not living truth).** Date: 2026-06-12 · Branch: `patch` ·
> ACTIVE_VERSION: `v2_multi_2026_04` · Truth standard: `intrabar_fixed` exits + flat 12 bps +
> SL-before-TP tie-break (truth_standard v2.0). Artifact:
> `results/research/qualification/qualify_majors.json`. Driver: `scripts/research/qualify_majors.py`.
> Conclusion promoted to the living record as **F-019** in [`current-findings.md`](../current-findings.md).

## Why this run

Trust-repair (R1–R4) is complete; the bottleneck shifted **trust → alpha**. Before inventing any
new hypothesis, *use the built lab*: run the **existing** pool (`spine`, `expansion_breakout`,
`mean_reversion`) through the M4 7-gate `QualificationGate` across the **crypto majors**
(BNB/ETH/BTC/SOL), **per-instrument first, then pooled**, vs falsification controls. The cheapest,
highest-ROI question: *do we already possess a qualifiable edge somewhere and simply never measured
it broadly?*

Two config families were required (they cannot share one `qualify` invocation): the **toy family**
(`research_config_majors.json`, `apply_signal_defaults=true`) and the **spine family**
(`research_config_spine_majors.json`, `apply_signal_defaults=false`, `prod_version=v2_multi_2026_04`).
Winning control is recomputed under each family's config (fair gate-4/gate-6 baseline). All gate math
is reused verbatim from `src/research/qualification.py` — the driver adds no statistics.

## Verdict table

`E` = net expectancy (R), net of 12 bps. `Δctrl` = `baseline_delta` vs the winning control
(`random_uniform` in every scope). `p` = one-sided permutation p vs that control.

| Hypothesis | Scope | n | PF | E(net) | Δctrl | p | Verdict | Nearest gate |
|---|---|---:|---:|---:|---:|---:|---|---|
| expansion_breakout | BNBUSDT | 12666 | 0.540 | −0.4392 | −0.0245 | 0.958 | **REJECT** | gate2 E<0 |
| expansion_breakout | ETHUSDT | 10763 | 0.633 | −0.3226 | +0.0011 | 0.469 | **REJECT** | gate2 E<0 |
| expansion_breakout | BTCUSDT | 12295 | 0.433 | −0.5953 | −0.0757 | 1.000 | **REJECT** | gate2 E<0 |
| expansion_breakout | SOLUSDT | 11882 | 0.698 | −0.2507 | +0.0004 | 0.491 | **REJECT** | gate2 E<0 |
| expansion_breakout | **POOLED** | 47606 | 0.564 | −0.4061 | −0.0288 | 0.999 | **REJECT** | gate2 E<0 |
| mean_reversion | BNBUSDT | 22368 | 0.563 | −0.4086 | +0.0061 | 0.279 | **REJECT** | gate2 E<0 |
| mean_reversion | ETHUSDT | 20348 | 0.637 | −0.3127 | +0.0110 | 0.164 | **REJECT** | gate2 E<0 |
| mean_reversion | BTCUSDT | 21740 | 0.505 | −0.4865 | +0.0331 | 0.002 | **REJECT** | gate2 E<0 |
| mean_reversion | SOLUSDT | 21213 | 0.703 | −0.2435 | +0.0076 | 0.238 | **REJECT** | gate2 E<0 |
| mean_reversion | **POOLED** | 85669 | 0.595 | −0.3647 | +0.0126 | 0.014 | **REJECT** | gate2 E<0 |
| spine | BNBUSDT | 13 | 0.324 | −0.8326 | −0.4179 | 0.868 | **INSUFFICIENT** | gate1 n<30 |
| spine | ETHUSDT | 5 | 0.666 | −0.3267 | −0.0030 | 0.535 | **INSUFFICIENT** | gate1 n<30 |
| spine | BTCUSDT | 5 | 0.409 | −0.5338 | −0.0142 | 0.511 | **INSUFFICIENT** | gate1 n<30 |
| spine | SOLUSDT | 7 | **2.455** | **+0.4501** | **+0.7012** | 0.128 | **INSUFFICIENT** | gate1 n<30 |
| spine | **POOLED** | 30 | 0.566 | −0.3992 | −0.0219 | 0.537 | **REJECT** | gate2 E<0 |

**PROMOTE: none.** Across every instrument and pooled, no existing hypothesis clears the gate.

## What this means

1. **The cheapest alpha question is answered: NO.** Nothing in the existing pool qualifies on any
   major or pooled, under honest exits + cost. This is a *successful* experiment (a clean
   falsification), not a failure — it forecloses a whole branch of "we may already have edge."

2. **The toy entry detectors are statistically indistinguishable from random.** `Δctrl` vs
   `random_uniform` is ≈0 everywhere (−0.076 … +0.033); E<0 on all 4 majors for both detectors. The
   detection geometry adds essentially **no directional information** over a coin-flip entry. This
   **extends F-001/F-002 and the process-characterizer's "direction is a coin-flip given vol band"
   from BNBUSDT to all four crypto majors** — the entry-edge null is cross-instrument, not a
   BNB-specific artifact. (Note: a couple of mean_reversion cells show low permutation p, e.g. BTC
   p=0.002 — but the realized E is still negative, so "significantly different from random" here
   means *significantly worse-or-equal in a losing way*, not an edge; gate-2 correctly rejects.)

3. **The spine is throughput-starved, not evaluable per-instrument.** 5–13 committed entries per
   instrument over ~2 years of M15 ⇒ all four per-instrument cells are INSUFFICIENT (n<30). Pooling
   the majors barely reaches n=30, and there E=−0.399 (REJECT, gate-2). The spine's defining
   selectivity is exactly what denies it statistical power. **Ties F-003/F-015** (throughput is the
   binding constraint; the cheap throughput levers are spent on BNB/SOL).

4. **One positive cell — flagged, explicitly NOT an edge claim.** `spine/SOLUSDT`: n=7, E=+0.45,
   PF=2.45, WR=71%, beats control by +0.70 (p=0.13). It is the *single* positive cell in the whole
   table, but n=7 makes it unusable (INSUFFICIENT). It is a **lead** ("the spine's selection may
   concentrate something on SOL"), not a result. Relatedly, the spine's *own* backtest reported BTC
   +0.62R and a positive SOL; under this research lens (single 2R TP, intrabar, 12 bps) only SOL
   stays positive — the gap between the spine's scale-out tp1/tp2 ledger and the single-TP research
   lens is **F-010 territory** (live ExecutionPlanner/UltronRiskGate PnL still unverified).

## Roadmap implication — the experiment selects the next phase

- **Phase C (invent new entry hypotheses) is NOT immediately justified.** Both existing
  geometry-based entry detectors are coin-flips on *all* majors; naively generating more of the same
  shape would most likely reproduce ≈random.
- **Highest-value next step = Phase B (process characterization).** Find *where/whether* direction
  becomes **conditionally** predictable (regime/session partitioning that measurably lowers
  conditional entropy) before committing to any new entry family. If no conditional pocket exists,
  the honest conclusion is *no spine-style entry edge on crypto-major M15* — and the search moves
  off entries entirely (toward the spine's selection mechanism at higher throughput, or off-spine).
- **Secondary thread (gated):** does the spine's *selection* concentrate edge when pooled at higher
  throughput (F-015 cross-instrument pooling)? Blocked by the known throughput constraint; the SOL
  n=7 cell is the only thing pointing at it.

## Reproduce

```
python scripts/research/qualify_majors.py --out results/research/qualification
```

Deterministic: the JSON body carries no wall-clock; a second run is byte-identical (the M3/M4
determinism invariant, re-verified for this new orchestration). Config provenance:
toy `config_sha256=04f4ba1a…`, spine `config_sha256=c6a72dbe…`, `prod_version=v2_multi_2026_04`.

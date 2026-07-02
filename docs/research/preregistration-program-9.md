# Pre-Registration — Program 9 (M5-base Multi-TF Expansion Forecasting, Non-Directional Ontology)

> **Status:** PRE-REGISTERED (written before any run). Authority: research/docs only (§6.5
> Authority Ladder). This document FREEZES the hypotheses, the targets, the thresholds, the
> execution construction, and the closure rule **before** results exist, so a null cannot be
> quietly re-spun into a finding and a hit cannot be threshold-shopped. Enforced socially by the
> Epistemic Integrity ritual (Program E-001,
> [`docs/governance/EPISTEMIC_INTEGRITY.md`](../governance/EPISTEMIC_INTEGRITY.md)).

## Context & scope

Program 4 (candle-state transition frontier, M15 base) is KILLED per F-040: the expansion
forecast is REAL (Stage-1 PASS — universal, persistent, p≈0.0005) but NOT consumable by a spot
**directional** consumer (Stage-2 FAIL) — the binding constraint is the execution model, not
predictability. Its Funding-Ledger reopen clause permits reopening ONLY via **new data**
(the on-disk M5 corpus), a **new market domain**, or a **new non-directional ontology** — never
parameter archaeology. Program 9 exercises **two** of the three reopen keys simultaneously:

1. **New data:** the strict-verified M5 corpus (Binance crypto 2-yr ladder, zero missing bars;
   MT5 FX ~270-day ladder) that did not exist at F-040's registration ("no M5 on disk").
2. **New ontology:** a NON-directional execution construction — a both-sided stop-entry
   straddle proxy (OCO at the compression box edges) whose payoff is long-volatility, the
   structure F-040 explicitly identified spot long/short as unable to express.

**Two-stage gate.** Stage 1 = information (Authority Level 1) with an **incremental-information
requirement** absent from Program 4: the M5-base conjunction must carry information **beyond**
the causally-available M15-base conjunction at the same instant (the F-043 lesson — statistically
real but redundant information earns nothing). Stage 2 = economic (`compression_box_straddle`
through the unchanged M4 QualificationGate, Authority Level 2). Stage 2 runs ONLY if Stage 1
clears every threshold below.

## Universe (frozen)

| Group | Instruments | Data | Coverage |
|---|---|---|---|
| crypto (primary, powered claim) | BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT | `data/binance/{SYM}_M5.csv` | 2024-05-22 → 2026-05-21, zero missing bars |
| fx (robustness / cross-market) | EURUSD, GBPUSD, AUDUSD, USDJPY, EURCAD, XAUUSD | `data/mt5/{SYM}_M5.csv` | 2025-10-06 → 2026-07-02 (~270d broker retention) |

FX caveats registered up-front: the 12 bps cost standard is 1.8–2.5× the median FX M15 bar
(F-035) and larger still relative to M5 bars — FX Stage-2 magnitudes are cost-dominated by
construction; XAUUSD carries reviewed holiday accept-list gaps. FX therefore informs the
cross-market verdict, not the primary claim.

## Hypotheses (all NON-DIRECTIONAL; conditioning cell = the M5∧M15∧H1∧H4 conjunction key)

Targets are the **unchanged** Program-4 kernels (`src/research/candle_state/transition_target.py`).

| ID | Conditioning (cell) | Forward target | H0 (null) |
|---|---|---|---|
| **9a** | conjunction key at t (M5 grid) | forward **vol expansion**: mean(ATR over t+1..t+k)/ATR_t > θ | the M5-base conjunction carries no information about forward expansion (IG ≤ permutation null) |
| **9b** | conjunction key at t (M5 grid) | forward **range expansion**: mean(range over t+1..t+k)/range_t > θ | same as 9a for bar range |
| **9c** | conjunction key at t (compression bars) | **regime transition**: COMPRESSION→EXPANSION within k on the M5 vol axis | the conjunction carries no compression→expansion timing info |

Each hypothesis additionally carries the **incremental null** H0ᴮ: conditioning on the fine key
K5 adds no information beyond the coarse key K15 (IG(target|K5) ≤ the within-K15-cell
permutation null).

**Key construction (frozen).** Per M5 bar t: **K5** = `"M5=<tok>|M15=<tok>|H1=<tok>|H4=<tok>"`
where M15/H1/H4 tokens come from the **last fully-closed** bucket of the M5→{M15,H1,H4} resample
(structural no-lookahead, same causal semantics as Program 4's `MultiTFConjunctionBuilder`);
**K15** = K5 with the `M5=` component stripped — the M15-base information causally available at
the same M5 instant.

## FROZEN thresholds and horizon rescale (no post-hoc changes)

Wall-clock-matched to Program 4's M15 values:

| Parameter | Program 4 (M15) | Program 9 (M5) | Wall-clock |
|---|---|---|---|
| Horizons swept | {1, 2, 4, 8} | **{3, 6, 12, 24}** | 15m / 30m / 1h / 2h |
| Decision horizon k | 4 | **12** | 1 hour |
| Half-life minimum | ≥ 4 bars | **≥ 12 bars** | ≥ 1 hour |
| Stage-2 max_forward | 40 | **120** | 10 hours |
| Straddle entry TTL | — | **12 bars** | 1 hour |

Unchanged: θ = 1.5 · ATR period 14 · permutation α = 0.05 · 2000 seeded permutations ·
MI retention ≥ 0.50 · n ≥ 30 · 12 bps round-trip · `intrabar_fixed` exit model · SL 1.0 / TP 2.0
ATR · M4 QualificationGate + Benjamini-Hochberg + controls, verbatim.

### Stage-1 PASS rule (both gates required)

| Gate | Threshold |
|---|---|
| **A — raw information** | permutation p ≤ 0.05 ∧ half-life ≥ 12 M5 bars ∧ MI retention ≥ 0.50 ∧ n ≥ 30 |
| **B — incremental beyond M15** | within-K15-cell permutation p ≤ 0.05 (shuffle target within each K15 cell, recompute IG(target\|K5); destroys only the M5 refinement) |

**Gate A pass + Gate B fail ⇒ verdict `M15_REDUNDANT` = Stage-1 FAIL** (the F-043
`REGIME_REDUNDANT` analogue — real but already-known information). Cross-market verdict logic
unchanged from Program 4, applied to the A∧B conjunction: crypto PASS + FX PASS ⇒ UNIVERSAL ·
crypto PASS + FX FAIL ⇒ DOMAIN_SPECIFIC · else ⇒ REJECTED. Only cross-market ≠ REJECTED
proceeds to Stage 2.

Changing any threshold requires a NEW pre-registration, not an edit to this file.

## Frozen execution decisions (D1–D7)

| ID | Decision |
|---|---|
| **D1** | **Reject-bar tie rule:** if BOTH box edges are touched within one M5 bar while the straddle is pending, the straddle is CANCELLED (no fill). The intrabar touch order is unknowable; inventing one is lookahead. |
| **D2** | **No fill-bar TP:** on the bar where a stop entry fills, the stop-loss is checked by full-range touch but TP is NEVER credited — the fill-touch vs TP-touch order is unknowable (consistent with the kernel's conservative SL-before-TP convention). |
| **D3** | **Unfilled straddles:** a straddle not filled within entry_ttl = 12 bars is cancelled and EXCLUDED from n (same as no signal). Fill-rate and cancel counts are reporting-only telemetry, never gates. |
| **D4** | **First-compression-bar gating:** the straddle fires only on the FIRST bar of a compression run (vol == COMPRESSION at setup ∧ prior bar NOT COMPRESSION) — no overlapping straddles from consecutive compression bars. |
| **D5** | **Stability split:** per-instrument chronological 50/50 split of valid decision bars (train = first half, test = second half). Program 4's calendar 2024/2025 split is impossible for FX (data starts 2025-10-06). |
| **D6** | **M15_REDUNDANT is a first-class Stage-1 FAIL verdict** (see Gate B) — recorded as such, never re-spun as "informative." |
| **D7** | **Sole-consumer rule:** `compression_box_straddle` is the ONLY permitted Stage-2 consumer. Program 9 closes immediately upon its verdict. No alternative consumers, payoff structures, box definitions, TTL variants, or execution architectures may be tested under Program 9 — a straddle-v2 sweep is parameter archaeology disguised as ontology exploration and requires a NEW pre-registration. |

## Program-9 closure rule

Program 9 is declared **CLOSED** once 9a **and** 9b **and** 9c each resolve to either
(Stage-1 FAIL — including `M15_REDUNDANT`) **or** (Stage-1 PASS + the Stage-2 verdict of the
sole consumer, whatever it is), under the fixed standard above. After closure, no further
M5-base multi-TF work may be promoted without new data, a new market domain, or a new ontology
(mirrors the Program-1 and Program-4 closures). D7 applies during the program as well: there is
no within-program iteration.

## Epistemic Integrity 6-question pre-check (per E-001)

1. **What artifact supports a future claim?** The deterministic Stage-1 JSON
   (`results/research/m5_mtf/m5_mtf_information.json`) + Stage-2
   (`results/research/m5_mtf/qualify_m5_straddle.json`), both byte-reproducible across double
   runs (seeded permutations, no wall-clock in bodies). No claim without a file:line citation.
2. **Could INSUFFICIENT explain it?** Yes — first-bar-of-compression events are sparser than
   compression bars, and OCO cancellations (D1/D3) shrink n further. Underpowered cells and
   scopes make NO claim (INSUFFICIENT, n < 30), never a verdict.
3. **Am I upgrading sign noise into meaning?** Guarded: IG significance at M5 sample sizes
   (≈210k bars/instrument) is even more N-saturated than F-020's M15 case — Gate B exists
   precisely to prevent "significant therefore new," and Stage-2, not Stage-1, is the only
   promote authority.
4. **Statistical or economic?** Explicitly separated: Stage 1 = information (Level 1), Stage 2 =
   economic (Level 2). A Stage-1 PASS — even UNIVERSAL — earns docs/research only, never
   sizing/fusion/production weight.
5. **Parent stronger than children?** The rollup asserts E-001E: a "M5 adds information" parent
   claim requires powered supporting cells; all-INSUFFICIENT ⇒ INSUFFICIENT, not a verdict.
6. **Would I phrase it differently after raw counts?** The report prints n per cell, per scope,
   per stage, plus fill/cancel counts; verdicts are written only after inspecting those counts.

## Expected outcome (prior, not a result)

`M15_REDUNDANT` ≈ 40% · other Stage-1 FAIL ≈ 20% · Stage-1 PASS + Stage-2 FAIL ≈ 30% ·
Stage-1 PASS + Stage-2 PASS ≈ 10%. Rationale: vol memory is strong at every timeframe (F-030,
H_atr ≈ 0.885), so the M5 conjunction will very likely clear Gate A — the live question is
Gate B (is the M5 refinement NEW?) and, if so, whether an OCO construction can monetize what
directional entries could not (F-040). All four outcomes are findings; the deliverable is a
definitive closure, not a strategy.

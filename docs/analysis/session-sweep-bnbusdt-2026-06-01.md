# Session Sweep — BNBUSDT M15 (Phase 6c empirical-throughput floor)

> Point-in-time analysis (NOT a living doc) · 2026-06-01 · config `v2_multi_2026_04 - deepdeektry`
> Harness: `scripts/analysis/session_sweep.py` · Results: `results/session_sweep/*.json`
> Purpose: the empirical half of the **Trd-M6 entry gate** — can session expansion produce a
> materially larger, still-profitable trade sample than the 15-trade baseline?

## Context

The Phase 6b funnel diagnosis (`roi-funnel-diagnosis-bnbusdt-2026-05-30.md`) showed the binding
throughput constraint is the **post-score SESSION filter** (64 of 93 `FILTER_REJECTED` are
session rejects: 44 OFF_SESSION + 20 ASIA), **not** the score gate (134/135 retests approved).
This sweep measures the session lever directly, **measure-only** (no config edit, no promotion),
gated on the existing quality gates — no objective change, no threshold relaxation.

**Lever:** session-NAME membership in `CRTConfig.allowed_sessions` (the mechanism
`p3b_session_relax_diag.py` uses). Construction mirrors that script
(`load_prod_config_from_registry` → `dataclasses.replace`) so V0 is faithful to the baseline.

## Method — staged experiment with attribution

Variants run one at a time (V0 first, analyze between), proposed floor **≥40 trades & PF ≥ 1.5**:

| Variant | `allowed_sessions` |
|---|---|
| V0 baseline | `LONDON, NEWYORK, OVERLAP` |
| V1 +ASIA | + `ASIA` |
| V2 +OFF_SESSION | + `OFF_SESSION` |
| V3 +both | + `ASIA, OFF_SESSION` |
| V4 all | full label universe (= V3, see below) |

## V0 baseline — HARD GATE: **PASS**

V0 reproduced the published baseline **exactly**: 15 trades / PF 1.7929 / ROI +4.91% / MAR 2.38 /
maxDD 2.07% (`roi-baseline-bnbusdt-2026-05-29.md`). The harness is trustworthy; deltas are real.

## BNBUSDT results

| variant | trades | Δ | WR | avg_R | PF | ROI | MAR | maxDD | fitness | gates |
|---|---|---|---|---|---|---|---|---|---|---|
| V0 baseline | 15 | — | 60% | +0.328R | 1.79 | +4.91% | 2.38 | 2.07% | 0.569 | PASS |
| V1 +ASIA | 23 | +8 | 65% | — | 2.54 | +13.29% | 6.40 | 2.08% | — | — |
| V2 +OFF_SESSION | 27 | +12 | 63% | — | 2.14 | +12.27% | 4.06 | 3.02% | — | — |
| **V3 +both** | **35** | **+20** | **66%** | **+0.545R** | **2.54** | **+20.59%** | **6.65** | **3.10%** | **0.686** | **PASS** |
| V4 all | 35 | +20 | 66% | +0.545R | 2.54 | +20.59% | 6.65 | 3.10% | 0.686 | PASS |

### Findings (attribution)
1. **Additive composition.** ASIA (+8) and OFF_SESSION (+12) compose **exactly** (+20 → 35). No
   destructive interaction.
2. **35 is the hard session ceiling.** V4 (allow every session label) == V3 — the session
   universe is exactly `{LONDON, NEWYORK, ASIA, OFF_SESSION}`. **Session expansion cannot exceed
   35 trades** on BNBUSDT/2yr; beyond this the bottleneck moves *up* the funnel (detection /
   RETEST supply), which sessions cannot fix.
3. **Quality improved, not degraded.** PF 1.79→2.54, avg_R +0.328→+0.545R, WR 60%→66%, ROI 4×,
   MAR 2.38→6.65, maxDD ~flat (2.07%→3.10%). "Rejects ≠ profitable trades" held favorably here:
   20 ASIA rejects yielded 8 high-quality trades.
4. **ConfigValidator hard+soft gates: PASS for BNBUSDT V3** (trades 35≥10, DD 3.10%≤35%,
   fitness 0.686≥0.3, WR 66%≥35%, expectancy +0.545R≥−0.5R). *(Computed from measured metrics;
   a formal `ConfigValidator.validate()` run is the pre-promotion step — see Caveats.)*

## Cross-instrument generalization (V3) — **NOT universal**

| instrument | V0 | V3 (+ASIA+OFF) | verdict |
|---|---|---|---|
| **BNBUSDT** | 15 / PF 1.79 / +4.91% | 35 / PF **2.54** / +20.59% | strongly positive |
| **SOLUSDT** | 6 / PF 0.29 / −2.85% | 29 / PF **1.17** / +2.40% | flips losing → profitable |
| **ETHUSDT** | 9 / PF 1.73 / +2.22% | 28 / PF **1.11** / +1.37% (maxDD 3.05%→6.88%) | **degrades** |
| **BTCUSDT** | 9 / PF 0.42 / −4.14% | 23 / PF 0.86 / −2.39% | unprofitable both ways |

**Session expansion is instrument-specific.** It is strongly positive for BNBUSDT, rehabilitates
SOLUSDT, but **degrades ETHUSDT** (PF toward 1, drawdown doubles) and BTCUSDT is unprofitable
regardless. A **blanket global** `allowed_sessions` change is therefore **not supported** — the
ConfigValidator cross-instrument-variance soft gate would (correctly) flag it.

## Floor verdict

- **PF floor (≥1.5): cleared decisively** — BNBUSDT V3 PF 2.54.
- **Trade floor (≥40): NOT reachable via sessions alone** — the session ceiling is **35**
  (5 short). 40+ requires attacking the *next* funnel bottleneck (detection / RETEST supply),
  which is out of scope here.
- **Spirit of the floor (materially larger, still-profitable):** **met for BNBUSDT** — +133%
  throughput (15→35) with *improved* quality. Operator's call whether 35 @ PF 2.54 clears the
  Trd-M6 admission bar or whether the literal ≥40 must be reached first.

## Recommendation (measure-only — no promotion this pass)

1. **BNBUSDT: adopt V3 sessions (`+ASIA, +OFF_SESSION`)** — a clean, no-code, no-new-intelligence
   win (+133% trades, PF 1.79→2.54, ROI 4×, DD flat).
2. **Do NOT apply globally.** Promotion must be **instrument-scoped** (BNBUSDT, and likely
   SOLUSDT) — never a blanket `allowed_sessions` change, given ETHUSDT degradation.
3. **Promotion delta (for the separate, gated step):** keep `engine_runner.allowed_sessions`
   consistent with `crt_engine.allowed_sessions` (the dual-enforcement nuance), run the formal
   `ConfigValidator.validate()` / `PromotionManager` path with an APPROVE report. **Not done
   here** (out of scope).

## Strategic read (informs Trd-M6 priority)

The funnel already approves 134/135 retests — detection/scoring/fusion *produce* opportunities;
the engine discarded them via a **temporal (session) policy** that, for BNBUSDT/SOLUSDT, was
**too conservative**. The recovered windows are **profitable**, so the next BNBUSDT gain is
**market-coverage expansion, not more intelligence** — **Trd-M6 becomes optimization, not
necessity** for this instrument. *However*, ETHUSDT/BTCUSDT show the edge is **instrument-
specific**: the broader open problem is **edge quality on some instruments**, not throughput, and
not something scenario-aware decisioning (Trd-M6) obviously fixes. **Next-investment decision:**
ship instrument-scoped session expansion (cheap, high-ROI) before any Trd-M6 investment; treat
ETH/BTC edge as a separate research question.

## Caveats
- **Construction-path note:** the harness builds the candidate via
  `load_prod_config_from_registry` + `replace(allowed_sessions=...)`. `ConfigValidator`'s
  `_params_to_crt_config` builds a CRTConfig from a flat params dict (defaults for unspecified) —
  a *different* path. The gate verdict above is computed from the harness's measured metrics; a
  formal pre-promotion `ConfigValidator.validate()` must pass the full prod params + the session
  override so its backtest matches.
- Measure-only: writes only `results/session_sweep/` + this doc. No config edit, no re-hash, no
  promotion.

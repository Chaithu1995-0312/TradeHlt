# B2A — Candidate-Formula Certification (FM-030 / FM-031)

_Generated 2026-07-12T09:14:16.158257+00:00 · method 1.0.0 · READ-ONLY._

**Overall verdict: `PROMOTE`**

> research/governance only — PROMOTE = B2B-eligibility for candidate math ONLY; decision impact UNKNOWN; economic value UNKNOWN; activation authority NONE

> Scope: observe-only; touches no registered impl, engine, config, or model; canonical vector stays 38-dim; PRODUCTION_BEHAVIOR_CHANGED = NO. After B2A, stop — B2B regenerates all downstream-impact evidence.

## Per-feature certification

| Candidate | Verdict | 3-path | scalar↔vector | NaN/Inf | scale-invariant | PIT |
|---|---|---|---|---|---|---|
| `ema_spread_atr` | **PROMOTE** | True | True | True/inf=0 | True (err=9.66e-14) | True |
| `momentum_score_atr` | **PROMOTE** | True | True | True/inf=0 | True (err=1.98e-14) | True |

Corpus arms: synthetic_1200, BNBUSDT_M15, BTCUSDT_M15, ETHUSDT_M15, SOLUSDT_M15.

Three cross-checked reconstruction paths (A independent raw-OHLC float64 · B linked `atr_relative*close` · C legacy-column identity `legacy/close`) agree within float32 tolerance; independent SMA14(TR) == pipeline `atr_14_raw`.

## Downstream diagnostics — NON-AUTHORITATIVE

> The block below is DIAGNOSTIC ONLY (authority: none) and is NOT an input to the verdict. All prior behavioral / decision-impact / economic / cross-instrument evidence for these formulas is treated as UNKNOWN for certification. Fresh B2B must regenerate it from the certified candidate semantics.
- legacy `ema_spread` scale ratio ×100/×1 ≈ 100.0 (the defect FM-030/031 corrects)
- legacy `momentum_score` scale ratio ×100/×1 ≈ 100.0 (the defect FM-030/031 corrects)

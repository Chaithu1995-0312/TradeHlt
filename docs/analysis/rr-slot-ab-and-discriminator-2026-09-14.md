# rr-slot A/B + discriminator analysis — XAUUSD frozen corpus (2026-09-14)

> OBSERVATION ONLY. No train. No promote. No production-config mutation.
> Research authority. Baseline sealed in a separate session-log entry.

## Scope

Sequential follow-ups on the sealed four-engine `fusion_compute` baseline
(`results/model_runners/fusion_compute/XAUUSD/20260914T072116Z/`, scores.jsonl
sha256 `bfa74ce43517…`):

1. **rr-slot A/B** — compare the fused score with the live candle-polarity `rr`
   slot (baseline) vs the same fusion with the non-quarantined 39-dim XAUUSD
   `rr_trained` artifact (`models/XAUUSD/20260728_v39/rr_model_20260728_v39_xau.json`)
   in the `rr` slot. Same static weights (`crt .4, gaussian .2, zone_gate .2, rr .2`),
   same frozen corpus (`data/mt5/XAUUSD_M15.csv`, sha256 `4d73f5ce…`).
2. **Discriminator analysis** — what drives the fused mean, and does any engine or
   fusion weighting discriminate next-bar direction?

Ground-truth label = sign of forward return at horizons H ∈ {1, 4} bars, computed
from the frozen OHLCV.

## Schema note (governed change)

`src/research/model_runners/schema_resolver.py` freeze-pins the registry id
`canonical_39` as **the live schema (48-dim)**. The only XAUUSD trained-RR artifact
declares `canonical_39` but is the 39-dim v4 generation, so it could not load
against the 48-dim corpus. Resolved **additively** (no freeze waived): added a new
registered schema id **`canonical_39_v4`** (39-dim v4 == live 48 minus the 9 v5.0-only
dims; keeps `macd_hist_raw`/`macd_hist_z`) and routed `rr_trained._ARTIFACT_SCHEMA_TO_ID`
`canonical_39 → canonical_39_v4`. `canonical_39` stays 48-dim. `gaussian_ml`
(`resolve_declared`) and `envelope_net` (`legacy_38_env`) untouched.
Tests updated (registry now four generations; new `test_canonical_39_v4_…`).

The quarantined canonical `models/rr_model.json` (canonical_38 v3,
SCHEMA-V4-VECTOR-MIGRATION) remains **excluded**.

## Step 1 — rr-slot A/B (`scripts/research/ab_rr_slot_xauusd.py`)

Aligned `n = 47197` bars (timestamp-exact). Recomposed fused score reproduces the
baseline `final_score` to `max|Δ| = 4.0e-05` (weights path verified).

| variable | mean | p50 | σ | range |
|---|---|---:|---:|---|
| fused (live-RR slot) — baseline | 0.6466 | 0.6392 | 0.0694 | [0.4434, 0.8993] |
| fused (rr_trained slot) | 0.5935 | 0.5781 | 0.0608 | [0.4270, 0.8049] |
| rr_live_polarity (component) | 0.7627 | 0.7676 | 0.1455 | [0.5000, 1.0000] |
| rr_trained (component) | 0.4974 | 0.4969 | 0.0062 | [0.4821, 0.5508] |

- **`rr` slot pair: pearson 0.014, spearman 0.006** → live candle-polarity and the
  trained RR are essentially unrelated on this corpus.
- **fused pair: pearson 0.908, spearman 0.884** → the two fusions are highly
  correlated despite the unrelated `rr` inputs (CRT/Gaussian/Zone carry 0.8 of the
  weight and are unchanged).
- The trained RR is **degenerate** here: near-constant `0.497` (σ 0.006), raw
  `confidence ≈ 1e-9`. Swapping it in only drags the fused mean 0.6466 → 0.5935.

**Discrimination vs direction (AUROC):**

| fusion variant | h1 AUROC | h4 AUROC |
|---|---:|---:|
| live-RR fused | 0.4959 | 0.4921 |
| rr_trained fused | 0.4973 | 0.4908 |

Neither variant predicts direction (≈ chance). The trained-RR swap neither helps
nor materially harms — it just reprices the constant floor.

## Step 2 — discriminator analysis (`scripts/research/discriminator_analysis_xauusd.py`)

**Per-engine AUROC / Spearman vs direction:**

| engine | h1 AUROC | h1 ρ | h4 AUROC | h4 ρ |
|---|---:|---:|---:|---:|
| crt | 0.4981 | −0.0023 | 0.4918 | −0.0131 |
| gaussian | 0.5001 | −0.0029 | 0.5009 | −0.0047 |
| zone_gate | 0.4957 | −0.0116 | 0.4952 | −0.0163 |
| rr_live_polarity | 0.4954 | −0.0052 | 0.4990 | 0.0037 |
| rr_trained | 0.5039 | 0.0111 | 0.5055 | 0.0150 |

All ≈ chance (0.49–0.51). **No engine discriminates next-bar direction** on this
feature set/corpus.

**Gaussian flatness:** mean 0.8827, σ 0.0049, range [0.8789, 1.0]; corr(gaussian →
fused) ≈ −0.014. The Gaussian is a near-fixed additive term: it contributes ≈
0.2 × 0.883 ≈ 0.177 to the 0.6466 mean with no discrimination.

**Component correlation (Pearson):** crt–zone = −0.32, zone–rr_trained = −0.40,
gaussian↔everything ≈ 0, rr_live↔rr_trained ≈ 0.01.

**Weight sensitivity (fused variants, live-RR slot):**

| variant | mean | σ | h1 AUROC | h4 AUROC |
|---|---:|---:|---:|---:|
| base (crt .4/g .2/z .2/rr .2) | 0.6466 | 0.0694 | 0.4959 | 0.4921 |
| no-Gaussian (renormalized) | 0.5876 | 0.0868 | 0.4958 | 0.4921 |
| uniform (0.25 each) | 0.7041 | 0.0545 | 0.4944 | 0.4924 |
| CRT-only | 0.4166 | 0.1601 | 0.4981 | 0.4918 |

Dropping the flat Gaussian lowers the mean (0.6466 → 0.5876) and widens spread but
**does not change discrimination** (still ≈ chance). Every weighting lands ≈ 0.49–0.50.

## Bottom line

- The **0.6466 fused mean is not a signal of predictive skill**: it is the sum of a
  flat Gaussian (≈0.177), CRT (≈0.167), Zone (≈0.151) and live-RR (≈0.153), none of
  which predicts next-bar direction.
- The **live `rr` slot (candle-polarity) and the trained RR are unrelated**; the trained
  RR is degenerate on this corpus, and swapping it in just lowers the constant floor.
- **No fusion weighting or single engine achieves AUROC above ≈0.51** on direction —
  a clean null result for this feature set / frozen corpus.

## Artefacts

- `results/research/ab_rr_slot_XAUUSD_20260914T094234Z.json`
- `results/research/ab_rr_slot_aligned_XAUUSD_20260914T094234Z.jsonl` (per-bar:
  components + both fused variants + forward returns)
- `results/research/discriminator_XAUUSD_20260914T094648Z.json`
- `results/model_runners/rr_trained/XAUUSD/20260914T093317Z/` (run + manifest)

# Feature Semantic Adjudication — PASS A

Generated (UTC): `2026-07-10T15:22:57Z`

**Read-only. No remediation. No promotion. No economic claims.**

## Binding

```json
{
  "require_phase1_frozen_candidate": "PASS",
  "path": "data/mt5/XAUUSD_M15.csv",
  "sha256": "4d73f5cebe33ec91c5312340337eb62c2cf1f49060c91c42761bf631b26aba56",
  "rows": 47275,
  "range": [
    "2024-05-22T01:00:00",
    "2026-05-21T23:45:00"
  ],
  "status": "FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION"
}
```

## Target verdicts

- **TARGET_A_SWING_PIT_STATUS** = `MIXED_BY_CALL_SITE`
- **TARGET_B_VOLUME_SEMANTIC_STATUS** = `MIXED_BY_CORPUS`
- **TARGET_C_FORMULA_AUTHORITY_STATUS** = `FORMULA_IDENTITY_DIVERGENT`
- **TARGET_D_VOLATILITY_REGIME_PIT_STATUS** = `GLOBAL_FIT_DEPENDENCE`
- **FEATURE_SEMANTIC_ADJUDICATION_PASS_A_STATUS** = `COMPLETE`

## Target A — Centered swing

- Window: SWING_WINDOW=2 → rolling width 5, future bars k=2
- Algorithm: swing_high[t]=1 iff high[t]==max(high[t-k:t+k+1]) with center=True, min_periods=5; swing_low analogous on low
- Math ID time: t+k (after future window closes)
- Publication default: written at row index t in batch (retrospective)
- Delay enforced default: False
- Direct: ['swing_high', 'swing_low']
- Transitive structure: ['higher_high', 'lower_low', 'break_of_structure', 'liquidity_sweep', 'sweep_detected', 'double_sweep', 'liquidity_distance', 'liquidity_pressure_score']
- Transitive retest chain: ['retest_depth', 'candles_since_retest']
- Membership count (code-derived): **12**
- Prefix invariance (swing_high): {'n': 130, 'mismatch': 23, 'samples': [{'t': 3200, 'ts': '2024-07-10 03:30:00', 'full': 1.0, 'prefix': 0.0}, {'t': 8000, 'ts': '2024-09-20 10:00:00', 'full': 1.0, 'prefix': 0.0}, {'t': 8800, 'ts': '2024-10-03 03:00:00', 'full': 1.0, 'prefix': 0.0}, {'t': 14400, 'ts': '2024-12-30 08:00:00', 'full': 1.0, 'prefix': 0.0}, {'t': 15200, 'ts': '2025-01-13 01:00:00', 'full': 1.0, 'prefix': 0.0}, {'t': 15600, 'ts': '2025-01-17 09:00:00', 'full': 1.0, 'prefix': 0.0}, {'t': 16800, 'ts': '2025-02-05 12:30:00', 'full': 1.0, 'prefix': 0.0}, {'t': 18000, 'ts': '2025-02-24 16:00:00', 'full': 1.0, 'prefix': 0.0}], 'mismatch_rate': 0.17692307692307693, 'verdict_hint': 'LEAKING'}
- Causal env: {'swing_high_match': True, 'note': 'causal shift path only when TRUST_SWING_CAUSAL=1; production default OFF'}

## Target B — Volume

- MT5 field: tick_volume → CSV column 'volume' (mt5_candle_fetcher.py:195)
- XAU unchanged through pipeline: True
- T-003 activates on all-zero mutant: True
- Production semantic detector: False

## Target C — disp/retest formula authority

- Pipeline disp: clip(body_size / (atr * close), 0, 3)
- Pipeline retest: if retest_flag: clip(|close-ema_fast|/(atr*close),0,1) else 0.0
- CRT: FM-027/FM-028 with BitNet alias map to retest_depth/disp_strength keys
- FM-020 vs FM-028 different samples: 5
- Secondary: ['ARTIFACT_BINDING_MISSING']

## Target D — volatility_regime

- Default formula: atr_pct = atr_14.rank(pct=True) GLOBAL over full DataFrame; regime = 0 if pct<0.33 else 1 if pct<0.66 else 2
- Prefix invariance: {'volatility_regime': {'n': 91, 'mismatch': 39, 'samples': [{'t': 3000, 'ts': '2024-07-05 22:30:00', 'full': 0.0, 'prefix': 1.0}, {'t': 4000, 'ts': '2024-07-22 19:30:00', 'full': 1.0, 'prefix': 2.0}, {'t': 4500, 'ts': '2024-07-30 06:30:00', 'full': 0.0, 'prefix': 1.0}, {'t': 5000, 'ts': '2024-08-06 16:30:00', 'full': 1.0, 'prefix': 2.0}, {'t': 6000, 'ts': '2024-08-21 13:30:00', 'full': 0.0, 'prefix': 1.0}, {'t': 7000, 'ts': '2024-09-05 13:00:00', 'full': 0.0, 'prefix': 1.0}, {'t': 7500, 'ts': '2024-09-12 23:00:00', 'full': 0.0, 'prefix': 1.0}, {'t': 8000, 'ts': '2024-09-20 10:00:00', 'full': 0.0, 'prefix': 1.0}], 'mismatch_rate': 0.42857142857142855, 'verdict_hint': 'LEAKING'}}
- Future mutation equal_at_t: True
- Default vs expanding disagreement: {'different': 21672, 'n': 47275}

## Adversarial coverage

```json
{
  "failure_classes_registered": 8,
  "canonical_seeds_defined": 8,
  "detectors_implemented": 4,
  "clean_path_probes_run": 4,
  "clean_path_probes_green": 4,
  "mutants_run": 6,
  "mutants_killed": 4,
  "mutation_score": "NOT_COMPLETE",
  "detector_gaps": [
    "no runtime volume_semantic contract detector",
    "no formula-id binding on model artifacts for FM-020 vs FM-028",
    "no default production guard for centered-swing lookahead",
    "no default production guard for global vol regime rank",
    "E-MT-01 OHLCV temporal classes still open"
  ],
  "probes": [
    {
      "id": "A_PREFIX",
      "clean": "prefix==full on causal features",
      "mutant": "center swing fails prefix invariance",
      "result": "MIXED_BY_CALL_SITE"
    },
    {
      "id": "A_FUTURE_MUT",
      "mutant": "mutate high after t changes swing at t",
      "result": {
        "swing_high": {
          "equal_at_t": false,
          "base": 1.0,
          "mutated": 0.0
        },
        "swing_low": {
          "equal_at_t": true,
          "base": 0.0,
          "mutated": 0.0
        },
        "higher_high": {
          "equal_at_t": true,
          "base": 1.0,
          "mutated": 1.0
        },
        "lower_low": {
          "equal_at_t": true,
          "base": 0.0,
          "mutated": 0.0
        },
        "break_of_structure": {
          "equal_at_t": true,
          "base": 0.0,
          "mutated": 0.0
        },
        "liquidity_sweep": {
          "equal_at_t": true,
          "base": 1.0,
          "mutated": 1.0
        },
        "sweep_detected": {
          "equal_at_t": true,
          "base": 1.0,
          "mutated": 1.0
        },
        "double_sweep": {
          "equal_at_t": true,
          "base": 0.0,
          "mutated": 0.0
        },
        "liquidity_distance": {
          "equal_at_t": true,
          "base": 0.11650023609399796,
          "mutated": 0.11650023609399796
        },
        "liquidity_pressure_score": {
          "equal_at_t
```

## What this does NOT prove

- Feature layer closed
- All 38 features validated
- Economic usefulness
- E-MT-01 complete
- Phase-2 complete
- XAUUSD AUTHORITATIVE promotion

Companions: availability graph, formula call-site binding, adversarial matrix JSON.

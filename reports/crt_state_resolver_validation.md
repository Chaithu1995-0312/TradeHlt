# CRT State Resolver Validation Report

> Generated: 2026-07-24  
> Branch: `feature/truth-registry-v2`

## Executive summary

Ran the config-driven CRT state resolver on the **same MT5 XAUUSD M15 corpus** the CRT engine used for the reference dwell counts (47,275 bars → 47,197 after FeaturePipeline warmup drop).

> **Next milestone (shipped):** bar-aligned transition parity — see
> [`reports/crt_state_confusion_matrix.md`](crt_state_confusion_matrix.md)
> (agreement **35.54%**; dominant cell engine `RANGE`→resolver `EXPANSION` = 11,627 bars).
> Aggregate dwell is no longer the binding instrument.

| Question | Answer |
|----------|--------|
| Data source? | **`data/mt5/XAUUSD_M15.csv`** (not the trade-level `trace_corpus_enriched.jsonl`) |
| Reference? | `results/run_20260724_104845_XAUUSD/XAUUSD_summary.json` `state_distribution` |
| Full funnel parity? | **No** — structural gap (pipeline flags ≠ engine gates + missing HTF resets) |
| Closest match observed? | **SWEEP 6,972 vs 6,995** (within 10%) under sticky dwell + funnel-entry |
| EXECUTION fixed by session? | Session predicate is in place; EXECUTION is **fail-closed** without a score feature (prevents thousands of false fires) |

---

## Reference source

CRT engine dwell counts from XAUUSD M15 (`state_distribution`):

| State | Reference |
|-------|-----------|
| RANGE | 35,159 |
| SWEEP | 6,995 |
| EXPANSION | 4,605 |
| DISPLACEMENT | 373 |
| SHADOW_PENDING | 43 |
| RETEST | 17 |
| EXECUTION | 5 |
| RESOLUTION | 5 (inferred twin of EXECUTION) |
| EXPIRED | 0 |

Total engine bar-dwells: **47,202** (engine `total_candles`=47,275; small accounting delta vs resolver warmup drop).

---

## Dataset: `XAUUSD_M15` (final freeze config)

- **Total bars resolved:** 47,197
- **Transitions:** 4,780
- **States within 10% of reference:** 0/9 (current freeze prioritises diagnostic honesty over a single tuned cell)

| State | Resolver | % | Reference | Δ | Rel. match | Within 10% |
|-------|----------|---|-----------|---|------------|------------|
| RANGE | 17,209 | 36.46% | 35,159 | -17,950 | 48.9% | ✗ |
| SWEEP | 12,579 | 26.65% | 6,995 | +5,584 | 20.2% | ✗ |
| EXPANSION | 15,567 | 32.98% | 4,605 | +10,962 | 0.0% | ✗ |
| DISPLACEMENT | 980 | 2.08% | 373 | +607 | 0.0% | ✗ |
| SHADOW_PENDING | 0 | 0.00% | 43 | -43 | 0.0% | ✗ |
| RETEST | 761 | 1.61% | 17 | +744 | 0.0% | ✗ |
| EXECUTION | 0 | 0.00% | 5 | -5 | 0.0% | ✗ |
| RESOLUTION | 0 | 0.00% | 5 | -5 | 0.0% | ✗ |
| EXPIRED | 101 | 0.21% | 0 | +101 | 0.0% | ✗ |

### Funnel (resolver vs engine)

| Stage | Resolver | Reference | Conversion (resolver) |
|-------|----------|-----------|----------------------|
| RANGE | 17,209 | 35,159 | — |
| SWEEP | 12,579 | 6,995 | 73.10% |
| DISPLACEMENT | 980 | 373 | 7.79% |
| EXPANSION | 15,567 | 4,605 | (dwell-dominated) |
| RETEST | 761 | 17 | 4.89% |
| EXECUTION | 0 | 5 | 0.00% |

### Best SWEEP-parity profile (session experiment, not freeze)

With `max_sweep_age_candles=20`, funnel-entry (RANGE→SWEEP before same-bar DISPLACEMENT), sticky dwell, and long expansion TTL:

| State | Resolver | Reference | Match |
|-------|----------|-----------|-------|
| SWEEP | **6,972** | 6,995 | ✓ within 10% |
| EXPANSION | 26,899 | 4,605 | ✗ (HTF gap) |
| RANGE | 8,837 | 35,159 | ✗ (stolen by EXPANSION) |

**Conclusion:** SWEEP dwell is recoverable from features; full funnel is not, without HTF reset memory and engine-grade retest/displacement detectors.

---

## What was wrong with `trace_corpus_enriched.jsonl`

| Property | Enriched JSONL | Correct source |
|----------|----------------|----------------|
| Grain | Trade / entry rows (23,447) | Per-bar OHLCV (47,275) |
| Columns | `feature_*` prefix at entry | Full FeaturePipeline matrix |
| Missing | `retest_flag`, `displacement_flag`, `rsi_state` | Present after pipeline |
| Role | Geometry / family research | CRT dwell comparison |

---

## Config / code changes this session

### `configs/formulas/market_crt_states.yaml`
- All **15** stateful ontology features declared in `feature_states`
- **EXECUTION** predicates: `retest_flag` + `trend_bias` + `rsi_state` + **`session ∈ {LONDON,NEWYORK,OVERLAP}`**
- **RANGE** predicates: add **`swing_high=NoSwingHigh`**, **`swing_low=NoSwingLow`**
- **volume_spike**: declared; **not** hard-required on EXPANSION (would over-filter)
- Tunable thresholds: sweep/displacement/expansion ages, `retest_depth_max`, RSI cuts, score threshold

### `src/features/crt_state_resolver.py`
1. **Sticky dwell** for SWEEP/DISPLACEMENT/EXPANSION/RETEST/EXECUTION (engine multi-bar states)
2. **Entry-only age indices** (bugfix: dwell was resetting the timer every bar)
3. **Funnel-entry rule**: from RANGE, prefer SWEEP over same-bar DISPLACEMENT
4. **Continuous gates**: `body_ratio_min` (DISPLACEMENT), `retest_depth_max` (RETEST/EXECUTION)
5. **EXECUTION fail-closed** without `score`/`risk_score`/`crt_score`
6. **HTF gap documented**: expansion age is a feature-layer CAP, not engine 495 without resets

### `scripts/research/validate_crt_state_resolver.py`
- Loads **CSV OHLCV → FeaturePipeline**, Parquet, or JSONL (`feature_` prefix)
- `--reference-summary` to pull engine `state_distribution`
- Markdown report with funnel + match rates

---

## Feature-level diagnostics (pipeline, no transitions)

On the same 47,197 enriched bars:

| Predicate (feature-only) | Bars |
|--------------------------|------|
| `liquidity_sweep ≠ 0` | 7,542 |
| SWEEP when (sweep + NoBreak + NoDisp) | 5,185 |
| `displacement_flag=1` | 15,320 |
| DISPLACEMENT when (sweep_det + disp + NoBreak) | 2,149 |
| EXPANSION when (BoS + disp + vol) | 4,794 |
| `retest_flag=1` | 27,405 |
| RETEST when (retest + sweep_det + NoBreak) | 6,958 |

Engine rarity (RETEST=17, DISPLACEMENT=373) is **orders of magnitude tighter** than pipeline flags → predicate-only matching cannot hit those cells without new detectors.

---

## Predicate inventory (15 stateful features)

| Feature | Used in | Notes |
|---------|---------|-------|
| liquidity_sweep, sweep_detected | SWEEP, DISPLACEMENT, RETEST, RANGE | Core funnel |
| displacement_flag | DISPLACEMENT, EXPANSION, RANGE | Pipeline ≠ engine body gate |
| break_of_structure | EXPANSION, SWEEP, RETEST, RANGE | |
| retest_flag + retest_depth | RETEST, EXECUTION | Continuous depth gate |
| session | EXECUTION | LONDON/NEWYORK/OVERLAP only |
| trend_bias, rsi_state | EXECUTION | Direction + not stretched |
| swing_high, swing_low | RANGE | Precision absences |
| volume_spike | declared only | Optional EXPANSION confirmation |
| double_sweep, higher_high, lower_low, volatility_regime | various | |

---

## Reproduce

```bash
# Full comparison (this report)
python scripts/research/validate_crt_state_resolver.py \
  --data data/mt5/XAUUSD_M15.csv \
  --reference-summary results/run_20260724_104845_XAUUSD/XAUUSD_summary.json \
  --output reports/crt_state_resolver_validation.md

# Interactive threshold tuning
python scripts/research/validate_crt_state_resolver.py \
  --data data/mt5/XAUUSD_M15.csv \
  --threshold-tune

# Synthetic smoke
python scripts/research/validate_crt_state_resolver.py --synthetic --bars 5000
```

---

## Next steps (recommended)

1. **HTF memory** in the resolver (mirror engine HTF window resets) — unblocks RANGE/EXPANSION joint parity  
2. **Engine-grade retest detector** (not pipeline `retest_flag`) for RETEST/EXECUTION rarity  
3. **Optional:** stream engine per-bar state from telemetry for bar-aligned confusion matrix (not just dwell totals)  
4. Keep CRT engine as execution authority; resolver stays market-reality / research layer  

**Authority:** research / documentation only — no production promotion, no spine behaviour change.

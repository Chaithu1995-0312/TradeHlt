# 12-Bar Feature Screen — 1.5 ATR vs 1.0 ATR Outcome Race

- Bars loaded: **47275**
- Continuous segments: **517**
- Feature windows (fully inside a segment, 48-bar warm-up): **16289**

## Outcome distribution (next 12 bars)

| Outcome | Count | Share |
|---------|-------|-------|
| down | 5180 | 31.8% |
| ambiguous | 1871 | 11.5% |
| up | 5181 | 31.8% |
| neither | 4057 | 24.9% |

Base rate up-first among decided (up vs down) windows: **50.0%**
Unconditional up-first rate (all windows): **31.8%** (down-first 31.8%)

**Big-move AUC interpretation:** values far below 0.5 mean *low* feature values predict the move (inverse signal); values far above 0.5 mean *high* feature values predict it.

## Per-feature results

| # | Feature | Corr(dir) | Dir AUC | Big AUC | P(up|top20) | P(down|bot20) | Lift* |
|---|---------|-----------|---------|---------|-------------|----------------|-------|
| 1 | Wick imbalance | 0.015 | 0.515 | 0.551 | 35.3% | 30.3% | 1.109 |
| 2 | Range efficiency | 0.016 | 0.512 | 0.450 | 31.7% | 35.7% | 1.122 |
| 3 | Path efficiency | 0.009 | 0.509 | 0.484 | 32.1% | 34.3% | 1.078 |
| 4 | Vol-weighted direction | -0.003 | 0.499 | 0.504 | 30.9% | 30.7% | 0.972 |
| 5 | Up/down imbalance | 0.004 | 0.498 | 0.510 | 30.1% | 30.7% | 0.966 |
| 6 | Coil ratio | -0.014 | 0.492 | 0.318 | 23.1% | 35.3% | 1.111 |
| 7 | Net drift | -0.013 | 0.489 | 0.513 | 30.6% | 29.7% | 0.963 |
| 8 | Body share | -0.018 | 0.488 | 0.454 | 29.5% | 32.0% | 1.006 |
| 9 | Linear slope | -0.015 | 0.486 | 0.515 | 31.0% | 28.5% | 0.974 |
| 10 | Close position | -0.033 | 0.477 | 0.500 | 30.5% | 29.9% | 0.958 |

*Lift = max(P(up|top20), P(down|bot20)) / unconditional up-first rate. >1 means the extreme end of the feature beats the unconditional direction rate.

### Ranked by directional AUC (up-first vs down-first only)

1. **Wick imbalance** — AUC 0.515 (dir n=10361, big-move AUC 0.551) ✅ high feature values → move
2. **Range efficiency** — AUC 0.512 (dir n=10361, big-move AUC 0.450) ⚠️ **inverse** (low feature values → move)
3. **Path efficiency** — AUC 0.509 (dir n=10361, big-move AUC 0.484)
4. **Vol-weighted direction** — AUC 0.499 (dir n=10361, big-move AUC 0.504)
5. **Up/down imbalance** — AUC 0.498 (dir n=10361, big-move AUC 0.510)
6. **Coil ratio** — AUC 0.492 (dir n=10361, big-move AUC 0.318) ⚠️ **inverse** (low feature values → move)
7. **Net drift** — AUC 0.489 (dir n=10361, big-move AUC 0.513)
8. **Body share** — AUC 0.488 (dir n=10361, big-move AUC 0.454)
9. **Linear slope** — AUC 0.486 (dir n=10361, big-move AUC 0.515)
10. **Close position** — AUC 0.477 (dir n=10361, big-move AUC 0.500)

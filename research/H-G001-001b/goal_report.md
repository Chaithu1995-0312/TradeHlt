# H-G001-001b Goal Report

Generated: `2026-07-26T08:51:55Z`

## Corpus / standard

- Instrument: **XAUUSD** M15
- Corpus: `D:/Tradelatest/data/mt5/XAUUSD_M15.csv` (FROZEN_CANDIDATE_PENDING_PHASE1_VALIDATION)
- Span: **23.9823** months
- Exit: `intrabar_fixed` · cost **12.0** bps
- Lens: `crt_only_gate_off` (BACKTEST_ENGINE_GATE='0')
- Prod version: `v2_multi_2026_04`

## Metrics (net of costs)

| Metric | Baseline | Treatment | Δ (T−B) |
|---|---:|---:|---:|
| Trade count (n) | 1 | 1 | 0 |
| Trades / month | 0.0417 | 0.0417 | 0.0 |
| Win rate | 0.0 | 0.0 | 0.0 |
| Profit factor | 0.0 | 0.0 | 0.0 |
| Expectancy (R net) | -1.6923 | -1.6923 | 0.0 |
| Max DD (R) | 1.6923 | 1.6923 | 0.0 |

Veto removed **0** / 1 entries (rate=0.0).

## G001 GoalValidator (measure-only)

### Baseline decision: **FAIL** (enabled=True, enforced=False)

- `trades_per_month_min`: FAIL (actual=0.0417, target=20.0, gap=-19.9583)
- `trades_per_month_max`: PASS (actual=0.0417, target=80.0, gap=79.9583)
- `avg_rr_min`: FAIL (actual=-1.6923, target=2.0, gap=-3.6923)
- `win_rate_min`: FAIL (actual=0.0, target=0.35, gap=-0.35)
- `max_drawdown_pct_max`: SKIP (actual=None, target=0.1, gap=None)
- `expectancy_r_min`: FAIL (actual=-1.6923, target=0.2, gap=-1.8923)

### Treatment decision: **FAIL**

- `trades_per_month_min`: FAIL (actual=0.0417, target=20.0, gap=-19.9583)
- `trades_per_month_max`: PASS (actual=0.0417, target=80.0, gap=79.9583)
- `avg_rr_min`: FAIL (actual=-1.6923, target=2.0, gap=-3.6923)
- `win_rate_min`: FAIL (actual=0.0, target=0.35, gap=-0.35)
- `max_drawdown_pct_max`: SKIP (actual=None, target=0.1, gap=None)
- `expectancy_r_min`: FAIL (actual=-1.6923, target=0.2, gap=-1.8923)

## M4 qualification verdicts

- Baseline: `INSUFFICIENT`
- Treatment: `INSUFFICIENT`

## Interpretation guard

Semantic correctness of FM-058 is **not** re-tested here.
This report answers economic usefulness vs G001 only.
Corpus remains non-promotable for live authority.

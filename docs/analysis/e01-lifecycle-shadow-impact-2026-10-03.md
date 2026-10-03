# E01 lifecycle sweep: full-corpus ACTIVE vs shadow impact (2026-10-03)

> Point-in-time diagnostic evidence for **F-112** (`docs/current-findings.md`). Not activation
> evidence, not an economic finding, not a revalidation of any downstream finding.

## What was compared

| | ACTIVE | SHADOW |
|---|---|---|
| Config | `v2_htfcrt_2026_08` (`ACTIVE_VERSION`) | `v2_htfcrt_e01lifecycle_shadow_2026_10` (non-promoted) |
| `feature_pipeline.sweep_semantics` | `latest_unconsumed` (FM-058/059/060/065) | `e01_lifecycle` (FM-090..093) |
| params `config_hash` | `7de09f62…` | `7de09f62…` (identical; the switch is non-`params`) |

- Corpus: `data/mt5/XAUUSD_M15.csv`, 47,275 bars, 2024-05-22 01:00 → 2026-05-21 23:45 (broker time),
  sha256 prefix `4d73f5cebe33ec91`. Dataset integrity APPROVE (504 intra-session gaps, 0 missing).
- Code: branch `semanticos_impl` at `f2e44ae` plus the uncommitted CH-e01-lifecycle-sweep-identity
  working tree (see `docs/governance/build_manifests/CH-e01-lifecycle-sweep-identity.impact.json`).
- Runner: `backtest_v2.main()` through `semantics.integration.observe.plain_backtest`, the shadow
  selected with `observe.prod_version(...)` (patches `PROD_VERSION` in `config_layer.production_config`
  and `runtime.backtest_v2`, restores afterwards). Default fusion gate as configured.
- Run artifacts (session scratch, not tracked): `run_20261003_104612_..._v2_htfcrt_2026_08_7de09f62`
  and `run_20261003_104610_..._v2_htfcrt_e01lifecycle_shadow_2026_10_7de09f62`. The numbers below
  are copied from the comparison output; re-running the two commands reproduces them.

## Observed

CRT event stream, compared on (event, timestamp, state_from, state_to, direction, price):
**identical**, no divergence index.

| Event | ACTIVE | SHADOW |
|---|---:|---:|
| RESET | 2,888 | 2,888 |
| STATE_TRANSITION | 2,381 | 2,381 |
| SWEEP | 1,792 | 1,792 |
| BEGIN_SOFT_CONF | 24 | 24 |
| FILTER_REJECTED | 19 | 19 |
| CONFIRMATION_FAILED | 1 | 1 |
| TRADE_BUILD_REJECTED | 1 | 1 |
| TRADE_OPENED | 3 | 3 |
| TRADE_STOPPED | 2 | 2 |
| TRADE_TP1 / TRADE_TP2 | 1 / 1 | 1 / 1 |

Trades (same entries, directions, prices, outcomes and PnL in both runs):

| id | Opened | Dir | Entry | Outcome | TP1 ACTIVE | TP1 SHADOW |
|---|---|---|---:|---|---:|---:|
| CRT-0001 | 2024-11-12 15:30 | LONG | 2614.46 | STOPPED next bar | 2618.8724 | **2617.9899** |
| CRT-0002 | 2024-11-15 07:45 | LONG | 2565.48 | STOPPED next bar | 2566.8602 | 2566.8602 |
| CRT-0003 | 2025-02-25 15:45 | LONG | 2934.39 | TP1 then TP2 | 2936.1602 | 2936.1602 |

TP1 intent (`crt_engine_v2._derive_trade_intent`, read from `RETEST_REPLAY` telemetry): 24 retests
in each run, all 24 common. Intent changed on **2 of 24**; accepted/rejected changed on **0**.

| Retest | idx | Accepted | ACTIVE intent | SHADOW intent | Effect |
|---|---:|---|---|---|---|
| 2024-11-12 15:30 | 11364 | yes (CRT-0001) | `reversal` (TP1 ×1.0) | `pullback` (TP1 ×0.8) | TP1 price moved; trade stopped identically |
| 2025-08-14 17:30 | 29132 | no, `OFF_SESSION` | `liq_sweep` | `breakout` | none; rejected in both |

Intent mix: ACTIVE reversal 12 / breakout 11 / liq_sweep 1; SHADOW reversal 11 / breakout 12 / pullback 1.

Summary metrics: the only differing key is `distribution.metrics_v2.rr.avg_planned_rr`
1.333333 → 1.266667.

## Interpretation

The E01 lifecycle producer change **reaches the CRT TP1-intent path** (it changed the intent on 2
retests and one planned TP1 price) but **did not alter the trade ledger** on this two-year corpus.

```
E01 semantic fix
      |
feature projections (FM-090..093)
      |
      +-- CRT TP1-intent path ---> MEASURED here: small observed effect, ledger unchanged
      +-- gate_intelligence -----> NOT measured
      +-- trained-model inputs --> NOT measured
```

## Limitations

- Only 3 trades: says nothing about economic neutrality.
- `gate_intelligence` LIQ_SWEEP scoring was not compared.
- Trained-model consumption (ZoneGate / RR / TradeNet inputs) was not evaluated through this A/B.
- One instrument, one config.
- Telemetry gap: `RETEST_REPLAY.tp1_mult` records the base `tp1_atr_multiplier` (1.0), not the
  intent-specific multiplier `build_trade` uses; the trade event's `tp1` price is the correct value.

## Status

Diagnostic evidence only. No activation conclusion, no system-wide risk conclusion, no economic
conclusion. Activation stays a separate user decision; findings whose inputs would move under
activation must then be named for revalidation explicitly (memory: revalidate-findings-after-semantic-fixes).
